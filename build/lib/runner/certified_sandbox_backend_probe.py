"""Compatibility alias for runner.substrate.certified_sandbox_backend_probe."""

from __future__ import annotations

import sys as _sys

from runner.substrate.certified_sandbox_backend_probe import *  # noqa: F401,F403
import runner.substrate.certified_sandbox_backend_probe as _canonical

_sys.modules[__name__] = _canonical
