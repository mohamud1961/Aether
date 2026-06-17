from __future__ import annotations

from runner.aether2.escalation import (
    EscalationDecision,
    apply_escalation,
    decide_escalation,
)


def test_escalation_is_inert_when_disabled_even_with_strong_signals() -> None:
    decision = decide_escalation(
        enabled=False,
        consecutive_no_progress_steps=10,
        verification_rounds_with_unresolved_relevant_evidence=10,
        current_route="base",
        escalation_route="heavy",
    )
    assert decision == EscalationDecision(escalate=False, target_route=None, reason_codes=())

    route = apply_escalation(
        {"provider": "base"},
        decision,
        escalation_route_config={"provider": "heavy"},
    )
    assert route == {"provider": "base"}


def test_easy_task_with_no_signals_stays_on_base_route_when_enabled() -> None:
    decision = decide_escalation(
        enabled=True,
        consecutive_no_progress_steps=0,
        verification_rounds_with_unresolved_relevant_evidence=0,
        current_route="base",
        escalation_route="heavy",
    )
    assert decision.escalate is False
    assert decision.target_route is None
    assert decision.reason_codes == ()


def test_repeated_no_progress_triggers_escalation_when_forced_on() -> None:
    decision = decide_escalation(
        enabled=True,
        consecutive_no_progress_steps=3,
        verification_rounds_with_unresolved_relevant_evidence=0,
        current_route="base",
        escalation_route="heavy",
        no_progress_threshold=3,
    )
    assert decision.escalate is True
    assert decision.target_route == "heavy"
    assert decision.reason_codes == ("repeated_no_progress",)

    route = apply_escalation(
        {"provider": "base"},
        decision,
        escalation_route_config={"provider": "heavy"},
    )
    assert route == {"provider": "heavy"}


def test_repeated_unresolved_verification_rounds_triggers_escalation_when_forced_on() -> None:
    decision = decide_escalation(
        enabled=True,
        consecutive_no_progress_steps=0,
        verification_rounds_with_unresolved_relevant_evidence=2,
        current_route="base",
        escalation_route="heavy",
        verification_round_threshold=2,
    )
    assert decision.escalate is True
    assert decision.target_route == "heavy"
    assert decision.reason_codes == ("repeated_unresolved_relevant_evidence",)


def test_already_on_escalation_route_does_not_re_escalate_but_reports_signals() -> None:
    decision = decide_escalation(
        enabled=True,
        consecutive_no_progress_steps=5,
        verification_rounds_with_unresolved_relevant_evidence=0,
        current_route="heavy",
        escalation_route="heavy",
    )
    assert decision.escalate is False
    assert decision.target_route is None
    assert decision.reason_codes == ("repeated_no_progress",)


def test_apply_escalation_without_escalation_route_config_returns_copy_unchanged() -> None:
    decision = EscalationDecision(escalate=True, target_route="heavy", reason_codes=("repeated_no_progress",))
    original = {"provider": "base"}
    route = apply_escalation(original, decision, escalation_route_config=None)
    assert route == {"provider": "base"}
    route["provider"] = "mutated"
    assert original == {"provider": "base"}
