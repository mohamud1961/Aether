"""Adversarial controls for the finish inventory's observed-change boundary."""
from __future__ import annotations

import asyncio
import shlex
from pathlib import Path
import time

from aether.core import receipt
from tests.core_fakes import LocalEnv


def test_terminal_write_with_restored_mtime_remains_observable_by_change_time(tmp_path):
    work, control = tmp_path / "work", tmp_path / "control"
    work.mkdir()
    control.mkdir()
    target = work / "artifact.bin"
    target.write_bytes(b"before")
    env = LocalEnv(work)
    asyncio.run(receipt.mark(env, str(control)))
    marker = (control / receipt.MARKER).stat()

    # Reproduce a shell task that modifies bytes, then restores the old mtime.
    # POSIX ctime cannot be set by utime, so it remains an independent signal.
    time.sleep(0.05)
    command = (
        f"printf AFTER! > {shlex.quote(str(target))} && "
        f"touch -r {shlex.quote(str(control / receipt.MARKER))} {shlex.quote(str(target))}"
    )
    result = asyncio.run(env.exec(command, timeout_sec=30))
    assert result.return_code == 0, result.stderr
    assert target.stat().st_mtime_ns == marker.st_mtime_ns
    observed = asyncio.run(receipt.changed(env, str(work), str(control)))

    assert "./artifact.bin" in observed


def test_change_inventory_does_not_claim_deleted_files_or_complete_custody(tmp_path):
    work, control = tmp_path / "work", tmp_path / "control"
    work.mkdir()
    control.mkdir()
    target = work / "artifact.bin"
    target.write_bytes(b"old")
    env = LocalEnv(work)
    asyncio.run(receipt.mark(env, str(control)))
    target.unlink()

    observed = asyncio.run(receipt.changed(env, str(work), str(control)))
    assert observed == []  # current-file scan cannot prove historical deletion


def test_recorder_does_not_recursively_capture_its_own_control_store(tmp_path):
    from aether.core.record import Record
    work=tmp_path/'work';work.mkdir();control=work/'ctl';control.mkdir()
    env=LocalEnv(work)
    async def scenario():
        await receipt.mark(env,str(control))
        (work/'artifact.txt').write_text('actual task artifact')
        record=Record(env,str(work),str(control),lambda:100,lambda *a,**kw:None)
        first=await record.snapshot(save=True)
        second=await record.snapshot(save=True)
        assert first==second=={'artifact.txt': __import__('hashlib').sha256(b'actual task artifact').hexdigest()}
        assert len([p for p in (control/'versions').rglob('*') if p.is_file()])==1
    asyncio.run(scenario())
