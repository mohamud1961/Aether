"""Checking a tool call against the advertised flat contract before any effect (split from tools.py, module cap)."""

from __future__ import annotations

import math
from typing import Any


def validate_call(
    name: str, arguments: dict[str, Any], definitions: list[dict[str, Any]]
) -> None:
    """Validate the advertised flat tool contract before any effect; never coerce an invalid value."""
    fn = next(
        (d["function"] for d in definitions if d["function"]["name"] == name), None
    )
    if fn is None:
        raise ValueError(
            f"unknown tool {name!r} (or unavailable in this run); use an advertised tool"
        )
    schema = fn["parameters"]
    missing = set(schema.get("required", ())) - arguments.keys()
    if missing:
        raise ValueError(
            f"{name}: missing required arguments: {', '.join(sorted(missing))}"
        )
    _check_object(name, arguments, schema)


def _check_object(where: str, value: dict[str, Any], schema: dict[str, Any]) -> None:
    properties = schema.get("properties", {})
    for key, item in value.items():
        if key not in properties:
            if schema.get("additionalProperties") is True:
                continue  # The downstream tool owns these keys and validates their values.
            raise ValueError(
                f"{where}: unknown argument {key!r}; allowed: {', '.join(properties)}"
            )
        _check_value(f"{where}.{key}", item, properties[key])


def _check_value(where: str, value: Any, rule: dict[str, Any]) -> None:
    """One value against its rule; arrays and objects are checked element by element."""
    kind = rule["type"]
    valid = {
        "string": isinstance(value, str),
        "boolean": type(value) is bool,
        "integer": type(value) is int,
        "number": type(value) in (int, float) and math.isfinite(value),
        "array": isinstance(value, list),
        "object": isinstance(value, dict),
    }.get(kind, False)
    if not valid:
        raise ValueError(f"{where}: expected {kind}, got {type(value).__name__}")
    if "enum" in rule and value not in rule["enum"]:
        raise ValueError(f"{where}: expected one of {rule['enum']}")
    if kind == "array" and "items" in rule:
        for index, element in enumerate(value):
            _check_value(f"{where}[{index}]", element, rule["items"])
    if kind == "object":
        missing = set(rule.get("required", ())) - value.keys()
        if missing:
            raise ValueError(
                f"{where}: missing required fields: {', '.join(sorted(missing))}"
            )
        _check_object(where, value, rule)


def unsendable_text(text: str, *, shell: bool) -> str:
    """Why ``text`` cannot reach its receiver byte for byte, or "". Owners check this before any state changes, so a
    refused call leaves nothing pending (T1, 15 Nov: a lone surrogate left a phantom "still running" terminal command,
    and a NUL byte was dropped by bash while the command reported exit 0)."""
    try:
        text.encode()
    except UnicodeEncodeError as exc:
        return (f"it contains text that has no UTF-8 bytes ({text[exc.start:exc.end]!r} at index {exc.start}, an "
                "unpaired surrogate)")
    if shell and "\x00" in text:
        return (f"it contains a NUL byte (index {text.index(chr(0))}), which a shell command cannot carry: bash drops it "
                "silently. Produce NUL bytes with printf '\\0' or from python instead")
    return ""
