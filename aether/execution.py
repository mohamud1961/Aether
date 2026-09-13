from __future__ import annotations

from dataclasses import dataclass, replace
import fnmatch
import hashlib
import re
from typing import Any, Callable, Mapping, Protocol

from .ledger import Receipt
from .lifecycle import declared_job_relevance
from .runtime_ir import ActionRequest, EnvMap, normalize_relpath


@dataclass(frozen=True)
class CommandResult:
    command: str
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    modified_paths: tuple[str, ...] = ()
    produced_artifacts: tuple[str, ...] = ()
    removed_paths: tuple[str, ...] = ()
    state_delta: Mapping[str, Any] = None  # type: ignore[assignment]
    metrics: Mapping[str, float] = None  # type: ignore[assignment]
    provenance: tuple[str, ...] = ()
    # Truthful capture beyond the inline cap: when a stream exceeds the
    # inline retention bound, the FULL stream is spooled to this path and the
    # inline field holds a marked head+tail.  Empty string = inline is full.
    stdout_overflow_path: str = ""
    stderr_overflow_path: str = ""
    stdout_bytes_total: int = -1
    stderr_bytes_total: int = -1
    timed_out: bool = False

    @property
    def success(self) -> bool:
        return self.exit_code == 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "state_delta", dict(self.state_delta or {}))
        object.__setattr__(self, "metrics", dict(self.metrics or {}))
        if self.stdout_bytes_total < 0:
            object.__setattr__(self, "stdout_bytes_total", len(self.stdout))
        if self.stderr_bytes_total < 0:
            object.__setattr__(self, "stderr_bytes_total", len(self.stderr))


@dataclass(frozen=True)
class ProcessHandle:
    process_id: str
    name: str
    command: str
    interactive: bool = False
    live: bool = True
    endpoint: str = ""
    detail: str = ""
    pid: int | None = None
    start_time_ticks: str = ""
    command_sha256: str = ""
    process_generation: str = ""
    stdout_log: str = ""
    stderr_log: str = ""
    status_log: str = ""
    status: str = "running"
    exit_code: int | None = None

@dataclass(frozen=True)
class TerminalSessionHandle:
    session_id: str
    name: str
    command: str
    live: bool
    pid: int | None = None
    start_time_ticks: str = ""
    command_sha256: str = ""
    process_generation: str = ""
    process_group_id: int | None = None
    session_leader_id: int | None = None
    transcript_path: str = ""
    state_delta: Mapping[str, Any] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        object.__setattr__(self, "state_delta", dict(self.state_delta or {}))


@dataclass(frozen=True)
class TerminalSessionState:
    session_id: str
    live: bool
    exit_code: int | None = None
    cursor: int = 0
    total_bytes: int = 0
    more_available: bool = False
    bytes_sent: int = 0
    signal: str = ""
    process_generation: str = ""
    process_group_id: int | None = None
    session_leader_id: int | None = None
    state_delta: Mapping[str, Any] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        object.__setattr__(self, "state_delta", dict(self.state_delta or {}))


@dataclass(frozen=True)
class TerminalReadResult:
    session_id: str
    output: str
    bytes_read: int
    cursor: int
    total_bytes: int
    more_available: bool
    live: bool
    exit_code: int | None = None
    process_generation: str = ""
    process_group_id: int | None = None
    session_leader_id: int | None = None
    state_delta: Mapping[str, Any] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        object.__setattr__(self, "state_delta", dict(self.state_delta or {}))


@dataclass(frozen=True)
class ProbeResult:
    target: str
    live: bool
    detail: str = ""
    fresh: bool = True
    service_name: str = ""
    process_id: str = ""
    process_generation: str = ""
    process_generation_verified: bool = False
    endpoint_owner_pids: tuple[int, ...] = ()

@dataclass(frozen=True)
class JobProbeResult:
    target: str
    found: bool
    status: str
    completed: bool
    succeeded: bool | None = None
    exit_code: int | None = None
    detail: str = ""
    job_id: str = ""
    process_id: str = ""
    process_generation: str = ""
    process_generation_verified: bool = False
    lifecycle_authority: str = ""
    pid: int | None = None


@dataclass(frozen=True)
class ComputerActionResult:
    action: Mapping[str, Any]
    success: bool
    screenshot_bytes: bytes
    media_type: str = "image/png"
    width: int | None = None
    height: int | None = None
    detail: str = ""
    state_delta: Mapping[str, Any] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        object.__setattr__(self, "action", dict(self.action or {}))
        object.__setattr__(self, "screenshot_bytes", bytes(self.screenshot_bytes or b""))
        object.__setattr__(self, "state_delta", dict(self.state_delta or {}))


