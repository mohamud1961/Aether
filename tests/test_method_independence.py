from aether.method_independence import (
    executed_observed_implementations,
    overlapping_accumulator_problem,
)


def test_direct_execution_of_observed_implementation_is_detected() -> None:
    command = "python3 /app/analyzer.py /app/input.bin && cat /app/output.txt"
    assert executed_observed_implementations(
        command, ("/app/analyzer.py", "/app/output.txt")
    ) == ("/app/analyzer.py",)


def test_reading_observed_artifact_is_not_execution_reuse() -> None:
    command = "python3 - <<'PY'\nfrom pathlib import Path\nprint(Path('/app/analyzer.py').read_text())\nPY"
    assert executed_observed_implementations(command, ("/app/analyzer.py",)) == ()


def test_overlapping_accumulator_detects_named_bucket_double_update() -> None:
    command = """python3 - <<'PY'
periods = {'recent': (1, 2), 'total': (0, 2)}
counts = {p: {'ERROR': 0} for p in periods}
severity = 'ERROR'
counts['total'][severity] += 1
for period, bounds in periods.items():
    counts[period][severity] += 1
PY"""
    problem = overlapping_accumulator_problem(command)
    assert "updates bucket 'total' directly" in problem


def test_non_overlapping_accumulator_is_accepted() -> None:
    command = """python3 - <<'PY'
periods = {'recent': (1, 2), 'total': (0, 2)}
counts = {p: {'ERROR': 0} for p in periods}
severity = 'ERROR'
for period, bounds in periods.items():
    counts[period][severity] += 1
PY"""
    assert overlapping_accumulator_problem(command) == ""
