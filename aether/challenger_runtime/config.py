"""Fail-closed selector, constants, and launch identity for the CHALLENGER claim-ledger arm."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Mapping


CONTROL = "control"
CHALLENGER_V1 = "challenger_v1"
CHALLENGER_V2 = "challenger_v2"  # v1 + failure-mode question, 0.8 hold threshold, no-admit-when-certain (P1)
CHALLENGER_V3 = "challenger_v3"  # v2 + P3: one verification hold on a confident done_with_unverified_parts
CHALLENGER_V4 = "challenger_v4"  # v2 semantics, but the completion card rides in the finish call (separate card turn is the fallback)
CHALLENGER_V5 = "challenger_v5"  # v4 + completion JUDGE request on actual artifact evidence (written files + test outputs) when files were written
V2_FAMILY = frozenset({CHALLENGER_V2, CHALLENGER_V3, CHALLENGER_V4, CHALLENGER_V5})  # modes carrying the v2 behaviour (failure mode, 0.8 holds, P1)
ACTIVE_CLAIM_LEDGER_MODES = frozenset({CHALLENGER_V1, CHALLENGER_V2, CHALLENGER_V3, CHALLENGER_V4, CHALLENGER_V5})
FINISH_CARD_MODES = frozenset({CHALLENGER_V4, CHALLENGER_V5})  # modes whose GLM-visible finish tool carries the completion card
SUPPORTED_CLAIM_LEDGER_MODES = frozenset({CONTROL}) | ACTIVE_CLAIM_LEDGER_MODES
CLAIM_LEDGER_ENV = "AETHER_G4_CLAIM_LEDGER"
CHALLENGER_EVIDENCE_ROOT_ENV = "AETHER_CHALLENGER_EVIDENCE_ROOT"
CHALLENGER_RUN_ID_ENV = "AETHER_CHALLENGER_RUN_ID"  # the launcher's real run id (Harbor does not expose one to the agent)

# T4 hold threshold, calibrated on 197 replayed states: 0.9 held 0/24 wrong finishes; 0.6 held 10/24
# with 2/22 false holds.
CONFIDENCE_THRESHOLD = 0.6
MAX_HOLD_CYCLES = 3
# challenger_v2 only. Hold threshold from the JUDGE bench (377 graded finishes): at 0.8 the per-criterion plus
# failure-mode rule caught 19/29 wrong finishes and falsely held 13/348 solved ones. Weak signals
# between CONFIDENCE_THRESHOLD and this stay advisory.
HOLD_THRESHOLD = 0.8
# challenger_v3 P3 (JUDGE bench, 377 graded finishes): holding on done_with_unverified_parts at >= 0.8 raised wrong-finish
# catches 19/29 -> 23/29 for 13/348 -> 23/348 false holds. At most one such hold per run.
UNVERIFIED_HOLD_THRESHOLD = 0.8
MAX_UNVERIFIED_HOLDS = 1
# challenger_v5 (JUDGE bench, 377 graded finishes): on runs that wrote files the artifact-evidence request (v6_artifacts) at
# 0.6 caught 15/18 wrong finishes vs 10/18 for the failure-mode question at 0.8, with the same false holds. Runs
# that wrote no workspace file keep the 0.8 failure-mode request.
ARTIFACT_HOLD_THRESHOLD = 0.6
ARTIFACT_MAX_REQUEST_BYTES = 120_000  # the JUDGE server accepts ~128 KB (HTTP 400 at 256 KB)
ARTIFACT_MAX_FILES_READ = 24
ARTIFACT_JUDGE_CAP_GBP = "0.25"  # ~20 requests at the byte cap; the 0.05 default covers only ~4
ARTIFACT_JUDGE_TIMEOUT_S = 30.0
EVIDENCE_VARIANT_ARTIFACTS = "v6_artifacts"
EVIDENCE_VARIANT_FAILURE_MODE = "v1_failure_mode"
# P1: past MAX_HOLD_CYCLES keep holding while any hold signal is at least this certain.
CERTAIN_THRESHOLD = 0.95
# P1 never holds past the deadline: below this many remaining seconds (the packet's
# remaining_run_sec) the finish is admitted, a best-effort submission beating a timeout.
DEADLINE_ADMIT_REMAINING_SEC = 300.0
# Total holds without deadline information (MAX_HOLD_CYCLES plus 3 extra), and the ceiling when the deadline is known.
HARD_HOLD_LIMIT_NO_DEADLINE = 6
HARD_HOLD_LIMIT_WITH_DEADLINE = 10
# T1 fallback: fire after this many accepted task actions if no production write was detected.
T1_FALLBACK_ACTIONS = 8
# T1 runs a read-only GLM-written check, so JUDGE confidence must not gate it. The
# policy table requires a threshold in (0, 1]; this floor only excludes zero.
DIAGNOSIS_CONFIDENCE_FLOOR = 0.01
# T2 stuck trigger: one JUDGE progress question per window of accepted task actions after T1.
T2_WINDOW_ACTIONS = 6
T2_FLAG_THRESHOLD = 0.8  # replay: 6/28 unsolved rows flagged, 0/15 solved rows
T2_MAX_REFRESHES = 2
T2_FLAG_CHOICES = ("no_material_change", "test_only_change")
# T1 + T2 refreshes + T4 hold cycles; only cycles that ran a card turn are counted.
LEDGER_MAX_CYCLES = 1 + T2_MAX_REFRESHES + MAX_HOLD_CYCLES
LEDGER_MAX_CYCLES_V2 = 1 + T2_MAX_REFRESHES + HARD_HOLD_LIMIT_WITH_DEADLINE
CARD_MAX_OUTPUT_TOKENS = 6000
JUDGE_MODEL = "judge-1.13.0"
JUDGE_MAX_CALLS = 16
JUDGE_CAP_GBP = "0.05"
JUDGE_INPUT_PRICE_GBP_PER_MILLION = "0.10"
JUDGE_JOURNAL_NAME = "challenger_judge_provider.jsonl"


class ClaimLedgerModeError(ValueError):
    """An unknown or conflicting claim-ledger mode was requested."""


def resolve_claim_ledger_mode(
    value: str | None = None, *, environ: Mapping[str, str] | None = None,
) -> str:
    env = environ or {}
    selected = str(value if value is not None else env.get(CLAIM_LEDGER_ENV, CONTROL)).strip()
    if selected not in SUPPORTED_CLAIM_LEDGER_MODES:
        raise ClaimLedgerModeError(f"unknown claim-ledger mode: {selected!r}")
    return selected


def validate_claim_ledger_launch(
    mode: str | None,
    *,
    context_mode: str = CONTROL,
    same_model_verifier: str = CONTROL,
    judge_verifier: str = CONTROL,
    judge_advice: str = CONTROL,
    judge_keyvault_direct: bool = False,
) -> str:
    # context_mode may be m_tree_v1: CHALLENGER feedback and card turns enter the M-TREE event log.
    """Refuse every conflict before a caller creates evidence paths."""
    selected = resolve_claim_ledger_mode(mode)
    if selected == CONTROL:
        return selected
    for name, value in (
        ("same-model verifier", same_model_verifier),
        ("JUDGE verifier", judge_verifier), ("JUDGE advice", judge_advice),
    ):
        if str(value).strip().lower() != CONTROL:
            raise ClaimLedgerModeError(f"{selected} conflicts with a non-control {name}")
    if not judge_keyvault_direct:
        raise ClaimLedgerModeError(
            f"{selected} needs the direct JUDGE route in the run process; pass --judge-keyvault-direct"
        )
    return selected


def add_claim_ledger_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--claim-ledger", choices=sorted(SUPPORTED_CLAIM_LEDGER_MODES), default=CONTROL,
        help="task-local claim ledger plus typed JUDGE verify/repair (opt-in)",
    )


def runtime_identity(mode: str) -> dict[str, Any]:
    selected = resolve_claim_ledger_mode(mode)
    identity: dict[str, Any] = {"claim_ledger": selected}
    if selected == CHALLENGER_V1:
        identity["claim_ledger_config"] = {
            "triggers": ["T1_first_production_write", "T4_finish_intent"],
            "confidence_threshold": CONFIDENCE_THRESHOLD,
            "max_hold_cycles": MAX_HOLD_CYCLES,
            "judge_model": JUDGE_MODEL,
            "judge_max_calls": JUDGE_MAX_CALLS,
        }
    elif selected in V2_FAMILY:
        identity["claim_ledger_config"] = {
            "triggers": ["T1_first_production_write", "T4_finish_intent"],
            "confidence_threshold": CONFIDENCE_THRESHOLD,
            "hold_threshold": HOLD_THRESHOLD,
            "failure_mode_question": True,
            "max_hold_cycles": MAX_HOLD_CYCLES,
            "p1_no_admit_when_certain": {
                "certain_threshold": CERTAIN_THRESHOLD,
                "deadline_admit_remaining_sec": DEADLINE_ADMIT_REMAINING_SEC,
                "hard_hold_limit_no_deadline": HARD_HOLD_LIMIT_NO_DEADLINE,
                "hard_hold_limit_with_deadline": HARD_HOLD_LIMIT_WITH_DEADLINE,
            },
            "judge_model": JUDGE_MODEL,
            "judge_max_calls": JUDGE_MAX_CALLS,
        }
        if selected == CHALLENGER_V3:
            identity["claim_ledger_config"]["p3_unverified_hold"] = {
                "threshold": UNVERIFIED_HOLD_THRESHOLD, "max_holds": MAX_UNVERIFIED_HOLDS,
            }
        if selected == CHALLENGER_V5:
            identity["claim_ledger_config"]["artifact_evidence"] = {
                "variant": EVIDENCE_VARIANT_ARTIFACTS, "hold_threshold": ARTIFACT_HOLD_THRESHOLD,
                "max_request_bytes": ARTIFACT_MAX_REQUEST_BYTES, "fallback_variant": EVIDENCE_VARIANT_FAILURE_MODE,
            }
        if selected in FINISH_CARD_MODES:
            identity["claim_ledger_config"]["finish_completion_card"] = True
    return identity


def build_claim_ledger_launch_binding(
    mode: str | None,
    *,
    evidence_root: str | Path,
    run_id: str = "",
    context_mode: str = CONTROL,
    same_model_verifier: str = CONTROL,
    judge_verifier: str = CONTROL,
    judge_advice: str = CONTROL,
    judge_keyvault_direct: bool = False,
) -> dict[str, Any]:
    """Validate, then return child env and manifest identity without creating paths."""
    selected = validate_claim_ledger_launch(
        mode, context_mode=context_mode, same_model_verifier=same_model_verifier,
        judge_verifier=judge_verifier, judge_advice=judge_advice,
        judge_keyvault_direct=judge_keyvault_direct,
    )
    env = {CLAIM_LEDGER_ENV: selected}
    if selected in ACTIVE_CLAIM_LEDGER_MODES:
        env[CHALLENGER_EVIDENCE_ROOT_ENV] = str(Path(evidence_root))
        if run_id:
            env[CHALLENGER_RUN_ID_ENV] = str(run_id)
        env["AETHER_JUDGE_CALLS_ALLOWED"] = "1"
    return {"claim_ledger": selected, "env": env, "manifest": runtime_identity(selected)}
