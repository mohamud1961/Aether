"""Core baseline runner that composes fixed Packet 02 blocks into one run."""

from __future__ import annotations

import json
import inspect
from time import perf_counter
from pathlib import Path
from typing import Any, Callable

from runner.action_bus import ActionBus
from runner.docker_sandbox import DockerSandbox
from runner.evidence_kernel import EvidenceKernel
from runner.evaluator import apply_packet01_guards, build_score_envelope
from runner.logger import RunLogger
from runner.model_client import ModelClient, ModelClientError, make_model_client_from_route
from runner.kernel_control_plane import export_control_plane_artifacts
from runner.packet04_route_manifest import (
    BASELINE_VARIANT_ID,
    build_legacy_route_manifest,
    build_packet04_route_manifest,
    load_runtime_callables,
    validate_independent_candidate_routing,
)
from runner.schemas import SCORE_ENVELOPE_VERSION, default_layers, utc_now, validate_model_route

BASELINE_BLOCK_SELECTION = {
    "orientation": "raw_prompt",
    "tools": "raw_bash",
    "execution": "flat_loop",
    "context": "full_history",
    "verification": "trust_model",
    "recovery": "no_recovery",
}


def resolve_model_client(model_route: dict[str, Any], **kwargs: Any) -> ModelClient:
    """Minimal factory hook for selecting a concrete model client from route metadata."""
    return make_model_client_from_route(model_route, **kwargs)


