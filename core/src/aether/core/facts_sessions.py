"""Render receipt-scoped session facts without claiming live state."""

from __future__ import annotations

import json
from typing import Any


def terminal_cwd_note(name: str, step: Any, session: dict[str, Any]) -> str:
    cwd = session.get("last_observed_cwd")
    if not isinstance(cwd, str) or len(cwd) > 256:
        return ""
    receipt = session.get("cwd_receipt_seq")
    source = (f"terminal completion receipt {receipt}" if type(receipt) is int
              else "an earlier terminal completion")
    note = (f"\nTerminal {json.dumps(name)} last observed cwd ({source}, "
            f"reported at Core step {step}): {json.dumps(cwd)}")
    if session.get("foreground") == "completion_not_observed":
        note += "; current cwd is unknown until a later observation"
    return note + "."


def python_cwd_note(session: dict[str, Any]) -> str:
    cwd, cell = session.get("last_observed_cwd"), session.get("cwd_receipt_cell")
    if not isinstance(cwd, str) or type(cell) is not int:
        return "\nPython cwd: unmeasured."
    note = f"\nPython last observed cwd (cell {cell} completion receipt): {json.dumps(cwd)}"
    if session.get("foreground") != "idle_at_last_observation":
        note += "; current cwd is unknown until a later observation"
    return note + "."
