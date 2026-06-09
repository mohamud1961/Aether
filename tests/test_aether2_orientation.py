from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

from runner.aether2.orientation import (
    ENV_CONTRACT_VERSION,
    HOME_PROBE_COMMAND,
    NETWORK_PROBE_COMMANDS,
    NPM_GLOBAL_PREFIX_PROBE_COMMAND,
    OrientationSnapshot,
    PIP_USER_BASE_PROBE_COMMAND,
    SHELL_LC_PROBE_COMMAND,
    SYSTEM_TMP_PROBE_COMMAND,
    TMPDIR_PROBE_COMMAND,
    orient,
)


@dataclass
class FakeResult:
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0


class FakeExecutor:
    def __init__(
        self,
        mapping: dict[str, FakeResult | str],
        *,
        workspace_root: str = "/work",
        container_workspace_root: str = "/app",
        backend_kind: str = "docker",
    ) -> None:
        self.mapping = mapping
        self.calls: list[tuple[str, str | None]] = []
        self.workspace_root = Path(workspace_root)
        self.container_workspace_root = container_workspace_root
        self.execution_boundary = backend_kind
        self.backend = SimpleNamespace(kind=backend_kind, exec_shell="sh")

    def run(self, cmd: str, timeout_sec: int = 10, cwd: str | None = None) -> FakeResult | str:
        self.calls.append((cmd, cwd))
        result = self.mapping.get(cmd)
        if result is not None:
            return result
        return FakeResult(stderr="command not found", exit_code=1)

    def to_container_path(self, path: str | Path) -> str:
        candidate = Path(path)
        workspace_root = self.workspace_root.resolve(strict=False)
        resolved = candidate.resolve(strict=False)
        relative = resolved.relative_to(workspace_root).as_posix()
        if relative == ".":
            return self.container_workspace_root
        return f"{self.container_workspace_root}/{relative}"


def _build_reachable_executor() -> FakeExecutor:
    return FakeExecutor(
        {
            "pwd": FakeResult(stdout="/work/subdir"),
            "id -un": FakeResult(stdout="builder"),
            "id -u": FakeResult(stdout="1000"),
            "id -g": FakeResult(stdout="1000"),
            "id -gn": FakeResult(stdout="builders"),
            "git rev-parse --show-toplevel": FakeResult(stdout="/work"),
            HOME_PROBE_COMMAND: FakeResult(stdout="/home/builder"),
            TMPDIR_PROBE_COMMAND: FakeResult(stdout="/tmpdir"),
            SYSTEM_TMP_PROBE_COMMAND: FakeResult(stdout="/tmp"),
            'sh -lc \'[ -w "$PWD" ] && printf writable || printf read-only\'': FakeResult(stdout="writable"),
            'python3 -c "import os; print(\'\\n\'.join(sorted(os.listdir(\'.\'))[:40]))"': FakeResult(
                stdout="alpha.txt\nbeta.txt"
            ),
            "command -v git": FakeResult(stdout="/usr/bin/git"),
            "command -v curl": FakeResult(stdout="/usr/bin/curl"),
            "command -v sh": FakeResult(stdout="/bin/sh"),
            "command -v python3": FakeResult(stdout="/usr/bin/python3"),
            "command -v python": FakeResult(stdout="/usr/bin/python"),
            "command -v gcc": FakeResult(stdout="/usr/bin/gcc"),
            "command -v make": FakeResult(stdout="/usr/bin/make"),
            "command -v tmux": FakeResult(stdout="/usr/bin/tmux"),
            "command -v node": FakeResult(stdout="/usr/bin/node"),
            "command -v npm": FakeResult(stdout="/usr/bin/npm"),
            "command -v pip": FakeResult(stdout="/usr/bin/pip"),
            "pip --version": FakeResult(stdout="pip 24.0"),
            "python3 -m pip --version": FakeResult(stdout="pip 24.0"),
            "python3 --version": FakeResult(stdout="Python 3.14.2"),
            "python --version": FakeResult(stdout="Python 3.11.0"),
            PIP_USER_BASE_PROBE_COMMAND: FakeResult(stdout="/home/builder/.local"),
            SHELL_LC_PROBE_COMMAND: FakeResult(stdout="shell_ok"),
            "node --version": FakeResult(stdout="v22.0.0"),
            "npm --version": FakeResult(stdout="10.0.0"),
            NPM_GLOBAL_PREFIX_PROBE_COMMAND: FakeResult(stdout="/usr/local"),
            "ps -eo comm= | head -n 20": FakeResult(stdout="python\nbash\ntmux"),
            "ss -ltn 2>/dev/null || netstat -ltn 2>/dev/null || true": FakeResult(
                stdout="State Recv-Q Send-Q Local Address:Port Peer Address:Port"
            ),
            NETWORK_PROBE_COMMANDS[0][0]: FakeResult(stdout="reachable: pypi.org:443"),
        },
        backend_kind="docker",
    )


