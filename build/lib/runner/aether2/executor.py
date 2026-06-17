"""Compatibility alias for harness.aether2.runtime.executor."""

import sys as _sys

from harness.aether2.runtime.executor import *  # noqa: F401,F403
import harness.aether2.runtime.executor as _canonical

_sys.modules[__name__] = _canonical
