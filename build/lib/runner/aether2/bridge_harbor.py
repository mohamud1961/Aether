"""Compatibility alias for harness.aether2.runtime.bridge_harbor."""

import sys as _sys

from harness.aether2.runtime.bridge_harbor import *  # noqa: F401,F403
import harness.aether2.runtime.bridge_harbor as _canonical

_sys.modules[__name__] = _canonical
