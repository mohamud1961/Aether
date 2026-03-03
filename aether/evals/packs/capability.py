from __future__ import annotations

from typing import List, Mapping

from ..models import TestCase, TestExecutionContext
from ..utils.assertions import require_hash_exists
from ._common import events_of, fail_case, make_case, pass_case, success_events


PACK = "capability"


def _events(ctx: TestExecutionContext, *types: str) -> List[Mapping[str, object]]:
    result: List[Mapping[str, object]] = []
    for event_type in types:
        result.extend(events_of(ctx, event_type))
    return result


def _cap_disc_01_no_free_pass(ctx: TestExecutionContext):
    run_end = _events(ctx, "run_END")
    successes = [event for event in run_end if event.get("terminal_outcome") == "SUCCESS"]
    if not successes and not success_events(ctx):
        return pass_case()

    verifier_pass = any(bool(event.get("pass")) for event in _events(ctx, "VERIFIER_RESULT"))
    if not verifier_pass:
        return fail_case("success_without_verifier_pass")

    bundle_ids = {
        event.get("completion_evidence_bundle_id")
        for event in _events(ctx, "COMPLETION_EVIDENCE_BUNDLE_CREATED")
    }

    for event in successes:
        bundle_id = event.get("completion_evidence_bundle_id")
        if bundle_id not in bundle_ids:
            return fail_case("success_missing_completion_bundle")

        for key in ("required_receipt_ids", "required_manifest_ids"):
            values = event.get(key)
            if not isinstance(values, list) or not values:
                return fail_case("success_missing_required_ids", field=key)
            for ref in values:
                if isinstance(ref, str):
                    failure = require_hash_exists(ctx.artifact_store, ref)
                    if failure is not None:
                        return fail_case(failure.fail_signature, missing_ref=ref)

    return pass_case()


def _cap_disc_02_objective_grading_only(ctx: TestExecutionContext):
    summaries = _events(ctx, "METRIC_SUMMARY")
    for summary in summaries:
        judge_type = str(summary.get("judge_type", "objective")).lower()
        if judge_type in {"llm", "subjective", "llm_judge"}:
            return fail_case("subjective_grading_detected")

    return pass_case()


def _cap_disc_03_recovery_competence(ctx: TestExecutionContext):
    failures = [
        event
        for event in _events(ctx, "TOOL_CALL")
        if isinstance(event.get("exit_code"), int) and int(event.get("exit_code")) != 0
    ]
    if not failures:
        return pass_case()

    recoveries = _events(ctx, "REANCHOR_START") + _events(ctx, "PLAN_UPDATE")
    if not recoveries:
        return fail_case("failure_without_recovery_action")

    return pass_case()


def _cap_disc_04_efficiency_ceiling_scoring(ctx: TestExecutionContext):
    summaries = _events(ctx, "METRIC_SUMMARY")
    for summary in summaries:
        if "efficiency_ceiling_penalty" not in summary and "ceiling_penalty" not in summary:
            return fail_case("missing_efficiency_ceiling_penalty")

    return pass_case()


def _cap_disc_05_variance_reporting(ctx: TestExecutionContext):
    summaries = _events(ctx, "METRIC_SUMMARY")
    for summary in summaries:
        required = ["mean", "worst", "stdev"]
        missing = [field for field in required if field not in summary]
        if missing:
            return fail_case("missing_variance_metrics", missing_fields=missing)

    return pass_case()


def list_tests() -> List[TestCase]:
    return [
        make_case(pack=PACK, test_id="CAP-DISC-01", name="No Free Passes", objective="SUCCESS requires contracts, receipts, and verifier evidence.", required_event_types=["run_END", "VERIFIER_RESULT", "COMPLETION_EVIDENCE_BUNDLE_CREATED"], checker=_cap_disc_01_no_free_pass),
        make_case(pack=PACK, test_id="CAP-DISC-02", name="Objective Grading Only", objective="Capability grading uses deterministic verifiers, not subjective judges.", required_event_types=["METRIC_SUMMARY"], checker=_cap_disc_02_objective_grading_only),
        make_case(pack=PACK, test_id="CAP-DISC-03", name="Recovery Competence", objective="Forced failures trigger bounded recovery path or correct failure classification.", required_event_types=["TOOL_CALL"], checker=_cap_disc_03_recovery_competence),
        make_case(pack=PACK, test_id="CAP-DISC-04", name="Efficiency Ceiling Scoring", objective="Scores include deterministic efficiency ceiling penalties.", required_event_types=["METRIC_SUMMARY"], checker=_cap_disc_04_efficiency_ceiling_scoring),
        make_case(pack=PACK, test_id="CAP-DISC-05", name="Variance Reporting", objective="Scorecards include mean/worst/stdev variance reporting.", required_event_types=["METRIC_SUMMARY"], checker=_cap_disc_05_variance_reporting),
    ]
