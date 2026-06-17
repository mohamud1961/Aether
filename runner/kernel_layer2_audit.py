"""Compatibility alias for runner.kernel.kernel_layer2_audit."""

from __future__ import annotations

import sys as _sys

from runner.kernel.kernel_layer2_audit import *  # noqa: F401,F403
import runner.kernel.kernel_layer2_audit as _canonical

_sys.modules[__name__] = _canonical
