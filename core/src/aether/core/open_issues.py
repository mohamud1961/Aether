"""The model's own account of what is still open, asked for at finish (AETHER_CORE_OPEN_ISSUES=on).

x0 audits (2026-10-28): five of sixteen failed Luna runs finished while their own words named a gap, with time
left (an output that "does not match" the task's stated value with 440 s unused, an installer "should be complete"
but never run, a visual reading contradicted by the string written). The finish tool takes ``open_issues``: the
requirements the model has not met or not checked. Listing any with time left returns the finish once, with the
list and the time remaining; the next finish ends the run whatever it lists. Core reads only what the model wrote
in the call; nothing is inferred from its reasoning, and an empty list ends the run at once."""

from __future__ import annotations

import copy
from typing import Any

OPEN_ISSUES_ENV = "AETHER_CORE_OPEN_ISSUES"
MIN_LEFT_S, MIN_LEFT_SHARE = 60.0, 0.10
FIELD = {
    "type": "array",
    "items": {"type": "string"},
    "description": "Every requirement of the task you have not met, or have not checked by observing the result "
    "(one item each, with why). An empty list means everything is met and checked.",
}


def with_field(tool_defs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The tool list with ``open_issues`` required on finish."""
    out = copy.deepcopy(tool_defs)
    for spec in out:
        fn = spec["function"]
        if fn["name"] == "finish" and "summary" in fn["parameters"]["properties"]:
            fn["parameters"]["properties"]["open_issues"] = FIELD
            fn["parameters"]["required"] = [*fn["parameters"]["required"], "open_issues"]
    return out


def issues(args: dict[str, Any]) -> list[str]:
    raw = args.get("open_issues") or []
    return [str(x).strip() for x in raw if str(x).strip()] if isinstance(raw, list) else [str(raw)]


def hold(args: dict[str, Any], remaining_s: float, timeout_s: float) -> str | None:
    """The text that returns the finish, or None when it takes effect."""
    open_ = issues(args)
    if not open_ or remaining_s < max(MIN_LEFT_S, MIN_LEFT_SHARE * timeout_s):
        return None
    listed = "\n".join(f"- {x}" for x in open_)
    return (
        f"[finish not taken yet: you listed {len(open_)} open issue(s) and {remaining_s:.0f}s remain]\n{listed}\n"
        "Resolve or check them now. Call finish again when done; the next finish ends the task whatever it lists."
    )
