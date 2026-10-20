"""File fidelity: pages are retrievable, paths exact, interrupted writes preserve prior work."""

import asyncio
from pathlib import Path

import pytest

from aether.core.files import Files
from tests.core.core_fakes import LocalEnv


def test_blank_lines_and_whitespace_in_paths_are_real_text(tmp_path):
    name = "  spaced.txt "
    (tmp_path / name).write_text("\n\n")
    result = asyncio.run(Files(LocalEnv(tmp_path), str(tmp_path)).read(name))
    assert "binary" not in result and "of 2" in result


def test_a_long_line_has_a_page_that_reaches_the_tail(tmp_path):
    (tmp_path / "long.txt").write_text("α" * 30000 + "TAIL-MARKER\n")
    files = Files(LocalEnv(tmp_path), str(tmp_path))
    first = asyncio.run(files.read("long.txt"))
    assert "next_offset=" in first
    offset = int(first.split("next_offset=", 1)[1].split()[0].rstrip("];"))
    second = asyncio.run(files.read("long.txt", offset=offset))
    assert "TAIL-MARKER" in second


def test_failed_upload_does_not_damage_existing_bytes_or_permissions(tmp_path):
    target = tmp_path / "existing"
    target.write_text("precious prior work")
    target.chmod(0o751)

    class CutUpload(LocalEnv):
        async def upload_file(self, source_path, target_path):
            Path(target_path).write_bytes(b"partial upload")
            raise OSError("upload cut off")

    with pytest.raises(OSError, match="upload cut"):
        asyncio.run(
            Files(CutUpload(tmp_path), str(tmp_path)).write("existing", "x" * 60000)
        )
    assert (
        target.read_text() == "precious prior work"
        and target.stat().st_mode & 0o777 == 0o751
    )


def test_atomic_write_keeps_a_symlink_and_updates_its_target(tmp_path):
    target = tmp_path / "target"
    target.write_text("before")
    alias = tmp_path / "alias"
    alias.symlink_to("target")
    asyncio.run(Files(LocalEnv(tmp_path), str(tmp_path)).write("alias", "after"))
    assert alias.is_symlink() and target.read_text() == "after"


@pytest.mark.parametrize("via_symlink", [False, True])
def test_directory_target_is_not_reported_as_a_successful_file_write(
    tmp_path, via_symlink
):
    directory = tmp_path / "out"
    directory.mkdir()
    path = directory
    if via_symlink:
        path = tmp_path / "alias"
        path.symlink_to(directory)
    with pytest.raises(OSError, match="directory"):
        asyncio.run(
            Files(LocalEnv(tmp_path), str(tmp_path)).write(str(path), "content")
        )
    assert list(directory.iterdir()) == []


def test_a_directory_created_during_transfer_is_never_used_as_a_destination(tmp_path):
    target = tmp_path / "out"

    class DirectoryAppears(LocalEnv):
        async def exec(self, command, **kwargs):
            if "uname -s" in command:
                target.mkdir()
            return await super().exec(command, **kwargs)

    with pytest.raises(OSError, match="committing write"):
        asyncio.run(
            Files(DirectoryAppears(tmp_path), str(tmp_path)).write("out", "content")
        )
    assert list(target.iterdir()) == []
    assert not list(tmp_path.glob("*.aether-*.tmp"))
