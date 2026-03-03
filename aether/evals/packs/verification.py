from __future__ import annotations

from typing import List, Mapping

from ..models import TestCase, TestExecutionContext
from ..utils.assertions import require_hash_exists
from ._common import events_of, fail_case, make_case, pass_case, success_events


PACK = "verification"


def _events(ctx: TestExecutionContext, *types: str) -> List[Mapping[str, object]]:
    result: List[Mapping[str, object]] = []
    for event_type in types:
        result.extend(events_of(ctx, event_type))
    return result


def _f1_stage_a_receipt_verification_mandatory(ctx: TestExecutionContext):
    calls = _events(ctx, "TOOL_CALL")
    dirty_calls = [event for event in calls if bool(event.get("files_written"))]
    if dirty_calls and not _events(ctx, "VERIFIER_RESULT"):
        return fail_case("dirty_tool_calls_without_verifier_events")

    tool_steps = {
        event.get("step_id")
        for event in calls
        if isinstance(event.get("step_id"), int)
    }
    if not tool_steps:
        return pass_case(applicability="NOT_APPLICABLE", reason="no_tool_calls")

    stage_a_steps = {
        event.get("step_id")
        for event in _events(ctx, "VERIFIER_RESULT")
        if str(event.get("verifier_stage", "")).upper() == "A"
    }
    missing = sorted(step for step in tool_steps if step not in stage_a_steps)
    if missing:
        return fail_case("missing_stage_a_verification", step_ids=missing)

    return pass_case(stage_a_steps=len(stage_a_steps))


def _f2_stage_b_required_for_plan_step_completion(ctx: TestExecutionContext):
    done_steps = [event for event in _events(ctx, "PLAN_STEP_STATUS") if event.get("status") == "DONE"]
    if not done_steps:
        return pass_case(applicability="NOT_APPLICABLE", reason="no_plan_done_steps")

    stage_b_verifiers = {
        event.get("verifier_id")
        for event in _events(ctx, "VERIFIER_RESULT")
        if str(event.get("verifier_stage", "")).upper() == "B" and event.get("pass") is True
    }

    for step in done_steps:
        refs = step.get("evidence_receipt_ids")
        verifiers = step.get("verifier_ids")
        if not isinstance(refs, list) or not refs:
            return fail_case("plan_done_step_missing_evidence_refs")
        if not isinstance(verifiers, list) or not verifiers:
            return fail_case("plan_done_step_missing_verifier_ids")
        if not any(verifier in stage_b_verifiers for verifier in verifiers):
            return fail_case("plan_done_step_missing_stage_b_verifier")

    return pass_case(done_steps=len(done_steps))


def _f3_stage_c_bundle_required_for_success(ctx: TestExecutionContext):
    if not success_events(ctx):
        return pass_case()

    bundle_events = _events(ctx, "COMPLETION_EVIDENCE_BUNDLE_CREATED")
    if not bundle_events:
        return fail_case("success_without_completion_bundle")

    bundle_ids = {event.get("completion_evidence_bundle_id") for event in bundle_events}
    for end in _events(ctx, "run_END"):
        if end.get("terminal_outcome") != "SUCCESS":
            continue
        bundle_id = end.get("completion_evidence_bundle_id")
        if bundle_id not in bundle_ids:
            return fail_case("run_end_missing_valid_bundle_id")

        for key in ("required_receipt_ids", "required_manifest_ids"):
            values = end.get(key)
            if not isinstance(values, list) or not values:
                return fail_case("run_end_missing_required_refs", field=key)
            for ref in values:
                if isinstance(ref, str):
                    missing = require_hash_exists(ctx.artifact_store, ref)
                    if missing is not None:
                        return fail_case(missing.fail_signature, missing_ref=ref)

    return pass_case(bundle_count=len(bundle_events))


def _f4_dirty_after_verify_blocks_commit(ctx: TestExecutionContext):
    verifier_pass_steps = [
        event.get("step_id")
        for event in _events(ctx, "VERIFIER_RESULT")
        if event.get("pass") is True and isinstance(event.get("step_id"), int)
    ]
    if not verifier_pass_steps:
        return pass_case(applicability="NOT_APPLICABLE", reason="no_verifier_pass")

    last_verify = max(verifier_pass_steps)
    writes_after = [
        event
        for event in _events(ctx, "TOOL_CALL")
        if isinstance(event.get("step_id"), int)
        and event.get("step_id") > last_verify
        and bool(event.get("files_written"))
    ]
    if writes_after and success_events(ctx):
        return fail_case("success_after_dirty_post_verify_without_reverify")

    return pass_case(writes_after_verify=len(writes_after))


def _f5_verifier_timeout_semantics(ctx: TestExecutionContext):
    timed_out = [event for event in _events(ctx, "VERIFIER_RESULT") if event.get("timeout") is True]
    if not timed_out:
        return pass_case(applicability="NOT_APPLICABLE", reason="no_verifier_timeouts")

    for event in timed_out:
        if event.get("pass") is not False:
            return fail_case("verifier_timeout_not_marked_failed")
        if event.get("timeout_ms") in (None, ""):
            return fail_case("verifier_timeout_missing_timeout_ms")

    if success_events(ctx):
        return fail_case("success_after_verifier_timeout")

    return pass_case(verifier_timeouts=len(timed_out))


def list_tests() -> List[TestCase]:
    return [
        make_case(pack=PACK, test_id="F1", name="Stage A mandatory", objective="Every tool receipt has Stage A verification.", required_event_types=["run_END"], checker=_f1_stage_a_receipt_verification_mandatory),
        make_case(pack=PACK, test_id="F2", name="Stage B for plan DONE", objective="Plan-step completion requires Stage B verifier linkage and evidence refs.", required_event_types=["run_END"], checker=_f2_stage_b_required_for_plan_step_completion),
        make_case(pack=PACK, test_id="F3", name="Stage C bundle for SUCCESS", objective="SUCCESS requires valid completion evidence bundle integrity.", required_event_types=["run_END"], checker=_f3_stage_c_bundle_required_for_success),
        make_case(pack=PACK, test_id="F4", name="Dirty-after-verify guard", objective="Edits after verify invalidate success unless re-verified.", required_event_types=["run_END"], checker=_f4_dirty_after_verify_blocks_commit),
        make_case(pack=PACK, test_id="F5", name="Verifier timeout semantics", objective="Verifier timeout is recorded, counted, and cannot be ignored.", required_event_types=["run_END"], checker=_f5_verifier_timeout_semantics),
    ]
