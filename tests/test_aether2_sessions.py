import os
from pathlib import Path

import pytest

from runner.aether2 import sessions as sessions_module
from runner.aether2.sessions import SessionRegistry


def test_session_registry_roundtrip_and_recreation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, retrying_subprocess
) -> None:
    retrying_subprocess(sessions_module)
    tmux_path = _write_fake_tmux(tmp_path)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")

    registry = SessionRegistry(tmp_path / ".aether2" / "state")
    registry.start("shell", "bash")
    registry.send("shell", "echo hello")
    first = registry.read("shell")
    second = SessionRegistry(tmp_path / ".aether2" / "state").read("shell")

    assert "echo hello" in first
    assert first == second
    log = (tmp_path / "fake_tmux_log.txt").read_text(encoding="utf-8")
    assert "new-session|-d|-s|shell|bash" in log
    assert "send-keys|-t|shell|echo hello" in log
    assert "capture-pane|-p|-t|shell" in log
    assert tmux_path.exists()


def test_session_registry_requires_tmux(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", str(tmp_path))
    registry = SessionRegistry(tmp_path / ".aether2" / "state")
    with pytest.raises(RuntimeError, match="tmux is unavailable"):
        registry.start("shell", "bash")


def test_session_registry_routes_through_docker_backend_not_host_tmux(tmp_path: Path, monkeypatch) -> None:
    """C1: when backend.kind == 'docker', tmux commands are routed through
    docker exec into the container, not the host tmux binary."""
    from runner.aether2.executor import ContainerBackend
    import subprocess as subprocess_module

    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(list(cmd))
        assert cmd[:3] == ["docker", "exec", "fake-container-id"]
        assert cmd[3] == "tmux"
        return subprocess_module.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(sessions_module.subprocess, "run", fake_run)

    backend = ContainerBackend(kind="docker", container_id="fake-container-id", container_workspace_root="/app")
    registry = SessionRegistry(tmp_path / ".aether2" / "state", backend=backend)
    registry.start("shell", "bash")
    registry.send("shell", "echo hi")
    registry.read("shell")

    assert len(calls) == 3
    for call in calls:
        assert call[:4] == ["docker", "exec", "fake-container-id", "tmux"]


def test_session_registry_docker_backend_truthful_error_when_tmux_absent(tmp_path: Path, monkeypatch) -> None:
    """C1: if tmux is absent inside the container, the docker-backed registry
    raises the same truthful 'tmux is unavailable' error as the local case."""
    from runner.aether2.executor import ContainerBackend
    import subprocess as subprocess_module

    def fake_run(cmd, **kwargs):
        raise subprocess_module.CalledProcessError(
            127, cmd, output="", stderr='OCI runtime exec failed: exec failed: unable to start container process: exec: "tmux": executable file not found in $PATH'
        )

    monkeypatch.setattr(sessions_module.subprocess, "run", fake_run)

    backend = ContainerBackend(kind="docker", container_id="fake-container-id", container_workspace_root="/app")
    registry = SessionRegistry(tmp_path / ".aether2" / "state", backend=backend)
    with pytest.raises(RuntimeError, match="tmux is unavailable"):
        registry.start("shell", "bash")


def test_session_start_collision_raises_clear_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, retrying_subprocess
) -> None:
    retrying_subprocess(sessions_module)
    _write_fake_tmux(tmp_path)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")

    registry = SessionRegistry(tmp_path / ".aether2" / "state")
    registry.start("shell", "bash")

    with pytest.raises(ValueError, match="already exists"):
        registry.start("shell", "bash")


def test_unknown_session_raises_clear_keyerror_on_send_and_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, retrying_subprocess
) -> None:
    retrying_subprocess(sessions_module)
    _write_fake_tmux(tmp_path)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")

    registry = SessionRegistry(tmp_path / ".aether2" / "state")

    with pytest.raises(KeyError, match="unknown session"):
        registry.send("ghost", "echo hi")

    with pytest.raises(KeyError, match="unknown session"):
        registry.read("ghost")

    with pytest.raises(KeyError, match="unknown session"):
        registry.stop("ghost")


