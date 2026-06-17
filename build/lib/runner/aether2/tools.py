"""Compatibility alias for harness.aether2.tools.native."""

import sys as _sys

from harness.aether2.tools.native import *  # noqa: F401,F403
import harness.aether2.tools.native as _canonical

_sys.modules[__name__] = _canonical
