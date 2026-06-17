"""Compatibility alias for harness.aether2.runtime.escalation."""

import sys as _sys

from harness.aether2.runtime.escalation import *  # noqa: F401,F403
import harness.aether2.runtime.escalation as _canonical

_sys.modules[__name__] = _canonical