def _build_blocked_executor() -> FakeExecutor:
    return FakeExecutor(
        {
            "pwd": FakeResult(stdout="/work/subdir"),
            "id -un": FakeResult(stdout="builder"),
            "id -u": FakeResult(stdout="0"),
            "id -g": FakeResult(stdout="0"),
            "id -gn": FakeResult(stdout="root"),
            "git rev-parse --show-toplevel": FakeResult(stdout="/work"),
            HOME_PROBE_COMMAND: FakeResult(stdout="/root"),
            TMPDIR_PROBE_COMMAND: FakeResult(stdout=""),
            SYSTEM_TMP_PROBE_COMMAND: FakeResult(stdout="/tmp"),
            'sh -lc \'[ -w "$PWD" ] && printf writable || printf read-only\'': FakeResult(stdout="read-only"),
            "command -v git": FakeResult(stdout="/usr/bin/git"),
            "command -v curl": FakeResult(stdout="/usr/bin/curl"),
            "command -v sh": FakeResult(stdout="/bin/sh"),
            "command -v python3": FakeResult(stdout="/usr/bin/python3"),
            "command -v python": FakeResult(stdout="/usr/bin/python"),
            "command -v gcc": FakeResult(stdout="/usr/bin/gcc"),
            "command -v make": FakeResult(stdout="/usr/bin/make"),
            "command -v tmux": FakeResult(stdout="/usr/bin/tmux"),
            "command -v node": FakeResult(stdout="/usr/bin/node"),
            "command -v npm": FakeResult(stdout="/usr/bin/npm"),
            "command -v pip": FakeResult(stdout="/usr/bin/pip"),
            "pip --version": FakeResult(stdout="pip 24.0"),
            "python3 -m pip --version": FakeResult(stdout="pip 24.0"),
            "python3 --version": FakeResult(stdout="Python 3.14.2"),
            "python --version": FakeResult(stdout="Python 3.11.0"),
            PIP_USER_BASE_PROBE_COMMAND: FakeResult(stdout="/root/.local"),
            SHELL_LC_PROBE_COMMAND: FakeResult(stdout="shell_ok"),
            "node --version": FakeResult(stdout="v22.0.0"),
            "npm --version": FakeResult(stdout="10.0.0"),
            NPM_GLOBAL_PREFIX_PROBE_COMMAND: FakeResult(stdout="/usr/local"),
            "ps -eo comm= | head -n 20": FakeResult(stdout="python\nbash"),
            "ss -ltn 2>/dev/null || netstat -ltn 2>/dev/null || true": FakeResult(stdout=""),
            NETWORK_PROBE_COMMANDS[0][0]: FakeResult(stderr="blocked: timeout", exit_code=1),
        },
        backend_kind="local",
        container_workspace_root="/work",
    )


