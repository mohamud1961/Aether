"""Active one-hold response to a mechanical verification-oracle edit observation.

V1b is deliberately mechanical.  The kernel does not decide whether the check
or the implementation is semantically correct.  It holds the first finish once,
keeps a factual obligation visible, then requires Primary either to:
- resolve it after a non-verification workspace mutation and current evidence; or
- explicitly disposition the observation as not applicable/overridden with an
  explanation.

The observation source is the deterministic verification-oracle guard, never a
model verdict.
"""
from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import json
from typing import Any, Mapping

from .ledger import Receipt
from .verification_oracle_guard import is_verification_path
from .verifier import VerifierFinding

CONTROL = "control"
ORACLE_HOLD_ONCE_V1 = "oracle_hold_once_v1"
SUPPORTED_MODES = frozenset({CONTROL, ORACLE_HOLD_ONCE_V1})
_FINDING_PREFIX = "oracle-hold-"
_HOLD_KIND = "v1b_oracle_finish_hold"
_DISPOSITION_KIND = "v1b_oracle_disposition"


def normalize_mode(value: str | None) -> str:
    mode = str(value or CONTROL).strip().lower()
    if mode not in SUPPORTED_MODES:
        raise ValueError(f"unsupported oracle finish response mode: {value!r}")
    return mode


def _edit(signal: Mapping[str, Any] | None) -> Mapping[str, Any] | None:
    if not isinstance(signal, Mapping):
        return None
    value = signal.get("verification_edit_observation")
    if not isinstance(value, Mapping):
        return None
    if value.get("edited_after_reported_failure") is not True:
        return None
    return value


