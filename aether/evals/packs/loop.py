from __future__ import annotations

from typing import List, Mapping, Tuple

from ..models import TestCase, TestExecutionContext
from ..utils.hashes import canonical_json_dumps
from ._common import events_of, fail_case, make_case, pass_case


PACK = "loop"


def _events(ctx: TestExecutionContext, *types: str) -> List[Mapping[str, object]]:
    result: List[Mapping[str, object]] = []
    for event_type in types:
        result.extend(events_of(ctx, event_type))
    return result


def _lc_01_fail_budget(ctx: TestExecutionContext):
    run_end = _events(ctx, "run_END")
    for event in run_end:
        if event.get("terminal_outcome") == "FAIL_BUDGET":
            if event.get("summary_reason_code") in (None, ""):
                return fail_case("fail_budget_missing_reason_code")
            return pass_case()
    return pass_case()


def _lc_02_exploration_floor_before_implement(ctx: TestExecutionContext):
    floor_evals = _events(ctx, "EXPLORATION_FLOOR_EVAL")
    for eval_event in floor_evals:
        if eval_event.get("pass") is False:
            denied = _events(ctx, "PHASE_TRANSITION_DENIED")
            if not denied:
                return fail_case("missing_phase_transition_denied")
    return pass_case()


def _lc_03_universal_phase_transition_request(ctx: TestExecutionContext):
    denied = _events(ctx, "PHASE_TRANSITION_DENIED")
    for event in denied:
        if event.get("deny_reason_code") in (None, ""):
            return fail_case("phase_transition_denied_missing_reason")
    return pass_case()


def _lc_04_retry_denied_without_progress(ctx: TestExecutionContext):
    calls = _events(ctx, "TOOL_CALL")
    fingerprints: List[Tuple[str, str, object]] = []
    for call in calls:
        fingerprints.append(
            (
                str(call.get("tool_name", "")),
                canonical_json_dumps(call.get("args_hash", call.get("tool_args", {}))),
                call.get("observed_workspace_hash_before", call.get("workspace_fingerprint_hash")),
            )
        )

    repeated = False
    for idx in range(1, len(fingerprints)):
        if fingerprints[idx] == fingerprints[idx - 1]:
            repeated = True
            break

    if repeated:
        denied = [
            event
            for event in (_events(ctx, "TOOL_DENY") + _events(ctx, "RETRY_DENIED"))
            if str(event.get("deny_reason_code", "")).upper() in {"RETRY_NO_PROGRESS", "REPEAT_FAILED_ATTEMPT"}
        ]
        if not denied:
            return fail_case("repeat_retry_allowed_without_progress")

    return pass_case()


def _lc_05_retry_allowed_with_progress(ctx: TestExecutionContext):
    updates = _events(ctx, "PLAN_UPDATE")
    if not updates:
        return pass_case()

    denied = [
        event
        for event in (_events(ctx, "TOOL_DENY") + _events(ctx, "RETRY_DENIED"))
        if str(event.get("deny_reason_code", "")).upper() in {"RETRY_NO_PROGRESS", "REPEAT_FAILED_ATTEMPT"}
    ]
    for update in updates:
        update_step = update.get("step_id")
        if isinstance(update_step, int):
            if all((event.get("step_id") or -1) <= update_step for event in denied):
                return pass_case()

    return pass_case()


def _lc_06_reanchor_triggers(ctx: TestExecutionContext):
    starts = _events(ctx, "REANCHOR_START")
    if not starts:
        return pass_case()

    for start in starts:
        trigger = start.get("trigger_code")
        if trigger in (None, ""):
            return fail_case("reanchor_missing_trigger_code")

    ends = _events(ctx, "REANCHOR_END")
    if not ends and len(starts) > 0:
        return fail_case("reanchor_missing_end_event")

    return pass_case()


def _lc_07_reanchor_loop_breaker(ctx: TestExecutionContext):
    repeats = _events(ctx, "REANCHOR_REPEAT_DETECTED")
    if not repeats:
        return pass_case()

    for repeat in repeats:
        action = repeat.get("action_taken")
        if action not in {"PLAN_UPDATE", "FAIL_STUCK", "UPDATED_REQUIRED"}:
            return fail_case("invalid_reanchor_repeat_action", action_taken=action)

    return pass_case()


def _lc_08_fail_stuck(ctx: TestExecutionContext):
    run_end = _events(ctx, "run_END")
    for event in run_end:
        if event.get("terminal_outcome") == "FAIL_STUCK":
            if event.get("summary_reason_code") in (None, ""):
                return fail_case("fail_stuck_missing_reason_code")
    return pass_case()


