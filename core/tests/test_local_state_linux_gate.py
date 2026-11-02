"""The temporary Linux gate must never delete a pre-existing profile."""

import json
from types import SimpleNamespace

from qa import local_state_linux_gate as gate


def _prepare(tmp_path, monkeypatch):
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.setattr(gate, "WORK", work)
    monkeypatch.setattr(gate, "OUT", tmp_path / "evidence")
    monkeypatch.setattr(gate, "digest", lambda path: gate.ARCHIVE_SHA if path.name == "source.tar.gz" else gate.REQ_SHA)
    monkeypatch.setattr(gate.signal, "signal", lambda *_args: None)


def test_gate_refuses_existing_profile_without_stopping_or_deleting_it(tmp_path, monkeypatch):
    _prepare(tmp_path, monkeypatch)
    calls = []

    def fake_run(argv, **_kwargs):
        calls.append(argv)
        return SimpleNamespace(returncode=0, stdout=json.dumps({"name": gate.PROFILE}) + "\n", stderr="")

    monkeypatch.setattr(gate.subprocess, "run", fake_run)
    assert gate.main() == 1
    assert calls == [["colima", "list", "--json"]]
    report = json.loads((gate.OUT / "host-summary.json").read_text())
    assert report["outcome"] == "incomplete_or_failed"


def test_failed_owned_start_attempt_cleans_only_its_named_profile(tmp_path, monkeypatch):
    _prepare(tmp_path, monkeypatch)
    calls = []

    def fake_run(argv, **_kwargs):
        calls.append(argv)
        if argv[:2] == ["colima", "list"]:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if argv[:2] == ["colima", "start"]:
            return SimpleNamespace(returncode=1, stdout="synthetic start failure", stderr="")
        assert argv[:2] in (["colima", "stop"], ["colima", "delete"])
        assert argv[argv.index("--profile") + 1] == gate.PROFILE
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(gate.subprocess, "run", fake_run)
    assert gate.main() == 1
    assert [argv[1] for argv in calls] == ["list", "start", "stop", "delete", "list"]
