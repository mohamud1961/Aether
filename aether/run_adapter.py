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

from .architect_v3_model import ArchitectV3Model
from .classifier import HarnessLimiterClassifier
from .envmap_builder import build_envmap_from_task
from .kernel import AetherNextKernel, KernelResult
from .model_hooks import ModelHooks, ModelCallable
from .model_interface import compact_model_interface_manifests
from .real_executor import SubprocessExecutor
from .result_metrics import run_metrics_for_row
from .task_metadata_loader import load_task_metadata
from .task_contract import TaskClause, TaskContract
from .world import WorldState



def _load_task_toml(task_dir: str) -> dict[str, Any]:
    return load_task_metadata(task_dir)

def ensure_certified_architect_mode(architect_mode: str) -> None:
    """Fail closed: certified production supports V3 or direct PERSISTENT V0."""
    if architect_mode in {"architect_v3", "persistent_v0"}:
        return
    raise ValueError(
        "legacy Architect modes are quarantined in reference_legacy and "
        "the Workbench Architect is quarantined from certified production; "
        "the certified harness supports architect_mode='architect_v3' or 'persistent_v0'"
    )


def _receipt_summary(result: KernelResult) -> list[dict[str, Any]]:
    """Compact receipt summaries for the run record."""
    items: list[dict[str, Any]] = []
    for receipt in result.receipts:
        items.append({
            "receipt_id": receipt.receipt_id,
            "kind": receipt.kind,
            "success": receipt.success,
            "failure_class": receipt.failure_class,
            "summary": receipt.summary,
        })
    return items


def architect_v3_for(
    architect_model: ModelCallable,
    *,
    hooks: ModelHooks | None = None,
) -> ArchitectV3Model:
    """Construct the certified one-call Architect V3 boundary."""
    model = hooks.call_architect_model if hooks is not None else architect_model
    return ArchitectV3Model(model)


def workbench_architect_for(
    architect_model: ModelCallable,
    *,
    architect_reviewer_model: ModelCallable | None = None,
    hooks: ModelHooks | None = None,
) -> Any:
    """Construct the certified workbench architect for a model callable.

    Supplying the owning hooks preserves provider telemetry attribution for the
    architect's initial and repair calls.  The raw-callable form remains for
    compatibility with offline callers and existing tests.
    """
    from .workbench_hooks import WorkbenchArchitect
    model = hooks.call_workbench_architect_model if hooks is not None else architect_model
    review_model = (
        hooks.call_architect_reviewer_model
        if hooks is not None and architect_reviewer_model is not None
        else architect_reviewer_model
    )
    return WorkbenchArchitect(model, review_model=review_model)


def _build_runtime_identity(
    *,
    task_dir: str,
    instruction_text: str,
    workspace_root: str,
    environment_id: str,
    max_steps: int,
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
        "budgets": {
            "max_kernel_steps": max(1, int(max_steps)),
        },
    })
    return identity


