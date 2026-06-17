"""Compatibility alias for eval_suite.adapters.final_harness_eval_suite_adapter."""

from __future__ import annotations

import sys as _sys

from eval_suite.adapters.final_harness_eval_suite_adapter import *  # noqa: F401,F403
import eval_suite.adapters.final_harness_eval_suite_adapter as _canonical

_sys.modules[__name__] = _canonical
