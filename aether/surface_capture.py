"""Generic provenance-bound live-surface capture for Aether-Next.

Aether does not own backend-specific live-surface capture strategy.
The Primary may already execute any legitimate task-local capture command through
``run_command``.  This module adds only the missing custody seam: a solver-authored
capture command names one live surface and one *fresh* output path, Aether executes
that command once, then binds the exact resulting bytes to ``exact_capture``
provenance.

No new fixed tool is introduced and no backend-specific command is synthesized.
If the command contains ``{output}``, Aether replaces it with a quoted task-local
path; a command may also name the declared output path directly. Requiring a fresh
output path prevents a successful no-op command from being misreported as a newly
observed screenshot.
"""
from __future__ import annotations

from hashlib import sha256
import shlex
from typing import Any

from .artifact_plane import exact_capture, identify_bytes
from .execution import run_stateful_command
from .ledger import Receipt
from .runtime_ir import normalize_relpath


def _read_exact_bytes(executor: Any, path: str) -> bytes:
    read_bytes = getattr(executor, "read_file_bytes", None)
    if callable(read_bytes):
        return bytes(read_bytes(path))
    return str(executor.read_file(path)).encode("utf-8")


def _capture_command(template: str, output_path: str) -> str:
    raw = str(template or "")
    if not raw.strip():
        raise ValueError("surface capture command must be non-empty")
    if "{output}" in raw:
        return raw.replace("{output}", shlex.quote(output_path))
    return raw


