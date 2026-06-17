"""Compatibility alias for runner.kernel.action_bus."""

from __future__ import annotations

import sys as _sys

from runner.kernel.action_bus import *  # noqa: F401,F403
import runner.kernel.action_bus as _canonical

_sys.modules[__name__] = _canonical