def run_reference_baseline(
    *,
    run_id: str,
    run_dir: str | Path,
    task_id: str,
    task_prompt: str,
    benchmark_family: str = "smoke",
    case_id: str | None = None,
    seed_id: str = "sc_b_01",
    model_route: dict[str, Any],
    model_client_kwargs: dict[str, Any] | None = None,
    runtime_probe: dict[str, Any] | None = None,
    workspace_state_overrides: dict[str, Any] | None = None,
    execution_state_overrides: dict[str, Any] | None = None,
    orientation_env_overrides: dict[str, Any] | None = None,
    max_steps: int = 3,
    timeout_sec: int = 600,
    sandbox_type: str = "none",
    sandbox_image: str | None = None,
    cwd: str | Path | None = None,
    route_manifest: dict[str, Any] | None = None,
    enforce_packet04_route_contract: bool = False,
) -> dict[str, Any]:
    """Execute one fixed-baseline Packet 02 run and emit run artifacts."""
    run_started_at = perf_counter()
    run_dir_path = Path(run_dir).resolve()
    workdir = Path(cwd or run_dir_path).resolve()
    baseline_manifest: dict[str, Any] | None = None
    manifest = route_manifest or _resolve_route_manifest(
        seed_id=seed_id,
        enforce_packet04_route_contract=enforce_packet04_route_contract,
    )
    if enforce_packet04_route_contract and seed_id != BASELINE_VARIANT_ID:
        baseline_manifest = build_packet04_route_manifest(BASELINE_VARIANT_ID)
        validate_independent_candidate_routing(
            candidate_manifest=manifest,
            baseline_manifest=baseline_manifest,
        )
    runtime_callables = load_runtime_callables(manifest)
    if baseline_manifest is not None:
        _validate_runtime_callable_identity(
            candidate_manifest=manifest,
            baseline_manifest=baseline_manifest,
            candidate_callables=runtime_callables,
            baseline_callables=load_runtime_callables(baseline_manifest),
        )
    route = validate_model_route(dict(model_route))
    model = resolve_model_client(route, **(model_client_kwargs or {}))
    timed_model = _TimedModelProxy(model)
    logger = RunLogger(run_dir_path)

    run_header = {
        "run_id": run_id,
        "started_at_utc": utc_now(),
        "task_id": task_id,
        "benchmark_family": benchmark_family,
        "seed_id": seed_id,
        "block_selection": _build_block_selection(manifest),
        "environment": {
            "sandbox_type": sandbox_type,
            "sandbox_image": sandbox_image,
            "cwd": str(workdir),
            "timeout_sec": timeout_sec,
        },
        "model_route": route,
        "scoring_contract": {"scoring_contract_version": SCORE_ENVELOPE_VERSION},
        "route_manifest_ref": "route_manifest.json",
        "route_manifest_fingerprint": manifest["route_manifest_fingerprint"],
        "variant_card_ref": manifest.get("variant_card_ref"),
        "routed_modules": list(manifest["routed_modules"]),
    }
    logger.start_run(run_header)
    logger.write_route_manifest(manifest)

    orientation_env = {"cwd": str(workdir), "task_id": task_id}
    if isinstance(orientation_env_overrides, dict):
        orientation_env.update(orientation_env_overrides)
    orient_started = perf_counter()
    oriented = runtime_callables["orientation"](task_prompt, env_info=orientation_env)
    orient_sec = perf_counter() - orient_started
    logger.append_event(
        phase="orient",
        event_type="oriented",
        payload={
            "details": {
                "initial_messages": len(oriented["messages"]),
                "timing_sec": orient_sec,
            }
        },
    )

    execution_result: dict[str, Any]
    execution_error: Exception | None = None
    recovery_action: dict[str, Any] | None = None
    workspace_state: dict[str, Any]
    tool_timing = _ToolTimingProbe()
    sandbox_total_started = perf_counter()
    sandbox_startup_sec = 0.0
    execution_sec = 0.0
    runtime_probe_sec = 0.0
    action_bus = ActionBus(run_id=run_id)
    evidence_kernel = EvidenceKernel(
        run_id=run_id,
        task_id=task_id,
        workspace_root=workdir,
    )
    with DockerSandbox(
        cwd=workdir,
        timeout_sec=timeout_sec,
        sandbox_type=sandbox_type,
        sandbox_image=sandbox_image,
    ) as sandbox:
        sandbox_startup_sec = perf_counter() - sandbox_total_started
        current_workspace_state = sandbox.workspace_state()
        tool_definitions = _call_with_supported_kwargs(
            runtime_callables["tools_getter"],
            cwd=str(workdir),
            workspace_state=current_workspace_state,
            task_prompt=task_prompt,
            route_manifest=manifest,
            run_id=run_id,
            task_id=task_id,
        )
        sandbox.native_tool_definitions = list(tool_definitions)
        sandbox.native_tool_runtime_cache = {}
        logger.append_event(
            phase="tool",
            event_type="sandbox_started",
            payload={
                "details": {
                    "sandbox_type": sandbox_type,
                    "tool_count": len(tool_definitions),
                    "timing_sec": sandbox_startup_sec,
                }
            },
        )
        evidence_kernel.set_declared_tools(tool_definitions)
        evidence_kernel.bind_session(sandbox.workspace_state())
        execution_started = perf_counter()
        try:
            tools = _build_declared_tools_dispatch(
                tool_definitions=tool_definitions,
                sandbox=sandbox,
                tool_executor=runtime_callables["tool_executor"],
                probe=tool_timing,
            )
            execution_context = {
                "history": oriented["messages"],
                "manage_history": runtime_callables["context"],
                "env_info": {
                    "cwd": str(workdir),
                    "task_id": task_id,
                    "run_id": run_id,
                    "task_prompt": task_prompt,
                    "workspace_root": str(workdir),
                    "canonical_workspace_root": str((orientation_env_overrides or {}).get("cwd") or workdir),
                    "variant_id": manifest.get("variant_id"),
                },
                "workspace_state": current_workspace_state,
                "route_manifest": manifest,
                "task_prompt": task_prompt,
            }
            execution_result = _call_with_supported_kwargs(
                runtime_callables["execution"],
                model=timed_model,
                tools=tools,
                context=execution_context,
                max_steps=max_steps,
                tool_definitions=tool_definitions,
                route_manifest=manifest,
                workspace_state=current_workspace_state,
            )
            execution_sec = perf_counter() - execution_started
            for step in execution_result["steps"]:
                completion_details = _build_model_completion_event_details(step)
                if completion_details is None:
                    continue
                logger.append_event(
                    phase="execute",
                    event_type="model_completion",
                    payload={"details": completion_details},
                )
            for step in execution_result["steps"]:
                completion = step.get("completion") if isinstance(step, dict) else None
                step_tool_calls = completion.get("tool_calls", []) if isinstance(completion, dict) else []
                for index, tool_result in enumerate(step.get("results", [])):
                    tool_call = step_tool_calls[index] if index < len(step_tool_calls) else None
                    action_record = action_bus.record_from_tool_call(
                        tool_call=tool_call,
                        step=step.get("step") if isinstance(step.get("step"), int) else None,
                        tool_index=index,
                        phase="execute",
                    )
                    kernel_receipt = _record_kernel_receipt(
                        evidence_kernel=evidence_kernel,
                        action_record=action_record.__dict__,
                        tool_call=tool_call,
                        tool_result=tool_result,
                        cwd=str(workdir),
                    )
                    details = _build_raw_tool_event_details(
                        tool_result=tool_result,
                        step=step.get("step"),
                        phase="execute",
                        forced_probe=False,
                    )
                    logger.append_event(
                        phase="tool",
                        event_type="raw_bash_result",
                        payload={"details": details},
                    )
                    logger.append_event(
                        phase="execute",
                        event_type="evidence_kernel_receipt",
                        payload={"details": kernel_receipt},
                    )
                    logger.append_event(
                        phase="execute",
                        event_type="action_bus_recorded",
                        payload={"details": action_record.__dict__},
                    )
            _append_control_plane_events(logger, execution_result.get("control_plane_events"))
        except Exception as err:
            execution_sec = perf_counter() - execution_started
            execution_error = err
            execution_result = {
                "status": "error",
                "history": list(oriented["messages"]),
                "steps": [],
                "step_count": 0,
                "last_completion": {},
            }
            error_details = getattr(err, "details", None)
            if isinstance(error_details, dict):
                lifecycle = error_details.get("execution_lifecycle")
                if isinstance(lifecycle, dict):
                    execution_result.update(lifecycle)
            if isinstance(err, ModelClientError):
                logger.append_event(
                    phase="execute",
                    event_type="model_client_error",
                    payload={"details": err.details},
                )
            recovery_action = runtime_callables["recovery"](err, execution_result["history"])
            logger.append_event(
                phase="recover",
                event_type="recovery_action",
                payload={"details": recovery_action},
            )
        _attach_bounded_autopsy_signal(execution_result)
        autopsy_payload = execution_result.get("autopsy")
        if isinstance(autopsy_payload, dict):
            evidence_kernel.apply_autopsy(
                autopsy=autopsy_payload,
                step_count=execution_result.get("step_count", 0),
            )
            logger.append_event(
                phase="recover",
                event_type="evidence_kernel_autopsy",
                payload={"details": dict(evidence_kernel.export_state().get("autopsy_state", {}))},
            )
        probe_started = perf_counter()
        probe_summary = _execute_runtime_probe(
            runtime_probe=runtime_probe,
            sandbox=sandbox,
            logger=logger,
            execution_result=execution_result,
            action_bus=action_bus,
            evidence_kernel=evidence_kernel,
            tool_executor=runtime_callables["tool_executor"],
            cwd=str(workdir),
        )
        runtime_probe_sec = perf_counter() - probe_started
        if probe_summary:
            execution_result["runtime_probe"] = probe_summary
        current_workspace_state = sandbox.workspace_state()
        if isinstance(execution_state_overrides, dict) and execution_state_overrides:
            _merge_execution_state_overrides(execution_result, execution_state_overrides)
            logger.append_event(
                phase="execute",
                event_type="execution_probe_state_applied",
                payload={"details": {"override_keys": sorted(execution_state_overrides.keys())}},
            )
        if _is_active_evidence_kernel_route(manifest):
            terminal_guard_result = None
            final_status = "pending_verification"
        else:
            terminal_guard_result = _call_with_supported_kwargs(
                runtime_callables["terminal_guard"],
                execution_result=execution_result,
                recovery_action=recovery_action,
                workspace_state=current_workspace_state,
            )
            if isinstance(terminal_guard_result, dict):
                final_status = str(terminal_guard_result.get("status") or terminal_guard_result.get("governed_status") or "error")
                execution_result.update(
                    {
                        "governed_status": terminal_guard_result.get("governed_status"),
                        "final_verdict": terminal_guard_result.get("final_verdict"),
                        "finalization_bundle": terminal_guard_result.get("evidence_bundle", {}),
                        "finalization_reason_codes": list(terminal_guard_result.get("reason_codes", []))
                        if isinstance(terminal_guard_result.get("reason_codes"), list)
                        else [],
                    }
                )
                if isinstance(terminal_guard_result.get("open_obligations"), dict):
                    execution_result["open_obligations"] = dict(terminal_guard_result["open_obligations"])
            else:
                final_status = str(terminal_guard_result)
        if execution_error is None:
            internal_model_error = _extract_internal_model_client_error(execution_result)
            if internal_model_error is not None:
                logger.append_event(
                    phase="execute",
                    event_type="model_client_error",
                    payload={"details": internal_model_error},
                )
            logger.append_event(
                phase="execute",
                event_type="loop_completed",
                payload={
                    "details": {
                        "status": final_status,
                        "step_count": execution_result["step_count"],
                    }
                },
            )
        logger.append_event(
            phase="execute",
            event_type="terminal_outcome_finalized",
            payload={
                "details": {
                    "status": final_status,
                    "terminal_write_count": execution_result.get("terminal_write_count"),
                    "terminal_write_attempt_count": execution_result.get("terminal_write_attempt_count"),
                    "cleanup_completion_reason_codes": execution_result.get(
                        "cleanup_completion_reason_codes",
                        [],
                    ),
                    "unresolved_state_exit_count": execution_result.get("unresolved_state_exit_count", 0),
                    "post_cancel_tool_return_count": execution_result.get("post_cancel_tool_return_count", 0),
                    "cleanup_race_detected": bool(execution_result.get("cleanup_race_detected")),
                    "lifecycle_reason_codes": execution_result.get("lifecycle_reason_codes", []),
                }
            },
        )
        # Apply post-run answer.json guard if the variant calls for it (e.g. for tool_result_attribution family)
        variant_id = manifest.get("variant_id")
        if variant_id in {"combined_guard", "no_call_attribution_guard", "ignored_result_ids_guard"}:
            try:
                from blocks.tools.result_attribution_guard_common import apply_answer_json_guard
                apply_answer_json_guard(workdir, mode=variant_id)
            except Exception as e:
                pass

        required_artifact_paths = execution_result.get("required_artifact_paths")
        if not isinstance(required_artifact_paths, list) or not required_artifact_paths:
            required_artifact_paths = ["run_header.json", "run_events.jsonl", "route_manifest.json"]
        canonical_workspace_root = str(
            execution_result.get("workspace_state", {}).get("canonical_workspace_root")
            or execution_result.get("workspace_state", {}).get("workspace_root")
            or workdir
        )
        artifact_probe = _probe_artifact_gate_in_sandbox(
            sandbox=sandbox,
            canonical_workspace_root=canonical_workspace_root,
            required_artifact_paths=list(required_artifact_paths),
        )
        artifact_present = artifact_probe["status"] == "pass"
        workspace_state = sandbox.workspace_state()
    sandbox_total_sec = perf_counter() - sandbox_total_started

    execution_completed = execution_result["status"] == "completed"
    replay_layer_pass = execution_result.get("unresolved_state_exit_count", 0) == 0
    workspace_state.update(
        {
            "execution_status": execution_result["status"],
            "model_claimed_done": execution_completed,
            "history_length": len(execution_result.get("history", [])),
            "inline_assertion_pass": execution_completed,
            "verifier_artifact_present": artifact_present,
            "required_artifact_paths": list(required_artifact_paths),
            "artifact_status": dict(artifact_probe),
            "replay_layer_pass": replay_layer_pass,
            "replay_or_state_grader_pass": replay_layer_pass,
            "execution_result": execution_result,
            "task_prompt": task_prompt,
        }
    )
    if isinstance(execution_result.get("workspace_state"), dict):
        workspace_state.update(execution_result["workspace_state"])
    if isinstance(execution_result.get("active_kernel_state"), dict):
        workspace_state["active_kernel_state"] = execution_result["active_kernel_state"]
    if isinstance(execution_result.get("active_context_pack"), dict):
        workspace_state["active_context_pack"] = execution_result["active_context_pack"]
    if isinstance(execution_result.get("open_obligations"), dict):
        workspace_state["open_obligations"] = dict(execution_result["open_obligations"])
    if isinstance(execution_result.get("native_tool_state"), dict):
        workspace_state["native_tool_state"] = dict(execution_result["native_tool_state"])
    if isinstance(execution_result.get("service_state"), dict):
        workspace_state["service_state"] = dict(execution_result["service_state"])
    if isinstance(execution_result.get("governed_status"), str):
        workspace_state["active_governed_status"] = execution_result["governed_status"]
    if isinstance(execution_result.get("final_verdict"), str):
        workspace_state["active_final_verdict"] = execution_result["final_verdict"]
    _apply_authoritative_artifact_probe(
        workspace_state=workspace_state,
        execution_result=execution_result,
        artifact_probe=artifact_probe,
    )
    if isinstance(workspace_state_overrides, dict) and workspace_state_overrides:
        workspace_state.update(workspace_state_overrides)
        logger.append_event(
            phase="verify",
            event_type="verification_probe_state_applied",
            payload={"details": {"override_keys": sorted(workspace_state_overrides.keys())}},
        )
    verify_started = perf_counter()
    verified = runtime_callables["verification"](task_prompt, workspace_state)
    evidence_kernel.set_verifier_gate(
        passed=bool(verified),
        reason_codes=workspace_state.get("verification_reason_codes", []),
    )
    evidence_kernel.artifact_gate = {
        "status": artifact_probe["status"],
        "required_paths": list(artifact_probe["required_paths"]),
        "missing_paths": list(artifact_probe["missing_paths"]),
        "hash_algorithm": artifact_probe.get("hash_algorithm", "sha256"),
        "observed_hashes": dict(artifact_probe.get("observed_hashes", {})),
    }
    verify_sec = perf_counter() - verify_started
    verification_summary = {
        "verified": bool(verified),
        "reason_codes": [
            code
            for code in workspace_state.get("verification_reason_codes", [])
            if isinstance(code, str) and code
        ],
        "substitution_violations": [
            code
            for code in workspace_state.get("verification_substitution_violations", [])
            if isinstance(code, str) and code
        ],
        "layer_statuses": {
            str(layer_id): str(status)
            for layer_id, status in workspace_state.get("verification_layer_statuses", {}).items()
            if isinstance(layer_id, str) and isinstance(status, str)
        },
    }
    logger.append_event(
        phase="verify",
        event_type="verification_completed",
        payload={"details": verification_summary},
    )
    verify_action_record = action_bus.record_system_action(
        action_type="verify",
        phase="verify",
        command="verification_gate",
    )
    verify_receipt = _record_kernel_receipt(
        evidence_kernel=evidence_kernel,
        action_record=verify_action_record.__dict__,
        tool_call=None,
        tool_result={
            "tool_name": "system",
            "command": "verification_gate",
            "exit_code": 0 if bool(verified) else 1,
            "stdout": "",
            "stderr": "",
            "timed_out": False,
            "reason_code": "verification_passed" if bool(verified) else "verification_failed",
            "result_class": "success" if bool(verified) else "runtime_error",
        },
        cwd=str(workdir),
    )
    logger.append_event(
        phase="verify",
        event_type="action_bus_recorded",
        payload={"details": verify_action_record.__dict__},
    )
    logger.append_event(
        phase="verify",
        event_type="evidence_kernel_receipt",
        payload={"details": verify_receipt},
    )
    logger.append_event(
        phase="verify",
        event_type="evidence_kernel_state",
        payload={"details": evidence_kernel.export_state()},
    )
    logger.append_event(
        phase="execute",
        event_type="action_bus_summary",
        payload={"details": action_bus.export_summary()},
    )
    logger.append_event(
        phase="context",
        event_type="evidence_kernel_working_context_pack",
        payload={"details": evidence_kernel.build_working_context_pack()},
    )

    active_route = _is_active_evidence_kernel_route(manifest)
    if active_route:
        finalization_result = _call_with_supported_kwargs(
            runtime_callables["terminal_guard"],
            execution_result=execution_result,
            recovery_action=recovery_action,
            workspace_state=workspace_state,
        )
        if isinstance(finalization_result, dict):
            execution_result.update(
                {
                    "governed_status": finalization_result.get("governed_status"),
                    "final_verdict": finalization_result.get("final_verdict"),
                    "finalization_bundle": finalization_result.get("evidence_bundle", {}),
                    "finalization_reason_codes": list(finalization_result.get("reason_codes", []))
                    if isinstance(finalization_result.get("reason_codes"), list)
                    else [],
                }
            )
            if isinstance(finalization_result.get("open_obligations"), dict):
                execution_result["open_obligations"] = dict(finalization_result["open_obligations"])
            workspace_state["active_governed_status"] = finalization_result.get("governed_status")
            workspace_state["active_final_verdict"] = finalization_result.get("final_verdict")
            workspace_state["finalization_bundle"] = finalization_result.get("evidence_bundle", {})
            if _is_control_plane_context_route(manifest):
                control_plane_state = _merge_control_plane_state_for_export(
                    execution_result=execution_result,
                    workspace_state=workspace_state,
                    verified=verified,
                    finalization_result=finalization_result,
                )
                if control_plane_state:
                    control_plane_refs = export_control_plane_artifacts(control_plane_state, run_dir_path)
                    execution_result["control_plane_state"] = control_plane_state
                    if isinstance(control_plane_state.get("last_working_window"), dict):
                        execution_result["control_plane_working_window"] = dict(control_plane_state["last_working_window"])
                    workspace_state["control_plane_state"] = dict(control_plane_state)
                    if isinstance(control_plane_state.get("last_working_window"), dict):
                        workspace_state["control_plane_working_window"] = dict(control_plane_state["last_working_window"])
                    workspace_state["control_plane_artifact_refs"] = dict(control_plane_refs)
                    logger.append_event(
                        phase="verify",
                        event_type="control_plane_state_updated",
                        payload={
                            "details": {
                                "reason_code": "verification_gate_checked",
                                "pinned_invariant_hash": control_plane_state.get("pinned_invariant_hash"),
                                "artifact_refs": dict(control_plane_refs),
                            }
                        },
                        artifact_refs=list(control_plane_refs.values()),
                    )
                    logger.append_event(
                        phase="eval",
                        event_type="kernel_finish_gate_result",
                        payload={
                            "details": {
                                "governed_status": finalization_result.get("governed_status"),
                                "final_verdict": finalization_result.get("final_verdict"),
                                "reason_codes": list(finalization_result.get("reason_codes", []))
                                if isinstance(finalization_result.get("reason_codes"), list)
                                else [],
                                "open_obligations_count": len(finalization_result.get("open_obligations", {}))
                                if isinstance(finalization_result.get("open_obligations"), dict)
                                else 0,
                                "artifact_refs": dict(control_plane_refs),
                            }
                        },
                        artifact_refs=list(control_plane_refs.values()),
                    )
            logger.append_event(
                phase="eval",
                event_type="active_terminal_finalization",
                payload={"details": dict(finalization_result)},
            )

    layers = default_layers()
    layers["L1_verifier_artifact"]["status"] = "pass" if artifact_present else "fail"
    layers["L1_verifier_artifact"]["score"] = {"kind": "boolean", "value": bool(artifact_present)}
    layers["L1_verifier_artifact"]["artifact_ref"] = str(logger.events_path)
    if active_route:
        final_verdict = execution_result.get("final_verdict")
        if final_verdict not in {"pass", "fail", "unresolved", "blocked_non_promotable"}:
            final_verdict = "pass" if bool(verified) else "unresolved"
        layers["L4_final_acceptance"]["status"] = "pass" if final_verdict == "pass" else "fail"
        layers["L4_final_acceptance"]["score"] = {"kind": "boolean", "value": final_verdict == "pass"}
        layers["L4_final_acceptance"]["final_gate"] = {
            "gate_type": "governed_finalization",
            "gate_value": final_verdict,
        }
        layers["L4_final_acceptance"]["reason_codes"].extend(
            code
            for code in execution_result.get("finalization_reason_codes", [])
            if isinstance(code, str) and code and code not in layers["L4_final_acceptance"]["reason_codes"]
        )
    else:
        final_verdict = "pass" if verified else "fail"
        layers["L4_final_acceptance"]["status"] = "pass" if verified else "fail"
        layers["L4_final_acceptance"]["score"] = {"kind": "boolean", "value": verified}
        layers["L4_final_acceptance"]["final_gate"] = {
            "gate_type": "benchmark_assert",
            "gate_value": verified,
        }
    if recovery_action:
        layers["L4_final_acceptance"]["reason_codes"].append("grader_unavailable")
    eval_started = perf_counter()
    envelope = build_score_envelope(
        run_id=run_id,
        benchmark_id=benchmark_family,
        case_id=case_id or task_id,
        layers=layers,
        final_verdict=final_verdict,
    )
    guarded = apply_packet01_guards(envelope)
    eval_sec = perf_counter() - eval_started
    total_sec = perf_counter() - run_started_at
    runtime_timing = {
        "total_sec": total_sec,
        "orient_sec": orient_sec,
        "sandbox_startup_sec": sandbox_startup_sec,
        "sandbox_total_sec": sandbox_total_sec,
        "execution_sec": execution_sec,
        "runtime_probe_sec": runtime_probe_sec,
        "verification_sec": verify_sec,
        "grading_and_report_sec": eval_sec,
        "model_backed_latency_sec": timed_model.total_sec,
        "model_call_count": timed_model.call_count,
        "tool_exec_sec": tool_timing.total_sec,
        "tool_call_count": tool_timing.call_count,
    }
    logger.append_event(
        phase="eval",
        event_type="runtime_timing_summary",
        payload={"details": runtime_timing},
    )
    finalize_action_record = action_bus.record_system_action(
        action_type="finalize",
        phase="eval",
        command="score_envelope_finalize",
    )
    finalize_receipt = _record_kernel_receipt(
        evidence_kernel=evidence_kernel,
        action_record=finalize_action_record.__dict__,
        tool_call=None,
        tool_result={
            "tool_name": "system",
            "command": "score_envelope_finalize",
            "exit_code": 0,
            "stdout": "",
            "stderr": "",
            "timed_out": False,
            "reason_code": f"final_verdict_{guarded['aggregate']['final_verdict']}",
            "result_class": "success",
        },
        cwd=str(workdir),
    )
    logger.append_event(
        phase="eval",
        event_type="action_bus_recorded",
        payload={"details": finalize_action_record.__dict__},
    )
    logger.append_event(
        phase="eval",
        event_type="evidence_kernel_receipt",
        payload={"details": finalize_receipt},
    )
    logger.append_event(
        phase="eval",
        event_type="score_envelope_ready",
        payload={
            "details": {
                "truth_scope": "pre_governance_score_envelope",
                "is_governed_final_truth": False,
                "score_envelope_verdict": guarded["aggregate"]["final_verdict"],
            }
        },
    )
    logger.write_score_envelope(guarded)

    return {
        "run_dir": str(run_dir_path),
        "run_header": logger.read_header(),
        "route_manifest": logger.read_route_manifest(),
        "run_events": logger.read_events(),
        "score_envelope": guarded,
        "execution": execution_result,
        "verification": verification_summary,
        "authoritative_closure_state": workspace_state.get("authoritative_closure_state"),
        "action_bus": action_bus.export_summary(),
        "evidence_kernel": evidence_kernel.export_state(),
        "evidence_kernel_working_context_pack": evidence_kernel.build_working_context_pack(),
        "control_plane_artifacts": dict(workspace_state.get("control_plane_artifact_refs", {})),
        "verified": verified,
        "runtime_timing": runtime_timing,
    }


