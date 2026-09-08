"""Mechanical relevance rules for active Verifier findings.

The kernel does not judge task semantics.  It binds findings to model-authored
clause/target identifiers and permits progress only when a later concrete
receipt touches those identifiers, or when a generic evidence finding receives
a fresh current-state inspection.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from .pcr_evidence import is_pcr_completion_evidence


_RELEVANT_EVIDENCE_KINDS = frozenset({
    "read_file",
    "read_file_page",
    "read_output",
    "grep_output",
    "write_file",
    "run_command",
    "bootstrap_acquire",
    "process_launch",
    "process_stop",
    "service_probe",
    "inspect_artifact",
    "inspect_diff",
    "query_artifact_history",
    "check_result",
    "schema_validation",
    "inspection_record",
})

_GENERIC_TARGETS = frozenset({
    "completion_evidence",
    "current_state",
    "task_state",
    "deliverable",
    "result",
})


def _normalise_target(value: Any) -> str:
    text = str(value or "").strip().replace("\\", "/")
    for prefix in (
        "path:", "handle:", "target:", "check_id:", "service_name:",
        "process_id:", "clause:", "clause_id:",
    ):
        if text.startswith(prefix):
            text = text[len(prefix):]
            break
    if text.startswith("/app/"):
        text = text[5:]
    elif text == "/app":
        text = "."
    while text.startswith("./"):
        text = text[2:]
    # Preserve a leading slash outside the workspace: /etc/config and
    # workspace-relative etc/config are different artifacts.
    if text != "/":
        text = text.rstrip("/")
    return text.lower()


def _target_matches(left: str, right: str) -> bool:
    if not left or not right:
        return False
    # _normalise_target already removes the workspace-root /app prefix and
    # normalizes separators. Treat the remaining identity as exact. A basename
    # suffix match (out.txt == nested/out.txt) can unlock re-verification or
    # retire a finding using evidence from the wrong artifact.
    if left in _GENERIC_TARGETS or right in _GENERIC_TARGETS:
        return False
    return left == right


def finding_targets(finding: Any) -> set[str]:
    raw = finding.get("applies_to", ()) if isinstance(finding, Mapping) else getattr(finding, "applies_to", ())
    return {_normalise_target(item) for item in (raw or ()) if _normalise_target(item)}


def receipt_targets(receipt: Any) -> set[str]:
    payload = getattr(receipt, "payload", {})
    if not isinstance(payload, Mapping):
        payload = {}
    values: list[Any] = []
    for key in (
        "path", "handle", "target", "check_id", "service_name", "process_id",
        "clause_id", "target_identity",
    ):
        value = payload.get(key)
        if value not in (None, ""):
            values.append(value)
    for key in (
        "artifact_paths", "modified_paths", "created_paths", "removed_paths",
        "inspection_ids", "clause_ids",
    ):
        raw = payload.get(key, ())
        if isinstance(raw, (list, tuple, set)):
            values.extend(raw)
    command = str(payload.get("command", "")).strip()
    if command:
        values.append(command)
    return {_normalise_target(item) for item in values if _normalise_target(item)}


def receipt_is_relevant(receipt: Any, finding: Any) -> bool:
    if getattr(receipt, "kind", "") not in _RELEVANT_EVIDENCE_KINDS:
        return False
    payload = getattr(receipt, "payload", {})
    if not isinstance(payload, Mapping):
        payload = {}
    if getattr(receipt, "kind", "") == "inspection_record":
        valid = bool(payload.get("observation_valid", getattr(receipt, "success", False)))
    else:
        valid = bool(getattr(receipt, "success", False))
    if not valid:
        return False
    targets = finding_targets(finding)
    observed = receipt_targets(receipt)
    if targets & _GENERIC_TARGETS:
        # Generic evidence gaps require a concrete current-state observation or
        # mutation, never memory/prose/control-plane activity.
        return bool(observed) or getattr(receipt, "kind", "") in {
            "inspection_record", "check_result", "schema_validation",
        }
    if not targets:
        return bool(observed)
    return any(_target_matches(left, right) for left in targets for right in observed)


def _latest_verifier_index(receipts: Sequence[Any]) -> int:
    last_verifier = -1
    for index, receipt in enumerate(receipts):
        if getattr(receipt, "kind", "") == "model_verifier_result":
            last_verifier = index
    return last_verifier


def evidence_after_latest_verifier(
    ledger: Any,
    finding: Any,
    *,
    nominated_evidence_receipts: Sequence[Any] = (),
) -> tuple[Any, ...]:
    """Return current evidence that can reopen a Verifier round.

    Ordinary receipts must mechanically touch a finding target. A validated
    PCR submission may additionally nominate its own current evidence bundle;
    those receipt IDs are allowed to reopen the Verifier without the Kernel
    deciding that they resolve any finding. The nomination is only accepted
    for a real successful completion-evidence receipt after the latest
    Verifier result, so stale, unknown, failed, and control-plane receipts
    cannot unlock re-entry.
    """
    receipts = tuple(ledger.all_receipts())
    last_verifier = _latest_verifier_index(receipts)
    post_verifier = receipts[last_verifier + 1:]
    relevant = [
        receipt for receipt in post_verifier
        if receipt_is_relevant(receipt, finding)
    ]
    nominated_ids = {
        str(getattr(item, "receipt_id", item)).strip()
        for item in nominated_evidence_receipts
        if str(getattr(item, "receipt_id", item)).strip()
    }
    if not nominated_ids:
        return tuple(relevant)
    already_relevant = {str(getattr(receipt, "receipt_id", "")) for receipt in relevant}
    for receipt in post_verifier:
        receipt_id = str(getattr(receipt, "receipt_id", ""))
        if (
            receipt_id in nominated_ids
            and receipt_id not in already_relevant
            and bool(getattr(receipt, "success", False))
            and is_pcr_completion_evidence(receipt)
        ):
            relevant.append(receipt)
            already_relevant.add(receipt_id)
    return tuple(relevant)


def active_findings_need_relevant_evidence(
    ledger: Any,
    *,
    nominated_evidence_receipts: Sequence[Any] = (),
) -> bool:
    active = ledger.active_finding_context(len(ledger.all_receipts()), limit=1000)
    return any(
        not evidence_after_latest_verifier(
            ledger,
            finding,
            nominated_evidence_receipts=nominated_evidence_receipts,
        )
        for finding in active
    )


def _current_registered_inspections(
    ledger: Any,
    inspection_ids: Iterable[str],
    *,
    packet_signature: str = "",
    after_receipt_index: int = -1,
) -> tuple[Any, ...]:
    from .inspection_registry import inspection_superseded_by_later_observation

    current_generation = int(ledger.task_state_generation())
    wanted = {str(item).strip() for item in inspection_ids if str(item).strip()}
    rows: list[Any] = []
    for receipt_index, receipt in enumerate(ledger.all_receipts()):
        if receipt_index <= int(after_receipt_index):
            continue
        if getattr(receipt, "kind", "") != "inspection_record":
            continue
        payload = getattr(receipt, "payload", {})
        inspection_id = str(payload.get("inspection_id", getattr(receipt, "receipt_id", ""))).strip()
        if inspection_id not in wanted or not bool(getattr(receipt, "success", False)):
            continue
        if not bool(payload.get("eligible_for_proof", False)):
            continue
        if inspection_superseded_by_later_observation(ledger, receipt):
            continue
        if packet_signature and str(payload.get("packet_signature", "")) != packet_signature:
            continue
        try:
            generation = int(payload.get("task_state_generation"))
        except (TypeError, ValueError):
            continue
        if generation == current_generation:
            rows.append(receipt)
    return tuple(rows)


def resolved_finding_ids_for_completed(
    ledger: Any,
    result: Any,
    *,
    packet_signature: str = "",
) -> set[str]:
    """Findings directly covered by current, same-round registered evidence."""
    entries = tuple(getattr(result, "completion_evidence", ()) or ())
    active = tuple(getattr(ledger.findings, "active", {}).values())
    # Evidence created before the latest Verifier result cannot retire a finding
    # that survived or was activated by that result, even if task generation is
    # unchanged. This binds finding resolution to a fresh Verifier evidence round.
    last_verifier_receipt_index = -1
    for index, receipt in enumerate(ledger.all_receipts()):
        if getattr(receipt, "kind", "") == "model_verifier_result":
            last_verifier_receipt_index = index
    resolved: set[str] = set()
    for finding in active:
        targets = finding_targets(finding)
        observed_generation = int(getattr(finding, "observed_task_state_generation", -1))
        for entry in entries:
            inspection_ids = tuple(getattr(entry, "inspection_refs", ()) or ())
            inspections = _current_registered_inspections(
                ledger,
                inspection_ids,
                packet_signature=packet_signature,
                after_receipt_index=last_verifier_receipt_index,
            )
            if not inspections:
                continue
            clause_ids = {
                _normalise_target(item)
                for item in (getattr(entry, "clause_ids", ()) or ())
                if _normalise_target(item)
            }
            if targets & clause_ids:
                resolved.add(finding.finding_id)
                break
            if targets & _GENERIC_TARGETS or not targets:
                if any(
                    int(item.payload.get("task_state_generation", -1)) >= observed_generation
                    for item in inspections
                ):
                    resolved.add(finding.finding_id)
                    break
            if any(
                receipt_is_relevant(item, finding)
                and int(item.payload.get("task_state_generation", -1)) >= observed_generation
                for item in inspections
            ):
                resolved.add(finding.finding_id)
                break
    return resolved
