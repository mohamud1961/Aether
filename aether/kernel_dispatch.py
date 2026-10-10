"""Solver action dispatch: executes one action via kernel-owned engines.

Extracted from kernel.py to honor the 500-LOC module cap.  ``kernel`` is the
AetherNextKernel instance supplying the engines (failure parser, integrity
guards, bootstrap/process/perception/experiment lanes).
"""
from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import json
import re
import time
import uuid
from typing import Any, Mapping

from .artifact_transform import execute_artifact_transform
from .edit_file_exec import execute_edit_file
from .env_lean import LEAN_V2 as ENV_LEAN_V2, actionable_error_hint
from .environment_extension_execution import execute_environment_extension
from .execution import (
    CommandResult,
    Executor,
    _delta_proves_no_workspace_change,
    run_stateful_command,
)
from .ledger import ExecutionLedger, Receipt
from .completion_record import update_completion_record_receipt
from .native_primary_perception import stage_same_primary_native_image
from .perception_vision import needs_vision, vision_transcribe_receipt
from .runtime_ir import ActionRequest, CompiledRuntime, EnvMap, normalize_relpath
from .run_cancellation import cancellation_requested
from .run_deadline import remaining_run_s
from .shell_state import persistent_shell_command
from .surface_capture import execute_surface_capture


def _resolved_display_path(path: str, workspace_root: str) -> str:
    root = str(workspace_root or "").rstrip("/") or "/"
    relative = str(path or "")
    if relative in ("", "."):
        return root
    return root.rstrip("/") + "/" + relative


def _with_receipt_integrity(kernel: Any, compiled: CompiledRuntime, receipt: Receipt) -> Receipt:
    guard = getattr(kernel, "integrity_guards", None)
    if guard is None:
        return receipt
    payload = dict(receipt.payload or {})
    state_delta = payload.get("state_delta")
    if isinstance(state_delta, Mapping):
        # Terminal and remote-executor receipts may carry the mechanical delta
        # only inside state_delta. Project it into the standard receipt path
        # fields before integrity/WorldState processing so all action frontiers
        # share one evidence vocabulary.
        if not payload.get("modified_paths"):
            payload["modified_paths"] = tuple(sorted(set(
                tuple(state_delta.get("content_changed_paths", ()) or ())
                + tuple(state_delta.get("metadata_changed_paths", ()) or ())
            )))
        if not payload.get("artifact_paths"):
            payload["artifact_paths"] = tuple(state_delta.get("created_paths", ()) or ())
        if not payload.get("removed_paths"):
            payload["removed_paths"] = tuple(state_delta.get("removed_paths", ()) or ())
    observation_check = getattr(guard, "validate_state_observation", None)
    violation = (
        observation_check(compiled.objective_graph, state_delta)
        if callable(observation_check) else None
    )
    changed_paths = (
        tuple(payload.get("modified_paths", ()) or ())
        + tuple(payload.get("artifact_paths", ()) or ())
        + tuple(payload.get("removed_paths", ()) or ())
    )
    if not violation and changed_paths:
        violation = guard.validate_modified_paths(
            compiled.objective_graph, changed_paths,
        )
    if violation:
        payload["integrity_violation"] = violation
    if payload == dict(receipt.payload or {}):
        return receipt
    return replace(receipt, payload=payload)


def _opaque_task_world_receipt(
    receipt: Receipt, *, scope: str,
) -> Receipt:
    """Mark a selected-Thin action boundary whose effects exceed workspace tracking.

    Preserve every concrete workspace delta while conservatively declaring the
    whole task-world mutation observation coarse. This is epistemic invalidation,
    not fabricated progress or a claim that a concrete external mutation occurred.
    """
    payload = dict(receipt.payload or {})
    delta = dict(payload.get("state_delta", {}) or {})
    workspace_status = str(delta.get("mutation_detection_status", "")).strip()
    if workspace_status:
        delta["workspace_mutation_detection_status"] = workspace_status
    delta["mutation_detection_status"] = "coarse"
    delta["mutation_detection_scope"] = scope
    payload["state_delta"] = delta
    return replace(receipt, payload=payload)


_VERIFICATION_COMMAND_RE = re.compile(
    r"(?ix)"
    r"(?:\bpytest\b|\bunittest\b|\bctest\b|\bcargo\s+test\b|"
    r"\bgo\s+test\b|\b(?:npm|pnpm|yarn)\s+(?:run\s+)?test\b|"
    r"public[_-]?smoke(?:\.py)?|smoke[_-]?test|"
    r"\b(?:verify|validate|check)\.py\b|"
    r"\b(?:verify|validate|check)[_-][A-Za-z0-9_.-]+\.py\b|"
    r"test_[A-Za-z0-9_.-]+\.py)"
)
_STRONG_FAILURE_OUTPUT_RE = re.compile(
    r"(?im)"
    r"(?:^Traceback \(most recent call last\):|"
    r"\bAssertionError\b|\bSyntaxError\s*:|"
    r"^FAILED(?:\s|$)|"
    r"^FAIL(?:ED)?\s*[:(]|"
    r"\bexit\s*=\s*[1-9][0-9]*\b|"
    r"\breturncode\s*=\s*[1-9][0-9]*\b)"
)
_UNGUARDED_PIPE_RE = re.compile(r"(?<!\|)\|(?!\|)")
_MASKING_SEQUENCE_RE = re.compile(
    r";\s*(?:echo\b|true\b|exit\s+0\b)",
    re.IGNORECASE,
)


def is_verification_command(command: str) -> bool:
    """Return whether a shell command mechanically looks like verification."""
    return bool(_VERIFICATION_COMMAND_RE.search(str(command or "")))


def has_failure_signature(text: str) -> bool:
    """Return whether command output carries a strong mechanical failure marker."""
    return bool(_STRONG_FAILURE_OUTPUT_RE.search(str(text or "")))


def _verification_completion_evidence_risk(
    command: str,
    *,
    stdout: str,
    stderr: str,
    success: bool,
) -> str:
    """Return why a successful shell result is unsafe as completion proof.

    The command receipt remains a successful observation of shell behavior. This
    only prevents a masked verification status from being cited as proof that
    the task is complete.
    """
    if not success:
        return ""
    command_text = str(command or "")
    output_text = f"{stdout or ''}\n{stderr or ''}"
    if _STRONG_FAILURE_OUTPUT_RE.search(output_text):
        return "successful_shell_contains_failure_signature"
    if not is_verification_command(command_text):
        return ""
    if "||" in command_text:
        return "verification_exit_status_masked_by_or"
    if _UNGUARDED_PIPE_RE.search(command_text) and "pipefail" not in command_text:
        return "verification_exit_status_masked_by_pipeline"
    if _MASKING_SEQUENCE_RE.search(command_text):
        return "verification_exit_status_masked_by_sequence"
    return ""


