"""Opt-in tool shapes from the 18 Nov Core-vs-Codex study (research/codex_gap_20261117/FINDINGS.md).

AETHER_CORE_MULTI_EDIT=on: edit_file also takes ``edits``, a list of replacements applied in order to one file in one
call, all or nothing. G15 biped: 48 single-replacement edit_file calls on one file (median 3.5 new lines, streaks of
up to 7 with nothing run between); Codex passes made 5-11 apply_patch calls of ~80-150 changed lines.

AETHER_CORE_WAIT_CAP=30: a terminal command or Python cell blocks a call for at most 30 s; the work keeps running and
the model decides whether to wait again or interrupt it. Codex's command tool returns within 10-30 s (its model then
polls or kills: 0-8 kills a run); G15 layout2 Core spent 41 min inside calls of 30 s or more (wait_s 300 on 38 calls,
1 interrupt).
"""

from __future__ import annotations

import copy
from typing import Any

EDITS_SCHEMA = {
    "type": "array",
    "description": "Several replacements in this one file, applied in order, each to the text the previous one left; "
    "if any old_str is missing or ambiguous nothing is written. Use instead of old_str/new_str.",
    "items": {
        "type": "object",
        "properties": {
            "old_str": {"type": "string"},
            "new_str": {"type": "string"},
            "replace_all": {"type": "boolean"},
        },
        "required": ["old_str", "new_str"],
    },
}


def multi_edit(spec: dict[str, Any]) -> dict[str, Any]:
    """edit_file with an ``edits`` list; old_str/new_str stay for a single replacement."""
    out = copy.deepcopy(spec)
    fn = out["function"]
    fn["description"] += " To change several places in one file, pass edits (one call, all or nothing)."
    fn["parameters"]["properties"]["edits"] = EDITS_SCHEMA
    fn["parameters"]["required"] = ["path"]
    return out


def capped(spec: dict[str, Any], cap_s: float) -> dict[str, Any]:
    """A terminal/python spec whose wait_s says the cap: the call returns by then and the work keeps running."""
    out = copy.deepcopy(spec)
    props = out["function"]["parameters"]["properties"]
    if "wait_s" in props:
        props["wait_s"]["description"] = (
            f"Max seconds this call waits (at most {cap_s:.0f}). Work still running then keeps running: call again "
            "to keep waiting, or interrupt it.")
    return out


def apply(specs: list[dict[str, Any]], *, multi: bool, cap_s: float) -> list[dict[str, Any]]:
    out = []
    for spec in specs:
        name = spec.get("function", {}).get("name")
        if multi and name == "edit_file":
            spec = multi_edit(spec)
        if cap_s and name in ("terminal", "python"):
            spec = capped(spec, cap_s)
        out.append(spec)
    return out


def wait(config: Any, wait_s: float) -> float:
    """The blocking window for one call: the model's wait_s, at most the cap when AETHER_CORE_WAIT_CAP is set."""
    cap = float(getattr(config, "wait_cap_s", 0.0) or 0.0)
    return min(wait_s, cap) if cap else wait_s
