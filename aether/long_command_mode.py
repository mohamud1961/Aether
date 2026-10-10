"""Opt-in execution policy for commands that outlive their tool timeout."""

from __future__ import annotations

import os

LONG_COMMAND_MODE_ENV = "AETHER_LONG_COMMAND_MODE"
LONG_COMMAND_CONTROL = "control"
LONG_COMMAND_BACKGROUND_V1 = "background_v1"
LONG_COMMAND_MODES = frozenset({LONG_COMMAND_CONTROL, LONG_COMMAND_BACKGROUND_V1})


def selected_long_command_mode() -> str:
    mode = str(os.environ.get(LONG_COMMAND_MODE_ENV, LONG_COMMAND_CONTROL) or LONG_COMMAND_CONTROL).strip()
    if mode not in LONG_COMMAND_MODES:
        raise ValueError(f"unsupported long-command mode: {mode!r}")
    return mode
