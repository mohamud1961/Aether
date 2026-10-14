"""Trial rows against a sealed plan: refusals, invalid-row handling and the three verdicts."""

from __future__ import annotations

import pytest

from harness_evals import prereg_analysis
from harness_evals.prereg import PlanError
from prereg_support import make_project, numbered, read_seal, trial_rows, uniform, write_rows

ALL = ("alpha", "beta", "gamma")


def _analyze(project, outcomes):
    seal = read_seal(project.seal)
    rows = trial_rows(seal, outcomes)
    numbered_rows = numbered(rows)
    problems = prereg_analysis.validate_rows(seal, numbered_rows)
    assert problems == []
    return prereg_analysis.analyze(seal, numbered_rows), seal


def _grid(baseline: dict[str, list], candidate: dict[str, list]):
    outcomes = {}
    for task_id in ALL:
        outcomes[("baseline", task_id)] = baseline[task_id]
        outcomes[("candidate", task_id)] = candidate[task_id]
    return outcomes


def test_supported_when_candidate_wins_everywhere_and_the_interval_excludes_zero(tmp_path):
    project = make_project(tmp_path, k=10)
    outcomes = _grid(
        baseline={task: uniform(False, 10) for task in ALL},
        candidate={task: uniform(True, 10) for task in ALL},
    )
    analysis, _ = _analyze(project, outcomes)
    assert analysis.verdict == "SUPPORTED"
    assert analysis.candidate.rate == 1.0
    assert analysis.baseline.rate == 0.0
    assert analysis.diff == 1.0
    assert analysis.diff_low is not None and analysis.diff_low > 0
    assert analysis.sentinels[0].regressed is False


def test_falsified_when_candidate_is_not_above_baseline(tmp_path):
    project = make_project(tmp_path, k=10)
    outcomes = _grid(
        baseline={task: uniform(True, 10) for task in ALL},
        candidate={task: uniform(False, 10) for task in ALL},
    )
    analysis, _ = _analyze(project, outcomes)
    assert analysis.verdict == "FALSIFIED"
    assert analysis.reasons == ("falsifier holds: candidate_rate <= baseline_rate",)


def test_falsified_when_a_sentinel_regresses_even_if_the_overall_rate_improves(tmp_path):
    project = make_project(tmp_path, k=10)
    outcomes = _grid(
        baseline={"alpha": uniform(False, 10), "beta": uniform(False, 10), "gamma": uniform(True, 10)},
        candidate={
            "alpha": uniform(True, 10),
            "beta": uniform(True, 10),
            "gamma": [True] * 5 + [False] * 5,
        },
    )
    analysis, _ = _analyze(project, outcomes)
    assert analysis.candidate.rate is not None and analysis.baseline.rate is not None
    assert analysis.candidate.rate > analysis.baseline.rate
    assert analysis.verdict == "FALSIFIED"
    assert analysis.reasons == ("sentinel task(s) regressed: gamma",)
    assert analysis.sentinels[0].regressed is True


def test_inconclusive_when_the_difference_is_too_small_to_clear_the_bar(tmp_path):
    project = make_project(tmp_path, k=2)
    outcomes = _grid(
        baseline={"alpha": [True, False], "beta": [False, False], "gamma": [True, False]},
        candidate={"alpha": [True, True], "beta": [False, False], "gamma": [True, False]},
    )
    analysis, _ = _analyze(project, outcomes)
    assert analysis.candidate.passes == 3 and analysis.candidate.valid == 6
    assert analysis.baseline.passes == 2 and analysis.baseline.valid == 6
    assert analysis.diff_low is not None and analysis.diff_low <= 0
    assert analysis.verdict == "INCONCLUSIVE"
    assert analysis.reasons[0].startswith("promotion bar not met")


def test_invalid_rows_are_excluded_from_rates_and_counted_by_reason(tmp_path):
    project = make_project(tmp_path, k=10)
    outcomes = _grid(
        baseline={task: uniform(False, 10) for task in ALL},
        candidate={
            "alpha": [True] * 8 + [None, None],
            "beta": uniform(True, 10),
            "gamma": uniform(True, 10),
        },
    )
    analysis, _ = _analyze(project, outcomes)
    assert analysis.candidate.valid == 28
    assert analysis.candidate.passes == 28
    assert analysis.candidate.invalid == 2
    assert analysis.candidate.invalid_reasons == (("provider_error", 2),)
    assert analysis.verdict == "SUPPORTED"


def test_inconclusive_when_an_arm_has_no_valid_trials(tmp_path):
    project = make_project(tmp_path, k=2)
    outcomes = _grid(
        baseline={task: uniform(False, 2) for task in ALL},
        candidate={task: uniform(None, 2) for task in ALL},
    )
    analysis, _ = _analyze(project, outcomes)
    assert analysis.verdict == "INCONCLUSIVE"
    assert analysis.reasons[0] == "arm 'candidate' has no valid trials"
    assert analysis.diff is None


