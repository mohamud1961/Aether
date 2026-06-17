"""Compatibility alias for runner.substrate.azure_openai_env."""

from __future__ import annotations

import sys as _sys

from runner.substrate.azure_openai_env import *  # noqa: F401,F403
import runner.substrate.azure_openai_env as _canonical

_sys.modules[__name__] = _canonical
