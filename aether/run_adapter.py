"""Run adapter: wire EnvMap + SubprocessExecutor + ModelHooks + Kernel into a single call."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Mapping

from .classifier import HarnessLimiterClassifier
from .envmap_builder import build_envmap_from_task
from .glm_model_view import MODEL_VIEW_CONTROL, normalize_model_view_mode
from .kernel import AetherNextKernel, KernelResult
from .model_hooks import ModelHooks, ModelCallable
from .model_profile import ModelProfile, PRODUCTION_PROFILE
from .provider_frontier_recovery import protected_final_reserve_s
from .model_interface import compact_model_interface_manifests
from .persistent_runtime import (
    SOLVER_REALITY_TRANSPORT_LATEST_EXCHANGE_V1,
    SOLVER_WORKING_CONTEXT_ASSISTANT_CONTENT_V1,
    SOLVER_WORKING_CONTEXT_MODES,
    SOLVER_WORKING_CONTEXT_OFF,
)
from .real_executor import SubprocessExecutor
from .result_metrics import provider_efficiency_metrics, run_metrics_for_row
from .run_cancellation import RunCancellationRequested
from .run_deadline import KernelRunTimeout, run_deadline
from .task_metadata_loader import load_task_metadata
from .task_contract import TaskClause, TaskContract
from .world import WorldState
from .thin_loop import ThinLoopConfig, run_thin_loop



def _load_task_toml(task_dir: str) -> dict[str, Any]:
    return load_task_metadata(task_dir)


def _receipt_records(result: KernelResult) -> list[dict[str, Any]]:
    return [{
        "receipt_id": receipt.receipt_id,
        "step": receipt.step,
        "kind": receipt.kind,
        "success": receipt.success,
        "summary": receipt.summary,
        "state_change": receipt.state_change,
        "failure_class": receipt.failure_class,
        "payload": dict(receipt.payload),
    } for receipt in result.receipts]


def _receipt_summary(result: KernelResult) -> list[dict[str, Any]]:
    return [{
        "receipt_id": receipt.receipt_id,
        "kind": receipt.kind,
        "success": receipt.success,
        "failure_class": receipt.failure_class,
        "summary": receipt.summary,
    } for receipt in result.receipts]

def _build_runtime_identity(
    *,
    task_dir: str,
    instruction_text: str,
    workspace_root: str,
    environment_id: str,
    max_steps: int | None,
    max_solver_turns: int | None = None,
    max_accepted_task_actions: int | None = None,
    supplied: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    identity = {str(key): value for key, value in dict(supplied or {}).items()}
    task_id = str(identity.get("task_id") or Path(task_dir).name)
    run_id = str(identity.get("run_id") or f"run-{uuid.uuid4().hex}")
    primary_agent_id = str(
        identity.get("primary_agent_id") or f"primary-agent:{run_id}"
    )
    source_commit = str(
        identity.get("source_commit")
        or os.environ.get("AETHER_SOURCE_COMMIT", "")
    ).strip()
    runtime_manifest = str(
        identity.get("runtime_manifest_sha256")
        or os.environ.get("AETHER_RUNTIME_MANIFEST_SHA256", "")
    ).strip()
    budgets = dict(identity.get("budgets", {}) or {})
    budgets["max_kernel_steps"] = (max(1, int(max_steps)) if max_steps is not None else None)
    if max_solver_turns is not None:
        budgets["max_solver_turns"] = max(1, int(max_solver_turns))
    if max_accepted_task_actions is not None:
        budgets["max_accepted_task_actions"] = max(1, int(max_accepted_task_actions))
    identity.update({
        "task_id": task_id,
        "run_id": run_id,
        "primary_agent_id": primary_agent_id,
        "workspace_id": str(Path(workspace_root).resolve()),
        "environment_id": environment_id,
        "raw_task_sha256": sha256(instruction_text.encode("utf-8")).hexdigest(),
        "source_commit": source_commit,
        "source_commit_state": "provided" if source_commit else "not_supplied",
        "runtime_manifest_sha256": runtime_manifest,
        "runtime_manifest_state": "provided" if runtime_manifest else "not_supplied",
        "source_custody_complete": bool(source_commit and runtime_manifest),
        "budgets": budgets,
    })
    return identity


def run_task(
    *,
    task_dir: str,
    instruction_text: str,
    solver_model: ModelCallable,
    verifier_model: ModelCallable,
    vision_model: Any | None = None,
    workspace_root: str = "/app",
    max_steps: int | None = 24,
    max_solver_turns: int | None = None,
    max_accepted_task_actions: int | None = None,
    solver_max_output_tokens: int | None = 16000,
    verifier_max_output_tokens: int | None = 12000,
    model_profile: ModelProfile = PRODUCTION_PROFILE,
    runtime_identity: Mapping[str, Any] | None = None,
    executor: Any | None = None,
    envmap_override: Any | None = None,
    close_executor: bool = True,
    solver_reanchor_mode: str = "current_full",
    solver_context_mode: str = "full",
    context_cleanup_mode: str = "off",
    completion_record_mode: str = "off",
    solver_completion_signal_mode: str = "control",
    solver_loop: str = "incumbent",
    context_tree_adapter: Any | None = None,
    claim_ledger_controller: Any | None = None,
    state_snapshot_evidence_path: str | Path | None = None,
    thin_failed_observation_disposition_mode: str = "control",
    semantic_assistance: Any | None = None,
    solver_reasoning_mode: str = "control",
    solver_async_mode: str = "control",
    solver_task_contract_mode: str = "raw_task_control",
    solver_prefix_renderer: str = "incumbent_context",
    solver_reality_transport_mode: str = "full_snapshot_control",
    solver_working_context_mode: str = SOLVER_WORKING_CONTEXT_OFF,
    solver_hosted_tool_search_mode: str = "control",
    solver_model_view_mode: str = MODEL_VIEW_CONTROL,
    solver_tool_surface_mode: str = "control",
    solver_long_command_mode: str | None = None,
    thin_terminal_verifier_mode: str = "control",
    oracle_finish_response_mode: str = "control",
    delivery_hygiene_mode: str = "control",
    verifier_activation_continuity_mode: str = "fresh_compact_control",
    boundary_verification_mode: str = "control",
    completion_disposition_mode: str = "control",
    provider_frontier_recovery_mode: str = "control",
    refresh_runtime_operation_status: bool = False,
    probe_runtime_capabilities: bool = True,
    cancellation_event: Any | None = None,
    run_timeout_s: float | None = None,
    run_started_monotonic: float | None = None,
    visible_deadline_sec: float | None = None,
    packet_mode: str = "control",
    env_mode: str = "control",
    protocol_resilience: str = "control",
) -> dict[str, Any]:
    """Execute a task end-to-end and return a JSON-serializable run record.

    Parameters
    ----------
    task_dir:
        Path to the task directory for building the EnvMap.
    instruction_text:
        The task instruction / prompt text.
    solver_model:
        Model callable for the solver role.
    workspace_root:
        Workspace root for the executor (default ``/app``).
    max_steps:
        Maximum kernel steps.
    max_solver_turns:
        Maximum Solver provider turns.  This may be paired with a separate
        accepted task-action ceiling so completion/closeout turns remain
        available after task work is bounded.
    max_accepted_task_actions:
        Maximum accepted mutating/observation task actions.  Finish and submit
        protocol turns are not counted against this task-action ceiling.

    Returns
    -------
    dict
        JSON-serializable run record.
    """
    task_run_started = time.monotonic()
    run_evidence_result: dict[str, Any] | None = None
    run_evidence_finish_results: list[dict[str, Any]] = []
    result: Any | None = None
    snapshot_start_marker: str | None = None

    def observe_finish(*, step: int, executor: Any, ledger: Any) -> None:
        try:
            assert state_snapshot_evidence_path is not None
            run_evidence_finish_results.append(_persist_host_run_evidence(
                path=_finish_evidence_path(Path(state_snapshot_evidence_path), step),
                executor=executor, workspace_root=workspace_root, task_text=instruction_text,
                receipts=tuple(ledger.all_receipts()), step=step,
                run_started_monotonic=run_started_monotonic,
                run_start_marker=snapshot_start_marker,
                elapsed_fraction=(
                    min(1.0, max(0.0, (time.monotonic() - run_started_monotonic) / float(run_timeout_s)))
                    if run_started_monotonic is not None and run_timeout_s and float(run_timeout_s) > 0 else 0.0
                ),
                run_id=str(resolved_runtime_identity.get("run_id", "")),
                snapshot_id=f"finish:{step}",
            ))
        except Exception as exc:
            run_evidence_finish_results.append({
                "status": "error", "snapshot_id": f"finish:{step}",
                "error_type": type(exc).__name__, "error": str(exc)[:300],
            })
    selected_solver_loop = str(solver_loop or "incumbent").strip().lower()
    if selected_solver_loop not in {"incumbent", "thin"}:
        raise ValueError(f"unsupported solver loop: {solver_loop}")
    if context_tree_adapter is not None and selected_solver_loop != "thin":
        raise ValueError("M-TREE context adapter requires solver_loop='thin'")
    if claim_ledger_controller is not None and selected_solver_loop != "thin":
        raise ValueError("CHALLENGER claim-ledger controller requires solver_loop='thin'")
    if state_snapshot_evidence_path is not None:
        if selected_solver_loop != "thin" or claim_ledger_controller is not None:
            raise ValueError("host run-evidence sink requires thin loop with CHALLENGER disabled")
        _validate_host_evidence_path(Path(state_snapshot_evidence_path), workspace_root)
    selected_working_context_mode = str(
        solver_working_context_mode or SOLVER_WORKING_CONTEXT_OFF
    ).strip().lower()
    if selected_working_context_mode not in SOLVER_WORKING_CONTEXT_MODES:
        raise ValueError(f"unsupported Solver working-context mode: {solver_working_context_mode}")
    if selected_working_context_mode == SOLVER_WORKING_CONTEXT_ASSISTANT_CONTENT_V1 and (
        selected_solver_loop != "thin"
        or str(solver_reality_transport_mode or "").strip().lower()
        != SOLVER_REALITY_TRANSPORT_LATEST_EXCHANGE_V1
    ):
        raise ValueError(
            "assistant_content_v1 requires the thin loop with latest_exchange_v1 reality transport"
        )
    selected_model_view_mode = normalize_model_view_mode(solver_model_view_mode)
    if selected_solver_loop != "thin" and selected_model_view_mode != MODEL_VIEW_CONTROL:
        raise ValueError(
            "solver model view mode is implemented only for the thin GLM loop"
        )
    if selected_solver_loop != "thin" and solver_tool_surface_mode != "control":
        raise ValueError("solver tool surface mode is implemented only for the thin loop")
    if selected_solver_loop != "thin" and env_mode != "control":
        raise ValueError("env mode is implemented only for the thin loop")
    if envmap_override is None:
        task_toml = _load_task_toml(task_dir)
        envmap = build_envmap_from_task(
            task_dir,
            instruction_text,
            workspace_root=workspace_root,
            task_toml=task_toml,
            projection_mode="factual_only",
        )
    else:
        envmap = envmap_override
        if str(getattr(envmap, "workspace_root", "")) != str(workspace_root):
            raise ValueError("envmap_override workspace_root does not match run workspace_root")

    resolved_executor = executor if executor is not None else SubprocessExecutor(workspace_root)
    resolved_runtime_identity = _build_runtime_identity(
        task_dir=task_dir,
        instruction_text=instruction_text,
        workspace_root=workspace_root,
        environment_id=envmap.digest(),
        max_steps=max_steps,
        max_solver_turns=max_solver_turns,
        max_accepted_task_actions=max_accepted_task_actions,
        supplied=runtime_identity,
    )
    # A cancellation event supplied to run_task is the task-lifecycle authority
    # for every model callable as well as the kernel. Harbor already performs
    # this binding before entering the adapter; repeat it here so direct adapter
    # callers cannot strand a blocking provider call outside cancellation
    # custody. Provider implementations treat rebinding to the same event as an
    # idempotent assignment.
    for model in (solver_model, verifier_model, vision_model, semantic_assistance):
        if model is None:
            continue
        bind_cancel = getattr(model, "bind_run_cancellation", None)
        if callable(bind_cancel):
            bind_cancel(cancellation_event)

    hooks = ModelHooks(
        solver_model,
        verifier_model,
        vision_model=vision_model,
        run_id=str(resolved_runtime_identity["run_id"]),
        task_id=str(resolved_runtime_identity["task_id"]),
        telemetry_identity=resolved_runtime_identity,
        solver_max_output_tokens=solver_max_output_tokens,
        verifier_max_output_tokens=verifier_max_output_tokens,
        model_profile=model_profile,
    )
    hooks.configure_provider_frontier_recovery(
        provider_frontier_recovery_mode,
        protected_reserve_s=(
            protected_final_reserve_s(run_timeout_s)
            if provider_frontier_recovery_mode != "control" else None
        ),
    )
    kernel = AetherNextKernel(
        max_steps=max_steps,
        max_solver_turns=max_solver_turns,
        max_accepted_task_actions=max_accepted_task_actions,
        runtime_identity=resolved_runtime_identity,
        solver_reanchor_mode=solver_reanchor_mode,
        solver_context_mode=solver_context_mode,
        context_cleanup_mode=context_cleanup_mode,
        completion_record_mode=completion_record_mode,
        solver_reasoning_mode=solver_reasoning_mode,
        solver_async_mode=solver_async_mode,
        solver_task_contract_mode=solver_task_contract_mode,
        solver_prefix_renderer=solver_prefix_renderer,
        solver_reality_transport_mode=solver_reality_transport_mode,
        solver_hosted_tool_search_mode=solver_hosted_tool_search_mode,
        verifier_activation_continuity_mode=verifier_activation_continuity_mode,
        boundary_verification_mode=boundary_verification_mode,
        completion_disposition_mode=completion_disposition_mode,
        provider_frontier_recovery_mode=provider_frontier_recovery_mode,
        refresh_runtime_operation_status=refresh_runtime_operation_status,
        cancellation_event=cancellation_event,
    )
    # Keep a task-scoped WorldState owned by the adapter so the production
    # boundary, not only the kernel's direct-call fallback, carries state into
    # every Verifier activation and can emit a final compact snapshot.
    world_state = WorldState(
        task_contract=TaskContract.create(
            instruction_text,
            (TaskClause("task:prompt", instruction_text),),
        ),
        env_facts={
            "workspace_root": workspace_root,
            "network_scope": envmap.network_scope,
            "visible_file_count": len(envmap.visible_files),
            "visible_dir_count": len(envmap.visible_dirs),
        },
    )
    deadline_monotonic = None
    if run_timeout_s is not None and float(run_timeout_s) > 0:
        deadline_monotonic = (
            float(run_started_monotonic)
            if run_started_monotonic is not None
            else time.monotonic()
        ) + float(run_timeout_s)
    if state_snapshot_evidence_path is not None:
        prepare_marker = getattr(resolved_executor, "prepare_state_snapshot_marker", None)
        if callable(prepare_marker):
            try:
                snapshot_start_marker = str(prepare_marker())
            except Exception:
                snapshot_start_marker = None
    try:
        with run_deadline(deadline_monotonic):
            if selected_solver_loop == "thin":
                result = run_thin_loop(
                    envmap, resolved_executor, hooks, world_state=world_state,
                    config=ThinLoopConfig(
                        max_steps=max_steps,
                        max_solver_turns=max_solver_turns,
                        max_accepted_task_actions=max_accepted_task_actions,
                        runtime_identity=resolved_runtime_identity,
                        run_timeout_s=run_timeout_s,
                        run_started_monotonic=run_started_monotonic,
                        visible_deadline_sec=visible_deadline_sec,
                        packet_mode=packet_mode,
                        env_mode=env_mode,
                        protocol_resilience=protocol_resilience,
                        refresh_runtime_operation_status=refresh_runtime_operation_status,
                        probe_runtime_capabilities=probe_runtime_capabilities,
                        cancellation_event=cancellation_event,
                        solver_reanchor_mode=solver_reanchor_mode,
                        solver_context_mode=solver_context_mode,
                        context_cleanup_mode=context_cleanup_mode,
                        completion_record_mode=completion_record_mode,
                        solver_completion_signal_mode=solver_completion_signal_mode,
                        solver_reasoning_mode=solver_reasoning_mode,
                        solver_async_mode=solver_async_mode,
                        solver_task_contract_mode=solver_task_contract_mode,
                        solver_reality_transport_mode=solver_reality_transport_mode,
                        solver_working_context_mode=selected_working_context_mode,
                        solver_hosted_tool_search_mode=solver_hosted_tool_search_mode,
                        solver_model_view_mode=selected_model_view_mode,
                        failed_observation_disposition_mode=thin_failed_observation_disposition_mode,
                        semantic_assistance=semantic_assistance,
                        solver_tool_surface_mode=solver_tool_surface_mode,
                        solver_long_command_mode=solver_long_command_mode,
                        terminal_verifier_mode=thin_terminal_verifier_mode,
                        oracle_finish_response_mode=oracle_finish_response_mode,
                        delivery_hygiene_mode=delivery_hygiene_mode,
                        context_tree_adapter=context_tree_adapter,
                        claim_ledger_controller=claim_ledger_controller,
                        run_evidence_finish_observer=(observe_finish if state_snapshot_evidence_path is not None else None),
                    ),
                )
            else:
                result = kernel.run(
                    envmap, resolved_executor, hooks, world_state=world_state,
                    run_timeout_s=run_timeout_s,
                    run_started_monotonic=run_started_monotonic,
                )
    except KernelRunTimeout:
        if selected_solver_loop == "thin":
            raise
        result = kernel.interrupted_result(
            status="timeout", blockers=("run_deadline_exceeded",),
        )
    except RunCancellationRequested:
        # External lifecycle cancellation (Harbor agent timeout/cancel) is not a
        # provider or model failure. Preserve the exact in-flight ledger as a
        # terminal timeout record so Harbor may still grade the task world and
        # the experiment collector has durable forensic evidence. The async
        # Harbor adapter still propagates its own CancelledError after draining
        # this worker, so this does not convert cancellation into success.
        if selected_solver_loop == "thin":
            raise
        result = kernel.interrupted_result(
            status="timeout",
            blockers=("external_run_cancellation",),
        )
    finally:
        if state_snapshot_evidence_path is not None:
            try:
                if result is None:
                    raise RuntimeError("run ended before a result was constructed")
                run_evidence_result = _persist_host_run_evidence(
                    path=Path(state_snapshot_evidence_path), executor=resolved_executor,
                    workspace_root=workspace_root, task_text=instruction_text,
                    receipts=tuple(getattr(result, "receipts", ()) or ()),
                    step=int(getattr(result, "step", 0) or 0),
                    run_started_monotonic=run_started_monotonic,
                    run_start_marker=snapshot_start_marker,
                    elapsed_fraction=1.0,
                    run_id=str(resolved_runtime_identity.get("run_id", "")), snapshot_id="run_end",
                )
            except Exception as exc:
                run_evidence_result = {
                    "status": "error", "error_type": type(exc).__name__, "error": str(exc)[:300],
                }
        if claim_ledger_controller is not None:
            try:
                claim_ledger_controller.on_run_end()
            except Exception:
                # Run cleanup remains authoritative; snapshot failures are logged
                # by the controller and never alter task execution outcome.
                pass
        if snapshot_start_marker is not None:
            cleanup_marker = getattr(resolved_executor, "cleanup_state_snapshot_marker", None)
            if callable(cleanup_marker):
                try:
                    cleanup_marker()
                except Exception:
                    pass
        # Provider-native cognitive state is task-scoped. Executor lifecycle is
        # explicitly owned by the caller when an external world such as Harbor
        # is injected.
        hooks.release_model_scope()
        if close_executor:
            close = getattr(resolved_executor, "close", None)
            if callable(close):
                close()

    classifier = HarnessLimiterClassifier()
    classification = classifier.classify(result)

    run_metrics = run_metrics_for_row(result, hooks.last_parse_errors)
    model_call_telemetry = hooks.drain_model_telemetry()
    run_metrics.update(provider_efficiency_metrics(model_call_telemetry))
    task_run_wall_s = max(0.0, time.monotonic() - task_run_started)
    measured_components = {
        "provider_request_build_s": float(run_metrics.get("provider_request_build_elapsed_s", 0.0) or 0.0),
        "provider_admission_wait_s": float(run_metrics.get("provider_admission_wait_s", 0.0) or 0.0),
        "provider_request_elapsed_s": float(run_metrics.get("provider_elapsed_s", 0.0) or 0.0),
        "tool_command_wall_s": float(run_metrics.get("mechanical_run_command_wall_time_s", 0.0) or 0.0),
    }
    component_sum_s = sum(measured_components.values())
    residual_s = task_run_wall_s - component_sum_s
    run_metrics["latency_anatomy"] = {
        "schema": "aether.latency_anatomy.v1",
        "task_run_wall_s": round(task_run_wall_s, 6),
        "measured_components_s": {
            key: round(value, 6) for key, value in measured_components.items()
        },
        "measured_component_sum_s": round(component_sum_s, 6),
        "unattributed_residual_s": round(residual_s, 6),
        "residual_fraction_of_task_run_wall": (
            round(residual_s / task_run_wall_s, 6) if task_run_wall_s > 0 else None
        ),
        "reconciliation_status": "diagnostic_only_preregister_lc0_tolerance_before_canary",
        "residual_includes": [
            "grader/verifier work without a dedicated timer",
            "runtime setup, context construction and evidence persistence",
            "any provider/tool activity without a corresponding telemetry event",
        ],
        "evidence_tier": "instrumentation_only_until_benchmark_native_lc0_e2e",
    }
    quarantined_model_call_telemetry = hooks.drain_quarantined_model_telemetry()
    model_interface_captures = hooks.drain_model_interface_captures()
    model_exchange_captures = hooks.drain_model_exchange_captures()

    record = {
        "runtime_mode": "thin_frontier" if selected_solver_loop == "thin" else "persistent_v0",
        "solver_loop": selected_solver_loop,
        "thin_failed_observation_disposition_mode": (
            thin_failed_observation_disposition_mode
            if selected_solver_loop == "thin" else "control"
        ),
        "runtime_identity": dict(resolved_runtime_identity),
        "status": result.status,
        "step": result.step,
        "reconfigurations": int(getattr(result, "reconfigurations", 0) or 0),
        "used_check_ids": list(getattr(result, "used_check_ids", ()) or ()),
        "blockers": list(result.blockers),
        "classifier_label": classification.label,
        "classifier_confidence": classification.confidence,
        "classifier_evidence": list(classification.evidence),
        "classifier_detail": classification.detail,
        "model_parse_errors": run_metrics.pop("model_parse_errors"),
        "run_metrics": run_metrics,
        "accounting": dict(result.accounting or {}),
        "runtime_budget_history": (
            list(kernel.runtime_budget_history) if selected_solver_loop == "incumbent" else []
        ),
        "context_cleanup_mode": context_cleanup_mode,
        "completion_record_mode": completion_record_mode,
        "solver_reasoning_mode": solver_reasoning_mode,
        "solver_async_mode": solver_async_mode,
        "solver_task_contract_mode": solver_task_contract_mode,
        "solver_model_view_mode": selected_model_view_mode,
        "context_accounting_history": (
            list(kernel.context_accounting_history)
            if selected_solver_loop == "incumbent"
            else [
                dict(request.get("context_accounting", {}))
                for request in getattr(result, "requests", ())
                if isinstance(request, Mapping) and request.get("context_accounting")
            ]
        ),
        "model_call_telemetry": list(model_call_telemetry),
        "quarantined_late_model_telemetry": list(quarantined_model_call_telemetry),
        "model_interface_manifests": compact_model_interface_manifests(model_interface_captures),
        "model_interface_captures": list(model_interface_captures),
        "model_exchange_records": list(model_exchange_captures),
        "world_state_snapshot": world_state.dynamic_snapshot(),
        "receipt_records": _receipt_records(result),
        "receipt_summary": _receipt_summary(result),
    }
    if state_snapshot_evidence_path is not None:
        record["run_evidence"] = {
            "run_end": run_evidence_result or {"status": "unavailable"},
            "finish_attempts": run_evidence_finish_results,
        }
    return record


def _validate_host_evidence_path(path: Path, workspace_root: str) -> None:
    workspace = Path(workspace_root).resolve(strict=False)
    destination = path.resolve(strict=False)
    try:
        destination.relative_to(workspace)
    except ValueError:
        return
    raise ValueError("run-evidence file must be outside the task workspace")


def _finish_evidence_path(run_end_path: Path, step: int) -> Path:
    return run_end_path.with_name(f"{run_end_path.stem}.finish-{step:04d}{run_end_path.suffix}")


def _persist_host_run_evidence(
    *, path: Path, executor: Any, workspace_root: str, task_text: str,
    receipts: tuple[Any, ...], step: int, run_started_monotonic: float | None,
    run_id: str, snapshot_id: str, run_start_marker: str | None, elapsed_fraction: float,
) -> dict[str, Any]:
    """Capture bounded real workspace state into an exclusive host-owned file."""
    from .challenger_runtime.state_snapshot import capture_state_snapshot

    _validate_host_evidence_path(path, workspace_root)
    workspace = Path(workspace_root).resolve(strict=False)

    class ReceiptView:
        def all_receipts(self) -> tuple[Any, ...]:
            return receipts

    snapshot = capture_state_snapshot(
        executor=executor, workspace_root=str(workspace), task_text=task_text,
        ledger=ReceiptView(), taken_at_unix_s=time.time(), elapsed_fraction=elapsed_fraction,
        step=step, run_start_marker=run_start_marker,
        run_started_monotonic=run_started_monotonic,
    )
    payload = {
        "schema": "aether.run_evidence.v1", "run_id": run_id,
        "snapshot_id": snapshot_id, "snapshot": snapshot,
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(encoded) > 50_000:
        raise ValueError("run-evidence document exceeds 50000-byte limit")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        # A hard-link publish is atomic and fails if a prior run already owns the destination.
        os.link(temp, path)
    finally:
        try:
            temp.unlink()
        except FileNotFoundError:
            pass
    return {
        "status": "captured", "path": str(path), "bytes": len(encoded),
        "sha256": sha256(encoded).hexdigest(), "snapshot_schema": snapshot.get("schema"),
    }


# ---------------------------------------------------------------------------
# Stub model for offline CLI use
# ---------------------------------------------------------------------------

class _StubSolverModel:
    """Scripted solver: submit_outcome immediately."""

    def __call__(
        self,
        messages: list[dict[str, str]],
        *,
        max_output_tokens: int = 8000,
    ) -> str:
        return json.dumps({
            "kind": "submit_outcome",
            "summary": "stub solver: submitting outcome immediately",
        })


class _StubVerifierModel:
    """Returns a minimal completed verifier verdict for offline PERSISTENT runs."""

    def __call__(
        self,
        messages: list[dict[str, str]],
        *,
        max_output_tokens: int = 8000,
    ) -> str:
        return json.dumps({
            "verdict": "completed",
            "confidence": "high",
            "summary": "Offline stub verifier observed sufficient local completion evidence.",
            "completion_evidence": ["offline_stub_verifier"],
        })


def _main() -> None:
    parser = argparse.ArgumentParser(
        description="Run an Aether-Next task with stub models (offline).",
    )
    parser.add_argument(
        "--task-dir",
        required=True,
        help="Path to the task directory.",
    )
    parser.add_argument(
        "--instruction-file",
        required=True,
        help="Path to a text file containing the task instruction.",
    )
    parser.add_argument(
        "--workspace-root",
        default="/tmp/aether_workspace",
        help="Workspace root directory (default: /tmp/aether_workspace).",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=24,
        help="Maximum kernel steps (default: 24).",
    )
    args = parser.parse_args()

    instruction_path = Path(args.instruction_file)
    if not instruction_path.is_file():
        print(f"error: instruction file not found: {args.instruction_file}", file=sys.stderr)
        sys.exit(1)
    instruction_text = instruction_path.read_text(encoding="utf-8")

    task_dir = str(Path(args.task_dir).resolve())
    if not Path(task_dir).is_dir():
        print(f"error: task directory not found: {args.task_dir}", file=sys.stderr)
        sys.exit(1)

    record = run_task(
        task_dir=task_dir,
        instruction_text=instruction_text,
        solver_model=_StubSolverModel(),
        verifier_model=_StubVerifierModel(),
        workspace_root=args.workspace_root,
        max_steps=args.max_steps,
    )

    json.dump(record, sys.stdout, indent=2, default=str)
    print()


if __name__ == "__main__":
    _main()
