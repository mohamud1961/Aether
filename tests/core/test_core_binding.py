"""The binding of a finding to the delivered state, and the check's end-to-end time, at their real boundaries.

Each test is a known-bad from the Codex re-review of e23ae2ca3 (15 Oct) that the previous code accepted: a failing
fingerprint read as an empty "unchanged" one; a 21 MiB deliverable repaired in the clone was certified; a permission
change was invisible; a shielded clone creation and a slow removal ran past the check's time."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import time

import pytest

from aether.core import binding as B
from aether.core import verify as V
from aether.core.clone import Clone, CloneError
from tests.core.core_fakes import LocalEnv
from tests.core.test_core_verify import PathClone, _run, _turn

MIB = 1024 * 1024


class NoSha(LocalEnv):
    """A container without sha256sum on its PATH."""

    async def exec(self, command, cwd=None, env=None, timeout_sec=None):
        return await super().exec(
            "PATH=/nonexistent; " + command, cwd=cwd, env=env, timeout_sec=timeout_sec
        )


def test_a_manifest_that_cannot_be_taken_is_unavailable_never_empty(tmp_path):
    with pytest.raises(B.BindingUnavailable, match="working directory unavailable"):
        asyncio.run(B.manifest(LocalEnv(tmp_path), str(tmp_path / "gone")))
    (tmp_path / "a.txt").write_text("x")
    with pytest.raises(B.BindingUnavailable, match="sha256sum unavailable"):
        asyncio.run(B.manifest(NoSha(tmp_path), str(tmp_path)))
    with pytest.raises(B.BindingUnavailable, match="cut short"):
        B.parse("M|regular file|644|./a.txt\n")


def test_the_manifest_binds_large_files_modes_and_links_and_names_what_it_leaves_out(
    tmp_path,
):
    w = tmp_path / "w"
    (w / ".git").mkdir(parents=True)
    (w / "big.bin").write_bytes(b"r" * (21 * MIB))
    (w / "run.sh").write_text("echo hi\n")
    os.symlink("run.sh", w / "link")
    before = asyncio.run(B.manifest(LocalEnv(w), str(w)))
    assert {"./big.bin", "./run.sh", "./link", "."} <= set(before.entries)
    assert before.unbound == ["./.git"]
    (w / "big.bin").write_bytes(b"b" * (21 * MIB))
    os.chmod(w / "run.sh", 0o755)
    os.remove(w / "link")
    os.symlink("big.bin", w / "link")
    (w / "scratch.log").write_text("ok\n")
    after = asyncio.run(B.manifest(LocalEnv(w), str(w)))
    assert B.changes(before, after) == {
        "modified": ["./big.bin", "./link", "./run.sh"],
        "deleted": [],
        "created": ["./scratch.log"],
    }


def test_names_that_could_forge_manifest_lines_make_the_binding_unavailable(tmp_path):
    w = tmp_path / "w"
    w.mkdir()
    (w / "colour.txt").write_text("red\n")
    # a directory named "x<newline><digest>  ." holding colour.txt prints a second line "<digest>  ./colour.txt"
    forged = w / ("x\n" + "0" * 64 + "  .")
    forged.mkdir()
    (forged / "colour.txt").write_text("")
    with pytest.raises(B.BindingUnavailable, match="newline"):
        asyncio.run(B.manifest(LocalEnv(w), str(w)))
    shutil.rmtree(forged)
    os.symlink("a|b", w / "piped")
    with pytest.raises(B.BindingUnavailable, match="link"):
        asyncio.run(B.manifest(LocalEnv(w), str(w)))
    line = "0" * 64 + "  ./colour.txt"
    with pytest.raises(B.BindingUnavailable, match="twice"):
        B.parse(f"M|regular file|644|./colour.txt\n{line}\n{line}\nEND\n")
    # Separators Python treats as line ends but the shell does not stay inside the name: no forged entry.
    for sep in ("\r", "\x1c", "\x85", "\u2028"):
        name = f"./a{sep}M|regular file|644|./ghost"
        digest = "0" * 64 + "  " + name
        text = f"M|directory|755|.\nM|regular file|644|{name}\n{digest}\nEND\n"
        assert set(B.parse(text).entries) == {".", name}


def test_a_record_missing_its_digest_or_link_target_makes_the_binding_unavailable():
    root = "M|directory|755|.\n"
    file, digest = "M|regular file|644|./colour.txt\n", "0" * 64 + "  ./colour.txt\n"
    link, target = "M|symbolic link|777|./l\n", "L|colour.txt|./l\n"
    assert set(B.parse(root + file + digest + link + target + "END\n").entries) == {
        ".",
        "./colour.txt",
        "./l",
    }
    for text, match in (
        (root + file + "END\n", "incomplete"),  # digest line removed: contents unbound
        (root + link + "END\n", "incomplete"),  # link target removed
        (root + "M|directory|755|./d\n" + "0" * 64 + "  ./d\nEND\n", "incomplete"),
        (root + "M|door|644|./x\nEND\n", "unrecognised"),
        (file + digest + "END\n", "working directory itself"),
        (root + target + "END\n", "without metadata"),
    ):
        with pytest.raises(B.BindingUnavailable, match=match):
            B.parse(text)


def _repair_script(path, content):
    return [
        _turn("finish", {"summary": "done"}, "s1"),
        _turn("write_file", {"path": path, "content": content}, "v1"),
        _turn("finish", {"verdict": "no_defect_found", "evidence": "it is blue"}, "v2"),
        _turn("finish", {"summary": "kept as is"}, "s2"),
    ]


def test_a_large_deliverable_repaired_in_the_copy_voids_the_finding(tmp_path):
    """Codex control: 21 MiB colour.txt starting red; the verifier writes a small blue one in its copy."""
    work = tmp_path / "box" / "work"
    work.mkdir(parents=True)
    (work / "colour.txt").write_text("red\n" + "x" * (21 * MIB))
    result, client, _, box = _run(tmp_path, _repair_script("colour.txt", "blue\n"))
    row = result.extras["verification"]
    assert row["status"] == "void_candidate_modified"
    assert row["clone_changes"]["modified"] == ["./colour.txt"]
    assert "void" in json.dumps(client.requests[3]["messages"][-1])
    assert (box / "work" / "colour.txt").read_text().startswith("red\n")


def test_a_permission_change_in_the_copy_voids_the_finding(tmp_path):
    """The binding is under test, not who changed the bits: the copy's run.sh gains +x (the fake clone cannot host
    a terminal)."""
    work = tmp_path / "box" / "work"
    work.mkdir(parents=True)
    (work / "run.sh").write_text("echo blue\n")

    async def chmodded(env, timeout_s=None):
        made = PathClone(tmp_path / "box")
        os.chmod(made.root / "work" / "run.sh", 0o755)
        return made

    script = [
        _turn("finish", {"summary": "done"}, "s1"),
        _turn("read_file", {"path": "run.sh"}, "v1"),
        _turn(
            "finish", {"verdict": "no_defect_found", "evidence": "prints blue"}, "v2"
        ),
        _turn("finish", {"summary": "kept"}, "s2"),
    ]
    result, _, _, box = _run(tmp_path, script, make_clone=chmodded)
    row = result.extras["verification"]
    assert row["status"] == "void_candidate_modified"
    assert row["clone_changes"]["modified"] == ["./run.sh"]
    assert not os.access(box / "work" / "run.sh", os.X_OK)


def test_a_finding_the_check_cannot_bind_is_marked_unbound_and_holds_nothing(
    tmp_path,
):
    async def no_sha_clone(env, timeout_s=None):
        made = PathClone(tmp_path / "box")
        inner = made.exec

        async def exec(command, cwd=None, env=None, timeout_sec=None):
            if "sha256sum" in command:  # only the manifest loses sha256sum
                command = "PATH=/nonexistent; " + command
            return await inner(command, cwd=cwd, env=env, timeout_sec=timeout_sec)

        made.exec = exec
        return made

    script = [
        _turn("write_file", {"path": "colour.txt", "content": "blue\n"}, "s1"),
        _turn("finish", {"summary": "done"}, "s2"),
        _turn("finish", {"verdict": "no_defect_found", "evidence": "blue"}, "v1"),
    ]
    result, client, _, _ = _run(tmp_path, script, make_clone=no_sha_clone)
    row = result.extras["verification"]
    assert row["status"] == "no_defect_found_unbound" and row["binding_unavailable"]
    assert result.status == "finished" and not client.script


# The check's time, with the real Clone.create and delayed host boundaries.


def _host(delay_s, *, honour_timeout=True, slow=("commit",)):
    """A docker host whose slow commands take ``delay_s``; with honour_timeout False it ignores the timeout it is
    given, like a daemon operation that outlives its client."""

    async def host(argv, timeout_s):
        if argv[1] == "inspect":
            return 0, "c" * 64, ""
        if (
            argv[1] == "exec"
        ):  # the identity proof: read back the token the environment wrote
            with open(argv[-1]) as fh:
                return 0, fh.read(), ""
        if argv[1] in slow:
            if honour_timeout and delay_s > timeout_s:
                await asyncio.sleep(timeout_s)
                return 124, "", f"timed out after {timeout_s:.1f}s"
            await asyncio.shield(asyncio.sleep(delay_s))
        return 0, "", ""

    return host


def _clone_factory(host, root):
    async def make(env, timeout_s=None):
        made = await Clone.create(env, host=host, known="cid", timeout_s=timeout_s)
        return PathCloneNamed(root, made)

    return make


class PathCloneNamed(PathClone):
    """The real Clone's lifecycle (create and close through the host) over a copied box for its file system."""

    def __init__(self, root, real):
        super().__init__(root)
        self.real = real

    async def close(self):
        await self.real.close()
        self.closed = True


