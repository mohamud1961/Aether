"""Compatibility alias for eval_suite.adapters.acebench."""

from __future__ import annotations

import sys as _sys

from eval_suite.adapters.acebench import *  # noqa: F401,F403
import eval_suite.adapters.acebench as _canonical

_sys.modules[__name__] = _canonical
