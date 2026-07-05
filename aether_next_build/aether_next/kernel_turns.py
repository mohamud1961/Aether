"""Act/submit turn execution, extracted from kernel.py for the 500-LOC cap.

``kernel`` is the AetherNextKernel instance supplying guards, engines, and
the completion gate; the gate decision is stored on the kernel as before.
"""
from __future__ import annotations

import csv
import json
from typing import Any, TYPE_CHECKING

from .automatic_memory import automatic_memory_receipt
from .execution import Executor
from .kernel_actions import handle_kernel_owned_action
from .kernel_checks import probe_checks
from .kernel_dispatch import dispatch_action
from .ledger import ExecutionLedger, Receipt
from .no_progress import NoProgressController
from .runtime_ir import CompiledRuntime, EnvMap, SolverTurn, normalize_relpath

if TYPE_CHECKING:
    from .tracing import RunTrace


def run_act_turn(kernel: Any, turn: SolverTurn, step: int, compiled: CompiledRuntime,
                 executor: Executor, envmap: EnvMap, ledger: ExecutionLedger) -> None:
    """Execute an act turn: validate, guard, dispatch, probe."""
    step_receipts: list[Receipt] = []

    def _record(r: Receipt) -> None:
        ledger.record(r)
        step_receipts.append(r)

    for action in turn.actions:
        action_errors = action.validate(compiled.action_schema)
        if action_errors:
            _record(Receipt(
                receipt_id=f"step-{step}:{action.action_id}:validation", step=step,
                kind="action_validation", success=False,
                summary=f"invalid action: {'; '.join(action_errors)}",
                failure_class="action_validation",
            ))
            continue
        safety_violation = kernel.safety_guard.violation(compiled, action)
        if safety_violation:
            _record(Receipt(
                receipt_id=f"step-{step}:{action.action_id}:safety", step=step,
                kind="safety_block", success=False,
                summary=safety_violation, failure_class="safety_violation",
            ))
            continue
        if action.kind == "write_file":
            path = str(action.arguments.get("path", "")).strip()
            if path:
                norm = normalize_relpath(path, envmap.workspace_root)
                violation = kernel.integrity_guards.explain_path_violation(
                    compiled.objective_graph, norm,
                )
                if violation:
                    _record(Receipt(
                        receipt_id=f"step-{step}:{action.action_id}:integrity",
                        step=step, kind="integrity_block", success=False,
                        summary=violation, failure_class="integrity_violation",
                        payload={"integrity_violation": violation},
                    ))
                    continue
        if compiled.automatic_memory_policy.mode != "off":
            automatic = automatic_memory_receipt(
                action, step=step, envmap=envmap, ledger=ledger,
            )
            if automatic is not None:
                _record(automatic)
                block_reason = _automatic_memory_block_reason(compiled, automatic)
                if block_reason:
                    _record(Receipt(
                        receipt_id=f"step-{step}:{action.action_id}:automatic_memory_advisory",
                        step=step,
                        kind="automatic_memory_advisory",
                        success=True,
                        summary=block_reason,
                        failure_class="",
                        payload={
                            "source_receipt_id": automatic.receipt_id,
                            "policy": compiled.automatic_memory_policy.mode,
                            "target": automatic.payload.get("target"),
                            "authority": "advisory_only",
                        },
                    ))
        no_progress = kernel.no_progress_controller.evaluate(action, ledger)
        if no_progress is not None:
            _record(NoProgressController.receipt(no_progress, step=step, action_id=action.action_id))
        handled = handle_kernel_owned_action(action, step, compiled, executor, envmap, ledger)
        if handled is not None:
            _record(handled); continue
        for receipt in dispatch_action(kernel, action, step, compiled, executor, envmap, ledger):
            _record(receipt)
    probe_checks(step, compiled, executor, envmap, ledger, tuple(step_receipts))


def _automatic_memory_block_reason(compiled: CompiledRuntime, receipt: Receipt) -> str:
    mode = compiled.automatic_memory_policy.mode
    if mode not in {"require_justification", "soft_block_exact_repeat"}:
        return ""
    payload = receipt.payload or {}
    if bool(payload.get("repeat_justified")):
        return ""
    target = payload.get("target") if isinstance(payload.get("target"), dict) else {}
    action_kind = str(payload.get("action_kind", ""))
    exact_repeat = bool(payload.get("same_content_hash")) or action_kind in {"run_command", "run_check"}
    if mode == "require_justification":
        return (
            "automatic memory requires repeat_justification before repeating "
            f"{action_kind} on {target.get('key', 'this target')}"
        )
    if mode == "soft_block_exact_repeat" and exact_repeat:
        return (
            "automatic memory soft-blocked an exact repeated action without new state or repeat_justification: "
            f"{action_kind} on {target.get('key', 'this target')}"
        )
    return ""

def run_submit_turn(
    kernel: Any,
    step: int,
    compiled: CompiledRuntime,
    executor: Executor,
    envmap: EnvMap,
    ledger: ExecutionLedger,
    trace: "RunTrace | None",
) -> None:
    """Execute submit_outcome logic; stores gate decision on the kernel."""
    for check in compiled.planned_checks():
        result = executor.run_command(check.command, cwd=envmap.workspace_root)
        failure_class = kernel.failure_parser.classify(
            result.stdout + "\n" + result.stderr, exit_code=result.exit_code,
        ) if not result.success else ""
        ledger.record(Receipt(
            receipt_id=f"step-{step}:check:{check.check_id}", step=step,
            kind="check_result", success=result.success,
            summary=f"check {check.label}: exit={result.exit_code}",
            state_change=result.success, failure_class=failure_class,
            payload={
                "check_id": check.check_id, "command": check.command,
                "passed": result.success, "origin": check.origin,
                "detail": (result.stderr or result.stdout)[:500],
            },
        ))
    if compiled.objective_graph.output_schema and compiled.objective_graph.output_schema_target:
        target_path = compiled.objective_graph.output_schema_target
        try:
            content = executor.read_file(target_path)
            schema = dict(compiled.objective_graph.output_schema)
            if target_path.lower().endswith(".csv"):
                reader = csv.DictReader(content.splitlines())
                fields = reader.fieldnames or []
                missing_keys = [k for k in schema if k not in fields]
            else:
                parsed = json.loads(content)
                missing_keys = [k for k in schema if k not in parsed]
            valid = not missing_keys
            detail = "" if valid else f"missing keys: {', '.join(missing_keys)}"
        except (FileNotFoundError, OSError, json.JSONDecodeError, ValueError) as exc:
            valid = False
            detail = str(exc)
        ledger.record(Receipt(
            receipt_id=f"step-{step}:schema_validation", step=step,
            kind="schema_validation", success=valid,
            summary=f"schema validation: {'pass' if valid else detail}",
            failure_class="" if valid else "schema_mismatch",
        ))
    alerts = kernel.monitor_runner.run(compiled, ledger)
    decision = kernel.completion_gate.evaluate(compiled, ledger, alerts)
    if trace is not None:
        trace.add_gate(step, decision)
    kernel._last_gate_decision = decision