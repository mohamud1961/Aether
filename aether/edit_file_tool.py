"""Opt-in ``edit_file`` action: grammar, provider tool, and pure edit semantics.

``edit_file`` is available only on the ``static_kernel_edit_v1`` tool surface.
It is a partial-edit companion to ``write_file``: the same workspace-anchored
path rules and the same kernel/executor path, but the model sends only the
changed region instead of replaying the whole file.

This module has no dependency on the protocol, kernel, or executor so that all
of them can import it.  Two forms share one tool:

* ``{path, old, new}`` / ``{path, old, new, replace_all: true}`` -- exact
  substring replacement (exactly one occurrence unless ``replace_all``).
* ``{path, insert_after_line, text}`` -- line insertion (0 = top of file).
"""
from __future__ import annotations

import difflib
from dataclasses import dataclass
from typing import Any, Mapping

EDIT_FILE_ACTION = "edit_file"
# Canonical kernel action-schema entry (name, required arguments).  It is added
# to a compiled runtime only on the edit surface, never to the control schema.
EDIT_FILE_ACTION_SCHEMA_ENTRY: tuple[str, tuple[str, ...]] = (EDIT_FILE_ACTION, ("path",))

MAX_DIFF_LINES = 40
MAX_HINT_LINES = 5

EDIT_FILE_DESCRIPTION = (
    "Edit an existing workspace file in place; paths work as in write_file. Replace one exact `old` "
    "substring with `new` (it must match exactly once; replace_all:true replaces every match), or "
    "insert `text` after line `insert_after_line` (0 = top). Prefer it to write_file for small changes."
)

_NONEMPTY: dict[str, Any] = {"type": "string", "pattern": r"\S"}


def _object(properties: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(properties),
        "properties": {key: dict(value) for key, value in properties.items()},
    }


def edit_file_argument_variants() -> tuple[dict[str, Any], ...]:
    """Exact canonical argument variants (the schema every turn is validated against)."""
    return (
        _object({"path": _NONEMPTY, "old": {"type": "string", "minLength": 1}, "new": {"type": "string"}}),
        _object({
            "path": _NONEMPTY, "old": {"type": "string", "minLength": 1},
            "new": {"type": "string"}, "replace_all": {"type": "boolean"},
        }),
        _object({
            "path": _NONEMPTY, "insert_after_line": {"type": "integer", "minimum": 0},
            "text": {"type": "string"},
        }),
    )


_EDIT_FIELDS = frozenset({"path", "old", "new", "replace_all", "insert_after_line", "text"})


def edit_file_arguments_error(arguments: Mapping[str, Any]) -> str:
    """Return a factual shape error for edit_file arguments, or the empty string."""
    keys = set(arguments)
    unknown = sorted(keys - _EDIT_FIELDS)
    if unknown:
        return f"edit_file does not take {', '.join(unknown)}"
    path = arguments.get("path")
    if not isinstance(path, str) or not path.strip():
        return "edit_file requires a non-empty string path"
    if "insert_after_line" in keys:
        extra = sorted(keys & {"old", "new", "replace_all"})
        if extra:
            return f"edit_file insert form takes only path, insert_after_line, text (got {', '.join(extra)})"
        line, text = arguments.get("insert_after_line"), arguments.get("text")
        if type(line) is not int or line < 0:
            return "edit_file insert_after_line must be an integer >= 0"
        if not isinstance(text, str):
            return "edit_file insert form requires string text"
        return ""
    if "text" in keys:
        return "edit_file text requires insert_after_line"
    old, new = arguments.get("old"), arguments.get("new")
    if not isinstance(old, str) or not old:
        return "edit_file requires a non-empty string old (or insert_after_line with text)"
    if not isinstance(new, str):
        return "edit_file requires string new"
    if "replace_all" in keys and type(arguments["replace_all"]) is not bool:
        return "edit_file replace_all must be a boolean"
    return ""


def edit_file_provider_tool(*, commitment_fields: Mapping[str, Mapping[str, Any]] | None = None) -> dict[str, Any]:
    """Flat Chat-Completions function shape (no ``arguments`` wrapper), like run_command.

    Mutual exclusivity of the two forms is validated locally with a factual error,
    so the provider schema carries only ``path`` as required and is not strict.
    """
    properties: dict[str, Any] = {
        "path": {**_NONEMPTY, "description": "File to edit, relative to the workspace root."},
        "old": {"type": "string", "description": "Exact text to replace (must occur exactly once unless replace_all)."},
        "new": {"type": "string", "description": "Replacement text."},
        "replace_all": {"type": "boolean", "description": "Replace every occurrence of old."},
        "insert_after_line": {"type": "integer", "minimum": 0, "description": "Insert text after this 1-based line (0 = top)."},
        "text": {"type": "string", "description": "Text to insert; used with insert_after_line."},
    }
    required = ["path"]
    for name, schema in (commitment_fields or {}).items():
        properties[name] = dict(schema)
        required.append(name)
    return {
        "type": "function",
        "name": EDIT_FILE_ACTION,
        "description": EDIT_FILE_DESCRIPTION,
        "parameters": {
            "type": "object", "additionalProperties": False,
            "required": required, "properties": properties,
        },
        "strict": False,
    }


