from __future__ import annotations
import io
import tarfile
from pathlib import Path

from evals.performance.h10_acquire_metadata_sources import _task_toml_relative, extract_task_tomls


def test_task_toml_member_filter_rejects_non_metadata():
    assert _task_toml_relative('repo/tasks/a/task.toml', 'tasks') == Path('tasks/a/task.toml')
    assert _task_toml_relative('repo/tasks/a/instruction.md', 'tasks') is None
    assert _task_toml_relative('repo/a/task.toml', None) == Path('a/task.toml')
    assert _task_toml_relative('repo/a/instruction.md', None) is None
    assert _task_toml_relative('repo/checks/test-tasks/a/task.toml', 'tasks') is None


def _archive(rows):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode='w:gz') as tf:
        for name, raw in rows:
            info = tarfile.TarInfo(name)
            info.size = len(raw)
            tf.addfile(info, io.BytesIO(raw))
    return buf.getvalue()


def test_extract_materializes_only_tb4_task_toml(tmp_path: Path):
    raw = _archive((
        ('repo/tasks/a/task.toml', b'[metadata]\ncategory="x"\n'),
        ('repo/tasks/a/instruction.md', b'SECRET INSTRUCTION'),
        ('repo/checks/test-tasks/fake/task.toml', b'[metadata]\ncategory="fake"\n'),
    ))
    count = extract_task_tomls(raw, tmp_path / 'out', 'tasks')
    assert count == 1
    assert (tmp_path / 'out/tasks/a/task.toml').is_file()
    assert not (tmp_path / 'out/tasks/a/instruction.md').exists()
    assert not (tmp_path / 'out/checks/test-tasks/fake/task.toml').exists()


def test_extract_materializes_only_tb2_root_task_toml(tmp_path: Path):
    raw = _archive((
        ('repo/a/task.toml', b'[metadata]\ncategory="x"\n'),
        ('repo/a/instruction.md', b'SECRET INSTRUCTION'),
        ('repo/nested/a/task.toml', b'[metadata]\ncategory="fake"\n'),
    ))
    count = extract_task_tomls(raw, tmp_path / 'out', None)
    assert count == 1
    assert (tmp_path / 'out/a/task.toml').is_file()
    assert not (tmp_path / 'out/a/instruction.md').exists()
    assert not (tmp_path / 'out/nested/a/task.toml').exists()