def run_task(
    *,
    task_dir: str,
    instruction_text: str,
    architect_model: ModelCallable,
    solver_model: ModelCallable,
    verifier_model: ModelCallable | None = None,
    architect_reviewer_model: ModelCallable | None = None,
    workspace_root: str = "/app",
    max_steps: int = 24,
    architect_mode: str = "architect_v3",
    runtime_identity: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute a task end-to-end and return a JSON-serializable run record.

    Parameters
    ----------
    task_dir:
        Path to the task directory for building the EnvMap.
    instruction_text:
        The task instruction / prompt text.
    architect_model:
        Model callable for the architect role.
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
    task_toml = _load_task_toml(task_dir)
    envmap = build_envmap_from_task(
        task_dir,
        instruction_text,
        workspace_root=workspace_root,
        task_toml=task_toml,
    )

    ensure_certified_architect_mode(architect_mode)
    if architect_reviewer_model is not None:
        raise ValueError(
            "Architect V3 has no reviewer or correction call in certified production"
        )

    executor = SubprocessExecutor(workspace_root)
    persistent_primary = architect_mode == "persistent_v0"
    resolved_runtime_identity = _build_runtime_identity(
        task_dir=task_dir,
        instruction_text=instruction_text,
        workspace_root=workspace_root,
        environment_id=envmap.digest(),
        max_steps=max_steps,
        supplied=runtime_identity,
    )
    hooks = ModelHooks(
        architect_model,
        solver_model,
        verifier_model=verifier_model,
        architect_reviewer_model=architect_reviewer_model,
        run_id=(
            str(resolved_runtime_identity["run_id"])
            if persistent_primary else None
        ),
        task_id=Path(task_dir).name,
    )
    kernel = AetherNextKernel(
        max_steps=max_steps,
        architect_v3_architect=(
            architect_v3_for(architect_model, hooks=hooks)
            if not persistent_primary else None
        ),
        persistent_primary=persistent_primary,
        runtime_identity=resolved_runtime_identity,
        certified_production=True,
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
        result = kernel.run(envmap, executor, hooks, world_state=world_state)
    finally:
        # Provider-native cognitive state and persistent terminal sessions are
        # both task-scoped. Release them even when the kernel/model raises.
        hooks.release_model_scope()
        executor.close()

    classifier = HarnessLimiterClassifier()
    classification = classifier.classify(result)

    run_metrics = run_metrics_for_row(result, hooks.last_parse_errors)
    model_call_telemetry = hooks.drain_model_telemetry()
    quarantined_model_call_telemetry = hooks.drain_quarantined_model_telemetry()
    model_interface_captures = hooks.drain_model_interface_captures()

    return {
        "architect_mode": architect_mode,
        "runtime_identity": dict(resolved_runtime_identity),
        "status": result.status,
        "step": result.step,
        "reconfigurations": result.reconfigurations,
        "architect_defect": result.architect_defect,
        "architect_defect_reasons": list(result.architect_defect_reasons),
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
        "world_state_snapshot": world_state.dynamic_snapshot(),
        "receipt_summary": _receipt_summary(result),
    }


# ---------------------------------------------------------------------------
# Stub model for offline CLI use
# ---------------------------------------------------------------------------

class _StubArchitectV3Model:
    """Returns one valid minimal V3 contract for offline adapter checks."""

    def __call__(
        self,
        messages: list[dict[str, str]],
        *,
        max_output_tokens: int = 5000,
    ) -> str:
        return json.dumps({
            "schema_version": "aether_architect.v3",
            "outcomes": [{
                "outcome_id": "task_completed",
                "description": "The requested task is completed.",
                "parameters": [],
                "source_refs": ["user_task"],
            }],
            "constraints": [],
            "proof_facets": [{
                "proof_id": "task_completion_state",
                "target_type": "outcome",
                "target_id": "task_completed",
                "proof_kind": "exact_state",
                "acceptance_observation": "Current inspectable state establishes the requested outcome.",
                "falsification_observation": "Current inspectable state does not establish the requested outcome.",
            }],
            "solver_strategy": {
                "approach": [{
                    "strategy_id": "resolve_completion_state",
                    "guidance": "Resolve which current state directly establishes the requested outcome before submitting.",
                    "uncertainty": "Which current inspectable state is authoritative for the requested outcome.",
                    "outcome_refs": ["task_completed"],
                    "constraint_refs": [],
                    "proof_refs": ["task_completion_state"],
                }]
            },
        })


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
    """Returns a minimal completed verifier verdict for offline workbench runs."""

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
        architect_model=_StubArchitectV3Model(),
        solver_model=_StubSolverModel(),
        verifier_model=_StubVerifierModel(),
        workspace_root=args.workspace_root,
        max_steps=args.max_steps,
    )

    json.dump(record, sys.stdout, indent=2, default=str)
    print()


if __name__ == "__main__":
    _main()
