"""Compatibility alias for runner.kernel.evidence_kernel."""

from __future__ import annotations

import sys as _sys

from runner.kernel.evidence_kernel import *  # noqa: F401,F403
import runner.kernel.evidence_kernel as _canonical

_sys.modules[__name__] = _canonical