@dataclass(frozen=True)
class EditResult:
    ok: bool
    form: str                      # replace | replace_all | insert
    new_content: str = ""
    failure_class: str = ""
    message: str = ""              # factual failure text (ok=False)
    replacements: int = 0
    first_line: int = 0            # 1-based range in the new file
    last_line: int = 0
    diff: str = ""


def _line_of(content: str, index: int) -> int:
    return content.count("\n", 0, index) + 1


def _occurrence_lines(content: str, needle: str) -> list[int]:
    lines: list[int] = []
    start = content.find(needle)
    while start != -1:
        lines.append(_line_of(content, start))
        start = content.find(needle, start + len(needle))
    return lines


def _fmt_lines(lines: list[int], limit: int = MAX_HINT_LINES) -> str:
    shown = ", ".join(str(n) for n in lines[:limit])
    return shown + (f" (+{len(lines) - limit} more)" if len(lines) > limit else "")


def _not_found_hint(content: str, old: str) -> str:
    first = old.split("\n", 1)[0]
    exact = [i for i, line in enumerate(content.split("\n"), 1) if first and first in line]
    if exact:
        return f"the first line of old appears at line(s) {_fmt_lines(exact)}; the rest of old does not match there"
    stripped = first.strip()
    loose = [i for i, line in enumerate(content.split("\n"), 1) if stripped and stripped in line.strip()]
    if loose:
        return (f"no exact match of old's first line; it matches ignoring surrounding whitespace at "
                f"line(s) {_fmt_lines(loose)}")
    return "the first line of old does not appear anywhere in the file"


def _bounded_diff(before: str, after: str, path: str) -> str:
    rows = list(difflib.unified_diff(
        before.splitlines(), after.splitlines(), f"a/{path}", f"b/{path}", n=2, lineterm="",
    ))
    if len(rows) > MAX_DIFF_LINES:
        omitted = len(rows) - MAX_DIFF_LINES
        rows = [*rows[:MAX_DIFF_LINES], f"... ({omitted} more diff lines)"]
    return "\n".join(rows)


def _changed_range(before: str, after: str) -> tuple[int, int]:
    """1-based inclusive changed range in the new file (a pure deletion reports its seam line)."""
    old_lines, new_lines = before.split("\n"), after.split("\n")
    first, last = None, 0
    for tag, _i1, _i2, j1, j2 in difflib.SequenceMatcher(None, old_lines, new_lines, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        first = j1 + 1 if first is None else first
        last = max(last, j2, j1 + 1)
    return (first or 1, max(last, first or 1))


def apply_edit(content: str, arguments: Mapping[str, Any], *, path: str) -> EditResult:
    """Apply one edit to ``content``; never raises for a model-side mistake."""
    error = edit_file_arguments_error({**dict(arguments), "path": path})
    if error:
        return EditResult(False, "replace", failure_class="edit_invalid_arguments", message=error)
    if "insert_after_line" in arguments:
        return _apply_insert(content, int(arguments["insert_after_line"]), str(arguments["text"]), path)
    old, new = str(arguments["old"]), str(arguments["new"])
    replace_all = arguments.get("replace_all") is True
    form = "replace_all" if replace_all else "replace"
    if old == new:
        return EditResult(False, form, failure_class="edit_no_change",
                          message="old and new are identical; the file would not change")
    lines = _occurrence_lines(content, old)
    if not lines:
        return EditResult(False, form, failure_class="edit_not_found",
                          message=f"old text not found in {path} (0 occurrences); {_not_found_hint(content, old)}")
    if len(lines) > 1 and not replace_all:
        return EditResult(False, form, failure_class="edit_ambiguous", replacements=len(lines), message=(
            f"old text matches {len(lines)} places in {path} (lines {_fmt_lines(lines)}); add surrounding "
            "context to old to make it unique, or pass replace_all:true"))
    updated = content.replace(old, new) if replace_all else content.replace(old, new, 1)
    first, last = _changed_range(content, updated)
    return EditResult(True, form, new_content=updated, replacements=len(lines) if replace_all else 1,
                      first_line=first, last_line=last, diff=_bounded_diff(content, updated, path))


def _apply_insert(content: str, after: int, text: str, path: str) -> EditResult:
    lines = content.splitlines(keepends=True)
    if after > len(lines):
        return EditResult(False, "insert", failure_class="edit_line_out_of_range", message=(
            f"insert_after_line {after} is past the end of {path} ({len(lines)} lines)"))
    if not text:
        return EditResult(False, "insert", failure_class="edit_no_change", message="text is empty; the file would not change")
    block = text if text.endswith("\n") else text + "\n"
    head, tail = lines[:after], lines[after:]
    if head and not head[-1].endswith("\n"):
        head[-1] += "\n"
    updated = "".join(head) + block + "".join(tail)
    count = block.count("\n") or 1
    return EditResult(True, "insert", new_content=updated, replacements=1, first_line=after + 1,
                      last_line=after + count, diff=_bounded_diff(content, updated, path))
