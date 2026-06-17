"""Compatibility alias for runner.substrate.atomic_eval_diagnostics."""

from __future__ import annotations

import sys as _sys

from runner.substrate.atomic_eval_diagnostics import *  # noqa: F401,F403
import runner.substrate.atomic_eval_diagnostics as _canonical

_sys.modules[__name__] = _canonical
