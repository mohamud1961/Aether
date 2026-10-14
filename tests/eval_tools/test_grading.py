from __future__ import annotations

import shutil
import textwrap

import pytest

from harness_evals.grading import grade, grade_audited
from harness_evals.sandbox import LocalSandbox
from harness_evals.task import load_task

pytestmark = pytest.mark.skipif(shutil.which("python3.11") is None, reason="python3.11 not on PATH")


def _grader_task(make_task, body: str):
    return load_task(make_task(grader=textwrap.dedent(body)))


def _state(task, command: str | None = None):
    sandbox = LocalSandbox(task)
    if command is not None:
        assert sandbox.exec(command, timeout_s=10).code == 0
    return sandbox


def test_reference_state_passes_and_untouched_fails(make_task):
    task = load_task(make_task())
    good = _state(task, f"bash {task.reference_script}")
    bad = _state(task)
    try:
        passed = grade(task, good.root)
        failed = grade(task, bad.root)
    finally:
        good.close()
        bad.close()
    assert passed.passed is True and passed.score == 1.0
    assert passed.reasons == ("state_done",)
    assert passed.error is None
    assert failed.passed is False and failed.reasons == ("state_not_done",)
    assert failed.error is None
    assert len(passed.grader_hash) == 64


def test_grade_and_grade_audited_agree_on_the_example(example_task):
    task = load_task(example_task)
    sandbox = _state(task, "true")
    try:
        plain = grade(task, sandbox.root)
        audited, outside = grade_audited(task, sandbox.root)
    finally:
        sandbox.close()
    assert plain == audited
    assert outside == ()


def test_grader_is_run_with_the_workspace_argument(make_task):
    task = _grader_task(
        make_task,
        """\
        import json, sys
        from pathlib import Path
        present = (Path(sys.argv[1]) / "state.txt").is_file()
        print(json.dumps({"passed": present, "score": 1.0, "reasons": [sys.argv[1]]}))
        """,
    )
    sandbox = _state(task)
    try:
        result = grade(task, sandbox.root)
    finally:
        sandbox.close()
    assert result.passed is True
    assert result.reasons == (str(sandbox.root.resolve()),)


@pytest.mark.parametrize(
    "body, fragment",
    [
        ("print('not json at all')", "malformed grader output"),
        ("pass", "printed no output"),
        ("import json\nprint(json.dumps({'passed': 'yes', 'score': 1, 'reasons': []}))", "passed must be a boolean"),
        ("import json\nprint(json.dumps({'passed': True, 'score': 1, 'reasons': [], 'extra': 1}))", "keys must be exactly"),
        ("import json\nprint(json.dumps({'passed': True, 'score': True, 'reasons': []}))", "score must be a finite number"),
        ("import json\nprint(json.dumps({'passed': True, 'score': 1, 'reasons': [1]}))", "reasons must be a list of strings"),
        ("import json\nprint(json.dumps(['passed']))", "not a JSON object"),
        ("import json, sys\nprint(json.dumps({'passed': True, 'score': 1, 'reasons': []}))\nsys.exit(3)", "exited with code 3"),
        ("import time\ntime.sleep(30)", "timed out"),
    ],
)
def test_contract_breaks_are_failed_with_error(make_task, body, fragment):
    task = _grader_task(make_task, body)
    sandbox = _state(task)
    try:
        result = grade(task, sandbox.root, timeout_s=2)
    finally:
        sandbox.close()
    assert result.passed is False
    assert result.score == 0.0
    assert result.reasons == ()
    assert result.error is not None and fragment in result.error


def test_last_stdout_line_is_the_result(make_task):
    task = _grader_task(
        make_task,
        """\
        import json
        print("progress noise")
        print(json.dumps({"passed": False, "score": 0.5, "reasons": ["half_done"]}))
        """,
    )
    sandbox = _state(task)
    try:
        result = grade(task, sandbox.root)
    finally:
        sandbox.close()
    assert result.passed is False
    assert result.score == 0.5
    assert result.reasons == ("half_done",)
    assert result.error is None


def test_missing_grader_interpreter_is_an_error(make_task, monkeypatch):
    task = load_task(make_task())
    monkeypatch.setattr("harness_evals.grading.GRADER_INTERPRETER", "no-such-python-interpreter")
    sandbox = _state(task)
    try:
        result = grade(task, sandbox.root)
    finally:
        sandbox.close()
    assert result.passed is False
    assert "interpreter not found" in (result.error or "")


def test_audit_reports_reads_outside_the_workspace(make_task, tmp_path):
    secret = tmp_path / "outside_secret.txt"
    secret.write_text("not part of the workspace\n", encoding="utf-8")
    task = _grader_task(
        make_task,
        f"""\
        import json, sys
        from pathlib import Path
        Path({str(secret)!r}).read_text()
        print(json.dumps({{"passed": True, "score": 1.0, "reasons": ["read_outside"]}}))
        """,
    )
    sandbox = _state(task)
    try:
        result, outside = grade_audited(task, sandbox.root)
    finally:
        sandbox.close()
    assert result.passed is True
    assert str(secret) in outside


def test_audit_allows_reads_inside_workspace_and_grader_dir(make_task):
    task = _grader_task(
        make_task,
        """\
        import json, sys
        from pathlib import Path
        here = Path(__file__).resolve().parent
        Path(sys.argv[1], "state.txt").read_text()
        (here / "helper_data.txt").read_text()
        print(json.dumps({"passed": True, "score": 1.0, "reasons": []}))
        """,
    )
    (task.root / "grader" / "helper_data.txt").write_text("data\n", encoding="utf-8")
    sandbox = _state(task)
    try:
        _, outside = grade_audited(task, sandbox.root)
    finally:
        sandbox.close()
    assert outside == ()


def test_example_reference_state_is_graded_as_passing(example_task):
    task = load_task(example_task)
    sandbox = _state(task, f"bash {task.reference_script}")
    try:
        result = grade(task, sandbox.root)
    finally:
        sandbox.close()
    assert result.passed is True
    assert result.reasons == ("port_ok", "log_level_ok")
