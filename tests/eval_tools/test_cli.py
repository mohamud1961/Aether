from __future__ import annotations

import shutil
import textwrap
from pathlib import Path

import pytest

from eval_support import WRONG_STATE, write_task
from harness_evals.cli import build_parser, load_command_modules, main
from harness_evals.commands.validate_graders import render
from harness_evals.validity import TaskValidity, ValidityReport, Violation

pytestmark = pytest.mark.skipif(shutil.which("python3.11") is None, reason="python3.11 not on PATH")


def _subcommand_names(package: str = "harness_evals.commands") -> set[str]:
    parser = build_parser(package)
    subparsers_action = next(action for action in parser._actions if action.choices)  # noqa: SLF001
    return set(subparsers_action.choices)


def test_shipped_commands_are_discovered():
    modules = {module.__name__.rsplit(".", 1)[-1] for module in load_command_modules("harness_evals.commands")}
    assert {"validate_graders", "run_one"} <= modules
    assert {"validate-graders", "run-one"} <= _subcommand_names()


def test_a_new_command_module_is_discovered_without_editing_cli(tmp_path, monkeypatch, capsys):
    package = tmp_path / "pluginonly_cmds"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "hello.py").write_text(
        textwrap.dedent(
            """\
            def _run(args):
                print("hello from plugin")
                return 0

            def register(subparsers):
                parser = subparsers.add_parser("hello", help="test command")
                parser.set_defaults(func=_run)
            """
        ),
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    assert "hello" in _subcommand_names("pluginonly_cmds")
    assert main(["hello"], package="pluginonly_cmds") == 0
    assert "hello from plugin" in capsys.readouterr().out


def test_module_without_register_is_rejected(tmp_path, monkeypatch):
    package = tmp_path / "noregister_cmds"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "broken.py").write_text("X = 1\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    with pytest.raises(RuntimeError, match="does not define register"):
        build_parser("noregister_cmds")


def test_no_command_prints_help_and_returns_2(capsys):
    assert main([]) == 2
    assert "validate-graders" in capsys.readouterr().out


def test_validate_graders_exit_zero_on_clean_example(example_task, capsys):
    assert main(["validate-graders", str(example_task.parent)]) == 0
    out = capsys.readouterr().out
    assert "config_repair" in out
    assert "1/1 tasks clean" in out


def test_validate_graders_exit_one_on_violation(tmp_path, capsys):
    write_task(
        tmp_path,
        known_bad={"wrong_state.sh": WRONG_STATE.replace("state_not_done", "other_code")},
    )
    code = main(["validate-graders", str(tmp_path)])
    out = capsys.readouterr().out
    assert code == 1
    assert "[known_bad_expect_missing]" in out


def test_validate_graders_exit_one_when_nothing_found(tmp_path, capsys):
    assert main(["validate-graders", str(tmp_path)]) == 1
    assert "no task directories" in capsys.readouterr().out


def test_render_lists_each_violation():
    report = ValidityReport(
        root=Path("/unused"),
        tasks=(
            TaskValidity(task_id="t1", path=Path("/unused/t1"), known_bad_count=1, violations=()),
            TaskValidity(
                task_id="t2",
                path=Path("/unused/t2"),
                known_bad_count=0,
                violations=(Violation("no_known_bads", "none"),),
            ),
        ),
    )
    text = render(report)
    assert "1/2 tasks clean" in text
    assert "t2: [no_known_bads] none" in text
