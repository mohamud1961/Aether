"""Small YAML compatibility shim for simple repository manifests.

The checkout contains a local ``yaml`` package path, so ``import yaml`` resolves
here before any optional PyYAML installation. This module intentionally exposes
the small ``safe_load``/``safe_dump`` surface the repo uses for nested mappings,
lists, and scalar values.
"""

from __future__ import annotations

from typing import Any


def safe_load(text: str) -> Any:
    """Parse a conservative subset of YAML used by repo manifests."""

    lines = _normal_lines(text)
    if not lines:
        return None
    value, _index = _parse_block(lines, 0, lines[0][0])
    return value


def safe_dump(payload: Any, *, sort_keys: bool = True, **_: Any) -> str:
    """Render nested dict/list/scalar payloads as simple YAML."""

    return "\n".join(_dump_lines(payload, indent=0, sort_keys=sort_keys)) + "\n"


def _normal_lines(text: str) -> list[tuple[int, str]]:
    normal: list[tuple[int, str]] = []
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        normal.append((indent, raw.strip()))
    return normal


def _parse_block(lines: list[tuple[int, str]], index: int, indent: int) -> tuple[Any, int]:
    if index >= len(lines):
        return {}, index
    if lines[index][1].startswith("- "):
        return _parse_list(lines, index, indent)
    return _parse_mapping(lines, index, indent)


def _parse_mapping(lines: list[tuple[int, str]], index: int, indent: int) -> tuple[dict[str, Any], int]:
    data: dict[str, Any] = {}
    while index < len(lines):
        current_indent, content = lines[index]
        if current_indent < indent:
            break
        if current_indent > indent:
            break
        if content.startswith("- "):
            break
        key, value = _split_key_value(content)
        if value is None:
            next_index = index + 1
            if next_index < len(lines) and lines[next_index][0] > current_indent:
                data[key], index = _parse_block(lines, next_index, lines[next_index][0])
            else:
                data[key] = None
                index = next_index
        else:
            data[key] = _parse_scalar(value)
            index += 1
    return data, index


def _parse_list(lines: list[tuple[int, str]], index: int, indent: int) -> tuple[list[Any], int]:
    items: list[Any] = []
    while index < len(lines):
        current_indent, content = lines[index]
        if current_indent != indent or not content.startswith("- "):
            break
        item_text = content[2:].strip()
        if not item_text:
            next_index = index + 1
            if next_index < len(lines) and lines[next_index][0] > current_indent:
                item, index = _parse_block(lines, next_index, lines[next_index][0])
                items.append(item)
            else:
                items.append(None)
                index = next_index
        elif ":" in item_text and not _looks_quoted(item_text):
            key, value = _split_key_value(item_text)
            item: dict[str, Any] = {key: _parse_scalar(value) if value is not None else None}
            index += 1
            if index < len(lines) and lines[index][0] > current_indent:
                child, index = _parse_mapping(lines, index, lines[index][0])
                item.update(child)
            items.append(item)
        else:
            items.append(_parse_scalar(item_text))
            index += 1
    return items, index


def _split_key_value(content: str) -> tuple[str, str | None]:
    if ":" not in content:
        raise ValueError(f"unsupported YAML line: {content}")
    key, value = content.split(":", 1)
    key = key.strip().strip("'\"")
    value = value.strip()
    return key, value if value else None


def _parse_scalar(value: str | None) -> Any:
    if value is None:
        return None
    stripped = value.strip()
    if stripped in {"true", "True"}:
        return True
    if stripped in {"false", "False"}:
        return False
    if stripped in {"null", "Null", "NULL", "~"}:
        return None
    if _looks_quoted(stripped):
        return stripped[1:-1]
    if stripped.startswith("[") and stripped.endswith("]"):
        inner = stripped[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(part.strip()) for part in inner.split(",")]
    try:
        return int(stripped)
    except ValueError:
        pass
    try:
        return float(stripped)
    except ValueError:
        return stripped


def _dump_lines(payload: Any, *, indent: int, sort_keys: bool) -> list[str]:
    prefix = " " * indent
    if isinstance(payload, dict):
        lines: list[str] = []
        keys = sorted(payload) if sort_keys else list(payload)
        for key in keys:
            value = payload[key]
            if isinstance(value, (dict, list)):
                lines.append(f"{prefix}{key}:")
                lines.extend(_dump_lines(value, indent=indent + 2, sort_keys=sort_keys))
            else:
                lines.append(f"{prefix}{key}: {_render_scalar(value)}")
        return lines
    if isinstance(payload, list):
        lines = []
        for value in payload:
            if isinstance(value, (dict, list)):
                lines.append(f"{prefix}-")
                lines.extend(_dump_lines(value, indent=indent + 2, sort_keys=sort_keys))
            else:
                lines.append(f"{prefix}- {_render_scalar(value)}")
        return lines
    return [f"{prefix}{_render_scalar(payload)}"]


def _render_scalar(value: Any) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return "null"
    text = str(value)
    if not text or text[:1].isspace() or text[-1:].isspace() or any(ch in text for ch in ":#[]{}"):
        return repr(text)
    return text


def _looks_quoted(value: str) -> bool:
    return len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}
