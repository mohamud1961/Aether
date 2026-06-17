"""Compatibility alias for harness.aether2.traces.mirror."""

import sys as _sys

from harness.aether2.traces.mirror import *  # noqa: F401,F403
import harness.aether2.traces.mirror as _canonical

_sys.modules[__name__] = _canonical
