"""Compatibility alias for harness.aether2.runtime.tpm_pacer."""

from __future__ import annotations

import sys as _sys

from harness.aether2.runtime.tpm_pacer import *  # noqa: F401,F403
import harness.aether2.runtime.tpm_pacer as _canonical

_sys.modules[__name__] = _canonical
