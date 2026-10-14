from __future__ import annotations

import random

import pytest

from harness_evals.stats import (
    bootstrap_rate_difference,
    fisher_exact_two_sided,
    mcnemar_exact_p,
    pass_all_k,
    pass_at_k,
    power_two_proportions,
    sample_size_two_proportions,
    simulated_power_fisher,
    summarize_rate,
    wilson_interval,
)


# pass@k and pass^k


@pytest.mark.parametrize(
    ("n", "c", "k", "expected"),
    [
        (5, 2, 1, 0.4),
        (5, 2, 2, 0.7),
        (10, 3, 5, 1 - 21 / 252),
        (5, 0, 3, 0.0),
        (5, 5, 3, 1.0),
        (5, 4, 2, 1.0),  # fewer failures than k: every draw of k contains a pass
        (1, 1, 1, 1.0),
        (1, 0, 1, 0.0),
    ],
)
def test_pass_at_k_known_values(n, c, k, expected):
    assert pass_at_k(n, c, k) == pytest.approx(expected, abs=1e-12)


def test_pass_at_1_is_the_plain_pass_rate():
    for n in range(1, 12):
        for c in range(n + 1):
            assert pass_at_k(n, c, 1) == pytest.approx(c / n, abs=1e-12)


def test_pass_at_k_is_unbiased_against_draw_simulation():
    # Estimator check: average over random k-subsets of attempts must match the closed form.
    n, c, k = 10, 4, 3
    population = [1] * c + [0] * (n - c)
    rng = random.Random(7)
    draws = 40_000
    observed = sum(max(rng.sample(population, k)) for _ in range(draws)) / draws
    assert observed == pytest.approx(pass_at_k(n, c, k), abs=0.01)
    # A biased plug-in (1 - (1 - c/n)^k) would give about 0.784 here, well outside the tolerance.
    assert abs(observed - (1 - (1 - c / n) ** k)) > 0.03


@pytest.mark.parametrize(
    ("n", "c", "k", "expected"),
    [
        (5, 2, 2, 0.1),
        (5, 5, 3, 1.0),
        (5, 2, 3, 0.0),
        (4, 3, 2, 0.5),
        (6, 4, 1, 4 / 6),
    ],
)
def test_pass_all_k_known_values(n, c, k, expected):
    assert pass_all_k(n, c, k) == pytest.approx(expected, abs=1e-12)


@pytest.mark.parametrize(
    "call",
    [
        lambda: pass_at_k(0, 0, 1),  # n = 0 has no estimate
        lambda: pass_all_k(0, 0, 1),
        lambda: pass_at_k(5, 6, 1),  # c > n
        lambda: pass_at_k(5, -1, 1),
        lambda: pass_at_k(5, 2, 0),  # k < 1
        lambda: pass_at_k(5, 2, 6),  # k > n
        lambda: pass_all_k(5, 2, 6),
        lambda: pass_at_k(5.0, 2, 1),  # not an integer
    ],
)
def test_pass_at_k_rejects_invalid_counts(call):
    with pytest.raises(ValueError):
        call()


# Wilson interval and rate summaries


def test_wilson_known_values():
    low, high = wilson_interval(8, 10)
    assert low == pytest.approx(0.4902, abs=5e-4)
    assert high == pytest.approx(0.9433, abs=5e-4)
    low, high = wilson_interval(1, 10)
    assert low == pytest.approx(0.0179, abs=5e-4)
    assert high == pytest.approx(0.4042, abs=5e-4)


def test_wilson_edges_stay_inside_unit_interval():
    low, high = wilson_interval(0, 10)
    assert low == 0.0 and 0.0 < high < 1.0
    low, high = wilson_interval(10, 10)
    assert high == 1.0 and 0.0 < low < 1.0


def test_wilson_with_no_trials_is_uninformative():
    assert wilson_interval(0, 0) == (0.0, 1.0)
    summary = summarize_rate(0, 0)
    assert summary.rate is None
    assert (summary.low, summary.high) == (0.0, 1.0)


def test_wilson_contains_the_observed_rate():
    for n in range(1, 40):
        for s in range(n + 1):
            low, high = wilson_interval(s, n)
            assert low - 1e-12 <= s / n <= high + 1e-12


def test_summarize_rate_reports_counts_and_rate():
    summary = summarize_rate(5, 9)
    assert (summary.successes, summary.trials) == (5, 9)
    assert summary.rate == pytest.approx(5 / 9)
    assert summary.low == pytest.approx(0.2667, abs=5e-4)
    assert summary.high == pytest.approx(0.8112, abs=5e-4)


def test_wilson_rejects_successes_above_trials():
    with pytest.raises(ValueError):
        wilson_interval(11, 10)


# Exact McNemar


def test_mcnemar_known_values():
    assert mcnemar_exact_p(10, 2) == pytest.approx(0.0385742, abs=1e-6)
    assert mcnemar_exact_p(7, 0) == pytest.approx(0.015625, abs=1e-12)
    assert mcnemar_exact_p(0, 7) == pytest.approx(0.015625, abs=1e-12)


def test_mcnemar_no_discordant_pairs_is_one():
    assert mcnemar_exact_p(0, 0) == 1.0


def test_mcnemar_single_discordant_pair_is_one():
    assert mcnemar_exact_p(1, 0) == 1.0


def test_mcnemar_balanced_discordance_is_one():
    assert mcnemar_exact_p(5, 5) == 1.0


def test_mcnemar_rejects_negative_counts():
    with pytest.raises(ValueError):
        mcnemar_exact_p(-1, 3)


