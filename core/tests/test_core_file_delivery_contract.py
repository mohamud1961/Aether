"""Red-before regression controls for Core file delivery evidence.

Source: aether-core at cd834c6e367cdda0c1cd9e94770c6fb899fb5545 (C0 destination).
These are high-level controls over ACTUAL Core code and REAL local filesystem IO
(``tests.core_fakes.LocalEnv``), not mirrors of helper structure. Each scenario
states the externally observable contract the harness must keep when a run says
what it delivered.

Three controls are expected to be RED on this source; they encode failures that
already exist, and must not be xfailed, skipped or weakened to look green:

1. literal path identity   - ``Files.write`` then ``receipt.changed`` must return
   the file names that really exist, or say the listing is unknown. Newline and
   U+0085 (NEL) names are legal here and currently split into false paths.
2. destination acknowledgement - a synthetic transport fault rewrites the
   committed destination before the write call returns; the call must report an
   error/uncertainty instead of a clean "wrote N bytes".
3. unreadable subtree      - a real ``chmod 000`` subtree hides truly changed
   files; the current listing and finish report present that as authoritative
   and incomplete/empty instead of unknown.

Positive controls (ordinary/space/tab/backslash/NBSP names, absolute paths,
symlink writes, unconditional replace with permission preservation) must stay
green: the fix may not buy literal identity by rejecting legal workflows.

Limits: no containment policy, no new filename bans, no arbitrary-writer CAS,
no permanent integrity, no provider/model/Harbor/benchmark involvement.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
from pathlib import Path
import re
import time

import pytest

from aether.core import finish_report, receipt
from aether.core.files import Files
from tests.core_fakes import LocalEnv

# Generated, fixed, safe fixtures: literal POSIX names a Core run may legitimately create.
NAMES = {
    "ordinary.txt": b"ordinary payload\n",
    "space led.txt": b"space payload\n",
    "nbsp\u00a0name.txt": b"nbsp payload\n",
    "tab\tname.txt": b"tab payload\n",
    "back\\slash.txt": b"backslash payload\n",
    "line\nname.txt": b"newline payload\n",
    "nel\u0085name.txt": b"nel payload\n",
}
LINE_BREAKERS = {"line\nname.txt", "nel\u0085name.txt"}

# A returned message may declare uncertainty in place of an error; it may not
# claim the destination matches what was submitted without saying so.
UNCERTAIN = re.compile(
    r"uncertain|unverif|could not (?:be )?confirm|cannot confirm|not confirmed|"
    r"mismatch|differ|not verified",
    re.I,
)

SYNTHETIC_FAULT_LABEL = (
    "SYNTHETIC fault envelope: same-length rewrite of the committed destination after "
    "the rename succeeds and before the caller receives its acknowledgement"
)


def _mark_and_list(work: Path, ctl: Path, env: LocalEnv) -> None:
    asyncio.run(receipt.mark(env, str(ctl)))
    # Guarantee the marker is strictly older than everything written below,
    # even on a filesystem with coarse mtime granularity.
    time.sleep(0.05)


def _actual_files(root: Path) -> set[str]:
    """Independent oracle: what the working directory really contains.

    Symlinks are excluded because Core's listing enumerates regular files only;
    following one is a separate (positive) workflow check.
    """
    return {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and not path.is_symlink()
    }


def _listed(env: LocalEnv, work: Path, ctl: Path) -> tuple[list[str] | None, str | None]:
    try:
        return asyncio.run(receipt.changed(env, str(work), str(ctl))), None
    except OSError as exc:  # an explicit failure is an acceptable outcome
        return None, str(exc)


class MutateAfterCommit(LocalEnv):
    """A real local environment whose transport mutates the destination once.

    The fault is injected only at the local environment boundary, after a
    successful rename command returns and before Core sees that success. It is
    not a claimed model of arbitrary concurrent writers or durable corruption.
    """

    def __init__(self, root: Path, target: Path) -> None:
        super().__init__(root)
        self.target = target
        self.fired = False
        self.actual_at_return: bytes | None = None

    async def exec(self, command, cwd=None, env=None, timeout_sec=None):
        result = await super().exec(command, cwd=cwd, env=env, timeout_sec=timeout_sec)
        if not self.fired and result.return_code == 0 and (
            "mv -fT" in command or "os.replace" in command
        ):
            self.fired = True
            self.target.write_bytes(b"EVIL")  # same length as the submitted b"GOOD"
            self.actual_at_return = self.target.read_bytes()
        return result


def test_changed_files_keep_literal_identity_or_say_unknown(tmp_path):
    work, ctl = tmp_path / "work", tmp_path / "ctl"
    work.mkdir()
    ctl.mkdir()
    env = LocalEnv(work)
    _mark_and_list(work, ctl, env)

    files = Files(env, str(work))
    for name, payload in NAMES.items():
        asyncio.run(files.write(name, payload.decode()))

    # The writes themselves are real: this is report identity, not failed creation.
    for name, payload in NAMES.items():
        assert (work / name).read_bytes() == payload

    expected = {"./" + name for name in _actual_files(work)}
    listed, reason = _listed(env, work, ctl)

    if listed is None:
        assert reason, "a listing failure must carry an explicit reason"
        return

    assert set(listed) == expected, (
        "changed-file evidence must match the names actually created, or be reported "
        f"as unknown; missing={sorted(expected - set(listed))} "
        f"false={sorted(set(listed) - expected)}"
    )

    report = asyncio.run(finish_report.build(
        env, str(work), str(ctl), [], status="finished", finish_summary="done", left_running=[]
    ))
    measured = {Path(row["path"]).relative_to(work).as_posix(): row for row in report["delivered_files"]}
    assert set(measured) == set(NAMES)
    for name, payload in NAMES.items():
        assert measured[name]["sha256"] == hashlib.sha256(payload).hexdigest()
        assert measured[name]["bytes"] == len(payload)


def test_ordinary_whitespace_unicode_absolute_and_symlink_writes_stay_exact(tmp_path):
    work, ctl = tmp_path / "work", tmp_path / "ctl"
    work.mkdir()
    ctl.mkdir()
    (work / "target.txt").write_bytes(b"before symlink write\n")
    (work / "alias.txt").symlink_to("target.txt")
    env = LocalEnv(work)
    _mark_and_list(work, ctl, env)
    files = Files(env, str(work))

    for name, payload in NAMES.items():
        if name in LINE_BREAKERS:
            continue
        asyncio.run(files.write(name, payload.decode()))
    asyncio.run(files.write(str(work / "absolute.txt"), "absolute payload\n"))
    message = asyncio.run(files.write("alias.txt", "after symlink write\n"))

    assert (work / "alias.txt").is_symlink(), "writing through a symlink keeps the link"
    assert (work / "target.txt").read_bytes() == b"after symlink write\n"
    assert "wrote" in message

    expected = {"./" + name for name in _actual_files(work)}
    listed, reason = _listed(env, work, ctl)
    assert reason is None and listed is not None
    assert set(listed) == expected


def test_destination_mutation_between_commit_and_ack_is_not_a_clean_write(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    target = work / "out.txt"
    env = MutateAfterCommit(work, target)

    try:
        returned = asyncio.run(Files(env, str(work)).write("out.txt", "GOOD"))
        raised = None
    except OSError as exc:
        returned, raised = None, str(exc)

    # Prove the injected fault really landed before judging the report.
    assert env.fired, "synthetic fault did not fire; the control would prove nothing"
    assert env.actual_at_return == b"EVIL"
    assert target.read_bytes() == b"EVIL"

    if raised is not None:
        return  # an explicit error is an honest outcome
    assert UNCERTAIN.search(returned or ""), (
        "the committed bytes were replaced before the call returned, yet the write "
        f"was reported as a clean success: {returned!r} ({SYNTHETIC_FAULT_LABEL})"
    )


def test_plain_replace_and_new_write_still_succeed_with_mode_preserved(tmp_path):
    work, ctl = tmp_path / "work", tmp_path / "ctl"
    work.mkdir()
    ctl.mkdir()
    kept = work / "kept.txt"
    kept.write_bytes(b"prior work here\n")
    kept.chmod(0o751)
    env = LocalEnv(work)
    _mark_and_list(work, ctl, env)
    files = Files(env, str(work))

    replace_message = asyncio.run(files.write("kept.txt", "replaced\n"))
    new_message = asyncio.run(files.write("fresh.txt", "made\n"))

    assert kept.read_bytes() == b"replaced\n"
    assert kept.stat().st_mode & 0o777 == 0o751
    assert (work / "fresh.txt").read_bytes() == b"made\n"
    assert "wrote 9 bytes" in replace_message and "(new file)" not in replace_message
    assert "wrote 5 bytes" in new_message and "(new file)" in new_message

    listed, reason = _listed(env, work, ctl)
    assert reason is None and listed is not None
    assert set(listed) == {"./" + name for name in {"kept.txt", "fresh.txt"}}


def test_unreadable_subtree_is_not_an_authoritative_delivery_listing(tmp_path):
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        pytest.skip(
            "test unavailable on this host: root can read a chmod 000 subtree, so the "
            "real permission fault cannot be created (no permission mock substitutes)"
        )
    work, ctl = tmp_path / "work", tmp_path / "ctl"
    work.mkdir()
    ctl.mkdir()
    env = LocalEnv(work)
    _mark_and_list(work, ctl, env)
    (work / "visible.txt").write_bytes(b"visible payload\n")
    locked = work / "locked"
    locked.mkdir()
    (locked / "inside.txt").write_bytes(b"hidden payload\n")
    expected = {"./" + name for name in _actual_files(work)}

    locked.chmod(0)
    try:
        listed, reason = _listed(env, work, ctl)
        report = asyncio.run(
            finish_report.build(
                env,
                str(work),
                str(ctl),
                [],
                status="finished",
                finish_summary="done",
                left_running=[],
            )
        )
    finally:
        locked.chmod(0o755)

    if listed is None:
        assert reason, "a listing failure must carry an explicit reason"
    if listed is None or set(listed) != expected:
        # Incomplete or absent enumeration may not be presented as the current delivery.
        assert isinstance(report["delivered_files"], str), (
            "a real changed file was dropped and the finish report still presented a "
            f"file list: {report['delivered_files']!r}"
        )
        assert "delivered files: unknown" in finish_report.render(report)
    else:
        delivered = {Path(row["path"]).name for row in report["delivered_files"]}
        assert delivered == {"visible.txt", "inside.txt"}


def test_readable_tree_yields_the_exact_listing_and_measured_files(tmp_path):
    work, ctl = tmp_path / "work", tmp_path / "ctl"
    work.mkdir()
    ctl.mkdir()
    env = LocalEnv(work)
    _mark_and_list(work, ctl, env)
    (work / "visible.txt").write_bytes(b"visible payload\n")
    (work / "sub").mkdir()
    (work / "sub" / "nested.txt").write_bytes(b"nested payload\n")

    listed, reason = _listed(env, work, ctl)
    assert reason is None and listed is not None
    assert set(listed) == {"./sub/nested.txt", "./visible.txt"}

    report = asyncio.run(
        finish_report.build(
            env,
            str(work),
            str(ctl),
            [],
            status="finished",
            finish_summary="done",
            left_running=[],
        )
    )
    rows = {Path(row["path"]).name: row for row in report["delivered_files"]}
    assert set(rows) == {"visible.txt", "nested.txt"}
    assert rows["nested.txt"]["bytes"] == len(b"nested payload\n")
    assert len(rows["nested.txt"]["sha256"]) == 64


def test_symlink_pivot_at_commit_is_reported_as_uncertain_without_rollback(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    original, other, alias = work / "original", work / "other", work / "alias"
    original.write_bytes(b"prior")
    other.write_bytes(b"other")
    alias.symlink_to(original.name)

    class PivotAtCommit(LocalEnv):
        async def exec(self, command, **kwargs):
            result = await super().exec(command, **kwargs)
            if result.return_code == 0 and ("mv -fT" in command or "os.replace" in command):
                alias.unlink()
                alias.symlink_to(other.name)
            return result

    with pytest.raises(OSError, match="write committed.*(destination bytes differ|could not be verified)"):
        asyncio.run(Files(PivotAtCommit(work), str(work)).write("alias", "GOOD"))
    assert original.read_bytes() == b"GOOD"  # actual effect retained, never rolled back
    assert alias.is_symlink() and alias.read_bytes() == b"other"
    assert not list(work.glob("*.aether-*.tmp"))


def test_lost_readback_reports_committed_but_unverified_effect(tmp_path):
    class LostReadback(LocalEnv):
        committed = False
        async def exec(self, command, **kwargs):
            if self.committed and "sha256sum <" in command:
                from types import SimpleNamespace
                return SimpleNamespace(return_code=1, stdout="", stderr="synthetic lost readback")
            result = await super().exec(command, **kwargs)
            if result.return_code == 0 and ("mv -fT" in command or "os.replace" in command):
                self.committed = True
            return result

    files = Files(LostReadback(tmp_path), str(tmp_path))
    with pytest.raises(OSError, match="write committed.*could not be verified"):
        asyncio.run(files.write("artifact", "GOOD"))
    assert (tmp_path / "artifact").read_bytes() == b"GOOD"
    assert not files.written  # no verified receipt is manufactured
    assert not list(tmp_path.glob("*.aether-*.tmp"))


def test_thrown_readback_fault_preserves_committed_effect_evidence(tmp_path):
    class ThrownReadback(LocalEnv):
        committed = False
        async def exec(self, command, **kwargs):
            if self.committed and "sha256sum <" in command:
                raise TimeoutError("transport lost after commit")
            result = await super().exec(command, **kwargs)
            if result.return_code == 0 and ("mv -fT" in command or "os.replace" in command):
                self.committed = True
            return result

    files = Files(ThrownReadback(tmp_path), str(tmp_path))
    with pytest.raises(OSError, match="write committed.*could not be verified"):
        asyncio.run(files.write("artifact", "GOOD"))
    assert (tmp_path / "artifact").read_bytes() == b"GOOD" and not files.written


def test_recorded_write_with_old_mtime_is_measured_and_inventory_limit_is_explicit(tmp_path):
    work, ctl = tmp_path / "work", tmp_path / "ctl"
    work.mkdir(); ctl.mkdir()
    env = LocalEnv(work)
    asyncio.run(receipt.mark(env, str(ctl)))
    (work / "artifact").write_bytes(b"GOOD")
    marker = (ctl / receipt.MARKER).stat()
    os.utime(work / "artifact", ns=(marker.st_atime_ns, marker.st_mtime_ns))
    step = finish_report.record(1, "write_file", {"path": "artifact"}, "wrote 4 bytes", str(work))
    report = asyncio.run(finish_report.build(env, str(work), str(ctl), [step], status="finished", finish_summary="done", left_running=[]))
    assert report["delivered_files"][0]["sha256"] == hashlib.sha256(b"GOOD").hexdigest()
    assert report["delivery_inventory_complete"] is False
    assert "not an exhaustive change inventory" in finish_report.render(report)
