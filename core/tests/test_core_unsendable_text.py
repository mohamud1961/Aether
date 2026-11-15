"""T1 refusals happen at each owner's entry, before any state changes or exec: nothing is left pending.

Known-bad (before 15 Nov): the terminal and the REPL took a sequence number and marked it pending, then failed to
encode the text, so every later call reported a command "still running" that had never been sent; bash dropped NUL
bytes from a command that then reported exit 0.
"""

import asyncio

import pytest

from aether.core.files import Files
from aether.core.repl import Repl
from aether.core.terminal import Terminals
from aether.core.tool_validate import unsendable_text
from tests.core_fakes import LocalEnv


def test_reasons():
    assert unsendable_text("plain é \U0001f680 \x03 \x1b", shell=True) == ""
    assert "NUL" in unsendable_text("a\x00b", shell=True)
    assert unsendable_text("a\x00b", shell=False) == ""  # files, python literals and JSON carry NUL
    assert "unpaired surrogate" in unsendable_text("a\ud800", shell=False)


@pytest.mark.parametrize("text", ["a\x00b", "a\ud800b"])
def test_terminal_refuses_before_any_exec_or_state(tmp_path, text):
    env = LocalEnv(tmp_path)
    ctrl = Terminals(env, str(tmp_path), lambda: 1000.0, control_dir=str(tmp_path / "ctl"), preserve_existing=True)
    with pytest.raises(ValueError, match="nothing ran"):
        asyncio.run(ctrl.use(name="t", input=text, wait_s=1))
    assert env.commands == [] and ctrl.names == []


def test_repl_refuses_before_any_exec_or_state(tmp_path):
    env = LocalEnv(tmp_path)
    repl = Repl(env, str(tmp_path), lambda: 600.0, None, base=str(tmp_path / "r"), track_operations=True)
    with pytest.raises(ValueError, match="nothing ran"):
        asyncio.run(repl.run("x = '\ud800'"))
    assert env.commands == [] and repl.pending == 0 and repl.seq == 0


def test_file_write_refuses_before_any_exec(tmp_path):
    env = LocalEnv(tmp_path)
    with pytest.raises(ValueError, match="nothing ran"):
        asyncio.run(Files(env, str(tmp_path)).write(str(tmp_path / "f"), "a\ud800"))
    assert env.commands == [] and not (tmp_path / "f").exists()
