"""Compatibility alias for eval_suite.adapters.letta."""

from __future__ import annotations

import sys as _sys

from eval_suite.adapters.letta import *  # noqa: F401,F403
import eval_suite.adapters.letta as _canonical

_sys.modules[__name__] = _canonical
