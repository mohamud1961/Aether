"""Compatibility alias for runner.substrate.experiment_contracts."""

from __future__ import annotations

import sys as _sys

from runner.substrate.experiment_contracts import *  # noqa: F401,F403
import runner.substrate.experiment_contracts as _canonical

_sys.modules[__name__] = _canonical
