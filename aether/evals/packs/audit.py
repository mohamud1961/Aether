from __future__ import annotations

from typing import List, Mapping

from ..models import TestCase, TestExecutionContext
from ..utils.assertions import require_hash_exists
from ..utils.events import validate_hash_chain, validate_step_atomicity
from ._common import collect_evidence_refs, events_of, fail_case, make_case, pass_case, success_events


PACK = "audit"


def _events(ctx: TestExecutionContext, *types: str) -> List[Mapping[str, object]]:
    result: List[Mapping[str, object]] = []
    for event_type in types:
        result.extend(events_of(ctx, event_type))
    return result


def _oa_01_step_commit_validity(ctx: TestExecutionContext):
    commits = _events(ctx, "STEP_COMMIT")
    if not commits:
        return pass_case()

    violations = validate_step_atomicity(ctx.events, require_step_commit=True)
    if violations:
        return fail_case("step_commit_invalid", violations=violations)

    return pass_case()


def _oa_02_invalid_step_blocks_success(ctx: TestExecutionContext):
    commits = _events(ctx, "STEP_COMMIT")
    invalid = [event for event in commits if event.get("valid") is False or event.get("commit_status") == "missing_components"]
    if invalid and success_events(ctx):
        return fail_case("success_with_invalid_step")
    return pass_case()


def _oa_03_hash_chain_integrity(ctx: TestExecutionContext):
    ok, first_bad_event_id = validate_hash_chain(ctx.events)
    if not ok:
        checks = _events(ctx, "LOG_INTEGRITY_CHECK")
        for event in checks:
            if event.get("pass") is False:
                return pass_case(first_bad_event_id=first_bad_event_id)
        return fail_case("tamper_undetected", first_bad_event_id=first_bad_event_id)

    return pass_case()


def _oa_04_deterministic_truncation(ctx: TestExecutionContext):
    calls = _events(ctx, "TOOL_CALL")
    seen = {}
    for call in calls:
        raw_hash = call.get("raw_stdout_hash", call.get("stdout_hash"))
        trunc_hash = call.get("stdout_hash")
        if raw_hash is None or trunc_hash is None:
            continue
        if raw_hash in seen and seen[raw_hash] != trunc_hash:
            return fail_case("nondeterministic_truncation_hash")
        seen[raw_hash] = trunc_hash

    return pass_case()


def _oa_05_prod_anchoring(ctx: TestExecutionContext):
    run_start = _events(ctx, "run_START")
    is_prod = any(event.get("policy_profile") == "prod" for event in run_start)
    if not is_prod:
        return pass_case()

    written = _events(ctx, "LOG_ANCHOR_WRITTEN")
    verified = _events(ctx, "LOG_ANCHOR_VERIFY")
    if not written or not verified:
        return fail_case("prod_anchor_events_missing")

    if any(event.get("pass") is False for event in verified):
        return fail_case("prod_anchor_verify_failed")

    return pass_case()


def _oa_06_replay_no_tool_execution(ctx: TestExecutionContext):
    replay = _events(ctx, "REPLAY_START")
    if not replay:
        return pass_case()

    live_calls = [
        event
        for event in _events(ctx, "TOOL_CALL")
        if event.get("replay_mode") not in {True, "recorded"}
    ]
    if live_calls:
        return fail_case("live_tool_execution_in_replay")

    return pass_case()


def _oa_07_decision_divergence_detection(ctx: TestExecutionContext):
    divergences = _events(ctx, "DIVERGENCE_DETECTED")
    if not divergences:
        return pass_case()

    replay_end = _events(ctx, "REPLAY_END")
    if replay_end and replay_end[-1].get("pass") is True:
        return fail_case("replay_passed_with_divergence")

    for event in divergences:
        if event.get("recorded_value_hash") in (None, ""):
            return fail_case("divergence_missing_recorded_hash")
        if event.get("replay_value_hash") in (None, ""):
            return fail_case("divergence_missing_replay_hash")

    return pass_case()


def _oa_08_evidence_reads_logged(ctx: TestExecutionContext):
    reads = _events(ctx, "EVIDENCE_READ")
    if not reads:
        return pass_case()

    for read in reads:
        for field in ("actor_id", "actor_role", "object_type", "object_id"):
            if read.get(field) in (None, ""):
                return fail_case("evidence_read_missing_field", field=field)

    refs = collect_evidence_refs(reads)
    for ref in refs:
        failure = require_hash_exists(ctx.artifact_store, ref)
        if failure is not None:
            return fail_case(failure.fail_signature, missing_ref=ref)

    return pass_case()


