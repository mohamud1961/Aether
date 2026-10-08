"""Opt-in arm that makes the real agent deadline visible to the Solver as budget facts.

Harbor kills the agent at the task's ``[agent] timeout_sec`` but does not hand that value to
the agent. The launcher reads it from the pinned task.toml and passes it through
``AETHER_AGENT_DEADLINE_SEC``; under ``visible_v1`` the context packet's existing
``budgets.run_timeout_sec`` / ``remaining_run_sec`` / ``wall_clock_authority`` carry it.
Nothing else changes: no nudge, no forced finish, no added text, no enforcement.
"""
from __future__ import annotations

import argparse
import math
from typing import Any, Mapping

CONTROL = "control"
VISIBLE_V1 = "visible_v1"
SUPPORTED_DEADLINE_VISIBILITY_MODES = frozenset({CONTROL, VISIBLE_V1})
DEADLINE_VISIBILITY_ENV = "AETHER_G4_DEADLINE_VISIBILITY"
AGENT_DEADLINE_SEC_ENV = "AETHER_AGENT_DEADLINE_SEC"
# The model aims to finish this long before Harbor's hard kill.
SAFETY_MARGIN_SEC = 60.0
WALL_CLOCK_AUTHORITY = "agent_timeout"


class DeadlineVisibilityError(ValueError):
    """An unknown mode or an unusable deadline was supplied."""


def resolve_deadline_visibility_mode(
    value: str | None = None, *, environ: Mapping[str, str] | None = None,
) -> str:
    env = environ or {}
    selected = str(value if value is not None else env.get(DEADLINE_VISIBILITY_ENV, CONTROL)).strip()
    if selected not in SUPPORTED_DEADLINE_VISIBILITY_MODES:
        raise DeadlineVisibilityError(f"unknown deadline-visibility mode: {selected!r}")
    return selected


def parse_deadline_sec(raw: Any) -> float:
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise DeadlineVisibilityError(f"agent deadline is not a number: {raw!r}") from exc
    if not math.isfinite(value) or value <= 0:
        raise DeadlineVisibilityError(f"agent deadline must be a positive finite number: {raw!r}")
    return value


def agent_deadline_from_env(environ: Mapping[str, str]) -> float:
    """Required under visible_v1; a missing deadline is a hard error, never a silent control."""
    raw = environ.get(AGENT_DEADLINE_SEC_ENV)
    if raw is None or not str(raw).strip():
        raise DeadlineVisibilityError(f"{DEADLINE_VISIBILITY_ENV}={VISIBLE_V1} requires {AGENT_DEADLINE_SEC_ENV}")
    return parse_deadline_sec(raw)


def visible_clock_fields(deadline_sec: float, elapsed_sec: float) -> dict[str, Any]:
    """The factual budget fields the packet already carries, computed from the agent-start clock."""
    return {
        "run_timeout_sec": float(deadline_sec),
        "remaining_run_sec": round(max(0.0, float(deadline_sec) - SAFETY_MARGIN_SEC - elapsed_sec), 3),
        "wall_clock_authority": WALL_CLOCK_AUTHORITY,
    }


def add_deadline_visibility_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--deadline-visibility", choices=sorted(SUPPORTED_DEADLINE_VISIBILITY_MODES), default=CONTROL,
        help="show the real agent timeout in the Solver's budget fields (opt-in)",
    )


def build_deadline_launch_binding(mode: str | None, *, agent_timeout_sec: float | None) -> dict[str, Any]:
    """Validate, then return child env and manifest identity. Control contributes nothing."""
    selected = resolve_deadline_visibility_mode(mode)
    env = {DEADLINE_VISIBILITY_ENV: selected}
    manifest: dict[str, Any] = {"deadline_visibility": selected}
    if selected == VISIBLE_V1:
        if agent_timeout_sec is None:
            raise DeadlineVisibilityError(f"{VISIBLE_V1} needs the task's pinned agent timeout; none was found")
        deadline = parse_deadline_sec(agent_timeout_sec)
        env[AGENT_DEADLINE_SEC_ENV] = repr(deadline)
        manifest["deadline_visibility_config"] = {
            "agent_deadline_sec": deadline,
            "safety_margin_sec": SAFETY_MARGIN_SEC,
            "wall_clock_authority": WALL_CLOCK_AUTHORITY,
            "source": "pinned task.toml [agent] timeout_sec",
        }
    return {"deadline_visibility": selected, "env": env, "manifest": manifest}
