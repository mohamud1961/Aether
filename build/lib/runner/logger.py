"""Compatibility alias for runner.kernel.logger."""

from __future__ import annotations

import sys as _sys

from runner.kernel.logger import *  # noqa: F401,F403
import runner.kernel.logger as _canonical

_sys.modules[__name__] = _canonical
