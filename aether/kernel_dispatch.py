"""Solver action dispatch: executes one action via kernel-owned engines.

Extracted from kernel.py to honor the 500-LOC module cap.  ``kernel`` is the
AetherNextKernel instance supplying the engines (failure parser, integrity
guards, bootstrap/process/perception/experiment lanes).
"""
from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import json
from typing import Any, Mapping

from .artifact_transform import execute_artifact_transform
from .environment_extension_execution import execute_environment_extension
from .execution import Executor, run_stateful_command
from .ledger import ExecutionLedger, Receipt
from .native_primary_perception import stage_same_primary_native_image
from .perception_vision import needs_vision, vision_transcribe_receipt
from .runtime_ir import ActionRequest, CompiledRuntime, EnvMap, normalize_relpath
from .surface_capture import execute_surface_capture


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
        base = {"path": path, "candidate_id": action.candidate_id}
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
                kind="read_file", success=False, summary=f"file not found: {path}",
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
                    "path": path, "offset": offset, "span": span,
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
                kind="read_file_page", success=False, summary=f"file not found: {path}",
                failure_class="missing_artifact", payload={"path": path},
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
        result = run_stateful_command(
            executor, command, cwd=envmap.workspace_root, timeout_s=timeout_s
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
        if integrity_violation:
            payload["integrity_violation"] = integrity_violation
        if result.metrics:
            first_key = sorted(result.metrics)[0]
            payload["metric_name"] = first_key
            payload["metric_value"] = result.metrics[first_key]
        return [Receipt(
            receipt_id=f"step-{step}:{action.action_id}:cmd",
            step=step,
            kind="run_command",
            success=result.success,
            summary=f"command exit={result.exit_code}: {command}",
            state_change=bool(
                result.modified_paths or result.produced_artifacts or result.removed_paths
            ),
            failure_class=failure_class,
            payload=payload,
        )]
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
                max_bytes=int(action.arguments.get("max_bytes", 20_000) or 20_000),
                wait_ms=int(action.arguments.get("wait_ms", 1000) or 1000),
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
            state = executor.terminal_wait(str(action.arguments.get("session_id", "")), timeout_s=float(action.arguments.get("timeout_s", 30) or 30))
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
        interactive = compiled.process_policy.mode == "interactive_detachable"
        receipt = kernel.process_orchestrator.launch(
            action, step, executor,
            workspace_root=envmap.workspace_root, interactive=interactive,
        )
        if receipt.success or receipt.state_change:
            receipt = _opaque_task_world_receipt(receipt, scope="opaque_process_task_world")
        return [_with_receipt_integrity(kernel, compiled, receipt)]
    if kind == "probe_job":
        receipt = kernel.process_orchestrator.probe_job(action, step, executor)
        return [_with_receipt_integrity(kernel, compiled, receipt)]
    if kind == "probe_service":
        receipt = kernel.process_orchestrator.probe(action, step, executor)
        return [_with_receipt_integrity(kernel, compiled, receipt)]
    if kind == "stop_process":
        receipt = kernel.process_orchestrator.stop(action, step, executor)
        if receipt.success or receipt.state_change:
            receipt = _opaque_task_world_receipt(receipt, scope="opaque_process_task_world")
        return [_with_receipt_integrity(kernel, compiled, receipt)]
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
