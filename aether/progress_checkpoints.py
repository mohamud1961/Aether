"""Opt-in timed, advisory Solver progress checkpoints for CHALLENGER v5 runs."""
from __future__ import annotations

import argparse
from typing import Any, Mapping

CONTROL = "control"
PROGRESS_CHECKPOINTS_ENV = "AETHER_G4_PROGRESS_CHECKPOINTS"
PROGRESS_CHECKPOINTS_MODE_ENV = "AETHER_G4_PROGRESS_CHECKPOINTS_MODE"
STATE_SNAPSHOT_ENV = "AETHER_G4_STATE_SNAPSHOT"
SUCCESS_CONTRACT_ENV = "AETHER_G4_SUCCESS_CONTRACT"
FINISH_REVIEW_ENV = "AETHER_G4_FINISH_REVIEW"
V2 = "v2"
STATE_SNAPSHOT_V1 = "v1"
SUCCESS_CONTRACT_V1 = "v1"
STATE_FINISH_REVIEW = "state_v1"
BLIND_FINISH_REVIEW = "state_blind_v1"
V2_DEFAULT_FRACTIONS = (25, 50, 75, 85)
MAX_CHECKPOINTS = 4
MAX_REQUEST_BYTES = 120_000
MAX_CALLS = 4
CALL_CAP_GBP = "0.05"


class ProgressCheckpointsError(ValueError):
    """An invalid progress-checkpoint selection or dependency was supplied."""


def parse_progress_checkpoints(value: str | None) -> tuple[int, ...]:
    selected = str(value if value is not None else CONTROL).strip()
    if selected == CONTROL:
        return ()
    try:
        fractions = tuple(int(part.strip()) for part in selected.split(","))
    except ValueError as exc:
        raise ProgressCheckpointsError(f"invalid progress-checkpoints selection: {selected!r}") from exc
    if (not fractions or len(fractions) > MAX_CHECKPOINTS
            or any(f < 1 or f > 99 for f in fractions)
            or tuple(sorted(set(fractions))) != fractions):
        raise ProgressCheckpointsError(
            "progress-checkpoints must be control or up to four increasing integer percentages from 1 to 99"
        )
    return fractions


def resolve_progress_checkpoints(
    value: str | None = None, *, environ: Mapping[str, str] | None = None,
) -> tuple[int, ...]:
    env = environ or {}
    return parse_progress_checkpoints(
        value if value is not None else env.get(PROGRESS_CHECKPOINTS_ENV, CONTROL)
    )


def resolve_progress_checkpoints_mode(value: str | None = None, *,
                                      environ: Mapping[str, str] | None = None) -> str:
    env = environ or {}
    selected = str(value if value is not None else env.get(PROGRESS_CHECKPOINTS_MODE_ENV, CONTROL)).strip()
    if selected not in {CONTROL, V2}:
        raise ProgressCheckpointsError(f"unknown progress-checkpoints-mode: {selected!r}")
    return selected


def resolve_progress_checkpoint_config(*, value: str | None = None, mode: str | None = None,
                                       environ: Mapping[str, str] | None = None) -> tuple[str, tuple[int, ...]]:
    selected_mode = resolve_progress_checkpoints_mode(mode, environ=environ)
    raw = value if value is not None else (environ or {}).get(PROGRESS_CHECKPOINTS_ENV, CONTROL)
    fractions = V2_DEFAULT_FRACTIONS if selected_mode == V2 and str(raw).strip() == CONTROL else parse_progress_checkpoints(raw)
    return selected_mode, fractions


def resolve_state_snapshot_mode(value: str | None = None, *,
                                environ: Mapping[str, str] | None = None) -> str:
    selected = str(value if value is not None else (environ or {}).get(STATE_SNAPSHOT_ENV, CONTROL)).strip()
    if selected not in {CONTROL, STATE_SNAPSHOT_V1}:
        raise ProgressCheckpointsError(f"unknown state-snapshot selection: {selected!r}")
    return selected


