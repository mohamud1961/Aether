"""Compatibility alias for harness.aether2.runtime.orientation."""

import sys as _sys

from harness.aether2.runtime.orientation import *  # noqa: F401,F403
import harness.aether2.runtime.orientation as _canonical

_sys.modules[__name__] = _canonical
