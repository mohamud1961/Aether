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


def test_test_container_sets_shell_entrypoint_and_keeps_network_disabled(tmp_path, monkeypatch):
    _prepare(tmp_path, monkeypatch)
    calls = []

    def fake_run(argv, **_kwargs):
        calls.append(argv)
        if argv[:2] == ["colima", "list"]:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        output, rc = "", 0
        if argv[:3] == ["docker", "image", "inspect"]:
            output = "linux/arm64 sha256:synthetic\n"
        elif argv[:3] == ["docker", "exec", gate.BUILDER] and argv[-2:] == ["uname", "-srm"]:
            output = "Linux 6.0 aarch64\n"
        elif argv[:2] == ["docker", "create"]:
            assert argv[argv.index("--entrypoint") + 1] == "sh"
            assert argv[argv.index("--network") + 1] == "none"
            assert argv[argv.index(gate.BUILT_IMAGE) + 1] == "-c"
        elif argv[:2] == ["docker", "inspect"]:
            output = "none 0\n"
        elif argv[:2] == ["docker", "start"]:
            rc = 2
        return SimpleNamespace(returncode=rc, stdout=output, stderr="")

    monkeypatch.setattr(gate.subprocess, "run", fake_run)
    assert gate.main() == 1
    assert any(argv[:2] == ["docker", "create"] for argv in calls)
    assert any(argv[:2] == ["colima", "delete"] for argv in calls)