def test_orient_builds_structured_env_contract_with_probe_backed_facts() -> None:
    executor = _build_reachable_executor()

    snapshot = orient(executor)
    payload = snapshot.as_dict()

    assert isinstance(snapshot, OrientationSnapshot)
    assert snapshot.cwd == "/work/subdir"
    assert snapshot.workspace_root == "/work"
    assert snapshot.user == "builder"
    assert snapshot.is_root is False
    assert snapshot.network == "reachable"
    assert snapshot.network_reachable is True
    assert snapshot.network_evidence == "reachable: pypi.org:443"
    assert snapshot.safe_file_listing == ["alpha.txt", "beta.txt"]
    assert snapshot.writable_paths == ["/work/subdir", "/work", "/tmp", "/tmpdir", "/home/builder"]
    assert snapshot.env_contract_version == ENV_CONTRACT_VERSION
    assert snapshot.env_contract_digest == snapshot.env_contract["contract_digest"]
    assert len(snapshot.env_contract_digest) == 64
    assert payload["env_contract"]["contract_version"] == ENV_CONTRACT_VERSION
    assert payload["env_contract"]["workspace"]["host_workspace_root"]["value"] == "/work"
    assert payload["env_contract"]["workspace"]["task_workspace_root"]["value"] == "/app"
    assert payload["env_contract"]["workspace"]["canonical_task_cwd"]["value"] == "/app/subdir"
    assert payload["env_contract"]["paths"]["artifact_root"] == {
        "basis": [],
        "known": False,
        "note": "not surfaced by executor config or substrate probes",
        "value": None,
    }
    assert payload["env_contract"]["execution"]["shell_executable"]["value"] == "/bin/sh"
    assert payload["env_contract"]["execution"]["shell_dash_lc"]["value"] is True
    assert payload["env_contract"]["execution"]["command_form"]["value"] == ["sh", "-lc", "<command>"]
    assert payload["env_contract"]["paths"]["cwd_translation_rule"]["value"]["kind"] == "workspace_root_prefix_rewrite"
    assert payload["env_contract"]["python"]["preferred_executable"]["value"] == "python3"
    assert payload["env_contract"]["python"]["preferred_version"]["value"] == "Python 3.14.2"
    assert payload["env_contract"]["python"]["module_invocation_contract"]["value"] == ["python3", "-m", "pip"]
    assert payload["env_contract"]["package_managers"]["pip_user_base"]["value"] == "/home/builder/.local"
    assert payload["env_contract"]["package_managers"]["npm_global_prefix"]["value"] == "/usr/local"
    assert payload["env_contract"]["permissions"]["effective_group"]["value"] == "builders"
    assert payload["env_contract"]["permissions"]["writable_roots"]["value"] == [
        "/work/subdir",
        "/work",
        "/tmp",
        "/tmpdir",
        "/home/builder",
    ]
    assert payload["env_contract"]["network"]["outbound_https"]["value"] == {
        "evidence": "reachable: pypi.org:443",
        "reachable": True,
    }
    assert payload["env_contract"]["persistence"]["session_manager_available"]["value"] is True
    assert payload["env_contract"]["services"]["visible_tcp_listeners"]["value"] == []
    assert payload["env_contract"]["runtime"]["containerized"]["value"] is True
    assert payload["env_contract"]["grader_boundary"]["grader_only_test_paths"]["known"] is False
    assert "task" not in payload
    assert "difficulty" not in payload
    assert "category" not in payload
    assert "tags" not in payload


def test_orient_serializes_honest_unknowns_and_blocked_network_without_guessing() -> None:
    executor = _build_blocked_executor()

    snapshot = orient(executor)
    payload = snapshot.as_dict()

    assert snapshot.network == "blocked"
    assert snapshot.network_reachable is False
    assert snapshot.network_evidence == "blocked: timeout"
    assert snapshot.is_root is True
    assert snapshot.writable_paths == []
    assert payload["env_contract"]["workspace"]["task_workspace_root"]["value"] == "/work"
    assert payload["env_contract"]["paths"]["cwd_translation_rule"]["value"]["kind"] == "identity"
    assert payload["env_contract"]["network"]["constraints"]["known"] is False
    assert payload["env_contract"]["runtime"]["lifecycle_owner"]["known"] is False
    assert payload["env_contract"]["grader_boundary"]["model_visible_test_paths"]["known"] is False
    assert payload["env_contract"]["grader_boundary"]["hidden_environment_details"]["known"] is False
    assert payload["env_contract"]["services"]["listener_snapshot"]["value"] == []
    assert set(payload) == {
        "cwd",
        "user",
        "is_root",
        "workspace_root",
        "writable_paths",
        "safe_file_listing",
        "tool_presence",
        "package_managers",
        "network",
        "network_reachable",
        "network_evidence",
        "runtimes",
        "processes",
        "ports",
        "env_contract_version",
        "env_contract_digest",
        "env_contract",
    }


def test_orientation_module_has_generic_one_sentence_description() -> None:
    assert orient.__module__ == "harness.aether2.runtime.orientation"
    from runner.aether2 import orientation as orientation_module

    assert orientation_module.__doc__ is not None
    assert orientation_module.__doc__.strip() == (
        "Probe the local workspace and runtime into a compact, factual snapshot."
    )
