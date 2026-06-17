"""Compatibility alias for runner.kernel.agent."""

from __future__ import annotations

import sys as _sys

from runner.kernel.agent import *  # noqa: F401,F403
import runner.kernel.agent as _canonical

_sys.modules[__name__] = _canonical
