"""Task-local PCR helper-tool lifecycle and smoke-test admission.

The Primary Agent may create code as a task-local computational extension.
The Kernel does not judge the helper's semantics. It binds helper generations
to exact file content, requires an explicit successful smoke test before an
explicit helper execution, preserves output provenance, and prevents helper
self-reports from becoming completion evidence.
"""
from __future__ import annotations

from hashlib import sha256
import shlex
from typing import Any, Iterable

from .ledger import ExecutionLedger, Receipt
from .runtime_ir import ActionRequest, CompiledRuntime, normalize_relpath


_HELPER_MODES = frozenset({"smoke_test", "execute"})


def _helper_dir(compiled: CompiledRuntime) -> str:
    return str(compiled.helper_tool_policy.task_local_dir or "").strip().strip("/")


def _normalized_helper_path(
    raw_path: str,
    compiled: CompiledRuntime,
    *,
    workspace_root: str,
) -> str:
    path = normalize_relpath(str(raw_path), workspace_root)
    directory = _helper_dir(compiled)
    if not directory or not (
        path == directory or path.startswith(directory + "/")
    ):
        raise ValueError(
            f"helper path {path!r} is outside task-local helper directory {directory!r}"
        )
    if path == directory:
        raise ValueError("helper path must identify a file, not the helper directory")
    return path


def _creation_receipts(ledger: ExecutionLedger) -> tuple[Receipt, ...]:
    return tuple(
        receipt for receipt in ledger.all_receipts()
        if receipt.kind == "pcr_helper_tool_created" and receipt.success
    )


def _latest_creation(
    ledger: ExecutionLedger,
    path: str,
) -> Receipt | None:
    matches = [
        receipt for receipt in _creation_receipts(ledger)
        if str(receipt.payload.get("path", "")) == path
    ]
    return matches[-1] if matches else None


def _current_smoke_test(
    ledger: ExecutionLedger,
    *,
    path: str,
    helper_generation: str,
) -> Receipt | None:
    matches = [
        receipt for receipt in ledger.all_receipts()
        if receipt.kind == "pcr_helper_smoke_test"
        and receipt.success
        and str(receipt.payload.get("path", "")) == path
        and str(receipt.payload.get("helper_generation", "")) == helper_generation
    ]
    return matches[-1] if matches else None


def _known_referenced_helper_paths(
    action: ActionRequest,
    ledger: ExecutionLedger,
) -> tuple[str, ...]:
    if action.kind != "run_command":
        return ()
    command = str(action.arguments.get("command", ""))
    matches: list[str] = []
    for receipt in _creation_receipts(ledger):
        path = str(receipt.payload.get("path", ""))
        if path and (path in command or shlex.quote(path) in command):
            matches.append(path)
    return tuple(dict.fromkeys(matches))


