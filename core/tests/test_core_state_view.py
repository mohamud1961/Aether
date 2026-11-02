"""The state view: a read-only command, installed with the start copy, that shows what changed since it."""

from __future__ import annotations

import asyncio
import shutil
import subprocess

import pytest

from aether.core import start_copy, state_view
from aether.core.harbor_agent import build_config
from tests.core_fakes import LocalEnv

BASE = {"AETHER_CORE_REVIEW": "off", "AETHER_CORE_CONTEXT": "clm", "AETHER_CORE_REPL": "off", "AETHER_CORE_IMAGES": "off"}
needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")


def _git(repo, *args):
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
           "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin", "HOME": str(repo)}
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True, env=env).stdout


def _repo(tmp_path):
    app = tmp_path / "my app"  # a space, so every path in the command must be quoted
    app.mkdir()
    _git(app, "init", "-q", "-b", "main")
    (app / "run.sh").write_text("export KEY=abc123\necho done\n")
    (app / "notes.md").write_text("keep me\n")
    _git(app, "add", "-A")
    _git(app, "commit", "-q", "-m", "start")
    return app


def _view(tmp_path, app):
    note, row = asyncio.run(start_copy.take(LocalEnv(tmp_path), str(app), str(tmp_path / "ctl"), view=True))
    assert row["copied"] and row["view"] == str(tmp_path / "ctl" / "bin" / "changes"), row
    return note, row, lambda: subprocess.run(["sh", row["view"]], capture_output=True, text=True, timeout=60)


@needs_git
def test_untouched_state_shows_no_differences_and_the_start_commit(tmp_path):
    app = _repo(tmp_path)
    note, row, run = _view(tmp_path, app)
    out = run()
    assert out.returncode == 0, out.stderr
    assert "files: no differences outside .git" in out.stdout
    assert f"git: HEAD is the start commit {row['start_head'][:7]}" in out.stdout
    assert "git: 0 of the 1 commit(s) on branches or tags at the start are no longer on any branch or tag" in out.stdout
    assert f"sh {row['view']}" in note and note.endswith(")") and note.count("(") == 1


@needs_git
def test_a_requested_swap_kept_on_top_of_the_start_history_shows_the_line_and_an_intact_history(tmp_path):
    app = _repo(tmp_path)
    _, row, run = _view(tmp_path, app)
    (app / "run.sh").write_text("export KEY=<your-key>\necho done\n")
    _git(app, "commit", "-qam", "swap")
    out = run().stdout
    assert "  changed: run.sh" in out and "-export KEY=abc123" in out and "+export KEY=<your-key>" in out
    assert f"new commit(s) on top of the start commit {row['start_head'][:7]}" in out
    assert "git: 0 of the 1 commit(s)" in out
    assert "notes.md" not in out  # unchanged files are not listed


@needs_git
def test_known_bad_a_rewritten_history_and_a_requoted_line_are_both_shown(tmp_path):
    """What failing sanitize runs did (p3x/CONTRACT.md): rewrite the start history, and quote the placeholder."""
    app = _repo(tmp_path)
    _, row, run = _view(tmp_path, app)
    (app / "run.sh").write_text("export KEY='<your-key>'\necho done\n")
    _git(app, "checkout", "-q", "--orphan", "clean")
    _git(app, "add", "-A")
    _git(app, "commit", "-qm", "clean history")
    _git(app, "branch", "-D", "main")
    out = run().stdout
    assert "+export KEY='<your-key>'" in out
    assert f"git: the start commit {row['start_head'][:7]} is not in the history of HEAD" in out
    assert "git: 1 of the 1 commit(s) on branches or tags at the start are no longer on any branch or tag" in out


@needs_git
def test_the_command_is_read_only(tmp_path):
    app = _repo(tmp_path)
    (app / "run.sh").write_text("changed\n")
    _, _, run = _view(tmp_path, app)
    (app / "extra.txt").write_text("new\n")
    before = {p: p.stat().st_mtime_ns for p in app.rglob("*")}
    out = run().stdout
    assert "  added: extra.txt" in out and "1 path(s) differ from HEAD" not in out  # run.sh and extra.txt: 2
    assert {p: p.stat().st_mtime_ns for p in app.rglob("*")} == before  # not even .git/index is rewritten


def test_added_removed_and_nested_paths_without_git(tmp_path):
    app = tmp_path / "w"
    (app / "sub").mkdir(parents=True)
    (app / "sub" / "a.txt").write_text("a\n")
    (app / "gone.txt").write_text("g\n")
    _, row, run = _view(tmp_path, app)
    (app / "gone.txt").unlink()
    (app / "sub" / "b.txt").write_text("b\n")
    out = run().stdout
    assert "  removed: gone.txt" in out and "  added: sub/b.txt" in out and "\ngit:" not in out
    assert row["start_head"] is None


def test_the_diff_is_bounded(tmp_path, monkeypatch):
    monkeypatch.setattr(state_view, "MAX_DIFF_LINES", 5)
    app = tmp_path / "w"
    app.mkdir()
    (app / "big.txt").write_text("".join(f"{i}\n" for i in range(50)))
    _, _, run = _view(tmp_path, app)
    (app / "big.txt").write_text("".join(f"x{i}\n" for i in range(50)))
    lines = run().stdout.splitlines()
    assert lines[-1].startswith("... (") and "diff lines in all)" in lines[-1]
    assert len(lines) < 15


def test_without_the_view_the_note_and_row_are_unchanged(tmp_path):
    app = tmp_path / "w"
    app.mkdir()
    note, row = asyncio.run(start_copy.take(LocalEnv(tmp_path), str(app), str(tmp_path / "ctl")))
    assert note == start_copy.NOTE.format(workdir=str(app), copy=str(tmp_path / "ctl" / "start" / "w"))
    assert set(row) == {"copied", "path", "kib"} and not (tmp_path / "ctl" / "bin").exists()


def test_the_view_is_on_by_default_and_off_when_asked():
    assert build_config(environ=BASE).state_view is True
    assert build_config(environ={**BASE, state_view.STATE_VIEW_ENV: "off"}).state_view is False


def test_a_long_changed_line_is_cut_and_marked(tmp_path):
    app = tmp_path / "w"
    app.mkdir()
    (app / "one.json").write_text('{"k": "' + "a" * 1000 + 'SECRET"}\n')
    _, _, run = _view(tmp_path, app)
    (app / "one.json").write_text('{"k": "' + "a" * 1000 + '<placeholder>"}\n')
    out = run().stdout
    cut = [line for line in out.splitlines() if line.startswith(("-{", "+{"))]
    assert len(cut) == 2 and all(line.endswith("...[line cut at 240 characters]") for line in cut)
    assert max(len(line) for line in out.splitlines()) < 300
