"""Compatibility alias for harness.aether2.runtime.action_bus."""

import sys as _sys

from harness.aether2.runtime.action_bus import *  # noqa: F401,F403
import harness.aether2.runtime.action_bus as _canonical

_sys.modules[__name__] = _canonical
