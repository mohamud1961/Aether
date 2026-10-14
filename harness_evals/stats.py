"""Statistics for trial outcomes: pass@k, pass^k, confidence intervals, paired and unpaired tests, power.

Counts are exact integers. Binomial and hypergeometric terms use integer arithmetic, so the exact
tests are not affected by floating-point rounding until the final division. Functions here read no
files and keep no state; randomised functions take an explicit seed.

Conventions:
- A rate with zero trials is undefined. pass_at_k and pass_all_k raise ValueError for n == 0.
  wilson_interval returns the uninformative interval (0.0, 1.0) for zero trials.
- Two-sided p-values are returned as floats in [0, 1].
"""

from __future__ import annotations

import math
import random
from collections.abc import Sequence
from dataclasses import dataclass
from statistics import NormalDist

Outcome = int | bool


@dataclass(frozen=True)
class RateSummary:
    """A pass rate with its Wilson interval. rate is None when there are no trials."""

    successes: int
    trials: int
    rate: float | None
    low: float
    high: float


def pass_at_k(n: int, c: int, k: int) -> float:
    """Unbiased pass@k estimator (Chen et al., 2021): 1 - C(n-c, k) / C(n, k).

    n is the number of attempts on one task, c of which passed, and k is the draw size.
    The estimate is 1.0 whenever fewer than k attempts failed.
    """
    _check_draw(n, c, k)
    if n - c < k:
        return 1.0
    return 1.0 - math.comb(n - c, k) / math.comb(n, k)


def pass_all_k(n: int, c: int, k: int) -> float:
    """Unbiased pass^k estimator: the probability that all k drawn attempts pass, C(c, k) / C(n, k)."""
    _check_draw(n, c, k)
    return math.comb(c, k) / math.comb(n, k)