def test_session_send_supports_control_key_roundtrip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, retrying_subprocess
) -> None:
    retrying_subprocess(sessions_module)
    _write_fake_tmux(tmp_path)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")

    registry = SessionRegistry(tmp_path / ".aether2" / "state")
    registry.start("shell", "bash")

    registry.send("shell", "echo hi")
    registry.send("shell", "Enter")
    registry.send("shell", "C-c")

    log = (tmp_path / "fake_tmux_log.txt").read_text(encoding="utf-8")
    assert "send-keys|-t|shell|echo hi" in log
    assert "send-keys|-t|shell|Enter" in log
    assert "send-keys|-t|shell|C-c" in log

    screen = registry.read("shell")
    assert "echo hi" in screen
    assert "Enter" in screen
    assert "C-c" in screen


def test_read_after_session_killed_outside_registry_is_truthful(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, retrying_subprocess
) -> None:
    retrying_subprocess(sessions_module)
    _write_fake_tmux(tmp_path)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")

    registry = SessionRegistry(tmp_path / ".aether2" / "state")
    registry.start("shell", "bash")

    # Simulate the underlying tmux session disappearing (e.g. inner process exited
    # and tmux exited with it) without going through registry.stop().
    state_path = tmp_path / "fake_tmux_state" / "shell.json"
    state_path.unlink()

    # read() must not crash; it should report a clean empty/blank result.
    screen = registry.read("shell")
    assert screen == ""


def test_stop_kills_session_and_removes_registry_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, retrying_subprocess
) -> None:
    retrying_subprocess(sessions_module)
    _write_fake_tmux(tmp_path)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")

    registry = SessionRegistry(tmp_path / ".aether2" / "state")
    registry.start("shell", "bash")
    assert registry.list_session_ids() == ["shell"]

    registry.stop("shell")

    assert registry.list_session_ids() == []
    log = (tmp_path / "fake_tmux_log.txt").read_text(encoding="utf-8")
    assert "kill-session|-t|shell" in log

    # Session is fully gone now: further operations raise unknown-session errors.
    with pytest.raises(KeyError, match="unknown session"):
        registry.read("shell")

    # And the underlying tmux session itself was killed (not just the registry record).
    assert not (tmp_path / "fake_tmux_state" / "shell.json").exists()


def _write_fake_tmux(root: Path) -> Path:
    script = root / "tmux"
    script.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "import json, sys",
                "from pathlib import Path",
                f"root = Path({str(root)!r})",
                "state = root / 'fake_tmux_state'",
                "state.mkdir(exist_ok=True)",
                "log_path = root / 'fake_tmux_log.txt'",
                "args = sys.argv[1:]",
                "log_path.write_text(log_path.read_text(encoding='utf-8') + '|'.join(args) + '\\n', encoding='utf-8') if log_path.exists() else log_path.write_text('|'.join(args) + '\\n', encoding='utf-8')",
                "cmd = args[0]",
                "if cmd == 'new-session':",
                "    session_id = args[3]",
                "    command = args[4]",
                "    (state / f'{session_id}.json').write_text(json.dumps({'command': command, 'pane': ''}), encoding='utf-8')",
                "    sys.exit(0)",
                "if cmd == 'send-keys':",
                "    session_id = args[2]",
                "    keys = args[3]",
                "    path = state / f'{session_id}.json'",
                "    payload = json.loads(path.read_text(encoding='utf-8'))",
                "    payload['pane'] += keys + '\\n'",
                "    path.write_text(json.dumps(payload), encoding='utf-8')",
                "    sys.exit(0)",
                "if cmd == 'capture-pane':",
                "    session_id = args[3]",
                "    path = state / f'{session_id}.json'",
                "    if not path.exists():",
                "        sys.stderr.write(f\"can't find session: {session_id}\\n\")",
                "        sys.exit(1)",
                "    payload = json.loads(path.read_text(encoding='utf-8'))",
                "    sys.stdout.write(payload['pane'])",
                "    sys.exit(0)",
                "if cmd == 'kill-session':",
                "    session_id = args[2]",
                "    path = state / f'{session_id}.json'",
                "    if not path.exists():",
                "        sys.stderr.write(f\"can't find session: {session_id}\\n\")",
                "        sys.exit(1)",
                "    path.unlink()",
                "    sys.exit(0)",
                "sys.exit(1)",
                "",
            ]
        ),
        encoding="utf-8",
    )
    script.chmod(0o755)
    return script
