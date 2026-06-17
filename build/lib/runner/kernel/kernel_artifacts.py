"""Compatibility alias for harness.aether2.traces.kernel_artifacts.

The artifact-record support module moved into the self-contained ``harness``
package during the public restructure; this shim preserves the
``runner.kernel_artifacts`` import path during the transition.
"""

from __future__ import annotations

import sys as _sys

from harness.aether2.traces.kernel_artifacts import *  # noqa: F401,F403
import harness.aether2.traces.kernel_artifacts as _canonical

_sys.modules[__name__] = _canonical