@dataclass(frozen=True)
class ArtifactInspection:
    path: str
    mode: str
    success: bool
    extracted_text: str = ""
    metadata: Mapping[str, Any] = None  # type: ignore[assignment]
    detail: str = ""
    outcome: str = ""
    reason_code: str = ""
    execution: str = ""
    recovery_operations: tuple[str, ...] = ()
    replay_safe: bool | None = None

    def __post_init__(self) -> None:
        metadata = dict(self.metadata or {})
        object.__setattr__(self, "metadata", metadata)
        if not self.outcome:
            default_outcome = (
                "success"
                if self.success
                else (
                    "unavailable"
                    if metadata.get("semantic_content_available") is False
                    and metadata.get("artifact_identity")
                    else "failed"
                )
            )
            object.__setattr__(self, "outcome", default_outcome)
        if not self.reason_code:
            object.__setattr__(
                self,
                "reason_code",
                "inspection_succeeded"
                if self.success
                else (
                    "semantic_content_unavailable"
                    if self.outcome == "unavailable"
                    else "artifact_inspection_failed"
                ),
            )
        if not self.execution:
            object.__setattr__(
                self,
                "execution",
                "exited" if self.success or metadata.get("artifact_identity") else "not_started",
            )
        object.__setattr__(self, "recovery_operations", tuple(
            str(item)[:200] for item in self.recovery_operations if str(item).strip()
        ))
        if self.replay_safe is None:
            object.__setattr__(self, "replay_safe", True)


class Executor(Protocol):
    def read_file(self, path: str) -> str:
        ...

    def write_file(self, path: str, content: str) -> None:
        ...

    def run_command(self, command: str, *, cwd: str | None = None, timeout_s: int = 30) -> CommandResult:
        ...

    def launch_process(
        self,
        name: str,
        command: str,
        *,
        interactive: bool = False,
        cwd: str | None = None,
    ) -> ProcessHandle:
        ...

    def start_terminal_session(
        self, name: str, command: str, *, cwd: str | None = None
    ) -> TerminalSessionHandle:
        ...

    def terminal_send(
        self, session_id: str, data: str, *, append_newline: bool = True
    ) -> TerminalSessionState:
        ...

    def terminal_read(
        self, session_id: str, *, max_bytes: int = 20_000, wait_ms: int = 1000
    ) -> TerminalReadResult:
        ...

    def terminal_wait(
        self, session_id: str, *, timeout_s: float = 30.0
    ) -> TerminalSessionState:
        ...

    def terminal_interrupt(self, session_id: str) -> TerminalSessionState:
        ...

    def terminal_close(self, session_id: str) -> TerminalSessionState:
        ...

    def probe_process(self, target: str) -> ProbeResult:
        ...

    def probe_job(self, target: str) -> JobProbeResult:
        ...

    def job_output(self, target: str, *, tail_lines: int = 40) -> dict[str, str]:
        ...

    def stop_process(self, target: str) -> bool:
        ...

    def inspect_artifact(self, path: str, mode: str) -> ArtifactInspection:
        ...

    def inspect_task_artifact(self, path: str, mode: str) -> ArtifactInspection:
        """Inspect an explicitly executor-authorized task-container path.

        This optional route is intentionally distinct from workspace reads.  A
        backend must enforce its own namespace/allowlist and, when needed, stage
        the exact bytes into the declared workspace before returning success.
        """
        ...

    def computer_available(self) -> bool:
        ...

    def computer_action(self, action: Mapping[str, Any]) -> ComputerActionResult:
        ...

    def refresh_envmap(self, envmap: EnvMap) -> EnvMap:
        ...

    def exists(self, path: str) -> bool:
        ...

    def glob(self, pattern: str) -> tuple[str, ...]:
        ...


_BOOTSTRAP_COMMAND_TIMEOUT_S = 120


def _bootstrap_command_timeout_s(envmap: EnvMap) -> tuple[int, str]:
    """Use explicit task time authority for dependency acquisition when present."""
    metadata = envmap.task_metadata if isinstance(envmap.task_metadata, Mapping) else {}
    budget = metadata.get("resource_budget") if isinstance(metadata.get("resource_budget"), Mapping) else {}
    for source in (budget, metadata):
        for key in ("agent_timeout_sec", "timeout_sec"):
            value = source.get(key) if isinstance(source, Mapping) else None
            try:
                if value is not None and float(value) > 0:
                    timeout_s = max(1, int(float(value)))
                    return timeout_s, f"task_declared:{key}={timeout_s}"
            except (TypeError, ValueError):
                pass
    return _BOOTSTRAP_COMMAND_TIMEOUT_S, f"metadata_poor_fallback={_BOOTSTRAP_COMMAND_TIMEOUT_S}"


