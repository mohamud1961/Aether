"""State verification at finish: probe guard, verdict handling, loop integration, and (Linux + docker) a real
container clone whose changes never reach the original."""
from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
import uuid

import pytest

from aether.core import verify as V
from aether.core.loop import CoreConfig, Trace, run_agent
from aether.core.provider import ChatProvider
from tests.core.core_fakes import LocalEnv, ScriptedClient, call

TASK = "Write the word done into out.txt in the working directory."


def _provider(script):
    client = ScriptedClient(script)
    return ChatProvider(client, model="glm", params={"tool_choice": "required", "parallel_tool_calls": False}), client


def _verdict(*reqs, call_id="v9"):
    return call("verdict", {"requirements": [dict(zip(("requirement", "status", "command", "observed"), r))
                                             for r in reqs]}, call_id)


class _FakeClone(LocalEnv):
    closed = 0

    async def close(self) -> None:
        _FakeClone.closed += 1


def _clone_factory(root):
    async def make(_env):
        return _FakeClone(root)
    return make


@pytest.mark.parametrize("cmd", ["ps aux", "curl -s http://localhost:8080/", "ss -ltnp", "find /app -name '*.py'",
                                 "cat /app/out.txt", "curl -sI http://127.0.0.1:3000", "curl -sSL http://localhost:80",
                                 "curl -m 5 -H 'Accept: text/html' http://localhost:8080/x", "tail -n 20 /var/log/x"])
def test_read_only_probes_are_allowed(cmd):
    assert V.probe_refusal(cmd) is None


@pytest.mark.parametrize("cmd", ["rm -rf /app", "ls; rm x", "curl -X POST http://x", "curl -sXPOST http://x",
                                 "curl -o /tmp/x http://x", "curl --data a=1 http://x", "find / -delete",
                                 "find / -exec rm {} +", "cat $(id)", "echo hi > f", "ls | sh", "touch /app/x",
                                 "curl -D /tmp/h http://x", "curl --trace /tmp/t http://x", "curl -c /tmp/jar http://x",
                                 "curl --libcurl /tmp/c http://x", "curl file:///etc/shadow", "curl -w @/etc/x http://x",
                                 "curl -sD /tmp/h http://x", "ss -K dst 1.2.3.4", "ss -tK", "file -C -m /tmp/m",
                                 "tail -f /var/log/x", "sha256sum -c sums"])
def test_probes_that_could_change_state_are_refused(cmd):
    assert V.probe_refusal(cmd)  # known-bad: each of these could modify the graded container


def test_the_clone_has_no_network_and_resource_limits():
    calls = []

    async def host(argv, timeout):
        calls.append(argv)
        return 0, "", ""

    class Env:
        async def exec(self, command, cwd=None, env=None, timeout_sec=None):
            from types import SimpleNamespace
            return SimpleNamespace(return_code=0, stdout="a" * 64 + "\nhost\n", stderr="")
    clone = asyncio.run(V.Clone.create(Env(), host))
    commit, start = calls[0], calls[1]
    assert commit[:3] == ["docker", "commit", "a" * 64]
    assert ["--network", "none"] == start[start.index("--network"):start.index("--network") + 2]
    assert "no-new-privileges" in start and "--memory" in start and "--pids-limit" in start
    asyncio.run(clone.close())
    assert calls[-2][:3] == ["docker", "rm", "-f"] and calls[-1][:3] == ["docker", "rmi", "-f"]


def test_a_requirement_observed_failing_holds_with_its_evidence(tmp_path):
    work = tmp_path / "work"; work.mkdir(); (work / "out.txt").write_text("nope\n")
    provider, client = _provider([
        call("terminal", {"input": "cat out.txt"}, "v1"),
        _verdict(("out.txt contains done", "not_met", "cat out.txt", "nope"))])
    v = asyncio.run(V.verify(provider, LocalEnv(work), task=TASK, workdir=str(work), budget_s=200,
                             control_dir=str(tmp_path / "ctl"), make_clone=_clone_factory(work)))
    assert v.status == "hold" and v.failed[0]["observed"] == "nope"
    text = v.feedback()
    assert "out.txt contains done" in text and "ran: cat out.txt" in text and "observed: nope" in text
    first = client.requests[0]["messages"]
    assert TASK in first[1]["content"] and "verdict" in json.dumps(client.requests[0]["tools"])
    # the verifier's terminal ran in the clone
    assert "nope" in client.requests[1]["messages"][-1]["content"]


