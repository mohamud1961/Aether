"""Fail-closed selector and launch identity for the M-TREE context mode."""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any, Mapping

from ..context_file.config import (
    CONTEXT_FILE_MODES, CTX_BUDGET_ENV, FORCED_TRIM_TARGET_FRACTION,
    OVER_BUDGET_TRIM_AFTER_TURNS, validate_budget,
)

CONTROL = "control"
M_TREE_V1 = "m_tree_v1"
# One selector, one context mechanism: M-TREE and the model-edited context file
# are alternatives, never combined.
SUPPORTED_CONTEXT_MODES = frozenset({CONTROL, M_TREE_V1, *CONTEXT_FILE_MODES})
CONTEXT_MODE_ENV = "AETHER_G4_CONTEXT_MODE"
M_TREE_EVIDENCE_ROOT_ENV = "AETHER_M_TREE_EVIDENCE_ROOT"
COMPACTOR_LIMITER_PATH_ENV = "AETHER_M_TREE_COMPACTOR_LIMITER_PATH"
COMPACTOR_DEPLOYMENT_ENV = "AETHER_M_TREE_COMPACTOR_DEPLOYMENT"
COMPACTOR_DEPLOYMENT = "FW-GLM-5.3-Flash-par-2"
COMPACTOR_ROUTE_KEY = "m_tree_compactor_route"
FORBIDDEN_TRANSPORTS = frozenset({"PTRA", "PTR1", "PTNR"})


class ContextModeError(ValueError):
    """An unknown or conflicting context mode was requested."""


def resolve_context_mode(value: str | None = None, *, environ: Mapping[str, str] | None = None) -> str:
    env = environ or {}
    selected = str(value if value is not None else env.get(CONTEXT_MODE_ENV, CONTROL)).strip()
    if selected not in SUPPORTED_CONTEXT_MODES:
        raise ContextModeError(f"unknown context mode: {selected!r}")
    return selected


def validate_context_launch(
    mode: str | None,
    *,
    capacity_recovery: str = CONTROL,
    transport: str = CONTROL,
) -> str:
    """Validate all inert-arm conflicts before a caller creates evidence paths."""
    selected = resolve_context_mode(mode)
    if selected == CONTROL:
        return selected
    if str(capacity_recovery).strip().lower() != CONTROL:
        raise ContextModeError(f"{selected} conflicts with capacity recovery")
    normalized = re.sub(r"[^A-Z0-9]", "", str(transport).upper())
    if normalized in FORBIDDEN_TRANSPORTS:
        raise ContextModeError(f"{selected} conflicts with transport {transport!r}")
    return selected


def add_context_mode_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--context-mode", choices=sorted(SUPPORTED_CONTEXT_MODES), default=CONTROL,
        help="task-local context policy",
    )
    parser.add_argument(
        "--context-budget-bytes", type=int, default=None,
        help="context_file_v1* only: override the selector's context-file budget (bytes)",
    )


def runtime_identity(
    mode: str, *, compactor_limiter_path: str | Path | None = None,
    ctx_budget_bytes: int | None = None,
) -> dict[str, Any]:
    selected = resolve_context_mode(mode)
    identity: dict[str, Any] = {"context_mode": selected}
    if selected in CONTEXT_FILE_MODES:
        budget = validate_budget(CONTEXT_FILE_MODES[selected] if ctx_budget_bytes is None else ctx_budget_bytes)
        identity["context_file"] = {
            "budget_bytes": budget, "budget_env": CTX_BUDGET_ENV,
            "forced_trim_after_turns": OVER_BUDGET_TRIM_AFTER_TURNS,
            "forced_trim_target_fraction": FORCED_TRIM_TARGET_FRACTION,
        }
    if selected == M_TREE_V1:
        identity[COMPACTOR_ROUTE_KEY] = {
            "deployment": COMPACTOR_DEPLOYMENT,
            "limiter_path": str(compactor_limiter_path) if compactor_limiter_path else None,
        }
    return identity


def prepare_evidence_directory(
    evidence_dir: str | Path,
    *,
    mode: str | None,
    capacity_recovery: str = CONTROL,
    transport: str = CONTROL,
) -> tuple[str, Path]:
    """Refuse conflicts before the evidence directory is created."""
    selected = validate_context_launch(
        mode, capacity_recovery=capacity_recovery, transport=transport
    )
    path = Path(evidence_dir)
    path.mkdir(parents=True, exist_ok=False)
    return selected, path
