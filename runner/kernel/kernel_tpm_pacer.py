"""Compatibility alias for harness.aether2.runtime.tpm_pacer.

Moved into the self-contained ``harness`` package during the public
restructure; this shim preserves the ``runner.kernel_tpm_pacer`` import path.
"""

from __future__ import annotations

import sys as _sys

from harness.aether2.runtime.tpm_pacer import *  # noqa: F401,F403
import harness.aether2.runtime.tpm_pacer as _canonical

_sys.modules[__name__] = _canonical
