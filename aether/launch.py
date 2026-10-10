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
import time
from typing import Any, Callable, Mapping, Sequence

from .model_profile import (
    PRODUCTION_PROFILE, PROVIDER_CALLS_ALLOWED_ENV, PROVIDER_PROFILE_SHA256_ENV,
)
from .official_launch_admission import (
    OfficialLaunchAdmission,
    OfficialLaunchAdmissionError,
)
from .provider_budget import (
    BUDGET_JOURNAL_ENV, BUDGET_PATH_ENV, BUDGET_SHA256_ENV, ProviderBudgetError,
    budget_journal_state, parse_budget_contract,
)
from .persistent_provider_protocol import persistent_action_contract_view

LAUNCH_SCHEMA = "aether.launch.v2"
PREFLIGHT_SCHEMA = "aether.launch_preflight.v1"
TERMINAL_SCHEMA = "aether.launch_terminal.v1"
_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$")
_AGENT_SELECTOR = "aether.harbor_agent:AetherHarborAgent"
_HARBOR_VERSION = "0.20.0"
_PACKAGE_NAME = "aether-runtime"
_PROVIDER_CANARY_SCHEMA = "aether.provider_runtime_canary.v1"
_PROVIDER_CANARY_MAX_AGE_S = 900.0

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
    """Hash the actual installed Primary PERSISTENT action contract."""
    return canonical_sha256(persistent_action_contract_view())


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


def _provider_runtime_identity() -> dict[str, Any]:
    """Provider-transport admission for the exact launcher Python runtime.

    This performs no network call and reads no provider credentials. It exists
    to fail before Harbor dispatch when a malformed/reused runtime cannot even
    construct the production transport selected by the immutable model profile.
    """
    if not bool(PRODUCTION_PROFILE.responses_websocket):
        return {
            "transport": "non_websocket",
            "websocket_client_required": False,
        }
    try:
        module = importlib.import_module("websocket")
        version = importlib.metadata.version("websocket-client")
    except (ModuleNotFoundError, importlib.metadata.PackageNotFoundError) as exc:
        raise LaunchError(
            "provider runtime admission failed: websocket-client is required for production Responses WebSocket mode"
        ) from exc
    create_connection = getattr(module, "create_connection", None)
    if not callable(create_connection):
        raise LaunchError(
            "provider runtime admission failed: websocket-client create_connection is unavailable"
        )
    match = re.match(r"^(\d+)\.(\d+)", str(version))
    if match is None or int(match.group(1)) != 1 or int(match.group(2)) < 8:
        raise LaunchError(
            f"provider runtime admission failed: websocket-client version {version!r} is outside required >=1.8,<2"
        )
    return {
        "transport": "responses_websocket",
        "websocket_client_required": True,
        "websocket_client_version": str(version),
        "create_connection_available": True,
        "network_calls_performed": 0,
        "provider_credentials_read": False,
    }


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


def _budget_binding(value: Mapping[str, Any] | str | Path | None) -> dict[str, Any] | None:
    if value is None:
        return None
    try:
        if isinstance(value, Mapping):
            raw = dict(value)
        else:
            source = _resolved_no_symlink(Path(value), must_exist=True)
            raw_value = json.loads(source.read_text(encoding="utf-8"))
            if not isinstance(raw_value, Mapping):
                raise ProviderBudgetError("budget contract file must contain one object")
            raw = dict(raw_value)
        contract = parse_budget_contract(raw)
    except (ProviderBudgetError, json.JSONDecodeError, OSError) as exc:
        raise LaunchError(f"invalid provider budget contract: {exc}") from exc
    return {
        "contract": contract.as_dict(),
        "contract_sha256": contract.sha256(),
    }


