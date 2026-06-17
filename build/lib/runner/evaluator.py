"""Compatibility alias for runner.substrate.evaluator."""

from __future__ import annotations

import sys as _sys

from runner.substrate.evaluator import *  # noqa: F401,F403
import runner.substrate.evaluator as _canonical

_sys.modules[__name__] = _canonical
