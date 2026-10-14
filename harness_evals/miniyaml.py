"""A small YAML subset for task.yaml. Anything outside the subset raises MiniYamlError.

Supported:
  key: value                  string, integer, or true/false (bare or quoted strings)
  key: [a, "b", 3]            inline list of scalars
  key:                        block list follows, one "- item" per indented line
    - a
    - b
  # comment                   full-line comments and trailing comments after whitespace

Not supported: nested mappings, multi-line scalars, anchors, tags, flow mappings.
A key with no value and no block items is an empty list.
"""

from __future__ import annotations

import re
from typing import Any

_INT = re.compile(r"-?\d+")
_KEY = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


class MiniYamlError(ValueError):
    """Raised for input outside the supported subset, with the line number."""


def parse(text: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    block_key: str | None = None
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = _strip_comment(raw).rstrip()
        if not line.strip():
            continue
        if line[0] in " \t":
            if block_key is None:
                raise MiniYamlError(
                    f"line {lineno}: indented line without a block list key"
                )
            indent = line[: len(line) - len(line.lstrip())]
            if "\t" in indent:
                raise MiniYamlError(
                    f"line {lineno}: tabs are not allowed for indentation"
                )
            item = line.strip()
            if item != "-" and not item.startswith("- "):
                raise MiniYamlError(f"line {lineno}: expected a '- item' list entry")
            result[block_key].append(_scalar(item[1:].strip(), lineno))
            continue
        key, sep, rest = line.partition(":")
        if not sep or not _KEY.fullmatch(key):
            raise MiniYamlError(f"line {lineno}: expected 'key: value'")
        if key in result:
            raise MiniYamlError(f"line {lineno}: duplicate key {key!r}")
        rest = rest.strip()
        block_key = None
        if rest == "":
            result[key] = []
            block_key = key
        elif rest.startswith("["):
            result[key] = _inline_list(rest, lineno)
        else:
            result[key] = _scalar(rest, lineno)
    return result


def _strip_comment(raw: str) -> str:
    """Cut a '#' that starts a comment: at line start or after whitespace, outside quotes."""
    quote: str | None = None
    for index, char in enumerate(raw):
        if quote is not None:
            if char == quote:
                quote = None
            continue
        if char in "\"'" and (index == 0 or raw[index - 1] in " :[,-\t"):
            quote = char
        elif char == "#" and (index == 0 or raw[index - 1] in " \t"):
            return raw[:index]
    return raw


def _inline_list(text: str, lineno: int) -> list[Any]:
    if not text.endswith("]"):
        raise MiniYamlError(f"line {lineno}: inline list must end with ']'")
    body = text[1:-1].strip()
    if body == "":
        return []
    return [_scalar(part.strip(), lineno) for part in _split_commas(body, lineno)]


def _split_commas(body: str, lineno: int) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    quote: str | None = None
    for char in body:
        if quote is not None:
            if char == quote:
                quote = None
            current.append(char)
        elif char in "\"'":
            quote = char
            current.append(char)
        elif char == ",":
            parts.append("".join(current))
            current = []
        else:
            current.append(char)
    if quote is not None:
        raise MiniYamlError(f"line {lineno}: unterminated quote in inline list")
    parts.append("".join(current))
    return parts


def _scalar(text: str, lineno: int) -> Any:
    if text == "":
        raise MiniYamlError(f"line {lineno}: empty value")
    if text[0] in "\"'":
        if len(text) < 2 or text[-1] != text[0]:
            raise MiniYamlError(f"line {lineno}: unterminated quoted value")
        return text[1:-1]
    if text in ("true", "false"):
        return text == "true"
    if _INT.fullmatch(text):
        return int(text)
    if text[0] in "[{&*!|>%@`":
        raise MiniYamlError(f"line {lineno}: unsupported YAML syntax {text[0]!r}")
    return text