def incident_key(signal: Mapping[str, Any] | None) -> str | None:
    edit = _edit(signal)
    if edit is None:
        return None
    payload = {
        "source_receipt_ids": list(signal.get("source_receipt_ids") or ()),
        "failed_receipt_ids": list(edit.get("failed_receipt_ids") or ()),
        "verification_files_changed": list(edit.get("verification_files_changed") or ()),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return sha256(raw.encode("utf-8")).hexdigest()


def finding_id_for(signal: Mapping[str, Any] | None) -> str | None:
    key = incident_key(signal)
    return f"{_FINDING_PREFIX}{key[:20]}" if key else None


def is_v1b_finding_id(value: Any) -> bool:
    return str(value or "").startswith(_FINDING_PREFIX)


def held_incident_keys(ledger: Any) -> set[str]:
    keys: set[str] = set()
    for receipt in ledger.all_receipts():
        if getattr(receipt, "kind", "") != _HOLD_KIND:
            continue
        payload = getattr(receipt, "payload", {}) or {}
        key = str(payload.get("incident_key") or "").strip()
        if key:
            keys.add(key)
    return keys


def should_hold_finish(ledger: Any, signal: Mapping[str, Any] | None, *, mode: str) -> bool:
    if normalize_mode(mode) == CONTROL:
        return False
    key = incident_key(signal)
    return bool(key and key not in held_incident_keys(ledger))


def record_finish_hold(
    ledger: Any,
    *,
    step: int,
    signal: Mapping[str, Any],
) -> str:
    key = incident_key(signal)
    finding_id = finding_id_for(signal)
    edit = _edit(signal)
    if not key or not finding_id or edit is None:
        raise ValueError("V1b hold requires a verification-edit observation")
    generation = int(ledger.task_state_generation())
    observation = str(edit.get("observation") or "").strip()
    files = tuple(str(p) for p in (edit.get("verification_files_changed") or ()) if str(p))
    failed_ids = tuple(str(p) for p in (edit.get("failed_receipt_ids") or ()) if str(p))
    source_ids = tuple(str(p) for p in (signal.get("source_receipt_ids") or ()) if str(p))

    # The active store is the existing completion-obligation lifecycle.  This
    # finding is kernel-origin factual state, not a model-verifier result.
    ledger.findings.active[finding_id] = VerifierFinding(
        finding_id=finding_id,
        created_step=int(step),
        verdict="needs_repair",
        priority="blocking",
        summary=(
            "A verification command passed after its earlier reported failure, "
            "and only verification files changed in between."
        ),
        evidence=(observation,) if observation else (),
        repair_instruction="",
        applies_to=files,
        keep_until="explicit_disposition_or_resolved",
        owner="kernel_mechanical_observation",
        observed_task_state_generation=generation,
        repair_condition=(
            "Either resolve with a non-verification workspace change and current "
            "evidence, or explicitly explain why the earlier check failure was "
            "not applicable to the task."
        ),
        lifecycle_origin="kernel_oracle_guard",
    )
    fact = {
        "schema": "aether.oracle_finish_hold_observation.v1",
        "edited_after_reported_failure": True,
        "verification_files_changed": list(files),
        "other_files_changed": [],
        "failed_receipt_ids": list(failed_ids),
        "source_receipt_ids": list(source_ids),
        "observation": observation,
        "task_state_generation": generation,
    }
    ledger.record(Receipt(
        receipt_id=f"step-{step}:completion_finding_witness:v1b:{key[:12]}",
        step=int(step),
        kind="completion_finding_witness",
        success=True,
        summary="mechanical verification-edit observation held for explicit completion disposition",
        payload={
            "finding_id": finding_id,
            "claim_status": "mechanical_observation_requires_disposition",
            "source": "mechanical_observation",
            "semantic_authority": "raw_user_task",
            "review_claim_summary": observation,
            "review_claim_observations": [observation] if observation else [],
            "supporting_factual_observations": [fact],
            "supporting_factual_observation_count": 1,
            "actual_observed_result_status": "current_factual_inspection_available",
            "observed_task_state_generation": generation,
            "supporting_observation_ids": list(source_ids),
            "coverage_status": "explicit_support_refs_present" if source_ids else "mechanical_observation",
            "supporting_observation_count": len(source_ids),
            "repair_strategy_included": False,
        },
    ))
    ledger.record(Receipt(
        receipt_id=f"step-{step}:{_HOLD_KIND}:{key[:12]}",
        step=int(step),
        kind=_HOLD_KIND,
        success=True,
        summary="first finish held once after verification-edit observation",
        payload={
            "incident_key": key,
            "finding_id": finding_id,
            "task_state_generation": generation,
            "source_receipt_ids": list(source_ids),
            "verification_files_changed": list(files),
            "hold_count": 1,
            "semantic_authority": "primary_solver_against_raw_task_and_observed_reality",
        },
    ))
    return finding_id


def current_v1b_finding_ids(packet: Mapping[str, Any]) -> tuple[str, ...]:
    raw = packet.get("open_completion_findings")
    if not isinstance(raw, list):
        return ()
    ids: list[str] = []
    for item in raw:
        if not isinstance(item, Mapping):
            continue
        finding_id = str(item.get("finding_id") or "").strip()
        if is_v1b_finding_id(finding_id) and finding_id not in ids:
            ids.append(finding_id)
    return tuple(ids)


def mark_v1b_obligations_current(packet: Mapping[str, Any]) -> dict[str, Any]:
    """Keep V1b's disposition obligation current across candidate mutations.

    The underlying observation remains bound to its historical generation; only
    the *obligation* stays current until Primary explicitly resolves/dispositions
    it.  This avoids treating an arbitrary write as a production repair.
    """
    out = dict(packet)
    raw = out.get("open_completion_findings")
    if not isinstance(raw, list):
        return out
    rows = []
    changed = False
    for item in raw:
        if not isinstance(item, Mapping):
            rows.append(item)
            continue
        row = dict(item)
        finding_id = str(row.get("finding_id") or "")
        if is_v1b_finding_id(finding_id):
            if row.get("currentness") == "historical_candidate":
                row["observation_currentness"] = "historical_candidate"
            row["currentness"] = "current_obligation"
            row["obligation"] = (
                "Before completion, either resolve this observation with a "
                "non-verification workspace change and current evidence, or "
                "explicitly disposition it with a specific explanation of why "
                "the earlier check failure was not applicable."
            )
            changed = True
        rows.append(row)
    if changed:
        out["open_completion_findings"] = rows
        out["oracle_finish_hold"] = {
            "mode": ORACLE_HOLD_ONCE_V1,
            "required_finding_ids": [
                str(item.get("finding_id"))
                for item in rows
                if isinstance(item, Mapping)
                and is_v1b_finding_id(item.get("finding_id"))
            ],
            "harness_role": "one_hold_mechanical_disposition_only",
            "semantic_authority": "primary_solver_against_raw_task_and_observed_reality",
        }
    return out


def _changed_paths(receipt: Any) -> set[str] | None:
    payload = getattr(receipt, "payload", {}) or {}
    delta = payload.get("state_delta") if isinstance(payload, Mapping) else None
    if isinstance(delta, Mapping):
        paths: set[str] = set()
        for key in ("created_paths", "modified_paths", "deleted_paths", "changed_paths"):
            values = delta.get(key)
            if isinstance(values, (list, tuple, set, frozenset)):
                paths.update(str(v).strip() for v in values if str(v).strip())
        status = str(delta.get("mutation_detection_status") or "").strip()
        if status in {"unavailable", "truncated", "coarse"} and not paths:
            return None
        if paths:
            return paths
    kind = str(getattr(receipt, "kind", "") or "")
    if kind == "write_file":
        path = str(payload.get("path") or "").strip()
        return {path} if path else None
    if getattr(receipt, "state_change", False):
        return None
    return set()


def _hold_receipt_for(ledger: Any, finding_id: str) -> Any | None:
    for receipt in reversed(tuple(ledger.all_receipts())):
        if getattr(receipt, "kind", "") != _HOLD_KIND:
            continue
        payload = getattr(receipt, "payload", {}) or {}
        if str(payload.get("finding_id") or "") == finding_id:
            return receipt
    return None


def has_nonverification_change_after_hold(ledger: Any, finding_id: str) -> bool:
    hold = _hold_receipt_for(ledger, finding_id)
    if hold is None:
        return False
    seen = False
    for receipt in ledger.all_receipts():
        if not seen:
            if getattr(receipt, "receipt_id", "") == getattr(hold, "receipt_id", ""):
                seen = True
            continue
        paths = _changed_paths(receipt)
        if paths is None:
            continue
        if any(path and not is_verification_path(path) for path in paths):
            return True
    return False


def validate_disposition(
    ledger: Any,
    *,
    turn: Any,
    finding_ids: tuple[str, ...],
) -> tuple[bool, str, tuple[dict[str, Any], ...]]:
    """Validate V1b's route-specific mechanical condition without consuming it."""
    by_id = {
        str(item.get("finding_id") or ""): dict(item)
        for item in (getattr(turn, "finding_dispositions", ()) or ())
        if isinstance(item, Mapping)
    }
    for finding_id in finding_ids:
        item = by_id.get(finding_id)
        if item is None:
            return False, "v1b_finding_not_dispositioned", ()
        disposition = str(item.get("disposition") or "").strip().lower()
        if disposition == "resolved" and not has_nonverification_change_after_hold(
            ledger, finding_id
        ):
            return False, "v1b_resolved_without_nonverification_change", ()
        if disposition not in {"resolved", "not_applicable", "override"}:
            return False, "v1b_unsupported_disposition", ()

    routes: list[dict[str, Any]] = []
    for finding_id in finding_ids:
        item = by_id[finding_id]
        disposition = str(item.get("disposition") or "").strip().lower()
        routes.append({
            "finding_id": finding_id,
            "disposition": disposition,
            "route": (
                "production_repair"
                if disposition == "resolved"
                else "check_defect_explanation"
            ),
            "explanation": str(item.get("explanation") or "").strip(),
        })
    return True, "v1b_disposition_validated", tuple(routes)


def record_validated_disposition(
    ledger: Any,
    *,
    finding_ids: tuple[str, ...],
    routes: tuple[Mapping[str, Any], ...],
    step: int,
) -> None:
    """Consume a validated V1b obligation only at an admitted finish boundary."""
    route_rows = [dict(item) for item in routes]
    if {str(item.get("finding_id") or "") for item in route_rows} != set(finding_ids):
        raise ValueError("validated V1b routes do not match active finding IDs")
    for finding_id in finding_ids:
        if finding_id not in ledger.findings.active:
            raise ValueError(f"V1b finding is no longer active: {finding_id}")
    for finding_id in finding_ids:
        ledger.findings.archive(finding_id, status="primary_dispositioned")
    ledger.record(Receipt(
        receipt_id=f"step-{step}:{_DISPOSITION_KIND}",
        step=int(step),
        kind=_DISPOSITION_KIND,
        success=True,
        summary="V1b oracle-edit observation explicitly dispositioned",
        payload={
            "routes": route_rows,
            "finding_ids": list(finding_ids),
            "semantic_authority": "primary_solver_against_raw_task_and_observed_reality",
            "harness_role": "mechanical_disposition_validation_only",
            "consumed_only_after_completion_gate_ready": True,
        },
    ))


def validate_and_record_disposition(
    ledger: Any,
    *,
    turn: Any,
    finding_ids: tuple[str, ...],
    step: int,
) -> tuple[bool, str]:
    """Compatibility helper: validate and immediately commit in direct callers."""
    allowed, reason, routes = validate_disposition(
        ledger, turn=turn, finding_ids=finding_ids,
    )
    if not allowed:
        return False, reason
    record_validated_disposition(
        ledger, finding_ids=finding_ids, routes=routes, step=step,
    )
    return True, "v1b_disposition_recorded"


__all__ = [
    "CONTROL",
    "ORACLE_HOLD_ONCE_V1",
    "SUPPORTED_MODES",
    "current_v1b_finding_ids",
    "finding_id_for",
    "has_nonverification_change_after_hold",
    "incident_key",
    "is_v1b_finding_id",
    "mark_v1b_obligations_current",
    "normalize_mode",
    "record_finish_hold",
    "should_hold_finish",
    "record_validated_disposition",
    "validate_and_record_disposition",
    "validate_disposition",
]
