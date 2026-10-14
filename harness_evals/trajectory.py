"""Trajectory analytics: tokens, cost, wall time, tool calls and action patterns per trial.

Inputs are plain values and action strings, so this module reads no trial rows and runs nothing.
Two action patterns are counted from an agent's action list:

- repeated actions: an identical action (after stripping surrounding whitespace) that occurs at
  least REPEAT_THRESHOLD times in one trial. The count is the number of occurrences of such
  actions, so ["ls", "ls", "ls", "cat a"] gives 3.
- idle waits: an action that is exactly `sleep N` with N >= IDLE_WAIT_MIN_S seconds. The count is
  the number of such actions and the total is the sum of their N.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

REPEAT_THRESHOLD = 3
IDLE_WAIT_MIN_S = 10.0

_SLEEP_ACTION = re.compile(r"sleep\s+(\d+(?:\.\d+)?)")


@dataclass(frozen=True)
class TrialMeasure:
    tokens_in: int
    tokens_out: int
    cost: float
    wall_s: float
    tool_calls: int
    repeated_actions: int
    idle_waits: int
    idle_wait_s: float


@dataclass(frozen=True)
class Distribution:
    count: int
    total: float
    mean: float | None
    median: float | None
    minimum: float | None
    maximum: float | None


@dataclass(frozen=True)
class TrajectorySummary:
    trials: int
    tokens_in: Distribution
    tokens_out: Distribution
    cost: Distribution
    wall_s: Distribution
    tool_calls: Distribution
    repeated_actions: Distribution
    idle_waits: Distribution

    def metrics(self) -> tuple[tuple[str, Distribution], ...]:
        return (
            ("tokens_in", self.tokens_in),
            ("tokens_out", self.tokens_out),
            ("cost", self.cost),
            ("wall_s", self.wall_s),
            ("tool_calls", self.tool_calls),
            ("repeated_actions", self.repeated_actions),
            ("idle_waits", self.idle_waits),
        )


def count_repeated_actions(
    actions: Sequence[str], threshold: int = REPEAT_THRESHOLD
) -> int:
    if threshold < 2:
        raise ValueError("threshold must be at least 2")
    counts = Counter(action.strip() for action in actions)
    return sum(count for count in counts.values() if count >= threshold)


def idle_waits(
    actions: Sequence[str], min_s: float = IDLE_WAIT_MIN_S
) -> tuple[int, float]:
    """Return (number of long sleep actions, total seconds they wait)."""
    count = 0
    total = 0.0
    for action in actions:
        match = _SLEEP_ACTION.fullmatch(action.strip())
        if match is None:
            continue
        seconds = float(match.group(1))
        if seconds >= min_s:
            count += 1
            total += seconds
    return count, total


def measure(
    *,
    tokens_in: int,
    tokens_out: int,
    cost: float,
    wall_s: float,
    tool_calls: int,
    actions: Sequence[str],
) -> TrialMeasure:
    waits, waited_s = idle_waits(actions)
    return TrialMeasure(
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost=cost,
        wall_s=wall_s,
        tool_calls=tool_calls,
        repeated_actions=count_repeated_actions(actions),
        idle_waits=waits,
        idle_wait_s=waited_s,
    )


def distribution(values: Sequence[float]) -> Distribution:
    if not values:
        return Distribution(
            count=0, total=0.0, mean=None, median=None, minimum=None, maximum=None
        )
    ordered = sorted(float(value) for value in values)
    count = len(ordered)
    middle = count // 2
    median = (
        ordered[middle] if count % 2 else (ordered[middle - 1] + ordered[middle]) / 2
    )
    total = sum(ordered)
    return Distribution(
        count=count,
        total=total,
        mean=total / count,
        median=median,
        minimum=ordered[0],
        maximum=ordered[-1],
    )


def summarize(measures: Sequence[TrialMeasure]) -> TrajectorySummary:
    return TrajectorySummary(
        trials=len(measures),
        tokens_in=distribution([m.tokens_in for m in measures]),
        tokens_out=distribution([m.tokens_out for m in measures]),
        cost=distribution([m.cost for m in measures]),
        wall_s=distribution([m.wall_s for m in measures]),
        tool_calls=distribution([m.tool_calls for m in measures]),
        repeated_actions=distribution([m.repeated_actions for m in measures]),
        idle_waits=distribution([m.idle_waits for m in measures]),
    )