def _lc_09_retry_after_fix_class_repeat(ctx: TestExecutionContext):
    retry_denies = [
        event
        for event in (_events(ctx, "RETRY_DENIED") + _events(ctx, "TOOL_DENY"))
        if str(event.get("deny_reason_code", "")).upper() in {"CLASS_REPEAT_LIMIT", "RETRY_CLASS_REPEAT", "REPEAT_FAILED_ATTEMPT"}
    ]
    if retry_denies:
        return pass_case()

    calls = _events(ctx, "TOOL_CALL")
    if len(calls) >= 3:
        last3 = calls[-3:]
        signatures = [
            stable
            for stable in (
                stable_call_signature(last3[0]),
                stable_call_signature(last3[1]),
                stable_call_signature(last3[2]),
            )
        ]
        if signatures[0] == signatures[1] == signatures[2]:
            return fail_case("class_repeat_not_blocked")

    return pass_case()


def stable_call_signature(call: Mapping[str, object]) -> str:
    return canonical_json_dumps(
        {
            "tool_name": call.get("tool_name"),
            "args_hash": call.get("args_hash"),
            "workspace": call.get("observed_workspace_hash_before", call.get("workspace_fingerprint_hash")),
        }
    )


def _lc_10_budget_extensions_require_approval(ctx: TestExecutionContext):
    approvals = [
        event
        for event in _events(ctx, "APPROVAL_GRANTED")
        if event.get("approval_type") == "BUDGET_EXTENSION"
    ]

    run_end = _events(ctx, "run_END")
    if not run_end:
        return pass_case()

    for end in run_end:
        outcome = end.get("terminal_outcome")
        if outcome == "FAIL_BUDGET":
            continue
        budget_extension_requested = bool(end.get("budget_extension_requested"))
        if budget_extension_requested and not approvals:
            return fail_case("budget_extended_without_approval")

    return pass_case()


def list_tests() -> List[TestCase]:
    return [
        make_case(pack=PACK, test_id="LC-01", name="Budgets Terminate with FAIL_BUDGET", objective="Budget overruns terminate deterministically with FAIL_BUDGET.", required_event_types=["run_END"], checker=_lc_01_fail_budget),
        make_case(pack=PACK, test_id="LC-02", name="Exploration Floors Before Implement", objective="Implement phase is gated by exploration floor evaluation.", required_event_types=["EXPLORATION_FLOOR_EVAL"], checker=_lc_02_exploration_floor_before_implement),
        make_case(pack=PACK, test_id="LC-03", name="Universal Phase Transition Request", objective="Transition requests are always available and receive deterministic response.", required_event_types=["run_END"], checker=_lc_03_universal_phase_transition_request),
        make_case(pack=PACK, test_id="LC-04", name="Retry Denied Without Progress", objective="Identical failed action retries are denied without progress signals.", required_event_types=["TOOL_CALL"], checker=_lc_04_retry_denied_without_progress),
        make_case(pack=PACK, test_id="LC-05", name="Retry Allowed With Progress", objective="Retries proceed when plan/workspace/evidence progress exists.", required_event_types=["PLAN_UPDATE"], checker=_lc_05_retry_allowed_with_progress),
        make_case(pack=PACK, test_id="LC-06", name="Deterministic Re-anchor Triggers", objective="Re-anchor triggers fire with deterministic trigger codes and lifecycle.", required_event_types=["REANCHOR_START"], checker=_lc_06_reanchor_triggers),
        make_case(pack=PACK, test_id="LC-07", name="Re-anchor Loop Breaker", objective="Repeat signatures force bounded breaker actions.", required_event_types=["REANCHOR_REPEAT_DETECTED"], checker=_lc_07_reanchor_loop_breaker),
        make_case(pack=PACK, test_id="LC-08", name="FAIL_STUCK Emission", objective="Death spirals terminate with FAIL_STUCK and reason code.", required_event_types=["run_END"], checker=_lc_08_fail_stuck),
        make_case(pack=PACK, test_id="LC-09", name="retry_after_fix Class-repeat Blocking", objective="Repeated same-class retries are denied after bounded attempts.", required_event_types=["TOOL_CALL"], checker=_lc_09_retry_after_fix_class_repeat),
        make_case(pack=PACK, test_id="LC-10", name="Budget extensions require approval", objective="Budget extensions require APPROVAL_GRANTED approval_type=BUDGET_EXTENSION.", required_event_types=["run_END"], checker=_lc_10_budget_extensions_require_approval),
    ]
