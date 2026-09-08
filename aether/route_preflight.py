"""Preflight certified proof routes in Solver and Verifier environments."""
from __future__ import annotations

from dataclasses import dataclass
import shlex
from typing import Any, Mapping, Sequence

from .runtime_ir import CompiledRuntime
from .verifier_overlay import VerifierOverlay


@dataclass(frozen=True)
class RoutePreflightIssue:
    code: str
    clause_id: str
    route: str
    detail: str

    def as_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "clause_id": self.clause_id,
            "route": self.route,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class RoutePreflightRow:
    clause_id: str
    route: str
    route_kind: str
    solver_available: bool
    verifier_available: bool
    solver_detail: str
    verifier_detail: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "clause_id": self.clause_id,
            "route": self.route,
            "route_kind": self.route_kind,
            "solver_available": self.solver_available,
            "verifier_available": self.verifier_available,
            "solver_detail": self.solver_detail,
            "verifier_detail": self.verifier_detail,
        }


def _route_parts(route: str) -> tuple[str, str]:
    kind, separator, target = str(route or "").strip().partition(":")
    return kind.strip(), target.strip() if separator else ""


def _command_executable(command: str) -> str:
    """Return an executable only for a syntactically concrete command."""
    try:
        parts = shlex.split(command)
    except ValueError:
        return ""
    if len(parts) < 2:
        return ""
    while parts and "=" in parts[0] and not parts[0].startswith(("/", "./")):
        name, _, _value = parts[0].partition("=")
        if not name.replace("_", "").isalnum():
            break
        parts.pop(0)
    return parts[0] if parts else ""


def _command_available(executor: Any, executable: str, *, cwd: str | None = None) -> tuple[bool, str]:
    result = executor.run_command(f"command -v {shlex.quote(executable)}", cwd=cwd, timeout_s=30)
    detail = (result.stdout or result.stderr).strip()[:500]
    return bool(result.success), detail or f"command -v {executable} exit={result.exit_code}"


def _overlay_command_available(overlay: VerifierOverlay, executable: str) -> tuple[bool, str]:
    result = overlay.run_command(f"command -v {shlex.quote(executable)}", timeout_s=30)
    if result.get("error"):
        return False, str(result["error"])
    detail = str(result.get("stdout") or result.get("stderr") or "").strip()[:500]
    return bool(result.get("success")), detail or f"command -v {executable} exit={result.get('exit_code')}"