def run_stateful_command(
    executor: Executor,
    command: str,
    *,
    cwd: str | None = None,
    timeout_s: int = 30,
) -> CommandResult:
    """Execute a task-authorized potentially mutating command.

    Remote substrates may expose an optional tracked route that derives
    workspace deltas around this exact action frontier. Executors whose normal
    ``run_command`` already tracks state, or simple test executors, retain their
    existing behavior unchanged.
    """
    tracked = getattr(executor, "run_tracked_command", None)
    if callable(tracked):
        return tracked(command, cwd=cwd, timeout_s=timeout_s)
    return executor.run_command(command, cwd=cwd, timeout_s=timeout_s)


class BootstrapEngine:
    _TEMPLATES: dict[str, Callable[[Mapping[str, Any]], str]] = {
        "apt": lambda args: f"apt-get update && apt-get install -y {args['target']}",
        "pip": lambda args: f"pip install {args['target']}",
        "uv": lambda args: f"uv pip install {args['target']}",
        "npm": lambda args: f"npm install {args['target']}",
        "cargo": lambda args: f"cargo install {args['target']}",
        "opam": lambda args: f"opam install -y {args['target']}",
        "git": lambda args: f"git clone {args['source']}",
        "wget": lambda args: f"wget -O {args.get('output', 'download.bin')} {args['source']}",
        "curl": lambda args: f"curl -L {args['source']} -o {args.get('output', 'download.bin')}",
        "hf": lambda args: f"hf download {args['target']}",
    }

    def execute(
        self,
        action: ActionRequest,
        step: int,
        executor: Executor,
        envmap: EnvMap,
    ) -> tuple[Receipt, EnvMap | None]:
        manager = str(action.arguments.get("manager", "")).strip()
        builder = self._TEMPLATES.get(manager)
        if builder is None:
            receipt = Receipt(
                receipt_id=f"step-{step}:{action.action_id}:bootstrap",
                step=step,
                kind="bootstrap",
                success=False,
                summary=f"unsupported bootstrap manager: {manager}",
                failure_class="bootstrap_required",
                payload={
                    "manager": manager,
                    "candidate_id": action.candidate_id,
                },
            )
            return receipt, None

        try:
            command = builder(action.arguments)
        except KeyError as exc:
            receipt = Receipt(
                receipt_id=f"step-{step}:{action.action_id}:bootstrap",
                step=step,
                kind="bootstrap",
                success=False,
                summary=f"bootstrap arguments missing: {exc.args[0]}",
                failure_class="bootstrap_required",
                payload={
                    "manager": manager,
                    "candidate_id": action.candidate_id,
                },
            )
            return receipt, None

        # Acquisition is intrinsically slower than ordinary shell probes
        # (package indexes, installers and compilers routinely exceed 30s).
        # Keep it bounded, but do not inherit the generic 30-second command
        # default that can turn a valid bootstrap into a harness exception.
        bootstrap_timeout_s, bootstrap_timeout_policy = _bootstrap_command_timeout_s(envmap)
        result = run_stateful_command(
            executor, command, cwd=envmap.workspace_root, timeout_s=bootstrap_timeout_s
        )
        refreshed = executor.refresh_envmap(envmap) if result.success else envmap
        old_caps = set(envmap.capabilities.keys())
        new_caps = set(refreshed.capabilities.keys())
        added_caps = tuple(sorted(new_caps - old_caps))
        receipt = Receipt(
            receipt_id=f"step-{step}:{action.action_id}:bootstrap",
            step=step,
            kind="bootstrap",
            success=result.success,
            summary=f"bootstrap {manager}: exit={result.exit_code}",
            state_change=bool(
                result.success
                or result.modified_paths
                or result.produced_artifacts
                or result.removed_paths
            ),
            failure_class="" if result.success else "bootstrap_required",
            payload={
                "manager": manager,
                "command": command,
                "timeout_s": bootstrap_timeout_s,
                "timeout_policy": bootstrap_timeout_policy,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "modified_paths": tuple(normalize_relpath(path, envmap.workspace_root) for path in result.modified_paths),
                "artifact_paths": tuple(normalize_relpath(path, envmap.workspace_root) for path in result.produced_artifacts),
                "removed_paths": tuple(normalize_relpath(path, envmap.workspace_root) for path in result.removed_paths),
                "state_delta": dict(result.state_delta),
                "provenance": list(result.provenance),
                "capabilities_added": added_caps,
                "candidate_id": action.candidate_id,
            },
        )
        if refreshed.digest() != envmap.digest():
            return receipt, refreshed
        return receipt, None


