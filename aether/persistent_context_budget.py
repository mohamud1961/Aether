"""Hard final-packet budgeting and preferred hot context for PERSISTENT V0.

The generic context compiler may compress its own intermediate packet, but PERSISTENT
adds raw task authority, evidence aliases, exact handles afterwards. This module measures the actual final PERSISTENT packet, derives a
smaller provenance-preserving hot view when that is strictly cheaper, and treats
the local working-context budget as an advisory compaction threshold. The
provider/model context authority, not a harness estimate, decides whether a
model call is admissible.

The preferred hot view never externalizes the immediately previous Primary
Agent result: one action -> one real observation -> next decision remains the
normal PERSISTENT causal boundary. Historical duplicate views can be externalized
only when a remaining exact retrieval action is available.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping

from .runtime_ir import stable_json


_EXTERNALIZABLE_LINKED_SECTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("command_results", ("query_history", "read_output")),
    ("latest_file_reads", ("query_history", "read_file_page")),
    ("artifact_history", ("query_history", "query_artifact_history")),
    ("output_handles", ("query_history", "read_output")),
)

_MINIMAL_LINKED_KEYS = frozenset({
    "open_obligations",
    "obligation_status",
    "monitor_alerts",
    "live_processes",
    "artifacts_present",
    "installed_capabilities",
    "planned_checks",
    "pending_checks",
    "persistent_context_boundary",
    "externalized_sections",
})

_PREFERRED_HOT_EVIDENCE_LIMIT = 12


def _item_count(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, Mapping):
        return len(value)
    if isinstance(value, (list, tuple, set, frozenset)):
        return len(value)
    return 1


def _measure(value: Mapping[str, Any]) -> tuple[int, int]:
    byte_count = len(stable_json(value).encode("utf-8"))
    return byte_count, max(1, (byte_count + 3) // 4)


def _section_record(
    selector: str,
    value: Any,
    retrieval_actions: tuple[str, ...],
    *,
    stage: str,
) -> dict[str, Any]:
    return {
        "selector": selector,
        "item_count": _item_count(value),
        "sha256": sha256(stable_json(value).encode("utf-8")).hexdigest(),
        "retrieval_actions": list(retrieval_actions),
        "stage": stage,
        "authority": "externalized_from_same_canonical_ledger",
    }


def _with_budget_metadata(
    body: Mapping[str, Any],
    *,
    budget_tokens: int,
    stages: list[str],
    externalized: list[dict[str, Any]],
    within_budget: bool,
    failure_reason: str = "",
    original_bytes: int,
    original_tokens: int,
) -> dict[str, Any]:
    packet = dict(body)
    packet.pop("context_budget", None)
    content_hash = sha256(stable_json(packet).encode("utf-8")).hexdigest()
    metadata: dict[str, Any] = {
        "schema_version": "persistent_context_budget.v1",
        "hard_limit_enforced": False,
        "provider_context_authority": True,
        "within_budget": within_budget,
        "budget_tokens_v1": budget_tokens,
        "budget_bytes_v1": budget_tokens * 4,
        "original_bytes_v1": original_bytes,
        "original_token_estimate_v1": original_tokens,
        "compression_stages": list(stages),
        "externalized_sections": list(externalized),
        "content_sha256_without_budget_metadata": content_hash,
        "token_estimator": "ceil(utf8_bytes/4)",
    }
    if "preferred_hot_context" in stages:
        metadata["preferred_hot_context"] = {
            "applied": True,
            "admission_rule": "strictly_smaller_than_full_canonical_packet",
            "latest_primary_result_inline_preserved": True,
            "historical_evidence_limit": _PREFERRED_HOT_EVIDENCE_LIMIT,
            "semantic_summarization_used": False,
        }
    if failure_reason:
        metadata["failure_reason"] = failure_reason
    packet["context_budget"] = metadata
    # Metadata contains the final measurement, so converge after updating the
    # digit widths rather than reporting the pre-metadata body size.
    for _ in range(4):
        final_bytes, final_tokens = _measure(packet)
        metadata["final_bytes_v1"] = final_bytes
        metadata["final_token_estimate_v1"] = final_tokens
        packet["context_budget"] = dict(metadata)
    return packet


def _fits(
    body: Mapping[str, Any],
    *,
    budget_tokens: int,
    stages: list[str],
    externalized: list[dict[str, Any]],
    original_bytes: int,
    original_tokens: int,
) -> tuple[bool, dict[str, Any]]:
    packet = _with_budget_metadata(
        body,
        budget_tokens=budget_tokens,
        stages=stages,
        externalized=externalized,
        within_budget=True,
        original_bytes=original_bytes,
        original_tokens=original_tokens,
    )
    return (
        int(packet["context_budget"]["final_token_estimate_v1"])
        <= budget_tokens,
        packet,
    )


def _externalize_linked_sections(
    packet: dict[str, Any],
    externalized: list[dict[str, Any]],
) -> None:
    linked = packet.get("linked_history")
    if not isinstance(linked, Mapping):
        return
    reduced = dict(linked)
    for selector, actions in _EXTERNALIZABLE_LINKED_SECTIONS:
        if selector not in reduced:
            continue
        value = reduced.pop(selector)
        externalized.append(_section_record(
            selector, value, actions, stage="linked_history_externalization",
        ))
    reduced["externalized_sections"] = list(externalized)
    packet["linked_history"] = reduced


def _semantic_advice_evidence_pins(
    packet: Mapping[str, Any],
) -> tuple[set[str], set[str]]:
    """Return exact evidence identities explicitly referenced by current advice.

    A semantic relation without the bounded observation it refers to is not a
    self-grounding model-facing fact. Keep only explicitly referenced evidence
    bodies hot; all ordinary historical evidence remains eligible for
    externalization and exact on-demand retrieval.
    """
    pinned_refs: set[str] = set()
    pinned_receipt_ids: set[str] = set()
    advice = packet.get("semantic_advice")
    if not isinstance(advice, Mapping):
        return pinned_refs, pinned_receipt_ids

    for item in advice.get("items", ()) or ():
        if not isinstance(item, Mapping):
            continue
        evidence_ref = str(item.get("evidence_ref", "") or "").strip()
        receipt_id = str(item.get("receipt_id", "") or "").strip()
        if evidence_ref:
            pinned_refs.add(evidence_ref)
        if receipt_id:
            pinned_receipt_ids.add(receipt_id)

    graph = advice.get("graph")
    if isinstance(graph, Mapping):
        # EvidenceGraph.compact_summary() emits subjects. Accept the
        # historical items spelling as well so retained packets stay replayable.
        subjects = graph.get("subjects")
        if not isinstance(subjects, (list, tuple)):
            subjects = graph.get("items", ()) or ()
        for subject in subjects:
            if not isinstance(subject, Mapping):
                continue
            for key in ("relations", "provenance"):
                for edge in subject.get(key, ()) or ():
                    if not isinstance(edge, Mapping):
                        continue
                    receipt_id = str(edge.get("receipt_id", "") or "").strip()
                    if receipt_id:
                        pinned_receipt_ids.add(receipt_id)
    return pinned_refs, pinned_receipt_ids


def _compact_evidence_views(packet: dict[str, Any]) -> None:
    rows = packet.get("evidence_index")
    if not isinstance(rows, list):
        return
    pinned_refs, pinned_receipt_ids = _semantic_advice_evidence_pins(packet)

    # The immediately previous observation already remains inline in
    # latest_primary_result. If semantic advice cites that same receipt, do
    # not retain a second bounded body in evidence_index.
    latest_refs: set[str] = set()
    latest_receipt_ids: set[str] = set()
    latest = packet.get("latest_primary_result")
    if isinstance(latest, Mapping):
        for row in latest.get("outcome_receipts", ()) or ():
            if not isinstance(row, Mapping):
                continue
            evidence_ref = str(row.get("evidence_ref", "") or "").strip()
            receipt_id = str(row.get("receipt_id", "") or "").strip()
            if evidence_ref:
                latest_refs.add(evidence_ref)
            if receipt_id:
                latest_receipt_ids.add(receipt_id)

    compacted: list[Any] = []
    for row in rows:
        if not isinstance(row, Mapping):
            compacted.append(row)
            continue
        item = dict(row)
        evidence_ref = str(item.get("evidence_ref", "") or "")
        receipt_id = str(item.get("receipt_id", "") or "")
        is_semantically_pinned = (
            evidence_ref in pinned_refs or receipt_id in pinned_receipt_ids
        )
        already_hot_as_latest = (
            evidence_ref in latest_refs or receipt_id in latest_receipt_ids
        )
        keep_bounded_view = is_semantically_pinned and not already_hot_as_latest
        if "bounded_view" in item and not keep_bounded_view:
            item.pop("bounded_view", None)
            item["bounded_view_externalized"] = True
            item["retrieval_action"] = "read_output"
            if is_semantically_pinned and already_hot_as_latest:
                item["bounded_view_hot_via"] = "latest_primary_result"
        elif "bounded_view" in item:
            item["bounded_view_hot_reason"] = "current_semantic_advice_reference"
        compacted.append(item)
    packet["evidence_index"] = compacted


def _compact_latest_primary_result(packet: dict[str, Any]) -> None:
    """Emergency hard-budget fallback only; never part of preferred hot view."""
    latest = packet.get("latest_primary_result")
    if not isinstance(latest, Mapping):
        return
    reduced = dict(latest)
    rows = reduced.get("outcome_receipts")
    if isinstance(rows, list):
        compacted: list[Any] = []
        for row in rows:
            if not isinstance(row, Mapping):
                compacted.append(row)
                continue
            item = dict(row)
            if "bounded_view" in item:
                item.pop("bounded_view", None)
                item["bounded_view_externalized"] = True
                item["exact_result_available_via"] = item.get("exact_access", {})
            compacted.append(item)
        reduced["outcome_receipts"] = compacted
    packet["latest_primary_result"] = reduced


def _trim_evidence_index(packet: dict[str, Any], limit: int = 12) -> None:
    rows = packet.get("evidence_index")
    if not isinstance(rows, list) or len(rows) <= limit:
        return
    pinned_refs, pinned_receipt_ids = _semantic_advice_evidence_pins(packet)
    latest = packet.get("latest_primary_result")
    if isinstance(latest, Mapping):
        for row in latest.get("outcome_receipts", ()) or ():
            if isinstance(row, Mapping):
                if row.get("evidence_ref"):
                    pinned_refs.add(str(row["evidence_ref"]))
                if row.get("receipt_id"):
                    pinned_receipt_ids.add(str(row["receipt_id"]))
    pinned = [
        row for row in rows
        if isinstance(row, Mapping)
        and (
            str(row.get("evidence_ref", "")) in pinned_refs
            or str(row.get("receipt_id", "")) in pinned_receipt_ids
        )
    ]
    recent = sorted(
        rows,
        key=lambda row: (
            int(row.get("step", -1))
            if isinstance(row, Mapping)
            and isinstance(row.get("step", -1), int)
            and not isinstance(row.get("step", -1), bool)
            else -1
        ),
        reverse=True,
    )[:limit]
    selected: list[Any] = []
    seen: set[str] = set()
    for row in [*recent, *pinned]:
        identity = stable_json(row)
        if identity in seen:
            continue
        seen.add(identity)
        selected.append(row)
    packet["evidence_index"] = selected
    handles = packet.get("receipt_exact_handles")
    if isinstance(handles, Mapping):
        kept_ids = {
            str(row.get("receipt_id", ""))
            for row in selected if isinstance(row, Mapping)
        }
        packet["receipt_exact_handles"] = {
            receipt_id: handle
            for receipt_id, handle in handles.items()
            if str(receipt_id) in kept_ids
        }


def _minimize_linked_history(
    packet: dict[str, Any],
    externalized: list[dict[str, Any]],
) -> None:
    """Externalize only sections that remain mechanically retrievable."""
    linked = packet.get("linked_history")
    if not isinstance(linked, Mapping):
        return
    retrieval = dict(_EXTERNALIZABLE_LINKED_SECTIONS)
    reduced: dict[str, Any] = {}
    for key, value in linked.items():
        if key in _MINIMAL_LINKED_KEYS or key not in retrieval:
            reduced[str(key)] = value
        else:
            externalized.append(_section_record(
                str(key), value, retrieval[str(key)], stage="linked_history_minimal",
            ))
    reduced["externalized_sections"] = list(externalized)
    packet["linked_history"] = reduced


def _preferred_hot_projection(
    original_body: Mapping[str, Any],
) -> tuple[dict[str, Any], list[str], list[dict[str, Any]], bool]:
    """Build a decision-hot PERSISTENT view and admit it only when strictly smaller.

    The immediately previous Primary result is deliberately untouched. We only
    externalize duplicated historical linked sections and historical evidence
    bounded views, then cap unpinned old evidence while preserving the latest evidence.
    """
    candidate = dict(original_body)
    externalized: list[dict[str, Any]] = []
    _externalize_linked_sections(candidate, externalized)
    _compact_evidence_views(candidate)
    _trim_evidence_index(candidate, limit=_PREFERRED_HOT_EVIDENCE_LIMIT)
    original_bytes, _ = _measure(original_body)
    candidate_bytes, _ = _measure(candidate)
    if candidate_bytes >= original_bytes:
        return dict(original_body), [], [], False
    return (
        candidate,
        [
            "preferred_hot_context",
            "externalize_linked_history",
            "compact_evidence_views",
            "trim_evidence_index_preserving_current",
        ],
        externalized,
        True,
    )


def finalize_persistent_context_budget(
    packet: Mapping[str, Any],
    compiled: Any,
) -> dict[str, Any]:
    """Return a preferred hot PERSISTENT packet or a measured fail-closed sentinel."""
    policy = compiled.context_policy
    budget_tokens = max(1, int(
        policy.model_context_window_tokens * policy.compression_trigger_ratio
    ))
    original_body = dict(packet)
    original_bytes, original_tokens = _measure(original_body)

    candidate, stages, externalized, hot_applied = _preferred_hot_projection(original_body)
    if hot_applied:
        fits, rendered = _fits(
            candidate,
            budget_tokens=budget_tokens,
            stages=stages,
            externalized=externalized,
            original_bytes=original_bytes,
            original_tokens=original_tokens,
        )
        if fits:
            return rendered
        # Hard-budget emergency: only now may the immediately previous result
        # lose its inline bounded view, with exact retrieval retained.
        _compact_latest_primary_result(candidate)
        stages.append("compact_latest_primary_result_inline_view")
        fits, rendered = _fits(
            candidate,
            budget_tokens=budget_tokens,
            stages=stages,
            externalized=externalized,
            original_bytes=original_bytes,
            original_tokens=original_tokens,
        )
        if fits:
            return rendered
        _minimize_linked_history(candidate, externalized)
        stages.append("minimize_linked_history")
        fits, rendered = _fits(
            candidate,
            budget_tokens=budget_tokens,
            stages=stages,
            externalized=externalized,
            original_bytes=original_bytes,
            original_tokens=original_tokens,
        )
        if fits:
            return rendered
    else:
        stages = []
        externalized = []
        fits, rendered = _fits(
            original_body,
            budget_tokens=budget_tokens,
            stages=stages,
            externalized=externalized,
            original_bytes=original_bytes,
            original_tokens=original_tokens,
        )
        if fits:
            return rendered

        candidate = dict(original_body)
        _externalize_linked_sections(candidate, externalized)
        stages.append("externalize_linked_history")
        fits, rendered = _fits(
            candidate,
            budget_tokens=budget_tokens, stages=stages,
            externalized=externalized, original_bytes=original_bytes,
            original_tokens=original_tokens,
        )
        if fits:
            return rendered

        _compact_evidence_views(candidate)
        stages.append("compact_evidence_views")
        fits, rendered = _fits(
            candidate,
            budget_tokens=budget_tokens, stages=stages,
            externalized=externalized, original_bytes=original_bytes,
            original_tokens=original_tokens,
        )
        if fits:
            return rendered

        _compact_latest_primary_result(candidate)
        stages.append("compact_latest_primary_result_inline_view")
        fits, rendered = _fits(
            candidate,
            budget_tokens=budget_tokens, stages=stages,
            externalized=externalized, original_bytes=original_bytes,
            original_tokens=original_tokens,
        )
        if fits:
            return rendered

        _trim_evidence_index(candidate)
        stages.append("trim_evidence_index_preserving_current")
        fits, rendered = _fits(
            candidate,
            budget_tokens=budget_tokens, stages=stages,
            externalized=externalized, original_bytes=original_bytes,
            original_tokens=original_tokens,
        )
        if fits:
            return rendered

        _minimize_linked_history(candidate, externalized)
        stages.append("minimize_linked_history")
        fits, rendered = _fits(
            candidate,
            budget_tokens=budget_tokens, stages=stages,
            externalized=externalized, original_bytes=original_bytes,
            original_tokens=original_tokens,
        )
        if fits:
            return rendered

    # The local byte/4 estimator is not provider authority. After every
    # provenance-preserving mechanical reduction has been attempted, send the
    # most compact truthful packet even when it exceeds the advisory threshold.
    # The actual model/provider context window is the only legitimate terminal
    # context boundary.
    return _with_budget_metadata(
        candidate,
        budget_tokens=budget_tokens,
        stages=[*stages, "advisory_threshold_exceeded_provider_authority"],
        externalized=externalized,
        within_budget=False,
        failure_reason="advisory_working_context_threshold_exceeded",
        original_bytes=original_bytes,
        original_tokens=original_tokens,
    )
