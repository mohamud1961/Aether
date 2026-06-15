"""Path-normalized tool surface with no-call attribution repair guard."""

from __future__ import annotations

from typing import Any

from .result_attribution_guard_common import NO_CALL_GUARD, execute_guarded_tool_call, get_tools


def execute_tool_call(tool_call: dict[str, Any], sandbox: Any) -> dict[str, Any]:
    return execute_guarded_tool_call(tool_call, sandbox, mode=NO_CALL_GUARD)