def _observe_process_workspace_state(executor: Executor, target: str) -> dict[str, Any]:
    observer = getattr(executor, "observe_process_state", None)
    if not callable(observer):
        return {}
    try:
        value = observer(str(target))
    except Exception as exc:  # noqa: BLE001 - observation failure is explicit freshness evidence
        return {
            "mutation_detection_status": "unavailable",
            "mutation_detection_scope": "managed_process_async_workspace_effects",
            "observation_error_type": type(exc).__name__,
            "observation_error": str(exc),
        }
    return dict(value or {})


def _delta_has_concrete_workspace_change(delta: Mapping[str, Any]) -> bool:
    return bool(
        tuple(delta.get("created_paths", ()) or ())
        or tuple(delta.get("removed_paths", ()) or ())
        or tuple(delta.get("content_changed_paths", ()) or ())
        or tuple(delta.get("metadata_changed_paths", ()) or ())
    )


def _delta_proves_no_workspace_change(delta: Mapping[str, Any]) -> bool:
    """Whether a process observation precisely proves an unchanged workspace.

    Process lifecycle is separate from task-world state.  A successful stop
    still creates a freshness boundary when observation is missing, truncated,
    coarse, or reports a concrete path delta.  Only a complete, non-truncated
    inventory with an explicit complete path-set comparison can classify the
    stop as lifecycle-only housekeeping.
    """
    if not isinstance(delta, Mapping):
        return False
    return bool(
        str(delta.get("mutation_detection_status", "")).strip() == "complete"
        and str(delta.get("path_set_delta_status", "")).strip() == "complete"
        and delta.get("before_truncated") is False
        and delta.get("after_truncated") is False
        and not _delta_has_concrete_workspace_change(delta)
    )


