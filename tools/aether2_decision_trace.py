#!/usr/bin/env python3
"""Compatibility wrapper for the public decision-trace module."""

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from harness.aether2.traces import decision_trace as _impl
from harness.aether2.traces.decision_trace import *  # noqa: F401,F403
from harness.aether2.traces.decision_trace import (
    build_and_write_bundle,
    build_parser,
    collect_decision_trace_bundle,
    main,
    render_summary,
    summarize_text,
)

__all__ = list(_impl.__all__)


if __name__ == "__main__":  # pragma: no cover - CLI wrapper
    raise SystemExit(main())
