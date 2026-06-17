"""Compatibility alias for runner.substrate.eval_substrate_execution."""

from __future__ import annotations

import sys as _sys

from runner.substrate.eval_substrate_execution import *  # noqa: F401,F403
import runner.substrate.eval_substrate_execution as _canonical

_sys.modules[__name__] = _canonical
