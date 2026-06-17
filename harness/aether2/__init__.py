"""Canonical Aether-2 namespace backed by the active implementation tree."""

from __future__ import annotations

from pathlib import Path as _Path

_AETHER_ROOT = _Path(__file__).resolve().parents[2] / "aether"

if not _AETHER_ROOT.exists():
    raise ImportError(f"active Aether-2 implementation root does not exist: {_AETHER_ROOT}")

__path__ = [str(_AETHER_ROOT)]

_source_path = _AETHER_ROOT / "__init__.py"
exec(compile(_source_path.read_text(encoding="utf-8"), str(_source_path), "exec"), globals())

from harness.aether2.runtime import (  # noqa: E402
    HANDOFF_TEMPLATE,
    build_fact_ledger,
    build_scorecard,
    orient,
    verify_fresh_context,
)

__all__ = sorted(
    set(__all__)
    | {
        "HANDOFF_TEMPLATE",
        "build_fact_ledger",
        "build_scorecard",
        "orient",
        "verify_fresh_context",
    }
)
