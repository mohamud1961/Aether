"""Real local-shell contract checks for the bounded environment probe."""

import asyncio
import json
import shlex
import socket
import threading

from aether.core import facts_probe
from tests.core_fakes import LocalEnv


class ScopedEnv(LocalEnv):
    def __init__(self, root, bindir):
        super().__init__(root)
        self.bindir = bindir

    async def exec(self, command, **kwargs):
        command = f"PATH={shlex.quote(str(self.bindir))}:/usr/bin:/bin; export PATH\n" + command
        return await super().exec(command, **kwargs)


def _tool(path, text):
    path.write_text("#!/bin/sh\n" + text + "\n")
    path.chmod(0o755)


def test_real_probe_observes_commands_versions_and_safe_bounded_files(tmp_path, monkeypatch):
    work = tmp_path / "work's $()"
    work.mkdir()
    bindir = tmp_path / "bin"
    bindir.mkdir()
    _tool(bindir / "afprobe", "printf 'AF probe 1.0\\n'")
    _tool(bindir / "timeout", 'shift; exec "$@"')
    (work / "visible.txt").write_text("synthetic content is never read")
    (work / "private-key.pem").write_text("SYNTHETIC_DO_NOT_READ")
    (work / "tests").mkdir()
    (work / "link").symlink_to(work / "visible.txt")
    monkeypatch.setattr(facts_probe, "COMMANDS", ("afprobe", "afmissing"))
    monkeypatch.setattr(facts_probe, "LANGUAGES", ("afprobe",))
    env = ScopedEnv(work, bindir)
    observation = asyncio.run(facts_probe.probe(env, str(work), full=True, remaining_s=30, hosts=()))
    assert observation["ok"], observation
    facts = observation["facts"]
    assert facts["commands"]["afprobe"] is not None
    assert facts["commands"]["afmissing"] is None
    assert facts["versions"]["afprobe"] is None
    assert facts["files"] == ["visible.txt"]
    assert not facts["files_complete"]
    assert "SYNTHETIC_DO_NOT_READ" not in json.dumps(observation)
    assert "private-key.pem" not in json.dumps(observation)
    assert not (tmp_path / "work").exists(), "quoted shell metacharacters must not be executed"


def test_listing_cap_and_symlink_root_are_explicit(tmp_path, monkeypatch):
    work = tmp_path / "work"
    work.mkdir()
    bindir = tmp_path / "bin"
    bindir.mkdir()
    for n in range(25):
        (work / f"file{n:02}.txt").write_text("not inspected")
    monkeypatch.setattr(facts_probe, "COMMANDS", ("sh",))
    env = ScopedEnv(work, bindir)
    observation = asyncio.run(facts_probe.probe(env, str(work), full=False, remaining_s=30, hosts=()))
    assert observation["ok"]
    assert len(observation["facts"]["files"]) == 20
    assert not observation["facts"]["files_complete"]
    link = tmp_path / "linked-root"
    link.symlink_to(work, target_is_directory=True)
    linked = asyncio.run(facts_probe.probe(env, str(link), full=False, remaining_s=30, hosts=()))
    assert linked["ok"] and linked["facts"]["files"] == []
    assert not linked["facts"]["files_complete"]
    class NoRootEnumeration(ScopedEnv):
        async def exec(self, command, **kwargs):
            glob = 'for __af_path in ./*; do'
            assert command.count(glob) == 1
            # If the guard regresses, test one guaranteed-absent canary instead
            # of listing the host's root directory.
            command = command.replace(glob, 'for __af_path in ./.codex-absent-root-canary; do')
            return await super().exec(command, **kwargs)

    root = asyncio.run(facts_probe.probe(NoRootEnumeration(work, bindir), "//", full=False,
                                         remaining_s=30, hosts=()))
    assert root["ok"] and root["facts"]["files"] == []
    assert not root["facts"]["files_complete"] and root["facts"]["workspace"] is None


def test_workspace_replaced_with_symlink_during_probe_is_not_listed(tmp_path, monkeypatch):
    work = tmp_path / "work"
    work.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "outside-canary.txt").write_text("synthetic content")
    bindir = tmp_path / "bin"
    bindir.mkdir()
    monkeypatch.setattr(facts_probe, "COMMANDS", ("sh",))

    class SwapAfterValidation(ScopedEnv):
        async def exec(self, command, **kwargs):
            marker = 'if [ "$__af_incomplete" -ne 0 ] || [ ! -d "$__af_root" ]; then __af_incomplete=1; else'
            assert command.count(marker) == 1
            swap = ('mv "$__af_root" "$__af_root.saved" && '
                    f'ln -s {shlex.quote(str(outside))} "$__af_root"\n')
            return await super().exec(command.replace(marker, swap + marker), **kwargs)

    observed = asyncio.run(facts_probe.probe(SwapAfterValidation(work, bindir), str(work),
                                             full=False, remaining_s=30, hosts=()))
    assert observed["ok"]
    assert observed["facts"]["files"] == [] and not observed["facts"]["files_complete"]
    assert observed["facts"]["workspace"] is None