def execute_surface_capture(
    kernel: Any,
    action: Any,
    step: int,
    compiled: Any,
    executor: Any,
    envmap: Any,
    *,
    timeout_s: int,
    timeout_note: str,
) -> Receipt:
    """Execute one generic capture command and bind the exact captured bytes."""
    surface = str(action.arguments.get("capture_surface", "")).strip()
    output_path = normalize_relpath(
        str(action.arguments.get("output_path", "")), envmap.workspace_root
    )
    template = str(action.arguments.get("command", ""))
    base_payload: dict[str, Any] = {
        "action_kind": "run_command",
        "capture_surface": surface,
        "output_path": output_path,
        "command_template": template,
        "candidate_id": getattr(action, "candidate_id", ""),
        "capture_authority": "task_local_command_capture_provenance_not_semantic_truth",
    }
    if not surface:
        return Receipt(
            receipt_id=f"step-{step}:{action.action_id}:surface_capture",
            step=step,
            kind="run_command",
            success=False,
            summary="surface capture requires a non-empty capture_surface",
            failure_class="action_validation",
            payload=base_payload,
        )
    if not output_path or output_path == ".":
        return Receipt(
            receipt_id=f"step-{step}:{action.action_id}:surface_capture",
            step=step,
            kind="run_command",
            success=False,
            summary="surface capture requires a file output_path",
            failure_class="action_validation",
            payload=base_payload,
        )
    try:
        command = _capture_command(template, output_path)
    except ValueError as exc:
        return Receipt(
            receipt_id=f"step-{step}:{action.action_id}:surface_capture",
            step=step,
            kind="run_command",
            success=False,
            summary=str(exc),
            failure_class="action_validation",
            payload=base_payload,
        )

    # A pre-existing target cannot prove that the command yielded a fresh live
    # observation. Fail before execution and require a new path rather than
    # deleting or overwriting task state behind the Solver's back.
    try:
        if executor.exists(output_path):
            return Receipt(
                receipt_id=f"step-{step}:{action.action_id}:surface_capture",
                step=step,
                kind="run_command",
                success=False,
                summary=(
                    f"surface capture output already exists: {output_path}; "
                    "choose a fresh output path"
                ),
                failure_class="stale_evidence",
                payload=base_payload,
            )
    except Exception as exc:  # noqa: BLE001 - environment truth must fail closed
        return Receipt(
            receipt_id=f"step-{step}:{action.action_id}:surface_capture",
            step=step,
            kind="run_command",
            success=False,
            summary=f"surface capture could not establish output freshness: {output_path}",
            failure_class="environment_probe_failure",
            payload={
                **base_payload,
                "error_type": type(exc).__name__,
                "error": str(exc)[:1000],
            },
        )

    result = run_stateful_command(
        executor, command, cwd=envmap.workspace_root, timeout_s=timeout_s
    )
    changed_paths = tuple(result.modified_paths) + tuple(result.produced_artifacts) + tuple(result.removed_paths)
    integrity_paths = tuple(sorted(set((*changed_paths, output_path))))
    integrity_violation = kernel.integrity_guards.validate_modified_paths(
        compiled.objective_graph, integrity_paths,
    )
    observation_check = getattr(kernel.integrity_guards, "validate_state_observation", None)
    if not integrity_violation and callable(observation_check):
        integrity_violation = observation_check(
            compiled.objective_graph, result.state_delta,
        )
    failure_class = (
        kernel.failure_parser.classify(
            result.stdout + "\n" + result.stderr,
            exit_code=result.exit_code,
        )
        if not result.success
        else ""
    )
    command_hash = sha256(command.encode("utf-8")).hexdigest()
    payload: dict[str, Any] = {
        **base_payload,
        "command": command,
        "command_sha256": command_hash,
        "timeout_s": timeout_s,
        "timeout_policy": timeout_note,
        "exit_code": result.exit_code,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "stdout_bytes": result.stdout_bytes_total,
        "stderr_bytes": result.stderr_bytes_total,
        "stdout_overflow_path": result.stdout_overflow_path,
        "stderr_overflow_path": result.stderr_overflow_path,
        "timed_out": result.timed_out,
        "modified_paths": tuple(
            normalize_relpath(path, envmap.workspace_root) for path in result.modified_paths
        ),
        "artifact_paths": tuple(
            normalize_relpath(path, envmap.workspace_root) for path in result.produced_artifacts
        ),
        "removed_paths": tuple(
            normalize_relpath(path, envmap.workspace_root) for path in result.removed_paths
        ),
        "state_delta": dict(result.state_delta),
    }
    if integrity_violation:
        payload["integrity_violation"] = integrity_violation
    if not result.success:
        return Receipt(
            receipt_id=f"step-{step}:{action.action_id}:surface_capture",
            step=step,
            kind="run_command",
            success=False,
            summary=f"surface capture command exit={result.exit_code}: {command}",
            state_change=bool(changed_paths),
            failure_class=failure_class or "command_failure",
            payload=payload,
        )
    try:
        captured_bytes = _read_exact_bytes(executor, output_path)
    except Exception as exc:  # noqa: BLE001 - successful command without capture is evidence
        return Receipt(
            receipt_id=f"step-{step}:{action.action_id}:surface_capture",
            step=step,
            kind="run_command",
            success=False,
            summary=f"surface capture command succeeded but output is missing: {output_path}",
            state_change=bool(changed_paths),
            failure_class="missing_artifact",
            payload={
                **payload,
                "output_error_type": type(exc).__name__,
                "output_error": str(exc)[:1000],
            },
        )
    if not captured_bytes:
        return Receipt(
            receipt_id=f"step-{step}:{action.action_id}:surface_capture",
            step=step,
            kind="run_command",
            success=False,
            summary=f"surface capture produced an empty artifact: {output_path}",
            state_change=True,
            failure_class="invalid_artifact",
            payload=payload,
        )

    generation = str(getattr(envmap, "digest", lambda: "")())
    output_identity = identify_bytes(
        captured_bytes,
        path=output_path,
        source="aether:surface_capture_output",
        generation=generation,
    )
    capture = exact_capture(
        captured_bytes,
        surface=surface,
        media_type=output_identity.media_type,
        capture_backend="task_local_command",
        capture_backend_version=command_hash,
        generation=generation,
    )
    payload.update({
        "artifact_paths": tuple(sorted(set((*payload["artifact_paths"], output_path)))),
        "artifact_handle": output_identity.handle,
        "artifact_identity": output_identity.as_dict(),
        "screen_capture_derivation": capture.as_dict(),
        "screen_capture_derivation_sha256": capture.identity,
        "capture_media_type": output_identity.media_type,
        "capture_bytes": len(captured_bytes),
        "fresh_output_required": True,
    })
    return Receipt(
        receipt_id=f"step-{step}:{action.action_id}:surface_capture",
        step=step,
        kind="run_command",
        success=not bool(integrity_violation),
        summary=f"captured live surface {surface!r} to {output_path}",
        state_change=True,
        failure_class="integrity_violation" if integrity_violation else "",
        payload=payload,
    )


__all__ = ["execute_surface_capture"]