class ProcessOrchestratorV2:
    def launch(
        self,
        action: ActionRequest,
        step: int,
        executor: Executor,
        *,
        workspace_root: str,
        interactive: bool,
    ) -> Receipt:
        service_name = str(action.arguments.get("service_name", "")).strip()
        command = str(action.arguments.get("command", "")).strip()
        handle = executor.launch_process(
            service_name,
            command,
            interactive=interactive,
            cwd=workspace_root,
        )
        state_delta = _observe_process_workspace_state(executor, handle.process_id)
        is_background_job = action.kind == "start_job"
        launch_tool = "start_job" if is_background_job else "launch_process"
        relevance, relevance_reason, replacement_job_id = declared_job_relevance(
            action.arguments
        )
        contract_guarantees = (
            ("detached_background_job", "persists_after_agent_loop_exit")
            if is_background_job else ()
        )
        return Receipt(
            receipt_id=f"step-{step}:{action.action_id}:launch",
            step=step,
            kind="process_launch",
            success=handle.live,
            summary=(
                f"started background job {handle.name} via start_job"
                if is_background_job else f"launched process {handle.name}"
            ),
            state_change=True,
            failure_class="" if handle.live else "service_not_ready",
            payload={
                "process_id": handle.process_id,
                "job_id": handle.process_id if is_background_job else "",
                "service_name": handle.name,
                "launch_tool": launch_tool,
                "launch_mode": "background_job" if is_background_job else "managed_process",
                "detached": bool(is_background_job and not handle.interactive),
                "contract_guarantees": list(contract_guarantees),
                "command": handle.command,
                "interactive": handle.interactive,
                "live": handle.live,
                "detail": handle.detail,
                "pid": handle.pid,
                "start_time_ticks": handle.start_time_ticks,
                "command_sha256": handle.command_sha256,
                "process_generation": handle.process_generation,
                "stdout_log": handle.stdout_log,
                "stderr_log": handle.stderr_log,
                "status_log": handle.status_log,
                "job_status": handle.status,
                "exit_code": handle.exit_code,
                "job_relevance": relevance or "unclassified",
                "job_relevance_source": (
                    "model_declared" if relevance is not None else "default_unclassified"
                ),
                "job_relevance_reason": relevance_reason,
                "replacement_job_id": replacement_job_id,
                "state_delta": state_delta,
                "candidate_id": action.candidate_id,
            },
        )

    def probe(
        self,
        action: ActionRequest,
        step: int,
        executor: Executor,
    ) -> Receipt:
        target = str(action.arguments.get("target", "")).strip()
        probe = executor.probe_process(target)
        state_delta = _observe_process_workspace_state(
            executor, probe.process_id or target
        )
        return Receipt(
            receipt_id=f"step-{step}:{action.action_id}:probe",
            step=step,
            kind="service_probe",
            success=probe.live,
            summary=f"probe {target}: {'live' if probe.live else 'not_live'}",
            state_change=_delta_has_concrete_workspace_change(state_delta),
            failure_class="" if probe.live else "service_not_ready",
            payload={
                "target": probe.target,
                "service_name": probe.service_name or target,
                "live": probe.live,
                "detail": probe.detail,
                "process_id": probe.process_id,
                "process_generation": probe.process_generation,
                "process_generation_verified": probe.process_generation_verified,
                "endpoint_owner_pids": list(probe.endpoint_owner_pids),
                "state_delta": state_delta,
                "candidate_id": action.candidate_id,
            },
        )

    def probe_job(
        self,
        action: ActionRequest,
        step: int,
        executor: Executor,
    ) -> Receipt:
        target = str(action.arguments.get("target", "")).strip()
        probe = executor.probe_job(target)
        state_delta = _observe_process_workspace_state(
            executor, probe.process_id or target
        )
        return Receipt(
            receipt_id=f"step-{step}:{action.action_id}:job_probe",
            step=step,
            kind="job_probe",
            success=probe.found,
            summary=f"probe job {target}: {probe.status}",
            state_change=_delta_has_concrete_workspace_change(state_delta),
            failure_class="" if probe.found else "job_not_found",
            payload={
                "target": probe.target,
                "job_id": probe.job_id,
                "process_id": probe.process_id,
                "job_status": probe.status,
                "completed": probe.completed,
                "job_succeeded": probe.succeeded,
                "exit_code": probe.exit_code,
                "detail": probe.detail,
                "process_generation": probe.process_generation,
                "process_generation_verified": probe.process_generation_verified,
                "lifecycle_authority": probe.lifecycle_authority,
                "pid": probe.pid,
                "state_delta": state_delta,
                "candidate_id": action.candidate_id,
            },
        )

    def stop(
        self,
        action: ActionRequest,
        step: int,
        executor: Executor,
    ) -> Receipt:
        target = str(action.arguments.get("target", "")).strip()
        stopped = executor.stop_process(target)
        state_delta = _observe_process_workspace_state(executor, target)
        relevance, relevance_reason, replacement_job_id = declared_job_relevance(
            action.arguments
        )
        disposition = {
            "job_relevance": relevance,
            "job_relevance_source": "model_declared",
            "job_relevance_reason": relevance_reason,
            "replacement_job_id": replacement_job_id,
        } if relevance is not None else {}
        return Receipt(
            receipt_id=f"step-{step}:{action.action_id}:stop",
            step=step,
            kind="process_stop",
            success=stopped,
            summary=f"stop {target}: {'ok' if stopped else 'not_found'}",
            # Stopping a process updates lifecycle custody, but it advances the
            # task-state generation only when the process observation reports a
            # concrete workspace change or an unknown boundary.  The dispatch
            # layer adds the latter's coarse marker; a complete unchanged
            # observation is lifecycle-only housekeeping.
            state_change=_delta_has_concrete_workspace_change(state_delta),
            failure_class="" if stopped else "service_not_ready",
            payload={
                "process_id": target,
                "service_name": target,
                "live": False,
                **disposition,
                "state_delta": state_delta,
                "candidate_id": action.candidate_id,
            },
        )


