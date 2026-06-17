"""Compatibility alias for runner.kernel.kernel_state."""

from __future__ import annotations

import sys as _sys

from runner.kernel.kernel_state import *  # noqa: F401,F403
import runner.kernel.kernel_state as _canonical

_sys.modules[__name__] = _canonical