# Fisher exact


def test_fisher_five_of_nine_versus_four_of_six_is_one():
    assert fisher_exact_two_sided(5, 4, 4, 2) == 1.0


def test_fisher_47_of_52_versus_42_of_52():
    assert fisher_exact_two_sided(47, 5, 42, 10) == pytest.approx(0.264, abs=5e-4)


def test_fisher_tea_tasting_table():
    assert fisher_exact_two_sided(3, 1, 1, 3) == pytest.approx(0.4857142857, abs=1e-9)


def test_fisher_perfect_separation_matches_hypergeometric_tail():
    # Two tails of 1/252 each.
    assert fisher_exact_two_sided(5, 0, 0, 5) == pytest.approx(2 / 252, abs=1e-12)


def test_fisher_is_symmetric_under_row_swap():
    assert fisher_exact_two_sided(47, 5, 42, 10) == pytest.approx(fisher_exact_two_sided(42, 10, 47, 5))


def test_fisher_empty_and_degenerate_tables_are_one():
    assert fisher_exact_two_sided(0, 0, 0, 0) == 1.0
    assert fisher_exact_two_sided(5, 0, 5, 0) == 1.0  # c = n in one arm, no spread in outcomes
    assert fisher_exact_two_sided(3, 3, 3, 3) == 1.0


def test_fisher_rejects_negative_cells():
    with pytest.raises(ValueError):
        fisher_exact_two_sided(1, -1, 1, 1)


# Bootstrap


def _outcomes(passes: int, n: int) -> list[int]:
    return [1] * passes + [0] * (n - passes)


def test_bootstrap_is_seeded_and_reproducible():
    a, b = _outcomes(7, 10), _outcomes(4, 10)
    first = bootstrap_rate_difference(a, b, iterations=2000, seed=3)
    second = bootstrap_rate_difference(a, b, iterations=2000, seed=3)
    assert first == second


def test_bootstrap_interval_for_clear_difference_excludes_zero():
    low, high = bootstrap_rate_difference(_outcomes(90, 100), _outcomes(10, 100), iterations=2000)
    assert low > 0.6
    assert low < 0.8 < high


def test_bootstrap_interval_for_identical_arms_straddles_zero():
    low, high = bootstrap_rate_difference(_outcomes(5, 10), _outcomes(5, 10), iterations=2000)
    assert low < 0 < high


def test_bootstrap_interval_contains_observed_difference():
    a, b = _outcomes(5, 9), _outcomes(4, 6)
    low, high = bootstrap_rate_difference(a, b, iterations=2000)
    assert low <= 5 / 9 - 4 / 6 <= high


def test_bootstrap_accepts_bools_and_rejects_other_values():
    low, high = bootstrap_rate_difference([True, False], [False, False], iterations=200)
    assert low <= high
    with pytest.raises(ValueError):
        bootstrap_rate_difference([2, 0], [1, 0], iterations=10)


def test_bootstrap_needs_trials_in_both_arms():
    with pytest.raises(ValueError):
        bootstrap_rate_difference([], [1, 0], iterations=10)
    with pytest.raises(ValueError):
        bootstrap_rate_difference([1, 0], [], iterations=10)


# Sample size and power


def test_sample_size_for_0_9_versus_0_7_is_62_per_arm():
    assert sample_size_two_proportions(0.9, 0.7, alpha=0.05, power=0.8) == 62


def test_sample_size_for_0_5_versus_0_6_is_388_per_arm():
    assert sample_size_two_proportions(0.5, 0.6) == 388


def test_sample_size_rejects_equal_or_out_of_range_proportions():
    with pytest.raises(ValueError):
        sample_size_two_proportions(0.5, 0.5)
    with pytest.raises(ValueError):
        sample_size_two_proportions(1.2, 0.5)


def test_power_at_the_computed_sample_size_meets_target():
    n = sample_size_two_proportions(0.9, 0.7)
    assert power_two_proportions(n, 0.9, 0.7) == pytest.approx(0.80, abs=0.01)
    assert power_two_proportions(n - 1, 0.9, 0.7) < 0.80 + 1e-9


def test_power_increases_with_sample_size():
    values = [power_two_proportions(n, 0.9, 0.7) for n in (10, 30, 62, 120)]
    assert values == sorted(values)
    assert values[0] < 0.5 < values[-1]


def test_power_without_difference_is_alpha():
    assert power_two_proportions(50, 0.6, 0.6, alpha=0.05) == 0.05


def test_simulated_power_agrees_with_normal_approximation():
    simulated = simulated_power_fisher(0.9, 0.7, 62, sims=2000, seed=0)
    normal = power_two_proportions(62, 0.9, 0.7)
    # Fisher's exact test is conservative, so the simulated power sits a little under the
    # normal-approximation value (observed 0.75 against 0.80). A gap larger than 0.1 means a bug.
    assert abs(simulated - normal) < 0.1
    assert simulated < normal


def test_simulated_power_is_low_for_small_samples():
    assert simulated_power_fisher(0.9, 0.7, 10, sims=2000, seed=0) < 0.2


def test_simulated_null_rejection_rate_is_at_most_alpha_plus_slack():
    rate = simulated_power_fisher(0.7, 0.7, 40, sims=2000, seed=1)
    assert rate <= 0.07


def test_simulated_power_is_reproducible():
    assert simulated_power_fisher(0.8, 0.6, 30, sims=300, seed=5) == simulated_power_fisher(
        0.8, 0.6, 30, sims=300, seed=5
    )
