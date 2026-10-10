"""Frontier-owned completion-record protocol v1.

This module is deliberately structural. Frontier owns task interpretation,
requirements, assessments, uncertainty, revision reasons, and the decision to
submit. The runtime only validates the bounded record protocol, preserves
immutable revisions as receipts, and projects factual reference freshness.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import re
from typing import Any, Mapping

from .ledger import ExecutionLedger, Receipt
from .persistent_context import evidence_alias

COMPLETION_RECORD_OFF = "off"
COMPLETION_RECORD_V1 = "v1"
SUPPORTED_COMPLETION_RECORD_MODES = frozenset({COMPLETION_RECORD_OFF, COMPLETION_RECORD_V1})
MAX_RECORD_BYTES = 12_288
MAX_CONDITIONS = 24
_RECORD_KIND = "completion_record_revision"
_NONADHERENCE_KIND = "completion_record_initial_nonadherence"
_FINISH_METADATA_KIND = "completion_record_finish_metadata"
_FINISH_NONADHERENCE_KIND = "completion_record_finish_nonadherence"
_ASSESSMENTS = frozenset({"open", "supported", "contradicted", "retired"})
_KINDS = frozenset({"explicit", "derived"})
_SHA256_RE = re.compile(r"^(?:sha256:)?([0-9a-fA-F]{64})$")

TREATMENT_INSTRUCTION = (
    "Maintain one compact Frontier-authored task-level completion record. After reading "
    "the task, create revision 1 before substantive implementation when practical; "
    "read-only exploration may come first. Revise the whole record when an assumption, "
    "meaningful validation result, or contradiction materially changes. The runtime "
    "stores and re-presents your record but does not judge whether any condition is "
    "semantically correct or sufficient. Open or contradicted conditions are visible "
    "but are not a runtime veto. Before finishing, review the current revision and "
    "supply finish_metadata with reviewed_revision, remaining_uncertainties, and a "
    "brief completion_basis."
)


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def canonical_task_hash(task_text: str) -> str:
    return "sha256:" + sha256(str(task_text).encode("utf-8")).hexdigest()


def _normalize_hash(value: Any) -> str:
    match = _SHA256_RE.fullmatch(str(value or "").strip())
    return match.group(1).lower() if match else ""


def _receipt_map(ledger: ExecutionLedger) -> dict[str, Receipt]:
    return {receipt.receipt_id: receipt for receipt in ledger.all_receipts()}


def latest_completion_record_receipt(ledger: ExecutionLedger) -> Receipt | None:
    return ledger.latest_receipt(_RECORD_KIND)


def latest_completion_record(ledger: ExecutionLedger) -> dict[str, Any] | None:
    receipt = latest_completion_record_receipt(ledger)
    if receipt is None:
        return None
    record = (receipt.payload or {}).get("record")
    return deepcopy(dict(record)) if isinstance(record, Mapping) else None


def current_revision(ledger: ExecutionLedger) -> int:
    record = latest_completion_record(ledger)
    if not record:
        return 0
    try:
        return int(record.get("revision", 0) or 0)
    except (TypeError, ValueError):
        return 0


# Frontier's ``artifact_hash`` evidence references must resolve to task-artifact
# content digests, never to Aether receipt/projection bookkeeping.  Only keys
# that carry content observed from the task world are artifact hashes;
# record_sha256, evidence_set_sha256, snapshot digests, exact-access envelope
# hashes, screenshot/transport/tool-schema digests, and task hashes are
# explicitly out of domain.
_ARTIFACT_HASH_KEYS = frozenset({
    "content_sha256",
    "artifact_sha256",
    "after_content_hash",
    "content_hash",
    "output_sha256",
    "file_sha256",
})
# A bare ``sha256`` value is accepted only inside these artifact-scoped
# containers (for example the ``metadata`` / ``artifact_identity`` of an
# artifact_inspection receipt, where it is the executor's content-addressed
# artifact digest).
_ARTIFACT_SHA256_CONTAINER_KEYS = frozenset({"metadata", "artifact_identity"})


def _all_artifact_hashes(value: Any, *, key_hint: str = "", artifact_container: bool = False) -> set[str]:
    """Collect only task-artifact content hashes, never receipt/projection hashes."""
    found: set[str] = set()
    if isinstance(value, Mapping):
        for key, item in value.items():
            if artifact_container and key == "sha256":
                normalized = _normalize_hash(item)
                if normalized:
                    found.add(normalized)
                continue
            if key in _ARTIFACT_HASH_KEYS:
                normalized = _normalize_hash(item)
                if normalized:
                    found.add(normalized)
            if isinstance(item, Mapping):
                scoped = artifact_container or key in _ARTIFACT_SHA256_CONTAINER_KEYS
                found.update(
                    _all_artifact_hashes(item, key_hint=str(key), artifact_container=scoped)
                )
    elif isinstance(value, (list, tuple, set, frozenset)):
        for item in value:
            found.update(
                _all_artifact_hashes(item, key_hint=key_hint, artifact_container=artifact_container)
            )
    return found


def _require_string(value: Any, field: str, *, nonempty: bool = False) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    if nonempty and not value.strip():
        raise ValueError(f"{field} must be non-empty")
    return value


def _validate_source_ref(ref: Any, *, task_hash: str, task_bytes: bytes, location: str) -> None:
    if not isinstance(ref, Mapping):
        raise ValueError(f"{location} must be an object")
    if set(ref) != {"task_hash", "start_byte", "end_byte"}:
        raise ValueError(f"{location} must contain exactly task_hash,start_byte,end_byte")
    if str(ref.get("task_hash") or "") != task_hash:
        raise ValueError(f"{location}.task_hash does not match this run's raw task")
    start = ref.get("start_byte")
    end = ref.get("end_byte")
    if isinstance(start, bool) or not isinstance(start, int):
        raise ValueError(f"{location}.start_byte must be an integer")
    if isinstance(end, bool) or not isinstance(end, int):
        raise ValueError(f"{location}.end_byte must be an integer")
    if start < 0 or end <= start or end > len(task_bytes):
        raise ValueError(
            f"{location} byte range [{start},{end}) is outside raw task bytes 0:{len(task_bytes)}"
        )


def _validate_evidence_ref(
    ref: Any,
    *,
    receipts: Mapping[str, Receipt],
    location: str,
) -> None:
    if not isinstance(ref, Mapping):
        raise ValueError(f"{location} must be an object")
    if set(ref) != {"receipt_id", "artifact_hash"}:
        raise ValueError(f"{location} must contain exactly receipt_id,artifact_hash")
    receipt_id = _require_string(ref.get("receipt_id"), f"{location}.receipt_id", nonempty=True)
    artifact_hash = _normalize_hash(ref.get("artifact_hash"))
    if not artifact_hash:
        raise ValueError(f"{location}.artifact_hash must be a sha256 digest")
    receipt = receipts.get(receipt_id)
    if receipt is None:
        raise ValueError(f"{location}.receipt_id does not resolve to an admitted receipt")
    observed_hashes = _all_artifact_hashes(receipt.payload or {})
    if artifact_hash not in observed_hashes:
        raise ValueError(
            f"{location}.artifact_hash does not resolve to an artifact-content hash "
            f"observed by receipt {receipt_id}; a receipt/projection hash is not an "
            "artifact hash"
        )


def validate_replacement_record(
    replacement_record: Any,
    *,
    expected_revision: int,
    task_text: str,
    ledger: ExecutionLedger,
) -> tuple[dict[str, Any], bytes]:
    if not isinstance(replacement_record, Mapping):
        raise ValueError("replacement_record must be an object")
    record = deepcopy(dict(replacement_record))
    allowed_top = {"schema_version", "revision", "task_hash", "conditions", "revision_reason"}
    if set(record) != allowed_top:
        raise ValueError(
            "replacement_record must contain exactly schema_version,revision,task_hash,conditions,revision_reason"
        )
    if record.get("schema_version") != 1:
        raise ValueError("schema_version must equal 1")
    if isinstance(expected_revision, bool) or not isinstance(expected_revision, int) or expected_revision < 0:
        raise ValueError("expected_revision must be a non-negative integer")
    observed_revision = current_revision(ledger)
    if expected_revision != observed_revision:
        raise ValueError(
            f"stale expected_revision: expected={expected_revision} observed={observed_revision}"
        )
    revision = record.get("revision")
    if isinstance(revision, bool) or not isinstance(revision, int) or revision != expected_revision + 1:
        raise ValueError(
            f"revision must equal expected_revision + 1 ({expected_revision + 1})"
        )
    task_bytes = str(task_text).encode("utf-8")
    task_hash = canonical_task_hash(task_text)
    if record.get("task_hash") != task_hash:
        raise ValueError("task_hash does not match the immutable raw task bytes")
    _require_string(record.get("revision_reason"), "revision_reason", nonempty=True)
    conditions = record.get("conditions")
    if not isinstance(conditions, list):
        raise ValueError("conditions must be an array")
    if len(conditions) > MAX_CONDITIONS:
        raise ValueError(
            f"condition limit exceeded: count={len(conditions)} limit={MAX_CONDITIONS}"
        )
    receipt_map = _receipt_map(ledger)
    ids: list[str] = []
    for index, condition in enumerate(conditions):
        location = f"conditions[{index}]"
        if not isinstance(condition, Mapping):
            raise ValueError(f"{location} must be an object")
        allowed = {
            "id", "outcome", "source_refs", "kind", "proof_needed",
            "evidence_refs", "assessment", "uncertainty", "retirement_reason",
        }
        # The provider's recursively strict object requires this field in
        # every condition. Non-retired conditions carry null; retired rows
        # must carry a Frontier-authored non-empty reason below.
        required = set(allowed)
        unknown = set(condition) - allowed
        missing = required - set(condition)
        if unknown or missing:
            raise ValueError(
                f"{location} fields invalid: missing={sorted(missing)} unknown={sorted(unknown)}"
            )
        condition_id = _require_string(condition.get("id"), f"{location}.id", nonempty=True)
        ids.append(condition_id)
        _require_string(condition.get("outcome"), f"{location}.outcome", nonempty=True)
        _require_string(condition.get("proof_needed"), f"{location}.proof_needed", nonempty=True)
        _require_string(condition.get("uncertainty"), f"{location}.uncertainty")
        if condition.get("kind") not in _KINDS:
            raise ValueError(f"{location}.kind must be explicit or derived")
        if condition.get("assessment") not in _ASSESSMENTS:
            raise ValueError(
                f"{location}.assessment must be open,supported,contradicted,or retired"
            )
        retirement_reason = condition.get("retirement_reason")
        if condition.get("assessment") == "retired":
            _require_string(
                retirement_reason,
                f"{location}.retirement_reason",
                nonempty=True,
            )
        elif retirement_reason is not None:
            _require_string(
                retirement_reason,
                f"{location}.retirement_reason",
                nonempty=True,
            )
        source_refs = condition.get("source_refs")
        if not isinstance(source_refs, list) or not source_refs:
            raise ValueError(f"{location}.source_refs must be a non-empty array")
        for ref_index, ref in enumerate(source_refs):
            _validate_source_ref(
                ref,
                task_hash=task_hash,
                task_bytes=task_bytes,
                location=f"{location}.source_refs[{ref_index}]",
            )
        evidence_refs = condition.get("evidence_refs")
        if not isinstance(evidence_refs, list):
            raise ValueError(f"{location}.evidence_refs must be an array")
        for ref_index, ref in enumerate(evidence_refs):
            _validate_evidence_ref(
                ref,
                receipts=receipt_map,
                location=f"{location}.evidence_refs[{ref_index}]",
            )
    if len(ids) != len(set(ids)):
        raise ValueError("condition ids must be unique")
    previous = latest_completion_record(ledger)
    if previous:
        previous_ids = {
            str(item.get("id") or "")
            for item in (previous.get("conditions") or [])
            if isinstance(item, Mapping)
        }
        missing_ids = sorted(previous_ids - set(ids))
        if missing_ids:
            raise ValueError(
                "prior condition ids may not disappear; retire them with a reason: "
                + ",".join(missing_ids)
            )
    encoded = _canonical_bytes(record)
    if len(encoded) > MAX_RECORD_BYTES:
        raise ValueError(
            f"record byte limit exceeded: bytes={len(encoded)} limit={MAX_RECORD_BYTES}"
        )
    return record, encoded


def update_completion_record_receipt(
    *,
    ledger: ExecutionLedger,
    expected_revision: Any,
    replacement_record: Any,
    task_text: str,
    step: int,
    action_id: str,
) -> Receipt:
    try:
        record, encoded = validate_replacement_record(
            replacement_record,
            expected_revision=expected_revision,
            task_text=task_text,
            ledger=ledger,
        )
    except (TypeError, ValueError) as exc:
        return Receipt(
            receipt_id=f"step-{step}:{action_id}:completion_record_rejected",
            step=step,
            kind="completion_record_update",
            success=False,
            summary=f"completion record update rejected: {exc}",
            failure_class="completion_record_validation",
            payload={
                "reason_code": "completion_record_validation",
                "detail": str(exc),
                "observed_revision": current_revision(ledger),
                "max_record_bytes": MAX_RECORD_BYTES,
                "max_conditions": MAX_CONDITIONS,
                "semantic_authority": "frontier",
                "prior_record_unchanged": True,
            },
        )
    revision = int(record["revision"])
    return Receipt(
        receipt_id=f"step-{step}:{action_id}:completion_record_revision:{revision}",
        step=step,
        kind=_RECORD_KIND,
        success=True,
        summary=f"accepted Frontier-authored completion record revision {revision}",
        state_change=False,
        payload={
            "revision": revision,
            "record_sha256": sha256(encoded).hexdigest(),
            "record_bytes": len(encoded),
            "condition_count": len(record.get("conditions") or []),
            "record": record,
            "semantic_authority": "frontier",
            "runtime_semantic_judgment": False,
        },
    )


def ensure_initial_nonadherence_receipt(
    ledger: ExecutionLedger,
    *,
    step: int,
    mode: str,
) -> None:
    if mode != COMPLETION_RECORD_V1 or step <= 0 or current_revision(ledger) > 0:
        return
    if ledger.latest_receipt(_NONADHERENCE_KIND) is not None:
        return
    ledger.record(Receipt(
        receipt_id=f"step-{step}:completion_record_initial_nonadherence",
        step=step,
        kind=_NONADHERENCE_KIND,
        success=True,
        summary="treatment record is still absent after the initial Solver turn",
        payload={
            "treatment_adherent": False,
            "submission_blocked": False,
            "semantic_authority": "frontier",
            "factual_reminder_ordinal": 1,
        },
    ))


def _receipt_paths(receipt: Receipt) -> set[str]:
    payload = receipt.payload if isinstance(receipt.payload, Mapping) else {}
    paths: set[str] = set()
    for key in (
        "path", "observed_path", "source_path", "output_path",
        "modified_paths", "artifact_paths", "removed_paths",
    ):
        value = payload.get(key)
        values = (value,) if isinstance(value, str) else value
        if isinstance(values, (list, tuple, set, frozenset)):
            paths.update(str(item).strip() for item in values if str(item).strip())
    delta = payload.get("state_delta")
    if isinstance(delta, Mapping):
        for key in (
            "created_paths", "content_changed_paths", "metadata_changed_paths",
            "modified_paths", "artifact_paths", "removed_paths",
        ):
            value = delta.get(key)
            values = (value,) if isinstance(value, str) else value
            if isinstance(values, (list, tuple, set, frozenset)):
                paths.update(str(item).strip() for item in values if str(item).strip())
    return paths


def _freshness_for_receipt(ledger: ExecutionLedger, receipt: Receipt) -> str:
    current_generation = ledger.task_state_generation()
    current_check = getattr(ledger, "receipt_snapshot_binding_is_current", None)
    if callable(current_check):
        try:
            if bool(current_check(receipt, expected_generation=current_generation)):
                return "observed"
        except Exception:
            pass

    receipts = list(ledger.all_receipts())
    try:
        source_index = next(i for i, row in enumerate(receipts) if row is receipt or row.receipt_id == receipt.receipt_id)
    except StopIteration:
        source_index = -1
    target_paths = _receipt_paths(receipt)
    uncertain_boundary = False
    for later in receipts[source_index + 1:]:
        later_paths = _receipt_paths(later)
        if target_paths and later.state_change and target_paths.intersection(later_paths):
            return "superseded"
        uncertain = getattr(ledger, "is_uncertain_task_state_boundary", None)
        if callable(uncertain):
            try:
                uncertain_boundary = uncertain_boundary or bool(uncertain(later))
            except Exception:
                pass
    if uncertain_boundary:
        return "unknown_since_mutation"

    payload = receipt.payload if isinstance(receipt.payload, Mapping) else {}
    try:
        observed_generation = int(
            payload.get("task_state_generation",
                        payload.get("observed_task_state_generation", current_generation))
        )
    except (TypeError, ValueError):
        observed_generation = current_generation
    if observed_generation == current_generation:
        return "observed"
    return "unknown_since_mutation"


def project_completion_record_context(
    ledger: ExecutionLedger,
    *,
    mode: str,
    task_text: str,
) -> dict[str, Any] | None:
    record = latest_completion_record(ledger)
    if mode == COMPLETION_RECORD_OFF and record is None:
        return None
    task_hash = canonical_task_hash(task_text)
    projection: dict[str, Any] = {
        "schema": "aether.completion_record_projection.v1",
        "mode": mode,
        "task_hash": task_hash,
        "current_revision": current_revision(ledger),
        "active_record": record,
        "semantic_authority": "frontier",
        "runtime_semantic_judgment": False,
    }
    if mode == COMPLETION_RECORD_V1:
        projection["treatment_instruction"] = TREATMENT_INSTRUCTION
        projection["initial_nonadherence_recorded"] = (
            ledger.latest_receipt(_NONADHERENCE_KIND) is not None
        )
    if record:
        receipts = _receipt_map(ledger)
        freshness: list[dict[str, Any]] = []
        for condition in record.get("conditions") or []:
            if not isinstance(condition, Mapping):
                continue
            condition_id = str(condition.get("id") or "")
            for evidence_ref in condition.get("evidence_refs") or []:
                if not isinstance(evidence_ref, Mapping):
                    continue
                receipt_id = str(evidence_ref.get("receipt_id") or "")
                receipt = receipts.get(receipt_id)
                if receipt is None:
                    continue
                payload = receipt.payload if isinstance(receipt.payload, Mapping) else {}
                observed_generation = payload.get(
                    "observed_task_state_generation",
                    payload.get("task_state_generation"),
                )
                freshness.append({
                    "condition_id": condition_id,
                    "receipt_id": receipt_id,
                    "source_receipt_id": receipt_id,
                    "observation_id": receipt_id,
                    "evidence_ref": evidence_alias(receipt_id),
                    "artifact_hash": evidence_ref.get("artifact_hash"),
                    "freshness": _freshness_for_receipt(ledger, receipt),
                    "run_id": str((ledger.runtime_identity or {}).get("run_id") or ""),
                    "observed_at": payload.get("observed_at", payload.get("at_unix_s")),
                    "workspace_generation": observed_generation,
                    "current_task_state_generation": ledger.task_state_generation(),
                })
        projection["evidence_freshness"] = freshness
    return projection


def record_finish_metadata(
    ledger: ExecutionLedger,
    *,
    finish_metadata: Mapping[str, Any] | None,
    mode: str,
    step: int,
) -> None:
    if not finish_metadata:
        if mode == COMPLETION_RECORD_V1 and ledger.latest_receipt(_FINISH_NONADHERENCE_KIND) is None:
            ledger.record(Receipt(
                receipt_id=f"step-{step}:completion_record_finish_nonadherence",
                step=step,
                kind=_FINISH_NONADHERENCE_KIND,
                success=True,
                summary="treatment finish omitted completion-record review metadata",
                payload={
                    "treatment_adherent": False,
                    "submission_blocked": False,
                    "semantic_authority": "frontier",
                },
            ))
        return
    metadata = dict(finish_metadata)
    reviewed = metadata.get("reviewed_revision")
    current = current_revision(ledger)
    known_revisions = {
        int((receipt.payload or {}).get("revision", 0) or 0)
        for receipt in ledger.all_receipts()
        if receipt.kind == _RECORD_KIND
    }
    known = isinstance(reviewed, int) and not isinstance(reviewed, bool) and reviewed in known_revisions
    ledger.record(Receipt(
        receipt_id=f"step-{step}:completion_record_finish_metadata:{len([r for r in ledger.all_receipts() if r.kind == _FINISH_METADATA_KIND]) + 1}",
        step=step,
        kind=_FINISH_METADATA_KIND,
        success=True,
        summary="captured Frontier-authored completion-record finish metadata",
        payload={
            "finish_metadata": metadata,
            "reviewed_revision": reviewed,
            "current_revision": current,
            "reviewed_revision_known": known,
            "review_mismatch": reviewed != current,
            "submission_blocked": False,
            "semantic_authority": "frontier",
        },
    ))


__all__ = [
    "COMPLETION_RECORD_OFF",
    "COMPLETION_RECORD_V1",
    "SUPPORTED_COMPLETION_RECORD_MODES",
    "MAX_RECORD_BYTES",
    "MAX_CONDITIONS",
    "TREATMENT_INSTRUCTION",
    "canonical_task_hash",
    "current_revision",
    "ensure_initial_nonadherence_receipt",
    "latest_completion_record",
    "project_completion_record_context",
    "record_finish_metadata",
    "update_completion_record_receipt",
    "validate_replacement_record",
]
