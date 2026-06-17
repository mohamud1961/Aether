"""Compatibility alias for harness.aether2.runtime.metrics."""

import sys as _sys

from harness.aether2.runtime.metrics import *  # noqa: F401,F403
import harness.aether2.runtime.metrics as _canonical

_sys.modules[__name__] = _canonical
