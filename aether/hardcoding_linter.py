from __future__ import annotations

from pathlib import Path

from .benchifying_linter import BenchifyingLinter, LinterViolation


class hardcodingLinter(BenchifyingLinter):
    """Backward-compatible alias for the anti-hardcoding contract tests."""

    def __init__(self, harness_root: Path):
        super().__init__(harness_root)


__all__ = ["hardcodingLinter", "BenchifyingLinter", "LinterViolation"]