def wilson_interval(
    successes: int, trials: int, confidence: float = 0.95
) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion, two-sided at the given confidence."""
    _check_counts(successes, trials)
    _check_confidence(confidence)
    if trials == 0:
        return (0.0, 1.0)
    z = NormalDist().inv_cdf(0.5 + confidence / 2)
    z2 = z * z
    p = successes / trials
    denominator = 1 + z2 / trials
    centre = (p + z2 / (2 * trials)) / denominator
    half_width = (
        z * math.sqrt(p * (1 - p) / trials + z2 / (4 * trials * trials)) / denominator
    )
    return (max(0.0, centre - half_width), min(1.0, centre + half_width))


def summarize_rate(
    successes: int, trials: int, confidence: float = 0.95
) -> RateSummary:
    """Pass rate with its Wilson interval. The rate is None when trials is zero."""
    low, high = wilson_interval(successes, trials, confidence)
    rate = None if trials == 0 else successes / trials
    return RateSummary(
        successes=successes, trials=trials, rate=rate, low=low, high=high
    )


def mcnemar_exact_p(only_a: int, only_b: int) -> float:
    """Exact two-sided McNemar test for paired outcomes.

    only_a counts pairs where arm A passed and arm B failed; only_b counts the reverse. Under the
    null hypothesis the discordant pairs split as Binomial(only_a + only_b, 1/2).
    With no discordant pairs the test gives p = 1.0.
    """
    _check_nonnegative(only_a, only_b)
    n = only_a + only_b
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(min(only_a, only_b) + 1))
    return min(1.0, 2 * tail / 2**n)


def fisher_exact_two_sided(a: int, b: int, c: int, d: int) -> float:
    """Fisher exact test, two-sided, for the 2x2 table [[a, b], [c, d]].

    The p-value is the total hypergeometric probability of every table whose probability does not
    exceed the observed table's probability. The comparison is exact (integer weights), with no
    tolerance. An empty table (all zeros) gives p = 1.0.
    """
    _check_nonnegative(a, b, c, d)
    total = a + b + c + d
    if total == 0:
        return 1.0
    row_one = a + b
    col_one = a + c
    lowest = max(0, row_one - (total - col_one))
    highest = min(row_one, col_one)
    denominator = math.comb(total, row_one)
    weights = {
        x: math.comb(col_one, x) * math.comb(total - col_one, row_one - x)
        for x in range(lowest, highest + 1)
    }
    observed = weights[a]
    return (
        sum(weight for weight in weights.values() if weight <= observed) / denominator
    )


def bootstrap_rate_difference(
    outcomes_a: Sequence[Outcome],
    outcomes_b: Sequence[Outcome],
    *,
    iterations: int = 10_000,
    confidence: float = 0.95,
    seed: int = 0,
) -> tuple[float, float]:
    """Percentile bootstrap interval for rate(A) - rate(B) with independent samples.

    Each arm is resampled with replacement on its own. The same seed gives the same interval.
    Both arms need at least one trial.
    """
    a = [_as_bit(value) for value in outcomes_a]
    b = [_as_bit(value) for value in outcomes_b]
    if not a or not b:
        raise ValueError("bootstrap needs at least one trial in each arm")
    if iterations < 1:
        raise ValueError("iterations must be at least 1")
    _check_confidence(confidence)
    rng = random.Random(seed)
    diffs = sorted(
        sum(rng.choices(a, k=len(a))) / len(a) - sum(rng.choices(b, k=len(b))) / len(b)
        for _ in range(iterations)
    )
    alpha = 1 - confidence
    low_index = math.floor(alpha / 2 * iterations)
    high_index = min(iterations - 1, math.ceil((1 - alpha / 2) * iterations) - 1)
    return (diffs[low_index], diffs[high_index])


def sample_size_two_proportions(
    p1: float, p2: float, alpha: float = 0.05, power: float = 0.8
) -> int:
    """Trials per arm to detect p1 versus p2 with a two-sided two-proportion z-test (normal approximation).

    Uses n = ((z_a * sqrt(2 p̄ q̄) + z_b * sqrt(p1 q1 + p2 q2)) / (p1 - p2))^2, rounded up.
    """
    _check_proportions(p1, p2)
    _check_alpha_power(alpha, power)
    if p1 == p2:
        raise ValueError("p1 and p2 must differ")
    z_alpha = NormalDist().inv_cdf(1 - alpha / 2)
    z_beta = NormalDist().inv_cdf(power)
    pooled = (p1 + p2) / 2
    numerator = z_alpha * math.sqrt(2 * pooled * (1 - pooled)) + z_beta * math.sqrt(
        p1 * (1 - p1) + p2 * (1 - p2)
    )
    raw = (numerator / (p1 - p2)) ** 2
    return math.ceil(round(raw, 9))


def power_two_proportions(
    trials_per_arm: int, p1: float, p2: float, alpha: float = 0.05
) -> float:
    """Power of the two-sided two-proportion z-test at a given sample size (normal approximation)."""
    _check_proportions(p1, p2)
    _check_alpha_power(alpha, 0.5)
    if trials_per_arm < 1:
        raise ValueError("trials_per_arm must be at least 1")
    if p1 == p2:
        return alpha
    z_alpha = NormalDist().inv_cdf(1 - alpha / 2)
    pooled = (p1 + p2) / 2
    spread = math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))
    z = (
        abs(p1 - p2) * math.sqrt(trials_per_arm)
        - z_alpha * math.sqrt(2 * pooled * (1 - pooled))
    ) / spread
    return NormalDist().cdf(z)


def simulated_power_fisher(
    p1: float,
    p2: float,
    trials_per_arm: int,
    *,
    alpha: float = 0.05,
    sims: int = 2000,
    seed: int = 0,
) -> float:
    """Share of simulated experiments in which Fisher's exact test (two-sided) rejects at alpha.

    Each simulated arm draws trials_per_arm Bernoulli outcomes with the given pass probability.
    This is a check on the normal approximation, using the same test that compare reports.
    """
    _check_proportions(p1, p2)
    _check_alpha_power(alpha, 0.5)
    if trials_per_arm < 1 or sims < 1:
        raise ValueError("trials_per_arm and sims must be at least 1")
    rng = random.Random(seed)
    n = trials_per_arm
    rejections = 0
    for _ in range(sims):
        a = sum(rng.random() < p1 for _ in range(n))
        b = sum(rng.random() < p2 for _ in range(n))
        if fisher_exact_two_sided(a, n - a, b, n - b) < alpha:
            rejections += 1
    return rejections / sims


def _check_counts(successes: int, trials: int) -> None:
    if not isinstance(successes, int) or not isinstance(trials, int):
        raise ValueError("counts must be integers")
    if successes < 0 or trials < 0:
        raise ValueError("counts must not be negative")
    if successes > trials:
        raise ValueError(f"successes ({successes}) cannot exceed trials ({trials})")


def _check_nonnegative(*values: int) -> None:
    if not all(isinstance(value, int) for value in values):
        raise ValueError("counts must be integers")
    if any(value < 0 for value in values):
        raise ValueError("counts must not be negative")


def _check_draw(n: int, c: int, k: int) -> None:
    if not all(isinstance(value, int) for value in (n, c, k)):
        raise ValueError("n, c and k must be integers")
    if n < 1:
        raise ValueError("pass@k needs at least one attempt (n >= 1)")
    if not 0 <= c <= n:
        raise ValueError(f"passes c={c} must be between 0 and n={n}")
    if not 1 <= k <= n:
        raise ValueError(f"k={k} must be between 1 and n={n}")


def _check_confidence(confidence: float) -> None:
    if not 0 < confidence < 1:
        raise ValueError("confidence must be strictly between 0 and 1")


def _check_proportions(p1: float, p2: float) -> None:
    for value in (p1, p2):
        if not 0 <= value <= 1:
            raise ValueError("proportions must be between 0 and 1")


def _check_alpha_power(alpha: float, power: float) -> None:
    if not 0 < alpha < 1:
        raise ValueError("alpha must be strictly between 0 and 1")
    if not 0 < power < 1:
        raise ValueError("power must be strictly between 0 and 1")


def _as_bit(value: Outcome) -> int:
    if isinstance(value, bool) or value in (0, 1):
        return int(value)
    raise ValueError(f"outcome must be 0/1 or a bool, got {value!r}")


__all__ = [
    "RateSummary",
    "bootstrap_rate_difference",
    "fisher_exact_two_sided",
    "mcnemar_exact_p",
    "pass_all_k",
    "pass_at_k",
    "power_two_proportions",
    "sample_size_two_proportions",
    "simulated_power_fisher",
    "summarize_rate",
    "wilson_interval",
]
