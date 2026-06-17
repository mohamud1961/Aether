"""Compatibility alias for runner.substrate.eval_batch_runner."""

from __future__ import annotations

import sys as _sys

from runner.substrate.eval_batch_runner import *  # noqa: F401,F403
import runner.substrate.eval_batch_runner as _canonical

_sys.modules[__name__] = _canonical