def _timed(tmp_path, monkeypatch, host, budget_s=2.0):
    monkeypatch.setattr(V, "VERIFY_MAX_S", budget_s)
    script = [
        _turn("write_file", {"path": "colour.txt", "content": "blue\n"}, "s1"),
        _turn("finish", {"summary": "done"}, "s2"),
        _turn("finish", {"verdict": "no_defect_found", "evidence": "blue"}, "v1"),
    ]
    started = time.monotonic()
    result, client, _, _ = _run(
        tmp_path, script, make_clone=_clone_factory(host, tmp_path / "box")
    )
    return result, client, time.monotonic() - started


def test_a_slow_docker_commit_is_bounded_by_the_checks_time(tmp_path, monkeypatch):
    result, client, wall = _timed(tmp_path, monkeypatch, _host(30))
    row = result.extras["verification"]
    assert result.status == "finished" and row["status"] == "error"
    # the commit's own bound (Clone.create got the work time) and the check's end coincide: either may report
    assert row["reason"] and row["elapsed_s"] <= 2.0 + 0.3
    assert wall < 5


def test_a_shielded_operation_that_ignores_its_timeout_is_handed_off_not_waited_for(
    tmp_path, monkeypatch
):
    """Codex control: Clone.create shields creation and waits for it when cancelled."""
    result, _, wall = _timed(tmp_path, monkeypatch, _host(4, honour_timeout=False))
    row = result.extras["verification"]
    assert result.status == "finished" and row["elapsed_s"] <= 2.0 + 0.3
    assert "handed to run-end cleanup" in row["cleanup"]
    # run-end cleanup owned it to completion: the commit finished, and the clone it made was removed
    assert result.extras["cleanup_errors"] == []
    assert wall >= 4


