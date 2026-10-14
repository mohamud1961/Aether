"""Pre-registration plans and seals: validation, sealing, and detection of every kind of change."""

from __future__ import annotations

import hashlib
import json
import textwrap

import pytest

from harness_evals import prereg
from harness_evals.prereg import PlanError, parse_plan
from harness_evals.task import load_task, task_hash
from prereg_support import ARM_LINES, SEALED_AT, make_project, plan_yaml, read_seal
from eval_support import GOOD_GRADER, write_task


def test_seal_records_plan_hash_settings_arms_and_task_hashes(tmp_path):
    project = make_project(tmp_path, k=4)
    record = read_seal(project.seal)
    assert record["schema"] == prereg.SEAL_SCHEMA
    assert record["plan_sha256"] == hashlib.sha256(project.plan.read_bytes()).hexdigest()
    assert record["sealed_at"] == SEALED_AT
    assert record["settings"]["k"] == 4
    assert record["settings"]["sentinels"] == ["gamma"]
    assert record["arms"] == {"baseline": {"agent": "noop"}, "candidate": {"agent": "minimal"}}
    for task_id in ("alpha", "beta", "gamma"):
        task = load_task(project.tasks_dir / task_id)
        assert record["tasks"][task_id]["task_hash"] == task_hash(task)
        assert record["tasks"][task_id]["grader_hash"] == prereg.grader_hash(task)
    assert record["prereg_hash"] == prereg.record_hash(record)


def test_seal_does_not_overwrite_without_replace(tmp_path):
    project = make_project(tmp_path)
    with pytest.raises(PlanError, match="already exists"):
        prereg.seal(project.plan, at=SEALED_AT, seal_path=project.seal)
    replaced = prereg.seal(project.plan, at="2026-11-01T00:00:00+00:00", seal_path=project.seal, replace=True)
    assert replaced["sealed_at"] == "2026-11-01T00:00:00+00:00"


def test_seal_rejects_a_timestamp_that_is_not_iso(tmp_path):
    project = make_project(tmp_path)
    with pytest.raises(PlanError, match="ISO 8601"):
        prereg.seal(project.plan, at="next tuesday", seal_path=tmp_path / "other.json")


def test_unchanged_plan_passes_check(tmp_path):
    project = make_project(tmp_path)
    verification = prereg.verify(project.plan, project.seal)
    assert verification.ok
    assert verification.changes == ()


def test_plan_edit_is_listed_with_the_old_and_new_value(tmp_path):
    project = make_project(tmp_path, k=10)
    project.plan.write_text(project.plan.read_text().replace("k: 10", "k: 11"), encoding="utf-8")
    changes = prereg.verify(project.plan, project.seal).changes
    assert any(change.startswith("plan file changed") for change in changes)
    assert "setting k: sealed 10, now 11" in changes


def test_grader_edit_is_listed_for_that_task_only(tmp_path):
    project = make_project(tmp_path)
    grader = project.tasks_dir / "beta" / "grader" / "grade.py"
    grader.write_text(GOOD_GRADER + "\n# changed after sealing\n", encoding="utf-8")
    changes = prereg.verify(project.plan, project.seal).changes
    assert any(change.startswith("task beta: grader changed") for change in changes)
    assert any(change.startswith("task beta: task files changed") for change in changes)
    assert not any(change.startswith("task alpha") or change.startswith("task gamma") for change in changes)


def test_workspace_edit_changes_task_hash_but_not_grader_hash(tmp_path):
    project = make_project(tmp_path)
    (project.tasks_dir / "alpha" / "workspace" / "state.txt").write_text("edited\n", encoding="utf-8")
    changes = prereg.verify(project.plan, project.seal).changes
    assert any(change.startswith("task alpha: task files changed") for change in changes)
    assert not any("grader changed" in change for change in changes)


def test_every_changed_item_is_listed_together(tmp_path):
    project = make_project(tmp_path, k=10)
    project.plan.write_text(project.plan.read_text().replace("k: 10", "k: 12"), encoding="utf-8")
    (project.tasks_dir / "beta" / "grader" / "grade.py").write_text(GOOD_GRADER + "# v2\n", encoding="utf-8")
    (project.tasks_dir / "alpha" / "prompt.md").write_text("A different prompt.\n", encoding="utf-8")
    changes = prereg.verify(project.plan, project.seal).changes
    assert len(changes) >= 4
    assert any("setting k" in change for change in changes)
    assert any("task beta: grader changed" in change for change in changes)
    assert any("task alpha: task files changed" in change for change in changes)


