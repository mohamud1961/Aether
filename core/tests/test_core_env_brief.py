"""The environment brief reports what the container has, as measured, and says nothing when the probe fails."""

from __future__ import annotations

import asyncio
import errno
import os
from types import SimpleNamespace

from aether.core import env_brief
from aether.core.harbor_agent import build_config
from aether.core.loop import CoreConfig, Trace, run_agent
from aether.core.provider import ChatProvider
from tests.core_fakes import LocalEnv, ScriptedClient, call

BASE = {"AETHER_CORE_REVIEW": "off", "AETHER_CORE_CONTEXT": "clm", "AETHER_CORE_REPL": "off", "AETHER_CORE_IMAGES": "off"}


def test_the_brief_lists_present_and_missing_tools_and_the_working_tree(tmp_path, monkeypatch):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "data.bin").write_bytes(b"12345")
    monkeypatch.setattr(env_brief, "TOOLS", ("sh", "no-such-tool-aether"))
    brief, row = asyncio.run(env_brief.take(LocalEnv(tmp_path), str(tmp_path / "app")))
    assert row["ok"] and brief.startswith("(Environment, measured by the harness")
    assert "available: sh" in brief and "not found on PATH: no-such-tool-aether" in brief
    assert "package managers:" in brief and "package servers:" in brief  # whether software can be installed
    assert "./data.bin (5 B)" in brief
    # machine size, what lies outside the working directory, what already runs (values depend on the host)
    assert "\nmachine: cpus " in brief and "disk free:" in brief
    assert f"\noutside {tmp_path / 'app'} (non-standard or non-empty):" in brief
    assert "\nrunning processes: " in brief


def test_a_failed_probe_gives_no_brief():
    class Broken:
        async def exec(self, command, cwd=None, env=None, timeout_sec=None):
            return SimpleNamespace(return_code=127, stdout="", stderr="sh: not found")

    brief, row = asyncio.run(env_brief.take(Broken(), "/app"))
    assert brief == "" and not row["ok"]


def test_startup_sample_never_reads_file_contents_or_follows_links(tmp_path, monkeypatch):
    workdir = tmp_path / "workspace with spaces"
    workdir.mkdir()
    outside = tmp_path / "outside"
    outside.write_bytes(b"x" * 193)
    (workdir / "linked").symlink_to(outside)
    os.mkfifo(workdir / "pipe")
    (workdir / "first\nsecond").write_text("hello")
    (workdir / "dir").mkdir()
    (workdir / "dir" / "ordinary").write_text("input")
    monkeypatch.setattr(env_brief, "INDEXES", ())
    client = ScriptedClient([
        call("write_file", {"path": "artifact", "content": "delivered\n"}, "write"),
        call("finish", {"summary": "Done."}, "finish"),
    ])

    async def exercise():
        fifo_reader = asyncio.Event()

        async def detect_reader():
            # If the old probe opens the FIFO, satisfy that read so the bad
            # control fails by observation instead of a process timeout.
            while True:
                try:
                    fd = os.open(workdir / "pipe", os.O_WRONLY | os.O_NONBLOCK)
                except OSError as exc:
                    if exc.errno != errno.ENXIO:
                        raise
                    await asyncio.sleep(0.01)
                else:
                    with os.fdopen(fd, "wb") as stream:
                        stream.write(b"unintended read")
                    fifo_reader.set()
                    return

        detector = asyncio.create_task(detect_reader())
        try:
            result = await run_agent(
                env=LocalEnv(workdir), task="Write delivered followed by a newline to artifact.",
                workdir=str(workdir), provider=ChatProvider(client, model="offline", params={}),
                trace=Trace(tmp_path / "trace.jsonl"), timeout_s=20,
                config=CoreConfig(env_brief=True, control_dir=str(tmp_path / "control")),
            )
        finally:
            if not detector.done():
                detector.cancel()
                await asyncio.gather(detector, return_exceptions=True)
            else:
                detector.result()
        assert not fifo_reader.is_set(), "the startup probe opened the FIFO for reading"
        return result

    assert asyncio.run(exercise()).status == "finished"
    assert (workdir / "artifact").read_bytes() == b"delivered\n"
    initial = "\n".join(m["content"] for m in client.requests[0]["messages"] if m["role"] == "user")
    assert "./linked (link)" in initial
    assert "./pipe (special)" in initial
    assert "./dir/ordinary (5 B)" in initial
    assert "first\\nsecond" in initial and "first\nsecond" not in initial
    assert "193 B" not in initial


def test_the_flag_is_off_by_default():
    assert build_config(environ=BASE).env_brief is False
    assert build_config(environ={**BASE, "AETHER_CORE_ENV_BRIEF": "on"}).env_brief is True
