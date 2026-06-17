"""Compatibility alias for harness.aether2.runtime.jobs."""

import sys as _sys

from harness.aether2.runtime.jobs import *  # noqa: F401,F403
import harness.aether2.runtime.jobs as _canonical

_sys.modules[__name__] = _canonical
