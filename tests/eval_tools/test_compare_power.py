from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness_evals.cli import build_parser, main
from harness_evals.commands.compare import Side, Trial, compare_sides


def _row(arm: str, task_id: str, passed: bool | None, *, attempt: int = 1, valid: bool = True) -> dict:
    return {"arm": arm, "task_id": task_id, "attempt": attempt, "valid": valid, "passed": passed}


def _write(path: Path, rows: list[dict]) -> Path:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return path


def _nine_vs_six_rows() -> list[dict]:
    # Arm A: 5 of 9 pass. Arm B: 4 of 6 pass on the first six tasks, plus one invalid row.
    rows = [_row("A", f"t{i}", i < 5) for i in range(9)]
    rows += [_row("B", f"t{i}", i < 4) for i in range(6)]
    rows.append(_row("B", "t9", True, valid=False))
    return rows


def test_compare_and_power_are_discovered_as_subcommands():
    parser = build_parser()
    subparsers = next(action for action in parser._actions if action.choices)  # noqa: SLF001
    assert {"compare", "power"} <= set(subparsers.choices)


def test_compare_reproduces_fisher_and_mcnemar_on_nine_vs_six(tmp_path, capsys):
    path = _write(tmp_path / "two_arms.jsonl", _nine_vs_six_rows())
    assert main(["compare", str(path), "--iterations", "500"]) == 0
    out = capsys.readouterr().out
    assert "arm A" in out and "rows 9, valid 9, excluded 0" in out
    assert "arm B" in out and "rows 7, valid 6, excluded 1" in out
    assert "pass rate: 0.556 (5/9)" in out
    assert "pass rate: 0.667 (4/6)" in out
    assert "unpaired Fisher exact, two-sided p = 1.0000" in out
    assert "paired trials (same task and attempt, valid in both arms): 6" in out
    assert "both pass 4, both fail 1, A only 1, B only 0" in out
    assert "paired exact McNemar, two-sided p = 1.0000" in out
    assert "NO DETECTABLE DIFFERENCE" in out


def test_compare_reports_a_difference_when_the_pairs_are_one_sided(tmp_path, capsys):
    rows = [_row("strong", f"t{i}", True) for i in range(20)] + [_row("weak", f"t{i}", False) for i in range(20)]
    path = _write(tmp_path / "one_sided.jsonl", rows)
    assert main(["compare", str(path), "--arm-a", "strong", "--arm-b", "weak", "--iterations", "500"]) == 0
    out = capsys.readouterr().out
    assert "both pass 0, both fail 0, A only 20, B only 0" in out
    assert "paired exact McNemar, two-sided p = <0.0001" in out
    assert "DIFFERENCE: strong passes more often" in out


def test_invalid_rows_never_enter_the_rates(tmp_path, capsys):
    rows = [_row("A", "t0", True), _row("A", "t1", False, valid=False), _row("B", "t0", False)]
    path = _write(tmp_path / "invalid.jsonl", rows)
    assert main(["compare", str(path), "--iterations", "100"]) == 0
    out = capsys.readouterr().out
    assert "arm A\n  rows 2, valid 1, excluded 1" in out
    assert "pass rate: 1.000 (1/1)" in out


def test_compare_two_single_arm_files(tmp_path, capsys):
    first = _write(tmp_path / "left.jsonl", [_row("base", f"t{i}", i < 3) for i in range(5)])
    second = _write(tmp_path / "right.jsonl", [_row("candidate", f"t{i}", i < 2) for i in range(5)])
    assert main(["compare", str(first), str(second), "--iterations", "100"]) == 0
    out = capsys.readouterr().out
    assert "arm base\n" in out and "arm candidate\n" in out
    assert "pass rate: 0.600 (3/5)" in out and "pass rate: 0.400 (2/5)" in out


def test_identical_arm_names_across_files_are_disambiguated(tmp_path, capsys):
    first = _write(tmp_path / "one.jsonl", [_row("same", "t0", True)])
    second = _write(tmp_path / "two.jsonl", [_row("same", "t0", False)])
    assert main(["compare", str(first), str(second), "--iterations", "100"]) == 0
    out = capsys.readouterr().out
    assert "arm same (one.jsonl)" in out and "arm same (two.jsonl)" in out


def test_pass_at_k_and_pass_all_k_per_task(tmp_path, capsys):
    # t0 has attempts [pass, fail]; t1 has [fail, fail]; t2 has one attempt and is skipped at k=2.
    rows = [
        _row("A", "t0", True, attempt=1),
        _row("A", "t0", False, attempt=2),
        _row("A", "t1", False, attempt=1),
        _row("A", "t1", False, attempt=2),
        _row("A", "t2", True, attempt=1),
        _row("B", "t0", False, attempt=1),
        _row("B", "t0", False, attempt=2),
        _row("B", "t1", False, attempt=1),
        _row("B", "t1", False, attempt=2),
        _row("B", "t2", False, attempt=1),
    ]
    path = _write(tmp_path / "per_task.jsonl", rows)
    assert main(["compare", str(path), "--k", "2", "--iterations", "100"]) == 0
    out = capsys.readouterr().out
    # pass@2: t0 -> 1.0, t1 -> 0.0; mean 0.500. pass^2: t0 -> 0.0, t1 -> 0.0; mean 0.000.
    assert "pass@2 0.500, pass^2 0.000 (mean over 2 tasks; 1 task skipped, each needs 2 valid attempts)" in out


