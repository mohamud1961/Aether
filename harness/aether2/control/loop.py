"""Continuous executor loop composing tools, context, mirror, and verification into one run."""

from __future__ import annotations

from dataclasses import dataclass, field, replace as dataclass_replace
from pathlib import Path
from typing import Any, Mapping
import hashlib
import json
import re
import shlex
import time

from harness.aether2.runtime.bridge_harbor import TaskSpec
from harness.aether2.runtime.compactor import rebase, should_rebase
from harness.aether2.runtime.context import ContextManager
from harness.aether2.hooks.registry import HookRegistry
from harness.aether2.traces.delta import (
    StateSnapshot,
    build_evidence_ledger,
    diff as delta_diff,
    ensure_stated_requirements,
    mark_blockers_candidate_resolved,
    mark_blockers_exhausted,
    record_check_results,
    record_observation_evidence,
    record_terminal_claim,
    record_verifier_report,
    should_suppress_verifier_call,
    snapshot as delta_snapshot,
    with_evidence_ledger,
)
from harness.aether2.traces.envelope import ObservationEnvelope, build_envelope
from harness.aether2.traces.envelope import FileDelta as EnvelopeFileDelta
from harness.aether2.traces.envelope import ProcessDelta
from harness.aether2.runtime.executor import ContainerExecutor
from harness.aether2.runtime.jobs import JobRegistry
from harness.aether2.traces.mirror import Mirror, MirrorNote, SemanticObservation
from harness.aether2.runtime.orientation import orient
from harness.aether2.runtime.prompts import (
    COMPLETION_REMINDER_INTRO,
    STRATEGY_RESET_REMINDER,
    SYSTEM_PROMPT,
    TASK_DONE_REMINDER,
)
from harness.aether2.traces.receipts import ReceiptWriter, _redact_text
from harness.aether2.runtime.sessions import SessionRegistry
from harness.aether2.tools.permissions import PermissionManager
from harness.aether2.tools.registry import ToolRegistry, build_native_tool_registry
from harness.aether2.runtime.verify import DiscrepancyReport, RequirementResult, replay_checks, verify_fresh_context
from harness.aether2.traces.redaction import _clean_hidden_refs


STEP_CAP = 120
MAX_VERIFICATION_ROUNDS = 3
CONTEXT_WINDOW_TOKENS = 128_000
_REQUIREMENT_PREVIEW_LIMIT = 4
_WEAK_EVIDENCE_STRENGTHS = {"none", "weak"}
_SERVICE_MONITOR_WINDOW_SEC = 2

# Generic package-manager invocations (first 1-2 shell tokens). Used only to
# detect "this run_command was a package install" for the §6.5 fact ledger's
# `installed_packages` entry -- no task-specific package names or logic.
_PACKAGE_MANAGER_PREFIXES: tuple[tuple[str, ...], ...] = (
    ("apt-get", "install"),
    ("apt", "install"),
    ("pip", "install"),
    ("pip3", "install"),
    ("python", "-m", "pip", "install"),
    ("python3", "-m", "pip", "install"),
    ("npm", "install"),
    ("npm", "i"),
    ("yarn", "add"),
    ("cargo", "install"),
    ("gem", "install"),
    ("go", "install"),
    ("brew", "install"),
    ("conda", "install"),
    ("apk", "add"),
    ("dnf", "install"),
    ("yum", "install"),
)


def _is_package_manager_install(command: str) -> bool:
    try:
        tokens = shlex.split(command, posix=True)
    except ValueError:
        return False
    for prefix in _PACKAGE_MANAGER_PREFIXES:
        if tuple(tokens[: len(prefix)]) == prefix:
            return True
    return False


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


def _error_raw(
    tool: str,
    exc: Exception,
    *,
    started_at: float,
    cwd: str,
    kind: str = "runtime_error",
) -> dict[str, Any]:
    return {
        "tool": tool,
        "exit_code": 1,
        "duration_sec": time.monotonic() - started_at,
        "cwd": cwd,
        "stdout": "",
        "stderr": str(exc),
        "error": {
            "kind": kind,
            "message": str(exc),
            "reason_code": kind,
            "tool_name": tool,
        },
    }


def _action_signature(tool_name: str, arguments: Mapping[str, Any]) -> str:
    return f"{tool_name}:" + json.dumps(arguments, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _envelope_failed(envelope: ObservationEnvelope) -> bool:
    if envelope.error is not None:
        return True
    if envelope.exit_code is not None and envelope.exit_code != 0:
        return True
    return False


def _build_blind_retry_blocked_envelope(
    tool_name: str, arguments: Mapping[str, Any], cwd: str, *, raw_log_dir: Path
) -> ObservationEnvelope:
    raw = {
        "tool": tool_name,
        "exit_code": 1,
        "duration_sec": 0.0,
        "cwd": cwd,
        "stdout": "",
        "stderr": "blind_retry_blocked_same_failed_command",
        "blind_retry_blocked": True,
        "error": {
            "kind": "blind_retry_blocked",
            "message": (
                "This exact action just failed and nothing has changed since. "
                "Try something different before repeating it."
            ),
            "reason_code": "blind_retry_blocked_same_failed_command",
            "tool_name": tool_name,
        },
    }
    return build_envelope(raw, raw_log_dir=raw_log_dir)


def _parse_tool_call_arguments(tool_call: Mapping[str, Any]) -> dict[str, Any]:
    arguments = tool_call.get("arguments")
    if isinstance(arguments, Mapping):
        return dict(arguments)
    if isinstance(arguments, str):
        if not arguments.strip():
            return {}
        try:
            parsed = json.loads(arguments)
        except (TypeError, ValueError):
            return {}
        if isinstance(parsed, dict):
            return parsed
    return {}


def _tool_call_name(tool_call: Mapping[str, Any]) -> str | None:
    name = tool_call.get("name")
    if isinstance(name, str) and name:
        return name
    function = tool_call.get("function")
    if isinstance(function, Mapping):
        nested_name = function.get("name")
        if isinstance(nested_name, str) and nested_name:
            return nested_name
    return None


def _envelope_to_message(tool_name: str, tool_call_id: Any, envelope: ObservationEnvelope) -> dict[str, Any]:
    payload = {
        "tool": envelope.tool,
        "exit_code": envelope.exit_code,
        "duration_sec": envelope.duration_sec,
        "cwd": envelope.cwd,
        "stdout_head": envelope.stdout_head,
        "stdout_tail": envelope.stdout_tail,
        "stderr_head": envelope.stderr_head,
        "stderr_tail": envelope.stderr_tail,
        "truncated": envelope.truncated,
        "raw_log_path": envelope.raw_log_path,
        "files_changed": [item.__dict__ for item in envelope.files_changed],
        "process_delta": envelope.process_delta.__dict__,
        "blind_retry_blocked": envelope.blind_retry_blocked,
        "error": None if envelope.error is None else envelope.error.__dict__,
        "truncation_digest": (
            None
            if envelope.truncation_digest is None
            else {
                "raw_log_path": envelope.truncation_digest.raw_log_path,
                "omitted_count": envelope.truncation_digest.omitted_count,
                "entries": [entry.__dict__ for entry in envelope.truncation_digest.entries],
            }
        ),
    }
    return {
        "role": "tool",
        "name": tool_name,
        "tool_call_id": tool_call_id,
        "content": json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True),
    }


# W1.1: requirement extraction stays descriptive and conservative -- the
# verbatim task instruction (`task.instruction` / `context.task_instruction`)
# remains the authoritative contract. This projection only seeds a compact,
# human-scannable requirement list for the evidence ledger and skips
# wrapper/boilerplate lines (pure headings, separators, "thanks"/sign-off
# style lines) so they do not become noisy requirement entries.
_REQUIREMENT_LINE_NOISE_PATTERNS = (
    "thank you",
    "thanks",
    "good luck",
    "please",
)

_WRAPPER_REQUIREMENT_PATTERNS = (
    "current working directory is",
    "writable task workspace",
    "official verifier",
    "hidden verifier",
    "hidden grader",
    "hidden tests",
    "solution.sh",
    "task_done",
    "plan-only diagnostic",
    "plausible file",
    "plausible process",
    "independent verifier",
    "if the task asks for",
    "for qemu/telnet",
    "for vnc/desktop",
    "for media/transcription",
    "for long-running jobs",
    "strong checks",
    "strong enough",
    "receipt-backed evidence",
)


def _is_noise_requirement_line(line: str) -> bool:
    """Conservative filter for wrapper/boilerplate lines.

    Only filters lines that are clearly structural noise: markdown heading
    markers, pure separator/punctuation lines, or very short sign-off style
    lines. Never filters anything that looks like it carries a path, command,
    constraint, or behavioral detail.
    """

    stripped = line.strip()
    if not stripped:
        return True
    # Markdown headings (e.g. "# Task", "## Notes") are structural, not
    # individually actionable requirements.
    if stripped.lstrip("#").strip() != stripped and stripped.startswith("#"):
        return True
    # Pure separator/punctuation lines (e.g. "---", "===", "***").
    if all(char in "-=*_~. " for char in stripped):
        return True
    # Short sign-off/wrapper lines with no path-, command-, or constraint-like
    # content (no slashes, backticks, digits, or quotes) are likely boilerplate.
    lowered = stripped.lower()
    if len(stripped) <= 40 and not any(token in stripped for token in ("/", "`", "\"", "'", ":")) and not any(char.isdigit() for char in stripped):
        if any(phrase in lowered for phrase in _REQUIREMENT_LINE_NOISE_PATTERNS):
            return True
    return False


def _is_harness_wrapper_requirement_line(line: str) -> bool:
    """Return true for wrapper doctrine that should not become task contract.

    These lines describe harness operating policy rather than the user-authored
    success condition. Real task constraints are still preserved
    unless they contain explicit harness-control vocabulary such as task_done,
    hidden grader/verifier files, or generic "if the task asks for..." doctrine.
    """

    lowered = line.lower()
    if "you can run" in lowered and "verify" in lowered:
        return True
    return any(pattern in lowered for pattern in _WRAPPER_REQUIREMENT_PATTERNS)


def _extract_stated_requirements(task_instruction: str) -> list[str]:
    requirements: list[str] = []
    for raw_line in task_instruction.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if _is_noise_requirement_line(line):
            continue
        if line.startswith(("-", "*")):
            requirement = line[1:].strip()
        else:
            digits = []
            for char in line:
                if char.isdigit():
                    digits.append(char)
                    continue
                if char in {".", ")"} and digits:
                    requirement = line[len(digits) + 1 :].strip()
                    break
                requirement = line
                break
            else:
                requirement = line
        if _is_harness_wrapper_requirement_line(requirement):
            continue
        if len(requirement) > 300:
            requirement = requirement[:297].rstrip() + "..."
        if requirement and requirement not in requirements:
            requirements.append(requirement)
    if requirements:
        return requirements
    trimmed = " ".join(task_instruction.split())
    if not trimmed:
        return ["Complete the stated task contract."]
    if len(trimmed) > 300:
        trimmed = trimmed[:297].rstrip() + "..."
    return [trimmed]


