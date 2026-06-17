"""Compatibility alias for runner.substrate.certified_sandbox."""

from __future__ import annotations

import sys as _sys

from runner.substrate.certified_sandbox import *  # noqa: F401,F403
import runner.substrate.certified_sandbox as _canonical

_sys.modules[__name__] = _canonical
