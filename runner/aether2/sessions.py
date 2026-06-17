"""Compatibility alias for harness.aether2.runtime.sessions."""

import sys as _sys

from harness.aether2.runtime.sessions import *  # noqa: F401,F403
import harness.aether2.runtime.sessions as _canonical

_sys.modules[__name__] = _canonical
