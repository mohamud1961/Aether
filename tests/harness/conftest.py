"""Force the deterministic suite to test this checkout's Aether source."""
from __future__ import annotations

import sys
from pathlib import Path

_BUILD_ROOT = Path(__file__).resolve().parents[2]
_build_text = str(_BUILD_ROOT)
if not sys.path or sys.path[0] != _build_text:
    sys.path.insert(0, _build_text)

import aether  # noqa: E402

_module_path = Path(aether.__file__).resolve()
if _BUILD_ROOT not in _module_path.parents:
    raise RuntimeError(
        "deterministic suite imported aether outside the active build root: "
        f"module={_module_path} expected_root={_BUILD_ROOT}"
    )