def preflight_proof_routes(
    compiled: CompiledRuntime,
    executor: Any,
    envmap: Any,
    *,
    hooks: Any | None = None,
) -> tuple[tuple[RoutePreflightRow, ...], tuple[RoutePreflightIssue, ...]]:
    """Prove that every certified route is executable before Solver work."""
    if not compiled.proof_contract:
        return (), ()
    rows: list[RoutePreflightRow] = []
    issues: list[RoutePreflightIssue] = []
    require_independent_isolation = True
    overlay = VerifierOverlay(
        executor,
        envmap.workspace_root,
        max_command_timeout_s=60,
        require_independent_isolation=require_independent_isolation,
    )
    isolation_probe: tuple[bool, str] | None = None

    def _pcr_isolation_available() -> tuple[bool, str]:
        nonlocal isolation_probe
        if not require_independent_isolation:
            return True, "independent isolation not required for this protocol"
        if isolation_probe is None:
            result = overlay.run_command("true", timeout_s=30)
            ok = (
                not bool(result.get("error"))
                and result.get("independent_isolation_verified") is True
                and result.get("isolation_cleanup_verified") is True
            )
            detail = str(result.get("error") or result.get("execution_isolation") or "")
            isolation_probe = (ok, detail or ("isolated verifier execution available" if ok else "isolated verifier execution unavailable"))
        return isolation_probe
    try:
        for clause in compiled.proof_contract:
            clause_id = str(clause.get("clause_id", "")).strip()
            route = str(clause.get("verifier_route", "")).strip()
            kind, target = _route_parts(route)
            solver_available = False
            verifier_available = False
            solver_detail = ""
            verifier_detail = ""

            if kind == "overlay_run_command":
                # The suffix is an Architect-declared description of the
                # required evidence method, not a command supplied for later
                # execution.  The Verifier chooses an actual bounded command
                # only in its V3 request, whose immutable command hash is
                # registered separately.  Preflight must therefore check the
                # execution capability, not try to execute a descriptive
                # label such as ``grpc-client-round-trip``.
                executable = _command_executable(target)
                if executable:
                    solver_available, solver_detail = _command_available(
                        executor, executable, cwd=envmap.workspace_root,
                    )
                    verifier_available, verifier_detail = _overlay_command_available(overlay, executable)
                else:
                    available = callable(getattr(executor, "run_command", None))
                    solver_available = available
                    solver_detail = (
                        "derived overlay command capability available; actual command is bound at inspection time"
                        if available else "command execution method missing"
                    )
                    if require_independent_isolation and available:
                        verifier_available, verifier_detail = _pcr_isolation_available()
                    else:
                        verifier_available = available
                        verifier_detail = solver_detail
            elif kind == "read_output":
                # Output handles are created only after Solver work.  Their
                # target cannot be checked at preflight, but the kernel-owned
                # read_output inspection route is always available to the
                # Verifier once a handle is registered.  Later receipt
                # freshness and successful inspection still decide proof.
                solver_available = verifier_available = True
                solver_detail = verifier_detail = (
                    "runtime-produced output handles are deferred until a receipt exists"
                )
            elif kind in {"read_file", "inspect_artifact"}:
                solver_available = all(hasattr(executor, name) for name in ("exists", "read_file"))
                verifier_available = solver_available
                solver_detail = "filesystem inspection methods available" if solver_available else "filesystem inspection method missing"
                verifier_detail = solver_detail
            elif kind == "compare_initial_path":
                available = callable(getattr(executor, "compare_initial_path", None))
                solver_available = verifier_available = available
                solver_detail = verifier_detail = (
                    "immutable generation-0/current comparator available"
                    if available else "immutable generation-0/current comparator unavailable"
                )
            elif kind == "rerun_check":
                check = compiled.eval_index.get(target)
                solver_available = check is not None and hasattr(executor, "run_command")
                solver_detail = "compiled check available" if solver_available else f"compiled check not found: {target}"
                if require_independent_isolation and solver_available:
                    verifier_available, verifier_detail = _pcr_isolation_available()
                else:
                    verifier_available = solver_available
                    verifier_detail = solver_detail
            elif kind in {"probe_port", "probe_http", "probe_process"}:
                available = hasattr(executor, "probe_process")
                solver_available = verifier_available = available
                solver_detail = verifier_detail = "probe method available" if available else "probe method missing"
            elif kind == "perceive_artifact":
                # Match preflight to the route actually implemented by both
                # Solver and Verifier: vision-backed image perception over an
                # executor binary read. A generic "perception" capability must
                # not advertise PDF/audio support that perceive_artifact cannot
                # execute, otherwise the run enters a guaranteed late failure.
                from .perception_vision import media_type_for
                capabilities = getattr(envmap, "capabilities", {}) or {}
                perception_capability = any(
                    bool(getattr(capability, "available", True))
                    and (
                        str(getattr(capability, "capability_id", "")).strip() == "perception"
                        or "inspect_artifact" in tuple(getattr(capability, "tool_names", ()) or ())
                    )
                    for capability in capabilities.values()
                )
                binary_read = callable(getattr(executor, "read_file_bytes", None))
                # Production preflight receives the current run hooks and can
                # therefore prove the actual vision route exists without
                # invoking it. Direct callers that omit hooks retain the older
                # capability-only compatibility behavior.
                vision_hook = (
                    callable(getattr(hooks, "perceive_image", None))
                    if hooks is not None else True
                )
                media_type = media_type_for(target) if target else ""
                available = bool(perception_capability and binary_read and vision_hook and media_type)
                solver_available = verifier_available = available
                if not perception_capability:
                    detail = "perception capability unavailable"
                elif not target:
                    detail = "perceive_artifact requires a concrete artifact path"
                elif not media_type:
                    detail = f"perceive_artifact media type unsupported by current vision route: {target}"
                elif not binary_read:
                    detail = "executor binary-read capability unavailable for perception"
                elif not vision_hook:
                    detail = "vision perception hook unavailable for perceive_artifact"
                else:
                    detail = f"vision image perception substrate available ({media_type})"
                solver_detail = verifier_detail = detail
            else:
                solver_detail = verifier_detail = f"unsupported preflight route kind: {kind}"

            row = RoutePreflightRow(
                clause_id=clause_id,
                route=route,
                route_kind=kind,
                solver_available=solver_available,
                verifier_available=verifier_available,
                solver_detail=solver_detail,
                verifier_detail=verifier_detail,
            )
            rows.append(row)
            if not solver_available:
                issues.append(RoutePreflightIssue(
                    "solver_route_preflight_failed", clause_id, route, solver_detail,
                ))
            if not verifier_available:
                issues.append(RoutePreflightIssue(
                    "verifier_route_preflight_failed", clause_id, route, verifier_detail,
                ))
            if solver_available != verifier_available:
                issues.append(RoutePreflightIssue(
                    "solver_verifier_route_parity_failed",
                    clause_id,
                    route,
                    f"solver_available={solver_available} verifier_available={verifier_available}",
                ))
    finally:
        overlay.teardown()
    return tuple(rows), tuple(issues)
