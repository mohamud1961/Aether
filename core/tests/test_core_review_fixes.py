"""Defects found by the independent adversarial review of the merged Core (2026-10-26), each reproduced first.

T1 a command body larger than one argv string; T2 a completion receipt planted before the send; T3 a command that
deletes its own terminal's control files; T4 a model-defined ``printf``/``mv``; S1 a launch that fails without a
PID; K1 a symlink in a continuation capture. Real local shells, no model.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from pathlib import Path

import pytest

import aether.core.terminal_session as terminal_session
from aether.core import continuation
from aether.core.env import ExecResult
from aether.core.terminal import Terminals
from aether.core.transfer import INLINE_BYTES
from tests.core_fakes import LocalEnv
from tests.test_core_continuation import FakeEnv

_OPEN: list[Terminals] = []


@pytest.fixture(autouse=True)
def _close_terminals():
    yield
    while _OPEN:
        asyncio.run(_OPEN.pop().close())


def _terms(tmp_path, env=None):
    work = tmp_path / "work"
    work.mkdir(exist_ok=True)
    terminals = Terminals(env or LocalEnv(work), str(work), lambda: 1000.0, control_dir=str(tmp_path / "ctl"))
    _OPEN.append(terminals)
    return terminals


class _ArgvSizes(LocalEnv):
    def __init__(self, root):
        super().__init__(root)
        self.longest = 0

    async def exec(self, command, cwd=None, env=None, timeout_sec=None):
        self.longest = max(self.longest, len(command.encode()))
        return await super().exec(command, cwd=cwd, env=env, timeout_sec=timeout_sec)


def test_t1_a_command_body_over_the_inline_limit_is_uploaded_not_inlined(tmp_path):
    (tmp_path / "work").mkdir()
    env = _ArgvSizes(tmp_path / "work")
    body = "x" * 120_000

    async def run():
        terminals = _terms(tmp_path, env)
        await terminals.use(input="true")
        return await terminals.use(input=f"cat > big.txt <<'EOF'\n{body}\nEOF\nwc -c < big.txt", wait_s=10)

    out = asyncio.run(run())
    assert "120001" in out and "[exit 0" in out, out
    assert env.longest < 2 * INLINE_BYTES, f"an exec carried {env.longest} bytes; Linux caps one argv at 128 KiB"


def test_t2_a_receipt_planted_before_the_send_does_not_complete_the_command(tmp_path):
    async def run():
        terminals = _terms(tmp_path)
        await terminals.use(input="true")
        root = Path(terminals._sessions["main"].root)
        (root / "done_2").write_text("\n__AETHER_DONE_2_0__ /forged\n")
        first = await terminals.use(input="sleep 2; echo real-finished", wait_s=0.5)
        second = await terminals.use(input="", wait_s=10)
        return first, second

    first, second = asyncio.run(run())
    assert "still running" in first and "/forged" not in first, first
    assert "real-finished" in second and "[exit 0" in second and "/forged" not in second, second


def test_t3_a_command_that_deletes_its_control_files_leaves_the_next_command_runnable(tmp_path):
    async def run():
        terminals = _terms(tmp_path)
        await terminals.use(input="true")
        root = terminals._sessions["main"].root
        first = await terminals.use(input=f"rm -rf {root}; sleep 0.2", wait_s=1)
        second = await terminals.use(input="echo should-run")
        return first, second

    first, second = asyncio.run(run())
    assert "could not send" not in first and "missing" in first, first
    assert "should-run" in second and "[exit 0" in second and "still running" not in second, second


def test_t4_model_defined_printf_and_mv_do_not_break_completion(tmp_path):
    async def run():
        terminals = _terms(tmp_path)
        outs = [await terminals.use(input="printf() { command printf 'garbage\\n'; }; mv() { :; }")]
        outs.append(await terminals.use(input="echo after", wait_s=5))
        return outs

    outs = asyncio.run(run())
    assert all("[exit 0" in o for o in outs), outs
    assert "after" in outs[1], outs[1]


def test_s1_a_launch_that_fails_without_a_pid_does_not_poison_close(tmp_path, monkeypatch):
    real = terminal_session.run

    async def failing_launch(env, command, *, timeout_s=30, cwd=None):
        if "nohup" in command:
            return ExecResult(1, "", "/bin/sh: python3: not found")
        return await real(env, command, timeout_s=timeout_s, cwd=cwd)

    monkeypatch.setattr(terminal_session, "run", failing_launch)
    terminals = _terms(tmp_path)
    with pytest.raises(RuntimeError, match="terminal launch failed"):
        asyncio.run(terminals.use(input="true"))
    _OPEN.remove(terminals)
    asyncio.run(terminals.close())  # raised before: the failed root stayed in _launching
    asyncio.run(terminals.close())
    assert not terminals._launching
    assert terminals.cleanup_receipt.get("status") == "partial_unverified", terminals.cleanup_receipt


def test_k1_one_symlink_in_a_capture_keeps_every_other_row(tmp_path):
    env, logs = FakeEnv(tmp_path / "c"), tmp_path / "logs"
    (logs / "continuation").mkdir(parents=True)
    env.put("/app/good.txt", b"good bytes\n")
    env.host("/app/link.txt").symlink_to("good.txt")
    asyncio.run(continuation.finish(env, logs, continuation._capture_plan(["/app/good.txt", "/app/link.txt"],
                                                                          "/app", 30.0)))
    rows = {r["remote"]: r for r in json.loads((logs / "continuation" / "capture_manifest.json").read_text())["rows"]}
    assert rows["/app/good.txt"]["status"] == "captured", rows
    assert rows["/app/link.txt"]["status"] == "error" and "symlink" in rows["/app/link.txt"]["error"], rows


def test_every_core_module_imports_first_in_a_fresh_interpreter():
    """Found in installed qualification: importing aether.core.transfer before env was a circular import."""
    import aether.core as core

    # repl_server is a program the REPL tool runs in the sandbox (it reads argv at start), not an importable module
    names = sorted(p.stem for p in Path(core.__file__).parent.glob("*.py") if p.stem not in ("__init__", "repl_server"))
    failed = {}
    for name in names:
        proc = subprocess.run([sys.executable, "-c", f"import aether.core.{name}"], capture_output=True, text=True)
        if proc.returncode:
            failed[name] = proc.stderr.strip().splitlines()[-1]
    assert not failed, failed