class PerceptionLane:
    def inspect(
        self,
        action: ActionRequest,
        step: int,
        executor: Executor,
        *,
        workspace_root: str,
    ) -> Receipt:
        requested_path = str(action.arguments.get("path", "")).strip()
        mode = str(action.arguments.get("mode", "")).strip()
        try:
            path = normalize_relpath(requested_path, workspace_root)
            inspection = executor.inspect_artifact(path, mode)
        except ValueError as exc:
            # Relative workspace escapes are rejected locally.  An absolute
            # task-container path gets one explicit backend-owned opportunity to
            # prove namespace mapping/staging; there is no host-path fallback.
            if not requested_path.startswith("/"):
                inspection = ArtifactInspection(
                    path=requested_path,
                    mode=mode,
                    success=False,
                    detail=f"artifact path rejected before inspection: {exc}",
                    outcome="rejected_before_execution",
                    reason_code="artifact_path_rejected",
                    execution="not_started",
                    recovery_operations=("resubmit_with_a_workspace_relative_path",),
                )
            else:
                inspect_task_artifact = getattr(executor, "inspect_task_artifact", None)
                if not callable(inspect_task_artifact):
                    inspection = ArtifactInspection(
                        path=requested_path,
                        mode=mode,
                        success=False,
                        detail=(
                            "task-container artifact route unavailable: this executor "
                            "does not expose explicit path staging"
                        ),
                        outcome="unavailable",
                        reason_code="task_container_artifact_route_unavailable",
                        execution="not_started",
                        recovery_operations=(
                            "use_a_workspace_relative_artifact_path",
                            "use_an_executor_declared_task_container_route",
                        ),
                    )
                else:
                    try:
                        inspection = inspect_task_artifact(requested_path, mode)
                    except Exception as task_exc:  # noqa: BLE001 - boundary is explicit
                        inspection = ArtifactInspection(
                            path=requested_path,
                            mode=mode,
                            success=False,
                            detail=(
                                f"task-container artifact inspection failed: "
                                f"{type(task_exc).__name__}: {task_exc}"
                            ),
                            outcome="unknown",
                            reason_code="task_container_artifact_inspection_unknown",
                            execution="unknown",
                            recovery_operations=(
                                "reconcile_the_artifact_by_identity_before_retry",
                            ),
                            replay_safe=False,
                        )
        except Exception as exc:  # noqa: BLE001 - convert executor failure to a receipt
            inspection = ArtifactInspection(
                path=requested_path,
                mode=mode,
                success=False,
                detail=f"artifact inspection failed: {type(exc).__name__}: {exc}",
                outcome="failed",
                reason_code="artifact_inspection_failed",
                execution="unknown",
                recovery_operations=("inspect_the_reported_failure_before_retry",),
                replay_safe=False,
            )

        path = str(inspection.path or requested_path).strip()
        try:
            visible_path = normalize_relpath(path, workspace_root)
        except ValueError:
            if inspection.success:
                inspection = ArtifactInspection(
                    path=path,
                    mode=mode,
                    success=False,
                    detail=(
                        "executor returned a successful artifact without a declared "
                        "workspace staging path"
                    ),
                    outcome="failed",
                    reason_code="artifact_staging_contract_invalid",
                    execution="exited",
                    recovery_operations=(
                        "use_a_backend_declared_workspace_staging_path",
                    ),
                    replay_safe=False,
                )
            visible_path = path
        payload = dict(inspection.metadata)
        artifact_identity = dict(payload.get("artifact_identity", {}) or {})
        artifact_handle = str(payload.get("artifact_handle", "") or "")
        if not artifact_handle:
            artifact_handle = str(artifact_identity.get("handle", "") or "")
        detail = str(inspection.detail or f"inspect {visible_path}")[:1000]
        receipt_id = f"step-{step}:{action.action_id}:inspect"
        observed_state: dict[str, Any] = {}
        if artifact_identity:
            observed_state["artifact_identity"] = artifact_identity
        staged_path = str(payload.get("staged_path", "") or "").strip()
        if staged_path:
            observed_state["staged_path"] = staged_path
        output_refs = [artifact_handle] if artifact_handle else []
        return Receipt(
            receipt_id=receipt_id,
            step=step,
            kind="artifact_inspection",
            success=inspection.success,
            summary=detail,
            state_change=False,
            failure_class=(
                ""
                if inspection.success
                else (
                    "perception_required"
                    if inspection.reason_code == "semantic_content_unavailable"
                    else inspection.reason_code
                )
            ),
            payload={
                "action_id": action.action_id,
                "requested": {
                    "tool": "inspect_artifact",
                    "arguments": {"path": requested_path[:1000], "mode": mode[:100]},
                },
                "outcome": inspection.outcome,
                "reason_code": inspection.reason_code,
                "detail": detail,
                "execution": inspection.execution,
                "observed_state": observed_state,
                "output_refs": output_refs,
                "recovery_operations": list(inspection.recovery_operations),
                "replay_safe": bool(inspection.replay_safe),
                "requested_path": requested_path,
                "path": visible_path,
                "mode": mode,
                "artifact_paths": (visible_path,) if inspection.success else (),
                "extracted_text": inspection.extracted_text,
                "metadata": payload,
                "artifact_handle": artifact_handle,
                "artifact_identity": artifact_identity,
                "candidate_id": action.candidate_id,
            },
        )


