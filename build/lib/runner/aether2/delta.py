"""Compatibility alias for harness.aether2.traces.delta."""

import sys as _sys

from harness.aether2.traces.delta import *  # noqa: F401,F403
import harness.aether2.traces.delta as _canonical

_sys.modules[__name__] = _canonical