def resolve_success_contract_mode(value: str | None = None, *,
                                  environ: Mapping[str, str] | None = None) -> str:
    selected = str(value if value is not None else (environ or {}).get(SUCCESS_CONTRACT_ENV, CONTROL)).strip()
    if selected not in {CONTROL, SUCCESS_CONTRACT_V1}:
        raise ProgressCheckpointsError(f"unknown success-contract selection: {selected!r}")
    return selected


def resolve_finish_review_mode(value: str | None = None, *,
                               environ: Mapping[str, str] | None = None) -> str:
    selected = str(value if value is not None else (environ or {}).get(FINISH_REVIEW_ENV, CONTROL)).strip()
    if selected not in {CONTROL, STATE_FINISH_REVIEW, BLIND_FINISH_REVIEW}:
        raise ProgressCheckpointsError(f"unknown finish-review selection: {selected!r}")
    return selected


def add_progress_checkpoints_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--progress-checkpoints", default=CONTROL,
        help="ask for advisory progress estimates at selected deadline percentages (requires challenger_v4 or challenger_v5 and visible deadline)",
    )
    parser.add_argument(
        "--progress-checkpoints-mode", choices=(CONTROL, V2), default=CONTROL,
        help="checkpoint request format; v2 adds asynchronous state snapshots and factual notes",
    )
    parser.add_argument("--state-snapshot", choices=(CONTROL, STATE_SNAPSHOT_V1), default=CONTROL,
                        help="capture bounded read-only workspace state at finish and run end")
    parser.add_argument("--success-contract", choices=(CONTROL, SUCCESS_CONTRACT_V1), default=CONTROL,
                        help="experimental one-time task-check capture after three actions (requires v2)")
    parser.add_argument("--finish-review", choices=(CONTROL, STATE_FINISH_REVIEW, BLIND_FINISH_REVIEW), default=CONTROL,
                        help="experimental state-aware completion review (requires challenger_v5 and state-snapshot v1)")


def build_progress_checkpoints_launch_binding(
    value: str | None, *, claim_ledger: str, deadline_visibility: str,
    mode: str = CONTROL, state_snapshot: str = CONTROL, success_contract: str = CONTROL,
    finish_review: str = CONTROL,
) -> dict[str, Any]:
    selected_mode = str(mode or CONTROL).strip()
    if selected_mode not in {CONTROL, V2}:
        raise ProgressCheckpointsError(f"unknown progress-checkpoints-mode: {selected_mode!r}")
    selected_snapshot = resolve_state_snapshot_mode(state_snapshot)
    selected_contract = resolve_success_contract_mode(success_contract)
    selected_finish = resolve_finish_review_mode(finish_review)
    if selected_mode == V2 and selected_snapshot != STATE_SNAPSHOT_V1:
        raise ProgressCheckpointsError("progress-checkpoints-mode v2 requires --state-snapshot v1")
    if selected_finish != CONTROL and (claim_ledger != "challenger_v5" or selected_snapshot != STATE_SNAPSHOT_V1):
        raise ProgressCheckpointsError("state-aware finish review requires --claim-ledger challenger_v5 and --state-snapshot v1")
    if selected_contract == SUCCESS_CONTRACT_V1 and selected_mode != V2:
        raise ProgressCheckpointsError("success-contract v1 requires --progress-checkpoints-mode v2")
    fractions = (V2_DEFAULT_FRACTIONS if selected_mode == V2 and (value is None or str(value).strip() == CONTROL)
                 else resolve_progress_checkpoints(value))
    selected = CONTROL if not fractions else ",".join(map(str, fractions))
    if fractions and claim_ledger not in ("challenger_v4", "challenger_v5"):
        raise ProgressCheckpointsError("progress checkpoints require --claim-ledger challenger_v4 or challenger_v5")
    if fractions and deadline_visibility != "visible_v1":
        raise ProgressCheckpointsError("progress checkpoints require --deadline-visibility visible_v1")
    manifest: dict[str, Any] = {"progress_checkpoints": selected}
    if selected_mode == V2:
        manifest["progress_checkpoints_mode"] = V2
    if selected_snapshot == STATE_SNAPSHOT_V1:
        manifest["state_snapshot"] = STATE_SNAPSHOT_V1
    if selected_contract == SUCCESS_CONTRACT_V1:
        manifest["success_contract"] = SUCCESS_CONTRACT_V1
    if selected_finish != CONTROL:
        manifest["finish_review"] = selected_finish
    if fractions:
        manifest["progress_checkpoints_config"] = {
            "fractions_percent": list(fractions), "max_per_run": MAX_CHECKPOINTS,
            "max_request_bytes": MAX_REQUEST_BYTES, "max_calls": MAX_CALLS,
            "call_cap_gbp": CALL_CAP_GBP, "advisory_only": True,
        }
    env = {PROGRESS_CHECKPOINTS_ENV: selected}
    if selected_mode == V2:
        env[PROGRESS_CHECKPOINTS_MODE_ENV] = V2
    if selected_snapshot == STATE_SNAPSHOT_V1:
        env[STATE_SNAPSHOT_ENV] = STATE_SNAPSHOT_V1
    if selected_contract == SUCCESS_CONTRACT_V1:
        env[SUCCESS_CONTRACT_ENV] = SUCCESS_CONTRACT_V1
    if selected_finish != CONTROL:
        env[FINISH_REVIEW_ENV] = selected_finish
    return {"progress_checkpoints": selected, "progress_checkpoints_mode": selected_mode,
            "state_snapshot": selected_snapshot, "success_contract": selected_contract,
            "finish_review": selected_finish,
            "env": env, "manifest": manifest}