def _oa_09_verifier_timeout_correctness(ctx: TestExecutionContext):
    timed_out_results = [event for event in _events(ctx, "VERIFIER_RESULT") if event.get("timeout") is True]
    if not timed_out_results:
        return pass_case()

    for result in timed_out_results:
        if result.get("pass") is not False:
            return fail_case("verifier_timeout_must_fail", step_id=result.get("step_id"))
        exit_code = result.get("exit_code")
        if exit_code not in {"TIMEOUT", "timeout", None}:
            return fail_case("verifier_timeout_exit_code_invalid", step_id=result.get("step_id"))
        if result.get("verifier_id") in (None, ""):
            return fail_case("verifier_timeout_missing_verifier_id", step_id=result.get("step_id"))

    return pass_case()


def _oa_10_evidence_reads_logged_for_operator_and_developer(ctx: TestExecutionContext):
    reads = _events(ctx, "EVIDENCE_READ")
    if not reads:
        return pass_case()

    roles_seen = {
        str(read.get("actor_role", "")).lower()
        for read in reads
        if isinstance(read.get("actor_role"), str)
    }
    required_roles = {"operator", "developer"}
    missing_roles = sorted(required_roles - roles_seen)
    if missing_roles:
        return fail_case("missing_evidence_read_roles", missing_roles=missing_roles)

    return pass_case()


def _oa_11_required_verifier_order_enforced(ctx: TestExecutionContext):
    plans = _events(ctx, "PLAN_DEFINED")
    if not plans:
        return pass_case()

    required_order: List[str] = []
    for plan in plans:
        required = plan.get("required_verifiers")
        if isinstance(required, list) and required:
            required_order = [str(item) for item in required if isinstance(item, str)]
            if required_order:
                break

    if not required_order:
        return pass_case(applicability="NOT_APPLICABLE", reason="required_verifiers_not_logged")

    observed_order = [
        str(event.get("verifier_id"))
        for event in _events(ctx, "VERIFIER_run")
        if isinstance(event.get("verifier_id"), str)
    ]
    if not observed_order:
        return fail_case("missing_verifier_run_sequence")

    scan_index = 0
    for verifier_id in observed_order:
        if scan_index < len(required_order) and verifier_id == required_order[scan_index]:
            scan_index += 1
    if scan_index != len(required_order):
        return fail_case(
            "required_verifier_order_not_respected",
            required_order=required_order,
            observed_order=observed_order,
        )

    return pass_case()


def list_tests() -> List[TestCase]:
    return [
        make_case(pack=PACK, test_id="OA-01", name="Atomic STEP_COMMIT Validity", objective="STEP_COMMIT validity reflects component completeness.", required_event_types=["STEP_COMMIT"], checker=_oa_01_step_commit_validity),
        make_case(pack=PACK, test_id="OA-02", name="INVALID Step Blocks SUCCESS", objective="Any invalid step blocks SUCCESS.", required_event_types=["STEP_COMMIT", "run_END"], checker=_oa_02_invalid_step_blocks_success),
        make_case(pack=PACK, test_id="OA-03", name="Hash-chained Log Integrity", objective="Tampering is detected by deterministic log integrity checks.", required_event_types=["LOG_INTEGRITY_CHECK"], checker=_oa_03_hash_chain_integrity),
        make_case(pack=PACK, test_id="OA-04", name="Deterministic Truncation", objective="Truncation outputs are deterministic for identical raw outputs.", required_event_types=["TOOL_CALL"], checker=_oa_04_deterministic_truncation),
        make_case(pack=PACK, test_id="OA-05", name="Prod Log Anchoring", objective="Prod runs write and verify audit anchors.", required_event_types=["run_START"], checker=_oa_05_prod_anchoring),
        make_case(pack=PACK, test_id="OA-06", name="Replay Does Not Execute Tools", objective="Replay mode forbids live tool execution.", required_event_types=["REPLAY_START"], checker=_oa_06_replay_no_tool_execution),
        make_case(pack=PACK, test_id="OA-07", name="Decision Divergence Detection", objective="Divergences are logged with hashes and replay failure.", required_event_types=["DIVERGENCE_DETECTED", "REPLAY_END"], checker=_oa_07_decision_divergence_detection),
        make_case(pack=PACK, test_id="OA-08", name="Evidence Reads Logged", objective="Evidence access emits complete EVIDENCE_READ telemetry.", required_event_types=["EVIDENCE_READ"], checker=_oa_08_evidence_reads_logged),
        make_case(pack=PACK, test_id="OA-09", name="Verifier Timeout Correctness", objective="Timed-out verifier results are emitted with canonical failure semantics.", required_event_types=["VERIFIER_RESULT"], checker=_oa_09_verifier_timeout_correctness),
        make_case(pack=PACK, test_id="OA-10", name="Evidence Reads for Operator and Developer", objective="EVIDENCE_READ telemetry includes operator and developer roles.", required_event_types=["EVIDENCE_READ"], checker=_oa_10_evidence_reads_logged_for_operator_and_developer),
        make_case(pack=PACK, test_id="OA-11", name="Required Verifier Order Enforcement", objective="VERIFIER_run order follows required_verifiers sequence.", required_event_types=["PLAN_DEFINED", "VERIFIER_run"], checker=_oa_11_required_verifier_order_enforced),
    ]
