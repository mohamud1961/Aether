"""ExecutionContext, ToolInvocationRecord, and RunResult for the Aether-2 control loop.

Pure extraction from loop.py — zero behaviour change. Public API re-exported
from loop.py so existing imports are unaffected.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from harness.aether2.hooks.registry import HookRegistry
from harness.aether2.runtime.executor import ContainerExecutor
from harness.aether2.runtime.jobs import JobRegistry
from harness.aether2.runtime.sessions import SessionRegistry
from harness.aether2.traces.delta import (
    StateSnapshot,
    diff as delta_diff,
    snapshot as delta_snapshot,
)
from harness.aether2.traces.envelope import ObservationEnvelope, build_envelope
from harness.aether2.traces.envelope import FileDelta as EnvelopeFileDelta
from harness.aether2.traces.envelope import ProcessDelta
from harness.aether2.traces.mirror import MirrorNote
from harness.aether2.tools.permissions import PermissionManager
from harness.aether2.tools.registry import ToolRegistry, build_native_tool_registry
from harness.aether2.traces.receipts import _redact_text

from harness.aether2.control.action_helpers import _error_raw
from harness.aether2.control.pkg_detect import _is_package_manager_install

__all__ = [
    "ExecutionContext",
    "RunResult",
    "ToolInvocationRecord",
]


@dataclass(frozen=True)
class ToolInvocationRecord:
    """One dispatched tool call, its arguments, and the resulting envelope."""

    step: int
    tool_name: str
    arguments: dict[str, Any]
    envelope: ObservationEnvelope
    permission_decision: dict[str, Any] | None = None
    hook_trace: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class RunResult:
    """The outcome of one continuity-loop run, carrying everything the scorecard needs."""

    verifier_clean: bool
    finalize_reason: str
    summary: str
    steps: int
    model_calls: int
    tokens_cached: int
    tokens_fresh: int
    cost: float
    wall_time: float
    no_delta_streaks: int
    verification_rounds: int
    suppressed_verifier_calls: int
    completion_precheck_rejections: int
    recoveries: int
    compaction_count: int
    job_survival: bool
    session_survival: bool
    grader_reward: float | None = None
    reasoning_trace_ref: str | None = None
    tool_invocations: list[ToolInvocationRecord] = field(default_factory=list)
    mirror_notes: list[MirrorNote] = field(default_factory=list)
    discrepancy_reports: list[Any] = field(default_factory=list)

    @property
    def pass_(self) -> bool:
        """Deprecated alias for `verifier_clean` (advisory verifier signal, not grader authority)."""
        return self.verifier_clean


class ExecutionContext:
    """Adapts the container executor, job registry, and session registry to the dispatch surface."""

    def __init__(
        self,
        *,
        executor: ContainerExecutor,
        job_registry: JobRegistry,
        session_registry: SessionRegistry,
        raw_log_dir: Path,
        hook_registry: HookRegistry | None = None,
        permission_manager: PermissionManager | None = None,
        tool_registry: ToolRegistry | None = None,
    ) -> None:
        self.executor = executor
        self.job_registry = job_registry
        self.session_registry = session_registry
        self.raw_log_dir = raw_log_dir
        self.hook_registry = hook_registry or HookRegistry()
        self.permission_manager = permission_manager or PermissionManager()
        self.tool_registry = tool_registry or build_native_tool_registry()
        self.workspace_root = executor.workspace_root
        self.last_snapshot: StateSnapshot = delta_snapshot(self.workspace_root)
        self.last_delta_report = delta_diff(self.last_snapshot, self.last_snapshot)
        # Cumulative run-level facts for the §6.5 fact ledger (not derivable from
        # a single filesystem snapshot).
        self.installed_packages: list[str] = []
        self.nonzero_exits: list[dict[str, Any]] = []
        # In-run tool invocation records exposed to query_history.
        self._run_tool_invocations: list["ToolInvocationRecord"] = []

    def run_command(self, cmd: str, timeout_sec: int = 120, cwd: str | None = None) -> ObservationEnvelope:
        raw = self.executor.run(cmd, timeout_sec=timeout_sec, cwd=cwd)
        exit_code = getattr(raw, "exit_code", None)
        if exit_code == 0 and _is_package_manager_install(cmd):
            self.installed_packages.append(cmd)
        elif exit_code is not None and exit_code != 0:
            self.nonzero_exits.append({"command": cmd, "exit_code": exit_code, "stderr": (getattr(raw, "stderr", "") or "")[-2048:]})
        return self._observe_raw(raw)

    def start_job(self, cmd: str, job_id: str | None = None, cwd: str | None = None) -> ObservationEnvelope:
        started_at = time.monotonic()
        try:
            resolved_job_id = self.job_registry.start(cmd, job_id=job_id, cwd=cwd)
            status = self.job_registry.status(resolved_job_id)
            raw = {
                "tool": "start_job",
                "exit_code": 0,
                "duration_sec": time.monotonic() - started_at,
                "cwd": status.cwd,
                "stdout": f"started job {resolved_job_id} (pid {status.pid})",
                "stderr": "",
            }
        except Exception as exc:  # noqa: BLE001 - surfaced as a truthful error envelope
            raw = _error_raw("start_job", exc, started_at=started_at, cwd=str(self.executor.workspace_root))
        return self._observe_raw(raw)

    def job_status(self, job_id: str) -> ObservationEnvelope:
        started_at = time.monotonic()
        try:
            status = self.job_registry.status(job_id)
            raw = {
                "tool": "job_status",
                "exit_code": status.exit_code if status.exit_code is not None else (0 if status.alive else None),
                "duration_sec": time.monotonic() - started_at,
                "cwd": status.cwd,
                "stdout": (
                    f"job {job_id}: alive={status.alive} exit_code={status.exit_code}\n--- log tail ---\n{status.tail}"
                ),
                "stderr": "",
            }
        except Exception as exc:  # noqa: BLE001
            raw = _error_raw("job_status", exc, started_at=started_at, cwd=str(self.executor.workspace_root))
        return self._observe_raw(raw)

    def session_start(self, session_id: str, command: str) -> ObservationEnvelope:
        started_at = time.monotonic()
        try:
            self.session_registry.start(session_id, command)
            raw = {
                "tool": "session_start",
                "exit_code": 0,
                "duration_sec": time.monotonic() - started_at,
                "cwd": str(self.executor.workspace_root),
                "stdout": f"started session {session_id}",
                "stderr": "",
            }
        except Exception as exc:  # noqa: BLE001
            raw = _error_raw("session_start", exc, started_at=started_at, cwd=str(self.executor.workspace_root))
        return self._observe_raw(raw)

    def session_send(self, session_id: str, keys: str) -> ObservationEnvelope:
        started_at = time.monotonic()
        try:
            self.session_registry.send(session_id, keys)
            raw = {
                "tool": "session_send",
                "exit_code": 0,
                "duration_sec": time.monotonic() - started_at,
                "cwd": str(self.executor.workspace_root),
                "stdout": f"sent keys to session {session_id}",
                "stderr": "",
            }
        except Exception as exc:  # noqa: BLE001
            raw = _error_raw("session_send", exc, started_at=started_at, cwd=str(self.executor.workspace_root))
        return self._observe_raw(raw)

    def session_read(self, session_id: str) -> ObservationEnvelope:
        started_at = time.monotonic()
        try:
            screen = self.session_registry.read(session_id)
            raw = {
                "tool": "session_read",
                "exit_code": None,
                "duration_sec": time.monotonic() - started_at,
                "cwd": str(self.executor.workspace_root),
                "stdout": screen,
                "stderr": "",
            }
        except Exception as exc:  # noqa: BLE001
            raw = _error_raw("session_read", exc, started_at=started_at, cwd=str(self.executor.workspace_root))
        return self._observe_raw(raw)

    def read_file(self, path: str, offset: int | None = None, limit: int | None = None) -> ObservationEnvelope:
        started_at = time.monotonic()
        try:
            target = self.executor.resolve_workspace_path(path)
            text = target.read_text(encoding="utf-8", errors="replace")
            lines = text.splitlines(keepends=True)
            start = offset or 0
            if limit is not None:
                selected = lines[start : start + limit]
            else:
                selected = lines[start:]
            content = "".join(selected)
            truncated_note = ""
            if start > 0 or (limit is not None and start + limit < len(lines)):
                truncated_note = f"\n...[showing lines {start}:{start + len(selected)} of {len(lines)}]"
            raw = {
                "tool": "read_file",
                "exit_code": 0,
                "duration_sec": time.monotonic() - started_at,
                "cwd": str(self.executor.workspace_root),
                "stdout": content + truncated_note,
                "stderr": "",
            }
        except ValueError as exc:
            raw = _error_raw(
                "read_file",
                exc,
                started_at=started_at,
                cwd=str(self.executor.workspace_root),
                kind="workspace_boundary_violation",
            )
        except FileNotFoundError as exc:
            raw = _error_raw("read_file", exc, started_at=started_at, cwd=str(self.executor.workspace_root), kind="file_not_found")
        except OSError as exc:
            raw = _error_raw("read_file", exc, started_at=started_at, cwd=str(self.executor.workspace_root), kind="io_error")
        return self._observe_raw(raw)

    def write_file(self, path: str, content: str) -> ObservationEnvelope:
        started_at = time.monotonic()
        try:
            target = self.executor.resolve_workspace_path(path)
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = target.with_name(target.name + ".aether2_tmp")
            tmp_path.write_text(content, encoding="utf-8")
            tmp_path.replace(target)
            raw = {
                "tool": "write_file",
                "exit_code": 0,
                "duration_sec": time.monotonic() - started_at,
                "cwd": str(self.executor.workspace_root),
                "stdout": f"wrote {len(content)} bytes to {path}",
                "stderr": "",
            }
        except ValueError as exc:
            raw = _error_raw(
                "write_file",
                exc,
                started_at=started_at,
                cwd=str(self.executor.workspace_root),
                kind="workspace_boundary_violation",
            )
        except OSError as exc:
            raw = _error_raw("write_file", exc, started_at=started_at, cwd=str(self.executor.workspace_root), kind="io_error")
        return self._observe_raw(raw)

    def wait(self, seconds: int, reason: str) -> ObservationEnvelope:
        started_at = time.monotonic()
        bounded_seconds = max(0, min(int(seconds), 300))
        time.sleep(bounded_seconds)
        raw = {
            "tool": "wait",
            "exit_code": 0,
            "duration_sec": time.monotonic() - started_at,
            "cwd": str(self.executor.workspace_root),
            "stdout": f"waited {bounded_seconds}s ({reason})",
            "stderr": "",
        }
        return self._observe_raw(raw)

    def task_done(self, summary: str, checks: list[str]) -> ObservationEnvelope:
        raw = {
            "tool": "task_done",
            "exit_code": 0,
            "duration_sec": 0.0,
            "cwd": str(self.executor.workspace_root),
            "stdout": summary,
            "stderr": "",
        }
        return self._observe_raw(raw)

    def observe_synthetic(self, raw: Mapping[str, Any]) -> ObservationEnvelope:
        return self._observe_raw(raw)

    def query_history(self, query: str, tool: str | None = None, limit: int = 10) -> ObservationEnvelope:
        """Search prior tool invocations from this run by keyword/substring."""
        import time as _time
        started_at = _time.monotonic()

        _SNIPPET_LEN = 300
        _ARGS_SUMMARY_LEN = 120
        _TOTAL_OUTPUT_BUDGET = 8000

        query_lower = query.lower().strip()
        limit = max(1, min(int(limit), 50))

        matches: list[dict[str, Any]] = []
        for record in reversed(self._run_tool_invocations):
            # Skip query_history invocations to prevent noise loops.
            if record.tool_name == "query_history":
                continue
            # Apply optional tool-name filter.
            if tool is not None and record.tool_name != tool:
                continue

            # Build a searchable text blob from the record's tool name, args, and output.
            args_text = json.dumps(record.arguments, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
            stdout_text = (record.envelope.stdout_head or "") + (record.envelope.stdout_tail or "")
            stderr_text = (record.envelope.stderr_head or "") + (record.envelope.stderr_tail or "")
            haystack = " ".join([record.tool_name, args_text, stdout_text, stderr_text]).lower()

            if query_lower and query_lower not in haystack:
                continue

            # Build a compact, redacted entry.
            args_summary = _redact_text(args_text)
            if len(args_summary) > _ARGS_SUMMARY_LEN:
                args_summary = args_summary[:_ARGS_SUMMARY_LEN] + "..."
            output_snippet = _redact_text((stdout_text + stderr_text).strip())
            if len(output_snippet) > _SNIPPET_LEN:
                output_snippet = output_snippet[:_SNIPPET_LEN] + "..."
            matches.append(
                {
                    "step": record.step,
                    "tool": record.tool_name,
                    "args_summary": args_summary,
                    "output_snippet": output_snippet,
                    "exit_code": record.envelope.exit_code,
                }
            )
            if len(matches) >= limit:
                break

        if not matches:
            result_text = f"no matching history for query={query!r}"
            if tool is not None:
                result_text += f" tool={tool!r}"
        else:
            parts = [f"query_history: {len(matches)} result(s) for {query!r}"]
            total = len(parts[0])
            for entry in matches:
                line = json.dumps(entry, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
                if total + len(line) > _TOTAL_OUTPUT_BUDGET:
                    parts.append("...[output budget reached]")
                    break
                parts.append(line)
                total += len(line)
            result_text = "\n".join(parts)

        raw = {
            "tool": "query_history",
            "exit_code": 0,
            "duration_sec": _time.monotonic() - started_at,
            "cwd": str(self.executor.workspace_root),
            "stdout": result_text,
            "stderr": "",
        }
        return self._observe_raw(raw)

    def _observe_raw(self, raw: Any) -> ObservationEnvelope:
        current_snapshot = delta_snapshot(self.workspace_root)
        delta_report = delta_diff(self.last_snapshot, current_snapshot)
        raw_payload = dict(raw) if isinstance(raw, Mapping) else raw.__dict__.copy()
        raw_payload["files_changed"] = [
            EnvelopeFileDelta(
                path=item.path,
                hash_before=item.hash_before,
                hash_after=item.hash_after,
                change_type=item.change_type,
            )
            for item in delta_report.files_changed
        ]
        raw_payload["process_delta"] = self._build_process_delta(self.last_snapshot, current_snapshot)
        envelope = build_envelope(raw_payload, raw_log_dir=self.raw_log_dir)
        self.last_snapshot = current_snapshot
        self.last_delta_report = delta_report
        return envelope

    def _build_process_delta(self, prev: StateSnapshot, curr: StateSnapshot) -> ProcessDelta:
        process_delta = ProcessDelta()

        prev_jobs = prev.job_registry
        curr_jobs = curr.job_registry
        prev_sessions = prev.session_registry
        curr_sessions = curr.session_registry
        prev_services = prev.service_registry
        curr_services = curr.service_registry
        prev_processes = prev.process_registry
        curr_processes = curr.process_registry

        for job_id in sorted(set(prev_jobs) | set(curr_jobs)):
            before = prev_jobs.get(job_id)
            after = curr_jobs.get(job_id)
            if before is None and after is not None:
                process_delta.jobs_started.append(job_id)
            elif before is not None and after is None:
                process_delta.jobs_exited.append(job_id)
            elif before is not None and after is not None:
                if bool(before.get("alive")) and not bool(after.get("alive")):
                    process_delta.jobs_exited.append(job_id)
                growth = int(after.get("log_size", 0)) - int(before.get("log_size", 0))
                if growth > 0:
                    process_delta.job_log_growth[job_id] = growth

        for session_id in sorted(set(prev_sessions) | set(curr_sessions)):
            before = prev_sessions.get(session_id)
            after = curr_sessions.get(session_id)
            if before is None and after is not None:
                process_delta.sessions_started.append(session_id)
            elif before is not None and after is None:
                process_delta.sessions_exited.append(session_id)

        for service_id in sorted(set(prev_services) | set(curr_services)):
            before = prev_services.get(service_id)
            after = curr_services.get(service_id)
            if before is None and after is not None:
                process_delta.services_started.append(service_id)
            elif before is not None and after is None:
                process_delta.services_exited.append(service_id)

        for process_id in sorted(set(prev_processes) | set(curr_processes)):
            before = prev_processes.get(process_id)
            after = curr_processes.get(process_id)
            if before is None and after is not None:
                process_delta.started.append(process_id)
            elif before is not None and after is None:
                process_delta.exited.append(process_id)

        return process_delta
