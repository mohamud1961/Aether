from __future__ import annotations

from typing import List, Mapping, Tuple

from ..models import TestCase, TestExecutionContext
from ..utils.hashes import canonical_json_dumps
from ._common import events_of, fail_case, make_case, pass_case


PACK = "loopvnext"


def _events(ctx: TestExecutionContext, *types: str) -> List[Mapping[str, object]]:
    result: List[Mapping[str, object]] = []
    for event_type in types:
        result.extend(events_of(ctx, event_type))
    return result


def _stable_action_signature(call: Mapping[str, object]) -> Tuple[str, str, object]:
    return (
        str(call.get("tool_name", "")),
        canonical_json_dumps(call.get("args_hash", call.get("tool_args", {}))),
        call.get("observed_workspace_hash_before", call.get("workspace_fingerprint_hash")),
    )


def _g1_action_fingerprint_stability(ctx: TestExecutionContext):
    seen: dict[Tuple[str, str, object], str] = {}
    for event in _events(ctx, "TOOL_CALL", "TOOL_DENY"):
        signature = _stable_action_signature(event)
        fingerprint = event.get("attempted_action_fingerprint")
        if signature in seen and fingerprint and seen[signature] != fingerprint:
            return fail_case("attempted_action_fingerprint_instability")
        if isinstance(fingerprint, str) and fingerprint:
            seen[signature] = fingerprint

    return pass_case(observed_fingerprints=len(seen))


def _g2_no_identical_retry_without_progress(ctx: TestExecutionContext):
    calls = _events(ctx, "TOOL_CALL")
    if len(calls) < 2:
        return pass_case(applicability="NOT_APPLICABLE", reason="insufficient_tool_calls")

    repeated = False
    for idx in range(1, len(calls)):
        if _stable_action_signature(calls[idx]) == _stable_action_signature(calls[idx - 1]):
            repeated = True
            break

    if not repeated:
        return pass_case()

    denied = [
        event
        for event in _events(ctx, "TOOL_DENY", "RETRY_DENIED")
        if str(event.get("deny_reason_code", "")).upper() in {"RETRY_NO_PROGRESS", "REPEAT_FAILED_ATTEMPT"}
    ]
    if not denied:
        return fail_case("identical_retry_without_retry_denied")

    return pass_case(retry_denials=len(denied))


def _g3_reanchor_signature_loop_breaker(ctx: TestExecutionContext):
    starts = _events(ctx, "REANCHOR_START")
    if len(starts) < 3:
        return pass_case(applicability="NOT_APPLICABLE", reason="insufficient_reanchor_cycles")

    signatures = [event.get("reanchor_signature") for event in starts if event.get("reanchor_signature")]
    if len(signatures) < 3:
        return pass_case(applicability="NOT_APPLICABLE", reason="missing_reanchor_signatures")

    repeated = signatures[-1] == signatures[-2] == signatures[-3]
    if not repeated:
        return pass_case()

    breaker_events = _events(ctx, "REANCHOR_REPEAT_DETECTED") + _events(ctx, "PLAN_UPDATE")
    if not breaker_events:
        run_end = _events(ctx, "run_END")
        if any(event.get("terminal_outcome") == "FAIL_STUCK" for event in run_end):
            return pass_case()
        return fail_case("reanchor_repeat_without_breaker_action")

    return pass_case(breaker_events=len(breaker_events))


def _g4_phase_deadlock_escape(ctx: TestExecutionContext):
    denials = _events(ctx, "PHASE_TRANSITION_DENIED")
    if not denials:
        return pass_case(applicability="NOT_APPLICABLE", reason="no_phase_transition_denials")

    for denial in denials:
        reason = denial.get("deny_reason_code") or denial.get("reason")
        if reason in (None, ""):
            return fail_case("phase_transition_denied_missing_reason")

    return pass_case(phase_transition_denials=len(denials))


def _g5_meta_work_limiter(ctx: TestExecutionContext):
    updates = _events(ctx, "PLAN_UPDATE")
    if len(updates) < 3:
        return pass_case(applicability="NOT_APPLICABLE", reason="insufficient_plan_updates")

    evidence_reads = _events(ctx, "EVIDENCE_READ")
    tool_calls = _events(ctx, "TOOL_CALL")
    if evidence_reads or tool_calls:
        return pass_case()

    limiter = [
        event
        for event in (_events(ctx, "LOOP_BREAKER_TRIGGER") + _events(ctx, "RETRY_DENIED") + _events(ctx, "run_END"))
        if str(event.get("deny_reason_code", event.get("terminal_outcome", ""))).upper()
        in {"RETRY_NO_PROGRESS", "FAIL_STUCK", "META_WORK_LIMIT"}
    ]
    if not limiter:
        return fail_case("plan_churn_without_loop_policy_action")

    return pass_case(loop_limiter_events=len(limiter))


def list_tests() -> List[TestCase]:
    return [
        make_case(pack=PACK, test_id="G1", name="Action fingerprint stability", objective="Same attempted action yields stable fingerprint.", required_event_types=["run_END"], checker=_g1_action_fingerprint_stability),
        make_case(pack=PACK, test_id="G2", name="No identical retry without progress", objective="Repeat attempts are denied unless progress exists.", required_event_types=["run_END"], checker=_g2_no_identical_retry_without_progress),
        make_case(pack=PACK, test_id="G3", name="Re-anchor loop breaker", objective="Repeated re-anchor signatures force breaker action or FAIL_STUCK.", required_event_types=["run_END"], checker=_g3_reanchor_signature_loop_breaker),
        make_case(pack=PACK, test_id="G4", name="Phase deadlock escape", objective="Transition denials are deterministic and request path stays available.", required_event_types=["run_END"], checker=_g4_phase_deadlock_escape),
        make_case(pack=PACK, test_id="G5", name="Meta-work limiter", objective="Plan churn without evidence triggers loop policy actions.", required_event_types=["run_END"], checker=_g5_meta_work_limiter),
    ]
