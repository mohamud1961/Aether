"""Compatibility alias for runner.kernel.kernel_artifacts."""

from __future__ import annotations

import sys as _sys

from runner.kernel.kernel_artifacts import *  # noqa: F401,F403
import runner.kernel.kernel_artifacts as _canonical

_sys.modules[__name__] = _canonical
