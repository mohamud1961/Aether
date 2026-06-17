"""Compatibility alias for harness.aether2.runtime.verify."""

import sys as _sys

from harness.aether2.runtime.verify import *  # noqa: F401,F403
import harness.aether2.runtime.verify as _canonical

_sys.modules[__name__] = _canonical