def test_compare_arms_from_a_summary_side(tmp_path):
    side_a = Side("A", tuple(Trial("A", f"t{i}", 1, True, i < 5) for i in range(9)))
    side_b = Side("B", tuple(Trial("B", f"t{i}", 1, True, i < 4) for i in range(6)))
    comparison = compare_sides(side_a, side_b, iterations=200)
    assert comparison.fisher_p == pytest.approx(1.0)
    assert comparison.paired is not None and comparison.paired.pairs == 6
    assert comparison.verdict.startswith("NO DETECTABLE DIFFERENCE")


def test_compare_with_no_valid_trial_in_one_arm_is_inconclusive(tmp_path, capsys):
    rows = [_row("A", "t0", True), _row("B", "t0", True, valid=False)]
    path = _write(tmp_path / "empty_arm.jsonl", rows)
    assert main(["compare", str(path), "--iterations", "100"]) == 0
    assert "INCONCLUSIVE: one arm has no valid trials" in capsys.readouterr().out


def test_compare_with_no_shared_task_is_inconclusive_for_mcnemar(tmp_path, capsys):
    rows = [_row("A", "t0", True), _row("B", "t1", False)]
    path = _write(tmp_path / "unpaired.jsonl", rows)
    assert main(["compare", str(path), "--iterations", "100"]) == 0
    out = capsys.readouterr().out
    assert "paired trials (same task and attempt, valid in both arms): 0" in out
    assert "INCONCLUSIVE: no task and attempt has valid trials in both arms" in out


@pytest.mark.parametrize(
    ("rows", "extra_args", "message"),
    [
        ([_row("A", "t0", True), _row("B", "t0", True), _row("C", "t0", True)], [], "holds arms"),
        ([_row("A", "t0", True), _row("A", "t0", False)], ["--arm-a", "A", "--arm-b", "A"], "must name different arms"),
        ([_row("A", "t0", True), _row("A", "t1", False)], ["--arm-a", "A", "--arm-b", "B"], "arm 'B' not found"),
        ([_row("A", "t0", True), _row("B", "t0", True), _row("B", "t0", False)], [], "duplicate trial"),
        ([{"arm": "A", "task_id": "t0", "attempt": 1, "passed": True}], [], "missing field 'valid'"),
        ([{"arm": "A", "task_id": "t0", "attempt": 1, "valid": True, "passed": None}], [], "passed set to true or false"),
        ([{"arm": "A", "task_id": "t0", "attempt": "1", "valid": True, "passed": True}], [], "attempt must be an integer"),
        ([_row("A", "t0", True), _row("B", "t0", True)], ["--arm-a", "A"], "give both --arm-a and --arm-b"),
    ],
)
def test_malformed_or_ambiguous_input_exits_with_status_2(tmp_path, capsys, rows, extra_args, message):
    path = _write(tmp_path / "bad.jsonl", rows)
    assert main(["compare", str(path), *extra_args]) == 2
    assert message in capsys.readouterr().err


def test_unknown_arm_name_exits_with_status_2(tmp_path, capsys):
    path = _write(tmp_path / "two.jsonl", [_row("A", "t0", True), _row("B", "t0", False)])
    assert main(["compare", str(path), "--arm-a", "A", "--arm-b", "Z"]) == 2
    assert "arm 'Z' not found" in capsys.readouterr().err


def test_invalid_json_line_exits_with_status_2(tmp_path, capsys):
    path = tmp_path / "broken.jsonl"
    path.write_text('{"arm": "A"\n', encoding="utf-8")
    assert main(["compare", str(path)]) == 2
    assert "invalid JSON" in capsys.readouterr().err


def test_three_files_are_rejected(tmp_path, capsys):
    paths = [_write(tmp_path / f"{name}.jsonl", [_row(name, "t0", True)]) for name in ("x", "y", "z")]
    assert main(["compare", *map(str, paths)]) == 2
    assert "one trial file with two arms, or two single-arm trial files" in capsys.readouterr().err


def test_power_prints_trials_per_arm_for_0_9_versus_0_7(capsys):
    assert main(["power", "--p1", "0.9", "--p2", "0.7", "--sims", "400"]) == 0
    out = capsys.readouterr().out
    assert "trials per arm (normal approximation): 62" in out
    assert "normal-approximation power at 62 per arm: 0.803" in out
    assert "simulated power at 62 per arm" in out


def test_power_rejects_equal_proportions(capsys):
    assert main(["power", "--p1", "0.5", "--p2", "0.5"]) == 2
    assert "p1 and p2 must differ" in capsys.readouterr().err


def test_power_rejects_out_of_range_proportion(capsys):
    assert main(["power", "--p1", "1.5", "--p2", "0.5"]) == 2
    assert "between 0 and 1" in capsys.readouterr().err