def test_workspace_moved_after_open_does_not_publish_stale_listing(tmp_path, monkeypatch):
    work = tmp_path / "work"
    work.mkdir()
    (work / "inside-canary.txt").write_text("synthetic content")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "outside-canary.txt").write_text("synthetic content")
    bindir = tmp_path / "bin"
    bindir.mkdir()
    monkeypatch.setattr(facts_probe, "COMMANDS", ("sh",))

    class SwapAfterOpen(ScopedEnv):
        async def exec(self, command, **kwargs):
            marker = '  for __af_path in ./*; do'
            assert command.count(marker) == 1
            swap = ('mv "$__af_root" "$__af_root.saved" && '
                    f'ln -s {shlex.quote(str(outside))} "$__af_root"\n')
            return await super().exec(command.replace(marker, swap + marker), **kwargs)

    observed = asyncio.run(facts_probe.probe(SwapAfterOpen(work, bindir), str(work),
                                             full=False, remaining_s=30, hosts=()))
    assert observed["ok"]
    assert observed["facts"]["files"] == [] and not observed["facts"]["files_complete"]
    assert observed["facts"]["workspace"] is None


def test_named_local_host_is_measured_without_public_network(tmp_path, monkeypatch):
    work = tmp_path / "work"
    work.mkdir()
    bindir = tmp_path / "bin"
    bindir.mkdir()
    trusted_timeout = tmp_path / "system-timeout"
    _tool(trusted_timeout, 'shift; exec "$@"')
    marker = tmp_path / "path-helper-ran"
    _tool(bindir / "timeout", f"printf touched > {shlex.quote(str(marker))}; exit 0")
    _tool(bindir / "bash", f"printf touched > {shlex.quote(str(marker))}; exit 0")
    monkeypatch.setattr(facts_probe, "SYSTEM_TIMEOUT_PATHS", (str(trusted_timeout),))
    monkeypatch.setattr(facts_probe, "COMMANDS", ("sh",))
    monkeypatch.setattr(facts_probe, "LANGUAGES", ())
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]
    accepted = threading.Event()

    def consume():
        connection, _address = server.accept()
        connection.close()
        accepted.set()

    thread = threading.Thread(target=consume, daemon=True)
    thread.start()
    try:
        observation = asyncio.run(facts_probe.probe(
            ScopedEnv(work, bindir), str(work), full=True, remaining_s=30,
            hosts=(("127.0.0.1", port),),
        ))
        assert observation["ok"], observation
        assert observation["facts"]["network"][f"127.0.0.1:{port}"] == "connected"
        assert accepted.wait(2)
        assert not marker.exists()
    finally:
        server.close()
        thread.join(timeout=2)


def test_failed_or_timed_out_probe_is_unknown():
    class Broken:
        async def exec(self, **_kwargs):
            raise TimeoutError("synthetic")

    result = asyncio.run(facts_probe.probe(Broken(), "/task", full=True, remaining_s=30, hosts=()))
    assert result == {"ok": False, "reason": "TimeoutError"}


def test_probe_does_not_execute_a_workspace_supplied_version_program(tmp_path, monkeypatch):
    work = tmp_path / "work"
    work.mkdir()
    bindir = work / "bin"
    bindir.mkdir()
    marker = work / "probe-ran-task-program"
    _tool(bindir / "afprobe", f"printf touched > {shlex.quote(str(marker))}; echo 'AF probe 1.0'")
    _tool(bindir / "timeout", 'shift; exec "$@"')
    monkeypatch.setattr(facts_probe, "COMMANDS", ("afprobe",))
    monkeypatch.setattr(facts_probe, "LANGUAGES", ("afprobe",))
    observation = asyncio.run(facts_probe.probe(
        ScopedEnv(work, bindir), str(work), full=True, remaining_s=30, hosts=(),
    ))
    assert observation["ok"], observation
    assert observation["facts"]["commands"]["afprobe"] is not None
    assert observation["facts"]["versions"]["afprobe"] is None
    assert not marker.exists()


def test_network_probe_does_not_execute_a_helper_through_a_linked_parent(tmp_path, monkeypatch):
    work = tmp_path / "work"
    work.mkdir()
    bindir = work / "bin"
    bindir.mkdir()
    marker = work / "fake-timeout-ran"
    _tool(bindir / "timeout", f"printf touched > {shlex.quote(str(marker))}; exit 0")
    link = tmp_path / "linked-bin"
    link.symlink_to(bindir, target_is_directory=True)
    monkeypatch.setattr(facts_probe, "SYSTEM_TIMEOUT_PATHS", (str(link / "timeout"),))
    monkeypatch.setattr(facts_probe, "COMMANDS", ("sh",))
    monkeypatch.setattr(facts_probe, "LANGUAGES", ())
    observation = asyncio.run(facts_probe.probe(
        ScopedEnv(work, bindir), str(work), full=True, remaining_s=30,
        hosts=(("127.0.0.1", 43131),),
    ))
    assert observation["ok"], observation
    assert observation["facts"]["network"]["127.0.0.1:43131"] == "unknown"
    assert not marker.exists()