def _extract_verifier_task_contract(task_instruction: str) -> str:
    """Compact task contract for fresh-context verification.

    The executor still receives the full task instruction, including any
    harness wrapper. The verifier receives only the requirement projection so
    harness-side doctrine cannot be reinterpreted as success criteria.
    """

    return "\n".join(_extract_stated_requirements(task_instruction))


# W1.1: a generic bucket for tool activity that does not visibly relate to any
# stated requirement (e.g. exploratory commands, environment probes). Keeping
# this separate avoids forcing every observation onto the first unresolved
# requirement, which previously made unrelated activity look like progress on
# that requirement.
UNASSIGNED_ACTIVITY_REQUIREMENT = "unassigned activity (not linked to a stated requirement)"


def _requirement_relevance_tokens(text: str) -> set[str]:
    tokens: set[str] = set()
    for raw_token in re.findall(r"[A-Za-z0-9_./\\-]+", text.lower()):
        token = raw_token.strip("./\\-_")
        if len(token) >= 3:
            tokens.add(token)
        # Path-like tokens: also index the basename and extension.
        if "/" in raw_token or "\\" in raw_token:
            base = raw_token.replace("\\", "/").rsplit("/", 1)[-1]
            base = base.strip("./\\-_")
            if len(base) >= 3:
                tokens.add(base)
    return tokens


def _observation_relevance_tokens(*, tool_name: str, arguments: Mapping[str, Any], artifact_paths: list[str]) -> set[str]:
    tokens: set[str] = set()
    for path in artifact_paths:
        tokens |= _requirement_relevance_tokens(path)
    for key in ("path", "cmd", "session_id", "job_id"):
        raw = arguments.get(key)
        if isinstance(raw, str) and raw.strip():
            tokens |= _requirement_relevance_tokens(raw)
    return tokens


def _relevant_requirement(
    ledger: Mapping[str, Any],
    fallback_requirements: list[str],
    *,
    tool_name: str,
    arguments: Mapping[str, Any],
    artifact_paths: list[str],
) -> str:
    """Pick the requirement an observation visibly relates to.

    Matches on shared path/command/identifier tokens between the observation
    and each requirement's text. Falls back to `UNASSIGNED_ACTIVITY_REQUIREMENT`
    when no stated requirement shares any visible token with the observation,
    instead of always attaching to the first unresolved requirement.
    """

    observation_tokens = _observation_relevance_tokens(
        tool_name=tool_name, arguments=arguments, artifact_paths=artifact_paths
    )
    if observation_tokens:
        for item in _ledger_requirements(ledger):
            requirement_text = _ledger_requirement_text(item)
            if requirement_text == UNASSIGNED_ACTIVITY_REQUIREMENT:
                continue
            if observation_tokens & _requirement_relevance_tokens(requirement_text):
                return requirement_text
    if tool_name == "task_done":
        return _primary_requirement(ledger, fallback_requirements)
    return UNASSIGNED_ACTIVITY_REQUIREMENT


def _current_evidence_ledger(context: ContextManager) -> dict[str, Any]:
    snapshot = context.delta_state
    if snapshot is None:
        return build_evidence_ledger()
    ledger = getattr(snapshot, "evidence_ledger", {}) or {}
    requirements = _extract_stated_requirements(context.task_instruction)
    return ensure_stated_requirements(ledger, requirements)


