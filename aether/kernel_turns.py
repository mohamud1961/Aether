"""Act/submit turn execution, extracted from kernel.py for the 500-LOC cap.

``kernel`` is the AetherNextKernel instance supplying guards, engines, and
the completion gate; the gate decision is stored on the kernel as before.
"""
from __future__ import annotations

import csv
import hashlib
import json
from typing import Any, Mapping, TYPE_CHECKING

from .execution import Executor
from .kernel_actions import handle_kernel_owned_action
from .kernel_checks import probe_checks
from .kernel_dispatch import dispatch_action
from .ledger import ExecutionLedger, Receipt
from .observation_batch import mutation_generation
from .pcr_capabilities import pcr_capability_violation
from .pcr_evidence import PCR_COMPLETION_EVIDENCE_KINDS, is_pcr_primary_action_result
from .pcr_helper_tools import helper_preflight_receipt, observe_helper_action
from .pcr_repeat import (
    action_execution_committed_receipt,
    action_execution_pending_receipt,
    evaluate_pcr_repeat,
    pending_execution_commitment,
    permit_consumed_receipt,
    record_repeat_observation,
    repeat_block_receipts,
    repeat_reuse_receipt,
)
from .solver_progress import build_progress_receipt
from .runtime_ir import CompiledRuntime, EnvMap, SolverTurn, normalize_relpath
from .world import WorldState, WorldStateDeltaError

if TYPE_CHECKING:
    from .tracing import RunTrace


# Dynamic GUI availability is normally stable. Re-probe only after generic
# process/session/job operations that can causally create, advance, or remove a
# desktop/RFB backend. File-only and read-only task work must not pay active
# X/RFB probes on every Solver turn.
_RUNTIME_CAPABILITY_INVALIDATING_ACTIONS = frozenset({
    "write_file", "run_command",
    "start_terminal_session", "terminal_send", "terminal_read", "terminal_wait",
    "terminal_interrupt", "terminal_close",
    "bootstrap_acquire",
    "launch_process", "start_job", "probe_job", "probe_service", "stop_process",
    "run_experiment",
})


def _invalidate_runtime_capabilities_after_dispatch(kernel: Any, action: Any) -> None:
    if str(getattr(action, "kind", "")) not in _RUNTIME_CAPABILITY_INVALIDATING_ACTIONS:
        return
    invalidate = getattr(kernel, "invalidate_runtime_capability_cache", None)
    if callable(invalidate):
        invalidate()


