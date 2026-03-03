from __future__ import annotations

from typing import List, Mapping

from ..models import TestCase, TestExecutionContext
from ..utils.assertions import require_hash_exists
from ..utils.benchify_patterns import (
    BENCHIFY_PATTERN_REGISTRY_VERSION,
    matches_benchify_pattern,
)
from ..utils.decision_fields import (
    DECISION_FIELDS_VERSION,
    DECISION_EVENT_FIELDS,
    required_decision_events_present,
    required_decision_fields_missing,
)
from ..utils.events import validate_step_atomicity
from ._common import events_of, fail_case, make_case, pass_case, success_events


PACK = "contract"


def _events(ctx: TestExecutionContext, *types: str) -> List[Mapping[str, object]]:
    result: List[Mapping[str, object]] = []
    for event_type in types:
        result.extend(events_of(ctx, event_type))
    return result


def _ct_01_evidence_bound_success(ctx: TestExecutionContext):
    run_end = _events(ctx, "run_END")
    if not run_end:
        return fail_case("missing_run_end")

    verifier_pass = any(
        bool(event.get("pass"))
        for event in _events(ctx, "VERIFIER_RESULT")
    )

    bundles = _events(ctx, "COMPLETION_EVIDENCE_BUNDLE_CREATED")
    bundle_ids = {event.get("completion_evidence_bundle_id") for event in bundles}

    for event in run_end:
        if event.get("terminal_outcome") != "SUCCESS":
            continue
        if not verifier_pass:
            return fail_case("success_without_required_verifier")

        bundle_id = event.get("completion_evidence_bundle_id")
        if bundle_id not in bundle_ids:
            return fail_case("success_missing_completion_evidence_bundle")

        for key in ("required_receipt_ids", "required_manifest_ids"):
            refs = event.get(key)
            if not isinstance(refs, list) or not refs:
                return fail_case("success_missing_required_refs", field=key)
            for ref in refs:
                if isinstance(ref, str):
                    failure = require_hash_exists(ctx.artifact_store, ref)
                    if failure is not None:
                        return fail_case(failure.fail_signature, field=key, missing_ref=ref)

    return pass_case()


def _ct_02_two_channel_completeness(ctx: TestExecutionContext):
    model_calls = _events(ctx, "MODEL_CALL")
    if not model_calls:
        return fail_case("missing_model_calls")

    compiled = _events(ctx, "CONTEXTPACK_COMPILED")
    bound = _events(ctx, "CONTEXT_SLICE_BOUND")
    if not compiled and not bound:
        return fail_case("missing_context_binding_events")

    compiled_by_step = {event.get("step_id") for event in compiled}
    bound_by_step = {event.get("step_id") for event in bound}

    for call in model_calls:
        step_id = call.get("step_id")
        if step_id not in compiled_by_step and step_id not in bound_by_step:
            return fail_case("model_call_without_context_binding", step_id=step_id)

    return pass_case()


def _ct_03_replay_zero_divergence(ctx: TestExecutionContext):
    replay_end = _events(ctx, "REPLAY_END")
    if not replay_end:
        return fail_case("missing_replay_end")

    latest = replay_end[-1]
    if latest.get("pass") is False:
        return fail_case("replay_marked_failed")

    divergence_rate = latest.get("divergence_rate")
    if divergence_rate is not None and float(divergence_rate) != 0.0:
        return fail_case("replay_divergence_nonzero", divergence_rate=divergence_rate)

    decision_events_by_type = {
        event_type: _events(ctx, event_type) for event_type in DECISION_EVENT_FIELDS
    }
    missing_required = required_decision_events_present(decision_events_by_type)
    if missing_required:
        return fail_case(
            "missing_required_decision_events",
            decision_fields_version=DECISION_FIELDS_VERSION,
            missing_event_types=missing_required,
        )

    for event_type, events in decision_events_by_type.items():
        for event in events:
            missing_fields = required_decision_fields_missing(event_type, event)
            if missing_fields:
                return fail_case(
                    "missing_required_decision_fields",
                    decision_fields_version=DECISION_FIELDS_VERSION,
                    event_type=event_type,
                    missing_fields=missing_fields,
                )

    for event in _events(ctx, "DIVERGENCE_DETECTED"):
        if event.get("divergence_type") != "decision":
            continue
        decision_type = str(event.get("event_type_name", event.get("decision_event_type", "")))
        if decision_type and decision_type not in DECISION_EVENT_FIELDS:
            return fail_case(
                "unknown_decision_event_type_in_divergence",
                decision_fields_version=DECISION_FIELDS_VERSION,
                decision_event_type=decision_type,
            )
        return fail_case(
            "decision_divergence_detected",
            decision_fields_version=DECISION_FIELDS_VERSION,
        )

    return pass_case()


