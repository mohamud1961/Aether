"""Compatibility alias for harness.aether2.runtime.cleanup_accounting."""

import sys as _sys

from harness.aether2.runtime.cleanup_accounting import *  # noqa: F401,F403
import harness.aether2.runtime.cleanup_accounting as _canonical

_sys.modules[__name__] = _canonical
