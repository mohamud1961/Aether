"""Compatibility alias for harness.aether2.runtime.model_client."""

import sys as _sys

from harness.aether2.runtime.model_client import *  # noqa: F401,F403
import harness.aether2.runtime.model_client as _canonical

_sys.modules[__name__] = _canonical