class ExperimentEngine:
    _METRIC_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_-]*)\s*[:=]\s*(-?\d+(?:\.\d+)?)")

    def run(
        self,
        action: ActionRequest,
        step: int,
        executor: Executor,
        *,
        workspace_root: str,
    ) -> Receipt:
        command = str(action.arguments.get("command", "")).strip()
        metric_name = str(action.arguments.get("metric_name", "")).strip()
        result = run_stateful_command(executor, command, cwd=workspace_root)

        metric_value = None
        if metric_name and metric_name in result.metrics:
            metric_value = result.metrics[metric_name]
        elif metric_name:
            metric_value = self._parse_metric(metric_name, result.stdout + "\n" + result.stderr)

        return Receipt(
            receipt_id=f"step-{step}:{action.action_id}:experiment",
            step=step,
            kind="experiment",
            success=result.success,
            summary=f"experiment {action.candidate_id}: exit={result.exit_code}",
            state_change=bool(
                result.success
                or result.modified_paths
                or result.produced_artifacts
                or result.removed_paths
            ),
            failure_class="" if result.success else "command_failure",
            payload={
                "candidate_id": action.arguments.get("candidate_id", action.candidate_id),
                "candidate_summary": action.arguments.get("summary", action.candidate_id),
                "command": command,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "metric_name": metric_name,
                "metric_value": metric_value,
                "modified_paths": tuple(normalize_relpath(path, workspace_root) for path in result.modified_paths),
                "artifact_paths": tuple(normalize_relpath(path, workspace_root) for path in result.produced_artifacts),
                "removed_paths": tuple(normalize_relpath(path, workspace_root) for path in result.removed_paths),
                "state_delta": dict(result.state_delta),
            },
        )

    def _parse_metric(self, metric_name: str, text: str) -> float | None:
        for match in self._METRIC_RE.finditer(text):
            if match.group(1) == metric_name:
                try:
                    return float(match.group(2))
                except ValueError:
                    return None
        return None


