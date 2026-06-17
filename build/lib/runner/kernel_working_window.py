"""Compatibility alias for runner.kernel.kernel_working_window."""

from __future__ import annotations

import sys as _sys

from runner.kernel.kernel_working_window import *  # noqa: F401,F403
import runner.kernel.kernel_working_window as _canonical

_sys.modules[__name__] = _canonical
