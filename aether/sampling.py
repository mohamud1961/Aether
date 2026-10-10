"""Opt-in arm: solver sampling parameters.

Control sends temperature 0.0 and no ``top_p`` (greedy decoding). Greedy decoding reproduces an identical
malformed call on every retry and is a suspected cause of think/act repetition runaways. ``t1_v1`` sends
temperature 1.0 and top_p 0.95 on every solver request. Only the solver callable is affected: the
compactor, claim-ledger card and verifier callables keep the control request bytes.
"""
from __future__ import annotations

import argparse
from typing import Any, Mapping

CONTROL = "control"
T1_V1 = "t1_v1"
SAMPLING_ENV = "AETHER_G4_SAMPLING"
SAMPLING_PARAMS: dict[str, dict[str, float]] = {T1_V1: {"temperature": 1.0, "top_p": 0.95}}
SUPPORTED_SAMPLING_MODES = frozenset({CONTROL, T1_V1})


class SamplingModeError(ValueError):
    """An unknown sampling mode was supplied."""


def resolve_sampling_mode(value: str | None = None, *, environ: Mapping[str, str] | None = None) -> str:
    env = environ or {}
    selected = str(value if value is not None else env.get(SAMPLING_ENV, CONTROL)).strip()
    if selected not in SUPPORTED_SAMPLING_MODES:
        raise SamplingModeError(f"unknown sampling mode: {selected!r}")
    return selected


def sampling_kwargs(mode: str) -> dict[str, float]:
    """ChatModel constructor kwargs for ``mode``; empty for control so its request bytes are unchanged."""
    return dict(SAMPLING_PARAMS.get(resolve_sampling_mode(mode), {}))


def add_sampling_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--sampling", choices=sorted(SUPPORTED_SAMPLING_MODES), default=CONTROL,
        help="solver sampling: t1_v1 = temperature 1.0 and top_p 0.95 on every solver request (opt-in)",
    )


def build_sampling_launch_binding(mode: str | None) -> dict[str, Any]:
    selected = resolve_sampling_mode(mode)
    manifest: dict[str, Any] = {"sampling": selected}
    if selected != CONTROL:
        manifest["sampling_config"] = dict(SAMPLING_PARAMS[selected])
    return {"sampling": selected, "env": {SAMPLING_ENV: selected}, "manifest": manifest}
