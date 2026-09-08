"""Capability-specific mechanical repetition control for PCR V0.

No semantic loop, intent loop, strategy judgment, or model-authored bypass is
used. Decisions depend only on canonical action identity, declared relevant
state, exact normalized results, tracked state change, and one bounded
Kernel-issued retry permit.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Mapping

from .ledger import ExecutionLedger, Receipt
from .runtime_ir import ActionRequest, stable_json


@dataclass(frozen=True)
class RepeatCapabilityDeclaration:
    mode: str
    relevant_state: str
    reuse_safe: bool = False


PCR_REPEAT_DECLARATIONS: dict[str, RepeatCapabilityDeclaration] = {
    "read_output": RepeatCapabilityDeclaration(
        "immutable_read", "immutable_output_or_receipt_handle", True,
    ),
    "grep_output": RepeatCapabilityDeclaration(
        "immutable_read", "immutable_output_or_receipt_handle_and_pattern", True,
    ),
    "read_file": RepeatCapabilityDeclaration("bounded_repeat", "path_state_and_task_generation"),
    "read_file_page": RepeatCapabilityDeclaration("bounded_repeat", "path_state_and_task_generation"),
    "inspect_artifact": RepeatCapabilityDeclaration("bounded_repeat", "path_state_and_task_generation"),
    "inspect_diff": RepeatCapabilityDeclaration("bounded_repeat", "path_state_and_task_generation"),
    "write_file": RepeatCapabilityDeclaration("bounded_repeat", "path_state_and_task_generation"),
    "run_command": RepeatCapabilityDeclaration("bounded_repeat", "task_state_generation"),
    "probe_service": RepeatCapabilityDeclaration("bounded_repeat", "target_state_and_task_generation"),
    "probe_job": RepeatCapabilityDeclaration("bounded_repeat", "target_state_and_task_generation"),
    "launch_process": RepeatCapabilityDeclaration("bounded_repeat", "target_state_and_task_generation"),
    "start_job": RepeatCapabilityDeclaration("bounded_repeat", "target_state_and_task_generation"),
    "stop_process": RepeatCapabilityDeclaration("bounded_repeat", "target_state_and_task_generation"),
    "bootstrap_acquire": RepeatCapabilityDeclaration("bounded_repeat", "task_state_generation"),
    # Diagnostic blocker reporting must not become an infinite action sink.
    # One report per unchanged task-state/classification is enough to preserve
    # the evidence; subsequent rewordings add no new reality.
    "report_blocker": RepeatCapabilityDeclaration("one_per_state", "task_state_generation"),
}


@dataclass(frozen=True)
class PCRRepeatDecision:
    consequence: str
    action_signature: str
    relevant_state_fingerprint: str
    declaration: RepeatCapabilityDeclaration | None
    prior_observation_ids: tuple[str, ...] = ()
    reused_outcome_receipt_ids: tuple[str, ...] = ()
    permit_receipt_id: str = ""
    issue_permit: bool = False
    detail: str = ""


def pending_execution_commitment(
    action: ActionRequest,
    ledger: ExecutionLedger,
) -> Receipt | None:
    """Return an earlier accepted action that lacks a durable outcome boundary.

    A process can fail after an external dispatch but before its result receipt
    is appended.  Re-dispatching the same canonical action from a recovered
    ledger could duplicate that external effect.  This check intentionally
    fails closed for that exact action/state identity; a later, observed state
    transition gives a new fingerprint and is evaluated normally.
    """
    declaration = PCR_REPEAT_DECLARATIONS.get(action.kind)
    identity = dict(getattr(ledger, "runtime_identity", {}) or {})
    signature = action_signature(action, identity)
    state = relevant_state_fingerprint(action, ledger, declaration)
    receipts_by_id = {
        receipt.receipt_id: receipt for receipt in ledger.all_receipts()
    }
    for receipt in reversed(ledger.all_receipts()):
        if receipt.kind != "pcr_action_execution_pending":
            continue
        payload = receipt.payload or {}
        if (
            str(payload.get("action_signature", "")) == signature
            and str(payload.get("relevant_state_fingerprint", "")) == state
        ):
            # A bookkeeping record must not close the at-most-once boundary by
            # itself.  The commit is authoritative only when it is a successful,
            # intact record that names at least one intact, already-recorded
            # concrete execution result.  In particular, an empty outcome list
            # (or a list containing only missing/control receipts) remains an
            # unresolved dispatch and therefore stays blocked.
            for commit in reversed(ledger.all_receipts()):
                if commit.kind != "pcr_action_execution_committed":
                    continue
                commit_payload = commit.payload if isinstance(commit.payload, Mapping) else {}
                if (
                    commit.success is not True
                    or not ledger.receipt_payload_is_intact(commit)
                    or str(commit_payload.get("pending_receipt_id", "")) != receipt.receipt_id
                    or str(commit_payload.get("action_signature", "")) != str(payload.get("action_signature", ""))
                    or str(commit_payload.get("relevant_state_fingerprint", "")) != str(payload.get("relevant_state_fingerprint", ""))
                    or commit_payload.get("outcome_observed") is not True
                ):
                    continue
                outcome_ids = commit_payload.get("outcome_receipt_ids", ())
                if isinstance(outcome_ids, str):
                    outcome_ids = (outcome_ids,)
                if not isinstance(outcome_ids, (list, tuple)) or not outcome_ids:
                    continue
                normalized_ids = tuple(str(item).strip() for item in outcome_ids)
                if (
                    any(not item for item in normalized_ids)
                    or len(set(normalized_ids)) != len(normalized_ids)
                    or any(item not in receipts_by_id for item in normalized_ids)
                ):
                    continue
                outcomes = tuple(receipts_by_id[item] for item in normalized_ids)
                if any(
                    outcome.kind in {
                        "pcr_action_execution_pending",
                        "pcr_action_execution_committed",
                        "pcr_action_execution_uncommitted",
                    }
                    or not ledger.receipt_payload_is_intact(outcome)
                    for outcome in outcomes
                ):
                    continue
                return None
            return receipt
    return None


def action_execution_pending_receipt(
    action: ActionRequest,
    ledger: ExecutionLedger,
    *,
    step: int,
) -> Receipt:
    """Persist the no-result-yet boundary immediately before dispatch."""
    declaration = PCR_REPEAT_DECLARATIONS.get(action.kind)
    identity = dict(getattr(ledger, "runtime_identity", {}) or {})
    signature = action_signature(action, identity)
    state = relevant_state_fingerprint(action, ledger, declaration)
    return Receipt(
        receipt_id=f"step-{step}:{action.action_id}:pcr_action_execution_pending",
        step=step,
        kind="pcr_action_execution_pending",
        success=True,
        summary="accepted action is pending an observed execution result",
        payload={
            "action_id": action.action_id,
            "action_kind": action.kind,
            "action_signature": signature,
            "relevant_state_fingerprint": state,
            "dispatch_started": False,
            "outcome_observed": False,
            "at_most_once_boundary": True,
        },
    )


def action_execution_committed_receipt(
    action: ActionRequest,
    pending: Receipt,
    outcomes: tuple[Receipt, ...],
    *,
    step: int,
) -> Receipt:
    """Close a pending execution only after concrete result receipts exist.

    Empty or malformed outcomes get an explicit *uncommitted* receipt.  This
    keeps the failed boundary observable without producing a
    ``pcr_action_execution_committed`` record that could be mistaken for an
    idempotency proof.  A later recovery can therefore append the real commit
    under its normal receipt ID without colliding with the failed attempt.
    """
    rows = tuple(outcomes)
    outcome_ids = tuple(
        str(receipt.receipt_id).strip()
        for receipt in rows
        if isinstance(receipt, Receipt) and str(receipt.receipt_id).strip()
    )
    admitted = bool(rows) and len(outcome_ids) == len(rows) and len(set(outcome_ids)) == len(outcome_ids)
    kind = "pcr_action_execution_committed" if admitted else "pcr_action_execution_uncommitted"
    suffix = kind
    return Receipt(
        receipt_id=f"step-{step}:{action.action_id}:{suffix}",
        step=step,
        kind=kind,
        success=admitted,
        summary=(
            "accepted action has durable observed execution result receipts"
            if admitted else
            "accepted action has no durable observed execution result; boundary remains pending"
        ),
        failure_class="" if admitted else "unresolved_action_execution",
        payload={
            "pending_receipt_id": pending.receipt_id,
            "action_id": action.action_id,
            "action_kind": action.kind,
            "action_signature": str((pending.payload or {}).get("action_signature", "")),
            "relevant_state_fingerprint": str(
                (pending.payload or {}).get("relevant_state_fingerprint", "")
            ),
            "outcome_receipt_ids": list(outcome_ids),
            "outcome_observed": admitted,
            "commit_admitted": admitted,
            "at_most_once_boundary": True,
        },
    )


def _repeat_identity_arguments(action: ActionRequest) -> dict[str, Any]:
    """Return capability arguments that define one mechanical repeat identity.

    ``run_command.timeout_s`` is an execution budget, not executable semantics.
    Treating it as command identity lets an unchanged command evade repeat
    control merely by cycling 10/20/30 second budgets after the same successful
    result.  The actual timeout remains on the ActionRequest and execution
    receipt; only the repeat fingerprint omits it.  Helper path/mode and every
    other argument remain identity-bearing.  A prior timeout is still observable
    through the result fingerprint and the existing bounded retry permit.
    """
    arguments = dict(action.arguments)
    if action.kind == "run_command":
        arguments.pop("timeout_s", None)
    if action.kind == "report_blocker":
        # Natural-language rephrasing is not mechanical novelty. Preserve only
        # the optional typed attribution classes in the repeat identity.
        return {
            key: str(arguments.get(key, "")).strip()
            for key in ("harness_constraint", "possible_missing_capability")
            if str(arguments.get(key, "")).strip()
        }
    return arguments



def action_signature(action: ActionRequest, identity: Mapping[str, Any]) -> str:
    return sha256(stable_json({
        "kind": action.kind,
        "capability_id": action.capability_id,
        "arguments": _repeat_identity_arguments(action),
        "workspace_id": identity.get("workspace_id", ""),
        "environment_id": identity.get("environment_id", ""),
    }).encode("utf-8")).hexdigest()


def _workspace_path_key(ledger: ExecutionLedger, path: Any) -> str:
    value = str(path or "").strip()
    workspace_root = str(
        (getattr(ledger, "runtime_identity", {}) or {}).get("workspace_id", "") or ""
    ).strip().rstrip("/")
    roots = tuple(
        root for root in dict.fromkeys((workspace_root, "/app")) if root
    )
    for root in roots:
        if value == root:
            return ""
        prefix = root + "/"
        if value.startswith(prefix):
            return value[len(prefix):]
    return value


def _latest_path_state(ledger: ExecutionLedger, path: str) -> dict[str, Any]:
    normalized = _workspace_path_key(ledger, path)
    for receipt in reversed(ledger.all_receipts()):
        payload = receipt.payload if isinstance(receipt.payload, Mapping) else {}
        receipt_path = _workspace_path_key(ledger, payload.get("path", ""))
        modified = {
            _workspace_path_key(ledger, item)
            for item in payload.get("modified_paths", ()) or ()
        }
        if normalized and normalized not in {receipt_path, *modified}:
            continue
        hashes = {
            key: payload.get(key)
            for key in (
                "content_hash",
                "after_content_hash",
                "before_content_hash",
                "sha256",
                "bytes",
                "exists",
            )
            if payload.get(key) not in (None, "")
        }
        if hashes:
            return {
                "source_receipt_id": receipt.receipt_id,
                "state": hashes,
            }
    return {"source_receipt_id": "", "state": "unknown"}


def _immutable_handle_state(ledger: ExecutionLedger, handle: str) -> dict[str, Any]:
    value = str(handle or "").strip()
    if value.startswith("receipt:"):
        receipt_id = value.split(":", 1)[1]
        receipt = next((
            row for row in ledger.all_receipts() if row.receipt_id == receipt_id
        ), None)
        if receipt is None:
            return {"handle": value, "state": "missing"}
        return {
            "handle": value,
            "receipt_id": receipt.receipt_id,
            "sha256": sha256(stable_json({
                "kind": receipt.kind,
                "success": receipt.success,
                "summary": receipt.summary,
                "state_change": receipt.state_change,
                "failure_class": receipt.failure_class,
                "payload": receipt.payload,
            }).encode("utf-8")).hexdigest(),
        }
    for receipt in reversed(ledger.all_receipts()):
        payload = receipt.payload if isinstance(receipt.payload, Mapping) else {}
        for key, stream in (("stdout_handle", "stdout"), ("stderr_handle", "stderr")):
            if str(payload.get(key, "") or "") == value:
                return {
                    "handle": value,
                    "stream": stream,
                    "sha256": payload.get(f"{stream}_hash", ""),
                    "bytes": payload.get(f"{stream}_bytes", 0),
                    "source_receipt_id": receipt.receipt_id,
                }
    return {"handle": value, "state": "unresolved"}


def _repeat_task_state_generation(action: ActionRequest, ledger: ExecutionLedger) -> int:
    """Return task generation without self-manufactured opaque-command novelty.

    Freshness uncertainty must invalidate old completion evidence, but rerunning
    the exact same opaque command must not make that command look mechanically
    novel forever. Subtract only uncertain, non-concrete boundaries produced by
    the same command. Uncertainty from another action and every concrete task
    mutation remain repeat-relevant.
    """
    generation = ledger.task_state_generation()
    if action.kind != "run_command":
        return generation
    command = str(action.arguments.get("command", ""))
    self_uncertain = 0
    for receipt in ledger.all_receipts():
        if receipt.kind != "run_command" or receipt.state_change:
            continue
        payload = receipt.payload if isinstance(receipt.payload, Mapping) else {}
        if str(payload.get("command", "")) != command:
            continue
        if ledger.is_uncertain_task_state_boundary(receipt):
            self_uncertain += 1
    return max(0, generation - self_uncertain)


def relevant_state_fingerprint(
    action: ActionRequest,
    ledger: ExecutionLedger,
    declaration: RepeatCapabilityDeclaration | None,
) -> str:
    if declaration is None:
        material: Any = {"mode": "not_repeat_controlled"}
    elif declaration.relevant_state.startswith("immutable_output"):
        material = _immutable_handle_state(
            ledger, str(action.arguments.get("handle", "")),
        )
    elif "path_state" in declaration.relevant_state:
        # Observation identity is not task state.  _latest_path_state keeps the
        # source receipt for diagnostics, but hashing that receipt ID would make
        # every identical read manufacture a new relevant-state fingerprint and
        # therefore defeat mechanical repeat detection.
        path_state = _latest_path_state(
            ledger, str(action.arguments.get("path", "")),
        )
        material = {
            "path": _workspace_path_key(ledger, action.arguments.get("path", "")),
            "path_state": path_state.get("state", "unknown"),
            "task_state_generation": ledger.task_state_generation(),
        }
    elif "target_state" in declaration.relevant_state:
        target = str(
            action.arguments.get("target", "")
            or action.arguments.get("service_name", "")
        )
        latest = next((
            receipt for receipt in reversed(ledger.all_receipts())
            if str((receipt.payload or {}).get("target", "") or "") == target
            or str((receipt.payload or {}).get("service_name", "") or "") == target
        ), None)
        material = {
            "target": target,
            "task_state_generation": ledger.task_state_generation(),
            "latest_target_receipt": (
                {
                    "kind": latest.kind,
                    "success": latest.success,
                    "state_change": latest.state_change,
                    "payload": latest.payload,
                }
                if latest is not None else None
            ),
        }
    else:
        material = {
            "task_state_generation": _repeat_task_state_generation(action, ledger),
            "check_id": str(action.arguments.get("check_id", "")),
        }
    return sha256(stable_json(material).encode("utf-8")).hexdigest()


def _observations(
    ledger: ExecutionLedger,
    *,
    signature: str,
    state_fingerprint: str,
) -> list[Receipt]:
    return [
        receipt
        for receipt in ledger.all_receipts()
        if receipt.kind == "pcr_repeat_observation"
        and str((receipt.payload or {}).get("action_signature", "")) == signature
        and str((receipt.payload or {}).get("relevant_state_fingerprint", "")) == state_fingerprint
    ]


def _permit_rows(
    ledger: ExecutionLedger,
    *,
    signature: str,
    state_fingerprint: str,
) -> tuple[list[Receipt], set[str]]:
    permits = [
        receipt for receipt in ledger.all_receipts()
        if receipt.kind == "pcr_repeat_permit"
        and str((receipt.payload or {}).get("action_signature", "")) == signature
        and str((receipt.payload or {}).get("relevant_state_fingerprint", "")) == state_fingerprint
    ]
    consumed = {
        str((receipt.payload or {}).get("permit_receipt_id", ""))
        for receipt in ledger.all_receipts()
        if receipt.kind == "pcr_repeat_permit_consumed"
    }
    return permits, consumed


def evaluate_pcr_repeat(
    action: ActionRequest,
    ledger: ExecutionLedger,
    *,
    step: int,
) -> PCRRepeatDecision:
    declaration = PCR_REPEAT_DECLARATIONS.get(action.kind)
    identity = dict(getattr(ledger, "runtime_identity", {}) or {})
    signature = action_signature(action, identity)
    state = relevant_state_fingerprint(action, ledger, declaration)
    if declaration is None:
        return PCRRepeatDecision("allow", signature, state, None)

    prior = _observations(ledger, signature=signature, state_fingerprint=state)
    if declaration.mode == "one_per_state" and prior:
        return PCRRepeatDecision(
            "block", signature, state, declaration,
            prior_observation_ids=(prior[-1].receipt_id,),
            issue_permit=False,
            detail=(
                "diagnostic report already recorded for the same unchanged task state; "
                "new external evidence or state change is required before another report"
            ),
        )
    if declaration.reuse_safe and prior:
        prior_reuses = [
            receipt for receipt in ledger.all_receipts()
            if receipt.kind == "pcr_repeat_reuse"
            and str((receipt.payload or {}).get("action_signature", "")) == signature
            and str((receipt.payload or {}).get("relevant_state_fingerprint", "")) == state
        ]
        if len(prior_reuses) >= 2:
            return PCRRepeatDecision(
                "block",
                signature,
                state,
                declaration,
                prior_observation_ids=tuple(row.receipt_id for row in prior_reuses[-2:]),
                issue_permit=False,
                detail=(
                    "the same immutable result has already been returned twice without "
                    "re-execution under the same relevant state"
                ),
            )
        latest = prior[-1]
        return PCRRepeatDecision(
            "reuse",
            signature,
            state,
            declaration,
            prior_observation_ids=(latest.receipt_id,),
            reused_outcome_receipt_ids=tuple(
                str(item)
                for item in (latest.payload or {}).get("outcome_receipt_ids", ()) or ()
            ),
            detail="immutable handle and canonical action are unchanged",
        )

    no_change = [
        receipt for receipt in prior
        if not bool((receipt.payload or {}).get("state_changed"))
        and str((receipt.payload or {}).get("result_fingerprint", ""))
    ]
    if len(no_change) < 2:
        return PCRRepeatDecision(
            "allow", signature, state, declaration,
            prior_observation_ids=tuple(row.receipt_id for row in no_change[-2:]),
        )
    last_two = no_change[-2:]
    result_hashes = {
        str((receipt.payload or {}).get("result_fingerprint", ""))
        for receipt in last_two
    }
    if len(result_hashes) != 1:
        return PCRRepeatDecision(
            "allow", signature, state, declaration,
            prior_observation_ids=tuple(row.receipt_id for row in last_two),
        )

    permits, consumed = _permit_rows(
        ledger, signature=signature, state_fingerprint=state,
    )
    usable = next((
        permit for permit in reversed(permits)
        if permit.receipt_id not in consumed
        and int((permit.payload or {}).get("expiry_turn", -1)) >= step
    ), None)
    if usable is not None:
        return PCRRepeatDecision(
            "allow_with_permit",
            signature,
            state,
            declaration,
            prior_observation_ids=tuple(row.receipt_id for row in last_two),
            permit_receipt_id=usable.receipt_id,
            detail="one Kernel-issued signature-bound retry permit is available",
        )
    return PCRRepeatDecision(
        "block",
        signature,
        state,
        declaration,
        prior_observation_ids=tuple(row.receipt_id for row in last_two),
        issue_permit=not permits,
        detail=(
            "the same canonical action produced the same normalized result twice "
            "under the same capability-declared relevant state with no tracked state change"
        ),
    )


def _result_fingerprint(receipts: list[Receipt]) -> str:
    excluded = {
        "runtime_accounting",
        "primary_decision",
        "solver_decision_state",
        "automatic_memory",
        "pcr_repeat_permit_consumed",
        "pcr_action_execution_pending",
        "pcr_action_execution_committed",
    }
    rows = []
    for receipt in receipts:
        if receipt.kind in excluded:
            continue
        payload = dict(receipt.payload or {})
        for key in tuple(payload):
            if key.endswith("_handle") or key in {
                "duration_ms", "started_at", "ended_at", "timestamp",
            }:
                payload.pop(key, None)
        rows.append({
            "kind": receipt.kind,
            "success": receipt.success,
            "state_change": receipt.state_change,
            "failure_class": receipt.failure_class,
            "payload": payload,
        })
    return sha256(stable_json(rows).encode("utf-8")).hexdigest()


def record_repeat_observation(
    action: ActionRequest,
    decision: PCRRepeatDecision,
    *,
    step: int,
    step_receipts: list[Receipt],
    ledger: ExecutionLedger,
) -> Receipt:
    action_marker = f":{action.action_id}:"
    outcomes = [
        receipt for receipt in step_receipts
        if action_marker in receipt.receipt_id
        and receipt.kind not in {
            "primary_decision",
            "runtime_accounting",
            "pcr_repeat_permit_consumed",
            "pcr_action_execution_pending",
            "pcr_action_execution_committed",
        }
    ]
    observed_state_fingerprint = relevant_state_fingerprint(
        action, ledger, decision.declaration,
    )
    return Receipt(
        receipt_id=f"step-{step}:{action.action_id}:pcr_repeat_observation",
        step=step,
        kind="pcr_repeat_observation",
        success=True,
        summary="recorded capability-specific mechanical action/result fingerprint",
        payload={
            "action_signature": decision.action_signature,
            "relevant_state_fingerprint": observed_state_fingerprint,
            "pre_dispatch_state_fingerprint": decision.relevant_state_fingerprint,
            "repeat_mode": (
                decision.declaration.mode if decision.declaration is not None else "none"
            ),
            "relevant_state_owner": (
                decision.declaration.relevant_state if decision.declaration is not None else "none"
            ),
            "result_fingerprint": _result_fingerprint(outcomes),
            "state_changed": any(receipt.state_change for receipt in outcomes),
            "outcome_receipt_ids": [receipt.receipt_id for receipt in outcomes],
            "semantic_loop_judged": False,
            "strategy_judged": False,
        },
    )


def repeat_block_receipts(
    action: ActionRequest,
    decision: PCRRepeatDecision,
    *,
    step: int,
) -> tuple[Receipt, ...]:
    rows = [Receipt(
        receipt_id=f"step-{step}:{action.action_id}:pcr_repeat_block",
        step=step,
        kind="pcr_repeat_block",
        success=False,
        summary=decision.detail,
        failure_class="equivalent_repeat_blocked",
        payload={
            "action_signature": decision.action_signature,
            "relevant_state_fingerprint": decision.relevant_state_fingerprint,
            "repeat_mode": (
                decision.declaration.mode if decision.declaration is not None else ""
            ),
            "relevant_state_owner": (
                decision.declaration.relevant_state if decision.declaration is not None else ""
            ),
            "prior_observation_ids": list(decision.prior_observation_ids),
            "objective_condition": "same_action_same_state_same_result_twice_no_state_change",
            "semantic_loop_judged": False,
            "strategy_judged": False,
        },
    )]
    if decision.issue_permit:
        rows.append(Receipt(
            receipt_id=f"step-{step}:{action.action_id}:pcr_repeat_permit",
            step=step,
            kind="pcr_repeat_permit",
            success=True,
            summary="issued one signature-bound retry permit for the next turn only",
            payload={
                "action_signature": decision.action_signature,
                "relevant_state_fingerprint": decision.relevant_state_fingerprint,
                "issuance_reason": "first mechanical repeat block for this signature and state",
                "remaining_uses": 1,
                "expiry_turn": step + 1,
            },
        ))
    return tuple(rows)


def repeat_reuse_receipt(
    action: ActionRequest,
    decision: PCRRepeatDecision,
    *,
    step: int,
) -> Receipt:
    return Receipt(
        receipt_id=f"step-{step}:{action.action_id}:pcr_repeat_reuse",
        step=step,
        kind="pcr_repeat_reuse",
        success=True,
        summary="returned prior immutable-handle result without re-execution",
        payload={
            "action_signature": decision.action_signature,
            "relevant_state_fingerprint": decision.relevant_state_fingerprint,
            "prior_observation_ids": list(decision.prior_observation_ids),
            "reused_outcome_receipt_ids": list(decision.reused_outcome_receipt_ids),
            "no_new_evidence": True,
            "dispatch_performed": False,
        },
    )


def permit_consumed_receipt(
    action: ActionRequest,
    decision: PCRRepeatDecision,
    *,
    step: int,
) -> Receipt:
    return Receipt(
        receipt_id=f"step-{step}:{action.action_id}:pcr_repeat_permit_consumed",
        step=step,
        kind="pcr_repeat_permit_consumed",
        success=True,
        summary="consumed one Kernel-issued retry permit",
        payload={
            "permit_receipt_id": decision.permit_receipt_id,
            "action_signature": decision.action_signature,
            "relevant_state_fingerprint": decision.relevant_state_fingerprint,
            "remaining_uses": 0,
        },
    )