def test_all_requirements_met_passes_and_unchecked_does_not_hold(tmp_path):
    work = tmp_path / "work"; work.mkdir()
    provider, _ = _provider([_verdict(("out.txt contains done", "met", "cat out.txt", "done"),
                                      ("server answers", "unchecked", "curl", "not running in copy"))])
    v = asyncio.run(V.verify(provider, LocalEnv(work), task=TASK, workdir=str(work), budget_s=200,
                             control_dir=str(tmp_path / "ctl"), make_clone=_clone_factory(work)))
    assert v.status == "pass"


def test_clone_failure_is_reported_not_held(tmp_path):
    work = tmp_path / "work"; work.mkdir()

    async def broken(_env):
        raise V.CloneError("docker commit failed: no space")
    provider, client = _provider([])
    v = asyncio.run(V.verify(provider, LocalEnv(work), task=TASK, workdir=str(work), budget_s=200,
                             control_dir=str(tmp_path / "ctl"), make_clone=broken))
    assert v.status == "error" and "no space" in v.error and not client.requests


def test_an_empty_verdict_is_refused_and_the_clone_is_always_closed(tmp_path):
    work = tmp_path / "work"; work.mkdir()
    before = _FakeClone.closed
    provider, client = _provider([call("verdict", {"requirements": []}, "v1"),
                                  _verdict(("x", "met", "true", ""))])
    v = asyncio.run(V.verify(provider, LocalEnv(work), task=TASK, workdir=str(work), budget_s=200,
                             control_dir=str(tmp_path / "ctl"), make_clone=_clone_factory(work)))
    assert v.status == "pass" and "at least one requirement" in client.requests[1]["messages"][-1]["content"]
    assert _FakeClone.closed == before + 1


def test_live_probe_runs_read_only_commands_on_the_original_only(tmp_path):
    work = tmp_path / "work"; work.mkdir(); (work / "live.txt").write_text("LIVE-STATE")
    copy = tmp_path / "copy"; copy.mkdir()
    provider, client = _provider([
        call("live_probe", {"command": f"cat {work / 'live.txt'}"}, "v1"),
        call("live_probe", {"command": f"touch {work / 'x'}"}, "v2"),
        _verdict(("x", "met", "cat", "LIVE-STATE"))])
    asyncio.run(V.verify(provider, LocalEnv(work), task=TASK, workdir=str(work), budget_s=200,
                         control_dir=str(tmp_path / "ctl"), make_clone=_clone_factory(copy)))
    results = [m["content"] for m in client.requests[2]["messages"] if m.get("role") == "tool"]
    assert "LIVE-STATE" in results[0] and "[refused" in results[1] and not (work / "x").exists()


def test_the_loop_hands_failing_evidence_to_the_worker_and_finishes_once_it_holds(tmp_path):
    work = tmp_path / "work"; work.mkdir()
    script = [
        call("finish", {"summary": "done"}, "w1"),                                   # worker
        _verdict(("out.txt contains done", "not_met", "cat out.txt", "No such file")),  # verifier: hold
        call("write_file", {"path": "out.txt", "content": "done\n"}, "w2"),          # worker fixes
        call("finish", {"summary": "done"}, "w3"),
        call("terminal", {"input": "cat out.txt"}, "v1"),                           # verifier checks
        _verdict(("out.txt contains done", "met", "cat out.txt", "done"))]
    provider, client = _provider(script)
    config = CoreConfig(verify=True, make_clone=_clone_factory(work), control_dir=str(tmp_path / "ctl"))
    result = asyncio.run(run_agent(env=LocalEnv(work), task=TASK, workdir=str(work), provider=provider,
                                   timeout_s=600, trace=Trace(tmp_path / "t.jsonl"), config=config))
    assert result.status == "finished"
    assert [r["status"] for r in result.reviews] == ["hold", "pass"]
    worker_view = json.dumps(client.requests[2]["messages"])
    assert "failed its checks" in worker_view and "No such file" in worker_view
    verifier_view = json.dumps(client.requests[1]["messages"])
    assert "summary" not in verifier_view and "done\\n" not in verifier_view  # never the worker's story
    assert (work / "out.txt").read_text() == "done\n"