def _ct_04_no_benchifying_static_and_dynamic(ctx: TestExecutionContext):
    benchify_violations = [
        event
        for event in _events(ctx, "POLICY_VIOLATION")
        if matches_benchify_pattern(event)
    ]
    if benchify_violations:
        return fail_case(
            "benchifying_static_violation",
            benchify_registry_version=BENCHIFY_PATTERN_REGISTRY_VERSION,
        )

    dynamic_divergence = [
        event
        for event in _events(ctx, "DIVERGENCE_DETECTED")
        if event.get("divergence_type") in {"decision", "benchify_dynamic"}
    ]
    if dynamic_divergence:
        return fail_case(
            "benchifying_dynamic_divergence",
            benchify_registry_version=BENCHIFY_PATTERN_REGISTRY_VERSION,
        )

    return pass_case()


def _ct_09_model_call_timeout_event_correctness(ctx: TestExecutionContext):
    model_calls = _events(ctx, "MODEL_CALL")
    timeout_calls = [event for event in model_calls if event.get("timeout") is True]
    if not timeout_calls:
        return pass_case()

    for call in timeout_calls:
        if call.get("model_id") in (None, ""):
            return fail_case("model_timeout_missing_model_id", step_id=call.get("step_id"))
        if call.get("latency_ms") in (None, ""):
            return fail_case("model_timeout_missing_latency_ms", step_id=call.get("step_id"))
        if call.get("timeout_ms") in (None, ""):
            return fail_case("model_timeout_missing_timeout_ms", step_id=call.get("step_id"))

    return pass_case()


def _ct_10_workspace_hash_equivalence(ctx: TestExecutionContext):
    commits = _events(ctx, "STEP_COMMIT")
    if not commits:
        return pass_case()

    matched = False
    for commit in commits:
        full_hash = commit.get("workspace_hash_full")
        incremental_hash = commit.get("workspace_hash_incremental")
        if full_hash in (None, "") and incremental_hash in (None, ""):
            continue
        if full_hash in (None, "") or incremental_hash in (None, ""):
            return fail_case("workspace_hash_equivalence_fields_missing", step_id=commit.get("step_id"))
        matched = True
        if full_hash != incremental_hash:
            return fail_case(
                "workspace_hash_equivalence_mismatch",
                step_id=commit.get("step_id"),
            )

    if not matched:
        return fail_case("workspace_hash_equivalence_not_logged")

    return pass_case()


def _ct_05_single_gateway_enforcement(ctx: TestExecutionContext):
    bypass = [
        event
        for event in _events(ctx, "POLICY_VIOLATION")
        if str(event.get("violation_code", "")).upper() in {"GATEWAY_BYPASS", "DIRECT_EXECUTION"}
    ]
    if bypass and success_events(ctx):
        return fail_case("success_after_gateway_bypass")

    return pass_case()


def _ct_06_completion_receipt_bypass_attempt(ctx: TestExecutionContext):
    run_end = _events(ctx, "run_END")
    for event in run_end:
        if event.get("terminal_outcome") != "SUCCESS":
            continue

        refs = []
        for key in ("required_receipt_ids", "required_manifest_ids"):
            values = event.get(key)
            if not isinstance(values, list) or not values:
                return fail_case("success_missing_completion_receipts", field=key)
            refs.extend([value for value in values if isinstance(value, str)])

        for ref in refs:
            failure = require_hash_exists(ctx.artifact_store, ref)
            if failure is not None:
                return fail_case("fabricated_completion_receipt", missing_ref=ref)

    return pass_case()