class _TimedModelProxy:
    def __init__(self, wrapped: Any):
        self._wrapped = wrapped
        self.call_count = 0
        self.total_sec = 0.0

    def complete(self, history: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        started = perf_counter()
        try:
            return self._wrapped.complete(history, **kwargs)
        finally:
            self.call_count += 1
            self.total_sec += perf_counter() - started

    def __getattr__(self, name: str) -> Any:
        return getattr(self._wrapped, name)


def _probe_artifact_gate_in_sandbox(
    *,
    sandbox: DockerSandbox,
    canonical_workspace_root: str,
    required_artifact_paths: list[str],
) -> dict[str, Any]:
    script = (
        "import hashlib, json\n"
        "from pathlib import Path\n"
        f"root = Path({canonical_workspace_root!r})\n"
        f"required = {json.dumps(required_artifact_paths)}\n"
        "missing = []\n"
        "observed = {}\n"
        "for rel_path in required:\n"
        "    target = root / rel_path\n"
        "    if not target.exists():\n"
        "        missing.append(rel_path)\n"
        "        continue\n"
        "    observed[rel_path] = hashlib.sha256(target.read_bytes()).hexdigest() if target.is_file() else 'dir'\n"
        "payload = {\n"
        "    'status': 'pass' if not missing else 'fail',\n"
        "    'required_paths': required,\n"
        "    'missing_paths': missing,\n"
        "    'hash_algorithm': 'sha256',\n"
        "    'observed_hashes': observed,\n"
        "}\n"
        "print(json.dumps(payload, sort_keys=True))\n"
    )
    probe = sandbox.exec(f"python3 - <<'PY'\n{script}\nPY", timeout_sec=60)
    stdout = str(probe.get("stdout") or "").strip()
    if probe.get("exit_code") == 0 and stdout:
        try:
            parsed = json.loads(stdout)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
    return {
        "status": "fail",
        "required_paths": list(required_artifact_paths),
        "missing_paths": list(required_artifact_paths),
        "hash_algorithm": "sha256",
        "observed_hashes": {},
    }


def _apply_authoritative_artifact_probe(
    *,
    workspace_state: dict[str, Any],
    execution_result: dict[str, Any],
    artifact_probe: dict[str, Any],
) -> None:
    """Project the post-execution sandbox artifact probe over stale kernel snapshots."""
    required_paths = [
        path
        for path in artifact_probe.get("required_paths", [])
        if isinstance(path, str) and path
    ]
    missing_paths = [
        path
        for path in artifact_probe.get("missing_paths", [])
        if isinstance(path, str) and path
    ]
    artifact_status = {
        "status": str(artifact_probe.get("status") or ("pass" if not missing_paths else "fail")),
        "required_paths": list(required_paths),
        "missing_paths": list(missing_paths),
        "hash_algorithm": str(artifact_probe.get("hash_algorithm") or "sha256"),
        "observed_hashes": dict(artifact_probe.get("observed_hashes", {}))
        if isinstance(artifact_probe.get("observed_hashes"), dict)
        else {},
    }
    if artifact_status["status"] == "fail":
        artifact_status["reason_codes"] = ["artifact_gate_failed"]
    else:
        artifact_status["reason_codes"] = []
    artifact_present = artifact_status["status"] == "pass"
    workspace_state["verifier_artifact_present"] = artifact_present
    workspace_state["required_artifact_paths"] = list(required_paths)
    workspace_state["artifact_status"] = dict(artifact_status)
    _sync_open_obligations_with_artifact_probe(
        workspace_state,
        artifact_present=artifact_present,
        missing_paths=missing_paths,
    )
    active_state = workspace_state.get("active_kernel_state")
    if isinstance(active_state, dict):
        active_state = dict(active_state)
        active_state["artifact_gate"] = {
            "status": artifact_status["status"],
            "required_paths": list(required_paths),
            "missing_paths": list(missing_paths),
            "observed_hashes": dict(artifact_status["observed_hashes"]),
        }
        _sync_open_obligations_with_artifact_probe(
            active_state,
            artifact_present=artifact_present,
            missing_paths=missing_paths,
        )
        workspace_state["active_kernel_state"] = active_state
    execution_workspace_state = execution_result.get("workspace_state")
    if isinstance(execution_workspace_state, dict):
        execution_workspace_state["verifier_artifact_present"] = artifact_present
        execution_workspace_state["required_artifact_paths"] = list(required_paths)
        execution_workspace_state["artifact_status"] = dict(artifact_status)
        _sync_open_obligations_with_artifact_probe(
            execution_workspace_state,
            artifact_present=artifact_present,
            missing_paths=missing_paths,
        )
        execution_workspace_active_state = execution_workspace_state.get("active_kernel_state")
        if isinstance(execution_workspace_active_state, dict):
            execution_workspace_active_state = dict(execution_workspace_active_state)
            execution_workspace_active_state["artifact_gate"] = {
                "status": artifact_status["status"],
                "required_paths": list(required_paths),
                "missing_paths": list(missing_paths),
                "observed_hashes": dict(artifact_status["observed_hashes"]),
            }
            _sync_open_obligations_with_artifact_probe(
                execution_workspace_active_state,
                artifact_present=artifact_present,
                missing_paths=missing_paths,
            )
            execution_workspace_state["active_kernel_state"] = execution_workspace_active_state
    execution_result["active_kernel_state"] = workspace_state.get(
        "active_kernel_state",
        execution_result.get("active_kernel_state", {}),
    )
    execution_result["open_obligations"] = dict(workspace_state.get("open_obligations", {}))


def _sync_open_obligations_with_artifact_probe(
    state: dict[str, Any],
    *,
    artifact_present: bool,
    missing_paths: list[str],
) -> None:
    open_obligations = state.get("open_obligations")
    if not isinstance(open_obligations, dict):
        open_obligations = {}
    else:
        open_obligations = dict(open_obligations)
    if artifact_present:
        open_obligations.pop("artifact_gate_missing_paths", None)
    elif missing_paths:
        open_obligations["artifact_gate_missing_paths"] = list(missing_paths)
    state["open_obligations"] = open_obligations


class _ToolTimingProbe:
    def __init__(self):
        self.call_count = 0
        self.total_sec = 0.0


def _timed_tool_executor(
    call: dict[str, Any],
    sandbox: DockerSandbox,
    *,
    tool_executor: Callable[..., dict[str, Any]],
    probe: _ToolTimingProbe,
) -> dict[str, Any]:
    started = perf_counter()
    try:
        return tool_executor(call, sandbox)
    finally:
        probe.call_count += 1
        probe.total_sec += perf_counter() - started


def _build_declared_tools_dispatch(
    *,
    tool_definitions: list[dict[str, Any]],
    sandbox: DockerSandbox,
    tool_executor: Callable[..., dict[str, Any]],
    probe: _ToolTimingProbe,
) -> dict[str, Callable[[dict[str, Any]], dict[str, Any]]]:
    names: list[str] = []
    for entry in tool_definitions:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        if isinstance(name, str) and name:
            names.append(name)
    if "raw_bash" not in names:
        names.append("raw_bash")
    return {
        tool_name: lambda call, _tool_name=tool_name: _timed_tool_executor(
            _normalize_tool_call_name(call, _tool_name),
            sandbox,
            tool_executor=tool_executor,
            probe=probe,
        )
        for tool_name in names
    }


def _normalize_tool_call_name(tool_call: dict[str, Any], tool_name: str) -> dict[str, Any]:
    if not isinstance(tool_call, dict):
        return {"name": tool_name, "arguments": {"command": ""}}
    normalized = dict(tool_call)
    normalized["name"] = tool_name
    return normalized


def _record_kernel_receipt(
    *,
    evidence_kernel: EvidenceKernel,
    action_record: dict[str, Any] | None,
    tool_call: Any,
    tool_result: dict[str, Any],
    cwd: str,
) -> dict[str, Any]:
    action_payload = {
        "command": "",
        "tool_name": "raw_bash",
        "action_id": "",
        "phase": "execute",
        "step": None,
        "tool_index": None,
    }
    action_type: str | None = None
    if isinstance(action_record, dict):
        maybe_type = action_record.get("action_type")
        if isinstance(maybe_type, str) and maybe_type:
            action_type = maybe_type
        maybe_name = action_record.get("tool_name")
        if isinstance(maybe_name, str) and maybe_name:
            action_payload["tool_name"] = maybe_name
        maybe_command = action_record.get("command")
        if isinstance(maybe_command, str) and maybe_command:
            action_payload["command"] = maybe_command
        maybe_action_id = action_record.get("action_id")
        if isinstance(maybe_action_id, str) and maybe_action_id:
            action_payload["action_id"] = maybe_action_id
        maybe_phase = action_record.get("phase")
        if isinstance(maybe_phase, str) and maybe_phase:
            action_payload["phase"] = maybe_phase
        if isinstance(action_record.get("step"), int):
            action_payload["step"] = action_record["step"]
        if isinstance(action_record.get("tool_index"), int):
            action_payload["tool_index"] = action_record["tool_index"]
    if isinstance(tool_call, dict):
        if isinstance(tool_call.get("name"), str):
            action_payload["tool_name"] = tool_call["name"]
        arguments = tool_call.get("arguments")
        action_payload["arguments"] = arguments
        if isinstance(arguments, dict) and isinstance(arguments.get("command"), str):
            action_payload["command"] = arguments["command"]
        elif isinstance(arguments, str):
            action_payload["command"] = arguments
    if not isinstance(tool_result, dict):
        return evidence_kernel.record_action(
            action_type=action_type,
            action_payload=action_payload,
            result_payload={"exit_code": 1, "stderr": "tool_result_not_mapping"},
            cwd=cwd,
        )
    command = tool_result.get("command")
    if isinstance(command, str) and command:
        action_payload["command"] = command
    if isinstance(tool_result.get("tool_name"), str) and tool_result.get("tool_name"):
        action_payload["tool_name"] = tool_result["tool_name"]
    return evidence_kernel.record_action(
        action_type=action_type,
        action_payload=action_payload,
        result_payload=tool_result,
        cwd=cwd,
    )


def _attach_bounded_autopsy_signal(execution_result: dict[str, Any]) -> None:
    steps = execution_result.get("steps")
    if not isinstance(steps, list) or not steps:
        return
    repeated_signatures: list[str] = []
    last_signature = ""
    streak = 0
    for step in steps:
        if not isinstance(step, dict):
            continue
        results = step.get("results")
        if not isinstance(results, list):
            continue
        for result in results:
            if not isinstance(result, dict):
                continue
            exit_code = int(result.get("exit_code", 0) or 0)
            timed_out = bool(result.get("timed_out", False))
            if exit_code == 0 and not timed_out:
                continue
            signature = "|".join(
                [
                    str(result.get("tool_name", "raw_bash")),
                    str(result.get("command", "")),
                    str(result.get("reason_code", "")),
                    str(exit_code),
                    "timeout" if timed_out else "no_timeout",
                ]
            )
            if signature == last_signature:
                streak += 1
            else:
                streak = 1
                last_signature = signature
            if streak >= 2:
                repeated_signatures.append(signature)
    if not repeated_signatures:
        return
    unique_signatures = _dedupe_preserve_order(repeated_signatures)
    autopsy = {
        "triggered": True,
        "repeated_failure_signatures": unique_signatures,
        "replan_required": True,
        "reason_codes": ["bounded_autopsy_replan_required_after_repeated_failure"],
    }
    execution_result["autopsy"] = autopsy
    existing_codes = execution_result.get("lifecycle_reason_codes", [])
    lifecycle_codes = [code for code in existing_codes if isinstance(code, str) and code]
    lifecycle_codes.extend(autopsy["reason_codes"])
    execution_result["lifecycle_reason_codes"] = _dedupe_preserve_order(lifecycle_codes)


def _build_model_completion_event_details(step: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(step, dict):
        return None
    completion = step.get("completion")
    if not isinstance(completion, dict):
        return None
    assistant_text = completion.get("text")
    reasoning_summary = completion.get("reasoning_summary")
    reasoning_token_count = completion.get("reasoning_token_count")
    provider_reasoning = completion.get("provider_reasoning")
    reasoning_artifact = completion.get("reasoning_artifact")
    tool_calls = completion.get("tool_calls")
    sanitized_tool_calls: list[dict[str, Any]] = []
    if isinstance(tool_calls, list):
        for tool_call in tool_calls:
            if not isinstance(tool_call, dict):
                continue
            name = tool_call.get("name")
            if not isinstance(name, str) or not name:
                continue
            entry: dict[str, Any] = {"name": name}
            call_id = tool_call.get("id")
            if isinstance(call_id, str) and call_id:
                entry["id"] = call_id
            arguments = tool_call.get("arguments")
            if isinstance(arguments, (dict, list, str, int, float, bool)) or arguments is None:
                entry["arguments"] = arguments
            sanitized_tool_calls.append(entry)
    details: dict[str, Any] = {
        "step": step.get("step"),
        "status": step.get("status"),
        "assistant_text": assistant_text if isinstance(assistant_text, str) else None,
        "assistant_text_char_count": len(assistant_text) if isinstance(assistant_text, str) else 0,
        "reasoning_summary": reasoning_summary if isinstance(reasoning_summary, str) else None,
        "reasoning_summary_char_count": len(reasoning_summary) if isinstance(reasoning_summary, str) else 0,
        "tool_call_count": len(sanitized_tool_calls),
        "tool_calls": sanitized_tool_calls,
    }
    context_token_attribution = step.get("context_token_attribution")
    if isinstance(context_token_attribution, dict):
        details["context_token_attribution"] = context_token_attribution
    if isinstance(reasoning_token_count, int) and reasoning_token_count >= 0:
        details["reasoning_token_count"] = reasoning_token_count
    if isinstance(provider_reasoning, dict):
        sanitized_provider_reasoning = {
            key: value
            for key, value in provider_reasoning.items()
            if isinstance(value, (str, int, float, bool)) and not isinstance(value, bool)
        }
        if sanitized_provider_reasoning:
            details["provider_reasoning"] = sanitized_provider_reasoning
    if isinstance(reasoning_artifact, dict):
        artifact_type = reasoning_artifact.get("type")
        encoding = reasoning_artifact.get("encoding")
        encrypted_char_count = reasoning_artifact.get("encrypted_content_char_count")
        encrypted_hashes = reasoning_artifact.get("encrypted_content_hashes")
        artifact_details: dict[str, Any] = {}
        if isinstance(artifact_type, str) and artifact_type:
            artifact_details["type"] = artifact_type
        if isinstance(encoding, str) and encoding:
            artifact_details["encoding"] = encoding
        if isinstance(encrypted_char_count, int) and encrypted_char_count >= 0:
            artifact_details["encrypted_content_char_count"] = encrypted_char_count
        if isinstance(encrypted_hashes, list):
            hash_list = [value for value in encrypted_hashes if isinstance(value, str) and value]
            artifact_details["encrypted_content_hash_count"] = len(hash_list)
            if hash_list:
                # Keep trace rows bounded; store only a short hash preview.
                artifact_details["encrypted_content_hashes_preview"] = hash_list[:3]
        if artifact_details:
            details["reasoning_artifact"] = artifact_details
    finish_reason = completion.get("finish_reason")
    if isinstance(finish_reason, str) and finish_reason:
        details["finish_reason"] = finish_reason
    return details


def _extract_internal_model_client_error(execution_result: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(execution_result, dict):
        return None
    last_model_client_error = execution_result.get("last_model_client_error")
    if isinstance(last_model_client_error, dict) and last_model_client_error:
        return dict(last_model_client_error)
    steps = execution_result.get("steps")
    if not isinstance(steps, list):
        return None
    for step in steps:
        if not isinstance(step, dict) or step.get("status") != "model_error":
            continue
        if step.get("error_type") != "ModelClientError":
            continue
        error_details = step.get("error_details")
        if isinstance(error_details, dict) and error_details:
            return dict(error_details)
        recovery_action = step.get("recovery_action")
        if isinstance(recovery_action, dict):
            nested = recovery_action.get("error_details")
            if isinstance(nested, dict) and nested:
                return dict(nested)
        error_text = step.get("error")
        if isinstance(error_text, str) and error_text.strip():
            return {"message": error_text}
    return None


def _execute_runtime_probe(
    *,
    runtime_probe: dict[str, Any] | None,
    sandbox: DockerSandbox,
    logger: RunLogger,
    execution_result: dict[str, Any],
    action_bus: ActionBus,
    evidence_kernel: EvidenceKernel,
    tool_executor: Callable[..., dict[str, Any]],
    cwd: str,
) -> dict[str, Any]:
    if not isinstance(runtime_probe, dict):
        return {}
    forced_calls = runtime_probe.get("forced_tool_calls")
    case_matrix_calls = runtime_probe.get("case_matrix_tool_calls")
    use_case_matrix_calls = not isinstance(forced_calls, list) and isinstance(case_matrix_calls, list)
    probe_calls = case_matrix_calls if use_case_matrix_calls else forced_calls
    contamination_safe = bool(runtime_probe.get("contamination_safe"))
    forced_probe_flag = not use_case_matrix_calls
    step_status = "forced_runtime_probe" if forced_probe_flag else "case_matrix_runtime_probe"
    summary = {
        "probe_id": runtime_probe.get("probe_id"),
        "defined": True,
        "contamination_safe": contamination_safe,
        "planned_call_count": len(probe_calls) if isinstance(probe_calls, list) else 0,
        "executed_call_count": 0,
        "interrupt_observed": False,
        "cleanup_observed": False,
        "observed_event_types": [],
    }
    if not isinstance(probe_calls, list) or not probe_calls:
        return summary

    steps = execution_result.setdefault("steps", [])
    base_step_index = len(steps)
    tool_results: list[dict[str, Any]] = []

    for index, probe_call in enumerate(probe_calls):
        if not isinstance(probe_call, dict):
            continue
        phase = _normalize_probe_phase(probe_call.get("phase"))
        label = probe_call.get("label")
        if not isinstance(label, str) or not label:
            label = f"runtime_probe_{index}"
        event_type = probe_call.get("event_type")
        if not isinstance(event_type, str) or not event_type:
            event_type = None

        tool_call = probe_call.get("tool_call")
        result = _execute_probe_tool_call(tool_call, sandbox, tool_executor=tool_executor)
        if isinstance(result, dict):
            result = {
                **result,
                "probe_label": label,
                "case_id": probe_call.get("case_id", label),
                "expected_class": probe_call.get("expected_class"),
                "phase": phase,
                "event_type": event_type,
            }
        action_record = action_bus.record_from_tool_call(
            tool_call=tool_call,
            step=base_step_index + len(tool_results),
            tool_index=0,
            phase=phase,
        )
        kernel_receipt = _record_kernel_receipt(
            evidence_kernel=evidence_kernel,
            action_record=action_record.__dict__,
            tool_call=tool_call,
            tool_result=result if isinstance(result, dict) else {"exit_code": 1, "stderr": "runtime_probe_result_not_mapping"},
            cwd=cwd,
        )
        tool_results.append(result)
        summary["executed_call_count"] += 1

        if phase == "execute" and _normalized_exit_code(result.get("exit_code"), default=0) != 0:
            summary["interrupt_observed"] = True
        elif phase == "execute" and summary["interrupt_observed"]:
            summary["post_cancel_tool_return_count"] = summary.get("post_cancel_tool_return_count", 0) + 1
        if phase == "recover" and _normalized_exit_code(result.get("exit_code"), default=1) == 0:
            summary["cleanup_observed"] = True

        details = {
            **_build_raw_tool_event_details(
                tool_result=result,
                step=base_step_index + len(tool_results) - 1,
                phase=phase,
                forced_probe=forced_probe_flag,
            ),
            "probe_label": label,
            "expected_class": probe_call.get("expected_class"),
        }
        logger.append_event(
            phase="tool",
            event_type="raw_bash_result",
            payload={"details": details},
        )
        logger.append_event(
            phase=phase,
            event_type="action_bus_recorded",
            payload={"details": action_record.__dict__},
        )
        logger.append_event(
            phase=phase,
            event_type="evidence_kernel_receipt",
            payload={"details": kernel_receipt},
        )
        if event_type:
            logger.append_event(
                phase=phase,
                event_type=event_type,
                payload={"details": details},
            )
            summary["observed_event_types"].append(event_type)

        steps.append(
            {
                "step": base_step_index + len(tool_results) - 1,
                "status": step_status,
                "tool_calls": 1,
                "results": [result],
                "completion": {
                    "text": "",
                    "tool_calls": [tool_call] if isinstance(tool_call, dict) else [],
                    "usage": {
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "total_tokens": 0,
                    },
                },
            }
        )

    summary["tool_results"] = tool_results
    execution_result["step_count"] = len(steps)
    return summary


def _build_raw_tool_event_details(
    *,
    tool_result: Any,
    step: Any,
    phase: str,
    forced_probe: bool,
) -> dict[str, Any]:
    result = tool_result if isinstance(tool_result, dict) else {}
    attribution_trace = result.get("attribution_trace")
    if not isinstance(attribution_trace, dict):
        attribution_trace = None
    mechanism_permission_signal = _extract_signal_flag(
        attribution_trace=attribution_trace,
        signal_key="permission_signal_detected",
    )
    mechanism_runtime_signal = _extract_signal_flag(
        attribution_trace=attribution_trace,
        signal_key="runtime_signal_detected",
    )
    proxy_permission_signal = result.get("permission_denied") if isinstance(result.get("permission_denied"), bool) else None
    proxy_runtime_signal = result.get("runtime_error") if isinstance(result.get("runtime_error"), bool) else None
    details = {
        "step": step if isinstance(step, int) and step >= 0 else None,
        "phase": phase,
        "forced_probe": forced_probe,
        "case_id": result.get("case_id"),
        "tool_name": result.get("tool_name", "raw_bash"),
        "command": result.get("command"),
        "raw_payload": result.get("raw_tool_call_payload"),
        "normalized_payload": result.get("normalized_tool_call_payload"),
        "tool_call_contract_class": result.get("tool_call_contract_class"),
        "result_class": result.get("result_class"),
        "reason_code": result.get("reason_code"),
        "decision_source": result.get("decision_source", "tool_executor"),
        "signal_attribution_scope": "mechanism_trace" if attribution_trace is not None else "proxy_only",
        "mechanism_permission_signal_detected": mechanism_permission_signal,
        "mechanism_runtime_signal_detected": mechanism_runtime_signal,
        "proxy_permission_signal_detected": proxy_permission_signal,
        "proxy_runtime_signal_detected": proxy_runtime_signal,
        # Legacy aliases: these now expose mechanism-level signals only.
        "permission_signal_detected": mechanism_permission_signal,
        "runtime_signal_detected": mechanism_runtime_signal,
        "attribution_trace": attribution_trace,
        "exit_code": result.get("exit_code"),
        "timed_out": bool(result.get("timed_out", False)),
    }
    return details


def _extract_signal_flag(*, attribution_trace: dict[str, Any] | None, signal_key: str) -> bool | None:
    if not isinstance(attribution_trace, dict):
        return None
    signal = attribution_trace.get(signal_key)
    if isinstance(signal, bool):
        return signal
    return None


def _merge_execution_state_overrides(
    execution_result: dict[str, Any],
    overrides: dict[str, Any],
) -> None:
    for key, value in overrides.items():
        if key == "runtime_probe" and isinstance(value, dict):
            existing_probe = execution_result.get("runtime_probe")
            if isinstance(existing_probe, dict):
                execution_result["runtime_probe"] = {**existing_probe, **value}
            else:
                execution_result["runtime_probe"] = dict(value)
            continue
        execution_result[key] = value


def _apply_terminal_outcome_cleanup_order_guard(
    *,
    execution_result: dict[str, Any],
    recovery_action: dict[str, Any] | None,
) -> str:
    sequence_parts: list[str] = []
    existing_fingerprint = execution_result.get("lifecycle_sequence_fingerprint")
    if isinstance(existing_fingerprint, str) and existing_fingerprint:
        sequence_parts.extend(part for part in existing_fingerprint.split(">") if part)

    status = execution_result.get("status")
    if not isinstance(status, str) or not status:
        status = "error"
    sequence_parts.append(f"runner_terminal_candidate:{status}")

    runtime_probe = execution_result.get("runtime_probe")
    interrupt_observed = False
    cleanup_observed = False
    post_cancel_tool_return_count = 0
    if isinstance(runtime_probe, dict):
        interrupt_observed = bool(runtime_probe.get("interrupt_observed"))
        cleanup_observed = bool(runtime_probe.get("cleanup_observed"))
        post_cancel_tool_return_count = int(runtime_probe.get("post_cancel_tool_return_count", 0) or 0)

    cleanup_reason_codes: list[str] = []
    existing_cleanup_codes = execution_result.get("cleanup_completion_reason_codes")
    if isinstance(existing_cleanup_codes, list):
        cleanup_reason_codes.extend(code for code in existing_cleanup_codes if isinstance(code, str) and code)

    if recovery_action is not None:
        recovery_cleanup_codes = recovery_action.get("cleanup_completion_reason_codes")
        if isinstance(recovery_cleanup_codes, list):
            cleanup_reason_codes.extend(
                code for code in recovery_cleanup_codes if isinstance(code, str) and code
            )
        else:
            cleanup_reason_codes.append("recovery_cleanup_completed")
        cleanup_observed = True
        sequence_parts.append("recovery_cleanup_completed")

    if interrupt_observed:
        sequence_parts.append("runtime_interrupt_observed")
        cleanup_reason_codes.append(
            "runtime_probe_cleanup_observed" if cleanup_observed else "runtime_probe_cleanup_missing"
        )

    if not cleanup_reason_codes:
        cleanup_reason_codes.append("loop_cleanup_completed")

    cleanup_completed = cleanup_observed or any(
        code in {"loop_cleanup_completed", "recovery_cleanup_completed", "runtime_probe_cleanup_observed"}
        for code in cleanup_reason_codes
    )

    final_status = status
    if status == "completed" and interrupt_observed and not cleanup_completed:
        final_status = "error"
        sequence_parts.append("terminal_downgraded_cleanup_missing")

    terminal_outcome = execution_result.get("terminal_outcome")
    if not isinstance(terminal_outcome, dict):
        terminal_outcome = {}
    terminal_outcome["status"] = final_status
    if not isinstance(terminal_outcome.get("reason_code"), str):
        terminal_outcome["reason_code"] = "runner_terminal_outcome_guard"
    terminal_outcome["committed_by"] = "runner_terminal_outcome_guard"
    execution_result["terminal_outcome"] = terminal_outcome

    observed_terminal_write_count = int(execution_result.get("terminal_write_count", 1) or 1)
    observed_terminal_write_attempt_count = int(
        execution_result.get("terminal_write_attempt_count", observed_terminal_write_count) or observed_terminal_write_count
    )
    duplicate_terminal_write_observed = observed_terminal_write_attempt_count > 1 or (
        isinstance(existing_fingerprint, str) and "terminal_outcome_duplicate_blocked" in existing_fingerprint
    )
    execution_result["terminal_write_count_observed"] = observed_terminal_write_count
    execution_result["terminal_write_attempt_count"] = observed_terminal_write_attempt_count
    execution_result["duplicate_terminal_write_observed"] = duplicate_terminal_write_observed
    execution_result["terminal_write_count"] = 1

    unresolved_state_exit_count = 0
    lifecycle_reason_codes = _dedupe_preserve_order(
        [
            code
            for code in execution_result.get("lifecycle_reason_codes", [])
            if isinstance(code, str) and code
        ]
    )
    if duplicate_terminal_write_observed or observed_terminal_write_count != 1:
        unresolved_state_exit_count += 1
        lifecycle_reason_codes.append("lifecycle_terminal_write_count_invalid")
    if interrupt_observed and not cleanup_completed:
        unresolved_state_exit_count += 1
        lifecycle_reason_codes.append("lifecycle_interrupt_cleanup_missing")
    if post_cancel_tool_return_count > 0:
        lifecycle_reason_codes.append("lifecycle_post_cancel_tool_return_observed")

    sequence_parts.append("runner_terminal_outcome_committed")
    execution_result["status"] = final_status
    execution_result["cleanup_completion_reason_codes"] = _dedupe_preserve_order(cleanup_reason_codes)
    execution_result["lifecycle_sequence_fingerprint"] = ">".join(sequence_parts)
    execution_result["unresolved_state_exit_count"] = unresolved_state_exit_count
    execution_result["post_cancel_tool_return_count"] = post_cancel_tool_return_count
    execution_result["cleanup_completed"] = cleanup_completed
    execution_result["cleanup_race_detected"] = interrupt_observed and not cleanup_completed
    execution_result["lifecycle_reason_codes"] = _dedupe_preserve_order(lifecycle_reason_codes)
    return final_status


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def _normalize_probe_phase(value: Any) -> str:
    if value in {"tool", "execute", "recover"}:
        return str(value)
    return "tool"


def _normalized_exit_code(value: Any, *, default: int) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value.strip())
        except Exception:
            return default
    return default


def _execute_probe_tool_call(
    tool_call: Any,
    sandbox: DockerSandbox,
    *,
    tool_executor: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    if not isinstance(tool_call, dict):
        return {
            "tool_name": "raw_bash",
            "command": "",
            "exit_code": 1,
            "stdout": "",
            "stderr": "runtime_probe_tool_call_malformed",
            "timed_out": False,
            "error": "runtime_probe_tool_call_malformed",
        }
    try:
        return tool_executor(tool_call, sandbox)
    except Exception as err:  # pragma: no cover - defensive conversion to normalized result
        return {
            "tool_name": "raw_bash",
            "command": _extract_probe_command(tool_call),
            "exit_code": 1,
            "stdout": "",
            "stderr": str(err),
            "timed_out": False,
            "error": f"{type(err).__name__}: {err}",
        }


def _extract_probe_command(tool_call: dict[str, Any]) -> str:
    arguments = tool_call.get("arguments")
    if isinstance(arguments, dict):
        command = arguments.get("command")
        if isinstance(command, str):
            return command
    if isinstance(arguments, str):
        return arguments
    return ""


def _resolve_route_manifest(*, seed_id: str, enforce_packet04_route_contract: bool) -> dict[str, Any]:
    if enforce_packet04_route_contract:
        return build_packet04_route_manifest(seed_id)
    return build_legacy_route_manifest(seed_id)


def _validate_runtime_callable_identity(
    *,
    candidate_manifest: dict[str, Any],
    baseline_manifest: dict[str, Any],
    candidate_callables: dict[str, Callable[..., Any]],
    baseline_callables: dict[str, Callable[..., Any]],
) -> None:
    baseline_by_surface = {entry["surface_id"]: entry for entry in baseline_manifest.get("routed_modules", [])}
    for entry in candidate_manifest.get("routed_modules", []):
        if not isinstance(entry, dict):
            continue
        runtime_key = entry.get("runtime_key")
        surface_id = entry.get("surface_id")
        if not isinstance(runtime_key, str) or not isinstance(surface_id, str):
            continue
        baseline_entry = baseline_by_surface.get(surface_id)
        if baseline_entry is None:
            continue
        candidate_callable = candidate_callables.get(runtime_key)
        baseline_callable = baseline_callables.get(runtime_key)
        if candidate_callable is None or baseline_callable is None:
            continue
        claimed_changed = bool(entry.get("claimed_changed_surface"))
        same_callable = _callable_identity(candidate_callable) == _callable_identity(baseline_callable)
        if claimed_changed and same_callable:
            raise ValueError(
                "claimed changed surface resolves to baseline callable identity "
                f"for runtime_key={runtime_key} surface_id={surface_id}"
            )
        if not claimed_changed and not same_callable:
            raise ValueError(
                "unchanged surface diverged callable identity "
                f"for runtime_key={runtime_key} surface_id={surface_id}"
            )


def _callable_identity(func: Callable[..., Any]) -> tuple[str, str]:
    return (getattr(func, "__module__", ""), getattr(func, "__qualname__", repr(func)))


def _call_with_supported_kwargs(func: Callable[..., Any], /, *args: Any, **kwargs: Any) -> Any:
    try:
        signature = inspect.signature(func)
    except (TypeError, ValueError):
        return func(*args)
    if any(param.kind == inspect.Parameter.VAR_KEYWORD for param in signature.parameters.values()):
        return func(*args, **kwargs)
    filtered = {
        key: value
        for key, value in kwargs.items()
        if key in signature.parameters
    }
    return func(*args, **filtered)


def _is_active_evidence_kernel_route(route_manifest: dict[str, Any]) -> bool:
    return str(route_manifest.get("variant_id") or "") in {
        "active_evidence_kernel_v1",
        "active_evidence_kernel_control_plane_context_v1",
    }


def _is_control_plane_context_route(route_manifest: dict[str, Any]) -> bool:
    return str(route_manifest.get("variant_id") or "") == "active_evidence_kernel_control_plane_context_v1"


def _append_control_plane_events(logger: RunLogger, control_plane_events: Any) -> None:
    if not isinstance(control_plane_events, list):
        return
    for event in control_plane_events:
        if not isinstance(event, dict):
            continue
        logger.append_event(
            phase=str(event.get("phase") or "context"),
            event_type=str(event.get("event_type") or "control_plane_event"),
            payload=event.get("payload") if isinstance(event.get("payload"), dict) else {"details": {}},
            artifact_refs=list(event.get("artifact_refs", [])) if isinstance(event.get("artifact_refs"), list) else None,
            correlation_id=event.get("correlation_id") if isinstance(event.get("correlation_id"), str) else None,
            ts_utc=event.get("ts_utc") if isinstance(event.get("ts_utc"), str) else None,
        )


def _merge_control_plane_state_for_export(
    *,
    execution_result: dict[str, Any],
    workspace_state: dict[str, Any],
    verified: bool,
    finalization_result: dict[str, Any],
) -> dict[str, Any]:
    control_plane_state = dict(execution_result.get("control_plane_state") or {})
    if not control_plane_state:
        return {}
    verifier_status = workspace_state.get("verifier_status") if isinstance(workspace_state.get("verifier_status"), dict) else {}
    if verifier_status:
        control_plane_state["verifier_state"] = dict(verifier_status)
    artifact_status = workspace_state.get("artifact_status") if isinstance(workspace_state.get("artifact_status"), dict) else control_plane_state.get("artifact_state", {})
    open_obligations = workspace_state.get("open_obligations") if isinstance(workspace_state.get("open_obligations"), dict) else control_plane_state.get("open_obligations", {})
    recovery_card = workspace_state.get("last_recovery_card") if isinstance(workspace_state.get("last_recovery_card"), dict) else control_plane_state.get("latest_recovery_card", {})
    control_plane_state["artifact_state"] = dict(artifact_status)
    control_plane_state["open_obligations"] = dict(open_obligations)
    control_plane_state["latest_recovery_card"] = dict(recovery_card)
    control_plane_state["verification_state"] = {
        "verified": bool(verified),
        "governed_status": str(finalization_result.get("governed_status") or ""),
        "final_verdict": str(finalization_result.get("final_verdict") or ""),
        "reason_codes": list(finalization_result.get("reason_codes", []))
        if isinstance(finalization_result.get("reason_codes"), list)
        else [],
    }
    if isinstance(workspace_state.get("control_plane_working_window"), dict):
        control_plane_state["last_working_window"] = dict(workspace_state["control_plane_working_window"])
    return control_plane_state


def _artifact_paths_present(root: Path, required_paths: list[str]) -> bool:
    if not required_paths:
        return False
    for rel_path in required_paths:
        candidate = Path(rel_path)
        if not candidate.is_absolute():
            candidate = root / candidate
        if not candidate.exists():
            return False
    return True


def _build_block_selection(route_manifest: dict[str, Any]) -> dict[str, str]:
    by_runtime_key = {
        entry["runtime_key"]: entry["module_import_path"]
        for entry in route_manifest.get("routed_modules", [])
    }
    return {
        "orientation": _module_label(by_runtime_key.get("orientation")) or BASELINE_BLOCK_SELECTION["orientation"],
        "tools": _module_label(by_runtime_key.get("tools_getter")) or BASELINE_BLOCK_SELECTION["tools"],
        "execution": _module_label(by_runtime_key.get("execution")) or BASELINE_BLOCK_SELECTION["execution"],
        "context": _module_label(by_runtime_key.get("context")) or BASELINE_BLOCK_SELECTION["context"],
        "verification": _module_label(by_runtime_key.get("verification")) or BASELINE_BLOCK_SELECTION["verification"],
        "recovery": _module_label(by_runtime_key.get("recovery")) or BASELINE_BLOCK_SELECTION["recovery"],
    }


def _module_label(spec: str | None) -> str | None:
    if not isinstance(spec, str) or ":" not in spec:
        return None
    module_name, callable_path = spec.split(":", 1)
    return f"{module_name.split('.')[-1]}:{callable_path.split('.')[-1]}"
