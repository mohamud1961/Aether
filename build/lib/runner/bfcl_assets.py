"""Compatibility alias for eval_suite.adapters.bfcl_assets."""

from __future__ import annotations

import sys as _sys

from eval_suite.adapters.bfcl_assets import *  # noqa: F401,F403
import eval_suite.adapters.bfcl_assets as _canonical

_sys.modules[__name__] = _canonical