def _ct_07_unknown_enum_blocks_success(ctx: TestExecutionContext):
    unknown_enum_events = [
        event
        for event in _events(ctx, "POLICY_VIOLATION")
        if event.get("violation_code") == "UNKNOWN_ENUM"
    ]
    if unknown_enum_events and success_events(ctx):
        return fail_case("success_after_unknown_enum")

    return pass_case()


def _ct_08_atomic_step_commit_invariant(ctx: TestExecutionContext):
    atomicity = validate_step_atomicity(ctx.events, require_step_commit=True)
    if atomicity:
        return fail_case("invalid_step_commit_atomicity", violations=atomicity)

    invalid_steps = [
        event
        for event in _events(ctx, "STEP_COMMIT")
        if event.get("valid") is False or event.get("commit_status") == "missing_components"
    ]
    if invalid_steps and success_events(ctx):
        return fail_case("success_with_invalid_step_commit")

    return pass_case()


def list_tests() -> List[TestCase]:
    return [
        make_case(pack=PACK, test_id="CT-01", name="Evidence-bound Success", objective="SUCCESS requires verifier-backed evidence and completion receipts.", required_event_types=["run_END", "VERIFIER_RESULT", "COMPLETION_EVIDENCE_BUNDLE_CREATED"], checker=_ct_01_evidence_bound_success),
        make_case(pack=PACK, test_id="CT-02", name="Two-channel Completeness", objective="Every model call has a context pack and context-slice binding.", required_event_types=["MODEL_CALL", "CONTEXTPACK_COMPILED"], checker=_ct_02_two_channel_completeness),
        make_case(pack=PACK, test_id="CT-03", name="Replay Zero Divergence", objective="Replay must preserve decisions with 0% divergence.", required_event_types=["REPLAY_END"], checker=_ct_03_replay_zero_divergence),
        make_case(pack=PACK, test_id="CT-04", name="No Benchifying Static and Dynamic", objective="No static benchmark routing and no dynamic decision drift under invariant signals.", required_event_types=["run_END"], checker=_ct_04_no_benchifying_static_and_dynamic),
        make_case(pack=PACK, test_id="CT-05", name="Single Gateway Enforcement", objective="Tool execution outside the gateway is blocked.", required_event_types=["run_END"], checker=_ct_05_single_gateway_enforcement),
        make_case(pack=PACK, test_id="CT-06", name="CompletionReceipt Bypass Attempt", objective="Fabricated completion receipts cannot produce SUCCESS.", required_event_types=["run_END"], checker=_ct_06_completion_receipt_bypass_attempt),
        make_case(pack=PACK, test_id="CT-07", name="Unknown Enum Blocks SUCCESS", objective="Unknown enum values produce policy violation and block SUCCESS.", required_event_types=["run_END"], checker=_ct_07_unknown_enum_blocks_success),
        make_case(pack=PACK, test_id="CT-08", name="Atomic Step Commit Invariant", objective="Invalid STEP_COMMIT blocks SUCCESS.", required_event_types=["STEP_COMMIT"], checker=_ct_08_atomic_step_commit_invariant),
        make_case(pack=PACK, test_id="CT-09", name="Model Call Timeout Event Correctness", objective="Timed-out MODEL_CALL events carry canonical timeout metadata.", required_event_types=["MODEL_CALL"], checker=_ct_09_model_call_timeout_event_correctness),
        make_case(pack=PACK, test_id="CT-10", name="Workspace Hash Equivalence", objective="Full and incremental workspace root hashes are equivalent when both are logged.", required_event_types=["STEP_COMMIT"], checker=_ct_10_workspace_hash_equivalence),
    ]
