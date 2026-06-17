"""Compatibility alias for eval_suite.adapters.contextbench_native."""

from __future__ import annotations

import sys as _sys

from eval_suite.adapters.contextbench_native import *  # noqa: F401,F403
import eval_suite.adapters.contextbench_native as _canonical

_sys.modules[__name__] = _canonical
