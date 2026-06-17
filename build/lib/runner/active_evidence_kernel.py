"""Compatibility alias for runner.kernel.active_evidence_kernel."""

from __future__ import annotations

import sys as _sys

from runner.kernel.active_evidence_kernel import *  # noqa: F401,F403
import runner.kernel.active_evidence_kernel as _canonical

_sys.modules[__name__] = _canonical
