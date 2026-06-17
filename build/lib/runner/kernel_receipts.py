"""Compatibility alias for runner.kernel.kernel_receipts."""

from __future__ import annotations

import sys as _sys

from runner.kernel.kernel_receipts import *  # noqa: F401,F403
import runner.kernel.kernel_receipts as _canonical

_sys.modules[__name__] = _canonical