def test_verification_is_skipped_when_too_little_time_remains(tmp_path):
    work = tmp_path / "work"; work.mkdir()
    provider, client = _provider([call("finish", {"summary": "x"}, "w1")])
    config = CoreConfig(verify=True, make_clone=_clone_factory(work), control_dir=str(tmp_path / "ctl"))
    result = asyncio.run(run_agent(env=LocalEnv(work), task=TASK, workdir=str(work), provider=provider,
                                   timeout_s=200, trace=Trace(tmp_path / "t.jsonl"), config=config))
    rows = [json.loads(l) for l in (tmp_path / "t.jsonl").read_text().splitlines()]
    assert result.status == "finished" and len(client.requests) == 1
    assert any(r.get("event") == "finish" and r.get("reason") == "low_time" for r in rows)


def _docker_ok() -> bool:
    if not shutil.which("docker"):
        return False
    return subprocess.run(["docker", "info"], capture_output=True).returncode == 0


@pytest.mark.skipif(not _docker_ok(), reason="needs a docker daemon")
def test_a_real_clone_is_isolated_from_the_original_container():
    local = subprocess.run(["docker", "image", "ls", "--format", "{{.Repository}}:{{.Tag}}"], capture_output=True,
                           text=True).stdout.split()
    image = next((i for i in local if "<none>" not in i and not i.startswith("aether-verify")), None)
    if image is None:
        pytest.skip("no small base image available locally")
    name = f"aether-verify-test-{uuid.uuid4().hex[:8]}"
    subprocess.run(["docker", "run", "-d", "--rm", "--name", name, image, "sh", "-c",
                    "mkdir -p /data && echo original > /data/a && sleep 600"], check=True, capture_output=True)

    class Live:
        async def exec(self, command, cwd=None, env=None, timeout_sec=None):
            p = subprocess.run(["docker", "exec", name, "sh", "-c", command], capture_output=True, text=True)
            from types import SimpleNamespace
            return SimpleNamespace(return_code=p.returncode, stdout=p.stdout, stderr=p.stderr)

    async def go():
        clone = await V.Clone.create(Live())
        try:
            seen = (await clone.exec("cat /data/a")).stdout
            await clone.exec("echo changed-in-clone > /data/a")
            changed = (await clone.exec("cat /data/a")).stdout
        finally:
            await clone.close()
        original = (await Live().exec("cat /data/a")).stdout
        gone = subprocess.run(["docker", "image", "inspect", clone.image], capture_output=True).returncode != 0
        return seen, changed, original, gone
    try:
        seen, changed, original, gone = asyncio.run(go())
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)
    assert seen.strip() == "original" and changed.strip() == "changed-in-clone"
    assert original.strip() == "original"  # the clone's writes never reach the original
    assert gone  # the clone image is removed afterwards


def test_changed_files_lists_what_the_run_modified_and_not_the_harness_files(tmp_path):
    work = tmp_path / "work"; work.mkdir(); (work / "old.txt").write_text("before")
    ctl = tmp_path / "ctl"; ctl.mkdir()

    async def go():
        env = LocalEnv(work)
        await env.exec(f"sleep 1.1; touch {ctl}/started; sleep 1.1; echo x > {work}/new.txt; echo y > {ctl}/noise")
        return await V.changed_files(env, str(work), str(ctl))
    files = asyncio.run(go())
    assert str(work / "new.txt") in files and str(work / "old.txt") not in files
    assert not any(str(ctl) in f for f in files)
