"""Carry forward compact linked-record query state from fact-style tool receipts.

Interface: ContextBlock.manage(history, new_observation) -> updated_history
"""

from __future__ import annotations

import re
from typing import Any

from .full_history import append_observation
from .semistructured_fact_projection import _extract_fact_receipts

_STATE_KEY = "linked_record_query_state"
_TAG = "[linked_record_query_state]"
_VERSION = "linked_record_query_state.v1"
_ID_RE = re.compile(r"(?:^id$|(?:^|_)(?:id|uuid|guid|code|key)$)")
_LINK_RE = re.compile(r"(?:owner|parent|manager|assignee|member|user|account|org|team|group|workspace|project|repo)")
_GROUP_RE = re.compile(r"(?:group|bucket|family|category|kind|type|status|owner|team|org|region)")
_RANK_RE = re.compile(r"(?:rank|score|priority|updated|created|timestamp|time|date|sequence|order|position|version|count|total)")
_SLOT_RE = re.compile(r"(?:slot|query|lookup|missing|target|filter|match|resolve|search|wanted|needed)")
_SHARED_RE = re.compile(r"(?:name|email|slug|title|handle|path|url|phone)")
_NONEISH = {"", "-", "?", "unknown", "none", "null", "missing", "unresolved", "pending", "tbd"}
def manage(history: list[dict[str, Any]], new_observation: dict[str, Any]) -> list[dict[str, Any]]:
    observation = dict(new_observation)
    if observation.get("role") != "tool":
        return append_observation(history, observation)
    signals = _merged_signals(history, observation)
    if not signals:
        return append_observation(history, observation)
    state = _build_state(signals)
    observation[_STATE_KEY] = state
    content = observation.get("content")
    marker = _marker_text(state)
    observation["content"] = f"{content}\n\n{marker}" if isinstance(content, str) and content else marker
    return append_observation(history, observation)
def _merged_signals(history: list[dict[str, Any]], observation: dict[str, Any]) -> list[dict[str, str]]:
    signals = list(_latest_state(history).get("signals") or [])
    seen = {(item.get("k"), item.get("v"), item.get("sf"), item.get("t")) for item in signals if isinstance(item, dict)}
    projection = observation.get("semistructured_fact_projection")
    facts = projection.get("facts") if isinstance(projection, dict) else None
    if not isinstance(facts, list):
        content = observation.get("content")
        facts = _extract_fact_receipts(content, len(history) + 1) if isinstance(content, str) and content else []
    for fact in facts:
        for signal in _fact_signals(fact):
            sig = (signal["k"], signal["v"], signal["sf"], signal["t"])
            if sig in seen:
                continue
            seen.add(sig)
            signals.append(signal)
    return signals[-24:]
def _latest_state(history: list[dict[str, Any]]) -> dict[str, Any]:
    for row in reversed(history):
        state = row.get(_STATE_KEY)
        if isinstance(state, dict):
            return dict(state)
    return {}
def _fact_signals(fact: Any) -> list[dict[str, str]]:
    if not isinstance(fact, dict):
        return []
    family = _source_family(fact.get("source_path"))
    value = fact.get("value")
    if isinstance(value, dict):
        signals: list[dict[str, str]] = []
        for raw_key, raw_value in value.items():
            key = _norm_key(raw_key)
            text = _norm_value(raw_value)
            if key or text:
                signals.append(_signal(key or "fact", text or "-", family, fact))
        return signals
    key = _norm_key(fact.get("key") or fact.get("fact_type") or "fact")
    text = _norm_value(value)
    if not key and not text:
        return []
    return [_signal(key or "fact", text or "-", family, fact)]


def _signal(key: str, value: str, family: str, fact: dict[str, Any]) -> dict[str, str]:
    tags: list[str] = []
    if _is_id_key(key):
        tags.append("id")
    if _is_link_key(key):
        tags.append("link")
    if _is_group_key(key):
        tags.append("group")
    if _is_rank_key(key):
        tags.append("rank")
    if _is_shared_key(key):
        tags.append("shared")
    if _is_unresolved(fact, key, value):
        tags.append("slot")
    return {"k": key, "v": value, "sf": family, "t": ",".join(tags) or "fact"}
