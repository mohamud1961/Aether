"""Generic provenance-bound artifact transformation for Aether-Next.

This is deliberately not a PDF/video/CAD/image specialist. The Primary Agent
supplies one task-local ``run_command`` containing ``{source}`` and ``{output}``.
Aether binds exact source bytes before execution, runs the command through the
existing Executor, then content-addresses the exact output and records the
source -> command -> derivative chain.

The transform receipt is execution provenance, not a semantic claim that the
command performed the intended task correctly. Completion remains evidence- and
Verifier-gated.
"""
from __future__ import annotations

from hashlib import sha256
import shlex
from typing import Any

from .artifact_plane import derive_bytes, identify_bytes
from .execution import run_stateful_command
from .ledger import Receipt
from .runtime_ir import normalize_relpath


def _read_exact_bytes(executor: Any, path: str) -> bytes:
    read_bytes = getattr(executor, "read_file_bytes", None)
    if callable(read_bytes):
        return bytes(read_bytes(path))
    # Memory/test executors may expose only textual reads. This fallback is
    # exact for their UTF-8 string world and keeps the production path honest:
    # real/Harbor/Docker executors all expose read_file_bytes.
    return str(executor.read_file(path)).encode("utf-8")


def _transform_command(template: str, source_path: str, output_path: str) -> str:
    raw = str(template or "")
    if raw.count("{source}") < 1 or raw.count("{output}") < 1:
        raise ValueError("provenance-bound command must contain both {source} and {output}")
    return raw.replace("{source}", shlex.quote(source_path)).replace(
        "{output}", shlex.quote(output_path)
    )


def execute_artifact_transform(
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
    """Execute one generic transform and return one exact action receipt."""
    source_path = normalize_relpath(
        str(action.arguments.get("source_path", "")), envmap.workspace_root
    )
    output_path = normalize_relpath(
        str(action.arguments.get("output_path", "")), envmap.workspace_root
    )
    template = str(action.arguments.get("command", ""))
    base_payload: dict[str, Any] = {
        "action_kind": "run_command",
        "source_path": source_path,
        "output_path": output_path,
        "command_template": template,
        "candidate_id": getattr(action, "candidate_id", ""),
    }
    if not source_path or source_path == "." or not output_path or output_path == ".":
        return Receipt(
            receipt_id=f"step-{step}:{action.action_id}:artifact_transform",
            step=step,
            kind="run_command",
            success=False,
            summary="artifact transform requires file source_path and output_path",
            failure_class="action_validation",
            payload=base_payload,
        )
    if source_path == output_path:
        return Receipt(
            receipt_id=f"step-{step}:{action.action_id}:artifact_transform",
            step=step,
            kind="run_command",
            success=False,
            summary="artifact transform source and output must be distinct",
            failure_class="action_validation",
            payload=base_payload,
        )
    try:
        source_bytes = _read_exact_bytes(executor, source_path)
    except Exception as exc:  # noqa: BLE001 - truthful source-read failure
        return Receipt(
            receipt_id=f"step-{step}:{action.action_id}:artifact_transform",
            step=step,
            kind="run_command",
            success=False,
            summary=f"artifact transform source unavailable: {source_path}",
            failure_class="missing_artifact",
            payload={**base_payload, "error_type": type(exc).__name__, "error": str(exc)[:1000]},
        )
    source_identity = identify_bytes(
        source_bytes,
        path=source_path,
        source="aether:artifact_transform_source",
        generation=str(getattr(envmap, "digest", lambda: "")()),
    )
    try:
        command = _transform_command(template, source_path, output_path)
    except ValueError as exc:
        return Receipt(
            receipt_id=f"step-{step}:{action.action_id}:artifact_transform",
            step=step,
            kind="run_command",
            success=False,
            summary=str(exc),
            failure_class="action_validation",
            payload={**base_payload, "source_artifact_identity": source_identity.as_dict()},
        )

    result = run_stateful_command(
        executor, command, cwd=envmap.workspace_root, timeout_s=timeout_s
    )
    failure_class = (
        kernel.failure_parser.classify(
            result.stdout + "\n" + result.stderr,
            exit_code=result.exit_code,
        )
        if not result.success
        else ""
    )
    changed_paths = tuple(result.modified_paths) + tuple(result.produced_artifacts) + tuple(result.removed_paths)
    integrity_violation = kernel.integrity_guards.validate_modified_paths(
        compiled.objective_graph, changed_paths,
    )
    observation_check = getattr(kernel.integrity_guards, "validate_state_observation", None)
    if not integrity_violation and callable(observation_check):
        integrity_violation = observation_check(
            compiled.objective_graph, result.state_delta,
        )
    payload: dict[str, Any] = {
        **base_payload,
        "command": command,
        "command_sha256": sha256(command.encode("utf-8")).hexdigest(),
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
        "source_artifact_handle": source_identity.handle,
        "source_artifact_identity": source_identity.as_dict(),
        "transform_authority": "task_local_command_execution_provenance_not_semantic_truth",
    }
    if integrity_violation:
        payload["integrity_violation"] = integrity_violation

    if not result.success:
        return Receipt(
            receipt_id=f"step-{step}:{action.action_id}:artifact_transform",
            step=step,
            kind="run_command",
            success=False,
            summary=f"artifact transform command exit={result.exit_code}: {command}",
            state_change=bool(changed_paths),
            failure_class=failure_class or "command_failure",
            payload=payload,
        )
    try:
        derivative_bytes = _read_exact_bytes(executor, output_path)
    except Exception as exc:  # noqa: BLE001 - successful process without output is a real failure
        return Receipt(
            receipt_id=f"step-{step}:{action.action_id}:artifact_transform",
            step=step,
            kind="run_command",
            success=False,
            summary=f"artifact transform command succeeded but output is missing: {output_path}",
            state_change=bool(changed_paths),
            failure_class="missing_artifact",
            payload={**payload, "output_error_type": type(exc).__name__, "output_error": str(exc)[:1000]},
        )

    env_digest = str(getattr(envmap, "digest", lambda: "")())
    command_hash = sha256(command.encode("utf-8")).hexdigest()
    derivation = derive_bytes(
        source_identity,
        derivative_bytes,
        derivative_path=output_path,
        transform="task_local_command",
        transform_version=f"env:{env_digest}:cmd:{command_hash}",
        parameters={
            "command_template": template,
            "effective_command": command,
            "source_path": source_path,
            "output_path": output_path,
            "timeout_s": timeout_s,
        },
        generation=env_digest,
        source="aether:artifact_transform_output",
    )
    payload.update({
        "artifact_paths": tuple(sorted(set((*payload["artifact_paths"], output_path)))),
        "artifact_derivation": derivation.as_dict(),
        "artifact_handle": derivation.derivative.handle,
        "artifact_identity": derivation.derivative.as_dict(),
    })
    return Receipt(
        receipt_id=f"step-{step}:{action.action_id}:artifact_transform",
        step=step,
        kind="run_command",
        success=not bool(integrity_violation),
        summary=f"artifact transform produced {output_path} from {source_path}",
        state_change=True,
        failure_class="integrity_violation" if integrity_violation else "",
        payload=payload,
    )


__all__ = ["execute_artifact_transform"]
