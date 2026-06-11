"""Path-normalized tool surface with ignored-result-id repair guard."""

from __future__ import annotations

from typing import Any

from .result_attribution_guard_common import IGNORED_IDS_GUARD, execute_guarded_tool_call, get_tools


def execute_tool_call(tool_call: dict[str, Any], sandbox: Any) -> dict[str, Any]:
    return execute_guarded_tool_call(tool_call, sandbox, mode=IGNORED_IDS_GUARD)
