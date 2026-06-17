"""Compatibility alias for harness.aether2.runtime.prompts."""

import sys as _sys

from harness.aether2.runtime.prompts import *  # noqa: F401,F403
import harness.aether2.runtime.prompts as _canonical

_sys.modules[__name__] = _canonical
