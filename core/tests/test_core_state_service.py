"""The v2 state service: a verified file/git account after every action, and an environment block kept current."""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess

import pytest

from aether.core import start_copy, state_service
from aether.core.harbor_agent import build_config
from tests.core_fakes import LocalEnv

BASE = {"AETHER_CORE_REVIEW": "off", "AETHER_CORE_CONTEXT": "clm", "AETHER_CORE_REPL": "off", "AETHER_CORE_IMAGES": "off"}
needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")


def _git(repo, *args):
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
           "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin", "HOME": str(repo)}
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, env=env)


def _service(tmp_path, app):
    env, ctl = LocalEnv(tmp_path), str(tmp_path / "ctl")
    asyncio.run(start_copy.take(env, str(app), ctl))
    rows = []
    svc = state_service.StateService(env, str(app), lambda: 300.0, lambda event, **row: rows.append(row), control_dir=ctl)
    block = asyncio.run(svc.start())
    step = iter(range(1, 1000))
    return svc, block, rows, lambda tool="terminal", **args: asyncio.run(svc.after_action(next(step), tool, args, ""))


def _app(tmp_path, git=False):
    app = tmp_path / "my app"
    (app / "sub").mkdir(parents=True)
    (app / "data.txt").write_text("abc\n")
    (app / "sub" / "keep.txt").write_text("k\n")
    if git:
        _git(app, "init", "-q", "-b", "main")
        _git(app, "add", "-A")
        _git(app, "commit", "-q", "-m", "start")
    return app


def test_an_untouched_workspace_shows_zero_and_the_block_is_pinned_text(tmp_path):
    svc, block, _, act = _service(tmp_path, _app(tmp_path))
    assert block.startswith(state_service.PREFIX) and "listening TCP ports" in block
    assert act() == "[state] files vs start: 0 added, 0 removed, 0 changed"
    assert svc.context_summary() == block and not svc.context_changed


def test_side_effects_are_counted_added_removed_changed(tmp_path):
    app = _app(tmp_path)
    _, _, _, act = _service(tmp_path, app)
    (app / "out.txt").write_text("new\n")
    (app / "sub" / "keep.txt").unlink()
    (app / "data.txt").write_text("xyz\n")
    assert act() == "[state] files vs start: 1 added, 1 removed, 1 changed"


def test_known_bad_a_same_size_edit_with_restored_mtime_is_still_seen(tmp_path):
    """mtime-only scanners miss this (touch -r, cp -p); ctime cannot be set back."""
    app = _app(tmp_path)
    _, _, _, act = _service(tmp_path, app)
    assert act().endswith("0 changed")
    st = os.stat(app / "data.txt")
    (app / "data.txt").write_text("abd\n")  # same size
    os.utime(app / "data.txt", ns=(st.st_atime_ns, st.st_mtime_ns))  # mtime restored
    assert act().endswith("1 changed")


def test_a_change_reverted_counts_as_unchanged(tmp_path):
    app = _app(tmp_path)
    _, _, _, act = _service(tmp_path, app)
    (app / "data.txt").write_text("other content\n")
    assert act().endswith("1 changed")
    (app / "data.txt").write_text("abc\n")
    assert act().endswith("0 changed")


def test_known_bad_a_known_change_survives_a_step_with_no_candidates(tmp_path):
    """A read-only action after an edit: no file is a candidate, and the edit must still be counted."""
    app = _app(tmp_path)
    _, _, _, act = _service(tmp_path, app)
    (app / "data.txt").write_text("xyz\n")
    assert act().endswith("1 changed")
    (tmp_path / "ctl" / "state2" / "t_prev").write_text("9999999999\n")  # nothing is racy on the next scan
    assert act().endswith("1 changed")


def test_known_bad_an_emptied_workspace_counts_every_start_file_removed(tmp_path):
    app = _app(tmp_path)
    _, _, _, act = _service(tmp_path, app)
    shutil.rmtree(app / "sub"); (app / "data.txt").unlink()
    assert act() == "[state] files vs start: 0 added, 2 removed, 0 changed"


