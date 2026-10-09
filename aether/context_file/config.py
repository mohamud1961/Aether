"""Selector values and budget resolution for the context-file arm.

The mode names live in the shared ``AETHER_G4_CONTEXT_MODE`` selector (see
``aether.context_tree.config``) so that M-TREE and the context file are
mutually exclusive by construction: one selector value, one mechanism.
"""
from __future__ import annotations

from typing import Mapping

CONTEXT_FILE_V1 = "context_file_v1"
CONTEXT_FILE_BUDGET_DEFAULT = 192_000
CONTEXT_FILE_MODES: dict[str, int] = {
    CONTEXT_FILE_V1: CONTEXT_FILE_BUDGET_DEFAULT,
    "context_file_v1_96k": 96_000,
    "context_file_v1_128k": 128_000,
    "context_file_v1_192k": 192_000,
}
# Launcher-set override of the selector's budget (bytes of UTF-8 file text).
CTX_BUDGET_ENV = "AETHER_MANAGED_CONTEXT_CTX_BUDGET_BYTES"
MIN_BUDGET_BYTES = 8_000
MAX_BUDGET_BYTES = 1_000_000
OVER_BUDGET_TRIM_AFTER_TURNS = 3
FORCED_TRIM_TARGET_FRACTION = 0.8
MANAGED_CONTEXT_OVERFLOW_CODE = "managed_context_context_overflow"


class ContextFileConfigError(ValueError):
    """The context-file budget or selector was invalid."""


def is_context_file_mode(mode: str | None) -> bool:
    return str(mode or "") in CONTEXT_FILE_MODES


def validate_budget(value: int) -> int:
    budget = int(value)
    if not MIN_BUDGET_BYTES <= budget <= MAX_BUDGET_BYTES:
        raise ContextFileConfigError(
            f"context file budget must be within {MIN_BUDGET_BYTES}..{MAX_BUDGET_BYTES} bytes, got {budget}"
        )
    return budget


def resolve_budget(mode: str, *, environ: Mapping[str, str] | None = None) -> int:
    """Budget for ``mode``: the launcher-set env value wins; invalid values fail closed."""
    if not is_context_file_mode(mode):
        raise ContextFileConfigError(f"not a context-file mode: {mode!r}")
    raw = str((environ or {}).get(CTX_BUDGET_ENV, "") or "").strip()
    if not raw:
        return CONTEXT_FILE_MODES[mode]
    try:
        return validate_budget(int(raw))
    except ValueError as exc:
        raise ContextFileConfigError(f"{CTX_BUDGET_ENV} is invalid: {exc}") from exc