def _ledger_requirements(ledger: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw_requirements = ledger.get("requirements", [])
    if not isinstance(raw_requirements, list):
        return []
    return [item for item in raw_requirements if isinstance(item, Mapping)]


def _ledger_requirement_text(requirement: Mapping[str, Any]) -> str:
    return str(requirement.get("requirement", "")).strip()


def _primary_requirement(ledger: Mapping[str, Any], fallback_requirements: list[str]) -> str:
    unresolved = _unresolved_requirements(ledger)
    if unresolved:
        return _ledger_requirement_text(unresolved[0])
    requirements = _ledger_requirements(ledger)
    if requirements:
        return _ledger_requirement_text(requirements[0])
    return fallback_requirements[0]


def _unresolved_requirements(ledger: Mapping[str, Any]) -> list[dict[str, Any]]:
    unresolved: list[dict[str, Any]] = []
    for item in _ledger_requirements(ledger):
        if _ledger_requirement_text(item) == UNASSIGNED_ACTIVITY_REQUIREMENT:
            continue
        status = str(item.get("status", "unproven"))
        blockers = item.get("verifier_blockers", []) or []
        next_required = item.get("next_required_evidence", []) or []
        if status != "proven" or blockers or next_required:
            unresolved.append(dict(item))
    return unresolved


def _tail_evidence_ledger(ledger: Mapping[str, Any]) -> dict[str, Any]:
    requirement_rows: list[dict[str, Any]] = []
    for item in _ledger_requirements(ledger)[:_REQUIREMENT_PREVIEW_LIMIT]:
        requirement_rows.append(
            {
                "requirement": _ledger_requirement_text(item),
                "status": str(item.get("status", "unproven")),
                "evidence_strength": str(item.get("evidence_strength", "none")),
                "failed_checks": list(item.get("failed_checks", []) or [])[:2],
                "open_risks": list(item.get("open_risks", []) or [])[:2],
                "verifier_blockers": list(item.get("verifier_blockers", []) or [])[:2],
                "next_required_evidence": list(item.get("next_required_evidence", []) or [])[:2],
            }
        )
    return {
        "requirements": requirement_rows,
        "repeated_failure_families": list(ledger.get("repeated_failure_families", []) or [])[:4],
    }


# W1.2: provenance labels that indicate evidence was generated by the model's
# own artifact/check rather than an independent or externally observable
# source. Used only for a passive, model-visible reflection note -- never to
# veto or rewrite an action.
_SELF_AUTHORED_PROVENANCE_LABELS = {
    "model_authored_artifact",
    "model_authored_check",
    "same_method_check",
}


def _build_completion_contract(task_instruction: str, ledger: Mapping[str, Any]) -> dict[str, Any]:
    unresolved = _unresolved_requirements(ledger)
    weak_evidence: list[str] = []
    next_required: list[str] = []
    blockers: list[str] = []
    for item in unresolved:
        evidence_strength = str(item.get("evidence_strength", "none"))
        requirement = _ledger_requirement_text(item)
        if evidence_strength in _WEAK_EVIDENCE_STRENGTHS and list(item.get("evidence_refs", []) or []):
            weak_evidence.append(f"{requirement}: evidence is only {evidence_strength}")
        for blocker in list(item.get("verifier_blockers", []) or []):
            blockers.append(f"{requirement}: {blocker}")
        for evidence in list(item.get("next_required_evidence", []) or []):
            next_required.append(f"{requirement}: {evidence}")
    contract_text = " ".join(task_instruction.split())
    if len(contract_text) > 280:
        contract_text = contract_text[:277].rstrip() + "..."

    # W1.2: a concise, per-turn evidence question derived from visible state.
    # Passive reflection only -- it states the current unresolved requirement,
    # the strongest missing evidence for it, and (when applicable) that the
    # existing evidence for that requirement was only weak/self-authored.
    current_unresolved_requirement: str | None = None
    strongest_missing_evidence: str | None = None
    current_evidence_is_self_authored_or_weak: bool = False
    if unresolved:
        top = unresolved[0]
        current_unresolved_requirement = _ledger_requirement_text(top)
        top_next_required = list(top.get("next_required_evidence", []) or [])
        if top_next_required:
            strongest_missing_evidence = str(top_next_required[0])
        evidence_strength = str(top.get("evidence_strength", "none"))
        provenance_labels = {str(label) for label in (top.get("evidence_provenance", []) or [])}
        has_evidence = bool(list(top.get("evidence_refs", []) or []))
        if has_evidence and (
            evidence_strength in _WEAK_EVIDENCE_STRENGTHS
            or (provenance_labels and provenance_labels.issubset(_SELF_AUTHORED_PROVENANCE_LABELS))
        ):
            current_evidence_is_self_authored_or_weak = True

    return {
        "intro": COMPLETION_REMINDER_INTRO,
        "stated_task_contract": contract_text,
        "unresolved_requirements": [_ledger_requirement_text(item) for item in unresolved[:_REQUIREMENT_PREVIEW_LIMIT]],
        "verifier_blockers": blockers[:_REQUIREMENT_PREVIEW_LIMIT],
        "weak_evidence": weak_evidence[:_REQUIREMENT_PREVIEW_LIMIT],
        "next_required_evidence": next_required[:_REQUIREMENT_PREVIEW_LIMIT],
        "current_unresolved_requirement": current_unresolved_requirement,
        "strongest_missing_evidence": strongest_missing_evidence,
        "current_evidence_is_self_authored_or_weak": current_evidence_is_self_authored_or_weak,
        "strategy_reset_rule": STRATEGY_RESET_REMINDER,
        "task_done_rule": TASK_DONE_REMINDER,
    }


def _strength_rank(value: str) -> int:
    return {"none": 0, "weak": 1, "moderate": 2, "strong": 3}.get(value, 0)


def _ledger_progress(before: Mapping[str, Any], after: Mapping[str, Any]) -> tuple[bool, bool]:
    before_map = {
        _ledger_requirement_text(item): item
        for item in _ledger_requirements(before)
        if _ledger_requirement_text(item)
    }
    after_map = {
        _ledger_requirement_text(item): item
        for item in _ledger_requirements(after)
        if _ledger_requirement_text(item)
    }
    requirement_advanced = False
    stronger_evidence_added = False
    for requirement, after_item in after_map.items():
        before_item = before_map.get(requirement, {})
        if str(before_item.get("status", "unproven")) != str(after_item.get("status", "unproven")):
            requirement_advanced = True
        if _strength_rank(str(after_item.get("evidence_strength", "none"))) > _strength_rank(
            str(before_item.get("evidence_strength", "none"))
        ):
            stronger_evidence_added = True
        if _new_independent_provenance_added(before_item, after_item):
            stronger_evidence_added = True
    return requirement_advanced, stronger_evidence_added


# Provenance labels that indicate the evidence was not merely self-authored
# (model-written artifact, replayed/same-method check, etc.). A newly added
# label from this set represents genuine independent evidence, distinct from
# a bare increase in evidence_refs count (e.g. an output write or status note).
_INDEPENDENT_PROVENANCE_LABELS = {
    "task_supplied",
    "external_tool_observation",
    "fresh_process",
    "fresh_client",
    "task_environment",
    "independent",
}


def _new_independent_provenance_added(before_item: Mapping[str, Any], after_item: Mapping[str, Any]) -> bool:
    before_labels = {str(label) for label in (before_item.get("evidence_provenance", []) or [])}
    after_labels = {str(label) for label in (after_item.get("evidence_provenance", []) or [])}
    newly_added = after_labels - before_labels
    return bool(newly_added & _INDEPENDENT_PROVENANCE_LABELS)


def _semantic_action_family(tool_name: str, arguments: Mapping[str, Any]) -> tuple[str, str | None, str | None]:
    if tool_name != "run_command":
        for key, target_kind in (("path", "path"), ("job_id", "job"), ("session_id", "session"), ("cwd", "path")):
            raw = arguments.get(key)
            if isinstance(raw, str) and raw.strip():
                return tool_name, raw, target_kind
        return tool_name, None, None

    command = str(arguments.get("cmd", ""))
    try:
        tokens = shlex.split(command, posix=True)
    except ValueError:
        return "run_command", command.strip() or None, "command"
    if not tokens:
        return "run_command", None, None
    family_tokens = [tokens[0]]
    if len(tokens) > 1 and tokens[0] in {"python", "python3", "pytest", "bash", "sh", "node", "Rscript", "make", "cmake", "cargo", "go", "npm", "pip", "pip3", "uv"}:
        family_tokens.append(tokens[1])
    target = None
    target_kind = None
    for token in tokens[1:]:
        if token.startswith("-") or "://" in token:
            continue
        if "/" in token or token.endswith((".py", ".sh", ".txt", ".json", ".md", ".toml", ".yaml", ".yml", ".csv")):
            target = token
            target_kind = "path"
            break
    return " ".join(family_tokens), target, target_kind


def _failure_class(envelope: ObservationEnvelope) -> str | None:
    if envelope.error is not None:
        return envelope.error.failure_class or envelope.error.reason_code or envelope.error.kind
    if envelope.exit_code is not None and envelope.exit_code != 0:
        return f"exit_{envelope.exit_code}"
    if not envelope.files_changed and envelope.exit_code == 0:
        return "no_effect"
    return None

def _build_tail_state(
    *,
    plan_text: str | None,
    elapsed_sec: float,
    remaining_sec: float | None,
    evidence_ledger: Mapping[str, Any],
    mirror: Mirror,
    streak: int,
    job_registry: JobRegistry,
    session_registry: SessionRegistry,
    job_ids: list[str],
    session_ids: list[str],
    note: MirrorNote | None,
    events: list[str] | None = None,
) -> dict[str, Any]:
    fuel_gauge: dict[str, Any] = {"elapsed_sec": round(elapsed_sec, 3)}
    if remaining_sec is not None:
        fuel_gauge["remaining_sec"] = round(remaining_sec, 3)

    jobs_state: dict[str, Any] = {}
    for job_id in job_ids:
        try:
            status = job_registry.status(job_id)
            jobs_state[job_id] = {"alive": status.alive, "exit_code": status.exit_code}
        except KeyError:
            continue

    derived_state: dict[str, Any] = {
        "no_delta_streak": streak,
        "active_jobs": jobs_state,
        "active_sessions": list(session_ids),
    }
    if events:
        derived_state["events"] = list(events)

    tail: dict[str, Any] = {
        "plan": plan_text or "",
        "fuel_gauge": fuel_gauge,
        "derived_state": derived_state,
        "evidence_ledger": _tail_evidence_ledger(evidence_ledger),
    }
    if note is not None:
        tail["mirror_note"] = note.text
        if note.fuel_gauge_text:
            tail["mirror_fuel_gauge"] = note.fuel_gauge_text
    return tail


def _trace_envelope_summary(envelope: ObservationEnvelope) -> dict[str, Any]:
    return {
        "tool": envelope.tool,
        "exit_code": envelope.exit_code,
        "duration_sec": round(envelope.duration_sec, 3),
        "cwd": envelope.cwd,
        "stdout_head": envelope.stdout_head,
        "stdout_tail": envelope.stdout_tail,
        "stderr_head": envelope.stderr_head,
        "stderr_tail": envelope.stderr_tail,
        "truncated": envelope.truncated,
        "raw_log_path": envelope.raw_log_path,
        "files_changed": [item.__dict__ for item in envelope.files_changed],
        "process_delta": envelope.process_delta.__dict__,
        "blind_retry_blocked": envelope.blind_retry_blocked,
        "error": None if envelope.error is None else envelope.error.__dict__,
    }


def _trace_tool_invocation_summary(record: ToolInvocationRecord) -> dict[str, Any]:
    return {
        "step": record.step,
        "tool_name": record.tool_name,
        "arguments": record.arguments,
        "permission_decision": record.permission_decision,
        "hook_trace": record.hook_trace,
        "observation": _trace_envelope_summary(record.envelope),
    }


def _model_visible_requirement_summary(
    completion_contract: Mapping[str, Any],
    ledger: Mapping[str, Any],
) -> dict[str, Any]:
    unresolved_requirements = completion_contract.get("unresolved_requirements")
    if not isinstance(unresolved_requirements, list):
        unresolved_requirements = []
    next_required_evidence = completion_contract.get("next_required_evidence")
    if not isinstance(next_required_evidence, list):
        next_required_evidence = []
    weak_evidence = completion_contract.get("weak_evidence")
    if not isinstance(weak_evidence, list):
        weak_evidence = []
    verifier_blockers = completion_contract.get("verifier_blockers")
    if not isinstance(verifier_blockers, list):
        verifier_blockers = []
    return {
        "unresolved_requirements": [str(item) for item in unresolved_requirements],
        "next_required_evidence": [str(item) for item in next_required_evidence],
        "weak_evidence": [str(item) for item in weak_evidence],
        "verifier_blockers": [str(item) for item in verifier_blockers],
        "persistent_blockers": list(ledger.get("blockers", []) or []),
    }


def _build_reasoning_trace_step(
    *,
    step: int | None,
    model_call_idx: int,
    call_role: str,
    response: Any,
    input_digests: Mapping[str, Any],
    visible_tail_state: Mapping[str, Any],
    completion_contract: Mapping[str, Any],
    pre_step_ledger: Mapping[str, Any],
    post_step_ledger: Mapping[str, Any],
    tool_invocations: list[ToolInvocationRecord],
    task_done_call: tuple[dict[str, Any], ObservationEnvelope] | None,
    decision_kind: str,
    plan_text: str | None,
    model_exchange_ref: str,
    verification_round_index: int | None = None,
    blocker_state: Mapping[str, Any] | None = None,
    finalize_reason: str | None = None,
) -> dict[str, Any]:
    requirement_advanced, stronger_evidence_added = _ledger_progress(pre_step_ledger, post_step_ledger)
    task_done_summary = {
        "called": task_done_call is not None,
        "summary": None,
        "checks": [],
    }
    if task_done_call is not None:
        task_done_summary["summary"] = str(task_done_call[0].get("summary", ""))
        task_done_summary["checks"] = [str(item) for item in task_done_call[0].get("checks", [])]

    return {
        "schema_version": 1,
        "step": step,
        "model_call_idx": model_call_idx,
        "call_role": call_role,
        "decision_kind": decision_kind,
        "assistant_text": getattr(response, "text", ""),
        "assistant_plan_after_turn": plan_text,
        "tool_call_count": len(tool_invocations),
        "tool_calls": [_trace_tool_invocation_summary(record) for record in tool_invocations],
        "model_input_digests": dict(input_digests),
        "visible_context": {
            "model_exchange_ref": model_exchange_ref,
            "tail_state": visible_tail_state,
            "completion_contract": completion_contract,
            "model_visible_requirements": _model_visible_requirement_summary(completion_contract, post_step_ledger),
        },
        "pre_step_evidence_ledger": pre_step_ledger,
        "post_step_evidence_ledger": post_step_ledger,
        "verification_round_index": verification_round_index,
        "blocker_state": dict(blocker_state or {}),
        "progress": {
            "requirement_advanced": requirement_advanced,
            "stronger_evidence_added": stronger_evidence_added,
            "no_progress": not (requirement_advanced or stronger_evidence_added),
        },
        "task_done": task_done_summary,
        "finalize_reason": finalize_reason,
    }


def _write_reasoning_trace(
    *,
    trace_path: Path,
    task_id: str,
    task_dir: Path,
    workspace_root: Path,
    receipts_root: Path,
    steps: list[dict[str, Any]],
    non_step_model_calls: list[dict[str, Any]],
    model_call_count: int,
    finalize_reason: str,
    finalize_pass: bool,
) -> Path:
    payload = {
        "schema_version": 1,
        "task_id": task_id,
        "task_dir": str(task_dir),
        "workspace_root": str(workspace_root),
        "receipts_root": str(receipts_root),
        "step_count": len(steps),
        "model_call_count": model_call_count,
        "finalize_reason": finalize_reason,
        "verifier_clean": finalize_pass,
        "steps": steps,
        "non_step_model_calls": non_step_model_calls,
    }
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    trace_path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")
    return trace_path


def _response_usage(response: Any) -> Mapping[str, Any]:
    usage = getattr(response, "usage", {})
    if isinstance(usage, Mapping):
        return usage
    return {}


def _response_cost(response: Any) -> float:
    raw_response = getattr(response, "raw_response", {})
    if isinstance(raw_response, Mapping):
        direct = raw_response.get("cost")
        if isinstance(direct, (int, float)):
            return float(direct)
        usage = raw_response.get("usage")
        if isinstance(usage, Mapping):
            value = usage.get("cost")
            if isinstance(value, (int, float)):
                return float(value)
    return 0.0


def _trace_non_step_model_calls(
    *,
    receipts_dir: Path,
    step_model_call_indices: set[int],
) -> list[dict[str, Any]]:
    non_step_calls: list[dict[str, Any]] = []
    for path in sorted(receipts_dir.glob("model_exchange_*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, Mapping):
            continue
        call_idx = payload.get("call_idx")
        if not isinstance(call_idx, int) or call_idx in step_model_call_indices:
            continue
        request_context = payload.get("request_context")
        if not isinstance(request_context, Mapping):
            request_context = {}
        non_step_calls.append(
            {
                "model_call_idx": call_idx,
                "call_role": payload.get("call_role"),
                "model_exchange_ref": str(path),
                "request_context": {
                    "env_contract": request_context.get("env_contract"),
                    "tool_schema_digest": request_context.get("tool_schema_digest"),
                    "tail_state_digest": _tail_payload_digest(request_context.get("tail_state")),
                },
            }
        )
    return non_step_calls


def _tail_payload_digest(payload: Any) -> str | None:
    if payload is None:
        return None
    try:
        rendered = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    except TypeError:
        return None
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _model_requested_rebase(response_text: str, tool_calls: Any) -> bool:
    if tool_calls:
        return False
    first_line = response_text.splitlines()[0].strip().upper() if response_text.splitlines() else ""
    return first_line.startswith("REBASE_REQUEST:")


def _model_requested_verification(response_text: str, tool_calls: Any) -> bool:
    if tool_calls:
        return False
    first_line = response_text.splitlines()[0].strip().upper() if response_text.splitlines() else ""
    return first_line.startswith("VERIFY_REQUEST:")


def _collect_established_facts(context: ContextManager) -> list[str]:
    snapshot = context.delta_state
    if snapshot is None:
        return []
    facts: list[str] = []
    files = getattr(snapshot, "files", {}) or {}
    jobs = getattr(snapshot, "job_registry", {}) or {}
    sessions = getattr(snapshot, "session_registry", {}) or {}
    if files:
        facts.append(f"written files: {', '.join(sorted(files)[:5])}")
    if jobs:
        facts.append(f"jobs: {', '.join(sorted(jobs)[:5])}")
    if sessions:
        facts.append(f"sessions: {', '.join(sorted(sessions)[:5])}")
    return facts


def _unused_affordances() -> list[str]:
    return [
        "start_job",
        "job_status",
        "session_start",
        "session_send",
        "session_read",
        "read_file",
        "write_file",
        "wait",
    ]


class _ReadOnlyVerificationContext:
    """Expose only read-only inspection affordances during verifier probes (C7).

    Deny-by-default: `run_command` is rejected unless every pipe segment's first
    token is a conservative read-only binary AND no shell metacharacters other
    than `|` (pipe) appear anywhere in the command. Every attempt -- allowed or
    rejected -- is recorded via `receipts.record_verifier_command` for a full
    audit trail. Perfect read-only enforcement in a shell is not possible (e.g.
    a malicious `find -exec`); this is a best-effort structural guard plus a
    complete audit trail, per the spec's honest-engineering posture.
    """

    _ALLOWED_BINARIES = {
        "ls",
        "cat",
        "head",
        "tail",
        "grep",
        "find",
        "stat",
        "wc",
        "file",
        "ps",
        "df",
        "du",
        "sha256sum",
        "jq",
        "pwd",
    }
    # Any of these appearing as standalone tokens (other than "|") makes the
    # command rejected: redirects, command chaining/substitution, backgrounding.
    _DISALLOWED_TOKENS = {
        ">", ">>", "<", "<<", ";", "&", "&&", "||", "`", "$(",
        "rm", "mv", "cp", "tee", "chmod", "chown", "mkdir", "touch", "kill",
        "dd", "truncate", "sed", "-exec", "-delete", "-ok",
    }

    def __init__(self, ctx: ExecutionContext, receipts: "ReceiptWriter | None" = None) -> None:
        self._ctx = ctx
        self._receipts = receipts
        self._call_idx = 0

    def _record(self, tool_name: str, arguments: dict[str, Any], envelope: ObservationEnvelope) -> ObservationEnvelope:
        self._call_idx += 1
        if self._receipts is not None:
            try:
                self._receipts.record_verifier_command(self._call_idx, tool_name, arguments, envelope)
            except Exception:  # noqa: BLE001 - receipts must never break verification
                pass
        return envelope

    def _rejected(self, cmd: str, message: str) -> ObservationEnvelope:
        return build_envelope(
            {
                "tool": "run_command",
                "exit_code": 1,
                "duration_sec": 0.0,
                "cwd": str(self._ctx.executor.workspace_root),
                "stdout": "",
                "stderr": message,
                "error": {
                    "kind": "verification_read_only_violation",
                    "message": message,
                    "reason_code": "verification_read_only_violation",
                    "command": cmd,
                },
            },
            raw_log_dir=self._ctx.raw_log_dir,
        )

    def run_command(self, cmd: str, timeout_sec: int = 120, cwd: str | None = None) -> ObservationEnvelope:
        try:
            tokens = shlex.split(cmd, posix=True)
        except ValueError:
            envelope = self._rejected(cmd, "verifier inspection command could not be parsed")
            return self._record("run_command", {"cmd": cmd, "timeout_sec": timeout_sec, "cwd": cwd}, envelope)

        if not tokens or any(token in self._DISALLOWED_TOKENS for token in tokens):
            envelope = self._rejected(cmd, "verifier inspection is read-only; command rejected")
            return self._record("run_command", {"cmd": cmd, "timeout_sec": timeout_sec, "cwd": cwd}, envelope)

        # Split on pipe tokens into segments; each segment's leading token must
        # be an allowed read-only binary.
        segments: list[list[str]] = [[]]
        for token in tokens:
            if token == "|":
                segments.append([])
            else:
                segments[-1].append(token)
        if any(not segment or segment[0] not in self._ALLOWED_BINARIES for segment in segments):
            envelope = self._rejected(cmd, "verifier inspection is read-only; command rejected")
            return self._record("run_command", {"cmd": cmd, "timeout_sec": timeout_sec, "cwd": cwd}, envelope)

        envelope = self._ctx.run_command(cmd, timeout_sec=timeout_sec, cwd=cwd)
        return self._record("run_command", {"cmd": cmd, "timeout_sec": timeout_sec, "cwd": cwd}, envelope)

    def read_file(self, path: str, offset: int | None = None, limit: int | None = None) -> ObservationEnvelope:
        envelope = self._ctx.read_file(path, offset=offset, limit=limit)
        return self._record("read_file", {"path": path, "offset": offset, "limit": limit}, envelope)

    def job_status(self, job_id: str) -> ObservationEnvelope:
        envelope = self._ctx.job_status(job_id)
        return self._record("job_status", {"job_id": job_id}, envelope)

    def session_read(self, session_id: str) -> ObservationEnvelope:
        envelope = self._ctx.session_read(session_id)
        return self._record("session_read", {"session_id": session_id}, envelope)


def _execute_tool_calls(
    *,
    response: Any,
    response_messages: list[dict[str, Any]],
    step: int,
    executor: ContainerExecutor,
    ctx: ExecutionContext,
    context: ContextManager,
    receipts: ReceiptWriter,
    mirror: Mirror,
    tool_invocations: list[ToolInvocationRecord],
    mirror_notes: list[MirrorNote],
    failure_tracker: dict[str, Any],
    recoveries: int,
    no_delta_streaks: int,
    job_ids: list[str],
    session_ids: list[str],
    stated_requirements: list[str],
    plan_text: str | None,
    elapsed_sec: float,
    remaining_sec: float | None,
    model_request_index: int,
) -> tuple[dict[str, Any], int, int, list[str], tuple[dict[str, Any], ObservationEnvelope] | None]:
    most_recent_checks: list[str] = []
    task_done_call: tuple[dict[str, Any], ObservationEnvelope] | None = None

    for tool_call in getattr(response, "tool_calls", ()) or ():
        tool_name = _tool_call_name(tool_call)
        tool_call_id = tool_call.get("id")
        if tool_name is None:
            envelope = build_envelope(
                {
                    "tool": "unknown",
                    "exit_code": 1,
                    "duration_sec": 0.0,
                    "cwd": str(executor.workspace_root),
                    "stdout": "",
                    "stderr": "malformed tool call: missing name",
                    "error": {
                        "kind": "malformed_tool_call",
                        "message": "tool call is missing a name",
                        "reason_code": "malformed_tool_call",
                    },
                },
                raw_log_dir=ctx.raw_log_dir,
            )
            context.append_turn(_envelope_to_message("unknown", tool_call_id, envelope))
            continue

        arguments = _parse_tool_call_arguments(tool_call)
        signature = _action_signature(tool_name, arguments)
        blind_retry = tool_name == "run_command" and failure_tracker.get("last_failure_signature") == signature
        permission_decision: dict[str, Any] | None = None
        hook_trace: list[dict[str, Any]] = []
        if blind_retry:
            envelope = _build_blind_retry_blocked_envelope(
                tool_name, arguments, str(executor.workspace_root), raw_log_dir=ctx.raw_log_dir
            )
            failure_tracker = {"last_failure_signature": None, "streak": 0}
        else:
            try:
                outcome = ctx.tool_registry.invoke(
                    tool_name,
                    arguments,
                    ctx,
                    call_id=None if tool_call_id is None else str(tool_call_id),
                )
                envelope = outcome.envelope
                permission_decision = outcome.permission_decision
                hook_trace = outcome.hook_trace
            except Exception as exc:  # noqa: BLE001
                envelope = build_envelope(
                    {
                        "tool": tool_name,
                        "exit_code": 1,
                        "duration_sec": 0.0,
                        "cwd": str(executor.workspace_root),
                        "stdout": "",
                        "stderr": str(exc),
                        "error": {
                            "kind": "dispatch_error",
                            "message": str(exc),
                            "reason_code": "dispatch_error",
                            "tool_name": tool_name,
                        },
                    },
                    raw_log_dir=ctx.raw_log_dir,
                )

        failed = _envelope_failed(envelope)
        failure_class_before = str(failure_tracker.get("last_failure_class") or "") or None
        failure_class_after = _failure_class(envelope)
        if failed:
            prior_signature = failure_tracker.get("last_failure_signature")
            streak = failure_tracker.get("streak", 0) + 1 if prior_signature == signature else 1
            failure_tracker = {
                "last_failure_signature": signature,
                "last_failure_class": failure_class_after,
                "streak": streak,
            }
        else:
            if failure_tracker.get("last_failure_signature") is not None:
                recoveries += 1
            failure_tracker = {"last_failure_signature": None, "last_failure_class": None, "streak": 0}

        context.append_turn(_envelope_to_message(tool_name, tool_call_id, envelope))
        _record = ToolInvocationRecord(
            step=step,
            tool_name=tool_name,
            arguments=arguments,
            envelope=envelope,
            permission_decision=permission_decision,
            hook_trace=hook_trace,
        )
        tool_invocations.append(_record)
        ctx._run_tool_invocations.append(_record)
        receipts.record_step(
            len(tool_invocations),
            request={"messages_len": len(response_messages)},
            response={"text": getattr(response, "text", "")},
            action={
                "tool": tool_name,
                "arguments": arguments,
                "permission_decision": permission_decision,
                "hook_trace": hook_trace,
            },
            raw_output=_envelope_to_message(tool_name, tool_call_id, envelope),
        )

        if tool_name == "start_job":
            job_id_arg = arguments.get("job_id")
            stdout = envelope.stdout_head
            started_job_id = job_id_arg
            if started_job_id is None and "started job " in stdout:
                started_job_id = stdout.split("started job ", 1)[1].split(" ", 1)[0]
            if started_job_id and started_job_id not in job_ids:
                job_ids.append(started_job_id)
        if tool_name == "session_start":
            session_id_arg = arguments.get("session_id")
            if session_id_arg and session_id_arg not in session_ids:
                session_ids.append(session_id_arg)

        ledger_before = _current_evidence_ledger(context)
        artifact_paths = [
            item.path
            for item in envelope.files_changed
            if item.change_type in {"added", "modified"}
        ]
        primary_requirement = _relevant_requirement(
            ledger_before,
            stated_requirements,
            tool_name=tool_name,
            arguments=arguments,
            artifact_paths=artifact_paths,
        )
        observation_note: str | None = None
        if tool_name == "task_done":
            observation_note = str(arguments.get("summary", "")).strip() or "task completion claimed"
        elif tool_name != "run_command" and envelope.exit_code == 0:
            observation_note = f"{tool_name} completed"
        elif artifact_paths:
            observation_note = f"{tool_name} changed visible workspace state"

        updated_ledger = record_observation_evidence(
            ledger_before,
            requirement=primary_requirement,
            tool_name=tool_name,
            step=step,
            exit_code=envelope.exit_code,
            raw_log_path=envelope.raw_log_path,
            artifact_paths=artifact_paths,
            note=observation_note,
            failure_family=failure_class_after,
        )
        if tool_name in {"task_done", "task_blocked"}:
            updated_ledger = record_terminal_claim(
                updated_ledger,
                claim=arguments,
                outcome=tool_name,
                step=step,
                raw_log_path=envelope.raw_log_path,
            )
        ctx.last_snapshot = with_evidence_ledger(ctx.last_snapshot, updated_ledger)
        context.delta_state = ctx.last_snapshot
        requirement_advanced, stronger_evidence_added = _ledger_progress(ledger_before, updated_ledger)
        action_family, semantic_target, semantic_target_kind = _semantic_action_family(tool_name, arguments)
        semantic_observation = SemanticObservation(
            action_family=action_family,
            target=semantic_target,
            target_kind=semantic_target_kind,
            failure_class_before=failure_class_before,
            failure_class_after=failure_class_after,
            requirement_advanced=requirement_advanced,
            stronger_evidence_added=stronger_evidence_added,
            artifact_evidence=tuple(artifact_paths),
            meaningful_artifact_change=bool(artifact_paths),
            legitimate_polling=bool(
                tool_name in {"job_status", "session_read", "wait"}
                and (
                    envelope.process_delta.job_log_growth
                    or envelope.process_delta.service_log_growth
                )
            ),
            bounded_retry=bool(tool_name == "wait"),
        )
        semantic_payload = (
            semantic_observation
            if (
                failure_class_after is not None
                or requirement_advanced
                or stronger_evidence_added
                or bool(artifact_paths)
                or tool_name in {"job_status", "session_read", "wait"}
            )
            else None
        )
        note = mirror.observe(
            signature,
            ctx.last_delta_report,
            semantic_observation=semantic_payload,
            established_facts=_collect_established_facts(context),
            unused_affordances=_unused_affordances(),
            fuel_gauge_text=(
                json.dumps(
                    {
                        "elapsed_sec": round(elapsed_sec, 3),
                        "remaining_sec": None if remaining_sec is None else round(remaining_sec, 3),
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=True,
                )
            ),
        )
        if note is not None:
            mirror_notes.append(note)
            no_delta_streaks += 1
            context.append_turn({"role": "system", "content": f"[mirror_note]\n{note.text}"})

        if tool_name == "task_done":
            task_done_call = (arguments, envelope)
            most_recent_checks = [str(item) for item in arguments.get("checks", [])]

    return failure_tracker, recoveries, no_delta_streaks, most_recent_checks, task_done_call



def _collect_tail_events(
    *,
    ctx: "ExecutionContext",
    job_registry: JobRegistry,
    job_ids: list[str],
    seen_artifacts: set[str],
    known_job_status: dict[str, tuple[bool, int | None]],
) -> list[str]:
    """Spec §6.3: artifact/service events since the last tail render.

    New artifacts written and job started/died transitions. Mutates
    `seen_artifacts` / `known_job_status` to track what has already been
    surfaced.
    """
    events: list[str] = []
    for path in sorted(ctx.last_delta_report.added_paths):
        if path in seen_artifacts:
            continue
        seen_artifacts.add(path)
        events.append(f"artifact_written:{path}")

    for job_id in job_ids:
        try:
            status = job_registry.status(job_id)
        except KeyError:
            continue
        current = (status.alive, status.exit_code)
        previous = known_job_status.get(job_id)
        if previous is None:
            events.append(f"job_started:{job_id}")
        elif previous[0] and not current[0]:
            events.append(f"job_died:{job_id} exit_code={current[1]}")
        known_job_status[job_id] = current

    return events


def _sync_fact_ledger_state(context: ContextManager, ctx: "ExecutionContext") -> None:
    """Merge ExecutionContext's cumulative run-level facts (installed packages,
    nonzero exits) into the delta state used by compactor.build_fact_ledger
    (spec §6.5)."""
    if context.delta_state is None:
        return
    context.delta_state = dataclass_replace(
        context.delta_state,
        installed_packages=tuple(ctx.installed_packages),
        nonzero_exits=tuple(ctx.nonzero_exits),
    )

def run_aether2_loop(
    task: TaskSpec,
    model_client: Any,
    executor: ContainerExecutor,
    *,
    deadline_ts: float,
    hook_registry: HookRegistry | None = None,
    permission_manager: PermissionManager | None = None,
    tool_registry: ToolRegistry | None = None,
) -> RunResult:
    """Run the orientation-to-finalize continuity loop for a single task against the live workspace."""

    if model_client is None:
        raise ValueError(
            "run_aether2_loop requires a model_client (e.g. runner.aether2.model_client.Aether2ModelClient); "
            "got None. Construct one from a model route before calling the loop."
        )

    started_at = time.monotonic()

    state_dir = task.workspace_root / ".aether2" / "state"
    raw_log_dir = task.workspace_root / ".aether2" / "raw_logs"
    receipts_root = task.task_dir / ".aether2" / "host_receipts"

    job_registry = JobRegistry(state_dir, backend=executor.backend, container_path_fn=executor.to_container_path)
    session_registry = SessionRegistry(state_dir, backend=executor.backend)
    ctx = ExecutionContext(
        executor=executor,
        job_registry=job_registry,
        session_registry=session_registry,
        raw_log_dir=raw_log_dir,
        hook_registry=hook_registry,
        permission_manager=permission_manager,
        tool_registry=tool_registry,
    )
    receipts = ReceiptWriter(receipts_root)

    orientation_snapshot = orient(executor)
    orientation_dict = orientation_snapshot.as_dict()
    stated_requirements = _extract_stated_requirements(task.instruction)
    verifier_task_contract = _extract_verifier_task_contract(task.instruction)
    seeded_ledger = ensure_stated_requirements(build_evidence_ledger(stated_requirements), stated_requirements)
    ctx.last_snapshot = with_evidence_ledger(ctx.last_snapshot, seeded_ledger)

    active_tool_schemas = ctx.tool_registry.tool_schemas()
    context = ContextManager(delta_state=ctx.last_snapshot)
    context.build_prefix(
        system_prompt=SYSTEM_PROMPT,
        task_instruction=task.instruction,
        orientation=orientation_dict,
        tool_schemas=active_tool_schemas,
    )
    context.set_completion_contract(_build_completion_contract(verifier_task_contract, seeded_ledger))

    mirror = Mirror()
    failure_tracker: dict[str, Any] = {"last_failure_signature": None, "last_failure_class": None, "streak": 0}
    job_ids: list[str] = []
    session_ids: list[str] = []
    seen_artifacts: set[str] = set()
    known_job_status: dict[str, tuple[bool, int | None]] = {}
    pending_tail_events: list[str] = []
    tool_invocations: list[ToolInvocationRecord] = []
    mirror_notes: list[MirrorNote] = []
    discrepancy_reports: list[Any] = []
    reasoning_trace_steps: list[dict[str, Any]] = []

    model_calls = 0
    tokens_cached = 0
    tokens_fresh = 0
    total_cost = 0.0
    compaction_count = 0
    verification_rounds = 0
    suppressed_verifier_calls = 0
    completion_precheck_rejections = 0
    recoveries = 0
    no_delta_streaks = 0

    finalize_reason: str | None = None
    finalize_summary = ""
    finalize_pass = False
    most_recent_checks: list[str] = []

    plan_text: str | None = None

    def record_exchange(
        call_idx: int,
        request_messages: list[dict[str, Any]],
        response: Any,
        *,
        tool_schemas: Any,
        call_role: str,
    ) -> None:
        receipts.record_model_exchange(
            call_idx,
            request_messages,
            response,
            tool_schemas=tool_schemas,
            call_role=call_role,
            tail_state=context.current_tail_payload(),
            ledger_state=_current_evidence_ledger(context),
        )

    def make_exchange_recorder(counter: dict[str, int]):
        def _record(
            request_messages: list[dict[str, Any]],
            response: Any,
            tool_schemas: Any,
            *,
            call_role: str,
            **_: Any,
        ) -> None:
            call_idx = counter["next"]
            counter["next"] += 1
            record_exchange(
                call_idx,
                request_messages,
                response,
                tool_schemas=tool_schemas,
                call_role=call_role,
            )

        return _record

    def append_trace_step(
        *,
        step_index: int | None,
        model_call_idx: int,
        call_role: str,
        response: Any,
        visible_tail_state: Mapping[str, Any],
        completion_contract: Mapping[str, Any],
        pre_step_ledger: Mapping[str, Any],
        post_step_ledger: Mapping[str, Any],
        tool_invocations_for_step: list[ToolInvocationRecord],
        task_done_call: tuple[dict[str, Any], ObservationEnvelope] | None,
        decision_kind: str,
        finalize_reason: str | None = None,
        verification_round_index: int | None = None,
        blocker_state: Mapping[str, Any] | None = None,
    ) -> None:
        reasoning_trace_steps.append(
            _build_reasoning_trace_step(
                step=step_index,
                model_call_idx=model_call_idx,
                call_role=call_role,
                response=response,
                input_digests=context.digest_snapshot(),
                visible_tail_state=visible_tail_state,
                completion_contract=completion_contract,
                pre_step_ledger=pre_step_ledger,
                post_step_ledger=post_step_ledger,
                tool_invocations=tool_invocations_for_step,
                task_done_call=task_done_call,
                decision_kind=decision_kind,
                plan_text=plan_text,
                model_exchange_ref=str(receipts.receipts_dir / f"model_exchange_{model_call_idx}.json"),
                verification_round_index=verification_round_index,
                blocker_state=blocker_state,
                finalize_reason=finalize_reason,
            )
        )

    step = 0
    while step < STEP_CAP:
        elapsed_sec = time.monotonic() - started_at
        remaining_sec = deadline_ts - time.time()
        if remaining_sec <= 0:
            finalize_reason = "budget_exhaustion"
            break

        step += 1

        if context.transcript:
            window_used_frac = (context.prefix.token_estimate + _estimate_transcript_tokens(context)) / CONTEXT_WINDOW_TOKENS
            if should_rebase(window_used_frac, False):
                _sync_fact_ledger_state(context, ctx)
                compaction_counter = {"next": model_calls + 1}
                context = rebase(
                    context,
                    model_client,
                    record_exchange=make_exchange_recorder(compaction_counter),
                )
                compaction_count += 1
                model_calls = compaction_counter["next"] - 1

        visible_ledger_before = _current_evidence_ledger(context)
        visible_tail_state = _build_tail_state(
            plan_text=plan_text,
            elapsed_sec=elapsed_sec,
            remaining_sec=remaining_sec,
            evidence_ledger=visible_ledger_before,
            mirror=mirror,
            streak=mirror.streak,
            job_registry=job_registry,
            session_registry=session_registry,
            job_ids=job_ids,
            session_ids=session_ids,
            note=None,
            events=pending_tail_events,
        )
        completion_contract = _build_completion_contract(verifier_task_contract, visible_ledger_before)
        messages = [*context.message_history()]
        tail_text = context.render_tail(visible_tail_state, completion_contract=completion_contract)
        if tail_text:
            messages = [*messages, {"role": "system", "content": tail_text}]
        pending_tail_events = []

        response = model_client.call(messages, active_tool_schemas, cache_prefix_len=context.prefix.token_estimate)
        model_calls += 1
        record_exchange(model_calls, messages, response, tool_schemas=active_tool_schemas, call_role="normal")
        usage = _response_usage(response)
        tokens_cached += int(usage.get("cached_input_tokens", 0))
        tokens_fresh += int(usage.get("fresh_input_tokens", 0))
        total_cost += _response_cost(response)

        assistant_message: dict[str, Any] = {"role": "assistant", "content": response.text}
        if response.tool_calls:
            assistant_message["tool_calls"] = [dict(tool_call) for tool_call in response.tool_calls]
        context.append_turn(assistant_message)

        plan_text = _update_plan_text(plan_text, response.text)

        if _model_requested_rebase(response.text, response.tool_calls):
            append_trace_step(
                step_index=step,
                model_call_idx=model_calls,
                call_role="normal",
                response=response,
                visible_tail_state=visible_tail_state,
                completion_contract=completion_contract,
                pre_step_ledger=visible_ledger_before,
                post_step_ledger=_current_evidence_ledger(context),
                tool_invocations_for_step=[],
                task_done_call=None,
                decision_kind="rebase_request",
            )
            _sync_fact_ledger_state(context, ctx)
            compaction_counter = {"next": model_calls + 1}
            context = rebase(
                context,
                model_client,
                record_exchange=make_exchange_recorder(compaction_counter),
            )
            compaction_count += 1
            model_calls = compaction_counter["next"] - 1
            continue

        if _model_requested_verification(response.text, response.tool_calls):
            finalize_reason = "verification_requested"
            finalize_summary = response.text
            append_trace_step(
                step_index=step,
                model_call_idx=model_calls,
                call_role="normal",
                response=response,
                visible_tail_state=visible_tail_state,
                completion_contract=completion_contract,
                pre_step_ledger=visible_ledger_before,
                post_step_ledger=_current_evidence_ledger(context),
                tool_invocations_for_step=[],
                task_done_call=None,
                decision_kind="verification_requested",
                finalize_reason=finalize_reason,
            )
            break

        if not response.tool_calls:
            finalize_reason = "implicit_stop"
            finalize_summary = response.text
            append_trace_step(
                step_index=step,
                model_call_idx=model_calls,
                call_role="normal",
                response=response,
                visible_tail_state=visible_tail_state,
                completion_contract=completion_contract,
                pre_step_ledger=visible_ledger_before,
                post_step_ledger=_current_evidence_ledger(context),
                tool_invocations_for_step=[],
                task_done_call=None,
                decision_kind="implicit_stop",
                finalize_reason=finalize_reason,
            )
            break

        step_tool_invocation_start = len(tool_invocations)
        failure_tracker, recoveries, no_delta_streaks, new_checks, task_done_call = _execute_tool_calls(
            response=response,
            response_messages=messages,
            step=step,
            executor=executor,
            ctx=ctx,
            context=context,
            receipts=receipts,
            mirror=mirror,
            tool_invocations=tool_invocations,
            mirror_notes=mirror_notes,
            failure_tracker=failure_tracker,
            recoveries=recoveries,
            no_delta_streaks=no_delta_streaks,
            job_ids=job_ids,
            session_ids=session_ids,
            stated_requirements=stated_requirements,
            plan_text=plan_text,
            elapsed_sec=elapsed_sec,
            remaining_sec=remaining_sec,
            model_request_index=model_calls,
        )
        if new_checks:
            most_recent_checks = new_checks

        step_tool_invocations = tool_invocations[step_tool_invocation_start:]

        pending_tail_events.extend(
            _collect_tail_events(
                ctx=ctx,
                job_registry=job_registry,
                job_ids=job_ids,
                seen_artifacts=seen_artifacts,
                known_job_status=known_job_status,
            )
        )

        if task_done_call is not None:
            finalize_reason = "task_done"
            finalize_summary = str(task_done_call[0].get("summary", ""))
            append_trace_step(
                step_index=step,
                model_call_idx=model_calls,
                call_role="normal",
                response=response,
                visible_tail_state=visible_tail_state,
                completion_contract=completion_contract,
                pre_step_ledger=visible_ledger_before,
                post_step_ledger=_current_evidence_ledger(context),
                tool_invocations_for_step=step_tool_invocations,
                task_done_call=task_done_call,
                decision_kind="task_done",
                finalize_reason=finalize_reason,
            )
            break

        append_trace_step(
            step_index=step,
            model_call_idx=model_calls,
            call_role="normal",
            response=response,
            visible_tail_state=visible_tail_state,
            completion_contract=completion_contract,
            pre_step_ledger=visible_ledger_before,
            post_step_ledger=_current_evidence_ledger(context),
            tool_invocations_for_step=step_tool_invocations,
            task_done_call=None,
            decision_kind="tool_calls",
        )

    if finalize_reason is None:
        finalize_reason = "budget_exhaustion"
        finalize_summary = "step cap safety rail reached before an explicit completion claim"

    if finalize_reason == "budget_exhaustion":
        check_results = replay_checks(most_recent_checks, executor) if most_recent_checks else []
        closing_messages = [
            *context.message_history(),
            {
                "role": "system",
                "content": (
                    "Wall-clock deadline reached. Here are the results of replaying your "
                    "most recently declared checks (if any). This is your final turn."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {"checks_results": [result.__dict__ for result in check_results]},
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=True,
                ),
            },
        ]
        response = model_client.call(closing_messages, [], cache_prefix_len=context.prefix.token_estimate)
        model_calls += 1
        record_exchange(model_calls, closing_messages, response, tool_schemas=[], call_role="closing")
        usage = _response_usage(response)
        tokens_cached += int(usage.get("cached_input_tokens", 0))
        tokens_fresh += int(usage.get("fresh_input_tokens", 0))
        total_cost += _response_cost(response)
        finalize_summary = response.text
        finalize_pass = bool(check_results) and all(
            result.exit_code == 0 for result in check_results
        )
        closing_elapsed_sec = time.monotonic() - started_at
        current_ledger = _current_evidence_ledger(context)
        append_trace_step(
            step_index=step if step > 0 else None,
            model_call_idx=model_calls,
            call_role="closing",
            response=response,
            visible_tail_state=_build_tail_state(
                plan_text=plan_text,
                elapsed_sec=closing_elapsed_sec,
                remaining_sec=deadline_ts - time.time(),
                evidence_ledger=current_ledger,
                mirror=mirror,
                streak=mirror.streak,
                job_registry=job_registry,
                session_registry=session_registry,
                job_ids=job_ids,
                session_ids=session_ids,
                note=None,
                events=pending_tail_events,
            ),
            completion_contract=_build_completion_contract(verifier_task_contract, current_ledger),
            pre_step_ledger=current_ledger,
            post_step_ledger=current_ledger,
            tool_invocations_for_step=[],
            task_done_call=None,
            decision_kind="closing",
            finalize_reason=finalize_reason,
        )
    else:
        rounds = 0
        claim_summary = finalize_summary
        claim_checks = most_recent_checks
        while rounds < MAX_VERIFICATION_ROUNDS:
            rounds += 1
            verification_rounds += 1
            check_results = replay_checks(claim_checks, executor) if claim_checks else []
            verification_ledger = _current_evidence_ledger(context)
            successful_check_summaries = [
                _check_result_summary(result)
                for result in check_results
                if getattr(result, "exit_code", None) == 0 and not bool(getattr(result, "timed_out", False))
            ]
            if check_results:
                verification_ledger = record_check_results(
                    verification_ledger,
                    requirement=_primary_requirement(verification_ledger, stated_requirements),
                    check_results=check_results,
                    step=step,
                    raw_log_path=None,
                )
            curr_snapshot = delta_snapshot(task.workspace_root)
            workspace_diff = delta_diff(ctx.last_snapshot, curr_snapshot)
            relevant_artifact_paths = [*workspace_diff.added_paths, *workspace_diff.modified_paths]
            verification_ledger = mark_blockers_candidate_resolved(
                verification_ledger,
                step=step,
                relevant_failed_checks=successful_check_summaries,
                relevant_artifact_paths=relevant_artifact_paths,
            )
            curr_snapshot = with_evidence_ledger(curr_snapshot, verification_ledger)
            service_monitoring, monitored_snapshot = _monitor_persistent_runtime(
                ctx=ctx,
                job_registry=job_registry,
                session_registry=session_registry,
                job_ids=job_ids,
                session_ids=session_ids,
                claim_checks=claim_checks,
                check_results=check_results,
                remaining_sec=deadline_ts - time.time(),
                start_snapshot=curr_snapshot,
            )
            curr_snapshot = monitored_snapshot
            workspace_diff = delta_diff(ctx.last_snapshot, curr_snapshot)
            relevant_artifact_paths = [*workspace_diff.added_paths, *workspace_diff.modified_paths]
            ctx.last_snapshot = curr_snapshot
            context.delta_state = curr_snapshot
            verification_orientation_dict = orient(executor).as_dict()

            action_digest = {
                "environment_contract": _env_contract_drift(orientation_dict, verification_orientation_dict),
                "service_monitoring": service_monitoring,
                "tool_calls": [
                    {"step": record.step, "tool": record.tool_name, "arguments": record.arguments}
                    for record in tool_invocations[-20:]
                ]
            }
            completion_gate_report = _build_completion_evidence_gate_report(
                verification_ledger,
                stated_requirements=stated_requirements,
                finalize_reason=finalize_reason,
                check_results=check_results,
                action_digest=action_digest,
            )
            if completion_gate_report is not None:
                completion_precheck_rejections += 1
                discrepancy_report = completion_gate_report
                updated_ledger = record_verifier_report(
                    _current_evidence_ledger(context),
                    report=discrepancy_report,
                    verifier_ref=f"completion_evidence_gate_round={verification_rounds}",
                    step=step,
                    exhaustion_round_limit=MAX_VERIFICATION_ROUNDS - 1,
                )
                if rounds >= MAX_VERIFICATION_ROUNDS:
                    updated_ledger = mark_blockers_exhausted(
                        updated_ledger,
                        step=step,
                        exhaustion_round_limit=MAX_VERIFICATION_ROUNDS - 1,
                        force=True,
                    )
            elif should_suppress_verifier_call(
                verification_ledger,
                relevant_failed_checks=successful_check_summaries,
                relevant_artifact_paths=relevant_artifact_paths,
            ):
                suppressed_verifier_calls += 1
                completion_precheck_rejections += 1
                if rounds >= MAX_VERIFICATION_ROUNDS:
                    verification_ledger = mark_blockers_exhausted(
                        verification_ledger,
                        step=step,
                        exhaustion_round_limit=MAX_VERIFICATION_ROUNDS - 1,
                        force=True,
                    )
                discrepancy_report = _build_suppressed_blocker_report(verification_ledger)
                updated_ledger = verification_ledger
            else:
                verifier_counter = {"next": model_calls + 1}
                discrepancy_report = verify_fresh_context(
                    verifier_task_contract,
                    orientation_dict,
                    _diff_to_dict(workspace_diff),
                    {"summary": claim_summary, "trigger": finalize_reason},
                    check_results,
                    action_digest,
                    model_client,
                    inspection_ctx=_ReadOnlyVerificationContext(ctx, receipts),
                    record_exchange=make_exchange_recorder(verifier_counter),
                    stated_requirements=stated_requirements,
                )
                model_calls = verifier_counter["next"] - 1
                updated_ledger = record_verifier_report(
                    _current_evidence_ledger(context),
                    report=discrepancy_report,
                    verifier_ref=f"verification_round={verification_rounds}",
                    step=step,
                    exhaustion_round_limit=MAX_VERIFICATION_ROUNDS - 1,
                )
                if discrepancy_report.has_discrepancies and rounds >= MAX_VERIFICATION_ROUNDS:
                    updated_ledger = mark_blockers_exhausted(
                        updated_ledger,
                        step=step,
                        exhaustion_round_limit=MAX_VERIFICATION_ROUNDS - 1,
                        force=True,
                    )
            discrepancy_reports.append(discrepancy_report)
            ctx.last_snapshot = with_evidence_ledger(ctx.last_snapshot, updated_ledger)
            context.delta_state = ctx.last_snapshot

            remaining_sec = deadline_ts - time.time()
            if not discrepancy_report.has_discrepancies or remaining_sec <= 0 or rounds >= MAX_VERIFICATION_ROUNDS:
                finalize_pass = not discrepancy_report.has_discrepancies
                finalize_summary = claim_summary if finalize_pass else discrepancy_report.summary
                break

            report_message = {
                "role": "system",
                "content": json.dumps(
                    _clean_hidden_refs(
                        {
                            "verification_blocker": discrepancy_report.summary,
                            "verification_report": {
                                "requirements": [item.__dict__ for item in discrepancy_report.requirements],
                                "reason_codes": list(discrepancy_report.reason_codes),
                                "summary": discrepancy_report.summary,
                            },
                            "checks_results": [result.__dict__ for result in check_results],
                            "time_remaining_sec": remaining_sec,
                        }
                    ),
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=True,
                ),
            }
            context.append_turn(report_message)

            messages = [*context.message_history()]
            repair_pre_ledger = _current_evidence_ledger(context)
            repair_completion_contract = _build_completion_contract(verifier_task_contract, repair_pre_ledger)
            repair_tail_state = context.current_tail_payload()
            response = model_client.call(messages, active_tool_schemas, cache_prefix_len=context.prefix.token_estimate)
            model_calls += 1
            record_exchange(model_calls, messages, response, tool_schemas=active_tool_schemas, call_role="repair")
            usage = _response_usage(response)
            tokens_cached += int(usage.get("cached_input_tokens", 0))
            tokens_fresh += int(usage.get("fresh_input_tokens", 0))
            total_cost += _response_cost(response)

            assistant_message = {"role": "assistant", "content": response.text}
            if response.tool_calls:
                assistant_message["tool_calls"] = [dict(tool_call) for tool_call in response.tool_calls]
            context.append_turn(assistant_message)

            claim_summary = response.text
            if _model_requested_rebase(response.text, response.tool_calls):
                append_trace_step(
                    step_index=step,
                    model_call_idx=model_calls,
                    call_role="repair",
                    response=response,
                    visible_tail_state=repair_tail_state,
                    completion_contract=repair_completion_contract,
                    pre_step_ledger=repair_pre_ledger,
                    post_step_ledger=_current_evidence_ledger(context),
                    tool_invocations_for_step=[],
                    task_done_call=None,
                    decision_kind="repair_rebase_request",
                    verification_round_index=rounds,
                    blocker_state={
                        "verification_summary": discrepancy_report.summary,
                        "reason_codes": list(discrepancy_report.reason_codes),
                    },
                )
                _sync_fact_ledger_state(context, ctx)
                compaction_counter = {"next": model_calls + 1}
                context = rebase(
                    context,
                    model_client,
                    record_exchange=make_exchange_recorder(compaction_counter),
                )
                compaction_count += 1
                model_calls = compaction_counter["next"] - 1
                continue

            repair_step_tool_invocation_start = len(tool_invocations)
            previous_claim_checks = list(claim_checks)
            failure_tracker, recoveries, no_delta_streaks, new_checks, new_task_done = _execute_tool_calls(
                response=response,
                response_messages=messages,
                step=step,
                executor=executor,
                ctx=ctx,
                context=context,
                receipts=receipts,
                mirror=mirror,
                tool_invocations=tool_invocations,
                mirror_notes=mirror_notes,
                failure_tracker=failure_tracker,
                recoveries=recoveries,
                no_delta_streaks=no_delta_streaks,
                job_ids=job_ids,
                session_ids=session_ids,
                stated_requirements=stated_requirements,
                plan_text=plan_text,
                elapsed_sec=time.monotonic() - started_at,
                remaining_sec=remaining_sec,
                model_request_index=model_calls,
            )
            repair_step_tool_invocations = tool_invocations[repair_step_tool_invocation_start:]
            if new_task_done is not None:
                claim_summary = str(new_task_done[0].get("summary", claim_summary))
            if new_checks:
                claim_checks = new_checks
            append_trace_step(
                step_index=step,
                model_call_idx=model_calls,
                call_role="repair",
                response=response,
                visible_tail_state=repair_tail_state,
                completion_contract=repair_completion_contract,
                pre_step_ledger=repair_pre_ledger,
                post_step_ledger=_current_evidence_ledger(context),
                tool_invocations_for_step=repair_step_tool_invocations,
                task_done_call=new_task_done,
                decision_kind="repair_task_done" if new_task_done is not None else ("repair_tool_calls" if response.tool_calls else "repair_implicit_stop"),
                verification_round_index=rounds,
                blocker_state={
                    "verification_summary": discrepancy_report.summary,
                    "reason_codes": list(discrepancy_report.reason_codes),
                    "previous_checks": previous_claim_checks,
                },
                finalize_reason=finalize_reason if new_task_done is not None else None,
            )
            if new_task_done is None and not response.tool_calls:
                # implicit stop during a verification round: treat as resubmission with no new checks
                continue

    job_survival = all(_job_alive_safe(job_registry, job_id) for job_id in job_ids) if job_ids else True
    session_survival = (
        all(sid in session_registry.list_session_ids() for sid in session_ids) if session_ids else True
    )

    wall_time = time.monotonic() - started_at
    step_model_call_indices = {
        int(step_payload["model_call_idx"])
        for step_payload in reasoning_trace_steps
        if isinstance(step_payload.get("model_call_idx"), int)
    }
    reasoning_trace_ref = str(
        _write_reasoning_trace(
            trace_path=receipts_root / "traces" / "reasoning_trace.json",
            task_id=task.task_id,
            task_dir=task.task_dir,
            workspace_root=task.workspace_root,
            receipts_root=receipts_root,
            steps=reasoning_trace_steps,
            non_step_model_calls=_trace_non_step_model_calls(
                receipts_dir=receipts.receipts_dir,
                step_model_call_indices=step_model_call_indices,
            ),
            model_call_count=model_calls,
            finalize_reason=finalize_reason,
            finalize_pass=finalize_pass,
        )
    )

    return RunResult(
        verifier_clean=finalize_pass,
        finalize_reason=finalize_reason,
        summary=finalize_summary,
        steps=step,
        model_calls=model_calls,
        tokens_cached=tokens_cached,
        tokens_fresh=tokens_fresh,
        cost=total_cost,
        wall_time=wall_time,
        no_delta_streaks=no_delta_streaks,
        verification_rounds=verification_rounds,
        suppressed_verifier_calls=suppressed_verifier_calls,
        completion_precheck_rejections=completion_precheck_rejections,
        recoveries=recoveries,
        compaction_count=compaction_count,
        job_survival=job_survival,
        session_survival=session_survival,
        reasoning_trace_ref=reasoning_trace_ref,
        tool_invocations=tool_invocations,
        mirror_notes=mirror_notes,
        discrepancy_reports=discrepancy_reports,
    )


def _update_plan_text(plan_text: str | None, response_text: str) -> str | None:
    """Track the model-owned plan (spec §6.3 tail telemetry).

    The first non-empty assistant `response.text` of the run becomes the initial plan.
    Thereafter, if an assistant turn's first line starts with "PLAN" (case-insensitive),
    its full text replaces the plan. No other parsing is performed.
    """
    if not response_text:
        return plan_text
    first_line = response_text.splitlines()[0] if response_text.splitlines() else ""
    if first_line.strip().upper().startswith("PLAN"):
        return response_text
    if plan_text is None:
        return response_text
    return plan_text


def _estimate_transcript_tokens(context: ContextManager) -> int:
    rendered = json.dumps(context.transcript, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return len(rendered.encode("utf-8")) // 4


def _diff_to_dict(report: Any) -> dict[str, Any]:
    return {
        "files_changed": [item.__dict__ for item in report.files_changed],
        "added_paths": list(report.added_paths),
        "modified_paths": list(report.modified_paths),
        "deleted_paths": list(report.deleted_paths),
        "artifact_registry_changed": report.artifact_registry_changed,
        "service_registry_changed": report.service_registry_changed,
        "process_registry_changed": report.process_registry_changed,
        "job_registry_changed": report.job_registry_changed,
        "session_registry_changed": report.session_registry_changed,
    }


def _job_alive_safe(job_registry: JobRegistry, job_id: str) -> bool:
    try:
        status = job_registry.status(job_id)
    except KeyError:
        return False
    return status.alive or status.exit_code == 0


def _check_result_summary(result: Any) -> str:
    command = str(getattr(result, "command", "") or "").strip() or "<unknown>"
    exit_code = getattr(result, "exit_code", None)
    summary = f"cmd={command} exit={exit_code if exit_code is not None else 'none'}"
    if bool(getattr(result, "timed_out", False)):
        summary += " timed_out=true"
    reason_code = str(getattr(result, "error_reason_code", "") or "").strip()
    if reason_code:
        summary += f" reason={reason_code}"
    return summary


def _active_blockers(ledger: Mapping[str, Any]) -> list[dict[str, Any]]:
    blockers = ledger.get("blockers", []) if isinstance(ledger, Mapping) else []
    if not isinstance(blockers, list):
        return []
    return [
        dict(item)
        for item in blockers
        if isinstance(item, Mapping) and str(item.get("status", "")) in {"active", "candidate_resolved", "exhausted"}
    ]


def _build_suppressed_blocker_report(ledger: Mapping[str, Any]) -> DiscrepancyReport:
    blocker_rows = _active_blockers(ledger)[:_REQUIREMENT_PREVIEW_LIMIT]
    requirements = tuple(
        RequirementResult(
            requirement=str(blocker.get("requirement", "")).strip() or "unresolved requirement",
            verdict="unverifiable",
            evidence=(
                str(blocker.get("insufficiency_reason", "")).strip()
                or "No new blocker-relevant evidence was provided."
            )
            + (
                ""
                if not list(blocker.get("required_next_evidence", []) or [])
                else f" Next evidence: {list(blocker.get('required_next_evidence', []) or [])[0]}"
            ),
            evidence_strength="weak",
            evidence_strength_reasons=("suppressed_verifier_without_new_relevant_evidence",),
            confidence="high",
            evidence_refs=tuple(str(item) for item in list(blocker.get("rejected_evidence_refs", []) or [])[:2]),
            unresolved=True,
        )
        for blocker in blocker_rows
    )
    summary = "Completion request rejected without a new verifier call because active blockers still require new relevant evidence."
    blocker_summaries = [
        f"{str(blocker.get('requirement', '')).strip()}: "
        f"{(list(blocker.get('required_next_evidence', []) or []) or ['new blocker-relevant evidence required'])[0]}"
        for blocker in blocker_rows
    ]
    if blocker_summaries:
        summary += " " + " | ".join(blocker_summaries)
    return DiscrepancyReport(
        requirements=requirements,
        reason_codes=("verifier_suppressed_no_new_relevant_evidence",),
        summary=summary,
        raw_response="suppressed_verifier_call",
    )


def _has_independent_runtime_evidence(action_digest: Mapping[str, Any]) -> bool:
    service_monitoring = action_digest.get("service_monitoring")
    if not isinstance(service_monitoring, Mapping) or not service_monitoring.get("applies"):
        return False

    jobs = service_monitoring.get("jobs")
    if isinstance(jobs, Mapping):
        for payload in jobs.values():
            if not isinstance(payload, Mapping):
                continue
            after = payload.get("end")
            if isinstance(after, Mapping) and (after.get("alive") is True or after.get("exit_code") == 0):
                return True

    sessions = service_monitoring.get("sessions")
    if isinstance(sessions, Mapping):
        for payload in sessions.values():
            if isinstance(payload, Mapping) and payload.get("end_present") is True:
                return True

    services = service_monitoring.get("services")
    if isinstance(services, Mapping):
        for payload in services.values():
            if isinstance(payload, Mapping) and payload.get("end") is not None:
                return True

    return False


def _build_completion_evidence_gate_report(
    ledger: Mapping[str, Any],
    *,
    stated_requirements: list[str],
    finalize_reason: str | None,
    check_results: list[Any],
    action_digest: Mapping[str, Any],
) -> DiscrepancyReport | None:
    if finalize_reason != "task_done":
        return None
    if check_results or _has_independent_runtime_evidence(action_digest):
        return None

    requirement = _primary_requirement(ledger, stated_requirements)
    evidence = (
        "task_done did not provide any replayed checks and the harness "
        "did not observe independent runtime/service/session evidence. Provide "
        "a concrete externally observable check, or keep working."
    )
    result = RequirementResult(
        requirement=requirement or "completion claim",
        verdict="unverifiable",
        evidence=evidence,
        evidence_strength="weak",
        evidence_strength_reasons=("no_replayed_check", "no_independent_runtime_evidence"),
        evidence_provenance=("model_authored",),
        confidence="high",
        evidence_refs=("claim", "action_digest.service_monitoring"),
        unresolved=True,
    )
    return DiscrepancyReport(
        requirements=(result,),
        reason_codes=("completion_evidence_gate_rejected",),
        summary="Completion request rejected before verifier because no replayed check or independent runtime evidence was available.",
        raw_response="completion_evidence_gate",
    )


def _service_monitoring_candidate(
    *,
    job_ids: list[str],
    session_ids: list[str],
    claim_checks: list[str],
    snapshot: StateSnapshot,
) -> bool:
    if job_ids or session_ids or getattr(snapshot, "service_registry", {}):
        return True
    service_tokens = ("curl", "http://", "https://", "port", "listen", "service", "server", "socket", "pgrep", "lsof")
    return any(any(token in check.lower() for token in service_tokens) for check in claim_checks)


def _job_status_payload(job_registry: JobRegistry, job_id: str) -> dict[str, Any]:
    try:
        status = job_registry.status(job_id)
    except KeyError:
        return {"present": False}
    return {
        "present": True,
        "alive": status.alive,
        "exit_code": status.exit_code,
        "pid": status.pid,
        "tail": status.tail,
    }


def _check_runs_in_workspace(result: Any, workspace_root: Path) -> bool:
    cwd = Path(str(getattr(result, "cwd", "") or "")).resolve(strict=False)
    try:
        cwd.relative_to(workspace_root.resolve(strict=False))
    except ValueError:
        return False
    return True


def _service_pid(entry: Mapping[str, Any] | None) -> str | None:
    if not isinstance(entry, Mapping):
        return None
    value = entry.get("pid")
    if value is None:
        return None
    return str(value)


def _monitor_persistent_runtime(
    *,
    ctx: ExecutionContext,
    job_registry: JobRegistry,
    session_registry: SessionRegistry,
    job_ids: list[str],
    session_ids: list[str],
    claim_checks: list[str],
    check_results: list[Any],
    remaining_sec: float | None,
    start_snapshot: StateSnapshot,
) -> tuple[dict[str, Any], StateSnapshot]:
    if not _service_monitoring_candidate(
        job_ids=job_ids,
        session_ids=session_ids,
        claim_checks=claim_checks,
        snapshot=start_snapshot,
    ):
        return {"applies": False}, start_snapshot

    bounded_window = max(0, min(_SERVICE_MONITOR_WINDOW_SEC, int(remaining_sec or 0)))
    if bounded_window <= 0:
        return {
            "applies": True,
            "window_sec": 0,
            "summary": ["bounded monitoring window unavailable before deadline"],
        }, start_snapshot

    start_jobs = {job_id: _job_status_payload(job_registry, job_id) for job_id in job_ids}
    start_sessions = set(session_registry.list_session_ids())
    start_services = getattr(start_snapshot, "service_registry", {}) or {}
    time.sleep(bounded_window)
    end_snapshot = delta_snapshot(ctx.workspace_root)
    end_snapshot = with_evidence_ledger(end_snapshot, getattr(start_snapshot, "evidence_ledger", {}))
    end_jobs = {job_id: _job_status_payload(job_registry, job_id) for job_id in job_ids}
    end_sessions = set(session_registry.list_session_ids())
    end_services = getattr(end_snapshot, "service_registry", {}) or {}

    summary: list[str] = []
    jobs_payload: dict[str, Any] = {}
    for job_id in job_ids:
        before = start_jobs.get(job_id, {"present": False})
        after = end_jobs.get(job_id, {"present": False})
        start_log_size = int(((getattr(start_snapshot, "job_registry", {}) or {}).get(job_id, {}) or {}).get("log_size", 0))
        end_log_size = int(((getattr(end_snapshot, "job_registry", {}) or {}).get(job_id, {}) or {}).get("log_size", 0))
        log_growth = max(0, end_log_size - start_log_size)
        jobs_payload[job_id] = {
            "start": before,
            "end": after,
            "log_growth_bytes": log_growth,
        }
        if before.get("alive") and after.get("alive"):
            summary.append(f"job {job_id} still running after {bounded_window}s bounded window")
        elif before.get("alive") and not after.get("alive"):
            summary.append(
                f"job {job_id} exited before end of {bounded_window}s bounded window exit code={after.get('exit_code')}"
            )
        if before.get("pid") and after.get("pid") and before.get("pid") != after.get("pid"):
            summary.append(
                f"job {job_id} pid changed from {before.get('pid')} to {after.get('pid')} after {bounded_window}s bounded window"
            )
        if log_growth:
            summary.append(f"job {job_id} log grew by {log_growth} bytes during bounded window")
        tail = str(after.get("tail", "") or "").lower()
        if any(token in tail for token in ("error", "traceback", "exception")):
            summary.append(f"job {job_id} produced new error output during bounded window")

    sessions_payload: dict[str, Any] = {}
    for session_id in session_ids:
        present_before = session_id in start_sessions
        present_after = session_id in end_sessions
        sessions_payload[session_id] = {"start_present": present_before, "end_present": present_after}
        if present_before and present_after:
            summary.append(f"session {session_id} remained registered after {bounded_window}s bounded window")
        elif present_before and not present_after:
            summary.append(f"session {session_id} disappeared before end of {bounded_window}s bounded window")

    services_payload: dict[str, Any] = {}
    for service_id in sorted(set(start_services) | set(end_services)):
        before = start_services.get(service_id)
        after = end_services.get(service_id)
        services_payload[service_id] = {"start": before, "end": after}
        before_pid = _service_pid(before)
        after_pid = _service_pid(after)
        if before is not None and after is not None and before_pid and after_pid and before_pid != after_pid:
            summary.append(
                f"service {service_id} pid changed from {before_pid} to {after_pid} after {bounded_window}s bounded window"
            )
        elif before is not None and after is not None:
            summary.append(f"service {service_id} remained registered after {bounded_window}s bounded window")
        elif before is not None and after is None:
            summary.append(f"service {service_id} disappeared before end of {bounded_window}s bounded window")

    same_workspace_probes = bool(check_results) and all(
        _check_runs_in_workspace(result, ctx.workspace_root) for result in check_results
    )
    if check_results:
        if same_workspace_probes:
            summary.append("client probes ran from the same workspace root")
        else:
            summary.append("client probes did not run from the same workspace root")
        if any(bool(getattr(result, "timed_out", False)) for result in check_results):
            summary.append("client probe timed out during bounded monitoring window")
        successful_outputs = [
            str(getattr(result, "stdout", "") or "").strip()
            for result in check_results
            if getattr(result, "exit_code", None) == 0 and str(getattr(result, "stdout", "") or "").strip()
        ]
        if len(successful_outputs) >= 2 and len(set(successful_outputs)) == 1:
            summary.append("repeated client probes returned the same response body across the bounded window")

    if not summary:
        summary.append(f"bounded monitoring observed no decisive service or persistence change over {bounded_window}s")

    return {
        "applies": True,
        "window_sec": bounded_window,
        "jobs": jobs_payload,
        "sessions": sessions_payload,
        "services": services_payload,
        "summary": summary,
    }, end_snapshot


def _env_contract_metadata(snapshot: Mapping[str, Any]) -> dict[str, str | None]:
    version = snapshot.get("env_contract_version")
    digest = snapshot.get("env_contract_digest")
    return {
        "version": str(version) if isinstance(version, str) and version else None,
        "digest": str(digest) if isinstance(digest, str) and digest else None,
    }


def _env_contract_drift(
    orientation_snapshot: Mapping[str, Any],
    verification_snapshot: Mapping[str, Any],
) -> dict[str, Any]:
    orientation_meta = _env_contract_metadata(orientation_snapshot)
    verification_meta = _env_contract_metadata(verification_snapshot)
    differences: list[str] = []
    if orientation_meta["version"] != verification_meta["version"]:
        differences.append("contract_version_changed")
    if orientation_meta["digest"] != verification_meta["digest"]:
        differences.append("contract_digest_changed")
    return {
        "orientation": orientation_meta,
        "verification": verification_meta,
        "drift_detected": bool(differences),
        "differences": differences,
    }


__all__ = ["ExecutionContext", "RunResult", "ToolInvocationRecord", "run_aether2_loop"]
