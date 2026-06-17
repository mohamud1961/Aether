"""Compatibility alias for runner.substrate.eval_substrate_scoreboard."""

from __future__ import annotations

import sys as _sys

from runner.substrate.eval_substrate_scoreboard import *  # noqa: F401,F403
import runner.substrate.eval_substrate_scoreboard as _canonical

_sys.modules[__name__] = _canonical
