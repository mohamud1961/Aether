"""Intent-bound actions: every action tool takes the model's own reason and expected result.

Evidence (228 traced GLM runs, 2026-10-21): 56% of actions had no reasoning before them. In base runs the share
grew over the run (0.59 at turns 6-15, 0.77 after turn 40) while runs that kept replaying their reasoning held at
~0.35: the history shows the model a past self that acts without thinking, and it carries on that way. Pruning the
reasoning (needed for context size) removes why each step was taken; this keeps a one-line why and expected result
in the call itself, in the model's own words, directly before the result it gets back. Nothing is echoed or checked
by the harness.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

INTENT_TOOLS = ("terminal", "python", "read_file", "write_file", "edit_file", "view_image")
INTENT = {
    "type": "string",
    "description": "Why you are taking this step and what you expect it to show or change, in one or two "
    "sentences.",
}


def with_intent(specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The same tool list with a required ``intent`` argument on every action tool."""
    out = []
    for spec in specs:
        fn = spec["function"]
        if fn["name"] in INTENT_TOOLS:
            spec = deepcopy(spec)
            params = spec["function"]["parameters"]
            params["properties"] = {"intent": INTENT, **params["properties"]}
            params["required"] = ["intent", *params.get("required", [])]
        out.append(spec)
    return out
