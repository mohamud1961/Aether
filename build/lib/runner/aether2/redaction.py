"""Compatibility alias for harness.aether2.traces.redaction."""

import sys as _sys

from harness.aether2.traces.redaction import *  # noqa: F401,F403
import harness.aether2.traces.redaction as _canonical

_sys.modules[__name__] = _canonical