def build_spec(
    task_path: str | Path,
    *,
    run_id: str,
    evidence_root: str | Path,
    provider_calls_allowed: bool = False,
    provider_canary_receipt: str | Path | None = None,
    provider_budget_contract: Mapping[str, Any] | str | Path | None = None,
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
    canary_path: str | None = None
    canary_sha256: str | None = None
    if provider_canary_receipt is not None:
        canary = _resolved_no_symlink(Path(provider_canary_receipt), must_exist=True)
        canary_path = str(canary)
        canary_sha256 = file_sha256(canary)
    budget_binding = _budget_binding(provider_budget_contract)
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
            "runtime_path": "persistent_v0",
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
        "provider": {
            "calls_allowed": bool(provider_calls_allowed),
            "canary_receipt_path": canary_path,
            "canary_receipt_sha256": canary_sha256,
        },
        "budget": budget_binding,
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
    _exact_keys(spec, {"schema_version","run_id","package","runtime","task","harbor","model","evidence","provider","budget","retry","metadata"}, "launch spec")
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
        "provider": {"calls_allowed","canary_receipt_path","canary_receipt_sha256"},
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
        "runtime_path": "persistent_v0",
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
    canary_path = spec["provider"].get("canary_receipt_path")
    canary_sha = spec["provider"].get("canary_receipt_sha256")
    if (canary_path is None) != (canary_sha is None):
        raise LaunchError("provider canary receipt path/hash must be both present or both null")
    if canary_sha is not None and not re.fullmatch(r"[0-9a-f]{64}", str(canary_sha)):
        raise LaunchError("provider.canary_receipt_sha256 must be exact lowercase sha256")
    if not bool(spec["provider"].get("calls_allowed")) and canary_path is not None:
        raise LaunchError("provider-disabled launch may not bind a provider canary receipt")
    budget = spec.get("budget")
    if bool(spec["provider"].get("calls_allowed")) and budget is None:
        raise LaunchError("provider-enabled launch requires a finite provider budget contract")
    if not bool(spec["provider"].get("calls_allowed")) and budget is not None:
        raise LaunchError("provider-disabled launch may not bind a provider budget contract")
    if budget is not None:
        if not isinstance(budget, Mapping):
            raise LaunchError("budget must be an object or null")
        _exact_keys(budget, {"contract", "contract_sha256"}, "budget")
        contract_value = budget.get("contract")
        if not isinstance(contract_value, Mapping):
            raise LaunchError("budget.contract must be an object")
        try:
            contract = parse_budget_contract(contract_value)
        except ProviderBudgetError as exc:
            raise LaunchError(f"invalid provider budget contract: {exc}") from exc
        if str(budget.get("contract_sha256") or "") != contract.sha256():
            raise LaunchError("provider budget contract SHA256 mismatch")
        if contract.vm_incremental_cap_gbp != 0:
            raise LaunchError("current provider diagnostic requires vm_incremental_cap_gbp = 0")
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
        raise LaunchError("production PERSISTENT tool schema changed after launch spec was built")
    provider_runtime = (
        _provider_runtime_identity()
        if bool(spec["provider"]["calls_allowed"])
        else {
            "transport": "not_admitted_provider_disabled",
            "websocket_client_required": False,
            "network_calls_performed": 0,
            "provider_credentials_read": False,
        }
    )
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
        "provider_runtime": provider_runtime,
        "provider_budget": (
            None if spec.get("budget") is None else {
                "contract_sha256": spec["budget"]["contract_sha256"],
                "budget_id": spec["budget"]["contract"]["budget_id"],
                "total_cap_gbp": spec["budget"]["contract"]["total_cap_gbp"],
                "budget_constrained": True,
            }
        ),
        "provider_credentials_read": False,
    }


def _provider_route_sha256() -> str:
    endpoint = str(os.environ.get(PRODUCTION_PROFILE.endpoint_env, "") or "").strip()
    deployment = str(os.environ.get(PRODUCTION_PROFILE.deployment_env, "") or "").strip()
    if not endpoint or not deployment:
        raise LaunchError("provider canary admission requires configured endpoint and deployment")
    return sha256(canonical_json({"endpoint": endpoint, "deployment": deployment}).encode("utf-8")).hexdigest()


def _official_launch_identity(spec: Mapping[str, Any]) -> dict[str, Any]:
    """Return the stable identity that admits at most one official launch.

    Evidence roots and run ids are deliberately excluded: callers must not be
    able to bypass the duplicate-launch boundary by choosing a new namespace.
    The provider route is included when it is configured, while the ordinary
    child-environment gate still rejects a launch with missing credentials.
    Canary receipt and budget identities are intentionally excluded: a fresh
    canary or a newly named budget must not bypass the at-most-once boundary.
    """
    route_sha256: str | None
    try:
        route_sha256 = _provider_route_sha256()
    except LaunchError:
        # Keep the identity deterministic while the launch remains pre-dispatch;
        # _child_environment will fail closed and the admission will be removed.
        route_sha256 = None
    return {
        "schema_version": "aether.official_launch_identity.v1",
        "package": {
            "name": spec["package"]["name"],
            "version": spec["package"]["version"],
            "closure_sha256": spec["package"]["closure_sha256"],
            "file_count": int(spec["package"]["file_count"]),
        },
        "runtime": dict(spec["runtime"]),
        "task": {
            "closure_sha256": spec["task"]["closure_sha256"],
            "file_count": int(spec["task"]["file_count"]),
        },
        "harbor": dict(spec["harbor"]),
        "model": dict(spec["model"]),
        "provider": {
            "calls_allowed": True,
            "route_sha256": route_sha256,
        },
        "retry": dict(spec["retry"]),
    }