def test_edited_arm_config_in_the_seal_is_detected(tmp_path):
    project = make_project(tmp_path)
    record = read_seal(project.seal)
    record["arms"]["candidate"]["agent"] = "noop"
    project.seal.write_text(json.dumps(record), encoding="utf-8")
    changes = prereg.verify(project.plan, project.seal).changes
    assert "arm candidate config agent: sealed 'noop', now 'minimal'" in changes
    assert any(change.startswith("seal record altered") for change in changes)


def test_edited_task_hash_in_the_seal_is_detected(tmp_path):
    project = make_project(tmp_path)
    record = read_seal(project.seal)
    record["tasks"]["alpha"]["task_hash"] = "0" * 64
    project.seal.write_text(json.dumps(record), encoding="utf-8")
    changes = prereg.verify(project.plan, project.seal).changes
    assert any(change.startswith("task alpha: task files changed") for change in changes)
    assert any(change.startswith("seal record altered") for change in changes)


def test_removed_task_directory_is_reported_as_unreadable(tmp_path):
    project = make_project(tmp_path)
    (project.tasks_dir / "beta" / "task.yaml").unlink()
    changes = prereg.verify(project.plan, project.seal).changes
    assert any(change.startswith("task ../tasks/beta: cannot load") for change in changes)
    assert "task beta: sealed but not readable now" in changes


def test_task_added_to_the_plan_is_listed(tmp_path):
    project = make_project(tmp_path)
    write_task(project.tasks_dir, task_id="delta")
    project.plan.write_text(
        project.plan.read_text().replace('  - "../tasks/gamma"', '  - "../tasks/gamma"\n  - "../tasks/delta"'),
        encoding="utf-8",
    )
    changes = prereg.verify(project.plan, project.seal).changes
    assert "task delta: added to plan" in changes


def test_missing_seal_is_a_refusal_not_a_pass(tmp_path):
    project = make_project(tmp_path)
    project.seal.unlink()
    with pytest.raises(PlanError, match="no seal"):
        prereg.verify(project.plan, project.seal)


def test_malformed_seal_field_is_a_change_not_a_crash(tmp_path):
    project = make_project(tmp_path)
    record = read_seal(project.seal)
    record["arms"] = ["not", "a", "mapping"]
    project.seal.write_text(json.dumps(record), encoding="utf-8")
    changes = prereg.verify(project.plan, project.seal).changes
    assert "seal field 'arms' is malformed" in changes


def test_valid_plan_parses_into_its_fields():
    plan = parse_plan(plan_yaml(k=3))
    assert plan.k == 3
    assert plan.baseline == "baseline" and plan.candidate == "candidate"
    assert plan.arms == {"baseline": {"agent": "noop"}, "candidate": {"agent": "minimal"}}
    assert plan.sentinels == ("gamma",)


@pytest.mark.parametrize(
    ("text", "message"),
    [
        (plan_yaml().replace("k: 10\n", ""), "missing keys"),
        (plan_yaml() + "extra: 1\n", "unknown keys"),
        (plan_yaml(arms=('  - "agent=noop"', '  - "name=candidate agent=minimal"')), "no name"),
        (plan_yaml(arms=('  - "name=baseline"', '  - "name=candidate"', '  - "name=third"')), "exactly two"),
        (plan_yaml(baseline="candidate"), "exactly two"),
        (plan_yaml(sentinels=("missing_task",)), "not in tasks"),
        (plan_yaml(sentinels=()), "non-empty"),
        (plan_yaml(k=0), "at least 1"),
        (plan_yaml().replace("k: 10", "k: true"), "at least 1"),
        (plan_yaml(primary="score"), "primary_metric"),
        (plan_yaml(falsifier="candidate_rate ~= baseline_rate"), "unknown operator"),
        (plan_yaml(promotion="diff > "), "operand operator operand"),
        (plan_yaml(tasks=("alpha", "alpha")), "same task directory name twice"),
        (plan_yaml(sentinels=("gamma", "gamma")), "twice"),
        (plan_yaml(arms=('  - "name=baseline agent=noop agent=x"', ARM_LINES[1])), "appears twice"),
    ],
)
def test_invalid_plans_are_refused(text, message):
    with pytest.raises(PlanError, match=message):
        parse_plan(text)


def test_plan_with_comments_and_block_layout_parses():
    text = textwrap.dedent(
        """\
        # a comment line
        question: "Is it better?"
        arms:
          - "name=baseline agent=noop"   # trailing comment
          - "name=candidate agent=minimal"
        baseline: baseline
        candidate: candidate
        tasks:
          - "../tasks/alpha"
        sentinels:
          - alpha
        k: 2
        primary_metric: pass_rate
        falsifier: "candidate_rate <= baseline_rate"
        promotion_bar: "diff_ci_low > 0"
        """
    )
    plan = parse_plan(text)
    assert plan.tasks == ("../tasks/alpha",)
    assert plan.k == 2
