"""Run adapter: wire EnvMap + SubprocessExecutor + ModelHooks + Kernel into a single call."""
from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path
from typing import Any

from .classifier import HarnessLimiterClassifier
from .envmap_builder import build_envmap_from_task
from .kernel import AetherNextKernel, KernelResult
from .model_hooks import ModelHooks, ModelCallable
from .real_executor import SubprocessExecutor



def _load_task_toml(task_dir: str) -> dict[str, Any]:
    path = Path(task_dir) / "task.toml"
    if not path.exists():
        return {}
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return {}

def ensure_certified_architect_mode(
    architect_mode: str,
    *,
    allow_reference_architect_mode: bool = False,
) -> None:
    """Fail closed unless certified runs explicitly opt into reference modes."""
    if architect_mode == "workbench":
        return
    if allow_reference_architect_mode:
        return
    raise ValueError(
        "reference architect modes are quarantined for certified/default runs; "
        "pass allow_reference_architect_mode=True only for explicit reference/debug use"
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


def architect_overrides_for_mode(architect_mode: str, architect_model: ModelCallable) -> tuple[Any | None, Any | None]:
    """Return ``(contract_architect, workbench_architect)`` for a mode."""
    if architect_mode == "ir":
        return None, None
    if architect_mode == "contract":
        from .contract_hooks import ContractArchitect
        return ContractArchitect(architect_model), None
    if architect_mode == "workbench":
        from .workbench_hooks import WorkbenchArchitect
        return None, WorkbenchArchitect(architect_model)
    raise ValueError(f"unsupported architect_mode: {architect_mode}")


def run_task(
    *,
    task_dir: str,
    instruction_text: str,
    architect_model: ModelCallable,
    solver_model: ModelCallable,
    verifier_model: ModelCallable | None = None,
    workspace_root: str = "/app",
    max_steps: int = 24,
    architect_mode: str = "workbench",
    allow_reference_architect_mode: bool = False,
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

    ensure_certified_architect_mode(
        architect_mode,
        allow_reference_architect_mode=allow_reference_architect_mode,
    )

    executor = SubprocessExecutor(workspace_root)
    hooks = ModelHooks(architect_model, solver_model, verifier_model=verifier_model)
    contract_architect, workbench_architect = architect_overrides_for_mode(architect_mode, architect_model)

    kernel = AetherNextKernel(
        max_steps=max_steps,
        contract_architect=contract_architect,
        workbench_architect=workbench_architect,
    )

    result = kernel.run(envmap, executor, hooks)

    classifier = HarnessLimiterClassifier()
    classification = classifier.classify(result)

    return {
        "architect_mode": architect_mode,
        "reference_architect_mode": architect_mode != "workbench",
        "status": result.status,
        "step": result.step,
        "reconfigurations": result.reconfigurations,
        "used_check_ids": list(result.used_check_ids),
        "blockers": list(result.blockers),
        "classifier_label": classification.label,
        "classifier_confidence": classification.confidence,
        "classifier_evidence": list(classification.evidence),
        "classifier_detail": classification.detail,
        "model_parse_errors": list(hooks.last_parse_errors),
        "receipt_summary": _receipt_summary(result),
    }


# ---------------------------------------------------------------------------
# Stub model for offline CLI use
# ---------------------------------------------------------------------------

class _StubArchitectModel:
    """Returns a valid RuntimeConfigIR JSON selecting shell + filesystem."""

    def __call__(
        self,
        messages: list[dict[str, str]],
        *,
        max_output_tokens: int = 8000,
    ) -> str:
        return json.dumps({
            "architect_summary": "stub architect: direct_build with shell+filesystem",
            "solver_identity_prompt": "You are a careful software engineer.",
            "selected_capabilities": ["shell", "filesystem"],
            "workflow_policy": {"mode": "direct_build"},
            "process_policy": {"mode": "stateless_shell"},
            "completion_policy": {"require_authoritative_check": False},
        })


class _StubWorkbenchArchitectModel:
    """Returns a valid HarnessConfigIR JSON for offline workbench mode."""

    def __call__(
        self,
        messages: list[dict[str, str]],
        *,
        max_output_tokens: int = 8000,
    ) -> str:
        return json.dumps({
            "schema_version": "harness_config.v1",
            "task_understanding": "stub workbench: configure a local file task",
            "success_definition": "required local artifacts exist and visible checks pass",
            "solver_system_prompt": {
                "role": "Careful local task solver",
                "workflow": ["inspect visible files", "make the requested change", "self-verify", "submit"],
                "self_verification": ["run configured checks before submitting"],
                "memory_use": ["query_memory only before repeating reads/checks or retrieving prior evidence"],
                "stop_conditions": ["submit only after visible evidence supports completion"],
            },
            "verifier_system_prompt": {
                "role": "Read-only current-state verifier for the local task",
                "success_criteria": ["required local artifacts exist and visible checks pass"],
                "required_evidence": ["current artifact state and visible check evidence support completion"],
                "false_positive_traps": ["artifact presence alone may not prove semantic correctness"],
                "verdict_guidance": ["completed requires current evidence; needs_repair names the missing or wrong state"],
                "feedback_guidance": ["give concrete repair feedback tied to observed state"],
            },
            "tool_policy": {"enabled_tools": ["read_file", "write_file", "run_command", "query_memory", "run_check"]},
            "context_policy": {"mode": "retrieval_augmented", "always_include": ["recent_progress", "pending_checks"]},
            "model_verifier_policy": {"enabled": True},
            "failure_feedback_policy": {"persist_until": "resolved_or_superseded"},
            "local_verification_limits": ["offline stub workbench does not prove hidden grader behavior"],
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
    parser.add_argument(
        "--architect-mode",
        default="workbench",
        choices=["ir", "contract", "workbench"],
        help="Architect mode: ir, contract, or workbench (default: workbench). "
        "Reference modes are quarantined unless --allow-reference-architect-mode is set.",
    )
    parser.add_argument(
        "--allow-reference-architect-mode",
        action="store_true",
        help="Explicitly opt into reference architect modes for offline/debug use.",
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

    architect_model = _StubWorkbenchArchitectModel() if args.architect_mode == "workbench" else _StubArchitectModel()
    solver_model = _StubSolverModel()
    verifier_model = _StubVerifierModel() if args.architect_mode == "workbench" else None

    record = run_task(
        task_dir=task_dir,
        instruction_text=instruction_text,
        architect_model=architect_model,
        solver_model=solver_model,
        verifier_model=verifier_model,
        workspace_root=args.workspace_root,
        max_steps=args.max_steps,
        architect_mode=args.architect_mode,
        allow_reference_architect_mode=args.allow_reference_architect_mode,
    )

    json.dump(record, sys.stdout, indent=2, default=str)
    print()


if __name__ == "__main__":
    _main()
