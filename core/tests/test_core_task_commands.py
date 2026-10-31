"""Coverage (AETHER_CORE_RECORD=coverage): commands the task shows, and whether a command the run sent contained them.
The fact compares text only; each test pairs the case that must fire with the case that must stay silent."""

from __future__ import annotations

import asyncio
from pathlib import Path

from aether.core import task_commands
from aether.core.harbor_agent import build_config
from aether.core.record import Record
from tests.core_fakes import LocalEnv

BASE = {"AETHER_CORE_REVIEW": "off", "AETHER_CORE_CONTEXT": "clm", "AETHER_CORE_REPL": "off", "AETHER_CORE_IMAGES": "off"}
CLONE = "git clone user@server:/git/server"
TASK = (f"Set up the repository so that `{CLONE}` works, then push. Check it with `python3 check.py --all`.\n"
        "Edit `README.md` and the file `WORK/config.yaml`. Use `bash`.\n\n"
        "    curl http://server:8080/hello.html\n\n```bash\ncd build && make install\nls\n```\n")
DONE = "\n[exit 0 · 0.2s · terminal main · cwd /app]"


def test_shown_takes_command_spans_indented_and_fenced_lines_only():
    got = task_commands.shown(TASK)
    assert got == [CLONE, "python3 check.py --all", "curl http://server:8080/hello.html", "cd build && make install"]
    assert task_commands.shown("Write the answer to `/app/out.txt` using `jq`.") == []  # paths and lone programs
    many = " ".join(f"`echo {i} done`" for i in range(20))
    assert len(task_commands.shown(many)) == task_commands.MAX_COMMANDS
    assert task_commands.shown("`ls -la` and `ls -la` again") == ["ls -la"]


def test_ran_matches_the_task_host_as_any_host_but_not_a_local_substitute():
    assert task_commands.ran(CLONE, ["cd /tmp && git clone user@localhost:/git/server repo"])
    assert task_commands.ran(CLONE, ["git clone 'user@127.0.0.1:/git/server'"])
    assert not task_commands.ran(CLONE, ["git clone /git/server /tmp/repo"])  # never went through the host
    assert not task_commands.ran(CLONE, ["git", "clone", "user@x:/git/server"])  # words split across commands
    assert task_commands.ran("curl http://server:8080/hello.html", ["curl -s http://localhost:8080/hello.html"])
    assert task_commands.ran("python3 convert.py <input_dir> X", ["python3 convert.py /data out"])
    assert not task_commands.ran("python3 check.py --all", ["python3 check.py"])  # 2 of 3 words < RUN_SHARE


def _record(tmp_path: Path, commands: bool, rows: list) -> Record:
    (tmp_path / "app").mkdir(exist_ok=True)
    return Record(LocalEnv(tmp_path), str(tmp_path / "app"), str(tmp_path / "ctl"), lambda: 300.0,
                  lambda event, **data: rows.append((event, data)), measure=True,
                  task=TASK.replace("WORK", str(tmp_path / "app")), paths_only=True,
                  commands=commands)


def test_first_finish_is_held_once_naming_only_the_commands_never_sent(tmp_path):
    async def go():
        rows: list = []
        record = _record(tmp_path, True, rows)
        (tmp_path / "app" / "config.yaml").write_text("x: 1\n")  # task-named path exists: only commands can hold
        for args in ({"input": "python3 check.py --all"}, {"input": "cd build && make install"},
                     {"input": CLONE, "interrupt": True}):
            await record.after_terminal(args, DONE, 1.0)
        refused = "[input not sent: terminal t2 is still running its previous command. ...]\nearlier output\n"
        await record.after_terminal({"input": "curl http://server:8080/hello.html", "name": "t2"}, refused, 2.0)
        hold, text, row = await record.at_finish()
        assert hold and row["not_run"] == [CLONE, "curl http://server:8080/hello.html"] and row["absent"] == []
        assert f"`{CLONE}`" in text and "check.py" not in text and "no input sent to a terminal" in text
        assert "do not exist" not in text and "300s" in text
        assert rows[-1][0] == "record_finish" and rows[-1][1]["hold"]
        assert (await record.at_finish())[0] is False  # only the first finish is examined

    asyncio.run(go())


def test_no_hold_once_every_shown_command_was_typed_into_a_terminal_or_when_coverage_is_off(tmp_path):
    async def go():
        record = _record(tmp_path, True, [])
        (tmp_path / "app" / "config.yaml").write_text("x: 1\n")
        await record.after_terminal({"input": f"{CLONE} r\n", "mode": "keys"}, "", 1.0)  # typed into a shell: counts
        await record.after_terminal({"input": "python3 check.py --all -v"}, DONE, 1.0)
        # a program that prints the refusal's words is not a refusal: the command was sent
        await record.after_terminal({"input": "curl -s http://127.0.0.1:8080/hello.html"},
                                    "[input not sent: this is the page's own text]" + DONE, 1.0)
        await record.after_terminal({"input": "cd build && make install"}, DONE, 1.0)
        assert (await record.at_finish())[0] is False
        paths_only = _record(tmp_path, False, [])  # paths mode: the same run never mentions commands
        assert paths_only.task_commands == [] and (await paths_only.at_finish())[0] is False

    asyncio.run(go())


def test_config_coverage_mode_is_paths_plus_commands():
    c = build_config(environ={**BASE, "AETHER_CORE_RECORD": "coverage"})
    assert c.record and c.record_measure and c.record_paths and c.record_commands
    p = build_config(environ={**BASE, "AETHER_CORE_RECORD": "paths"})
    assert p.record_paths and not p.record_commands
