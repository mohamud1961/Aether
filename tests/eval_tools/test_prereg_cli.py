"""The prereg command: exit codes and output for seal, check and analyze."""

from __future__ import annotations

from harness_evals.cli import main
from prereg_support import SEALED_AT, make_project, numbered, read_seal, trial_rows, uniform, write_rows
from harness_evals import prereg_analysis

ALL = ("alpha", "beta", "gamma")


def _outcomes(baseline: bool, candidate: bool | None, k: int):
    outcomes = {}
    for task_id in ALL:
        outcomes[("baseline", task_id)] = uniform(baseline, k)
        outcomes[("candidate", task_id)] = uniform(candidate, k)
    return outcomes


def _write_trials(project, outcomes):
    seal = read_seal(project.seal)
    write_rows(project.trials, trial_rows(seal, outcomes))


def test_seal_writes_the_default_seal_file_and_exits_zero(tmp_path, capsys):
    project = make_project(tmp_path)
    project.seal.unlink()
    code = main(["prereg", "seal", str(project.plan), "--at", SEALED_AT])
    assert code == 0
    assert project.seal.exists()
    out = capsys.readouterr().out
    assert "prereg_hash" in out


def test_seal_refuses_a_bad_timestamp_with_exit_one(tmp_path, capsys):
    project = make_project(tmp_path)
    project.seal.unlink()
    code = main(["prereg", "seal", str(project.plan), "--at", "yesterday", "--seal", str(project.seal)])
    assert code == 1
    assert "ISO 8601" in capsys.readouterr().err
    assert not project.seal.exists()


def test_check_passes_then_fails_listing_the_change(tmp_path, capsys):
    project = make_project(tmp_path, k=10)
    assert main(["prereg", "check", str(project.plan)]) == 0
    assert capsys.readouterr().out.startswith("OK: plan matches its seal")

    project.plan.write_text(project.plan.read_text().replace("k: 10", "k: 9"), encoding="utf-8")
    code = main(["prereg", "check", str(project.plan)])
    err = capsys.readouterr().err
    assert code == 1
    assert "CHANGED: plan no longer matches its seal" in err
    assert "setting k: sealed 10, now 9" in err


def test_check_without_a_seal_exits_one(tmp_path, capsys):
    project = make_project(tmp_path)
    project.seal.unlink()
    assert main(["prereg", "check", str(project.plan)]) == 1
    assert "no seal" in capsys.readouterr().err


def test_analyze_supported_exits_zero_and_prints_the_verdict(tmp_path, capsys):
    project = make_project(tmp_path, k=10)
    _write_trials(project, _outcomes(baseline=False, candidate=True, k=10))
    code = main(["prereg", "analyze", str(project.plan), "--trials", str(project.trials)])
    out = capsys.readouterr().out
    assert code == 0
    assert out.splitlines()[0] == "SUPPORTED"
    assert "difference (candidate - baseline): 1.0000" in out


def test_analyze_falsified_exits_two(tmp_path, capsys):
    project = make_project(tmp_path, k=10)
    _write_trials(project, _outcomes(baseline=True, candidate=False, k=10))
    code = main(["prereg", "analyze", str(project.plan), "--trials", str(project.trials)])
    assert code == 2
    assert capsys.readouterr().out.splitlines()[0] == "FALSIFIED"


def test_analyze_inconclusive_exits_three(tmp_path, capsys):
    project = make_project(tmp_path, k=2)
    outcomes = {
        ("baseline", "alpha"): [True, False],
        ("baseline", "beta"): [False, False],
        ("baseline", "gamma"): [True, False],
        ("candidate", "alpha"): [True, True],
        ("candidate", "beta"): [False, False],
        ("candidate", "gamma"): [True, False],
    }
    _write_trials(project, outcomes)
    code = main(["prereg", "analyze", str(project.plan), "--trials", str(project.trials)])
    assert code == 3
    assert capsys.readouterr().out.splitlines()[0] == "INCONCLUSIVE"


def test_analyze_refuses_when_the_plan_changed_and_prints_no_verdict(tmp_path, capsys):
    project = make_project(tmp_path, k=10)
    _write_trials(project, _outcomes(baseline=False, candidate=True, k=10))
    (project.tasks_dir / "alpha" / "grader" / "grade.py").write_text("print('{}')\n", encoding="utf-8")
    code = main(["prereg", "analyze", str(project.plan), "--trials", str(project.trials)])
    captured = capsys.readouterr()
    assert code == 1
    assert "SUPPORTED" not in captured.out and "SUPPORTED" not in captured.err
    assert "task alpha: grader changed" in captured.err


def test_analyze_refuses_rows_that_do_not_match_the_seal(tmp_path, capsys):
    project = make_project(tmp_path, k=10)
    seal = read_seal(project.seal)
    rows = trial_rows(seal, _outcomes(baseline=False, candidate=True, k=10))
    rows[0]["prereg_hash"] = "0" * 64
    write_rows(project.trials, rows)
    code = main(["prereg", "analyze", str(project.plan), "--trials", str(project.trials)])
    captured = capsys.readouterr()
    assert code == 1
    assert "REFUSED: trial rows do not match the seal" in captured.err
    assert "prereg_hash is not the sealed hash" in captured.err
    assert "SUPPORTED" not in captured.out


def test_analyze_refuses_a_missing_trials_file(tmp_path, capsys):
    project = make_project(tmp_path)
    code = main(["prereg", "analyze", str(project.plan), "--trials", str(tmp_path / "none.jsonl")])
    assert code == 1
    assert "cannot read trials" in capsys.readouterr().err


def test_rows_module_round_trip_matches_the_command(tmp_path):
    project = make_project(tmp_path, k=10)
    _write_trials(project, _outcomes(baseline=False, candidate=True, k=10))
    seal = read_seal(project.seal)
    rows, problems = prereg_analysis.load_rows(project.trials)
    assert problems == []
    assert prereg_analysis.validate_rows(seal, rows) == []
    assert prereg_analysis.analyze(seal, numbered([row for _, row in rows])).verdict == "SUPPORTED"
