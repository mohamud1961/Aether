"""Run adapter: wire EnvMap + SubprocessExecutor + ModelHooks + Kernel into a single call."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Mapping

from .classifier import HarnessLimiterClassifier
from .envmap_builder import build_envmap_from_task
from .kernel import AetherNextKernel, KernelResult
from .model_hooks import ModelHooks, ModelCallable
from .model_interface import compact_model_interface_manifests
from .real_executor import SubprocessExecutor
from .result_metrics import run_metrics_for_row
from .run_cancellation import RunCancellationRequested
from .task_metadata_loader import load_task_metadata
from .task_contract import TaskClause, TaskContract
from .world import WorldState



def _load_task_toml(task_dir: str) -> dict[str, Any]:
    return load_task_metadata(task_dir)


def _receipt_records(result: KernelResult) -> list[dict[str, Any]]:
    return [{
        "receipt_id": receipt.receipt_id,
        "step": receipt.step,
        "kind": receipt.kind,
        "success": receipt.success,
        "summary": receipt.summary,
        "state_change": receipt.state_change,
        "failure_class": receipt.failure_class,
        "payload": dict(receipt.payload),
    } for receipt in result.receipts]


def _receipt_summary(result: KernelResult) -> list[dict[str, Any]]:
    return [{
        "receipt_id": receipt.receipt_id,
        "kind": receipt.kind,
        "success": receipt.success,
        "failure_class": receipt.failure_class,
        "summary": receipt.summary,
    } for receipt in result.receipts]

def _build_runtime_identity(
    *,
    task_dir: str,
    instruction_text: str,
    workspace_root: str,
    environment_id: str,
    max_steps: int | None,
    supplied: Mapping[str, Any] | None,
) -> dict[str, Any]:
    identity = {str(key): value for key, value in dict(supplied or {}).items()}
    task_id = str(identity.get("task_id") or Path(task_dir).name)
    run_id = str(identity.get("run_id") or f"run-{uuid.uuid4().hex}")
    primary_agent_id = str(
        identity.get("primary_agent_id") or f"primary-agent:{run_id}"
    )
    source_commit = str(
        identity.get("source_commit")
        or os.environ.get("AETHER_SOURCE_COMMIT", "")
    ).strip()
    runtime_manifest = str(
        identity.get("runtime_manifest_sha256")
        or os.environ.get("AETHER_RUNTIME_MANIFEST_SHA256", "")
    ).strip()
    budgets = dict(identity.get("budgets", {}) or {})
    budgets["max_kernel_steps"] = (max(1, int(max_steps)) if max_steps is not None else None)
    identity.update({
        "task_id": task_id,
        "run_id": run_id,
        "primary_agent_id": primary_agent_id,
        "workspace_id": str(Path(workspace_root).resolve()),
        "environment_id": environment_id,
        "raw_task_sha256": sha256(instruction_text.encode("utf-8")).hexdigest(),
        "source_commit": source_commit,
        "source_commit_state": "provided" if source_commit else "not_supplied",
        "runtime_manifest_sha256": runtime_manifest,
        "runtime_manifest_state": "provided" if runtime_manifest else "not_supplied",
        "source_custody_complete": bool(source_commit and runtime_manifest),
        "budgets": budgets,
    })
    return identity


def run_task(
    *,
    task_dir: str,
    instruction_text: str,
    solver_model: ModelCallable,
    verifier_model: ModelCallable,
    vision_model: Any | None = None,
    workspace_root: str = "/app",
    max_steps: int | None = 24,
    solver_max_output_tokens: int | None = 16000,
    verifier_max_output_tokens: int | None = 12000,
    runtime_identity: Mapping[str, Any] | None = None,
    executor: Any | None = None,
    envmap_override: Any | None = None,
    close_executor: bool = True,
    solver_reanchor_mode: str = "current_full",
    solver_context_mode: str = "full",
    cancellation_event: Any | None = None,
    run_timeout_s: float | None = None,
    run_started_monotonic: float | None = None,
) -> dict[str, Any]:
    """Execute a task end-to-end and return a JSON-serializable run record.

    Parameters
    ----------
    task_dir:
        Path to the task directory for building the EnvMap.
    instruction_text:
        The task instruction / prompt text.
    solver_model:
        Model callable for the solver role.
    workspace_root:
        Workspace root for the executor (default ``/app``).
    max_steps:
        Maximum kernel steps.

    Returns
    -------
    dict
        JSON-serializable run record.
    """
    if envmap_override is None:
        task_toml = _load_task_toml(task_dir)
        envmap = build_envmap_from_task(
            task_dir,
            instruction_text,
            workspace_root=workspace_root,
            task_toml=task_toml,
            projection_mode="factual_only",
        )
    else:
        envmap = envmap_override
        if str(getattr(envmap, "workspace_root", "")) != str(workspace_root):
            raise ValueError("envmap_override workspace_root does not match run workspace_root")

    resolved_executor = executor if executor is not None else SubprocessExecutor(workspace_root)
    resolved_runtime_identity = _build_runtime_identity(
        task_dir=task_dir,
        instruction_text=instruction_text,
        workspace_root=workspace_root,
        environment_id=envmap.digest(),
        max_steps=max_steps,
        supplied=runtime_identity,
    )
    # A cancellation event supplied to run_task is the task-lifecycle authority
    # for every model callable as well as the kernel. Harbor already performs
    # this binding before entering the adapter; repeat it here so direct adapter
    # callers cannot strand a blocking provider call outside cancellation
    # custody. Provider implementations treat rebinding to the same event as an
    # idempotent assignment.
    for model in (solver_model, verifier_model, vision_model):
        if model is None:
            continue
        bind_cancel = getattr(model, "bind_run_cancellation", None)
        if callable(bind_cancel):
            bind_cancel(cancellation_event)

    hooks = ModelHooks(
        solver_model,
        verifier_model,
        vision_model=vision_model,
        run_id=str(resolved_runtime_identity["run_id"]),
        task_id=str(resolved_runtime_identity["task_id"]),
        telemetry_identity=resolved_runtime_identity,
        solver_max_output_tokens=solver_max_output_tokens,
        verifier_max_output_tokens=verifier_max_output_tokens,
    )
    kernel = AetherNextKernel(
        max_steps=max_steps,
        runtime_identity=resolved_runtime_identity,
        solver_reanchor_mode=solver_reanchor_mode,
        solver_context_mode=solver_context_mode,
        cancellation_event=cancellation_event,
    )
    # Keep a task-scoped WorldState owned by the adapter so the production
    # boundary, not only the kernel's direct-call fallback, carries state into
    # every Verifier activation and can emit a final compact snapshot.
    world_state = WorldState(
        task_contract=TaskContract.create(
            instruction_text,
            (TaskClause("task:prompt", instruction_text),),
        ),
        env_facts={
            "workspace_root": workspace_root,
            "network_scope": envmap.network_scope,
            "visible_file_count": len(envmap.visible_files),
            "visible_dir_count": len(envmap.visible_dirs),
        },
    )
    try:
        result = kernel.run(
            envmap, resolved_executor, hooks, world_state=world_state,
            run_timeout_s=run_timeout_s,
            run_started_monotonic=run_started_monotonic,
        )
    except RunCancellationRequested:
        # External lifecycle cancellation (Harbor agent timeout/cancel) is not a
        # provider or model failure. Preserve the exact in-flight ledger as a
        # terminal timeout record so Harbor may still grade the task world and
        # the experiment collector has durable forensic evidence. The async
        # Harbor adapter still propagates its own CancelledError after draining
        # this worker, so this does not convert cancellation into success.
        result = kernel.interrupted_result(
            status="timeout",
            blockers=("external_run_cancellation",),
        )
    finally:
        # Provider-native cognitive state is task-scoped. Executor lifecycle is
        # explicitly owned by the caller when an external world such as Harbor
        # is injected.
        hooks.release_model_scope()
        if close_executor:
            close = getattr(resolved_executor, "close", None)
            if callable(close):
                close()

    classifier = HarnessLimiterClassifier()
    classification = classifier.classify(result)

    run_metrics = run_metrics_for_row(result, hooks.last_parse_errors)
    model_call_telemetry = hooks.drain_model_telemetry()
    quarantined_model_call_telemetry = hooks.drain_quarantined_model_telemetry()
    model_interface_captures = hooks.drain_model_interface_captures()
    model_exchange_captures = hooks.drain_model_exchange_captures()

    return {
        "runtime_mode": "pcr_v0",
        "runtime_identity": dict(resolved_runtime_identity),
        "status": result.status,
        "step": result.step,
        "reconfigurations": result.reconfigurations,
        "used_check_ids": list(result.used_check_ids),
        "blockers": list(result.blockers),
        "classifier_label": classification.label,
        "classifier_confidence": classification.confidence,
        "classifier_evidence": list(classification.evidence),
        "classifier_detail": classification.detail,
        "model_parse_errors": run_metrics.pop("model_parse_errors"),
        "run_metrics": run_metrics,
        "model_call_telemetry": list(model_call_telemetry),
        "quarantined_late_model_telemetry": list(quarantined_model_call_telemetry),
        "model_interface_manifests": compact_model_interface_manifests(model_interface_captures),
        "model_interface_captures": list(model_interface_captures),
        "model_exchange_records": list(model_exchange_captures),
        "world_state_snapshot": world_state.dynamic_snapshot(),
        "receipt_records": _receipt_records(result),
        "receipt_summary": _receipt_summary(result),
    }


# ---------------------------------------------------------------------------
# Stub model for offline CLI use
# ---------------------------------------------------------------------------

class _StubSolverModel:
    """Scripted solver: submit_outcome immediately."""

    def __call__(
        self,
        messages: list[dict[str, str]],
        *,
        max_output_tokens: int = 8000,
    ) -> str:
        return json.dumps({
            "kind": "submit_outcome",
            "summary": "stub solver: submitting outcome immediately",
        })


class _StubVerifierModel:
    """Returns a minimal completed verifier verdict for offline PCR runs."""

    def __call__(
        self,
        messages: list[dict[str, str]],
        *,
        max_output_tokens: int = 8000,
    ) -> str:
        return json.dumps({
            "verdict": "completed",
            "confidence": "high",
            "summary": "Offline stub verifier observed sufficient local completion evidence.",
            "completion_evidence": ["offline_stub_verifier"],
        })


def _main() -> None:
    parser = argparse.ArgumentParser(
        description="Run an Aether-Next task with stub models (offline).",
    )
    parser.add_argument(
        "--task-dir",
        required=True,
        help="Path to the task directory.",
    )
    parser.add_argument(
        "--instruction-file",
        required=True,
        help="Path to a text file containing the task instruction.",
    )
    parser.add_argument(
        "--workspace-root",
        default="/tmp/aether_workspace",
        help="Workspace root directory (default: /tmp/aether_workspace).",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=24,
        help="Maximum kernel steps (default: 24).",
    )
    args = parser.parse_args()

    instruction_path = Path(args.instruction_file)
    if not instruction_path.is_file():
        print(f"error: instruction file not found: {args.instruction_file}", file=sys.stderr)
        sys.exit(1)
    instruction_text = instruction_path.read_text(encoding="utf-8")

    task_dir = str(Path(args.task_dir).resolve())
    if not Path(task_dir).is_dir():
        print(f"error: task directory not found: {args.task_dir}", file=sys.stderr)
        sys.exit(1)

    record = run_task(
        task_dir=task_dir,
        instruction_text=instruction_text,
        solver_model=_StubSolverModel(),
        verifier_model=_StubVerifierModel(),
        workspace_root=args.workspace_root,
        max_steps=args.max_steps,
    )

    json.dump(record, sys.stdout, indent=2, default=str)
    print()


if __name__ == "__main__":
    _main()
