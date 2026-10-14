"""Detect progress stalls in tournament loops.

A score counts as progress only when it is strictly greater than the best score so far.
After 3 non-improving attempts the loop recommends a forced diagnostic; after 5 it recommends
pausing as blocked. This module is a pure function: it reads attempt records and recommends an
action, and runs nothing.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any

STALL_STATE_ACTIVE = "active"
STALL_STATE_ESCALATE = "escalate"
STALL_STATE_BLOCKED = "blocked"
STALL_STATE_INSUFFICIENT_SIGNAL = "insufficient_signal"

ACTION_CONTINUE = "continue"
ACTION_FORCE_DIAGNOSTIC = "force_diagnostic"
ACTION_PAUSE_BLOCKED = "pause_blocked"

ESCALATE_AFTER = 3  # non-improving attempts before a forced diagnostic
BLOCK_AFTER = 5  # non-improving attempts before the loop is paused as blocked


def _parse_score(value: Any) -> tuple[int, int] | None:
    if isinstance(value, str) and "/" in value:
        left, right = value.split("/", 1)
        try:
            numerator = int(left)
            denominator = int(right)
        except ValueError:
            return None
        return (numerator, denominator) if denominator > 0 else None
    if isinstance(value, dict):
        try:
            numerator = int(value.get("pass_count"))
            denominator = int(value.get("total"))
        except (TypeError, ValueError):
            return None
        return (numerator, denominator) if denominator > 0 else None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        frac = Fraction(value).limit_denominator(100)
        return frac.numerator, frac.denominator
    return None


def _score_label(score: tuple[int, int]) -> str:
    reduced = Fraction(score[0], score[1])
    return f"{reduced.numerator}/{reduced.denominator}"


def evaluate_target_gate_stall(attempts: list[dict[str, Any]]) -> dict[str, Any]:
    """Recommend an action from the ordered attempt history.

    A score counts as progress only when it is strictly greater than the best
    score so far. Attempts without a parseable score are ignored and listed.
    """
    parsed_scores: list[tuple[int, int]] = []
    ignored_attempt_indices: list[int] = []
    for index, attempt in enumerate(attempts):
        score = (
            _parse_score(attempt.get("target_gate"))
            or _parse_score(attempt.get("best_target_gate_score"))
            or _parse_score(attempt.get("target_gate_score"))
        )
        if score is None:
            ignored_attempt_indices.append(index)
            continue
        parsed_scores.append(score)
    if not parsed_scores:
        return {
            "stall_state": STALL_STATE_INSUFFICIENT_SIGNAL,
            "recommended_action": ACTION_CONTINUE,
            "parsed_attempt_count": 0,
            "ignored_attempt_indices": ignored_attempt_indices,
            "no_progress_iterations": 0,
            "best_target_gate_score": "",
        }
    best = parsed_scores[0]
    no_progress_iterations = 0
    for score in parsed_scores[1:]:
        if Fraction(score[0], score[1]) > Fraction(best[0], best[1]):
            best = score
            no_progress_iterations = 0
        else:
            no_progress_iterations += 1
    state = STALL_STATE_ACTIVE
    action = ACTION_CONTINUE
    if no_progress_iterations >= BLOCK_AFTER:
        state = STALL_STATE_BLOCKED
        action = ACTION_PAUSE_BLOCKED
    elif no_progress_iterations >= ESCALATE_AFTER:
        state = STALL_STATE_ESCALATE
        action = ACTION_FORCE_DIAGNOSTIC
    return {
        "stall_state": state,
        "recommended_action": action,
        "parsed_attempt_count": len(parsed_scores),
        "ignored_attempt_indices": ignored_attempt_indices,
        "no_progress_iterations": no_progress_iterations,
        "best_target_gate_score": _score_label(best),
    }