def _build_state(signals: list[dict[str, str]]) -> dict[str, Any]:
    linked_values: dict[str, list[dict[str, str]]] = {}
    unresolved, families = [], []
    join_keys, group_keys, rank_keys, entity_ids, ownership = [], [], [], [], []
    for item in signals:
        key, value, family, tags = item["k"], item["v"], item["sf"], set(item["t"].split(","))
        if family and family not in families:
            families.append(family)
        if "slot" in tags and key not in unresolved:
            unresolved.append(key)
        if "group" in tags and key not in group_keys:
            group_keys.append(key)
        if "rank" in tags and key not in rank_keys:
            rank_keys.append(key)
        if "id" in tags and value not in _NONEISH and f"{key}={value}" not in entity_ids:
            entity_ids.append(f"{key}={value}")
        if _LINK_RE.search(key) and key not in ownership:
            ownership.append(key)
        if value not in _NONEISH and tags.intersection({"id", "link", "shared"}):
            linked_values.setdefault(value, []).append(item)
    linked_groups = [group for group in linked_values.values() if _forms_link(group)]
    for group in linked_groups:
        for item in group:
            if item["k"] not in join_keys:
                join_keys.append(item["k"])
    linked_records = len(linked_groups)
    reduction_ready = bool(linked_records and not unresolved and (rank_keys or group_keys))
    next_action = (
        "resolve_query_slots"
        if unresolved
        else "reduce_ranked_records"
        if linked_records and rank_keys
        else "reduce_grouped_records"
        if linked_records and group_keys
        else "collect_linked_records"
        if join_keys
        else "collect_more_receipts"
    )
    return {
        "version": _VERSION,
        "receipt_count": len(signals),
        "signals": signals,
        "source_families": families[:4],
        "entity_ids": entity_ids[:4],
        "ownership_links": ownership[:4],
        "join_keys": join_keys[:5],
        "grouping_keys": group_keys[:4],
        "ranking_fields": rank_keys[:4],
        "unresolved_slots": unresolved[:4],
        "linked_records_formed": linked_records,
        "reduction_ready": reduction_ready,
        "next_action": next_action,
    }
def _forms_link(group: list[dict[str, str]]) -> bool:
    keys = {item["k"] for item in group}
    families = {item["sf"] for item in group}
    return len(group) >= 2 and (len(keys) >= 2 or len(families) >= 2)
def _marker_text(state: dict[str, Any]) -> str:
    unresolved = ",".join(state["unresolved_slots"]) or "none"
    join_keys = ",".join(state["join_keys"]) or "none"
    groups = ",".join(state["grouping_keys"]) or "none"
    ranking = ",".join(state["ranking_fields"]) or "none"
    families = ",".join(state["source_families"]) or "unknown"
    return (
        f"{_TAG} linked_records_formed={state['linked_records_formed']} unresolved_slots={unresolved} "
        f"join_keys={join_keys} reduction_ready={str(state['reduction_ready']).lower()} "
        f"next_action={state['next_action']}\n"
        f"linked_record_query_state.details source_families={families} grouping_keys={groups} ranking_fields={ranking}"
    )
def _source_family(path: Any) -> str:
    text = str(path or "").strip().lower()
    if not text:
        return "unknown"
    for suffix, family in ((".json", "structured"), (".csv", "structured"), (".yaml", "structured"), (".yml", "structured"), (".log", "logs"), (".md", "docs"), (".txt", "docs")):
        if text.endswith(suffix):
            return family
    parts = [part for part in text.split("/") if part]
    return parts[0] if parts else "unknown"
def _norm_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")
def _norm_value(value: Any) -> str:
    text = str(value if value is not None else "").replace("\n", " ").strip().strip(",;:")
    return text[:48].lower()
def _is_id_key(key: str) -> bool:
    return bool(key and (_ID_RE.search(key) or key.endswith("_id")))
def _is_link_key(key: str) -> bool:
    return bool(key and (_is_id_key(key) or _LINK_RE.search(key)))
def _is_group_key(key: str) -> bool:
    return bool(key and _GROUP_RE.search(key))
def _is_rank_key(key: str) -> bool:
    return bool(key and _RANK_RE.search(key))
def _is_shared_key(key: str) -> bool:
    return bool(key and _SHARED_RE.search(key))
def _is_unresolved(fact: dict[str, Any], key: str, value: str) -> bool:
    if value in _NONEISH:
        return True
    if _SLOT_RE.search(key) or "slot" in _norm_key(fact.get("fact_type")):
        return True
    raw = _norm_value(fact.get("raw_text") or "")
    return any(token in raw for token in ("missing", "unresolved", "lookup", "need ", "wanted", "tbd"))