def _verify_provider_canary_receipt(
    spec: Mapping[str, Any],
    *,
    package_root_override: Path | None = None,
    now_unix_s: float | None = None,
) -> dict[str, Any]:
    provider = spec["provider"]
    raw_path = provider.get("canary_receipt_path")
    expected_sha = provider.get("canary_receipt_sha256")
    if not raw_path or not expected_sha:
        raise LaunchError("provider-enabled dispatch requires a bound successful provider canary receipt")
    path = _resolved_no_symlink(Path(str(raw_path)), must_exist=True)
    observed_sha = file_sha256(path)
    if observed_sha != str(expected_sha):
        raise LaunchError("provider canary receipt hash changed after launch spec was built")
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise LaunchError(f"provider canary receipt is not valid JSON: {exc}") from exc
    if not isinstance(receipt, Mapping) or receipt.get("schema_version") != _PROVIDER_CANARY_SCHEMA:
        raise LaunchError("provider canary receipt schema mismatch")
    if receipt.get("passed") is not True:
        raise LaunchError("provider canary receipt did not pass")
    if int(receipt.get("requested_width") or 0) != 1 or int(receipt.get("completed_provider_calls") or 0) != 1:
        raise LaunchError("provider canary receipt must prove exactly one completed width-1 call")
    candidate = receipt.get("candidate") if isinstance(receipt.get("candidate"), Mapping) else {}
    pkg_root = _resolved_no_symlink(package_root_override or package_root(), must_exist=True)
    closure = package_closure(pkg_root)
    expected_candidate = {
        "package_closure_sha256": closure.sha256,
        "package_file_count": closure.file_count,
        "model_profile_sha256": PRODUCTION_PROFILE.sha256(),
        "tool_schema_sha256": production_tool_schema_sha256(),
        "model_id": PRODUCTION_PROFILE.model_id,
        "solver_reasoning_effort": PRODUCTION_PROFILE.solver_reasoning_effort,
    }
    if dict(candidate) != expected_candidate:
        raise LaunchError("provider canary candidate identity does not match exact launch runtime")
    if str(receipt.get("python_executable") or "") != str(Path(sys.executable).resolve()):
        raise LaunchError("provider canary Python runtime differs from launch runtime")
    if str(receipt.get("package_root") or "") != str(pkg_root.resolve()):
        raise LaunchError("provider canary package root differs from launch runtime")
    if str(receipt.get("provider_route_sha256") or "") != _provider_route_sha256():
        raise LaunchError("provider canary route differs from current provider route")
    runtime = receipt.get("provider_runtime") if isinstance(receipt.get("provider_runtime"), Mapping) else {}
    current_runtime = _provider_runtime_identity()
    for key in ("transport", "websocket_client_version", "create_connection_available"):
        if runtime.get(key) != current_runtime.get(key):
            raise LaunchError(f"provider canary runtime mismatch for {key}")
    policy = receipt.get("provider_policy") if isinstance(receipt.get("provider_policy"), Mapping) else {}
    if policy != {
        "responses_websocket": True,
        "responses_background": False,
        "provider_max_retries": 0,
        "sdk_max_retries": 0,
        "poll_timeout_s": 180,
        "max_output_tokens": 2000,
        "budget_constrained": True,
    }:
        raise LaunchError("provider canary did not use the required bounded zero-retry WebSocket policy")
    canary_budget = receipt.get("provider_budget") if isinstance(receipt.get("provider_budget"), Mapping) else {}
    snapshot = canary_budget.get("snapshot") if isinstance(canary_budget.get("snapshot"), Mapping) else {}
    role_counts = snapshot.get("role_create_counts") if isinstance(snapshot.get("role_create_counts"), Mapping) else {}
    try:
        canary_cap = float(canary_budget.get("total_cap_gbp"))
    except (TypeError, ValueError):
        canary_cap = -1.0
    if not (
        canary_budget.get("model_id") == PRODUCTION_PROFILE.model_id
        and isinstance(canary_budget.get("contract_sha256"), str)
        and re.fullmatch(r"[0-9a-f]{64}", str(canary_budget.get("contract_sha256")))
        and int(canary_budget.get("max_total_provider_creates") or 0) == 1
        and 0 < canary_cap <= 1.0
        and int(snapshot.get("aggregate_create_count") or 0) == 1
        and int(role_counts.get("solver") or 0) == 1
        and int(role_counts.get("verifier") or 0) == 0
        and int(role_counts.get("vision") or 0) == 0
    ):
        raise LaunchError("provider canary did not prove one finite budget-guarded create")
    worker = receipt.get("worker") if isinstance(receipt.get("worker"), Mapping) else {}
    if not (
        worker.get("passed") is True
        and worker.get("transport_mode") == "websocket"
        and worker.get("native_tool_name") == "read_file"
        and int(worker.get("native_tool_call_count") or 0) == 1
        and int(worker.get("attempt_ordinal") or 0) == 1
    ):
        raise LaunchError("provider canary worker evidence is not an exact successful native read_file call")
    started = float(receipt.get("created_at_unix_s") or 0.0)
    finished = float(receipt.get("finished_at_unix_s") or 0.0)
    now = time.time() if now_unix_s is None else float(now_unix_s)
    if started <= 0 or finished < started or finished > now + 60.0:
        raise LaunchError("provider canary timestamps are invalid")
    age = now - finished
    if age < 0 or age > _PROVIDER_CANARY_MAX_AGE_S:
        raise LaunchError(f"provider canary is stale: age_s={age:.3f}")
    return {
        "status": "valid",
        "receipt_path": str(path),
        "receipt_sha256": observed_sha,
        "age_s": round(age, 3),
        "finished_at_unix_s": finished,
        "python_executable": str(Path(sys.executable).resolve()),
        "package_closure_sha256": closure.sha256,
        "profile_sha256": PRODUCTION_PROFILE.sha256(),
        "tool_schema_sha256": production_tool_schema_sha256(),
        "provider_route_sha256": _provider_route_sha256(),
        "transport_mode": "websocket",
        "native_tool_name": "read_file",
        "completed_provider_calls": 1,
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


def _budget_journal_summary(path: Path, spec: Mapping[str, Any]) -> dict[str, Any] | None:
    budget = spec.get("budget")
    if budget is None:
        return None
    try:
        contract = parse_budget_contract(budget["contract"])
        state = budget_journal_state(
            contract, contract_sha=str(budget["contract_sha256"]), journal_path=path,
        )
    except (ProviderBudgetError, KeyError, TypeError) as exc:
        raise LaunchError(f"provider budget journal invalid: {exc}") from exc
    return {
        "budget_id": contract.budget_id,
        "model_id": contract.model_id,
        "contract_sha256": budget["contract_sha256"],
        "total_cap_gbp": budget["contract"]["total_cap_gbp"],
        "reservation_count": int(state["reservation_count"]),
        "role_create_counts": dict(state["role_create_counts"]),
        "reserved_gbp": str(state["reserved_gbp"]),
        "journal_path": str(path),
        "journal_sha256": file_sha256(path) if path.exists() else None,
        "missing_usage_is_zero": False,
        "journal_validation": "valid",
    }


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
    budget_contract_path = run_root / "provider_budget_contract.json"
    budget_journal_path = run_root / "provider_budget_reservations.jsonl"
    if spec.get("budget") is not None:
        _write_json(budget_contract_path, dict(spec["budget"]["contract"]))
    dispatch_started = False
    admission: OfficialLaunchAdmission | None = None
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
                "provider_budget": _budget_journal_summary(budget_journal_path, spec),
                "max_attempts": 1,
                "max_retries": 0,
            }
            _write_json(run_root / "terminal_launch_receipt.json", terminal)
            return terminal
        provider_canary = (
            _verify_provider_canary_receipt(spec, package_root_override=package_root_override)
            if bool(spec["provider"]["calls_allowed"])
            else None
        )
        if provider_canary is not None:
            _write_json(run_root / "provider_canary_admission.json", provider_canary)
            try:
                admission = OfficialLaunchAdmission.acquire(
                    _official_launch_identity(spec),
                    run_id=str(spec["run_id"]),
                    evidence_root=str(evidence_root),
                )
            except OfficialLaunchAdmissionError as exc:
                raise LaunchError(str(exc)) from exc
            admission_receipt = {
                "schema_version": "aether.official_launch_admission.v1",
                "identity_sha256": admission.identity_sha256,
                "record_path": str(admission.record_path),
                "lock_path": str(admission.lock_path),
            }
            _write_json(run_root / "official_launch_admission.json", admission_receipt)
        child_env = _child_environment(spec)
        child_env["AETHER_PROVIDER_LIFECYCLE_JOURNAL"] = str(run_root / "provider_lifecycle.jsonl")
        if spec.get("budget") is not None:
            child_env[BUDGET_PATH_ENV] = str(budget_contract_path)
            child_env[BUDGET_SHA256_ENV] = str(spec["budget"]["contract_sha256"])
            child_env[BUDGET_JOURNAL_ENV] = str(budget_journal_path)
        if admission is not None:
            # A failed durable transition is treated as dispatch-uncertain and
            # therefore retained as a terminal blocker by the exception path.
            try:
                admission.mark_dispatch_started()
            except Exception:
                dispatch_started = True
                raise
        dispatch_started = True
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
            "provider_canary": provider_canary,
            "provider_budget": _budget_journal_summary(budget_journal_path, spec),
            "stdout": stdout,
            "stderr": stderr,
            "max_attempts": 1,
            "max_retries": 0,
            "harbor_owns_lifecycle": True,
            "harbor_owns_grading": True,
        }
        _write_json(run_root / "terminal_launch_receipt.json", terminal)
        if admission is not None:
            admission.finalize(status=terminal["status"], exit_code=exit_code)
        return terminal
    except Exception as exc:
        if admission is not None:
            try:
                if dispatch_started:
                    admission.finalize(
                        status="unknown",
                        error=f"{type(exc).__name__}: {exc}",
                    )
                else:
                    admission.abandon_before_dispatch()
            except Exception:
                # Preserve the original launch error.  A lease that cannot be
                # finalized is intentionally left durable by its own helper.
                pass
        terminal = {
            "schema_version": TERMINAL_SCHEMA,
            "status": "launch_blocked",
            "error_type": type(exc).__name__,
            "error": str(exc),
            # Before child dispatch credentials are provably unread. After the
            # Harbor child has started, fail conservatively: the credential was
            # available to that child even if terminal accounting later failed.
            "provider_credentials_read": bool(
                dispatch_started and spec["provider"]["calls_allowed"]
            ),
        }
        _write_json(run_root / "terminal_launch_receipt.json", terminal)
        raise


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aether", description="Aether PERSISTENT task launcher")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="launch exactly one task through Harbor")
    run.add_argument("task_path")
    run.add_argument("--run-id", required=True)
    run.add_argument("--evidence", required=True)
    run.add_argument("--allow-provider", action="store_true")
    run.add_argument("--provider-canary-receipt", help="successful provider canary receipt bound to this exact runtime")
    run.add_argument("--budget-contract", help="finite GBP provider budget contract for this exact run")
    run.add_argument("--smoke", action="store_true", help="Harbor install-only lifecycle smoke; provider-free")
    run.add_argument("--dry-run", action="store_true", help="validate and seal launch without Harbor dispatch")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(list(argv) if argv is not None else None)
    if args.command != "run":
        raise LaunchError("unsupported command")
    if args.smoke and args.allow_provider:
        raise LaunchError("--smoke and --allow-provider are mutually exclusive")
    if args.provider_canary_receipt and not args.allow_provider:
        raise LaunchError("--provider-canary-receipt requires --allow-provider")
    if args.allow_provider and not args.provider_canary_receipt:
        raise LaunchError("--allow-provider requires --provider-canary-receipt")
    if args.allow_provider and not args.budget_contract:
        raise LaunchError("--allow-provider requires --budget-contract")
    if args.budget_contract and not args.allow_provider:
        raise LaunchError("--budget-contract requires --allow-provider")
    spec = build_spec(
        args.task_path,
        run_id=args.run_id,
        evidence_root=args.evidence,
        provider_calls_allowed=bool(args.allow_provider),
        provider_canary_receipt=args.provider_canary_receipt,
        provider_budget_contract=args.budget_contract,
    )
    terminal = launch(spec, smoke=bool(args.smoke), dry_run=bool(args.dry_run))
    print(json.dumps(terminal, sort_keys=True))
    return 0 if terminal.get("status") in {"completed","smoke_completed","dry_run_valid"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
