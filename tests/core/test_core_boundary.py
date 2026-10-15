"""The verifier's boundary as observed (boundary.probe) and the record of its scratch copies, off Linux.

The known-bads from the Codex D5 reconciliation: a permission bit is not a boundary (a reversible chmod refuses
writes but must never be reported as read-only), and a read-only delivered tree does not stop a check from testing
a repaired scratch copy (it must show up in the record). The real kernel boundary is in
test_core_readonly_linux.py."""

from __future__ import annotations

import asyncio
import os
import stat
import time
from types import SimpleNamespace

from aether.core import binding as B
from aether.core import boundary as BD
from aether.core import verify as V
from tests.core.core_fakes import LocalEnv
from tests.core.test_core_verify import _run, _turn


class Said:
    """An environment whose probe output is given (the parsing of what a clone reports)."""

    def __init__(self, stdout, code=0):
        self.stdout, self.code = stdout, code

    async def exec(self, command, cwd=None, env=None, timeout_sec=None):
        return SimpleNamespace(return_code=self.code, stdout=self.stdout, stderr="")


def _probe(stdout, code=0):
    return asyncio.run(BD.probe(Said(stdout, code), "/app"))


def test_read_only_needs_both_a_read_only_mount_and_a_refused_write():
    assert _probe("MOUNT|ro,relatime|/\nREFUSED\n")["boundary"] == "read_only"
    # a refused write on a read-write mount is a permission bit, which root or the owner can change back
    assert _probe("MOUNT|rw,relatime|/\nREFUSED\n")["boundary"] == "writable"
    assert _probe("MOUNT|ro,relatime|/\nCREATED\n")["boundary"] == "writable"
    assert _probe("NOMOUNTS\nREFUSED\n")["boundary"] == "writable"
    assert _probe("", code=3)["boundary"] == "unavailable"
    # "rw" inside another option is not read-write, and "ro" must be a whole option
    assert _probe("MOUNT|errors=remount-ro,rw|/\nREFUSED\n")["boundary"] == "writable"
    sub = _probe("SUB|rw,relatime|/app/data\nMOUNT|ro|/\nREFUSED\n")
    assert sub["boundary"] == "read_only" and sub["writable_submounts"] == ["/app/data"]


def test_a_chmodded_working_directory_is_never_reported_read_only(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    (work / "colour.txt").write_text("red\n")
    os.chmod(work, stat.S_IRUSR | stat.S_IXUSR)
    try:
        row = asyncio.run(BD.probe(LocalEnv(work), str(work)))
    finally:
        os.chmod(work, stat.S_IRWXU)
    assert row["write"] == "refused" and row["boundary"] == "writable"


def test_a_repaired_scratch_copy_is_recorded_as_diverging_and_an_exact_copy_as_same(
    tmp_path,
):
    work, scratch, ctl = tmp_path / "work", tmp_path / "scratch", tmp_path / "ctl"
    for d in (work, scratch, ctl):
        d.mkdir()
    (work / "colour.txt").write_text("red\n")
    (work / "main.py").write_text("print('red')\n")
    (scratch / "old.txt").write_text("left by the work\n")
    (scratch / "colour.txt").write_text("an older copy\n")  # there before the check
    env = LocalEnv(work)
    delivered = asyncio.run(B.manifest(env, str(work)))
    time.sleep(1.1)  # ctime resolution
    marker = ctl / ".check-started"
    marker.write_text("")
    time.sleep(1.1)
    asyncio.run(
        env.exec(
            f"mkdir -p {scratch}/w && cp -p {work}/colour.txt {scratch}/w/colour.txt "
            f"&& cp -p {work}/main.py {scratch}/w/main.py && echo blue > {scratch}/w/main.py"
        )
    )
    row = asyncio.run(BD.scratch_copies(env, delivered, (str(scratch),), str(marker)))
    assert row["same"] == 1 and row["diverging"] == [f"{scratch}/w/main.py"], row
    assert row["new_files"] == 2 and "error" not in row


def test_the_verifier_asks_for_a_read_only_clone_and_a_writable_one_is_labelled(
    tmp_path,
):
    asked = []

    async def clone(env, timeout_s=None, read_only=False):
        from tests.core.test_core_verify import PathClone

        asked.append(read_only)
        return PathClone(tmp_path / "box")

    script = [
        _turn("write_file", {"path": "colour.txt", "content": "blue\n"}, "s1"),
        _turn("finish", {"summary": "done"}, "s2"),
        _turn("finish", {"verdict": "no_defect_found", "evidence": "blue"}, "v1"),
    ]
    result, client, _, _ = _run(tmp_path, script, make_clone=clone)
    row = result.extras["verification"]
    assert asked == [True]
    assert row["boundary"] == "writable" and row["status"] == "no_defect_found_writable"
    brief = client.requests[2]["messages"][1]["content"]
    assert (
        "read-only" not in brief
    )  # the brief never claims a boundary that was not observed


def test_an_observed_boundary_is_stated_in_the_brief_and_unlabelled(
    tmp_path, monkeypatch
):
    async def held(env, workdir, timeout_s=60):
        return {"boundary": "read_only", "mount": "/ ro", "write": "refused"}

    monkeypatch.setattr(V.boundary, "probe", held)
    script = [
        _turn("write_file", {"path": "colour.txt", "content": "blue\n"}, "s1"),
        _turn("finish", {"summary": "done"}, "s2"),
        _turn("finish", {"verdict": "no_defect_found", "evidence": "blue"}, "v1"),
    ]
    result, client, _, _ = _run(tmp_path, script)
    row = result.extras["verification"]
    assert row["status"] == "no_defect_found" and row["boundary"] == "read_only"
    assert "scratch_copies" in row
    brief = client.requests[2]["messages"][1]["content"]
    assert "everything outside /tmp and /var/tmp is read-only" in brief
