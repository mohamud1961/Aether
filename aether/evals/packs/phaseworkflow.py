from __future__ import annotations

from typing import List, Mapping

from ..models import TestCase, TestExecutionContext
from ._common import events_of, fail_case, make_case, pass_case


PACK = "phaseworkflow"


def _events(ctx: TestExecutionContext, *types: str) -> List[Mapping[str, object]]:
    result: List[Mapping[str, object]] = []
    for event_type in types:
        result.extend(events_of(ctx, event_type))
    return result


def _c1_exploration_floor_enforced(ctx: TestExecutionContext):
    floor_events = _events(ctx, "EXPLORATION_FLOOR_EVAL")
    transitions = _events(ctx, "PHASE_TRANSITION", "PHASE_TRANSITION_DENIED")
    floor_expected = False
    for event in transitions:
        from_phase = str(event.get("from_phase", ""))
        to_phase = str(event.get("to_phase", ""))
        reason = str(event.get("deny_reason_code") or event.get("reason") or "").lower()
        if (from_phase == "Explore" and to_phase == "Implement") or ("exploration_floor" in reason):
            floor_expected = True
            break

    if not floor_events:
        if floor_expected:
            return fail_case("missing_exploration_floor_events")
        return pass_case(applicability="NOT_APPLICABLE", reason="no_exploration_floor_expected")

    denied = _events(ctx, "PHASE_TRANSITION_DENIED")
    for event in floor_events:
        if event.get("pass") is False and not denied:
            return fail_case("exploration_floor_fail_without_transition_deny")

    return pass_case(exploration_floor_events=len(floor_events), denials=len(denied))


def _c2_verify_cannot_be_skipped_when_dirty(ctx: TestExecutionContext):
    dirty_steps = {
        event.get("step_id")
        for event in _events(ctx, "TOOL_CALL")
        if isinstance(event.get("step_id"), int) and bool(event.get("files_written"))
    }
    if not dirty_steps:
        return pass_case(applicability="NOT_APPLICABLE", reason="no_workspace_writes")

    verifier_steps = {
        event.get("step_id")
        for event in _events(ctx, "VERIFIER_RESULT")
        if isinstance(event.get("step_id"), int) and event.get("pass") is True
    }

    if not verifier_steps:
        return fail_case("dirty_workspace_without_verify")

    if max(dirty_steps) > max(verifier_steps):
        return fail_case("write_after_last_verify_without_reverify")

    return pass_case(dirty_steps=len(dirty_steps), verifier_steps=len(verifier_steps))


def _c3_auto_advance_noise_rate(ctx: TestExecutionContext):
    denied = _events(ctx, "PHASE_TRANSITION_DENIED")
    transitions = _events(ctx, "PHASE_TRANSITION")
    if not denied:
        return pass_case(denial_noise_rate=0.0)

    denom = max(1, len(denied) + len(transitions))
    noise_rate = round(len(denied) / denom, 4)
    if noise_rate > 0.5:
        return fail_case("phase_transition_denied_noise_high", noise_rate=noise_rate)

    return pass_case(denial_noise_rate=noise_rate)


def _c4_universal_phase_transition_request_surface(ctx: TestExecutionContext):
    starts = _events(ctx, "run_START")
    if not starts:
        return fail_case("run_start_missing")

    surface = starts[-1].get("tool_surface_profile")
    if not isinstance(surface, Mapping):
        return fail_case("tool_surface_profile_missing")

    tools = surface.get("tools")
    if not isinstance(tools, list) or not tools:
        return fail_case("tool_surface_profile_tools_missing")
    if "request_phase_transition" not in tools:
        return fail_case("request_phase_transition_missing_from_surface")
    return pass_case(tool_count=len(tools))


def _c5_phase_tool_surface_coherence(ctx: TestExecutionContext):
    denials = _events(ctx, "PHASE_TRANSITION_DENIED")
    for denial in denials:
        reason = denial.get("deny_reason_code") or denial.get("reason")
        if reason in (None, ""):
            return fail_case("phase_transition_denied_missing_reason")

    for event in _events(ctx, "PHASE_TRANSITION"):
        if event.get("from_phase") in (None, "") or event.get("to_phase") in (None, ""):
            return fail_case("phase_transition_missing_phase_fields")

    return pass_case(phase_transitions=len(_events(ctx, "PHASE_TRANSITION")))


def list_tests() -> List[TestCase]:
    return [
        make_case(pack=PACK, test_id="C1", name="Exploration floor", objective="Implement transition is denied until exploration floor evidence passes.", required_event_types=["run_END"], checker=_c1_exploration_floor_enforced),
        make_case(pack=PACK, test_id="C2", name="Verify cannot be skipped", objective="Dirty workspace requires verifier pass before completion.", required_event_types=["run_END"], checker=_c2_verify_cannot_be_skipped_when_dirty),
        make_case(pack=PACK, test_id="C3", name="Auto-advance denial noise", objective="PHASE_TRANSITION_DENIED noise is bounded and explainable.", required_event_types=["run_END"], checker=_c3_auto_advance_noise_rate),
        make_case(pack=PACK, test_id="C4", name="Universal transition request", objective="request_phase_transition is always available in tool surface.", required_event_types=["run_START"], checker=_c4_universal_phase_transition_request_surface),
        make_case(pack=PACK, test_id="C5", name="Phase/tool coherence", objective="Phase transitions and denials remain deterministic and coherent.", required_event_types=["run_END"], checker=_c5_phase_tool_surface_coherence),
    ]
