"""A file read's visible page and range describe the same observed stream."""

import asyncio
import os
import shlex
import shutil

from aether.core.loop import CoreConfig, Trace, run_agent
from aether.core.provider import ChatProvider
from tests.core_fakes import LocalEnv, ScriptedClient, call


def test_file_replaced_after_first_scan_has_consistent_page_and_range(tmp_path, monkeypatch):
    work = tmp_path / "work"
    work.mkdir()
    target = work / "data.txt"
    replacement = tmp_path / "replacement"
    target.write_text("old\n")
    replacement.write_text("new-1\nnew-2\nnew-3\n")
    completed, release = tmp_path / "first_scan_done", tmp_path / "release"

    # Pause after the first real awk process has read the target. With two
    # passes, replacement happens between count and page; with one pass, it
    # happens after both page and count were observed together.
    real_awk = shutil.which("awk")
    assert real_awk
    bindir = tmp_path / "bin"
    bindir.mkdir()
    wrapper = bindir / "awk"
    wrapper.write_text(
        "#!/bin/sh\n"
        "for arg do last=$arg; done\n"
        f"if [ \"$last\" = {shlex.quote(str(target))} ] && [ ! -e {shlex.quote(str(completed))} ]; then\n"
        f"  {shlex.quote(real_awk)} \"$@\" || exit $?\n"
        f"  : > {shlex.quote(str(completed))}\n"
        f"  i=0; while [ ! -e {shlex.quote(str(release))} ]; do\n"
        "    [ \"$i\" -lt 1000 ] || exit 1; sleep 0.01; i=$((i+1))\n"
        "  done\n  exit 0\nfi\n"
        f"exec {shlex.quote(real_awk)} \"$@\"\n"
    )
    wrapper.chmod(0o755)
    monkeypatch.setenv("PATH", str(bindir) + os.pathsep + os.environ.get("PATH", ""))

    client = ScriptedClient([
        call("read_file", {"path": str(target)}, "read"),
        call("finish", {"summary": "done"}, "finish"),
    ])

    async def writer():
        for _ in range(1000):
            if completed.exists():
                os.replace(replacement, target)
                release.touch()
                return
            await asyncio.sleep(0.01)
        raise TimeoutError("the first read did not complete")

    async def episode():
        return await asyncio.gather(run_agent(
            env=LocalEnv(work), task="Read the file.", workdir=str(work),
            provider=ChatProvider(client, model="scripted", params={}), trace=Trace(tmp_path / "trace.jsonl"),
            timeout_s=40, config=CoreConfig(control_dir=str(tmp_path / "control"), end_processes="stop"),
        ), writer())

    result, _ = asyncio.run(episode())
    assert result.status == "finished", result.error
    assert target.read_text() == "new-1\nnew-2\nnew-3\n"
    observed = next(message["content"] for message in client.requests[-1]["messages"]
                    if message.get("role") == "tool" and message.get("tool_call_id") == "read")
    if "new-1" in observed:
        assert "new-2" in observed and "new-3" in observed
        assert "lines 1-3 of 3" in observed, observed
    else:
        assert "old" in observed and "lines 1-1 of 1" in observed, observed