def helper_preflight_receipt(
    action: ActionRequest,
    compiled: CompiledRuntime,
    ledger: ExecutionLedger,
    *,
    step: int,
    workspace_root: str,
) -> Receipt | None:
    """Return a refusal receipt when an explicit helper execution is invalid."""
    if action.kind != "run_command":
        return None
    mode = str(action.arguments.get("helper_mode", "")).strip()
    raw_path = str(action.arguments.get("helper_path", "")).strip()
    referenced = _known_referenced_helper_paths(action, ledger)
    if not mode and not raw_path:
        if not referenced:
            return None
        return Receipt(
            receipt_id=f"step-{step}:{action.action_id}:helper_preflight",
            step=step,
            kind="action_validation",
            success=False,
            summary=(
                "command references a registered PCR helper generation but does "
                "not declare helper_path and helper_mode"
            ),
            failure_class="helper_lifecycle_required",
            payload={
                "referenced_helper_paths": list(referenced),
                "required_helper_modes": sorted(_HELPER_MODES),
            },
        )
    if not mode or not raw_path:
        return Receipt(
            receipt_id=f"step-{step}:{action.action_id}:helper_preflight",
            step=step,
            kind="action_validation",
            success=False,
            summary="helper_path and helper_mode must be supplied together",
            failure_class="helper_lifecycle_invalid",
        )
    if mode not in _HELPER_MODES:
        return Receipt(
            receipt_id=f"step-{step}:{action.action_id}:helper_preflight",
            step=step,
            kind="action_validation",
            success=False,
            summary=f"unsupported helper_mode: {mode}",
            failure_class="helper_lifecycle_invalid",
        )
    try:
        path = _normalized_helper_path(
            raw_path, compiled, workspace_root=workspace_root,
        )
    except ValueError as exc:
        return Receipt(
            receipt_id=f"step-{step}:{action.action_id}:helper_preflight",
            step=step,
            kind="action_validation",
            success=False,
            summary=str(exc),
            failure_class="helper_path_invalid",
        )
    command = str(action.arguments.get("command", ""))
    if path not in command and shlex.quote(path) not in command:
        return Receipt(
            receipt_id=f"step-{step}:{action.action_id}:helper_preflight",
            step=step,
            kind="action_validation",
            success=False,
            summary="declared helper_path is not present in the command",
            failure_class="helper_command_binding_invalid",
            payload={"path": path},
        )
    creation = _latest_creation(ledger, path)
    if creation is None:
        return Receipt(
            receipt_id=f"step-{step}:{action.action_id}:helper_preflight",
            step=step,
            kind="action_validation",
            success=False,
            summary=f"no registered current helper generation exists for {path}",
            failure_class="helper_generation_missing",
            payload={"path": path},
        )
    generation = str(creation.payload.get("helper_generation", ""))
    if (
        mode == "execute"
        and compiled.helper_tool_policy.require_smoke_test
        and _current_smoke_test(
            ledger, path=path, helper_generation=generation,
        ) is None
    ):
        return Receipt(
            receipt_id=f"step-{step}:{action.action_id}:helper_preflight",
            step=step,
            kind="action_validation",
            success=False,
            summary=(
                f"current helper generation for {path} requires a successful "
                "smoke test before execution"
            ),
            failure_class="helper_smoke_test_required",
            payload={
                "path": path,
                "helper_generation": generation,
                "creation_receipt_id": creation.receipt_id,
            },
        )
    return None


def observe_helper_action(
    action: ActionRequest,
    action_receipts: Iterable[Receipt],
    compiled: CompiledRuntime,
    ledger: ExecutionLedger,
    *,
    step: int,
    workspace_root: str,
) -> tuple[Receipt, ...]:
    """Annotate direct results and create helper lifecycle provenance receipts."""
    receipts = tuple(action_receipts)
    if action.kind == "write_file":
        raw_path = str(action.arguments.get("path", ""))
        try:
            path = _normalized_helper_path(
            raw_path, compiled, workspace_root=workspace_root,
        )
        except ValueError:
            return ()
        write = next((item for item in receipts if item.kind == "write_file"), None)
        if write is None or not write.success:
            return ()
        content_hash = str(write.payload.get("after_content_hash", ""))
        generation = sha256(
            f"{path}\0{content_hash}".encode("utf-8")
        ).hexdigest()
        # A helper artifact is a tool implementation, not a task deliverable or
        # proof of task completion.
        write.payload["helper_tool_artifact"] = True
        write.payload["helper_generation"] = generation
        write.payload["completion_evidence_eligible"] = False
        return (Receipt(
            receipt_id=f"step-{step}:{action.action_id}:helper_created",
            step=step,
            kind="pcr_helper_tool_created",
            success=True,
            summary=f"registered task-local helper generation for {path}",
            state_change=False,
            payload={
                "path": path,
                "helper_id": "helper:" + sha256(path.encode("utf-8")).hexdigest()[:16],
                "helper_generation": generation,
                "content_hash": content_hash,
                "write_receipt_id": write.receipt_id,
                "smoke_test_required": compiled.helper_tool_policy.require_smoke_test,
                "trust_for_completion": compiled.helper_tool_policy.trust_for_completion,
                "completion_evidence_eligible": False,
                "semantic_content_interpreted_by_kernel": False,
            },
        ),)

    if action.kind != "run_command":
        return ()
    mode = str(action.arguments.get("helper_mode", "")).strip()
    raw_path = str(action.arguments.get("helper_path", "")).strip()
    if mode not in _HELPER_MODES or not raw_path:
        return ()
    path = _normalized_helper_path(
            raw_path, compiled, workspace_root=workspace_root,
        )
    creation = _latest_creation(ledger, path)
    if creation is None:
        return ()
    generation = str(creation.payload.get("helper_generation", ""))
    command_result = next((item for item in receipts if item.kind == "run_command"), None)
    if command_result is None:
        return ()
    command_result.payload.update({
        "helper_mode": mode,
        "helper_path": path,
        "helper_generation": generation,
        "helper_creation_receipt_id": creation.receipt_id,
        "helper_output_trust_for_completion": False,
        "completion_evidence_eligible": False,
    })
    command_hash = sha256(
        str(action.arguments.get("command", "")).encode("utf-8")
    ).hexdigest()
    if mode == "smoke_test":
        return (Receipt(
            receipt_id=f"step-{step}:{action.action_id}:helper_smoke_test",
            step=step,
            kind="pcr_helper_smoke_test",
            success=command_result.success,
            summary=(
                f"helper smoke test passed for {path}"
                if command_result.success
                else f"helper smoke test failed for {path}"
            ),
            failure_class="" if command_result.success else "helper_smoke_test_failed",
            payload={
                "path": path,
                "helper_generation": generation,
                "creation_receipt_id": creation.receipt_id,
                "command_receipt_id": command_result.receipt_id,
                "command_sha256": command_hash,
                "stdout_handle": command_result.payload.get("stdout_handle", ""),
                "stderr_handle": command_result.payload.get("stderr_handle", ""),
                "completion_evidence_eligible": False,
                "semantic_sufficiency_judged_by_kernel": False,
            },
        ),)
    smoke = _current_smoke_test(
        ledger, path=path, helper_generation=generation,
    )
    return (Receipt(
        receipt_id=f"step-{step}:{action.action_id}:helper_execution",
        step=step,
        kind="pcr_helper_execution",
        success=command_result.success,
        summary=f"executed smoke-qualified helper generation for {path}",
        failure_class="" if command_result.success else "helper_execution_failed",
        payload={
            "path": path,
            "helper_generation": generation,
            "creation_receipt_id": creation.receipt_id,
            "smoke_test_receipt_id": "" if smoke is None else smoke.receipt_id,
            "command_receipt_id": command_result.receipt_id,
            "command_sha256": command_hash,
            "stdout_handle": command_result.payload.get("stdout_handle", ""),
            "stderr_handle": command_result.payload.get("stderr_handle", ""),
            "completion_evidence_eligible": False,
            "helper_output_trust_for_completion": False,
            "semantic_sufficiency_judged_by_kernel": False,
        },
    ),)


