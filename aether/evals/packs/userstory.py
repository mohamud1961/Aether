from __future__ import annotations

from typing import List, Mapping

from ..models import TestCase, TestExecutionContext
from ..utils.assertions import require_enum, require_hash_exists
from ..utils.final_report_schema import (
    FINAL_REPORT_SCHEMA_VERSION,
    validate_final_report_schema,
)
from ._common import collect_evidence_refs, events_of, fail_case, make_case, pass_case, success_events


PACK = "userstory"


def _events(ctx: TestExecutionContext, *types: str) -> List[Mapping[str, object]]:
    result: List[Mapping[str, object]] = []
    for event_type in types:
        result.extend(events_of(ctx, event_type))
    return result


def _us_01_see_what_happened(ctx: TestExecutionContext):
    attempts = _events(ctx, "TOOL_CALL", "TOOL_DENY")
    if not attempts:
        return fail_case("missing_tool_attempts")

    commits = _events(ctx, "STEP_COMMIT")
    if commits:
        commit_steps = {event.get("step_id") for event in commits}
        for attempt in attempts:
            if attempt.get("step_id") not in commit_steps:
                return fail_case("tool_attempt_not_in_committed_step")

    return pass_case()


def _us_02_see_what_model_saw(ctx: TestExecutionContext):
    model_calls = _events(ctx, "MODEL_CALL")
    if not model_calls:
        return pass_case()

    compiled = _events(ctx, "CONTEXTPACK_COMPILED")
    bound = _events(ctx, "CONTEXT_SLICE_BOUND")
    by_step = {event.get("step_id") for event in compiled} | {event.get("step_id") for event in bound}

    for call in model_calls:
        if call.get("step_id") not in by_step:
            return fail_case("model_call_missing_contextpack")

    return pass_case()


def _us_03_denial_reason_codes(ctx: TestExecutionContext):
    denials = _events(ctx, "TOOL_DENY", "PHASE_TRANSITION_DENIED")
    if not denials:
        return pass_case()

    for denial in denials:
        code = denial.get("deny_reason_code")
        if code in (None, ""):
            return fail_case("missing_deny_reason_code")
        failure = require_enum(ctx.enum_registry, "deny_reason_code", code)
        if failure is not None:
            return fail_case(failure.fail_signature, code=code)

    return pass_case()


def _us_04_trust_done(ctx: TestExecutionContext):
    if not success_events(ctx):
        return pass_case()

    commits = _events(ctx, "STEP_COMMIT")
    for commit in commits:
        if commit.get("valid") is False or commit.get("commit_status") == "missing_components":
            return fail_case("success_with_invalid_step_commit")

    verifier_pass = any(bool(event.get("pass")) for event in _events(ctx, "VERIFIER_RESULT"))
    if not verifier_pass:
        return fail_case("success_without_verifier")

    return pass_case()


def _us_05_useful_failure_mode(ctx: TestExecutionContext):
    run_end = _events(ctx, "run_END")
    if not run_end:
        return pass_case()

    allowed = {"SUCCESS", "FAIL_POLICY", "FAIL_BUDGET", "FAIL_STUCK", "FAIL_ENV", "FAIL_UNKNOWN"}
    for event in run_end:
        outcome = event.get("terminal_outcome")
        if outcome not in allowed:
            return fail_case("invalid_terminal_outcome", terminal_outcome=outcome)
        for key in ("summary_reason_code", "required_receipt_ids", "required_manifest_ids"):
            if event.get(key) in (None, ""):
                return fail_case("run_end_missing_required_field", field=key)

    return pass_case()


def _us_06_reproduce_offline(ctx: TestExecutionContext):
    replay_end = _events(ctx, "REPLAY_END")
    if not replay_end:
        return pass_case()

    latest = replay_end[-1]
    if latest.get("pass") is False:
        return fail_case("replay_pass_false")
    divergence = latest.get("divergence_rate")
    if divergence is not None and float(divergence) != 0.0:
        return fail_case("replay_divergence_nonzero")

    return pass_case()


def _us_07_cost_cap_predictable_stop(ctx: TestExecutionContext):
    run_end = _events(ctx, "run_END")
    for event in run_end:
        if event.get("terminal_outcome") == "FAIL_BUDGET":
            if event.get("summary_reason_code") in (None, ""):
                return fail_case("fail_budget_missing_reason")

    return pass_case()


def _us_08_prompt_injection_protection(ctx: TestExecutionContext):
    compiled = _events(ctx, "CONTEXTPACK_COMPILED")
    for event in compiled:
        slices = event.get("slice_list")
        if not isinstance(slices, list):
            continue
        for slice_item in slices:
            if not isinstance(slice_item, Mapping):
                continue
            text = str(slice_item.get("content_preview", ""))
            trust = str(slice_item.get("trust_level", "")).upper()
            if ("SYSTEM:" in text or "IMPORTANT:" in text) and trust not in {"UNTRUSTED", "LOW"}:
                return fail_case("injection_crossed_trust_boundary")

    return pass_case()


