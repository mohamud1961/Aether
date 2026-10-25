"""Actual inaccessible files must not be classified as successfully read binary data."""
import asyncio
import os

import pytest

from aether.core.files import Files
from tests.core_fakes import LocalEnv


def test_unreadable_text_reports_an_error_and_recovers_after_permissions_restored(tmp_path):
    if os.geteuid() == 0:
        pytest.skip("root cannot create the real read-permission failure")
    target = tmp_path / "source.txt"
    target.write_text("actual text\n")
    files = Files(LocalEnv(tmp_path), str(tmp_path))
    target.chmod(0)
    try:
        with pytest.raises(OSError):
            asyncio.run(files.read(target.name))
    finally:
        target.chmod(0o600)
    assert "actual text" in asyncio.run(files.read(target.name))


def test_empty_whitespace_binary_and_multibyte_pages_remain_distinct(tmp_path):
    files = Files(LocalEnv(tmp_path), str(tmp_path))
    (tmp_path / "empty").write_bytes(b"")
    (tmp_path / "blank").write_bytes(b"\n\n")
    (tmp_path / "binary").write_bytes(b"\0\xff\0\x01")
    (tmp_path / "long").write_text("α" * 30000 + "TAIL\n")
    assert "of 0" in asyncio.run(files.read("empty"))
    assert "of 2" in asyncio.run(files.read("blank"))
    assert "binary file, 4 bytes" in asyncio.run(files.read("binary"))
    first = asyncio.run(files.read("long"))
    offset = int(first.split("next_offset=", 1)[1].split("]", 1)[0])
    assert "TAIL" in asyncio.run(files.read("long", offset=offset))


def test_second_read_stage_failure_is_not_a_successful_empty_page(tmp_path):
    import shlex
    import shutil
    from pathlib import Path

    real_awk = shutil.which("awk")
    assert real_awk, "real awk is required for this failure-injection control"
    source = tmp_path / "source.txt"
    source.write_text("important source text\n")
    toolbin = tmp_path / "fault-bin"
    toolbin.mkdir()
    count, fired = tmp_path / "awk-count", tmp_path / "fault-fired"
    wrapper = toolbin / "awk"
    wrapper.write_text(
        "#!/bin/sh\n"
        f"if [ -f {shlex.quote(str(count))} ]; then touch {shlex.quote(str(fired))}; "
        "echo 'synthetic second-stage read failure' >&2; exit 7; fi\n"
        f"touch {shlex.quote(str(count))}\nexec {shlex.quote(real_awk)} \"$@\"\n"
    )
    wrapper.chmod(0o700)

    class FailingPageEnv(LocalEnv):
        async def exec(self, command, **kwargs):
            return await super().exec("PATH=" + shlex.quote(str(toolbin)) + ':"$PATH"; ' + command, **kwargs)

    try:
        with pytest.raises(OSError):
            asyncio.run(Files(FailingPageEnv(tmp_path), str(tmp_path)).read(source.name))
    finally:
        assert fired.exists(), "the negative must actually reach the failing second read"
    assert source.read_text() == "important source text\n"
