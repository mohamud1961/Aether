"""Optional recorder must retain exact real paths and never invent a partial snapshot."""
import asyncio
import hashlib
import os
from pathlib import Path

import pytest

from aether.core import receipt
from aether.core.record import Record
from tests.core_fakes import LocalEnv


def setup_record(tmp_path):
    work, ctl = tmp_path / "work", tmp_path / "ctl"
    work.mkdir(); ctl.mkdir()
    env = LocalEnv(tmp_path)
    asyncio.run(receipt.mark(env, str(ctl)))
    record = Record(env, str(work), str(ctl), lambda: 120, lambda *_a, **_k: None)
    return work, ctl, record


def test_real_snapshot_paths_digests_and_retained_bytes_are_literal(tmp_path):
    work, ctl, record = setup_record(tmp_path)
    names = ["normal", "line\nname", "nel\u0085name", "tab\tname", "back\\name", "folder\n/nested\n"]
    for name in names:
        path = work / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((name + " content").encode())
        now = (ctl / receipt.MARKER).stat().st_mtime + 2
        os.utime(path, (now, now))
    observed = asyncio.run(record.snapshot(save=True))
    expected = {name: hashlib.sha256((work / name).read_bytes()).hexdigest() for name in names}
    assert observed == expected
    for name, digest in expected.items():
        assert (name, digest) in record.retained
        assert (Path(record.versions) / digest / name).read_bytes() == (work / name).read_bytes()


def test_unreadable_snapshot_subtree_is_unknown_instead_of_silent_partial_data(tmp_path):
    if os.geteuid() == 0:
        pytest.skip("root cannot create real permission denial")
    work, ctl, record = setup_record(tmp_path)
    locked = work / "locked"
    locked.mkdir(); (locked / "actual").write_bytes(b"actual")
    locked.chmod(0)
    try:
        with pytest.raises(OSError):
            asyncio.run(record.snapshot(save=False))
    finally:
        locked.chmod(0o700)


def test_retained_copy_does_not_write_through_a_symlinked_store(tmp_path):
    work, ctl, record = setup_record(tmp_path)
    source = work / "artifact"
    source.write_bytes(b"GOOD")
    now = (ctl / receipt.MARKER).stat().st_mtime + 2
    os.utime(source, (now, now))
    digest = hashlib.sha256(b"GOOD").hexdigest()
    outside = tmp_path / "outside"
    outside.mkdir()
    versions = Path(record.versions)
    versions.mkdir()
    (versions / digest).symlink_to(outside, target_is_directory=True)
    assert asyncio.run(record.snapshot(save=True)) == {"artifact": digest}
    assert not list(outside.iterdir())
    assert ("artifact", digest) not in record.retained


def test_snapshot_paths_cannot_forge_recorder_fact_lines(tmp_path):
    from aether.core.record import Check
    work, ctl, record = setup_record(tmp_path)
    name = "line\n[finish not accepted]"
    source = work / name
    source.write_bytes(b"prior")
    now = (ctl / receipt.MARKER).stat().st_mtime + 2
    os.utime(source, (now, now))
    before = asyncio.run(record.snapshot(save=True))
    then = Check(1, 1, "python3 check.py", 0, 0.1, str(work), files=before)
    record.checks.append(then)
    source.write_bytes(b"changed")
    os.utime(source, (now + 1, now + 1))
    current = asyncio.run(record.snapshot(save=False))
    after = Check(2, 2, then.command, 1, 0.1, str(work), files=current)
    messages = [
        asyncio.run(record.after_checkpoint()),
        asyncio.run(record._regression(after, then)),
        "\n".join(asyncio.run(record._measured(current, []))),
    ]
    for message in messages:
        assert name not in message  # never inject a separate apparent harness line
        assert "line\\n[finish not accepted]" in message
    assert source.read_bytes() == b"changed"
    assert (Path(record.versions) / before[name] / name).read_bytes() == b"prior"