class MemoryExecutor:
    def __init__(
        self,
        *,
        workspace_root: str = "/app",
        files: Mapping[str, str] | None = None,
        refresh_hook: Callable[[EnvMap, "MemoryExecutor"], EnvMap] | None = None,
    ) -> None:
        self.workspace_root = workspace_root
        self.files: dict[str, str] = {
            normalize_relpath(path, workspace_root): content
            for path, content in (files or {}).items()
        }
        self.command_handlers: dict[str, Callable[["MemoryExecutor", str], CommandResult]] = {}
        self.launch_handlers: dict[str, Callable[["MemoryExecutor", str, str, bool], ProcessHandle]] = {}
        self.inspect_handlers: dict[str, Callable[["MemoryExecutor", str, str], ArtifactInspection]] = {}
        self.computer_handler: Callable[["MemoryExecutor", Mapping[str, Any]], ComputerActionResult] | None = None
        self.computer_history: list[dict[str, Any]] = []
        self.processes: dict[str, ProcessHandle] = {}
        self.command_history: list[str] = []
        self.refresh_hook = refresh_hook

    def register_command(self, command: str, handler: Callable[["MemoryExecutor", str], CommandResult]) -> None:
        self.command_handlers[command] = handler

    def register_launch(
        self,
        key: str,
        handler: Callable[["MemoryExecutor", str, str, bool], ProcessHandle],
    ) -> None:
        self.launch_handlers[key] = handler

    def register_inspector(
        self,
        path: str,
        handler: Callable[["MemoryExecutor", str, str], ArtifactInspection],
    ) -> None:
        self.inspect_handlers[normalize_relpath(path, self.workspace_root)] = handler

    def register_computer(
        self, handler: Callable[["MemoryExecutor", Mapping[str, Any]], ComputerActionResult]
    ) -> None:
        self.computer_handler = handler

    def computer_available(self) -> bool:
        return self.computer_handler is not None

    def computer_action(self, action: Mapping[str, Any]) -> ComputerActionResult:
        row = dict(action or {})
        self.computer_history.append(row)
        if self.computer_handler is None:
            return ComputerActionResult(row, False, b"", detail="computer backend unavailable")
        return self.computer_handler(self, row)

    def read_file(self, path: str) -> str:
        normalized = normalize_relpath(path, self.workspace_root)
        if normalized not in self.files:
            raise FileNotFoundError(normalized)
        return self.files[normalized]

    def write_file(self, path: str, content: str) -> None:
        normalized = normalize_relpath(path, self.workspace_root)
        self.files[normalized] = content

    def run_command(self, command: str, *, cwd: str | None = None, timeout_s: int = 30) -> CommandResult:
        del cwd, timeout_s
        self.command_history.append(command)
        handler = self.command_handlers.get(command)
        if handler is None:
            return CommandResult(
                command=command,
                exit_code=127,
                stderr=f"{command}: command not found",
            )
        return handler(self, command)

    def launch_process(
        self,
        name: str,
        command: str,
        *,
        interactive: bool = False,
        cwd: str | None = None,
    ) -> ProcessHandle:
        del cwd
        handler = self.launch_handlers.get(command) or self.launch_handlers.get(name)
        if handler is not None:
            handle = handler(self, name, command, interactive)
        else:
            ordinal = len(self.processes) + 1
            pid = 10_000 + ordinal
            start_ticks = str(ordinal)
            command_sha256 = hashlib.sha256(command.encode("utf-8")).hexdigest()
            generation = hashlib.sha256(
                f"memory\0{pid}\0{start_ticks}\0{command_sha256}".encode("utf-8")
            ).hexdigest()[:24]
            process_id = f"process:{generation}"
            handle = ProcessHandle(
                process_id=process_id,
                name=name,
                command=command,
                interactive=interactive,
                live=True,
                endpoint=f"local://{name}",
                detail="started",
                pid=pid,
                start_time_ticks=start_ticks,
                command_sha256=command_sha256,
                process_generation=generation,
                status="running",
            )
        # A new generation supersedes earlier generations with the same name.
        for existing_id, existing in tuple(self.processes.items()):
            if existing.name == handle.name and existing.live:
                self.processes[existing_id] = replace(existing, live=False, detail="superseded")
        self.processes[handle.process_id] = handle
        return handle

    def _registered_process(self, target: str) -> ProcessHandle | None:
        direct = self.processes.get(target)
        if direct is not None:
            return direct
        matches = [handle for handle in self.processes.values() if handle.name == target]
        return matches[-1] if matches else None

    def probe_process(self, target: str) -> ProbeResult:
        handle = self._registered_process(target)
        if handle is None:
            return ProbeResult(target=target, live=False, detail="not found", service_name=target)
        return ProbeResult(
            target=target,
            live=handle.live,
            detail=handle.detail or ("live" if handle.live else "dead"),
            service_name=handle.name,
            process_id=handle.process_id,
            process_generation=handle.process_generation,
            process_generation_verified=bool(handle.live and handle.process_generation),
            endpoint_owner_pids=((handle.pid,) if handle.pid is not None else ()),
        )

    def probe_job(self, target: str) -> JobProbeResult:
        handle = self._registered_process(target)
        if handle is None:
            return JobProbeResult(
                target=target, found=False, status="unknown", completed=False,
                detail="no registered job generation",
            )
        status = handle.status or ("running" if handle.live else "unknown")
        completed = status in {"completed", "failed"}
        succeeded = True if status == "completed" else (False if status == "failed" else None)
        return JobProbeResult(
            target=target, found=True, status=status, completed=completed,
            succeeded=succeeded, exit_code=handle.exit_code,
            detail=handle.detail or status, job_id=handle.process_id,
            process_id=handle.process_id, process_generation=handle.process_generation,
            process_generation_verified=bool(handle.process_generation),
            lifecycle_authority="in_memory_registered_generation", pid=handle.pid,
        )

    def job_output(self, target: str, *, tail_lines: int = 40) -> dict[str, str]:
        handle = self._registered_process(target)
        output = getattr(handle, "output", None) if handle is not None else None
        if isinstance(output, Mapping):
            count = max(1, min(200, int(tail_lines)))
            return {
                key: "\n".join(str(output.get(key, "")).splitlines()[-count:])
                for key in ("stdout", "stderr")
            }
        return {"stdout": "", "stderr": ""}

    def stop_process(self, target: str) -> bool:
        handle = self._registered_process(target)
        if handle is None:
            return False
        self.processes[handle.process_id] = ProcessHandle(
            process_id=handle.process_id,
            name=handle.name,
            command=handle.command,
            interactive=handle.interactive,
            live=False,
            endpoint=handle.endpoint,
            detail="stopped",
            pid=handle.pid,
            start_time_ticks=handle.start_time_ticks,
            command_sha256=handle.command_sha256,
            process_generation=handle.process_generation,
            stdout_log=handle.stdout_log,
            stderr_log=handle.stderr_log,
            status_log=handle.status_log,
            status="failed",
            exit_code=handle.exit_code,
        )
        return True

    def inspect_artifact(self, path: str, mode: str) -> ArtifactInspection:
        normalized = normalize_relpath(path, self.workspace_root)
        handler = self.inspect_handlers.get(normalized)
        if handler is not None:
            return handler(self, normalized, mode)
        if normalized not in self.files:
            return ArtifactInspection(
                path=normalized,
                mode=mode,
                success=False,
                detail="missing artifact",
            )
        return ArtifactInspection(
            path=normalized,
            mode=mode,
            success=True,
            extracted_text=self.files[normalized],
            metadata={"length": len(self.files[normalized])},
            detail=f"inspected {normalized}",
        )

    def refresh_envmap(self, envmap: EnvMap) -> EnvMap:
        if self.refresh_hook is None:
            return envmap
        return self.refresh_hook(envmap, self)

    def exists(self, path: str) -> bool:
        normalized = normalize_relpath(path, self.workspace_root)
        return normalized in self.files

    def glob(self, pattern: str) -> tuple[str, ...]:
        normalized = normalize_relpath(pattern, self.workspace_root)
        matches = sorted(path for path in self.files if fnmatch.fnmatch(path, normalized))
        return tuple(matches)
