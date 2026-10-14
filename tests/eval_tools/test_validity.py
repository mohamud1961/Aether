"""validate-graders must catch every broken grader below. A check that cannot fail is not a check."""

from __future__ import annotations

import shutil
import textwrap

import pytest

from harness_evals.validity import validate_task_dir, validate_tree
from eval_support import EXAMPLE_TASK, WRONG_STATE

pytestmark = pytest.mark.skipif(shutil.which("python3.11") is None, reason="python3.11 not on PATH")

ALWAYS_PASS = textwrap.dedent(
    """\
    import json
    print(json.dumps({"passed": True, "score": 1.0, "reasons": ["state_done"]}))
    """
)
ALWAYS_FAIL = textwrap.dedent(
    """\
    import json
    print(json.dumps({"passed": False, "score": 0.0, "reasons": ["nothing_matches"]}))
    """
)
NONCE = textwrap.dedent(
    """\
    import json, sys, time
    from pathlib import Path
    text = (Path(sys.argv[1]) / "state.txt").read_text().strip()
    passed = text == "done"
    print(json.dumps({"passed": passed, "score": 1.0 if passed else 0.0,
                      "reasons": ["state_done" if passed else "state_not_done", str(time.perf_counter_ns())]}))
    """
)
READS_OUTSIDE = textwrap.dedent(
    """\
    import json, sys
    from pathlib import Path
    text = (Path(sys.argv[1]) / "state.txt").read_text().strip()
    Path("/etc/hosts").read_text()
    passed = text == "done"
    print(json.dumps({"passed": passed, "score": 1.0 if passed else 0.0,
                      "reasons": ["state_done" if passed else "state_not_done"]}))
    """
)


def _checks(task_dir):
    return {violation.check for violation in validate_task_dir(task_dir).violations}


def test_example_task_is_clean(example_task):
    result = validate_task_dir(example_task)
    assert result.ok, result.violations
    assert result.known_bad_count == 2


def test_clean_synthetic_task_is_clean(make_task):
    assert validate_task_dir(make_task()).ok


def test_grader_that_passes_a_known_bad_is_a_violation(make_task):
    path = make_task(grader=ALWAYS_PASS)
    checks = _checks(path)
    assert "known_bad_passes" in checks
    assert "untouched_passes" in checks


def test_grader_that_fails_the_reference_is_a_violation(make_task):
    checks = _checks(make_task(grader=ALWAYS_FAIL))
    assert "reference_not_passing" in checks


def test_known_bad_with_wrong_expect_code_is_a_violation(make_task):
    path = make_task(known_bad={"wrong_state.sh": WRONG_STATE.replace("state_not_done", "some_other_code")})
    result = validate_task_dir(path)
    assert [v.check for v in result.violations] == ["known_bad_expect_missing"]
    assert "some_other_code" in result.violations[0].detail


def test_nondeterministic_grader_is_a_violation(make_task):
    checks = _checks(make_task(grader=NONCE))
    assert "grading_not_deterministic" in checks


def test_grader_reading_outside_the_workspace_is_a_violation(make_task):
    checks = _checks(make_task(grader=READS_OUTSIDE))
    assert "grader_reads_outside_workspace" in checks


def test_task_without_known_bads_is_a_violation(make_task):
    result = validate_task_dir(make_task(known_bad={}))
    assert [v.check for v in result.violations] == ["no_known_bads"]
    assert result.known_bad_count == 0


def test_failing_reference_script_is_a_violation(make_task):
    checks = _checks(make_task(reference="#!/usr/bin/env bash\nexit 4\n"))
    assert "reference_script_failed" in checks


def test_failing_known_bad_script_is_a_violation(make_task):
    path = make_task(known_bad={"broken.sh": "# expect: state_not_done\nexit 1\n"})
    assert "known_bad_script_failed" in _checks(path)


def test_task_that_does_not_load_is_a_violation(make_task):
    path = make_task()
    (path / "task.yaml").write_text("id: demo\n", encoding="utf-8")
    result = validate_task_dir(path)
    assert [v.check for v in result.violations] == ["task_load"]


def test_empty_tree_is_not_clean(tmp_path):
    report = validate_tree(tmp_path)
    assert report.tasks == ()
    assert report.ok is False


def test_tree_report_covers_every_task(make_task, tmp_path):
    make_task(task_id="good")
    make_task(task_id="bad", grader=ALWAYS_PASS)
    report = validate_tree(tmp_path / "tasks")
    by_id = {task.task_id: task for task in report.tasks}
    assert by_id["good"].ok
    assert not by_id["bad"].ok
    assert report.ok is False


def test_example_tree_root_is_found(example_task):
    report = validate_tree(EXAMPLE_TASK.parent)
    assert [task.task_id for task in report.tasks] == ["config_repair"]
    assert report.ok
