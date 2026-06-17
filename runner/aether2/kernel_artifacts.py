"""Compatibility alias for harness.aether2.traces.kernel_artifacts."""

import sys as _sys

from harness.aether2.traces.kernel_artifacts import *  # noqa: F401,F403
import harness.aether2.traces.kernel_artifacts as _canonical

_sys.modules[__name__] = _canonical
