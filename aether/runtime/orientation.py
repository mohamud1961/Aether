"""Probe the local workspace and runtime into a compact, factual snapshot."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

ENV_CONTRACT_VERSION = "aether2_env_contract_v2"
SHELL_LC_PROBE_COMMAND = "sh -lc 'printf shell_ok'"
HOME_PROBE_COMMAND = "sh -lc 'printf %s \"$HOME\"'"
TMPDIR_PROBE_COMMAND = "sh -lc 'printf %s \"${TMPDIR:-}\"'"
SYSTEM_TMP_PROBE_COMMAND = "sh -lc 'if [ -d /tmp ]; then printf /tmp; fi'"
PIP_USER_BASE_PROBE_COMMAND = "python3 -m site --user-base"
NPM_GLOBAL_PREFIX_PROBE_COMMAND = "npm prefix -g"


@dataclass(frozen=True)
class OrientationSnapshot:
    cwd: str
    user: str
    is_root: bool
    workspace_root: str
    writable_paths: list[str]
    safe_file_listing: list[str]
    tool_presence: dict[str, str]
    package_managers: dict[str, str]
    network: str
    network_reachable: bool
    network_evidence: str
    runtimes: dict[str, str]
    processes: list[str]
    ports: list[str]
    env_contract_version: str
    env_contract_digest: str
    env_contract: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


NETWORK_PROBE_COMMANDS: tuple[tuple[str, str], ...] = (
    (
        "python3 -c \"import socket; s=socket.create_connection(('pypi.org', 443), 3); s.close(); print('reachable: pypi.org:443')\"",
        "python3 direct DNS+TCP probe",
    ),
    (
        "python -c \"import socket; s=socket.create_connection(('pypi.org', 443), 3); s.close(); print('reachable: pypi.org:443')\"",
        "python direct DNS+TCP probe",
    ),
    (
        "sh -lc 'curl -Is --max-time 3 https://pypi.org | head -n 1'",
        "curl HEAD probe",
    ),
)

_UNKNOWN_NOTE = "not surfaced by executor config or substrate probes"


def _read_text(result: Any) -> str:
    if result is None:
        return ""
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        for key in ("stdout", "output", "text", "content", "result"):
            value = result.get(key)
            if isinstance(value, str) and value.strip():
                return value
        stderr = result.get("stderr")
        if isinstance(stderr, str):
            return stderr
        return ""
    for attr in ("stdout", "output", "text", "content", "result"):
        value = getattr(result, attr, None)
        if isinstance(value, str) and value.strip():
            return value
    stderr = getattr(result, "stderr", None)
    if isinstance(stderr, str):
        return stderr
    return ""


def _exit_code(result: Any) -> int | None:
    if result is None:
        return None
    if isinstance(result, dict):
        for key in ("exit_code", "returncode", "code", "status"):
            value = result.get(key)
            if isinstance(value, int):
                return value
        return None
    for attr in ("exit_code", "returncode", "code", "status"):
        value = getattr(result, attr, None)
        if isinstance(value, int):
            return value
    return None


def _probe(executor: Any, command: str, *, cwd: str | None = None) -> tuple[str, bool]:
    raw = executor.run(command, timeout_sec=10, cwd=cwd)
    text = _read_text(raw).strip()
    code = _exit_code(raw)
    success = code == 0 if code is not None else bool(text)
    return text, success


def _probe_candidates(executor: Any, commands: list[str], *, cwd: str | None = None, missing_value: str = "") -> str:
    for command in commands:
        text, success = _probe(executor, command, cwd=cwd)
        if success:
            return text
    return missing_value


def _split_lines(text: str, *, limit: int = 40) -> list[str]:
    if not text:
        return []
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[:limit]


def _probe_presence(executor: Any, commands: list[str], *, cwd: str | None = None) -> str:
    return _probe_candidates(executor, commands, cwd=cwd, missing_value="missing")


def _probe_network(executor: Any) -> tuple[bool, str]:
    last_evidence = "blocked"
    for command, label in NETWORK_PROBE_COMMANDS:
        text, success = _probe(executor, command)
        if success:
            evidence = text or f"reachable via {label}"
            return True, evidence
        if text and last_evidence == "blocked":
            last_evidence = text
    return False, last_evidence or "blocked"


def _fact(value: Any, *basis: str, note: str | None = None) -> dict[str, Any]:
    return {
        "known": True,
        "value": value,
        "basis": [item for item in basis if item],
        "note": note,
    }


def _unknown(*basis: str, note: str = _UNKNOWN_NOTE) -> dict[str, Any]:
    return {
        "known": False,
        "value": None,
        "basis": [item for item in basis if item],
        "note": note,
    }


def _stable_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _stable_digest(payload: Any) -> str:
    return hashlib.sha256(_stable_json(payload).encode("utf-8")).hexdigest()


def _as_path_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, Path):
        return str(value)
    text = str(value).strip()
    return text


def _translate_path(executor: Any, path: str) -> str:
    if not path:
        return ""
    translate = getattr(executor, "to_container_path", None)
    if not callable(translate):
        return ""
    try:
        translated = translate(path)
    except Exception:
        return ""
    return _as_path_text(translated)


def _relative_to_root(path: str, root: str) -> str:
    if not path or not root:
        return ""
    try:
        return Path(path).resolve(strict=False).relative_to(Path(root).resolve(strict=False)).as_posix()
    except ValueError:
        return ""


def _append_unique(values: list[str], candidate: str) -> None:
    if candidate and candidate not in values:
        values.append(candidate)


def _probe_writable_paths(executor: Any, candidates: list[str]) -> list[str]:
    writable_paths: list[str] = []
    for path in candidates:
        writable_probe = _probe_candidates(
            executor,
            [
                'sh -lc \'[ -w "$PWD" ] && printf writable || printf read-only\'',
                'python3 -c "import os; print(\'writable\' if os.access(\'.\', os.W_OK) else \'read-only\')"',
            ],
            cwd=path,
        )
        if writable_probe == "writable":
            _append_unique(writable_paths, path)
    return writable_paths


def _parse_listener_addresses(lines: list[str]) -> list[str]:
    listeners: list[str] = []
    for line in lines:
        lowered = line.lower()
        if "local address:port" in lowered or lowered.startswith("active internet"):
            continue
        parts = line.split()
        for index in (3, 4, -1):
            if -len(parts) <= index < len(parts):
                candidate = parts[index]
                if ":" in candidate:
                    _append_unique(listeners, candidate)
                    break
    return listeners


def _backend_kind(executor: Any) -> str:
    value = getattr(executor, "execution_boundary", None)
    if isinstance(value, str) and value.strip():
        return value.strip()
    backend = getattr(executor, "backend", None)
    kind = getattr(backend, "kind", None)
    if isinstance(kind, str) and kind.strip():
        return kind.strip()
    return "unknown"


def orient(executor: Any) -> OrientationSnapshot:
    cwd = _probe_candidates(executor, ["pwd"]) or ""
    user = _probe_candidates(executor, ["id -un", "whoami"]) or "unavailable"
    uid = _probe_candidates(executor, ["id -u"])
    gid = _probe_candidates(executor, ["id -g"])
    group = _probe_candidates(executor, ["id -gn"]) or "unavailable"
    is_root = uid == "0"

    probed_workspace_root = _probe_candidates(
        executor,
        ["git rev-parse --show-toplevel", "pwd"],
        cwd=cwd or None,
    ) or cwd
    configured_host_workspace_root = _as_path_text(getattr(executor, "workspace_root", None))
    workspace_root = configured_host_workspace_root or probed_workspace_root

    configured_task_workspace_root = _as_path_text(getattr(executor, "container_workspace_root", None))
    translated_workspace_root = _translate_path(executor, workspace_root)
    translated_cwd = _translate_path(executor, cwd)
    task_workspace_root = translated_workspace_root or configured_task_workspace_root or workspace_root
    task_cwd = translated_cwd or cwd

    home_path = _probe_candidates(executor, [HOME_PROBE_COMMAND])
    tmpdir_path = _probe_candidates(executor, [TMPDIR_PROBE_COMMAND])
    system_tmp_path = _probe_candidates(executor, [SYSTEM_TMP_PROBE_COMMAND])
    writable_candidates: list[str] = []
    for candidate in [cwd, workspace_root, system_tmp_path, tmpdir_path, home_path]:
        _append_unique(writable_candidates, candidate)
    writable_paths = _probe_writable_paths(executor, writable_candidates)

    safe_file_listing = _split_lines(
        _probe_candidates(
            executor,
            [
                'python3 -c "import os; print(\'\\n\'.join(sorted(os.listdir(\'.\'))[:40]))"',
                "ls -1A",
            ],
            cwd=workspace_root or cwd or None,
        )
    )

    tool_presence = {
        "git": _probe_presence(executor, ["command -v git", "git --version"]),
        "curl": _probe_presence(executor, ["command -v curl", "curl --version"]),
        "sh": _probe_presence(executor, ["command -v sh"]),
        "python3": _probe_presence(executor, ["command -v python3", "python3 --version"]),
        "python": _probe_presence(executor, ["command -v python", "python --version"]),
        "gcc": _probe_presence(executor, ["command -v gcc", "gcc --version"]),
        "make": _probe_presence(executor, ["command -v make", "make --version"]),
        "tmux": _probe_presence(executor, ["command -v tmux", "tmux -V"]),
        "node": _probe_presence(executor, ["command -v node", "node --version"]),
        "npm": _probe_presence(executor, ["command -v npm", "npm --version"]),
        "uv": _probe_presence(executor, ["command -v uv", "uv --version"]),
        "pip": _probe_presence(executor, ["command -v pip", "pip --version", "python3 -m pip --version"]),
    }

    package_managers = {
        "apt": _probe_presence(executor, ["command -v apt", "apt --version"]),
        "pip": _probe_presence(executor, ["command -v pip", "pip --version", "python3 -m pip --version"]),
        "npm": _probe_presence(executor, ["command -v npm", "npm --version"]),
        "uv": _probe_presence(executor, ["command -v uv", "uv --version"]),
    }

    network_reachable, network_evidence = _probe_network(executor)
    network = "reachable" if network_reachable else "blocked"

    runtimes = {
        "python3": _probe_presence(executor, ["python3 --version", "python3 -V"]),
        "python": _probe_presence(executor, ["python --version", "python -V"]),
        "node": _probe_presence(executor, ["node --version", "node -v"]),
        "npm": _probe_presence(executor, ["npm --version", "npm -v"]),
    }

    processes = _split_lines(
        _probe_candidates(
            executor,
            [
                "ps -eo comm= | head -n 20",
                "ps -A -o comm= | head -n 20",
            ],
        )
    )

    ports = _split_lines(
        _probe_candidates(
            executor,
            [
                "ss -ltn 2>/dev/null || netstat -ltn 2>/dev/null || true",
                "netstat -ltn 2>/dev/null || true",
            ],
        )
    )
    visible_tcp_listeners = _parse_listener_addresses(ports)

    shell_lc_text, shell_lc_ok = _probe(executor, SHELL_LC_PROBE_COMMAND)
    shell_supports_lc = shell_lc_ok and shell_lc_text == "shell_ok"
    preferred_python_name = "python3" if tool_presence["python3"] != "missing" else ("python" if tool_presence["python"] != "missing" else "")
    preferred_python_path = tool_presence.get(preferred_python_name, "missing") if preferred_python_name else "missing"
    preferred_python_version = runtimes.get(preferred_python_name, "missing") if preferred_python_name else "missing"
    pip_user_base = _probe_candidates(executor, [PIP_USER_BASE_PROBE_COMMAND])
    npm_global_prefix = _probe_candidates(executor, [NPM_GLOBAL_PREFIX_PROBE_COMMAND])
    backend_kind = _backend_kind(executor)
    relative_cwd = _relative_to_root(cwd, workspace_root)
    translation_rule_kind = "identity" if workspace_root == task_workspace_root else "workspace_root_prefix_rewrite"

    env_contract_body: dict[str, Any] = {
        "contract_version": ENV_CONTRACT_VERSION,
        "workspace": {
            "host_workspace_root": _fact(
                workspace_root,
                "config:executor.workspace_root" if configured_host_workspace_root else "",
                "probe:git rev-parse --show-toplevel",
            ),
            "task_workspace_root": _fact(
                task_workspace_root,
                "config:executor.container_workspace_root" if configured_task_workspace_root else "",
                "config:executor.to_container_path" if translated_workspace_root else "",
            ),
            "canonical_host_cwd": _fact(cwd, "probe:pwd"),
            "canonical_task_cwd": _fact(
                task_cwd,
                "probe:pwd",
                "config:executor.to_container_path" if translated_cwd else "",
            ),
            "cwd_relative_to_host_workspace": _fact(
                relative_cwd or ".",
                "probe:pwd",
                "config:executor.workspace_root" if configured_host_workspace_root else "probe:git rev-parse --show-toplevel",
            ),
            "workspace_listing_sample": _fact(
                safe_file_listing,
                "probe:python3 -c os.listdir(.)",
            ),
        },
        "paths": {
            "task_root": _fact(task_workspace_root, "config:executor.to_container_path" if translated_workspace_root else "config:executor.container_workspace_root"),
            "artifact_root": _unknown(),
            "model_visible_test_paths": _unknown(),
            "grader_only_test_paths": _unknown(),
            "cwd_translation_rule": _fact(
                {
                    "kind": translation_rule_kind,
                    "host_prefix": workspace_root,
                    "task_prefix": task_workspace_root,
                    "host_cwd": cwd,
                    "task_cwd": task_cwd,
                },
                "config:executor.to_container_path" if translated_workspace_root or translated_cwd else "config:executor.workspace_root",
            ),
        },
        "execution": {
            "shell_executable": _fact(tool_presence["sh"], "probe:command -v sh"),
            "shell_dash_lc": _fact(shell_supports_lc, f"probe:{SHELL_LC_PROBE_COMMAND}"),
            "command_form": _fact(["sh", "-lc", "<command>"], f"probe:{SHELL_LC_PROBE_COMMAND}"),
            "execution_boundary": _fact(backend_kind, "config:executor.execution_boundary"),
        },
        "python": {
            "preferred_executable": _fact(
                preferred_python_name or None,
                "probe:command -v python3" if preferred_python_name == "python3" else "probe:command -v python",
                note=None if preferred_python_name else _UNKNOWN_NOTE,
            )
            if preferred_python_name
            else _unknown("probe:command -v python3", "probe:command -v python"),
            "preferred_path": _fact(
                preferred_python_path,
                "probe:command -v python3" if preferred_python_name == "python3" else "probe:command -v python",
            )
            if preferred_python_name
            else _unknown("probe:command -v python3", "probe:command -v python"),
            "preferred_version": _fact(
                preferred_python_version,
                "probe:python3 --version" if preferred_python_name == "python3" else "probe:python --version",
            )
            if preferred_python_name
            else _unknown("probe:python3 --version", "probe:python --version"),
            "module_invocation_contract": _fact(
                [preferred_python_name, "-m", "pip"],
                "probe:python3 -m pip --version" if preferred_python_name == "python3" else "probe:python -m pip --version",
            )
            if preferred_python_name and package_managers["pip"] != "missing"
            else _unknown("probe:python3 -m pip --version", "probe:python -m pip --version"),
        },
        "package_managers": {
            "apt": _fact(package_managers["apt"], "probe:command -v apt"),
            "pip": _fact(package_managers["pip"], "probe:command -v pip"),
            "npm": _fact(package_managers["npm"], "probe:command -v npm"),
            "uv": _fact(package_managers["uv"], "probe:command -v uv"),
            "pip_user_base": _fact(pip_user_base, f"probe:{PIP_USER_BASE_PROBE_COMMAND}") if pip_user_base else _unknown(f"probe:{PIP_USER_BASE_PROBE_COMMAND}"),
            "npm_global_prefix": _fact(npm_global_prefix, f"probe:{NPM_GLOBAL_PREFIX_PROBE_COMMAND}") if npm_global_prefix else _unknown(f"probe:{NPM_GLOBAL_PREFIX_PROBE_COMMAND}"),
            "workspace_install_scope": _unknown(),
        },
        "permissions": {
            "effective_user": _fact(user, "probe:id -un"),
            "effective_uid": _fact(uid, "probe:id -u") if uid else _unknown("probe:id -u"),
            "effective_group": _fact(group, "probe:id -gn") if group else _unknown("probe:id -gn"),
            "effective_gid": _fact(gid, "probe:id -g") if gid else _unknown("probe:id -g"),
            "is_root": _fact(is_root, "probe:id -u"),
            "writable_roots": _fact(
                writable_paths,
                "probe:writability checks",
            ),
        },
        "network": {
            "outbound_https": _fact(
                {"reachable": network_reachable, "evidence": network_evidence},
                "probe:python socket create_connection",
                "probe:curl HEAD https://pypi.org",
            ),
            "constraints": _unknown(),
        },
        "persistence": {
            "process_sample": _fact(processes, "probe:ps -eo comm= | head -n 20"),
            "session_manager": _fact(tool_presence["tmux"], "probe:command -v tmux"),
            "session_manager_available": _fact(tool_presence["tmux"] != "missing", "probe:command -v tmux"),
            "job_persistence_model": _unknown(),
        },
        "services": {
            "listener_snapshot": _fact(ports, "probe:ss -ltn || netstat -ltn"),
            "visible_tcp_listeners": _fact(visible_tcp_listeners, "probe:ss -ltn || netstat -ltn"),
        },
        "runtime": {
            "execution_boundary": _fact(backend_kind, "config:executor.execution_boundary"),
            "task_runtime_root": _fact(task_workspace_root, "config:executor.to_container_path" if translated_workspace_root else "config:executor.container_workspace_root"),
            "containerized": _fact(backend_kind == "docker", "config:executor.execution_boundary"),
            "lifecycle_owner": _unknown(),
        },
        "grader_boundary": {
            "model_visible_test_paths": _unknown(),
            "grader_only_test_paths": _unknown(),
            "hidden_environment_details": _unknown(),
        },
        "model_start_contract": {
            "canonical_task_cwd": _fact(
                task_cwd,
                "probe:pwd",
                "config:executor.to_container_path" if translated_cwd else "",
            ),
            "task_workspace_root": _fact(
                task_workspace_root,
                "config:executor.to_container_path" if translated_workspace_root else "config:executor.container_workspace_root",
            ),
            "known_writable_roots": _fact(writable_paths, "probe:writability checks"),
            "visible_test_paths": _unknown(),
            "hidden_tests_available_to_model": _fact(False, "harness policy"),
        },
        "artifact_expectations": {
            "artifact_root": _unknown(),
            "workspace_must_sync_back": _unknown(),
            "empty_artifact_is_not_success": _fact(True, "harness policy"),
        },
        "service_expectations": {
            "listener_snapshot": _fact(visible_tcp_listeners, "probe:ss -ltn || netstat -ltn"),
            "fresh_client_probe_required_when_task_requests_service": _fact(True, "harness policy"),
            "open_port_only_is_weak_evidence": _fact(True, "harness policy"),
            "long_running_jobs_need_survival_check": _fact(True, "harness policy"),
        },
        "finalization_expectations": {
            "task_done_requires_successful_replayed_check_or_runtime_evidence": _fact(True, "harness policy"),
            "self_authored_readback_is_weak_evidence": _fact(True, "harness policy"),
            "official_grader_is_final_authority": _fact(True, "harness policy"),
        },
    }
    env_contract_digest = _stable_digest(env_contract_body)
    env_contract = dict(env_contract_body)
    env_contract["contract_digest"] = env_contract_digest

    return OrientationSnapshot(
        cwd=cwd,
        user=user,
        is_root=is_root,
        workspace_root=workspace_root,
        writable_paths=writable_paths,
        safe_file_listing=safe_file_listing,
        tool_presence=tool_presence,
        package_managers=package_managers,
        network=network,
        network_reachable=network_reachable,
        network_evidence=network_evidence,
        runtimes=runtimes,
        processes=processes,
        ports=ports,
        env_contract_version=ENV_CONTRACT_VERSION,
        env_contract_digest=env_contract_digest,
        env_contract=env_contract,
    )
