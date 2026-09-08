"""Strict one-task Aether launch/admission boundary.

The launcher freezes package/task/runtime custody, creates one evidence namespace,
and delegates benchmark lifecycle and official grading to Harbor.  It never
chooses task strategy, runs a grader itself, schedules boards, invokes a shell,
or retries a task/provider call.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from hashlib import sha256
import importlib
import importlib.metadata
import importlib.resources
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Callable, Mapping, Sequence

from .model_profile import (
    PRODUCTION_PROFILE, PROVIDER_CALLS_ALLOWED_ENV, PROVIDER_PROFILE_SHA256_ENV,
)
from .pcr_provider_protocol import pcr_action_contract_view

LAUNCH_SCHEMA = "aether.launch.v1"
PREFLIGHT_SCHEMA = "aether.launch_preflight.v1"
TERMINAL_SCHEMA = "aether.launch_terminal.v1"
_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$")
_AGENT_SELECTOR = "aether.harbor_agent:AetherHarborAgent"
_HARBOR_VERSION = "0.20.0"
_PACKAGE_NAME = "aether-runtime"

# Environment inherited by Harbor is intentionally bounded. Provider secrets
# enter only through the profile-owned names when explicit authorization exists.
_SAFE_ENV_NAMES = (
    "PATH", "HOME", "USER", "LOGNAME", "SHELL", "TMPDIR", "TEMP", "TMP",
    "LANG", "LC_ALL", "TERM", "DOCKER_HOST", "XDG_RUNTIME_DIR",
    "SSL_CERT_FILE", "SSL_CERT_DIR", "REQUESTS_CA_BUNDLE",
    "AETHER_SOURCE_COMMIT", "AETHER_RUNTIME_MANIFEST_SHA256",
)


class LaunchError(RuntimeError):
    pass


@dataclass(frozen=True)
class ClosureIdentity:
    sha256: str
    file_count: int

    def as_dict(self) -> dict[str, Any]:
        return {"sha256": self.sha256, "file_count": self.file_count}


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def canonical_sha256(value: Any) -> str:
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


def production_tool_schema_sha256() -> str:
    """Hash the actual installed Primary PCR action contract."""
    return canonical_sha256(pcr_action_contract_view())


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _resolved_no_symlink(path: Path, *, must_exist: bool) -> Path:
    expanded = path.expanduser()
    if must_exist and not expanded.exists():
        raise LaunchError(f"path does not exist: {expanded}")
    absolute = expanded.absolute()
    # Refuse any symlink component that currently exists. resolve() alone would
    # silently accept path aliases and erase the custody distinction.
    cursor = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        cursor = cursor / part
        if cursor.exists() and cursor.is_symlink():
            # macOS exposes a few immutable root aliases (/var, /tmp, /etc)
            # into /private. Accept only that exact OS-level shape; any later
            # user/task/package symlink remains a custody violation.
            root_alias = (
                cursor.parent == Path("/")
                and cursor.resolve() == (Path("/private") / cursor.name)
            )
            if not root_alias:
                raise LaunchError(f"symlink path component is not admissible: {cursor}")
    return absolute.resolve(strict=must_exist)


def _is_within(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def _assert_separate_paths(task: Path, evidence: Path, package_root: Path) -> None:
    pairs = (
        (evidence, task, "evidence root overlaps task"),
        (task, evidence, "task overlaps evidence root"),
        (evidence, package_root, "evidence root overlaps installed package"),
        (package_root, evidence, "installed package overlaps evidence root"),
    )
    for child, parent, message in pairs:
        if child == parent or _is_within(child, parent):
            raise LaunchError(message)


def path_closure(path: str | Path, *, reject_symlinks: bool = True) -> ClosureIdentity:
    root = Path(path)
    if not root.exists():
        raise LaunchError(f"closure path does not exist: {root}")
    if reject_symlinks and root.is_symlink():
        raise LaunchError(f"closure root may not be a symlink: {root}")
    rows: list[tuple[str, str, int]] = []
    if root.is_file():
        rows.append((root.name, file_sha256(root), root.stat().st_size))
    else:
        for item in sorted(root.rglob("*"), key=lambda p: p.as_posix()):
            rel = item.relative_to(root).as_posix()
            if any(part == "__pycache__" for part in item.parts) or item.suffix == ".pyc":
                continue
            if reject_symlinks and item.is_symlink():
                raise LaunchError(f"symlink in closure is not admissible: {item}")
            if item.is_file():
                rows.append((rel, file_sha256(item), item.stat().st_size))
    return ClosureIdentity(canonical_sha256(rows), len(rows))


def package_root() -> Path:
    return Path(__file__).resolve().parent


def package_closure(root: Path | None = None) -> ClosureIdentity:
    return path_closure(root or package_root(), reject_symlinks=True)


def _harbor_lock() -> dict[str, Any]:
    try:
        text = importlib.resources.files("aether").joinpath("harbor_runtime_lock.json").read_text(encoding="utf-8")
        value = json.loads(text)
    except Exception as exc:
        raise LaunchError(f"Harbor runtime lock unavailable: {exc}") from exc
    if not isinstance(value, dict):
        raise LaunchError("Harbor runtime lock must be an object")
    return value


def _harbor_identity() -> dict[str, str]:
    lock = _harbor_lock()
    if lock.get("harbor_version") != _HARBOR_VERSION or lock.get("agent_selector") != _AGENT_SELECTOR:
        raise LaunchError("installed Harbor runtime lock does not match launcher authority")
    try:
        version = importlib.metadata.version("harbor")
    except importlib.metadata.PackageNotFoundError as exc:
        raise LaunchError("Harbor 0.20.0 is not installed") from exc
    if version != _HARBOR_VERSION:
        raise LaunchError(f"Harbor version mismatch: installed={version!r}, required={_HARBOR_VERSION!r}")
    module_name, symbol = _AGENT_SELECTOR.split(":", 1)
    try:
        module = importlib.import_module(module_name)
        getattr(module, symbol)
    except Exception as exc:
        raise LaunchError(f"production Harbor agent import failed: {_AGENT_SELECTOR}: {exc}") from exc
    return {"version": version, "agent_selector": _AGENT_SELECTOR}


def build_spec(
    task_path: str | Path,
    *,
    run_id: str,
    evidence_root: str | Path,
    provider_calls_allowed: bool = False,
    metadata: Mapping[str, Any] | None = None,
    package_root_override: Path | None = None,
) -> dict[str, Any]:
    if not _RUN_ID_RE.fullmatch(str(run_id)):
        raise LaunchError("run_id must match [A-Za-z0-9][A-Za-z0-9._-]{0,119}")
    task = _resolved_no_symlink(Path(task_path), must_exist=True)
    evidence = _resolved_no_symlink(Path(evidence_root), must_exist=False)
    pkg_root = _resolved_no_symlink(package_root_override or package_root(), must_exist=True)
    _assert_separate_paths(task, evidence, pkg_root)
    task_id = path_closure(task)
    package_id = package_closure(pkg_root)
    harbor = _harbor_identity()
    try:
        package_version = importlib.metadata.version(_PACKAGE_NAME)
    except importlib.metadata.PackageNotFoundError:
        # Source-tree qualification before wheel installation. The closure hash,
        # not this convenience version string, is the immutable source identity.
        package_version = "source-tree"
    spec = {
        "schema_version": LAUNCH_SCHEMA,
        "run_id": str(run_id),
        "package": {
            "name": _PACKAGE_NAME,
            "version": package_version,
            "closure_sha256": package_id.sha256,
            "file_count": package_id.file_count,
        },
        "runtime": {
            "runtime_path": "pcr_v0",
            "profile_id": PRODUCTION_PROFILE.profile_id,
            "profile_sha256": PRODUCTION_PROFILE.sha256(),
            "tool_schema_sha256": production_tool_schema_sha256(),
        },
        "task": {
            "path": str(task),
            "closure_sha256": task_id.sha256,
            "file_count": task_id.file_count,
        },
        "harbor": harbor,
        "model": {
            "model_id": PRODUCTION_PROFILE.model_id,
            "deployment_env": PRODUCTION_PROFILE.deployment_env,
        },
        "evidence": {"root": str(evidence)},
        "provider": {"calls_allowed": bool(provider_calls_allowed)},
        "retry": {"max_attempts": 1, "max_retries": 0},
        "metadata": dict(metadata or {}),
    }
    validate_spec(spec)
    return spec


def _exact_keys(value: Mapping[str, Any], required: set[str], location: str) -> None:
    actual = set(value)
    missing = sorted(required - actual)
    unknown = sorted(actual - required)
    if missing or unknown:
        raise LaunchError(f"{location} keys invalid: missing={missing}, unknown={unknown}")


def validate_spec(spec: Mapping[str, Any]) -> None:
    if not isinstance(spec, Mapping):
        raise LaunchError("launch spec must be an object")
    _exact_keys(spec, {"schema_version","run_id","package","runtime","task","harbor","model","evidence","provider","retry","metadata"}, "launch spec")
    if spec.get("schema_version") != LAUNCH_SCHEMA:
        raise LaunchError("unsupported launch schema_version")
    if not _RUN_ID_RE.fullmatch(str(spec.get("run_id", ""))):
        raise LaunchError("invalid run_id")
    shapes = {
        "package": {"name","version","closure_sha256","file_count"},
        "runtime": {"runtime_path","profile_id","profile_sha256","tool_schema_sha256"},
        "task": {"path","closure_sha256","file_count"},
        "harbor": {"version","agent_selector"},
        "model": {"model_id","deployment_env"},
        "evidence": {"root"},
        "provider": {"calls_allowed"},
        "retry": {"max_attempts","max_retries"},
    }
    for key, keys in shapes.items():
        row = spec.get(key)
        if not isinstance(row, Mapping):
            raise LaunchError(f"{key} must be an object")
        _exact_keys(row, keys, key)
    if not isinstance(spec.get("metadata"), Mapping):
        raise LaunchError("metadata must be an object")
    if spec["package"].get("name") != _PACKAGE_NAME:
        raise LaunchError("package.name mismatch")
    if spec["runtime"] != {
        "runtime_path": "pcr_v0",
        "profile_id": PRODUCTION_PROFILE.profile_id,
        "profile_sha256": PRODUCTION_PROFILE.sha256(),
        "tool_schema_sha256": production_tool_schema_sha256(),
    }:
        raise LaunchError("runtime/profile identity mismatch")
    if spec["harbor"] != {"version": _HARBOR_VERSION, "agent_selector": _AGENT_SELECTOR}:
        raise LaunchError("Harbor identity mismatch")
    if spec["model"] != {"model_id": PRODUCTION_PROFILE.model_id, "deployment_env": PRODUCTION_PROFILE.deployment_env}:
        raise LaunchError("model identity mismatch")
    if not isinstance(spec["provider"].get("calls_allowed"), bool):
        raise LaunchError("provider.calls_allowed must be boolean")
    if spec["retry"] != {"max_attempts": 1, "max_retries": 0}:
        raise LaunchError("retry policy is fixed at one attempt and zero retries")
    for section, field in (("package","closure_sha256"),("runtime","profile_sha256"),("runtime","tool_schema_sha256"),("task","closure_sha256")):
        value = str(spec[section].get(field, ""))
        if not re.fullmatch(r"[0-9a-f]{64}", value):
            raise LaunchError(f"{section}.{field} must be exact lowercase sha256")
    if int(spec["package"].get("file_count", 0)) <= 0 or int(spec["task"].get("file_count", 0)) <= 0:
        raise LaunchError("package/task file_count must be positive")


def verify_custody(spec: Mapping[str, Any], *, package_root_override: Path | None = None) -> dict[str, Any]:
    validate_spec(spec)
    task = _resolved_no_symlink(Path(str(spec["task"]["path"])), must_exist=True)
    evidence = _resolved_no_symlink(Path(str(spec["evidence"]["root"])), must_exist=False)
    pkg_root = _resolved_no_symlink(package_root_override or package_root(), must_exist=True)
    _assert_separate_paths(task, evidence, pkg_root)
    observed_task = path_closure(task)
    observed_package = package_closure(pkg_root)
    if observed_task.sha256 != spec["task"]["closure_sha256"] or observed_task.file_count != spec["task"]["file_count"]:
        raise LaunchError("task closure changed after launch spec was built")
    if observed_package.sha256 != spec["package"]["closure_sha256"] or observed_package.file_count != spec["package"]["file_count"]:
        raise LaunchError("package closure changed after launch spec was built")
    harbor = _harbor_identity()
    if harbor != dict(spec["harbor"]):
        raise LaunchError("Harbor identity changed after launch spec was built")
    if PRODUCTION_PROFILE.sha256() != spec["runtime"]["profile_sha256"]:
        raise LaunchError("production model profile changed after launch spec was built")
    if production_tool_schema_sha256() != spec["runtime"]["tool_schema_sha256"]:
        raise LaunchError("production PCR tool schema changed after launch spec was built")
    return {
        "schema_version": PREFLIGHT_SCHEMA,
        "status": "valid",
        "spec_sha256": canonical_sha256(spec),
        "task_closure_sha256": observed_task.sha256,
        "package_closure_sha256": observed_package.sha256,
        "profile_sha256": PRODUCTION_PROFILE.sha256(),
        "tool_schema_sha256": production_tool_schema_sha256(),
        "harbor_version": harbor["version"],
        "agent_selector": harbor["agent_selector"],
        "provider_credentials_read": False,
    }


def _child_environment(spec: Mapping[str, Any]) -> dict[str, str]:
    allowed = bool(spec["provider"]["calls_allowed"])
    child = {name: os.environ[name] for name in _SAFE_ENV_NAMES if name in os.environ}
    child[PROVIDER_CALLS_ALLOWED_ENV] = "1" if allowed else "0"
    child[PROVIDER_PROFILE_SHA256_ENV] = str(spec["runtime"]["profile_sha256"])
    child["AETHER_CAMPAIGN_ID"] = str(
        (spec.get("metadata") or {}).get("campaign_id")
        or spec["runtime"]["profile_id"]
    )
    child["AETHER_TASK_CLOSURE_SHA256"] = str(spec["task"]["closure_sha256"])
    child["AETHER_PACKAGE_CLOSURE_SHA256"] = str(spec["package"]["closure_sha256"])
    if allowed:
        for name in (PRODUCTION_PROFILE.endpoint_env, PRODUCTION_PROFILE.deployment_env, PRODUCTION_PROFILE.key_env):
            if name not in os.environ or not str(os.environ[name]).strip():
                raise LaunchError(f"authorized provider launch missing required environment variable: {name}")
            child[name] = os.environ[name]
    return child


def harbor_argv(spec: Mapping[str, Any], run_root: Path, *, smoke: bool = False) -> list[str]:
    argv = [
        sys.executable, "-m", "harbor.cli.main", "run",
        "--path", str(spec["task"]["path"]),
        "--agent", _AGENT_SELECTOR,
        "--jobs-dir", str(run_root / "harbor"),
        "--job-name", str(spec["run_id"]),
        "--n-attempts", "1",
        "--max-retries", "0",
        "--n-concurrent", "1",
        "--yes",
        "--quiet",
    ]
    if smoke:
        argv.append("--install-only")
    return argv


def _stream_record(path: Path, text: str) -> dict[str, Any]:
    path.write_text(text, encoding="utf-8")
    raw = text.encode("utf-8")
    preview = text if len(text) <= 4000 else text[:2000] + "\n...[preview truncated]...\n" + text[-2000:]
    return {"path": str(path), "sha256": sha256(raw).hexdigest(), "bytes": len(raw), "preview": preview}


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def launch(
    spec: Mapping[str, Any],
    *,
    smoke: bool = False,
    dry_run: bool = False,
    runner: Callable[..., Any] = subprocess.run,
    package_root_override: Path | None = None,
) -> dict[str, Any]:
    validate_spec(spec)
    if smoke and bool(spec["provider"]["calls_allowed"]):
        raise LaunchError("provider-enabled launch cannot use provider-free smoke mode")
    evidence_root = _resolved_no_symlink(Path(str(spec["evidence"]["root"])), must_exist=False)
    run_root = evidence_root / str(spec["run_id"])
    if run_root.exists():
        raise LaunchError(f"run-id collision: evidence namespace already exists: {run_root}")
    run_root.mkdir(parents=True, exist_ok=False)
    _write_json(run_root / "launch_spec.json", dict(spec))
    try:
        preflight = verify_custody(spec, package_root_override=package_root_override)
        _write_json(run_root / "preflight_receipt.json", preflight)
        # Re-check immediately before dispatch. This is intentionally redundant:
        # prepare-time identity is not enough if source/task bytes changed.
        repeated = verify_custody(spec, package_root_override=package_root_override)
        if repeated["spec_sha256"] != preflight["spec_sha256"]:
            raise LaunchError("launch identity changed between preflight and dispatch")
        argv = harbor_argv(spec, run_root, smoke=smoke)
        argv_sha = canonical_sha256(argv)
        if not bool(spec["provider"]["calls_allowed"]) and not smoke and not dry_run:
            terminal = {
                "schema_version": TERMINAL_SCHEMA,
                "status": "blocked_provider_not_authorized",
                "spec_sha256": preflight["spec_sha256"],
                "argv_sha256": argv_sha,
                "provider_calls_allowed": False,
                "provider_credentials_read": False,
                "max_attempts": 1,
                "max_retries": 0,
            }
            _write_json(run_root / "terminal_launch_receipt.json", terminal)
            return terminal
        if dry_run:
            terminal = {
                "schema_version": TERMINAL_SCHEMA,
                "status": "dry_run_valid",
                "spec_sha256": preflight["spec_sha256"],
                "argv": argv,
                "argv_sha256": argv_sha,
                "provider_calls_allowed": bool(spec["provider"]["calls_allowed"]),
                "provider_credentials_read": False,
                "max_attempts": 1,
                "max_retries": 0,
            }
            _write_json(run_root / "terminal_launch_receipt.json", terminal)
            return terminal
        child_env = _child_environment(spec)
        proc = runner(argv, text=True, capture_output=True, env=child_env, shell=False)
        stdout = _stream_record(run_root / "launcher.stdout", str(getattr(proc, "stdout", "") or ""))
        stderr = _stream_record(run_root / "launcher.stderr", str(getattr(proc, "stderr", "") or ""))
        exit_code = int(getattr(proc, "returncode", 1))
        terminal = {
            "schema_version": TERMINAL_SCHEMA,
            "status": ("smoke_completed" if smoke and exit_code == 0 else "completed" if exit_code == 0 else "harbor_failed"),
            "spec_sha256": preflight["spec_sha256"],
            "argv": argv,
            "argv_sha256": argv_sha,
            "exit_code": exit_code,
            "provider_calls_allowed": bool(spec["provider"]["calls_allowed"]),
            "provider_credentials_read": bool(spec["provider"]["calls_allowed"]),
            "stdout": stdout,
            "stderr": stderr,
            "max_attempts": 1,
            "max_retries": 0,
            "harbor_owns_lifecycle": True,
            "harbor_owns_grading": True,
        }
        _write_json(run_root / "terminal_launch_receipt.json", terminal)
        return terminal
    except Exception as exc:
        terminal = {
            "schema_version": TERMINAL_SCHEMA,
            "status": "launch_blocked",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "provider_credentials_read": False,
        }
        _write_json(run_root / "terminal_launch_receipt.json", terminal)
        raise


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aether", description="Aether PCR task launcher")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="launch exactly one task through Harbor")
    run.add_argument("task_path")
    run.add_argument("--run-id", required=True)
    run.add_argument("--evidence", required=True)
    run.add_argument("--allow-provider", action="store_true")
    run.add_argument("--smoke", action="store_true", help="Harbor install-only lifecycle smoke; provider-free")
    run.add_argument("--dry-run", action="store_true", help="validate and seal launch without Harbor dispatch")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(list(argv) if argv is not None else None)
    if args.command != "run":
        raise LaunchError("unsupported command")
    if args.smoke and args.allow_provider:
        raise LaunchError("--smoke and --allow-provider are mutually exclusive")
    spec = build_spec(
        args.task_path,
        run_id=args.run_id,
        evidence_root=args.evidence,
        provider_calls_allowed=bool(args.allow_provider),
    )
    terminal = launch(spec, smoke=bool(args.smoke), dry_run=bool(args.dry_run))
    print(json.dumps(terminal, sort_keys=True))
    return 0 if terminal.get("status") in {"completed","smoke_completed","dry_run_valid"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