def _us_09_claims_to_evidence_mapping(ctx: TestExecutionContext):
    run_end = _events(ctx, "run_END")
    if not run_end:
        return pass_case()

    success_run_end = [event for event in run_end if event.get("terminal_outcome") == "SUCCESS"]
    if not success_run_end:
        return pass_case()

    final_report_refs = []
    for event in success_run_end:
        ref = event.get("final_report_artifact_id")
        if isinstance(ref, str):
            final_report_refs.append(ref)
    if not final_report_refs:
        return fail_case("missing_final_report_artifact")

    for report_ref in final_report_refs:
        failure = require_hash_exists(ctx.artifact_store, report_ref)
        if failure is not None:
            return fail_case(failure.fail_signature, missing_ref=report_ref)

        report_payload = ctx.artifact_store.load_json(report_ref)
        missing_top, claim_errors = validate_final_report_schema(report_payload)
        if missing_top:
            return fail_case(
                "final_report_schema_missing_fields",
                schema_version=FINAL_REPORT_SCHEMA_VERSION,
                missing_fields=missing_top,
            )
        if claim_errors:
            return fail_case(
                "final_report_schema_claim_errors",
                schema_version=FINAL_REPORT_SCHEMA_VERSION,
                claim_errors=claim_errors,
            )

        claims = report_payload.get("claims")
        if isinstance(claims, list):
            for claim in claims:
                if not isinstance(claim, Mapping):
                    continue
                refs = claim.get("evidence_refs", [])
                if isinstance(refs, list):
                    for ref in refs:
                        if isinstance(ref, str):
                            failure = require_hash_exists(ctx.artifact_store, ref)
                            if failure is not None:
                                return fail_case("claim_without_evidence_mapping", missing_ref=ref)

    for event in success_run_end:
        receipt_ids = event.get("required_receipt_ids") or []
        manifest_ids = event.get("required_manifest_ids") or []
        for ref in receipt_ids + manifest_ids:
            if isinstance(ref, str):
                failure = require_hash_exists(ctx.artifact_store, ref)
                if failure is not None:
                    return fail_case("claim_without_evidence_mapping", missing_ref=ref)

    return pass_case(
        evidence_refs=collect_evidence_refs(success_run_end),
        schema_version=FINAL_REPORT_SCHEMA_VERSION,
    )


def _us_10_reanchor_transparent_bounded(ctx: TestExecutionContext):
    starts = _events(ctx, "REANCHOR_START")
    repeats = _events(ctx, "REANCHOR_REPEAT_DETECTED")

    if not starts:
        return pass_case()

    if not repeats:
        signatures = [event.get("reanchor_signature") for event in starts if event.get("reanchor_signature")]
        if len(signatures) >= 3 and signatures[-1] == signatures[-2] == signatures[-3]:
            return fail_case("unbounded_reanchor_without_repeat_detection")
    return pass_case()


def list_tests() -> List[TestCase]:
    return [
        make_case(pack=PACK, test_id="US-01", name="I can see what happened", objective="Every tool attempt is visible and linked to committed steps.", required_event_types=["TOOL_CALL"], checker=_us_01_see_what_happened),
        make_case(pack=PACK, test_id="US-02", name="I can see what the model saw", objective="Every model call has context-pack lineage.", required_event_types=["MODEL_CALL", "CONTEXTPACK_COMPILED"], checker=_us_02_see_what_model_saw),
        make_case(pack=PACK, test_id="US-03", name="I can see why denied", objective="Denials include deterministic enum reason codes.", required_event_types=["run_END"], checker=_us_03_denial_reason_codes),
        make_case(pack=PACK, test_id="US-04", name="I can trust done", objective="SUCCESS implies valid steps and verifier-backed evidence.", required_event_types=["run_END", "VERIFIER_RESULT"], checker=_us_04_trust_done),
        make_case(pack=PACK, test_id="US-05", name="Useful failure mode", objective="run_END always includes complete deterministic terminal metadata.", required_event_types=["run_END"], checker=_us_05_useful_failure_mode),
        make_case(pack=PACK, test_id="US-06", name="Reproduce decisions offline", objective="Replay provides deterministic 0-divergence guarantees.", required_event_types=["REPLAY_END"], checker=_us_06_reproduce_offline),
        make_case(pack=PACK, test_id="US-07", name="Cost cap predictable stop", objective="Budget exhaustion emits FAIL_BUDGET with reason.", required_event_types=["run_END"], checker=_us_07_cost_cap_predictable_stop),
        make_case(pack=PACK, test_id="US-08", name="Protected from prompt injection", objective="Injection remains confined to untrusted context slices.", required_event_types=["CONTEXTPACK_COMPILED"], checker=_us_08_prompt_injection_protection),
        make_case(pack=PACK, test_id="US-09", name="Claims map to evidence", objective="Final claims are backed by receipt/manifest evidence hashes.", required_event_types=["run_END"], checker=_us_09_claims_to_evidence_mapping),
        make_case(pack=PACK, test_id="US-10", name="Re-anchor transparent and bounded", objective="Re-anchor activity is visible and bounded by loop-breaker policy.", required_event_types=["REANCHOR_START"], checker=_us_10_reanchor_transparent_bounded),
    ]