def progress_checkpoints_runtime_identity(value: str | None, mode: str = CONTROL,
                                          state_snapshot: str = CONTROL,
                                          success_contract: str = CONTROL,
                                          finish_review: str = CONTROL) -> dict[str, Any]:
    selected_mode = str(mode or CONTROL).strip()
    if selected_mode not in {CONTROL, V2}:
        raise ProgressCheckpointsError(f"unknown progress-checkpoints-mode: {selected_mode!r}")
    selected_snapshot = resolve_state_snapshot_mode(state_snapshot)
    selected_contract = resolve_success_contract_mode(success_contract)
    selected_finish = resolve_finish_review_mode(finish_review)
    if selected_mode == V2 and selected_snapshot != STATE_SNAPSHOT_V1:
        raise ProgressCheckpointsError("progress-checkpoints-mode v2 requires --state-snapshot v1")
    if selected_contract == SUCCESS_CONTRACT_V1 and selected_mode != V2:
        raise ProgressCheckpointsError("success-contract v1 requires --progress-checkpoints-mode v2")
    if selected_finish != CONTROL and selected_snapshot != STATE_SNAPSHOT_V1:
        raise ProgressCheckpointsError("state-aware finish review requires --state-snapshot v1")
    fractions = (V2_DEFAULT_FRACTIONS if selected_mode == V2 and (value is None or str(value).strip() == CONTROL)
                 else resolve_progress_checkpoints(value))
    selected = CONTROL if not fractions else ",".join(map(str, fractions))
    manifest: dict[str, Any] = {"progress_checkpoints": selected}
    if selected_mode == V2:
        manifest["progress_checkpoints_mode"] = V2
    if selected_snapshot == STATE_SNAPSHOT_V1:
        manifest["state_snapshot"] = STATE_SNAPSHOT_V1
    if selected_contract == SUCCESS_CONTRACT_V1:
        manifest["success_contract"] = SUCCESS_CONTRACT_V1
    if selected_finish != CONTROL:
        manifest["finish_review"] = selected_finish
    if fractions:
        manifest["progress_checkpoints_config"] = {
            "fractions_percent": list(fractions), "max_per_run": MAX_CHECKPOINTS,
            "max_request_bytes": MAX_REQUEST_BYTES, "max_calls": MAX_CALLS,
            "call_cap_gbp": CALL_CAP_GBP, "advisory_only": True,
        }
    return manifest
