"""Compatibility alias for harness.aether2.runtime.compactor."""

import sys as _sys

from harness.aether2.runtime.compactor import *  # noqa: F401,F403
import harness.aether2.runtime.compactor as _canonical

_sys.modules[__name__] = _canonical