def test_a_removal_that_outlives_the_checks_end_is_handed_off_and_owned_to_completion():
    """_close at the check's end: a clone removal (through the real Clone.close) that runs past it is handed to
    run-end cleanup, which awaits it; nothing is dropped."""
    from types import SimpleNamespace

    async def scenario():
        clone = Clone("n", "img", _host(0.5, honour_timeout=False, slow=("rm",)))
        s = SimpleNamespace(pending_cleanup=[])
        row: dict = {}
        started = time.monotonic()
        await V._close(s, {"clone": clone}, row, time.monotonic() + 0.1)
        returned_after = time.monotonic() - started
        ((label, task),) = s.pending_cleanup
        await task
        return row, returned_after, label, task

    row, returned_after, label, task = asyncio.run(scenario())
    assert returned_after < 0.3 and "handed to run-end cleanup" in row["close_error"]
    assert label == "verifier clone close" and task.done() and task.exception() is None


# Linux qualification (runs where a docker daemon is available): the real manifest script in real containers,
# GNU stat, a real commit-clone, and Clone.create under a deadline too short to finish.


def _docker_image_with_tools():
    import shutil
    import subprocess

    if (
        not shutil.which("docker")
        or subprocess.run(["docker", "info"], capture_output=True).returncode
    ):
        return None
    local = subprocess.run(
        ["docker", "image", "ls", "--format", "{{.Repository}}:{{.Tag}}"],
        capture_output=True,
        text=True,
    ).stdout.split()
    probe = (
        "command -v sha256sum && command -v find && stat -c %a . && command -v readlink"
    )
    for image in local:
        if "<none>" in image or image.startswith("aether-clone"):
            continue
        ok = subprocess.run(
            ["docker", "run", "--rm", "--entrypoint", "sh", image, "-c", probe],
            capture_output=True,
            timeout=120,
        )
        if ok.returncode == 0:
            return image
    return None


