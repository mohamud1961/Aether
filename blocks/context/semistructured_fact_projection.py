"""Project parser-emitted fact receipts into prompt-visible grounded evidence.

Interface: ContextBlock.manage(history, new_observation) -> updated_history
"""

from __future__ import annotations

import json
import re
from typing import Any

from .full_history import append_observation
from .structured_observation_register import apply_structured_observation_register

_FACT_PREFIX_RE = re.compile(
    r"^\s*(?:[-*]\s*)?(?:P07_FACT|SEMISTRUCTURED_FACT|"
    r"\[(?:fact_receipt|fact-receipt|parser_fact_receipt)\]|"
    r"(?:fact_receipt|fact-receipt|parser_fact_receipt|FACT_RECEIPT))\s*[:|-]?\s*(?P<payload>.*)$"
)
_KV_RE = re.compile(r"(?P<key>[A-Za-z0-9_.-]+)\s*(?:=|:)\s*(?P<value>.+)")


def manage(history: list[dict[str, Any]], new_observation: dict[str, Any]) -> list[dict[str, Any]]:
    observation = apply_structured_observation_register(history, dict(new_observation))
    if observation.get("role") != "tool":
        return append_observation(history, observation)
    content = observation.get("content")
    if not isinstance(content, str) or not content:
        return append_observation(history, observation)
    facts = _extract_fact_receipts(content, len(history) + 1)
    if not facts:
        return append_observation(history, observation)
    observation["semistructured_fact_projection"] = {
        "status": "active",
        "fact_count": len(facts),
        "fact_ids": [fact["fact_id"] for fact in facts],
        "facts": facts,
    }
    projection = _projection_text(facts)
    observation["content"] = f"{content}\n\n{projection}" if projection else content
    return append_observation(history, observation)


def _extract_fact_receipts(content: str, base_index: int) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for line_index, raw_line in enumerate(content.splitlines(), start=1):
        match = _FACT_PREFIX_RE.match(raw_line)
        if not match:
            continue
        payload = _parse_payload(match.group("payload"))
        facts.append(
            {
                "fact_id": f"sfp-{base_index:04d}-{len(facts) + 1:02d}",
                "line_index": line_index,
                "raw_line": raw_line,
                "fact_type": _text(payload, "fact_type", "type", default="fact"),
                "key": _text(payload, "key", "field", "name"),
                "value": _value(payload),
                "source_path": _text(payload, "source_path", "path"),
                "source_span": _text(payload, "source_span", "span"),
                "raw_text": _text(payload, "raw_text", "text", default=raw_line.strip()),
                "confidence": _text(payload, "confidence", default="unknown"),
                "parser_mode": _text(payload, "parser_mode", "mode", default="unknown"),
                "receipt_fields": payload,
            }
        )
    return facts


def _parse_payload(payload: str) -> dict[str, Any]:
    stripped = payload.strip()
    if not stripped:
        return {}
    if stripped.startswith("{") and stripped.endswith("}"):
        parsed = _try_json(stripped)
        if isinstance(parsed, dict):
            return parsed
    result: dict[str, Any] = {}
    parts = [part.strip() for part in re.split(r"\s+\|\s+|\s*;\s*", stripped) if part.strip()]
    for part in parts:
        match = _KV_RE.fullmatch(part)
        if not match:
            continue
        key = match.group("key")
        result[key] = _coerce_scalar(match.group("value"))
    if result:
        return result
    return {"raw_text": stripped}


def _try_json(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _coerce_scalar(value: str) -> Any:
    stripped = value.strip().strip(",")
    if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in {'"', "'"}:
        stripped = stripped[1:-1]
    lowered = stripped.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"null", "none"}:
        return None
    if re.fullmatch(r"-?\d+", stripped):
        return int(stripped)
    if re.fullmatch(r"-?\d+\.\d+", stripped):
        return float(stripped)
    return stripped


def _text(payload: dict[str, Any], *keys: str, default: str = "") -> str:
    for key in keys:
        value = payload.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return default


def _value(payload: dict[str, Any]) -> Any:
    if "value" in payload:
        return payload["value"]
    for key in ("raw_text", "text"):
        if key in payload:
            return payload[key]
    return ""


def _projection_text(facts: list[dict[str, Any]]) -> str:
    lines = [
        "[semistructured_fact_projection] "
        f"parser_created_fact=true | fact_count={len(facts)} | fact_selection_ready=true | "
        "grounding_mode=provenance_oriented | parser_created_fact=true"
    ]
    for idx, fact in enumerate(facts[:3], start=1):
        label = fact["key"] or fact["fact_type"]
        value = _short(fact["value"], 72)
        provenance = _provenance(fact)
        lines.append(
            f"fact[{idx}] id={fact['fact_id']} key={label} value={value} "
            f"provenance={provenance} confidence={fact['confidence']} parser_mode={fact['parser_mode']}"
        )
    if len(facts) > 3:
        lines.append(f"fact[more] count={len(facts) - 3} select_additional_facts_from_structured_state=true")
    return "\n".join(lines)


def _provenance(fact: dict[str, Any]) -> str:
    path = _short(fact.get("source_path") or "-", 48)
    span = str(fact.get("source_span") or "-")
    return f"{path}@{span}"


def _short(value: Any, limit: int) -> str:
    text = str(value).replace("\n", "\\n").strip()
    if len(text) <= limit:
        return text or "-"
    return f"{text[: limit - 3]}..."
