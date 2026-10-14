from __future__ import annotations

import pytest

from harness_evals.task import TaskFormatError, discover, find_task_dirs, load_task, task_hash
from eval_support import default_yaml, write_task


def test_example_task_loads_every_field(example_task):
    task = load_task(example_task)
    assert task.id == "config_repair"
    assert task.family == "_example"
    assert task.timeout_s == 60
    assert task.network is False
    assert task.outputs == ("config.json",)
    assert task.tags == ("example", "config")
    assert task.workspace_dir == example_task / "workspace"
    assert task.grader_path == example_task / "grader" / "grade.py"
    assert task.reference_script == example_task / "reference" / "solve.sh"
    assert task.ceiling_path == example_task / "ceiling.md"
    assert "port" in task.prompt


def test_known_bads_are_sorted_and_carry_expect_codes(example_task):
    task = load_task(example_task)
    names = [bad.path.name for bad in task.known_bad]
    assert names == ["fix_log_level_only.sh", "fix_port_only.sh"]
    expects = {bad.path.name: bad.expect for bad in task.known_bad}
    assert expects == {"fix_log_level_only.sh": "port_not_integer_8080", "fix_port_only.sh": "log_level_not_info"}


def test_discover_finds_example_task(example_task):
    tasks = discover(example_task.parent, include_smoke=True)
    assert [task.id for task in tasks] == ["config_repair"]
    assert find_task_dirs(example_task.parent) == [example_task]


def test_known_bad_without_expect_line_is_rejected(make_task):
    path = make_task(known_bad={"bad.sh": "#!/usr/bin/env bash\necho nothing\n"})
    with pytest.raises(TaskFormatError, match="exactly one '# expect"):
        load_task(path)


def test_known_bad_with_two_expect_lines_is_rejected(make_task):
    script = "# expect: a_code\n# expect: b_code\n"
    path = make_task(known_bad={"bad.sh": script})
    with pytest.raises(TaskFormatError, match="found 2"):
        load_task(path)


def test_missing_required_file_is_rejected(make_task):
    path = make_task()
    (path / "grader" / "grade.py").unlink()
    with pytest.raises(TaskFormatError, match="missing grader/grade.py"):
        load_task(path)


@pytest.mark.parametrize(
    "mutation, fragment",
    [
        (lambda text: text.replace("title: Demo task\n", ""), "missing fields"),
        (lambda text: text + "extra: 1\n", "unknown fields"),
        (lambda text: text.replace("timeout_s: 30", "timeout_s: 0"), "timeout_s must be positive"),
        (lambda text: text.replace("network: false", "network: 0"), "field 'network'"),
        (lambda text: text.replace("id: demo", "id: other"), "must equal the directory name"),
        (lambda text: text.replace("summary: A demo task for tests.", "summary: '  '"), "field 'summary'"),
    ],
)
def test_bad_task_yaml_is_rejected(make_task, mutation, fragment):
    path = make_task()
    (path / "task.yaml").write_text(mutation(default_yaml("demo")), encoding="utf-8")
    with pytest.raises(TaskFormatError, match=fragment):
        load_task(path)


def test_task_hash_is_stable_and_tracks_every_file(make_task):
    path = make_task()
    task = load_task(path)
    first = task_hash(task)
    assert first == task_hash(load_task(path))
    (path / "ceiling.md").write_text("changed\n", encoding="utf-8")
    assert task_hash(load_task(path)) != first


def test_task_hash_ignores_bytecode(make_task):
    path = make_task()
    task = load_task(path)
    before = task_hash(task)
    (path / "grader" / "__pycache__").mkdir()
    (path / "grader" / "__pycache__" / "grade.cpython-311.pyc").write_bytes(b"x")
    assert task_hash(task) == before


def test_write_task_helper_round_trips(tmp_path):
    path = write_task(tmp_path, task_id="roundtrip", known_bad={})
    task = load_task(path)
    assert task.known_bad == ()
    assert task.id == "roundtrip"