@needs_git
def test_known_bad_a_rewritten_history_is_shown_and_new_commits_are_not(tmp_path):
    app = _app(tmp_path, git=True)
    _, _, _, act = _service(tmp_path, app)
    assert act().endswith("· git: HEAD is the start commit")
    (app / "data.txt").write_text("swap\n")
    _git(app, "commit", "-qam", "swap")
    assert act().endswith("· git: 1 new commit(s) on the start commit")
    _git(app, "checkout", "-q", "--orphan", "clean")
    _git(app, "commit", "-qm", "clean")
    assert act().endswith("· git: the start commit is not in HEAD's history")


def test_known_bad_the_full_check_catches_an_incremental_miss_and_corrects_it(tmp_path):
    app = _app(tmp_path)
    svc, _, rows, act = _service(tmp_path, app)
    act()
    (app / "data.txt").write_text("zzz\n")
    state = tmp_path / "ctl" / "state2"
    # simulate a scanner miss: make the previous scan agree with the edited file and move the racy window away
    scan = subprocess.run(["sh", "-c", f"cd '{app}' && find . ! -type d -exec stat -f '%N|%z|%m|%c|%i' {{}} + "
                           "2>/dev/null || find . ! -type d -exec stat -c '%n|%s|%Y|%Z|%i' {} +"],
                          capture_output=True, text=True).stdout
    (state / "prev.tsv").write_text("".join(sorted(line[2:] + "\n" for line in scan.splitlines())))
    (state / "t_prev").write_text("9999999999\n")
    # the next step is a full check: its incremental pass misses the edit, the byte comparison does not
    line = asyncio.run(svc.after_action(state_service.VERIFY_EVERY, "terminal", {}, ""))
    assert line.endswith("1 changed") and svc.misses and "data.txt" in svc.misses[0]["paths"]
    assert svc.safe_record()["misses"] == svc.misses


def test_finish_runs_a_full_check_and_shows_nothing(tmp_path):
    svc, _, rows, _ = _service(tmp_path, _app(tmp_path))
    assert asyncio.run(svc.after_action(1, "finish", {}, "")) == ""
    assert rows[-1]["mode"] == "verify"


def test_without_a_start_copy_the_line_says_so(tmp_path):
    app = _app(tmp_path)
    svc = state_service.StateService(LocalEnv(tmp_path), str(app), lambda: 300.0, lambda *a, **k: None,
                                     control_dir=str(tmp_path / "ctl"))
    asyncio.run(svc.start())
    assert asyncio.run(svc.after_action(1, "terminal", {}, "")) == "[state] files: no start copy to compare with"


def test_env_change_names_gained_and_lost_tools_and_ignores_equal_blocks():
    old = "os: Debian\navailable: python3 git\nnot found on PATH: tesseract\npython packages (2): a b\n"
    new = "os: Debian\navailable: python3 git tesseract\nnot found on PATH:\npython packages (3): a b c\n"
    assert state_service.env_change(old, old) == ""
    text = state_service.env_change(old, new)
    assert "now on PATH: tesseract" in text and "python packages" in text


def test_an_install_command_measures_the_environment_again(tmp_path, monkeypatch):
    svc, block, _, _ = _service(tmp_path, _app(tmp_path))
    current = svc.env_text
    gained = "\n".join(line + " tesseract9" if line.startswith("available:") else line
                       for line in current.splitlines())

    async def fake_env():
        return gained
    monkeypatch.setattr(svc, "_env", fake_env)
    line = asyncio.run(svc.after_action(1, "terminal", {"input": "apt-get install -y tesseract-ocr"}, ""))
    assert line.endswith(" · env changed (now on PATH: tesseract9)") and svc.context_changed
    assert "tesseract9" in svc.context_summary() and svc.context_summary() != block


def test_the_mode_is_selected_by_the_managed_facts_flag():
    assert build_config(environ=BASE).facts_v2 is False
    cfg = build_config(environ={**BASE, "AETHER_CORE_MANAGED_FACTS": "v2"})
    assert cfg.facts_v2 and cfg.managed_facts and not cfg.facts_pull
