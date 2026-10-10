"""Fail-closed recovery for incomplete native tool argument JSON."""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any


class _InvalidJSON(ValueError):
    pass


def _pairs_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _InvalidJSON(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _constant_rejected(value: str) -> None:
    raise _InvalidJSON(f"non-JSON constant: {value}")


def _strict_loads(value: str) -> Any:
    return json.loads(
        value, object_pairs_hook=_pairs_no_duplicates, parse_constant=_constant_rejected,
    )


def _incomplete_value_tail(value: str) -> bool:
    """Recognize only clear end-of-input truncations, never arbitrary bad syntax."""
    tail = value.rstrip()
    if not tail:
        return True
    if tail.startswith('"'):
        index = 1
        while index < len(tail):
            char = tail[index]
            if ord(char) < 0x20:
                return False
            if char == '"':
                return False
            if char == "\\":
                index += 1
                if index == len(tail):
                    return True
                escape = tail[index]
                if escape == "u":
                    digits = tail[index + 1:index + 5]
                    if any(digit not in "0123456789abcdefABCDEF" for digit in digits):
                        return False
                    return len(digits) < 4
                if escape not in '"\\/bfnrt':
                    return False
            index += 1
        return True
    if tail in {"t", "tr", "tru", "f", "fa", "fal", "fals", "n", "nu", "nul", "-"}:
        return True
    if re.fullmatch(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]*)?(?:[eE][+-]?[0-9]*)?", tail):
        return tail.endswith((".", "e", "E", "e+", "e-", "E+", "E-"))
    return False


def _salvage_object(text: str) -> tuple[dict[str, Any], str] | None:
    """Return complete top-level members and the discarded trailing bytes.

    Complete invalid members, duplicate keys, and syntax errors before the final
    member are rejected. Missing required fields are left for the unchanged
    canonical tool validator to reject.
    """
    decoder = json.JSONDecoder(object_pairs_hook=_pairs_no_duplicates, parse_constant=_constant_rejected)
    n = len(text)
    pos = 0

    def ws(index: int) -> int:
        while index < n and text[index] in " \t\r\n":
            index += 1
        return index

    pos = ws(pos)
    if pos >= n or text[pos] != "{":
        return None
    pos = ws(pos + 1)
    fields: dict[str, Any] = {}
    dropped_start: int | None = None
    while True:
        if pos >= n:
            return (fields, text[dropped_start:]) if fields and dropped_start is not None else (fields, "") if fields else None
        if text[pos] == "}":
            if dropped_start is not None:
                return None
            end = ws(pos + 1)
            if end != n:
                return None
            return fields, text[dropped_start:] if dropped_start is not None else ""
        member_start = pos
        try:
            key, key_end = decoder.raw_decode(text, pos)
        except (ValueError, json.JSONDecodeError):
            tail = text[pos:]
            if fields and _incomplete_value_tail(tail):
                return fields, text[dropped_start if dropped_start is not None else member_start:]
            return None
        if not isinstance(key, str) or key in fields:
            return None
        colon = ws(key_end)
        if colon >= n:
            return None
        if text[colon] != ":":
            return None
        value_start = ws(colon + 1)
        try:
            member_value, value_end = decoder.raw_decode(text, value_start)
        except (ValueError, json.JSONDecodeError):
            if fields and _incomplete_value_tail(text[value_start:]):
                return fields, text[dropped_start if dropped_start is not None else member_start:]
            return None
        fields[key] = member_value
        dropped_start = None
        pos = ws(value_end)
        if pos < n and text[pos] == "}":
            end = ws(pos + 1)
            return (fields, text[dropped_start:] if dropped_start is not None else "") if end == n else None
        if pos >= n:
            return fields, text[dropped_start:] if dropped_start is not None else ""
        if text[pos] != ",":
            return None
        comma = pos
        pos = ws(pos + 1)
        dropped_start = comma if dropped_start is None else dropped_start


def _recover_nested_arguments(payload: dict[str, Any]) -> tuple[dict[str, Any], str, str] | None:
    """Decode or salvage an arguments string without changing its envelope."""
    inner = payload.get("arguments")
    if not isinstance(inner, str):
        return None
    try:
        decoded = _strict_loads(inner)
    except (ValueError, TypeError):
        decoded = None
    if isinstance(decoded, dict):
        return {**payload, "arguments": decoded}, "json_string_arguments", ""
    partial = _salvage_object(inner)
    if partial is None:
        return None
    recovered, dropped_tail = partial
    kind = "truncated_json_string_wrapper" if set(payload) == {"arguments"} else "truncated_json_string_arguments"
    return {**payload, "arguments": recovered}, kind, dropped_tail


def recover_argument_object(arguments: str) -> tuple[str, dict[str, Any] | None]:
    """Unwrap or salvage one object; return canonical JSON and provenance.

    Final schema validation remains the responsibility of the existing native
    tool canonicalizer. This helper never supplies or changes a field value.
    """
    original = str(arguments)
    payload: Any
    try:
        payload = _strict_loads(original)
    except (ValueError, TypeError):
        payload = None
    kind = ""
    dropped_tail = ""
    if isinstance(payload, str):
        inner = payload
        try:
            decoded = _strict_loads(inner)
        except (ValueError, TypeError):
            decoded = None
        if isinstance(decoded, dict):
            payload = decoded
            nested = _recover_nested_arguments(payload)
            if nested is not None:
                payload, kind, dropped_tail = nested
            else:
                kind = "json_string"
        else:
            partial = _salvage_object(inner)
            if partial is None:
                return original, None
            payload, dropped_tail = partial
            kind = "truncated_json_string"
    elif isinstance(payload, dict) and isinstance(payload.get("arguments"), str):
        nested = _recover_nested_arguments(payload)
        if nested is None:
            return original, None
        payload, kind, dropped_tail = nested
    elif not isinstance(payload, dict):
        partial = _salvage_object(original)
        if partial is None:
            return original, None
        payload, dropped_tail = partial
        kind = "truncated_json"
    else:
        return original, None

    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    provenance = {
        "kind": kind,
        "original_arguments_sha256": hashlib.sha256(original.encode("utf-8")).hexdigest(),
        "dropped_tail": dropped_tail,
    }
    return encoded, provenance


def compact_interpreted_arguments(arguments: dict[str, Any], *, limit: int = 160) -> str:
    """Render a bounded preview for the model-visible salvage notice."""
    preview = dict(arguments)
    for key, value in preview.items():
        if isinstance(value, str) and len(value) > 80:
            preview[key] = value[:48] + f"…<{len(value) - 48} chars omitted>"
    encoded = json.dumps(preview, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    if len(encoded) <= limit:
        return encoded
    keys = sorted(str(key)[:8] for key in arguments)
    return json.dumps(
        {"keys": keys[:3], "additional_key_count": max(0, len(keys) - 3), "preview": "<large values omitted>"},
        separators=(",", ":"),
    )
