"""Compatibility alias for harness.aether2.runtime.model_routes.

The provider model-client backend moved into the self-contained ``harness``
package. This shim keeps the historical ``runner.model_client`` import path
working during the public restructure; it is removed when ``runner`` is retired.
"""

from __future__ import annotations

import sys as _sys

from harness.aether2.runtime.model_routes import *  # noqa: F401,F403
import harness.aether2.runtime.model_routes as _canonical

_sys.modules[__name__] = _canonical
