"""The single model-visible tool of the context-file arm, and its argument contract."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

EDIT_CONTEXT_ACTION = "edit_context"
CONTEXT_FILE_CAPABILITY = "context_file"
# While the file is over budget the model may only edit it or finish.
RESTRICTED_TOOL_NAMES = frozenset({EDIT_CONTEXT_ACTION, "finish"})
EDIT_FIELDS = frozenset({"old", "new", "replace_all_text"})

EDIT_CONTEXT_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": EDIT_CONTEXT_ACTION,
        "description": (
            "Edit your context file, the <context_file> block shown every turn. "
            "Either pass old and new to replace one exact, unique substring of the "
            "file (new may be empty to delete it), or pass replace_all_text to "
            "rewrite the whole file. Keep the file within its byte budget."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "old": {"type": "string", "minLength": 1},
                "new": {"type": "string"},
                "replace_all_text": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
}


def edit_arguments_error(arguments: Mapping[str, Any]) -> str:
    """Return a factual shape error for edit_context arguments, or the empty string."""
    keys = set(arguments)
    if keys == {"old", "new"}:
        if not isinstance(arguments["old"], str) or not arguments["old"]:
            return "edit_context old must be a non-empty string"
        if not isinstance(arguments["new"], str):
            return "edit_context new must be a string"
        return ""
    if keys == {"replace_all_text"}:
        return "" if isinstance(arguments["replace_all_text"], str) else (
            "edit_context replace_all_text must be a string"
        )
    return "edit_context takes exactly old+new or replace_all_text"


CONTEXT_FILE_MODES = frozenset({"off", "on", "restricted"})


def surface_tools(tools: tuple[dict[str, Any], ...], mode: str) -> tuple[dict[str, Any], ...]:
    """Chat-shaped tool list for a context-file scope mode (``off`` leaves it untouched)."""
    if mode == "off":
        return tools
    kept = tuple(tool for tool in tools if tool["function"].get("name") != EDIT_CONTEXT_ACTION)
    if mode == "restricted":
        kept = tuple(tool for tool in kept if tool["function"].get("name") in RESTRICTED_TOOL_NAMES)
    return (*kept, deepcopy(EDIT_CONTEXT_TOOL))
