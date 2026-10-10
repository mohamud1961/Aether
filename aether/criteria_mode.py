"""Opt-in CHALLENGER task-criteria extraction mode."""
from __future__ import annotations

import argparse
import os
from typing import Any, Mapping

CONTROL = "control"
COMPLETE_V1 = "complete_v1"
CRITERIA_MODES = (CONTROL, COMPLETE_V1)
CRITERIA_MODE_ENV = "AETHER_G4_CRITERIA_MODE"


class CriteriaModeError(ValueError):
    """An unsupported task-criteria extraction mode was selected."""


def resolve_criteria_mode(value: str | None = None, *, environ: Mapping[str, str] | None = None) -> str:
    env = os.environ if environ is None else environ
    selected = str(value if value is not None else env.get(CRITERIA_MODE_ENV, CONTROL)).strip()
    if selected not in CRITERIA_MODES:
        raise CriteriaModeError(f"criteria mode must be one of {', '.join(CRITERIA_MODES)}")
    return selected


def add_criteria_mode_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--criteria-mode", choices=CRITERIA_MODES, default=CONTROL,
        help="task criterion extraction mode (complete_v1 preserves wrapped clauses; opt-in)",
    )


def build_criteria_mode_launch_binding(value: str | None) -> dict[str, Any]:
    selected = resolve_criteria_mode(value)
    manifest = {"criteria_mode": selected} if selected != CONTROL else {}
    return {"criteria_mode": selected,
            "env": {CRITERIA_MODE_ENV: selected} if selected != CONTROL else {},
            "manifest": manifest}


def criteria_mode_runtime_identity(value: str | None = None) -> dict[str, Any]:
    selected = resolve_criteria_mode(value)
    return {"criteria_mode": selected} if selected != CONTROL else {}
