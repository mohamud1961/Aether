"""Compatibility alias for harness.aether2.runtime.context."""

import sys as _sys

from harness.aether2.runtime.context import *  # noqa: F401,F403
import harness.aether2.runtime.context as _canonical

_sys.modules[__name__] = _canonical
