"""Compatibility alias for harness.aether2.control.loop."""

import sys as _sys

from harness.aether2.control.loop import *  # noqa: F401,F403
import harness.aether2.control.loop as _canonical

_sys.modules[__name__] = _canonical