def _shell_state_id(kernel: Any) -> str:
    """One persistent-shell state directory name per kernel (run)."""
    state_id = getattr(kernel, "_persistent_shell_state_id", "")
    if not state_id:
        state_id = "r" + uuid.uuid4().hex[:16]
        kernel._persistent_shell_state_id = state_id
    return state_id


def _head_tail(text: str, cap: int) -> str:
    """Return a marked head+tail excerpt without destroying full payloads."""
    if len(text) <= cap:
        return text
    half = max(1, cap // 2)
    omitted = len(text) - (half * 2)
    return text[:half] + f"\n... [omitted {omitted} chars; full output available by handle]\n" + text[-half:]



def _action_timeout_s(action: ActionRequest, envmap: EnvMap) -> tuple[int, str]:
    """Bound solver-requested command timeout by generic task budget metadata.

    The solver may request a longer timeout for builds/training/service setup,
    and explicit task timeout metadata is the ceiling authority. Task metadata
    comes from task.toml when available; this is generic budget information, not
    hidden grader logic. Metadata-poor environments retain the 300-second
    mechanical fallback rather than inventing task knowledge.
    """
    requested_raw = action.arguments.get("timeout_s", None)
    default_timeout = 30
    metadata = envmap.task_metadata if isinstance(envmap.task_metadata, Mapping) else {}
    budget = metadata.get("resource_budget") if isinstance(metadata.get("resource_budget"), Mapping) else {}
    timeout_candidates = [300]
    for key in ("agent_timeout_sec", "timeout_sec", "verifier_timeout_sec"):
        value = budget.get(key) or metadata.get(key)
        try:
            if value is not None:
                timeout_candidates.append(max(30, int(float(value))))
        except (TypeError, ValueError):
            pass
    max_timeout = max(timeout_candidates)
    if requested_raw is None:
        return default_timeout, f"default={default_timeout}; max_available={max_timeout}"
    try:
        requested = int(float(requested_raw))
    except (TypeError, ValueError):
        return default_timeout, f"invalid_requested={requested_raw!r}; default={default_timeout}; max_available={max_timeout}"
    if requested <= 0:
        return default_timeout, f"nonpositive_requested={requested}; default={default_timeout}; max_available={max_timeout}"
    effective = min(requested, max_timeout)
    return effective, f"requested={requested}; effective={effective}; max_available={max_timeout}"


def dispatch_action(kernel: Any, action: ActionRequest, step: int, compiled: CompiledRuntime,
                executor: Executor, envmap: EnvMap, ledger: ExecutionLedger) -> list[Receipt]:
    """Execute one solver action through the kernel-owned engines and return receipts."""
    kind = action.kind
    if kind == "read_file":
        path = normalize_relpath(str(action.arguments.get("path", "")), envmap.workspace_root)
        resolved_path = _resolved_display_path(path, envmap.workspace_root)
        base = {
            "path": path,
            "resolved_path": resolved_path,
            "candidate_id": action.candidate_id,
        }
        try:
            content = executor.read_file(path)
            payload = dict(base)
            payload.update({
                "content_sha256": sha256(content.encode("utf-8", "replace")).hexdigest(),
                "content_sha256_provenance": "captured_bytes",
                "bytes": len(content.encode("utf-8", "replace")),
                "chars": len(content),
                "content": content,
                "excerpt": _head_tail(content, 4000),
                "file_handle": f"file:{path}",
            })
            return [Receipt(
                receipt_id=f"step-{step}:{action.action_id}:read", step=step,
                kind="read_file", success=True,
                summary=f"read {path} ({len(content)} bytes)", payload=payload,
            )]
        except FileNotFoundError:
            return [Receipt(
                receipt_id=f"step-{step}:{action.action_id}:read", step=step,
                kind="read_file", success=False,
                summary=f"file not found: {_resolved_display_path(path, envmap.workspace_root)}",
                failure_class="missing_artifact", payload=base,
            )]
    if kind == "read_file_page":
        path = normalize_relpath(str(action.arguments.get("path", "")), envmap.workspace_root)
        try:
            content = executor.read_file(path)
            offset = max(0, int(action.arguments.get("offset", 0) or 0))
            span = max(1, min(20000, int(action.arguments.get("span", 8000) or 8000)))
            chunk = content[offset: offset + span]
            total_chars = len(content)
            return [Receipt(
                receipt_id=f"step-{step}:{action.action_id}:read_page",
                step=step, kind="read_file_page", success=True,
                summary=f"read {path} characters {offset}:{offset + len(chunk)}",
                payload={
                    "path": path,
                    "resolved_path": _resolved_display_path(path, envmap.workspace_root),
                    "offset": offset, "span": span,
                    "paging_unit": "characters",
                    "total_chars": total_chars,
                    "returned_chars": len(chunk),
                    "bytes": len(content.encode("utf-8", "replace")),
                    "more_available": offset + len(chunk) < total_chars,
                    "chunk": chunk, "file_handle": f"file:{path}",
                },
            )]
        except FileNotFoundError:
            return [Receipt(
                receipt_id=f"step-{step}:{action.action_id}:read_page", step=step,
                kind="read_file_page", success=False,
                summary=f"file not found: {_resolved_display_path(path, envmap.workspace_root)}",
                failure_class="missing_artifact",
                payload={
                    "path": path,
                    "resolved_path": _resolved_display_path(path, envmap.workspace_root),
                },
            )]
    if kind in {"read_output", "grep_output"}:
        handle = str(action.arguments.get("handle", "")).strip()
        pattern = str(action.arguments.get("pattern", ""))
        full = ""
        source_receipt = ""
        stream = ""
        overflow = ""
        if handle.startswith("receipt:"):
            target_receipt_id = handle.split(":", 1)[1]
            target = next((
                receipt for receipt in ledger.all_receipts()
                if receipt.receipt_id == target_receipt_id
            ), None)
            if target is not None:
                full = json.dumps({
                    "receipt_id": target.receipt_id,
                    "step": target.step,
                    "kind": target.kind,
                    "success": target.success,
                    "summary": target.summary,
                    "state_change": target.state_change,
                    "failure_class": target.failure_class,
                    "payload": target.payload,
                }, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
                source_receipt = target.receipt_id
                stream = "receipt"
        for receipt in ledger.all_receipts():
            payload = receipt.payload or {}
            if source_receipt:
                break
            if payload.get("stdout_handle") == handle:
                full = str(payload.get("stdout_full", "")); source_receipt = receipt.receipt_id; stream = "stdout"
                overflow = str(payload.get("stdout_overflow_path", ""))
                break
            if payload.get("stderr_handle") == handle:
                full = str(payload.get("stderr_full", "")); source_receipt = receipt.receipt_id; stream = "stderr"
                overflow = str(payload.get("stderr_overflow_path", ""))
                break
        if source_receipt and overflow:
            # The complete stream was spooled to disk; serve from the spool
            # so paging/grep operate on the full untruncated output.
            try:
                with open(overflow, encoding="utf-8", errors="replace") as fh:
                    full = fh.read()
            except OSError as exc:
                return [Receipt(
                    receipt_id=f"step-{step}:{action.action_id}:output", step=step,
                    kind=kind, success=False,
                    summary=f"output spool unreadable for handle {handle}: {exc}",
                    failure_class="missing_context_handle",
                    payload={"handle": handle, "overflow_path": overflow},
                )]
        if not source_receipt:
            return [Receipt(
                receipt_id=f"step-{step}:{action.action_id}:output", step=step,
                kind=kind, success=False, summary=f"output handle not found: {handle}",
                failure_class="missing_context_handle", payload={"handle": handle},
            )]
        if kind == "grep_output":
            lines = [line for line in full.splitlines() if pattern in line]
            selected = lines[:200]
            chunk = "\n".join(selected)
            summary = (
                f"grep_output {handle!r} pattern={pattern!r}: "
                f"returned {len(selected)}/{len(lines)} matching lines"
            )
            payload = {
                "handle": handle, "pattern": pattern, "matches": len(lines),
                "returned_matches": len(selected), "match_cap": 200,
                "more_available": len(selected) < len(lines),
                "coverage": "first_matching_lines_in_stream_order",
                "chunk": chunk, "source_receipt_id": source_receipt, "stream": stream,
            }
        else:
            offset = max(0, int(action.arguments.get("offset", 0) or 0))
            span = max(1, min(20000, int(action.arguments.get("span", 8000) or 8000)))
            chunk = full[offset: offset + span]
            total_chars = len(full)
            summary = f"read_output {handle!r} characters {offset}:{offset + len(chunk)}"
            payload = {
                "handle": handle, "offset": offset, "span": span,
                "paging_unit": "characters", "total_chars": total_chars,
                "returned_chars": len(chunk),
                "bytes": len(full.encode("utf-8", "replace")),
                "more_available": offset + len(chunk) < total_chars,
                "chunk": chunk, "source_receipt_id": source_receipt, "stream": stream,
            }
        return [Receipt(
            receipt_id=f"step-{step}:{action.action_id}:output", step=step, kind=kind, success=True, summary=summary, payload=payload,
        )]
    if kind == "report_blocker":
        payload = {
            "blocker": str(action.arguments.get("blocker", "")),
            "evidence": str(action.arguments.get("evidence", "")),
            "candidate_id": action.candidate_id,
        }
        for optional_key in ("harness_constraint", "possible_missing_capability"):
            optional_value = str(action.arguments.get(optional_key, "")).strip()
            if optional_value:
                payload[optional_key] = optional_value
        return [Receipt(
            receipt_id=f"step-{step}:{action.action_id}:blocker", step=step,
            kind="report_blocker", success=False,
            summary=f"solver reported blocker: {payload['blocker']}",
            failure_class="solver_reported_blocker", payload=payload,
        )]
    if kind == "computer_action":
        requested_actions = [dict(row) for row in (action.arguments.get("actions") or ())]
        requested = {"actions": requested_actions}
        receipt_id = f"step-{step}:{action.action_id}:computer"
        available = getattr(executor, "computer_available", None)
        execute = getattr(executor, "computer_action", None)
        if not callable(available) or not available() or not callable(execute):
            return [Receipt(
                receipt_id=receipt_id, step=step, kind="computer_action", success=False,
                summary="computer backend unavailable in current task environment",
                failure_class="missing_capability", payload=requested,
            )]
        result = execute(requested)
        raw = bytes(getattr(result, "screenshot_bytes", b"") or b"")
        state_change_requested = any(
            str(row.get("type") or "") not in {"screenshot", "wait"}
            for row in requested_actions
        )
        if not raw:
            return [Receipt(
                receipt_id=receipt_id, step=step, kind="computer_action", success=False,
                summary="computer call returned no fresh screenshot",
                state_change=bool(getattr(result, "success", False) and state_change_requested),
                failure_class="missing_computer_observation",
                payload={**requested, "detail": str(getattr(result, "detail", ""))},
            )]
        digest = sha256(raw).hexdigest()
        hooks = getattr(kernel, "active_hooks", None)
        stage = getattr(hooks, "stage_primary_computer_observation", None)
        staged = bool(callable(stage) and stage(
            screenshot_bytes=raw, media_type=str(getattr(result, "media_type", "image/png") or "image/png"),
            screenshot_sha256=digest, source_receipt_id=receipt_id, action=requested,
        ))
        state_change = bool(getattr(result, "success", False) and state_change_requested)
        payload = {
            **requested,
            "computer_action_count": len(requested_actions),
            "computer_action_types": [str(row.get("type") or "") for row in requested_actions],
            "screenshot_sha256": digest,
            "screenshot_bytes": len(raw),
            "screenshot_media_type": str(getattr(result, "media_type", "image/png") or "image/png"),
            "screenshot_width": getattr(result, "width", None),
            "screenshot_height": getattr(result, "height", None),
            "screenshot_staged_to_same_primary": staged,
            "fresh_post_action_screenshot": True,
            "detail": str(getattr(result, "detail", "")),
            "state_delta": dict(getattr(result, "state_delta", {}) or {}),
        }
        success = bool(getattr(result, "success", False) and staged)
        return [Receipt(
            receipt_id=receipt_id, step=step, kind="computer_action", success=success,
            summary=(f"computer call executed {len(requested_actions)} action(s) with fresh screenshot" if success
                     else "computer call observation could not be staged"),
            state_change=state_change,
            failure_class="" if success else ("computer_observation_staging_failed" if getattr(result, "success", False) else "computer_action_failed"),
            payload={k: v for k, v in payload.items() if v not in (None, "")},
        )]
    if kind == "edit_file":
        return execute_edit_file(action, step, executor, envmap)
    if kind == "write_file":
        path = normalize_relpath(str(action.arguments.get("path", "")), envmap.workspace_root)
        before_hash = ""
        before_bytes = None
        # Creation must not require a successful download/read of a path that
        # does not exist yet. Harbor's file transport reports missing remote
        # paths as a transport RuntimeError rather than FileNotFoundError, so
        # probe existence through the Executor contract before reading prior
        # content. Existing-file overwrites still retain exact before hashes.
        before_content = ""
        if executor.exists(path):
            before_content = executor.read_file(path)
            before_hash = sha256(before_content.encode("utf-8", "replace")).hexdigest()[:16]
            before_bytes = len(before_content)
        content = str(action.arguments.get("content", ""))
        executor.write_file(path, content)
        after_hash = sha256(content.encode("utf-8", "replace")).hexdigest()
        payload = {
            "path": path,
            "modified_paths": (path,),
            "artifact_paths": (path,),
            "candidate_id": action.candidate_id,
            "before_content_hash": before_hash,
            "after_content_hash": after_hash,
            "content_sha256": after_hash,
            "content_sha256_provenance": "captured_bytes",
            "before_bytes": before_bytes,
            "bytes": len(content.encode("utf-8", "replace")),
            "chars": len(content),
            "content": content,
            "excerpt": _head_tail(content, 4000),
            "file_handle": f"file:{path}",
        }
        return [Receipt(
            receipt_id=f"step-{step}:{action.action_id}:write", step=step,
            kind="write_file", success=True, summary=f"wrote {path}", state_change=True,
            payload={k: v for k, v in payload.items() if v is not None and v != ""},
        )]
    if kind == "run_command":
        command = str(action.arguments.get("command", ""))
        timeout_s, timeout_note = _action_timeout_s(action, envmap)
        background_job_result: CommandResult | None = None
        background_job_metadata: dict[str, Any] = {}
        background_job_overflow_receipts: list[Receipt] = []
        if "capture_surface" in action.arguments:
            return [execute_surface_capture(
                kernel, action, step, compiled, executor, envmap,
                timeout_s=timeout_s, timeout_note=timeout_note,
            )]
        provenance_fields = {"source_path", "output_path"} & set(action.arguments)
        if provenance_fields:
            return [execute_artifact_transform(
                kernel, action, step, compiled, executor, envmap,
                timeout_s=timeout_s, timeout_note=timeout_note,
            )]
        if "extension_server" in action.arguments or "extension_operation" in action.arguments:
            receipt = execute_environment_extension(
                action, step, executor, envmap,
                timeout_s=timeout_s, timeout_note=timeout_note,
            )
            return [_with_receipt_integrity(kernel, compiled, receipt)]
        if str((compiled.config_realization or {}).get("solver_long_command_mode", "control")) == "background_v1":
            # Start through the same registered executor path as start_job before
            # waiting. A timeout therefore detaches this exact process generation.
            started = time.monotonic()
            overflow_receipts: list[Receipt] = []
            jobs = getattr(kernel, "_long_command_jobs", None)
            if jobs is None:
                jobs = []
                kernel._long_command_jobs = jobs
            live_jobs = []
            for job_id in list(jobs):
                probe_live = executor.probe_job(job_id)
                if probe_live.found and not probe_live.completed:
                    live_jobs.append(job_id)
            if len(live_jobs) >= 4:
                oldest = live_jobs[0]
                stopped = executor.stop_process(oldest)
                after_stop = executor.probe_job(oldest)
                if not after_stop.found or not after_stop.completed:
                    failure = Receipt(
                        receipt_id=f"step-{step}:{action.action_id}:job_limit_stop_failed",
                        step=step, kind="process_launch", success=False,
                        summary=f"cannot launch a fifth job: stopping oldest job {oldest} was not verified",
                        failure_class="background_job_limit_cleanup_failed",
                        payload={"job_id": oldest, "stop_requested": bool(stopped),
                            "status_after": after_stop.status, "exit_code": after_stop.exit_code,
                            "task_action_dispatched": False},
                    )
                    return [_with_receipt_integrity(kernel, compiled, failure)]
                overflow_receipts.append(Receipt(
                    receipt_id=f"step-{step}:{action.action_id}:oldest_job_stopped",
                    step=step, kind="job_stop", success=bool(after_stop.found and after_stop.completed),
                    summary=f"stopped oldest background job {oldest} to enforce four-live-job limit",
                    payload={"job_id": oldest, "reason": "max_live_jobs", "stop_requested": bool(stopped),
                        "status_after": after_stop.status, "exit_code": after_stop.exit_code},
                ))
                if oldest in jobs:
                    jobs.remove(oldest)
            job_command = command
            if (compiled.config_realization or {}).get("solver_persistent_shell"):
                # Same wrapper as the normal path. The wrapper's EXIT trap saves
                # cwd/env state when the job process exits, so a job that
                # detaches saves its state only on eventual exit (acceptable).
                job_command = persistent_shell_command(command, state_id=_shell_state_id(kernel))
            launch_action = replace(
                action, kind="start_job",
                arguments={"service_name": f"command-{action.action_id}", "command": job_command},
            )
            launch = kernel.process_orchestrator.launch(
                launch_action, step, executor,
                workspace_root=envmap.workspace_root, interactive=False,
            )
            if not launch.success:
                return [*(_with_receipt_integrity(kernel, compiled, item) for item in overflow_receipts), _with_receipt_integrity(kernel, compiled, launch)]
            process_id = str((launch.payload or {}).get("process_id") or "")
            if not process_id:
                failed = replace(
                    launch, success=False,
                    summary="managed command launch returned no registered process id",
                    failure_class="process_launch_identity_missing",
                    payload={**dict(launch.payload or {}), "task_action_dispatched": False},
                )
                return [*(_with_receipt_integrity(kernel, compiled, item) for item in overflow_receipts), _with_receipt_integrity(kernel, compiled, failed)]
            jobs.append(process_id)
            executor_jobs = getattr(executor, "_aether_long_command_jobs", None)
            if executor_jobs is None:
                executor_jobs = []
                setattr(executor, "_aether_long_command_jobs", executor_jobs)
            executor_jobs.append(process_id)
            deadline = started + timeout_s
            probe = executor.probe_job(process_id)
            poll_interval_s = 0.05
            while probe.found and not probe.completed and time.monotonic() < deadline:
                cancellation = getattr(
                    kernel, "_cancellation_event", getattr(kernel, "cancellation_event", None),
                )
                remaining = remaining_run_s()
                if cancellation_requested(cancellation) or (remaining is not None and remaining <= 0):
                    break
                poll_s = min(poll_interval_s, max(0.0, deadline - time.monotonic()))
                if remaining is not None:
                    poll_s = min(poll_s, remaining)
                time.sleep(poll_s)
                # Backoff keeps remote (Harbor docker exec) probes cheap.
                poll_interval_s = min(1.0, poll_interval_s * 2)
                probe = executor.probe_job(process_id)
            elapsed = max(0.0, time.monotonic() - started)
            output_reader = getattr(executor, "job_output", None)
            full_reader = getattr(executor, "job_output_full", None)
            completed_job = bool(probe.found and probe.completed)
            if completed_job and callable(full_reader):
                # Completed within its timeout: return what the control path
                # would (full stream under the normal cap/spool policy).
                output = full_reader(process_id)
            else:
                # Still running / detached (or executor lacks full retrieval):
                # bounded tail only.
                output = output_reader(process_id, tail_lines=40) if callable(output_reader) else {"stdout": "", "stderr": ""}
            if completed_job:
                observed_state = getattr(executor, "observe_process_state", None)
                job_delta = observed_state(process_id) if callable(observed_state) else {}
                background_job_result = CommandResult(
                    command=command,
                    exit_code=int(probe.exit_code),
                    stdout=output.get("stdout", ""), stderr=output.get("stderr", ""),
                    stdout_overflow_path=str(output.get("stdout_overflow_path", "") or ""),
                    stderr_overflow_path=str(output.get("stderr_overflow_path", "") or ""),
                    stdout_bytes_total=int(output.get("stdout_bytes_total", -1)),
                    stderr_bytes_total=int(output.get("stderr_bytes_total", -1)),
                    state_delta=job_delta,
                    metrics={"managed_job_elapsed_s": elapsed},
                )
                background_job_metadata = {
                    "job_id": process_id, "job_status": probe.status,
                    "managed_job_elapsed_s": elapsed,
                }
                if process_id in jobs:
                    jobs.remove(process_id)
                if process_id in getattr(executor, "_aether_long_command_jobs", ()):
                    executor._aether_long_command_jobs.remove(process_id)
                # Fall through the common run_command receipt builder. Besides
                # preserving one accounting path, this keeps later opt-in
                # result enrichments (for example lean environment hints)
                # available when treatment branches are composed.
                background_job_overflow_receipts = overflow_receipts
            else:
                detached = replace(
                    launch,
                    summary=(f"command is still running as job {process_id} after {elapsed:.1f}s; "
                        f"check with job_output/job_wait and stop with job_stop"),
                    payload={**dict(launch.payload or {}), "command": command,
                        "job_status": "running", "exit_code": None,
                        "elapsed_s": elapsed, "stdout_tail": output.get("stdout", ""),
                        "stderr_tail": output.get("stderr", ""),
                        "how_to_check": f"job_output(job_id={process_id}) or job_wait(job_id={process_id}, timeout_s=...) ",
                        "how_to_stop": f"job_stop(job_id={process_id})"},
                )
                return [*(_with_receipt_integrity(kernel, compiled, item) for item in overflow_receipts), _with_receipt_integrity(kernel, compiled, detached)]
        exec_command = command
        if (compiled.config_realization or {}).get("solver_persistent_shell") and background_job_result is None:
            # Opt-in edit surface: cwd and exported variables persist across
            # commands; receipts and all analysis below keep the user's command.
            exec_command = persistent_shell_command(command, state_id=_shell_state_id(kernel))
        result = background_job_result or run_stateful_command(
            executor, exec_command, cwd=envmap.workspace_root, timeout_s=timeout_s
        )
        failure_class = kernel.failure_parser.classify(
            result.stdout + "\n" + result.stderr,
            exit_code=result.exit_code,
        ) if not result.success else ""
        changed_paths = (
            tuple(result.modified_paths)
            + tuple(result.produced_artifacts)
            + tuple(result.removed_paths)
        )
        integrity_violation = kernel.integrity_guards.validate_modified_paths(
            compiled.objective_graph, changed_paths,
        )
        observation_check = getattr(kernel.integrity_guards, "validate_state_observation", None)
        if not integrity_violation and callable(observation_check):
            integrity_violation = observation_check(
                compiled.objective_graph, result.state_delta,
            )
        task_world_delta = dict(result.state_delta)
        # The tracked executor can make a complete claim only about its observed
        # workspace. An arbitrary shell command may also mutate task-visible
        # state outside that scope, so the whole task-world boundary remains
        # conservatively coarse until a later direct observation recovers it.
        workspace_status = str(
            task_world_delta.get("mutation_detection_status", "")
        ).strip()
        if workspace_status:
            task_world_delta["workspace_mutation_detection_status"] = workspace_status
        task_world_delta["mutation_detection_status"] = "coarse"
        task_world_delta["mutation_detection_scope"] = "opaque_run_command_task_world"
        verification_integrity_risk = _verification_completion_evidence_risk(
            command,
            stdout=result.stdout,
            stderr=result.stderr,
            success=result.success,
        )
        payload: dict[str, Any] = {
            "command": command,
            "timeout_s": timeout_s,
            "timeout_policy": timeout_note,
            "exit_code": result.exit_code,
            "stdout": _head_tail(result.stdout, 8000),
            "stderr": _head_tail(result.stderr, 8000),
            "stdout_full": result.stdout,
            "stderr_full": result.stderr,
            "stdout_handle": f"{step}:{action.action_id}:stdout",
            "stderr_handle": f"{step}:{action.action_id}:stderr",
            "stdout_bytes": result.stdout_bytes_total,
            "stderr_bytes": result.stderr_bytes_total,
            "stdout_overflow_path": result.stdout_overflow_path,
            "stderr_overflow_path": result.stderr_overflow_path,
            "timed_out": result.timed_out,
            "modified_paths": tuple(
                normalize_relpath(p, envmap.workspace_root) for p in result.modified_paths
            ),
            "artifact_paths": tuple(
                normalize_relpath(p, envmap.workspace_root) for p in result.produced_artifacts
            ),
            "removed_paths": tuple(
                normalize_relpath(p, envmap.workspace_root) for p in result.removed_paths
            ),
            "state_delta": task_world_delta,
            "candidate_id": action.candidate_id,
        }
        if background_job_metadata:
            payload.update(background_job_metadata)
        if verification_integrity_risk:
            payload["completion_evidence_eligible"] = False
            payload["verification_integrity_risk"] = verification_integrity_risk
        if integrity_violation:
            payload["integrity_violation"] = integrity_violation
        if result.metrics:
            # Preserve the complete mechanical executor metric map for run-level
            # latency/transport analysis. The legacy single metric fields remain
            # for existing ledger consumers and are intentionally unchanged.
            payload["metrics"] = dict(result.metrics)
            first_key = sorted(result.metrics)[0]
            payload["metric_name"] = first_key
            payload["metric_value"] = result.metrics[first_key]
        summary = f"command exit={result.exit_code}: {command}"
        if (compiled.config_realization or {}).get("solver_env_mode") == ENV_LEAN_V2:
            environment_probe = (envmap.task_metadata or {}).get("environment_probe", {})
            if isinstance(environment_probe, Mapping):
                hint = actionable_error_hint(
                    exit_code=result.exit_code,
                    output=result.stdout + "\n" + result.stderr,
                    probe=environment_probe,
                    success=result.success,
                )
                if hint:
                    payload["actionable_error_hint"] = hint
        command_receipt = Receipt(
            receipt_id=f"step-{step}:{action.action_id}:cmd",
            step=step,
            kind="run_command",
            success=result.success,
            summary=summary,
            state_change=bool(
                result.modified_paths or result.produced_artifacts or result.removed_paths
            ),
            failure_class=failure_class,
            payload=payload,
        )
        return [*(_with_receipt_integrity(kernel, compiled, item) for item in background_job_overflow_receipts), command_receipt]
    if kind == "start_terminal_session":
        try:
            handle = executor.start_terminal_session(
                str(action.arguments.get("session_name", "terminal")),
                str(action.arguments.get("command", "")),
                cwd=str(action.arguments.get("cwd", envmap.workspace_root)),
            )
            delta = dict(handle.state_delta)
            receipt = Receipt(
                receipt_id=f"step-{step}:{action.action_id}:terminal_start",
                step=step, kind="terminal_start", success=handle.live,
                summary=f"started terminal session {handle.session_id}",
                state_change=bool(delta.get("created_paths") or delta.get("removed_paths") or delta.get("content_changed_paths") or delta.get("metadata_changed_paths")),
                failure_class="" if handle.live else "process_launch_failure",
                payload={
                    "session_id": handle.session_id, "name": handle.name,
                    "command": handle.command, "live": handle.live,
                    "pid": handle.pid, "start_time_ticks": handle.start_time_ticks,
                    "command_sha256": handle.command_sha256,
                    "process_generation": handle.process_generation,
                    "process_group_id": handle.process_group_id,
                    "session_leader_id": handle.session_leader_id,
                    "state_delta": delta, "candidate_id": action.candidate_id,
                },
            )
            receipt = _opaque_task_world_receipt(receipt, scope="opaque_terminal_task_world")
            return [_with_receipt_integrity(kernel, compiled, receipt)]
        except Exception as exc:
            return [Receipt(
                receipt_id=f"step-{step}:{action.action_id}:terminal_start",
                step=step, kind="terminal_start", success=False,
                summary=f"terminal start failed: {type(exc).__name__}: {exc}",
                failure_class="process_launch_failure",
                payload={"error_type": type(exc).__name__, "error": str(exc), "candidate_id": action.candidate_id},
            )]
    if kind == "terminal_send":
        try:
            state = executor.terminal_send(
                str(action.arguments.get("session_id", "")),
                str(action.arguments.get("data", "")),
                append_newline=bool(action.arguments.get("append_newline", True)),
            )
            delta = dict(state.state_delta)
            receipt = Receipt(
                receipt_id=f"step-{step}:{action.action_id}:terminal_send",
                step=step, kind="terminal_send", success=True,
                summary=f"sent {state.bytes_sent} bytes to {state.session_id}",
                state_change=bool(delta.get("created_paths") or delta.get("removed_paths") or delta.get("content_changed_paths") or delta.get("metadata_changed_paths")),
                payload={"session_id": state.session_id, "bytes_sent": state.bytes_sent, "live": state.live, "exit_code": state.exit_code, "cursor": state.cursor, "total_bytes": state.total_bytes, "process_generation": state.process_generation, "state_delta": delta, "candidate_id": action.candidate_id},
            )
            receipt = _opaque_task_world_receipt(receipt, scope="opaque_terminal_task_world")
            return [_with_receipt_integrity(kernel, compiled, receipt)]
        except Exception as exc:
            return [Receipt(receipt_id=f"step-{step}:{action.action_id}:terminal_send", step=step, kind="terminal_send", success=False, summary=f"terminal send failed: {type(exc).__name__}: {exc}", failure_class="service_not_ready", payload={"error_type": type(exc).__name__, "error": str(exc), "candidate_id": action.candidate_id})]
    if kind == "terminal_read":
        try:
            result = executor.terminal_read(
                str(action.arguments.get("session_id", "")),
                max_bytes=int(20_000 if action.arguments.get("max_bytes") is None else action.arguments.get("max_bytes")),
                wait_ms=int(1000 if action.arguments.get("wait_ms") is None else action.arguments.get("wait_ms")),
            )
            delta = dict(result.state_delta)
            receipt = Receipt(
                receipt_id=f"step-{step}:{action.action_id}:terminal_read",
                step=step, kind="terminal_read", success=True,
                summary=f"read {result.bytes_read} terminal bytes from {result.session_id}",
                state_change=bool(delta.get("created_paths") or delta.get("removed_paths") or delta.get("content_changed_paths") or delta.get("metadata_changed_paths")),
                payload={"session_id": result.session_id, "output": result.output, "bytes_read": result.bytes_read, "cursor": result.cursor, "total_bytes": result.total_bytes, "more_available": result.more_available, "live": result.live, "exit_code": result.exit_code, "process_generation": result.process_generation, "state_delta": delta, "candidate_id": action.candidate_id},
            )
            return [_with_receipt_integrity(kernel, compiled, receipt)]
        except Exception as exc:
            return [Receipt(receipt_id=f"step-{step}:{action.action_id}:terminal_read", step=step, kind="terminal_read", success=False, summary=f"terminal read failed: {type(exc).__name__}: {exc}", failure_class="service_not_ready", payload={"error_type": type(exc).__name__, "error": str(exc), "candidate_id": action.candidate_id})]
    if kind == "terminal_wait":
        try:
            state = executor.terminal_wait(
                str(action.arguments.get("session_id", "")),
                timeout_s=float(30 if action.arguments.get("timeout_s") is None else action.arguments.get("timeout_s")),
            )
            delta = dict(state.state_delta)
            receipt = Receipt(
                receipt_id=f"step-{step}:{action.action_id}:terminal_wait", step=step,
                kind="terminal_wait", success=True,
                summary=f"terminal wait {state.session_id}: {'live' if state.live else 'exited'}",
                state_change=bool(delta.get("created_paths") or delta.get("removed_paths") or delta.get("content_changed_paths") or delta.get("metadata_changed_paths")),
                payload={"session_id": state.session_id, "live": state.live, "exit_code": state.exit_code, "cursor": state.cursor, "total_bytes": state.total_bytes, "more_available": state.more_available, "process_generation": state.process_generation, "state_delta": delta, "candidate_id": action.candidate_id},
            )
            receipt = _opaque_task_world_receipt(receipt, scope="opaque_terminal_task_world")
            return [_with_receipt_integrity(kernel, compiled, receipt)]
        except Exception as exc:
            return [Receipt(receipt_id=f"step-{step}:{action.action_id}:terminal_wait", step=step, kind="terminal_wait", success=False, summary=f"terminal wait failed: {type(exc).__name__}: {exc}", failure_class="service_not_ready", payload={"error_type": type(exc).__name__, "error": str(exc), "candidate_id": action.candidate_id})]
    if kind == "terminal_interrupt":
        try:
            state = executor.terminal_interrupt(str(action.arguments.get("session_id", "")))
            delta = dict(state.state_delta)
            receipt = Receipt(
                receipt_id=f"step-{step}:{action.action_id}:terminal_interrupt", step=step,
                kind="terminal_interrupt", success=True,
                summary=f"sent SIGINT to terminal {state.session_id}",
                state_change=bool(delta.get("created_paths") or delta.get("removed_paths") or delta.get("content_changed_paths") or delta.get("metadata_changed_paths")),
                payload={"session_id": state.session_id, "signal": state.signal, "live": state.live, "exit_code": state.exit_code, "process_generation": state.process_generation, "state_delta": delta, "candidate_id": action.candidate_id},
            )
            receipt = _opaque_task_world_receipt(receipt, scope="opaque_terminal_task_world")
            return [_with_receipt_integrity(kernel, compiled, receipt)]
        except Exception as exc:
            return [Receipt(receipt_id=f"step-{step}:{action.action_id}:terminal_interrupt", step=step, kind="terminal_interrupt", success=False, summary=f"terminal interrupt failed: {type(exc).__name__}: {exc}", failure_class="service_not_ready", payload={"error_type": type(exc).__name__, "error": str(exc), "candidate_id": action.candidate_id})]
    if kind == "terminal_close":
        try:
            state = executor.terminal_close(str(action.arguments.get("session_id", "")))
            delta = dict(state.state_delta)
            receipt = Receipt(
                receipt_id=f"step-{step}:{action.action_id}:terminal_close", step=step,
                kind="terminal_close", success=not state.live,
                summary=f"closed terminal {state.session_id}",
                state_change=bool(delta.get("created_paths") or delta.get("removed_paths") or delta.get("content_changed_paths") or delta.get("metadata_changed_paths")),
                failure_class="" if not state.live else "service_not_ready",
                payload={"session_id": state.session_id, "live": state.live, "exit_code": state.exit_code, "process_generation": state.process_generation, "state_delta": delta, "candidate_id": action.candidate_id},
            )
            receipt = _opaque_task_world_receipt(receipt, scope="opaque_terminal_task_world")
            return [_with_receipt_integrity(kernel, compiled, receipt)]
        except Exception as exc:
            return [Receipt(receipt_id=f"step-{step}:{action.action_id}:terminal_close", step=step, kind="terminal_close", success=False, summary=f"terminal close failed: {type(exc).__name__}: {exc}", failure_class="service_not_ready", payload={"error_type": type(exc).__name__, "error": str(exc), "candidate_id": action.candidate_id})]
    if kind == "bootstrap_acquire":
        receipt, refreshed = kernel.bootstrap_engine.execute(action, step, executor, envmap)
        # Preserve the post-bootstrap factual EnvMap for the next model turn;
        # the old path discarded the refresh while retaining only the receipt.
        kernel._last_envmap_refresh = refreshed
        if receipt.success or receipt.state_change or isinstance((receipt.payload or {}).get("state_delta"), Mapping):
            receipt = _opaque_task_world_receipt(receipt, scope="opaque_bootstrap_task_world")
        return [_with_receipt_integrity(kernel, compiled, receipt)]
    if kind in {"launch_process", "start_job"}:
        async_mode = getattr(kernel, "solver_async_mode", "control")
        if kind == "start_job" and async_mode in {"serial_jobs_v1", "independent_jobs_v1"}:
            live_jobs = [
                item
                for item in ledger.live_processes().values()
                if str(item.get("launch_mode") or "") == "background_job"
            ]
            max_live_jobs = 1 if async_mode == "serial_jobs_v1" else 2
            if len(live_jobs) >= max_live_jobs:
                return [_with_receipt_integrity(kernel, compiled, Receipt(
                    receipt_id=f"step-{step}:{action.action_id}:async_concurrency_limit",
                    step=step,
                    kind="process_launch",
                    success=False,
                    summary=f"{async_mode} permits at most {max_live_jobs} live background job(s)",
                    failure_class="async_concurrency_limit",
                    payload={
                        "solver_async_mode": async_mode,
                        "max_live_background_jobs": max_live_jobs,
                        "current_live_background_job_ids": [
                            str(item.get("process_id") or "") for item in live_jobs
                        ],
                        "task_action_dispatched": False,
                    },
                ))]
        interactive = compiled.process_policy.mode == "interactive_detachable"
        receipt = kernel.process_orchestrator.launch(
            action, step, executor,
            workspace_root=envmap.workspace_root, interactive=interactive,
        )
        if receipt.success or receipt.state_change:
            receipt = _opaque_task_world_receipt(receipt, scope="opaque_process_task_world")
        return [_with_receipt_integrity(kernel, compiled, receipt)]
    if kind == "job_output":
        job_id = str(action.arguments.get("job_id", "")).strip()
        tail_lines = max(1, min(20, int(action.arguments.get("tail_lines", 20) or 20)))
        reader = getattr(executor, "job_output", None)
        output = reader(job_id, tail_lines=tail_lines) if callable(reader) else {"stdout": "", "stderr": ""}
        probe = executor.probe_job(job_id)
        receipt = Receipt(
            receipt_id=f"step-{step}:{action.action_id}:job_output", step=step,
            kind="job_output", success=probe.found,
            summary=f"read new output tail for job {job_id}",
            failure_class="job_not_found" if not probe.found else "",
            payload={"job_id": job_id, "job_status": probe.status,
                "exit_code": probe.exit_code, "stdout_tail": output.get("stdout", ""),
                "stderr_tail": output.get("stderr", ""), "tail_lines": tail_lines},
        )
        if probe.found and probe.completed:
            registry = getattr(kernel, "_long_command_terminal_reads", set())
            registry.add(job_id)
            kernel._long_command_terminal_reads = registry
            try:
                kernel._long_command_jobs.remove(job_id)
            except (ValueError, AttributeError):
                pass
            try:
                executor._aether_long_command_jobs.remove(job_id)
            except (ValueError, AttributeError):
                pass
        return [_with_receipt_integrity(kernel, compiled, receipt)]
    if kind == "job_wait":
        job_id = str(action.arguments.get("job_id", "")).strip()
        timeout_s = max(0.0, min(300.0, float(action.arguments.get("timeout_s", 0) or 0)))
        wait_started = time.monotonic()
        deadline = time.monotonic() + timeout_s
        probe = executor.probe_job(job_id)
        while probe.found and not probe.completed and time.monotonic() < deadline:
            cancellation = getattr(
                kernel, "_cancellation_event", getattr(kernel, "cancellation_event", None),
            )
            remaining = remaining_run_s()
            if cancellation_requested(cancellation) or (remaining is not None and remaining <= 0):
                break
            poll_s = min(0.1, max(0.0, deadline - time.monotonic()))
            if remaining is not None:
                poll_s = min(poll_s, remaining)
            time.sleep(poll_s)
            probe = executor.probe_job(job_id)
        reader = getattr(executor, "job_output", None)
        output = reader(job_id, tail_lines=20) if callable(reader) else {"stdout": "", "stderr": ""}
        receipt = Receipt(
            receipt_id=f"step-{step}:{action.action_id}:job_wait", step=step,
            kind="job_probe", success=probe.found,
            summary=f"job {job_id} is {probe.status}" + (f" (exit {probe.exit_code})" if probe.completed else ""),
            failure_class="job_not_found" if not probe.found else "",
            payload={"job_id": job_id, "target": job_id, "job_status": probe.status,
                "completed": probe.completed, "exit_code": probe.exit_code,
                "elapsed_s": max(0.0, time.monotonic() - wait_started), "stdout_tail": output.get("stdout", ""),
                "stderr_tail": output.get("stderr", "")},
        )
        if probe.found and probe.completed:
            registry = getattr(kernel, "_long_command_terminal_reads", set())
            registry.add(job_id)
            kernel._long_command_terminal_reads = registry
            try:
                kernel._long_command_jobs.remove(job_id)
            except (ValueError, AttributeError):
                pass
            try:
                executor._aether_long_command_jobs.remove(job_id)
            except (ValueError, AttributeError):
                pass
        return [_with_receipt_integrity(kernel, compiled, receipt)]
    if kind == "job_stop":
        job_id = str(action.arguments.get("job_id", "")).strip()
        receipt = kernel.process_orchestrator.stop(
            replace(action, kind="stop_process", arguments={"target": job_id}), step, executor,
        )
        payload = {**dict(receipt.payload or {}), "job_id": job_id}
        receipt = replace(receipt, kind="job_stop", payload=payload)
        return [_with_receipt_integrity(kernel, compiled, receipt)]
    if kind == "probe_job":
        receipt = kernel.process_orchestrator.probe_job(action, step, executor)
        return [_with_receipt_integrity(kernel, compiled, receipt)]
    if kind == "probe_service":
        receipt = kernel.process_orchestrator.probe(action, step, executor)
        return [_with_receipt_integrity(kernel, compiled, receipt)]
    if kind == "stop_process":
        receipt = kernel.process_orchestrator.stop(action, step, executor)
        state_delta = (receipt.payload or {}).get("state_delta")
        if receipt.state_change or (
            receipt.success
            and not _delta_proves_no_workspace_change(state_delta or {})
        ):
            receipt = _opaque_task_world_receipt(receipt, scope="opaque_process_task_world")
        return [_with_receipt_integrity(kernel, compiled, receipt)]
    if kind == "set_job_disposition":
        receipt = ledger.set_job_disposition(
            str(action.arguments.get("job_id", "")),
            str(action.arguments.get("relevance", "")),
            str(action.arguments.get("reason", "")),
            str(action.arguments.get("replacement_job_id", "") or "") or None,
            step=step,
            action_id=action.action_id,
            persist=False,
        )
        return [_with_receipt_integrity(kernel, compiled, receipt)]
    if kind == "update_completion_record":
        return [update_completion_record_receipt(
            ledger=ledger,
            expected_revision=action.arguments.get("expected_revision"),
            replacement_record=action.arguments.get("replacement_record"),
            task_text=compiled.task_prompt,
            step=step,
            action_id=action.action_id,
        )]
    if kind == "inspect_artifact":
        base = kernel.perception_lane.inspect(
            action, step, executor, workspace_root=envmap.workspace_root,
        )
        if needs_vision(base):
            native = stage_same_primary_native_image(
                kernel, action, step, executor, base,
            )
            if native is not None:
                return [native]
            vision = vision_transcribe_receipt(kernel, action, step, executor, base)
            if vision is not None:
                return [vision]
        return [base]
    if kind == "register_candidate":
        cid = str(action.arguments.get("candidate_id", "")).strip()
        return [Receipt(
            receipt_id=f"step-{step}:{action.action_id}:register", step=step,
            kind="register_candidate", success=True,
            summary=f"registered candidate {cid}", state_change=True,
            payload={"candidate_id": cid,
                     "candidate_summary": str(action.arguments.get("summary", "")).strip(),
                     "candidate_status": "active"},
        )]
    if kind == "run_experiment":
        receipt = kernel.experiment_engine.run(
            action, step, executor, workspace_root=envmap.workspace_root,
        )
        return [_with_receipt_integrity(kernel, compiled, receipt)]
    return [Receipt(
        receipt_id=f"step-{step}:{action.action_id}:unknown", step=step,
        kind="unknown_action", success=False,
        summary=f"unknown action kind: {kind}", failure_class="action_validation",
    )]
