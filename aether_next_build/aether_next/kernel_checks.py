"""Live check probing: run cheap deterministic checks after file-modifying act turns.

Extracted from kernel.py to keep it under the 500-LOC cap.  The probe runs
only when the compiled runtime has planned checks (contract runs); baseline
runs with no check plan are entirely unaffected.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from .ledger import ExecutionLedger, Receipt
from .runtime_ir import CheckSpec, CompiledRuntime, EnvMap

if TYPE_CHECKING:
    from .execution import Executor

# Only commands starting with these prefixes are considered cheap enough
# to run mid-turn without risk of side effects or long runtime.
_CHEAP_PREFIXES: tuple[str, ...] = (
    "test ",
    "[ ",
    "python3 -c",
    "stat ",
)

_MAX_PROBE_CHECKS: int = 16


def _is_cheap_check(command: str) -> bool:
    """Return True if *command* starts with a known-cheap deterministic prefix."""
    for prefix in _CHEAP_PREFIXES:
        if command.startswith(prefix):
            return True
    return False


def _step_modified_files(step_receipts: tuple[Receipt, ...]) -> bool:
    """Return True if any receipt from this step indicates file modification."""
    for receipt in step_receipts:
        # write_file actions always modify files
        if receipt.kind == "write_file" and receipt.success:
            return True
        # run_command or other actions that report modified_paths
        modified = receipt.payload.get("modified_paths")
        if modified:
            return True
    return False


def probe_checks(
    step: int,
    compiled: CompiledRuntime,
    executor: "Executor",
    envmap: EnvMap,
    ledger: ExecutionLedger,
    step_receipts: tuple[Receipt, ...],
) -> list[Receipt]:
    """Run cheap planned checks after a file-modifying act turn.

    Returns the list of probe receipts recorded.  Skips entirely when
    ``compiled.planned_checks()`` is empty (baseline path unchanged).
    """
    planned = compiled.planned_checks()
    if not planned:
        return []

    if not _step_modified_files(step_receipts):
        return []

    probe_receipts: list[Receipt] = []
    count = 0
    for check in planned:
        if count >= _MAX_PROBE_CHECKS:
            break
        if not _is_cheap_check(check.command):
            continue
        result = executor.run_command(check.command, cwd=envmap.workspace_root)
        receipt = Receipt(
            receipt_id=f"step-{step}:probe:{check.check_id}",
            step=step,
            kind="check_result",
            success=result.success,
            summary=f"probe {check.label}: exit={result.exit_code}",
            state_change=result.success,
            failure_class="" if result.success else "check_failed",
            payload={
                "check_id": check.check_id,
                "command": check.command,
                "passed": result.success,
                "origin": "probe",
                "detail": (result.stderr or result.stdout)[:500],
            },
        )
        probe_receipts.append(receipt)
        ledger.record(receipt)
        count += 1

    return probe_receipts


def cheap_checks_all_passed(
    compiled: CompiledRuntime,
    ledger: ExecutionLedger,
) -> bool:
    """Return True when every *cheap* planned check has a passing latest result.

    Considers only the planned checks whose command satisfies
    ``_is_cheap_check``.  Returns False when there are no planned checks, no
    cheap checks among them, or any cheap check lacks a passing latest result.
    Non-cheap checks are intentionally ignored here -- they are evaluated later
    by ``_run_submit_turn`` when auto-submit fires.
    """
    planned = compiled.planned_checks()
    if not planned:
        return False
    cheap_ids: list[str] = [
        check.check_id for check in planned if _is_cheap_check(check.command)
    ]
    if not cheap_ids:
        return False
    latest_by_id = {
        outcome.check_id: outcome
        for outcome in ledger.latest_checks(compiled.check_plan_ids)
    }
    for cid in cheap_ids:
        outcome = latest_by_id.get(cid)
        if outcome is None or not outcome.passed:
            return False
    return True


def run_planned_check(
    step: int,
    compiled: CompiledRuntime,
    executor: "Executor",
    envmap: EnvMap,
    check_id: str,
    *,
    receipt_prefix: str,
) -> Receipt:
    """Run a configured planned check by id and return its receipt."""
    check = compiled.eval_index.get(check_id)
    if check is None or check_id not in compiled.check_plan_ids:
        return Receipt(
            receipt_id=f"{receipt_prefix}:check_missing", step=step,
            kind="check_result", success=False,
            summary=f"unknown or unplanned check_id: {check_id}",
            failure_class="unknown_check",
            payload={"check_id": check_id, "passed": False, "origin": "solver_callable"},
        )
    result = executor.run_command(check.command, cwd=envmap.workspace_root)
    return Receipt(
        receipt_id=f"{receipt_prefix}:check:{check.check_id}", step=step,
        kind="check_result", success=result.success,
        summary=f"solver-ran check {check.label}: exit={result.exit_code}",
        state_change=result.success,
        failure_class="" if result.success else "check_failed",
        payload={
            "check_id": check.check_id,
            "command": check.command,
            "passed": result.success,
            "origin": "solver_callable",
            "detail": (result.stderr or result.stdout)[:500],
        },
    )