def helper_context(compiled: CompiledRuntime, ledger: ExecutionLedger) -> dict[str, Any]:
    creations = [
        receipt for receipt in ledger.all_receipts()
        if receipt.kind == "pcr_helper_tool_created" and receipt.success
    ]
    current: dict[str, dict[str, Any]] = {}
    for creation in creations:
        path = str(creation.payload.get("path", ""))
        generation = str(creation.payload.get("helper_generation", ""))
        smoke = _current_smoke_test(
            ledger, path=path, helper_generation=generation,
        )
        executions = [
            receipt for receipt in ledger.all_receipts()
            if receipt.kind == "pcr_helper_execution"
            and str(receipt.payload.get("path", "")) == path
            and str(receipt.payload.get("helper_generation", "")) == generation
        ]
        current[path] = {
            "path": path,
            "helper_id": creation.payload.get("helper_id", ""),
            "helper_generation": generation,
            "creation_receipt_id": creation.receipt_id,
            "smoke_test_status": (
                "passed" if smoke is not None else "required"
            ),
            "smoke_test_receipt_id": "" if smoke is None else smoke.receipt_id,
            "latest_execution_receipt_id": (
                executions[-1].receipt_id if executions else ""
            ),
            "completion_evidence_eligible": False,
        }
    return {
        "enabled": compiled.helper_tool_policy.allow_creation,
        "task_local_dir": _helper_dir(compiled),
        "smoke_test_required": compiled.helper_tool_policy.require_smoke_test,
        "trust_for_completion": compiled.helper_tool_policy.trust_for_completion,
        "execution_contract": {
            "create": "write_file under task_local_dir",
            "smoke_test": "run_command with helper_mode=smoke_test and helper_path",
            "execute": "run_command with helper_mode=execute and helper_path",
            "helper_self_report_is_task_evidence": False,
        },
        "current_helpers": [current[path] for path in sorted(current)[-24:]],
        "omitted_older_helper_count": max(0, len(current) - 24),
    }