def test_inconclusive_when_a_sentinel_has_no_valid_trials_in_one_arm(tmp_path):
    project = make_project(tmp_path, k=2)
    outcomes = _grid(
        baseline={task: uniform(False, 2) for task in ALL},
        candidate={"alpha": uniform(True, 2), "beta": uniform(True, 2), "gamma": uniform(None, 2)},
    )
    analysis, _ = _analyze(project, outcomes)
    assert analysis.verdict == "INCONCLUSIVE"
    assert analysis.reasons == ("sentinel 'gamma' has no valid trials in one arm",)


def test_render_puts_the_verdict_first_and_shows_the_numbers(tmp_path):
    project = make_project(tmp_path, k=10)
    outcomes = _grid(
        baseline={task: uniform(False, 10) for task in ALL},
        candidate={task: uniform(True, 10) for task in ALL},
    )
    analysis, seal = _analyze(project, outcomes)
    text = prereg_analysis.render(analysis, seal)
    lines = text.splitlines()
    assert lines[0] == "SUPPORTED"
    assert "candidate candidate: 30/30 = 1.0000" in text
    assert "baseline baseline: 0/30 = 0.0000" in text
    assert "gamma: baseline 0.0000 candidate 1.0000 -> ok" in text


def test_clean_rows_have_no_validation_problems(tmp_path):
    project = make_project(tmp_path, k=2)
    seal = read_seal(project.seal)
    rows = trial_rows(seal, _grid({t: uniform(True, 2) for t in ALL}, {t: uniform(False, 2) for t in ALL}))
    assert prereg_analysis.validate_rows(seal, numbered(rows)) == []


def _problems(project, k_rows_mutator):
    seal = read_seal(project.seal)
    rows = trial_rows(seal, _grid({t: uniform(True, 2) for t in ALL}, {t: uniform(False, 2) for t in ALL}))
    rows = k_rows_mutator(seal, rows)
    return prereg_analysis.validate_rows(seal, numbered(rows))


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (lambda seal, rows: [dict(row, prereg_hash="f" * 64) if i == 0 else row for i, row in enumerate(rows)],
         "prereg_hash is not the sealed hash"),
        (lambda seal, rows: [dict(row, task_hash="f" * 64) if row["task_id"] == "alpha" else row for row in rows],
         "task_hash for 'alpha' differs"),
        (lambda seal, rows: [dict(row, grader_hash="f" * 64) if row["task_id"] == "beta" else row for row in rows],
         "grader_hash for 'beta' differs"),
        (lambda seal, rows: rows[1:], "expected exactly 2"),
        (lambda seal, rows: rows + [dict(rows[0])], "repeats"),
        (lambda seal, rows: [dict(row, attempt=3) if i == 0 else row for i, row in enumerate(rows)],
         "outside 1..2"),
        (lambda seal, rows: [dict(row, arm="surprise") if i == 0 else row for i, row in enumerate(rows)],
         "arm 'surprise' is not in the plan"),
        (lambda seal, rows: [dict(row, task_id="zeta") if i == 0 else row for i, row in enumerate(rows)],
         "task 'zeta' is not in the plan"),
        (lambda seal, rows: [dict(row, arm=["baseline"]) if i == 0 else row for i, row in enumerate(rows)],
         "arm and task_id must be strings"),
        (lambda seal, rows: [dict(row, passed="yes") if i == 0 else row for i, row in enumerate(rows)],
         "must be booleans"),
        (lambda seal, rows: [{key: value for key, value in row.items() if key != "grader_hash"} if i == 0 else row
                             for i, row in enumerate(rows)],
         "missing fields ['grader_hash']"),
    ],
)
def test_rows_that_do_not_match_the_seal_are_refused(tmp_path, mutate, expected):
    project = make_project(tmp_path, k=2)
    problems = _problems(project, mutate)
    assert any(expected in problem for problem in problems), problems


def test_load_rows_reports_non_json_lines_and_keeps_good_ones(tmp_path):
    project = make_project(tmp_path, k=2)
    seal = read_seal(project.seal)
    rows = trial_rows(seal, _grid({t: uniform(True, 2) for t in ALL}, {t: uniform(False, 2) for t in ALL}))
    write_rows(project.trials, rows)
    with project.trials.open("a", encoding="utf-8") as handle:
        handle.write("not json\n[1, 2]\n")
    loaded, problems = prereg_analysis.load_rows(project.trials)
    assert len(loaded) == len(rows)
    assert problems == ["line 13: not JSON (Expecting value)", "line 14: not a JSON object"]


def test_load_rows_refuses_a_missing_file(tmp_path):
    with pytest.raises(PlanError, match="cannot read trials"):
        prereg_analysis.load_rows(tmp_path / "absent.jsonl")
