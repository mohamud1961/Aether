"""Shared helpers for the eval-tools tests: a parameterised task-directory builder and the example task path."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

EVALS_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_TASK = EVALS_ROOT / "tests" / "eval_tools" / "fixtures" / "config_repair"

GOOD_GRADER = textwrap.dedent(
    """\
    import json
    import sys
    from pathlib import Path

    text = (Path(sys.argv[1]) / "state.txt").read_text(encoding="utf-8")
    passed = text.strip() == "done"
    print(json.dumps({"passed": passed, "score": 1.0 if passed else 0.0,
                      "reasons": ["state_done" if passed else "state_not_done"]}))
    """
)
REFERENCE = "#!/usr/bin/env bash\nprintf 'done\\n' > state.txt\n"
WRONG_STATE = "#!/usr/bin/env bash\n# expect: state_not_done\nprintf 'half\\n' > state.txt\n"


def default_yaml(task_id: str, timeout_s: int = 30) -> str:
    return (
        f"id: {task_id}\n"
        "family: unit\n"
        "title: Demo task\n"
        "summary: A demo task for tests.\n"
        f"timeout_s: {timeout_s}\n"
        "network: false\n"
        "outputs:\n"
        "  - state.txt\n"
        "tags:\n"
        "  - test\n"
    )


def write_task(
    parent: Path,
    *,
    task_id: str = "demo",
    grader: str = GOOD_GRADER,
    reference: str | None = REFERENCE,
    known_bad: dict[str, str] | None = None,
    workspace: dict[str, str] | None = None,
    task_yaml: str | None = None,
    timeout_s: int = 30,
) -> Path:
    """Write a task directory under parent. known_bad=None gives one wrong-state script; {} gives none."""
    task = parent / task_id
    (task / "workspace").mkdir(parents=True)
    (task / "grader").mkdir()
    (task / "reference").mkdir()
    (task / "task.yaml").write_text(task_yaml if task_yaml is not None else default_yaml(task_id, timeout_s))
    (task / "prompt.md").write_text("Make state.txt say done.\n", encoding="utf-8")
    (task / "ceiling.md").write_text("A perfect solution writes done to state.txt.\n", encoding="utf-8")
    (task / "grader" / "grade.py").write_text(grader, encoding="utf-8")
    if reference is not None:
        (task / "reference" / "solve.sh").write_text(reference, encoding="utf-8")
    for name, content in (workspace if workspace is not None else {"state.txt": "initial\n"}).items():
        (task / "workspace" / name).parent.mkdir(parents=True, exist_ok=True)
        (task / "workspace" / name).write_text(content, encoding="utf-8")
    scripts = {"wrong_state.sh": WRONG_STATE} if known_bad is None else known_bad
    if scripts:
        (task / "known_bad").mkdir()
        for name, content in scripts.items():
            (task / "known_bad" / name).write_text(content, encoding="utf-8")
    return task


@pytest.fixture
def make_task(tmp_path: Path):
    def _make(**kwargs):  # type: ignore[no-untyped-def]
        return write_task(tmp_path / "tasks", **kwargs)

    return _make


@pytest.fixture
def example_task() -> Path:
    return EXAMPLE_TASK