def run_act_turn(kernel: Any, turn: SolverTurn, step: int, compiled: CompiledRuntime,
                 executor: Executor, envmap: EnvMap, ledger: ExecutionLedger,
                 world_state: WorldState | None = None) -> EnvMap | None:
    """Execute an act turn: validate, guard, dispatch, probe."""
    kernel._last_envmap_refresh = None
    step_receipts: list[Receipt] = []

    def _record(r: Receipt) -> None:
        ledger.record(r)
        step_receipts.append(r)

    # SolverTurn.validate guarantees one action frontier. Persist the
    # mechanical Primary decision before execution.
    action = turn.actions[0]
    _record(Receipt(
        receipt_id=f"step-{step}:{action.action_id}:primary_decision",
        step=step,
        kind="primary_decision",
        success=True,
        summary=turn.summary,
        payload={
            "action_id": action.action_id,
            "action_kind": action.kind,
            "capability_id": action.capability_id,
            "arguments_sha256": hashlib.sha256(
                json.dumps(
                    dict(action.arguments),
                    sort_keys=True,
                    separators=(",", ":"),
                    default=str,
                ).encode("utf-8")
            ).hexdigest(),
            "mutation_generation": mutation_generation(ledger),
            "cognitive_fields_authored_by_kernel": False,
        },
    ))

    for action in turn.actions:
        action_errors = action.validate(
            compiled.action_schema
        )
        if action_errors:
            _record(Receipt(
                receipt_id=f"step-{step}:{action.action_id}:validation", step=step,
                kind="action_validation", success=False,
                summary=f"invalid action: {'; '.join(action_errors)}",
                failure_class="action_validation",
            ))
            _record(ledger.record_accounting(
                receipt_id=f"step-{step}:{action.action_id}:refused_invalid",
                step=step, counter="solver_refused_actions",
                event="action_validation_failed", action_id=action.action_id,
            ))
            continue
        if action.kind in {
            "read_file", "read_file_page", "write_file", "inspect_artifact",
            "query_artifact_history", "inspect_diff",
        }:
            try:
                normalize_relpath(
                    str(action.arguments.get("path", "")), envmap.workspace_root,
                )
            except ValueError as exc:
                _record(Receipt(
                    receipt_id=f"step-{step}:{action.action_id}:workspace_path",
                    step=step,
                    kind="action_validation",
                    success=False,
                    summary=f"invalid workspace path: {exc}",
                    failure_class="workspace_path_escape",
                    payload={"action_id": action.action_id, "action_kind": action.kind},
                ))
                _record(ledger.record_accounting(
                    receipt_id=f"step-{step}:{action.action_id}:refused_workspace_path",
                    step=step,
                    counter="solver_refused_actions",
                    event="workspace_path_escape",
                    action_id=action.action_id,
                ))
                continue
        capability_violation = pcr_capability_violation(
            action, compiled,
            runtime_capability_ids=tuple(
                getattr(ledger, "runtime_capabilities", set()) or ()
            ),
        )
        if capability_violation:
            _record(Receipt(
                receipt_id=f"step-{step}:{action.action_id}:capability",
                step=step,
                kind="action_validation",
                success=False,
                summary=capability_violation,
                failure_class="capability_contract_mismatch",
                payload={
                    "action_id": action.action_id,
                    "action_kind": action.kind,
                    "capability_id": action.capability_id,
                },
            ))
            _record(ledger.record_accounting(
                receipt_id=f"step-{step}:{action.action_id}:refused_capability",
                step=step, counter="solver_refused_actions",
                event="capability_contract_mismatch", action_id=action.action_id,
            ))
            continue
        safety_violation = kernel.safety_guard.violation(compiled, action, network_scope=envmap.network_scope)
        if safety_violation:
            _record(Receipt(
                receipt_id=f"step-{step}:{action.action_id}:safety", step=step,
                kind="safety_block", success=False,
                summary=safety_violation, failure_class="safety_violation",
            ))
            _record(ledger.record_accounting(
                receipt_id=f"step-{step}:{action.action_id}:refused_safety",
                step=step, counter="solver_refused_actions",
                event="safety_violation", action_id=action.action_id,
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
                    _record(ledger.record_accounting(
                        receipt_id=f"step-{step}:{action.action_id}:refused_integrity",
                        step=step, counter="solver_refused_actions",
                        event="integrity_violation", action_id=action.action_id,
                    ))
                    continue
        if (
            kernel.max_accepted_task_actions is not None
            and ledger.accounting_value("solver_accepted_task_actions")
            >= kernel.max_accepted_task_actions
        ):
            _record(Receipt(
                receipt_id=f"step-{step}:{action.action_id}:action_budget",
                step=step,
                kind="action_budget_refused",
                success=False,
                summary=(
                    f"accepted task-action limit reached: {kernel.max_accepted_task_actions}; "
                    "action was not dispatched"
                ),
                failure_class="accepted_action_budget_exhausted",
                payload={"action_id": action.action_id, "action_kind": action.kind},
            ))
            _record(ledger.record_accounting(
                receipt_id=f"step-{step}:{action.action_id}:refused_action",
                step=step,
                counter="solver_refused_actions",
                event="accepted_action_budget_exhausted",
                action_id=action.action_id,
            ))
            continue
        pcr_repeat_decision = evaluate_pcr_repeat(
            action, ledger, step=step,
        )
        if pcr_repeat_decision.consequence == "reuse":
            _record(repeat_reuse_receipt(
                action, pcr_repeat_decision, step=step,
            ))
            _record(ledger.record_accounting(
                receipt_id=f"step-{step}:{action.action_id}:repeat_reused",
                step=step,
                counter="primary_repeat_reuses",
                event="immutable_result_reused",
                action_id=action.action_id,
            ))
            continue
        if pcr_repeat_decision.consequence == "block":
            for repeat_receipt in repeat_block_receipts(
                action, pcr_repeat_decision, step=step,
            ):
                _record(repeat_receipt)
            _record(ledger.record_accounting(
                receipt_id=f"step-{step}:{action.action_id}:refused_repeat",
                step=step,
                counter="solver_refused_actions",
                event="equivalent_repeat_blocked",
                action_id=action.action_id,
            ))
            continue
        if pcr_repeat_decision.consequence == "allow_with_permit":
            _record(permit_consumed_receipt(
                action, pcr_repeat_decision, step=step,
            ))
        helper_preflight = helper_preflight_receipt(
            action, compiled, ledger, step=step,
            workspace_root=envmap.workspace_root,
        )
        if helper_preflight is not None:
            _record(helper_preflight)
            _record(ledger.record_accounting(
                receipt_id=f"step-{step}:{action.action_id}:refused_helper",
                step=step, counter="solver_refused_actions",
                event=helper_preflight.failure_class, action_id=action.action_id,
            ))
            continue
        pending_commitment = pending_execution_commitment(action, ledger)
        if pending_commitment is not None:
            _record(Receipt(
                receipt_id=f"step-{step}:{action.action_id}:pcr_action_execution_block",
                step=step,
                kind="pcr_action_execution_block",
                success=False,
                summary=(
                    "equivalent action was accepted previously but has no durable "
                    "observed result; action was not re-dispatched"
                ),
                failure_class="unresolved_action_execution",
                payload={
                    "action_id": action.action_id,
                    "action_kind": action.kind,
                    "pending_receipt_id": pending_commitment.receipt_id,
                    "action_signature": str(
                        (pending_commitment.payload or {}).get("action_signature", "")
                    ),
                    "relevant_state_fingerprint": str(
                        (pending_commitment.payload or {}).get(
                            "relevant_state_fingerprint", ""
                        )
                    ),
                    "re_dispatch_prevented": True,
                    "at_most_once_boundary": True,
                },
            ))
            _record(ledger.record_accounting(
                receipt_id=f"step-{step}:{action.action_id}:refused_unresolved_execution",
                step=step,
                counter="solver_refused_actions",
                event="unresolved_action_execution",
                action_id=action.action_id,
            ))
            continue
        execution_pending = action_execution_pending_receipt(
            action, ledger, step=step,
        )
        _record(execution_pending)
        _record(ledger.record_accounting(
            receipt_id=f"step-{step}:{action.action_id}:accepted_action",
            step=step,
            counter="solver_accepted_task_actions",
            event="accepted_for_dispatch",
            action_id=action.action_id,
            detail=f"accepted solver action {action.kind}",
        ))
        handled = handle_kernel_owned_action(action, step, compiled, executor, envmap, ledger)
        if handled is not None:
            _record(handled)
            _update_world_from_receipt(world_state, handled, step=step, ledger=ledger)
            if execution_pending is not None:
                _record(action_execution_committed_receipt(
                    action, execution_pending, (handled,), step=step,
                ))
            if pcr_repeat_decision is not None:
                _record(record_repeat_observation(
                    action, pcr_repeat_decision,
                    step=step, step_receipts=step_receipts, ledger=ledger,
                ))
            _invalidate_runtime_capabilities_after_dispatch(kernel, action)
            continue
        dispatched = tuple(
            dispatch_action(kernel, action, step, compiled, executor, envmap, ledger)
        )
        helper_receipts = observe_helper_action(
            action, dispatched, compiled, ledger, step=step,
            workspace_root=envmap.workspace_root,
        )
        for receipt in dispatched:
            _record(receipt)
            _update_world_from_receipt(world_state, receipt, step=step, ledger=ledger)
        for receipt in helper_receipts:
            _record(receipt)
        if execution_pending is not None:
            _record(action_execution_committed_receipt(
                action, execution_pending, dispatched, step=step,
            ))
        if pcr_repeat_decision is not None:
            repeat_observation = record_repeat_observation(
                action, pcr_repeat_decision,
                step=step, step_receipts=step_receipts, ledger=ledger,
            )
            _record(repeat_observation)
            for supersession in _pcr_failure_supersession_receipts(
                action, pcr_repeat_decision, repeat_observation, ledger, step,
            ):
                _record(supersession)
        _invalidate_runtime_capabilities_after_dispatch(kernel, action)

    probe_receipts = probe_checks(
        step, compiled, executor, envmap, ledger, tuple(step_receipts)
    )
    step_receipts.extend(probe_receipts)
    _record(build_progress_receipt(
        action,
        step=step,
        step_receipts=step_receipts,
        ledger=ledger,
    ))
    _record_primary_action_result_index(
        action=action,
        step=step,
        step_receipts=step_receipts,
        record=_record
    )
    return getattr(kernel, "_last_envmap_refresh", None)


def _record_primary_action_result_index(
    *,
    action: Any,
    step: int,
    step_receipts: list[Receipt],
    record: Any,
) -> None:
    action_marker = f":{action.action_id}:"
    excluded = {
        "primary_decision",
        "solver_decision_state",
        "accounting",
        "automatic_memory",
        "no_progress_control",
        "solver_progress_assessment",
    }
    outcomes = [
        receipt
        for receipt in step_receipts
        if action_marker in receipt.receipt_id
        and is_pcr_primary_action_result(receipt)
    ]
    if not outcomes:
        status = "missing"
    elif all(receipt.success for receipt in outcomes):
        status = "succeeded"
    elif all(not receipt.success for receipt in outcomes):
        status = "failed"
    else:
        status = "mixed"
    success = status == "succeeded"
    record(Receipt(
        receipt_id=f"step-{step}:{action.action_id}:primary_action_result_index",
        step=step,
        kind="primary_action_result_index",
        success=success,
        summary=(
            f"Primary Agent action {action.action_id} produced {len(outcomes)} governed result receipt(s)"
            if outcomes
            else f"Primary Agent action {action.action_id} produced no governed result receipt"
        ),
        failure_class="" if outcomes else "missing_primary_action_result",
        payload={
            "action_id": action.action_id,
            "action_kind": action.kind,
            "status": status,
            "outcome_receipt_ids": [receipt.receipt_id for receipt in outcomes],
            "outcome_kinds": [receipt.kind for receipt in outcomes],
        },
    ))


def _pcr_failure_supersession_receipts(
    action: Any,
    decision: Any,
    observation: Receipt,
    ledger: ExecutionLedger,
    step: int,
) -> tuple[Receipt, ...]:
    """Link a failed task result only to a later same-action success.

    This is deliberately narrower than semantic task completion.  The kernel
    may state that a *particular failed action result* is superseded only when
    the identical capability/action has since produced a successful observed
    result after its relevant task state changed.  It cannot infer that a
    different successful command, a control receipt, or a model claim repaired
    the original failure.
    """
    current = observation.payload if isinstance(observation.payload, Mapping) else {}
    current_state = str(current.get("relevant_state_fingerprint", ""))
    current_outcome_ids = current.get("outcome_receipt_ids", ())
    if not current_state or not isinstance(current_outcome_ids, (list, tuple)):
        return ()
    receipts_by_id = {receipt.receipt_id: receipt for receipt in ledger.all_receipts()}
    successors = [
        receipts_by_id.get(str(receipt_id))
        for receipt_id in current_outcome_ids
    ]
    successors = [
        receipt for receipt in successors
        if receipt is not None
        and receipt.success is True
        and receipt.kind in PCR_COMPLETION_EVIDENCE_KINDS
    ]
    if not successors:
        return ()
    rows: list[Receipt] = []
    already_linked = {
        str((receipt.payload or {}).get("source_failure_receipt_id", ""))
        for receipt in ledger.all_receipts()
        if receipt.kind == "pcr_task_failure_supersession"
    }
    for prior in ledger.all_receipts():
        if prior.kind != "pcr_repeat_observation":
            continue
        payload = prior.payload if isinstance(prior.payload, Mapping) else {}
        if str(payload.get("action_signature", "")) != decision.action_signature:
            continue
        source_state = str(payload.get("relevant_state_fingerprint", ""))
        if not source_state or source_state == current_state:
            continue
        source_ids = payload.get("outcome_receipt_ids", ())
        if not isinstance(source_ids, (list, tuple)):
            continue
        for source_id in source_ids:
            failure = receipts_by_id.get(str(source_id))
            if (
                failure is None
                or failure.receipt_id in already_linked
                or failure.success is True
                or failure.kind not in PCR_COMPLETION_EVIDENCE_KINDS
                or not failure.failure_class
            ):
                continue
            successor = successors[0]
            rows.append(Receipt(
                receipt_id=(
                    f"step-{step}:{action.action_id}:pcr_failure_supersedes:"
                    f"{len(rows)}"
                ),
                step=step,
                kind="pcr_task_failure_supersession",
                success=True,
                summary="kernel linked prior failed task result to later same-action success after state change",
                payload={
                    "source_failure_receipt_id": failure.receipt_id,
                    "successor_receipt_id": successor.receipt_id,
                    "action_signature": decision.action_signature,
                    "source_relevant_state_fingerprint": source_state,
                    "successor_relevant_state_fingerprint": current_state,
                    "task_state_generation": ledger.task_state_generation(),
                    "authority": "kernel_observed_same_action_after_changed_state",
                },
            ))
            already_linked.add(failure.receipt_id)
    return tuple(rows)


def _receipt_path_projection(payload: dict[str, Any], *, step: int) -> dict[str, Any]:
    """Project concrete filesystem deltas without consuming receipt semantics."""
    modified_paths = tuple(
        str(item).strip() for item in payload.get("modified_paths", ()) or ()
        if str(item).strip()
    )
    created_paths = tuple(
        str(item).strip() for item in payload.get("artifact_paths", ()) or ()
        if str(item).strip()
    )
    removed_paths = tuple(
        str(item).strip() for item in payload.get("removed_paths", ()) or ()
        if str(item).strip()
    )
    projected: dict[str, Any] = {}
    file_rows = {path: {"status": "modified", "step": step} for path in modified_paths}
    file_rows.update({path: {"status": "created", "step": step} for path in created_paths})
    if file_rows:
        projected["files"] = file_rows
    if created_paths:
        projected["artifacts"] = {
            item: {"status": "available", "step": step} for item in created_paths
        }
    if removed_paths:
        projected["removed_files"] = list(removed_paths)
        projected["removed_artifacts"] = list(removed_paths)
    return projected


def _observed_changed_paths_projection(
    world_state: WorldState,
    receipt: Receipt,
    payload: Mapping[str, Any],
    ledger: ExecutionLedger,
) -> dict[str, Any] | None:
    """Accumulate executor-observed mutation facts without inventing coverage."""
    created = tuple(str(item).strip() for item in payload.get("artifact_paths", ()) or () if str(item).strip())
    modified = tuple(str(item).strip() for item in payload.get("modified_paths", ()) or () if str(item).strip())
    removed = tuple(str(item).strip() for item in payload.get("removed_paths", ()) or () if str(item).strip())
    state_delta = payload.get("state_delta")
    # These categories are intentionally populated only from executor facts.
    # A generic command string is not evidence that a file was read, nor is a
    # newly-created file automatically compiler residue.  Executors that can
    # observe either fact may supply it in the receipt/state delta.
    generated_residue = tuple(
        str(item).strip()
        for item in (
            payload.get("generated_residue_paths", ())
            or (state_delta.get("generated_residue_paths", ()) if isinstance(state_delta, Mapping) else ())
        )
        if str(item).strip()
    )
    read = tuple(
        str(item).strip()
        for item in payload.get("read_paths", ()) or ()
        if str(item).strip()
    )
    if receipt.kind in {"read_file", "read_file_page"}:
        path = str(payload.get("path", "") or "").strip()
        if path:
            read = (*read, path)
    mutation_status = (
        str(state_delta.get("mutation_detection_status", "")).strip()
        if isinstance(state_delta, Mapping) else ""
    )
    if not (created or modified or removed or generated_residue or read or mutation_status):
        return None
    prior = world_state.named_sections.get("observed_changed_paths")
    prior = prior if isinstance(prior, Mapping) else {}

    def merged(name: str, new: tuple[str, ...]) -> list[str]:
        old = prior.get(name, ())
        old = old if isinstance(old, (tuple, list)) else ()
        return sorted({str(item).strip() for item in (*old, *new) if str(item).strip()})

    uncertain = mutation_status in {"coarse", "truncated", "unavailable"}
    return {
        "schema_version": "observed_changed_paths.v2",
        "created": merged("created", created),
        "modified": merged("modified", modified),
        "removed": merged("removed", removed),
        "generated_residue": merged("generated_residue", generated_residue),
        "read": merged("read", read),
        "last_observation_receipt_id": receipt.receipt_id,
        "task_state_generation": ledger.task_state_generation(),
        # This is a path-delta record, not an omniscient filesystem inventory.
        "external_state_unknown": bool(prior.get("external_state_unknown", False) or uncertain),
        "latest_mutation_detection_status": mutation_status or "not_reported",
        "content_hash_availability": "unknown_without_captured_bytes",
    }


def _update_world_from_receipt(
    world_state: WorldState | None,
    receipt: Receipt,
    *,
    step: int,
    ledger: ExecutionLedger,
) -> None:
    """Project compact, receipt-backed state into the verifier WorldState.

    The verifier must see current state, but never needs raw command output.
    Keep only typed hashes/handles/status fields and treat malformed projection
    as a harness-owned receipt rather than mutating state partially.
    """
    if world_state is None:
        return
    payload = receipt.payload if isinstance(receipt.payload, dict) else {}
    delta: dict[str, Any] = {}
    path = str(payload.get("path", "") or "").strip()
    if receipt.kind in {"write_file", "read_file", "read_file_page"} and path:
        prior_file = world_state.files.get(path) if world_state is not None else None
        prior_status = (
            str(prior_file.get("status", "")).strip()
            if isinstance(prior_file, dict)
            else ""
        )
        if receipt.kind == "write_file":
            file_status = "modified"
        elif prior_status in {"created", "modified"}:
            # Observation may refresh hashes and handles, but it must not erase
            # the already-known mutation status of the current task episode.
            file_status = prior_status
        else:
            file_status = "present"
        delta["files"] = {
            path: {
                "status": file_status,
                "step": step,
                "bytes": payload.get("bytes", payload.get("before_bytes", 0)),
                "content_sha256": payload.get("content_sha256", ""),
                "content_sha256_provenance": payload.get("content_sha256_provenance", ""),
                "handle": payload.get("file_handle", f"file:{path}"),
            }
        }
        if receipt.kind == "write_file":
            delta["artifacts"] = {
                path: {"status": "available", "step": step}
            }
    elif receipt.kind in {
        "run_command", "check_result", "schema_validation",
        "environment_extension", "bootstrap", "experiment",
        "terminal_start", "terminal_send", "terminal_read", "terminal_wait",
        "terminal_interrupt", "terminal_close",
    }:
        delta.update(_receipt_path_projection(payload, step=step))
        delta["latest_result"] = {
            "status": "passed" if receipt.success else "failed",
            "step": step,
            "kind": receipt.kind,
            "returncode": payload.get("exit_code", 0 if receipt.success else 1),
            "stdout_handle": payload.get("stdout_handle", ""),
            "stderr_handle": payload.get("stderr_handle", ""),
            "sha256": payload.get("content_hash", ""),
        }
    elif receipt.kind == "job_probe":
        delta.update(_receipt_path_projection(payload, step=step))
        identifier = str(payload.get("job_id") or payload.get("process_id") or payload.get("target") or "").strip()
        if identifier:
            generation = str(payload.get("process_generation", "") or "").strip()
            registered = ledger.processes.get(identifier)
            generation_verified = bool(payload.get("process_generation_verified", False))
            current_generation = bool(
                receipt.success
                and registered is not None
                and generation_verified
                and generation
                and generation == str(registered.get("process_generation", ""))
            )
            observed_state = str(payload.get("job_status", "unknown"))
            delta["jobs"] = {identifier: {
                "state": observed_state if current_generation else "unverified",
                "step": step,
                "pid": payload.get("pid"),
                "returncode": payload.get("exit_code") if current_generation else None,
                "process_generation": generation,
                "process_generation_verified": bool(current_generation),
                "lifecycle_authority": payload.get("lifecycle_authority", ""),
                "completed": bool(payload.get("completed", False)) if current_generation else False,
                "job_succeeded": payload.get("job_succeeded") if current_generation else None,
            }}
            delta["latest_result"] = {
                "status": (
                    "observed" if current_generation
                    else ("unverified" if receipt.success else "failed")
                ),
                "step": step,
                "kind": receipt.kind,
                "returncode": payload.get("exit_code") if current_generation else None,
            }
    elif receipt.kind in {"process_launch", "process_stop", "service_probe"}:
        delta.update(_receipt_path_projection(payload, step=step))
        # Production process receipts use ``service_name`` / ``process_id``.
        # Accept older aliases only as a read-side compatibility projection;
        # the executor remains the sole owner of process creation/teardown.
        identifier = str(
            payload.get("service_name")
            or payload.get("process_id")
            or payload.get("service")
            or payload.get("name")
            or payload.get("process")
            or ""
        ).strip()
        if identifier:
            # A failed teardown is an action outcome, not a service-state
            # transition. The authoritative ledger preserves the last known
            # live generation, so leave the Verifier-facing world state intact
            # as well rather than replacing running/ready with stop_failed.
            if receipt.kind == "process_stop" and not receipt.success:
                return
            process_id = str(payload.get("process_id", "") or "").strip()
            process_generation = str(payload.get("process_generation", "") or "").strip()
            generation_verified = bool(payload.get("process_generation_verified", False))
            registered = ledger.processes.get(process_id) if process_id else None
            readiness: bool | None = None
            if receipt.kind == "process_stop":
                # stop_process accepts either a process ID or service name, but
                # its receipt carries that input alias in both fields. Resolve
                # the alias back through the authoritative process registry so
                # the Verifier does not leave the real service/job generation
                # falsely running under its original key.
                stop_target = process_id or identifier
                matches = [
                    (registered_id, row)
                    for registered_id, row in ledger.processes.items()
                    if registered_id == stop_target
                    or str(row.get("name", "")).strip() == stop_target
                ]
                if matches:
                    resolved_id, registered = matches[-1]
                    process_id = resolved_id
                    process_generation = str(registered.get("process_generation", "")).strip()
                    identifier = str(registered.get("name", "")).strip() or identifier
                state = "stopped" if receipt.success else "stop_failed"
                readiness = False if receipt.success else None
            elif receipt.kind == "process_launch":
                state = "running" if receipt.success else "failed"
            else:
                # A TCP endpoint can be live while being owned by an unrelated
                # process.  Do not project that as service readiness. Bind the
                # observation to the currently registered live process
                # generation before exposing ``ready`` to the Verifier.
                current_generation = bool(
                    receipt.success
                    and registered is not None
                    and bool(registered.get("live", False))
                    and generation_verified
                    and process_generation
                    and process_generation == str(registered.get("process_generation", ""))
                    and identifier == str(registered.get("name", ""))
                )
                readiness = bool(current_generation)
                if current_generation:
                    state = "ready"
                elif receipt.success:
                    state = "unverified_live"
                else:
                    state = "not_ready"
            process_row = {
                "state": state,
                "step": step,
                "pid": payload.get("pid", registered.get("pid") if registered else None),
                "port": payload.get("port"),
                "readiness": readiness,
                "process_generation": process_generation,
                "process_generation_verified": bool(
                    generation_verified and process_generation
                ),
            }
            delta["services"] = {identifier: process_row}
            if receipt.kind == "process_launch" and str(payload.get("launch_mode", "")) == "background_job":
                delta["jobs"] = {str(payload.get("job_id") or identifier): {
                    **process_row,
                    "process_generation": payload.get("process_generation"),
                }}
            elif (
                receipt.kind == "process_stop"
                and receipt.success
                and world_state is not None
                and process_id in world_state.jobs
            ):
                delta["jobs"] = {process_id: {
                    "state": "stopped",
                    "step": step,
                    "pid": registered.get("pid") if registered else None,
                    "readiness": False,
                    "process_generation": process_generation,
                    "process_generation_verified": False,
                    "completed": False,
                }}
    observed_changes = _observed_changed_paths_projection(
        world_state, receipt, payload, ledger,
    )
    if observed_changes is not None:
        delta.setdefault("named_sections", {})["observed_changed_paths"] = observed_changes
    if not delta:
        return
    try:
        world_state.apply_delta(delta, step=step)
    except WorldStateDeltaError as exc:
        ledger.record(Receipt(
            receipt_id=f"step-{step}:world_state_projection:{receipt.receipt_id}",
            step=step,
            kind="world_state_projection_failed",
            success=False,
            summary=f"world-state projection rejected receipt {receipt.receipt_id}: {exc}",
            failure_class="harness_state_projection",
            payload={"source_receipt_id": receipt.receipt_id},
        ))


def run_submit_turn(
    kernel: Any,
    step: int,
    compiled: CompiledRuntime,
    executor: Executor,
    envmap: EnvMap,
    ledger: ExecutionLedger,
    trace: "RunTrace | None",
) -> None:
    """Execute the deterministic mechanical completion checks; stores the gate decision on the kernel."""
    for check in compiled.planned_checks():
        if not _check_inputs_changed(ledger, check.check_id):
            # Nothing in the workspace changed since this check last ran; the
            # prior outcome (still held by the ledger's check store) stands.
            # Re-executing identical checks burned hundreds of receipts live.
            ledger.record(Receipt(
                receipt_id=f"step-{step}:check_skipped:{check.check_id}", step=step,
                kind="check_skipped_unchanged", success=True,
                summary=f"check {check.label} not re-run: no state change since last execution",
                payload={"check_id": check.check_id, "command": check.command},
            ))
            continue
        result = executor.run_command(check.command, cwd=envmap.workspace_root)
        failure_class = kernel.failure_parser.classify(
            result.stdout + "\n" + result.stderr, exit_code=result.exit_code,
        ) if not result.success else ""
        ledger.record(Receipt(
            receipt_id=f"step-{step}:check:{check.check_id}", step=step,
            kind="check_result", success=result.success,
            summary=f"check {check.label}: exit={result.exit_code}",
            # A planned check observes the current workspace; it does not
            # itself advance task-state freshness.
            state_change=False, failure_class=failure_class,
            payload={
                **ledger.current_snapshot_binding_payload(),
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
            payload=ledger.current_snapshot_binding_payload(),
        ))
    alerts = kernel.monitor_runner.run(compiled, ledger)
    decision = kernel.completion_gate.evaluate(compiled, ledger, alerts)
    if trace is not None:
        trace.add_gate(step, decision)
    kernel._last_gate_decision = decision

def _check_inputs_changed(ledger: ExecutionLedger, check_id: str) -> bool:
    """True when the check has never run, or any state change happened after
    its most recent execution."""
    receipts = ledger.all_receipts()
    last_index = -1
    for index, receipt in enumerate(receipts):
        if receipt.kind == "check_result" and (receipt.payload or {}).get("check_id") == check_id:
            last_index = index
    if last_index < 0:
        return True
    return any(
        r.state_change or ledger.is_uncertain_task_state_boundary(r)
        for r in receipts[last_index + 1:]
    )