class _Live:
    def __init__(self, name):
        self.name = name

    async def exec(self, command, cwd=None, env=None, timeout_sec=None):
        import subprocess
        from types import SimpleNamespace

        p = await asyncio.to_thread(
            subprocess.run,
            ["docker", "exec", self.name, "sh", "-c", command],
            capture_output=True,
            text=True,
        )
        return SimpleNamespace(
            return_code=p.returncode, stdout=p.stdout, stderr=p.stderr
        )


def test_linux_the_manifest_binds_a_real_clone_and_sees_its_repairs():
    import subprocess
    import uuid

    image = _docker_image_with_tools()
    if image is None:
        pytest.skip(
            "needs a docker daemon and an image with sha256sum, find, GNU stat and readlink"
        )
    name = f"aether-binding-test-{uuid.uuid4().hex[:8]}"
    setup = (
        "mkdir -p /data/.git && head -c 22020096 /dev/zero > /data/big.bin && echo hi > /data/run.sh "
        "&& ln -s run.sh /data/link && sleep 600"
    )
    subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--rm",
            "--name",
            name,
            "--entrypoint",
            "sh",
            image,
            "-c",
            setup,
        ],
        check=True,
        capture_output=True,
    )
    try:
        live = _Live(name)

        async def go():
            for _ in range(50):  # wait for the set-up command
                if (await live.exec("test -L /data/link")).return_code == 0:
                    break
                await asyncio.sleep(0.2)
            before = await B.manifest(live, "/data")
            clone = await Clone.create(live, timeout_s=300)
            try:
                same = await B.manifest(clone, "/data")
                await clone.exec(
                    "chmod +x /data/run.sh && echo blue > /data/big.bin && echo s > /data/new.log"
                )
                after = await B.manifest(clone, "/data")
            finally:
                await clone.close()
            original = await B.manifest(live, "/data")
            with pytest.raises((TimeoutError, CloneError)):
                await Clone.create(live, timeout_s=0.05)
            return before, same, after, original

        before, same, after, original = asyncio.run(go())
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)
    assert before.entries["./big.bin"].startswith("regular file|644|")  # GNU stat path
    assert before.entries["./link"].startswith("symbolic link|777|->run.sh")
    assert before.unbound == ["./.git"]
    assert B.changes(before, same) == {"modified": [], "deleted": [], "created": []}
    assert B.changes(before, after) == {
        "modified": ["./big.bin", "./run.sh"],
        "deleted": [],
        "created": ["./new.log"],
    }
    assert B.changes(before, original) == {"modified": [], "deleted": [], "created": []}
    leftovers = subprocess.run(
        ["docker", "ps", "-a", "--filter", "name=aether-clone", "-q"],
        capture_output=True,
        text=True,
    ).stdout.split()
    assert leftovers == []
