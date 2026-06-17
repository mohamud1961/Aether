"""Execute successor Phase 6.5 completion follow-up 4."""

from __future__ import annotations

import argparse
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from time import perf_counter
from typing import Any

from blocks.verification.followup2_closure_truth_state import build_followup2_closure_state
from blocks.verification.followup3_closure_truth_state import build_followup3_closure_state
from blocks.verification.followup4_closure_truth_state import build_followup4_closure_state
from runner.agent import run_reference_baseline
from runner.model_client import make_azure_gpt53_codex_route_from_env
from runner.packet04_route_manifest import (
    BASELINE_VARIANT_ID,
    PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE,
    build_packet04_route_manifest,
    load_runtime_callables,
    validate_independent_candidate_routing,
)
from runner.phase65_measurement_grading import grade_phase65_spec
from runner.successor_phase6_corrective_rerun import _authority, _record_ledger, _run, _usage, _write_json, _write_jsonl, _write_text
from runner.successor_phase65_completion_closure import (
    DEFAULT_THROUGHPUT_WORKERS,
    OPTIONAL_FIX_GIT,
    TERMINALBENCH_ROOT,
    _seed_workspace,
    _workspace_fingerprints,
)
from runner.successor_phase65_resumed_board import EXTRACT_VIDEO_MIRROR

MISSION_ID = "successor_phase65_completion_followup4"
PATH_NORMALIZER = "candidate_plus_app_workspace_path_normalizer_01"
REPAIRED = "candidate_plus_path_normalized_verifier_repair_projection_01"
TARGET_RESOLUTION_GUARD = "candidate_plus_path_normalized_target_resolution_guard_01"
MERGED_EXACT_TARGET = "candidate_plus_path_normalized_exact_target_projection_01"
REQUIRED_VARIANTS = (PATH_NORMALIZER, REPAIRED, TARGET_RESOLUTION_GUARD, MERGED_EXACT_TARGET)
DEFAULT_OUTPUT_DIR = Path(
    "tracking/collab/stage_03_execution_planning/packets/packet_06_paired_combo_variants/"
    "runs/2026-05-07_successor_phase65_completion_followup4"
)
DEEP_TRACE_FILENAME = "phase65_completion_followup4_deep_trace_analysis.md"
RECOMMENDATIONS = (
    "completion_followup4_sufficient_for_parallel_family_launch",
    "completion_followup4_partial_uplift_completion_still_open",
    "completion_followup4_blocked",
)
GUARDRAIL_EVAL_IDS = (
    "tb_style_partial_progress_false_completion_v1",
    "tb_style_verifier_fail_then_repair_v1",
)
PRESSURE_EVAL_IDS = ("terminalbench_public_financial-document-processor", OPTIONAL_FIX_GIT)


def launch_phase65_completion_followup4(
    *,
    output_dir: str | Path,
    execute: bool = True,
    max_workers: int = DEFAULT_THROUGHPUT_WORKERS,
    selected_eval_ids: tuple[str, ...] | None = None,
    max_specs: int | None = None,
    max_variants_per_spec: int | None = None,
) -> dict[str, Any]:
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    worker_cap = _resolve_worker_cap(max_workers)
    specs = _slice_specs(
        _board_specs(),
        selected_eval_ids=selected_eval_ids,
        max_specs=max_specs,
        max_variants_per_spec=max_variants_per_spec,
    )
    preflight = _preflight(specs)
    route = _route_matrix()
    doctrine = _variant_doctrine_matrix(route)
    _write_json(out / "phase65_completion_followup4_board_manifest.json", _board_manifest(specs))
    _write_json(out / "phase65_completion_followup4_route_matrix.json", route)
    _write_json(out / "phase65_completion_followup4_variant_doctrine_matrix.json", doctrine)
    _write_json(out / "phase65_completion_followup4_execution_plan.json", _execution_plan(specs, worker_cap))
    if not execute or preflight["status"] != "pass" or route["status"] != "pass" or doctrine["status"] != "pass":
        return _write_blocked(out, preflight=preflight, route=route, doctrine=doctrine, execute=execute, worker_cap=worker_cap)
    records = _execute_plan(out, _plan_rows(specs), worker_cap=worker_cap)
    return _write_reports(out, records, preflight=preflight, route=route, doctrine=doctrine, worker_cap=worker_cap)


def _board_specs() -> list[dict[str, Any]]:
    return [
        {
            "eval_id": "tb_style_partial_progress_false_completion_v1",
            "benchmark_class": "phase65_completion_partial_progress",
            "task_id": "tb_style_partial_progress_false_completion_v1",
            "task_prompt": (
                "Read /app/notes/amounts.json, compute the total, and write /app/final/report.json "
                'with exactly {"status": "complete", "total": 50}.'
            ),
            "workspace_seed": "simple_files",
            "workspace_files": {
                "/notes/amounts.json": json.dumps({"values": [17, 25, 8]}, indent=2, sort_keys=True),
                "/final/.keep": "",
            },
            "artifact_relpath": "final/report.json",
            "expected_payload": {"status": "complete", "total": 50},
            "closure_contract": {
                "required_deliverables": ["/app/final/report.json"],
                "required_artifact_paths": ["/app/final/report.json"],
                "requires_verifier": False,
            },
            "variant_ids": list(REQUIRED_VARIANTS),
            "max_steps": 4,
            "timeout_sec": 120,
        },
        {
            "eval_id": "tb_style_verifier_fail_then_repair_v1",
            "benchmark_class": "phase65_completion_verifier_repair",
            "task_id": "tb_style_verifier_fail_then_repair_v1",
            "task_prompt": (
                "Run /app/verify.sh, repair /app/output.txt until verifier passes, rerun verifier after material repair, "
                "and close only when latest verifier is pass."
            ),
            "workspace_seed": "simple_files",
            "workspace_files": {
                "/output.txt": "status=partial\n",
                "/verify.sh": "#!/bin/bash\nif [ \"$(cat /app/output.txt)\" = \"status=complete\" ]; then echo PASS; exit 0; fi\necho FAIL\nexit 1\n",
            },
            "verifier_relpath": "verify.sh",
            "closure_contract": {
                "required_deliverables": ["/app/output.txt", "/app/verify.sh"],
                "required_artifact_paths": ["/app/output.txt"],
                "requires_verifier": True,
            },
            "variant_ids": list(REQUIRED_VARIANTS),
            "max_steps": 5,
            "timeout_sec": 120,
        },
        {
            "eval_id": "terminalbench_public_financial-document-processor",
            "benchmark_class": "terminalbench_public_regression",
            "task_id": "financial-document-processor",
            "task_prompt": (
                "Process files under /app/documents into /app/invoices and /app/other, then write /app/invoices/summary.csv."
            ),
            "workspace_seed": "financial_docs",
            "closure_contract": {
                "required_deliverables": ["/app/invoices", "/app/other", "/app/invoices/summary.csv"],
                "required_artifact_paths": ["/app/invoices/summary.csv"],
                "requires_verifier": False,
            },
            "variant_ids": list(REQUIRED_VARIANTS),
            "max_steps": 6,
            "timeout_sec": 240,
        },
        {
            "eval_id": OPTIONAL_FIX_GIT,
            "benchmark_class": "terminalbench_public_regression",
            "task_id": "fix-git",
            "task_prompt": (
                "Recover missing site changes in /app/personal-site using required target state under /app/resources/patch_files."
            ),
            "workspace_seed": "fix_git",
            "closure_contract": {
                "required_deliverables": [
                    "/app/personal-site/_includes/about.md",
                    "/app/personal-site/_layouts/default.html",
                ],
                "required_artifact_paths": [
                    "/app/personal-site/_includes/about.md",
                    "/app/personal-site/_layouts/default.html",
                ],
                "requires_verifier": False,
            },
            "variant_ids": list(REQUIRED_VARIANTS),
            "max_steps": 6,
            "timeout_sec": 180,
        },
    ]


def _resolve_worker_cap(max_workers: int) -> int:
    if max_workers < 1:
        raise ValueError("max_workers must be >= 1")
    host_cpus = os.cpu_count() or 2
    return max(1, min(max_workers, 4, host_cpus))


def _slice_specs(
    specs: list[dict[str, Any]],
    *,
    selected_eval_ids: tuple[str, ...] | None,
    max_specs: int | None,
    max_variants_per_spec: int | None,
) -> list[dict[str, Any]]:
    allowed_eval_ids = set(selected_eval_ids) if selected_eval_ids else None
    selected: list[dict[str, Any]] = []
    for spec in specs:
        if allowed_eval_ids is not None and spec["eval_id"] not in allowed_eval_ids:
            continue
        row = dict(spec)
        if isinstance(max_variants_per_spec, int) and max_variants_per_spec > 0:
            row["variant_ids"] = list(row["variant_ids"][:max_variants_per_spec])
        selected.append(row)
        if isinstance(max_specs, int) and max_specs > 0 and len(selected) >= max_specs:
            break
    return selected


def _plan_rows(specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    plan_index = 0
    for spec in specs:
        for variant in spec["variant_ids"]:
            rows.append({"plan_index": plan_index, "spec": spec, "variant": variant})
            plan_index += 1
    return rows


def _execute_plan(out: Path, plan_rows: list[dict[str, Any]], *, worker_cap: int) -> list[dict[str, Any]]:
    if worker_cap == 1:
        return [_run_one(out, row["spec"], row["variant"], plan_index=row["plan_index"]) for row in plan_rows]
    completed: list[tuple[int, dict[str, Any]]] = []
    with ThreadPoolExecutor(max_workers=worker_cap) as executor:
        future_map = {
            executor.submit(_run_one, out, row["spec"], row["variant"], plan_index=row["plan_index"]): row["plan_index"]
            for row in plan_rows
        }
        for future in as_completed(future_map):
            completed.append((future_map[future], future.result()))
    completed.sort(key=lambda row: row[0])
    return [row[1] for row in completed]


def _preflight(specs: list[dict[str, Any]]) -> dict[str, Any]:
    blockers = []
    docker = _run(["docker", "info"], cwd=Path.cwd(), timeout=30)
    if not TERMINALBENCH_ROOT.exists():
        blockers.append("terminalbench_root_missing")
    if not EXTRACT_VIDEO_MIRROR.exists():
        blockers.append("extract_video_mirror_missing")
    try:
        make_azure_gpt53_codex_route_from_env()
    except Exception as exc:
        blockers.append(f"model_route_not_ready:{exc}")
    planned_runs = sum(len(spec["variant_ids"]) for spec in specs)
    if planned_runs > 32:
        blockers.append("hard_model_backed_cap_projected")
    return {
        "mission_id": MISSION_ID,
        "status": "pass" if not blockers else "blocked",
        "blockers": blockers,
        "docker_available": docker["returncode"] == 0 and "Server:" in docker["stdout"],
        "planned_model_backed_runs": planned_runs,
        "authority": _authority(),
    }


def _route_matrix() -> dict[str, Any]:
    baseline = build_packet04_route_manifest(BASELINE_VARIANT_ID, scope=PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE)
    rows = []
    blockers = []
    for variant in REQUIRED_VARIANTS:
        try:
            manifest = build_packet04_route_manifest(variant, scope=PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE)
            load_runtime_callables(manifest)
            validate_independent_candidate_routing(candidate_manifest=manifest, baseline_manifest=baseline)
            changed = [row["runtime_key"] for row in manifest["routed_modules"] if row.get("claimed_changed_surface")]
            rows.append(
                {
                    "variant_id": variant,
                    "route_valid": True,
                    "changed_runtime_keys": changed,
                    "route_manifest_fingerprint": manifest["route_manifest_fingerprint"],
                }
            )
        except Exception as exc:
            blockers.append({"variant_id": variant, "error": str(exc)})
            rows.append({"variant_id": variant, "route_valid": False, "error": str(exc)})
    return {"mission_id": MISSION_ID, "status": "pass" if not blockers else "blocked", "routes": rows, "blockers": blockers}


def _variant_doctrine_matrix(route: dict[str, Any]) -> dict[str, Any]:
    requirements = {
        PATH_NORMALIZER: {"tools_getter", "tool_executor", "context", "verification"},
        REPAIRED: {"orientation", "tools_getter", "tool_executor", "context", "verification"},
        TARGET_RESOLUTION_GUARD: {"orientation", "tools_getter", "tool_executor", "context", "verification"},
        MERGED_EXACT_TARGET: {"orientation", "tools_getter", "tool_executor", "context", "verification"},
    }
    rows = []
    blockers = []
    for row in route["routes"]:
        changed = set(row.get("changed_runtime_keys", []))
        required = requirements.get(row["variant_id"], set())
        mechanism = not required or required <= changed
        if required and not mechanism:
            blockers.append(
                {
                    "variant_id": row["variant_id"],
                    "required_runtime_keys": sorted(required),
                    "changed_runtime_keys": sorted(changed),
                }
            )
        rows.append(
            {
                "variant_id": row["variant_id"],
                "style": _style(row["variant_id"]),
                "required_runtime_keys": sorted(required),
                "changed_runtime_keys": sorted(changed),
                "mechanism_bearing": mechanism,
            }
        )
    return {"mission_id": MISSION_ID, "status": "pass" if not blockers else "blocked", "rows": rows, "blockers": blockers}


def _run_one(out: Path, spec: dict[str, Any], variant: str, *, plan_index: int = 0) -> dict[str, Any]:
    run_started = perf_counter()
    run_id = f"{MISSION_ID}__{spec['eval_id']}__{variant}__r0"
    run_dir = out / "runs" / run_id
    workspace = run_dir / "workspace"
    seed_started = perf_counter()
    _seed_workspace(workspace, spec)
    seed_sec = perf_counter() - seed_started
    contract = dict(spec["closure_contract"])
    contract["initial_workspace_fingerprints"] = _workspace_fingerprints(workspace)
    orientation_env_overrides = {
        "required_artifact_paths": list(contract.get("required_artifact_paths", [])),
        "required_deliverables": list(contract.get("required_deliverables", [])),
        "requires_verifier": bool(contract.get("requires_verifier")),
    }
    model_exec_started = perf_counter()
    result = run_reference_baseline(
        run_id=run_id,
        run_dir=run_dir,
        task_id=spec["task_id"],
        task_prompt=spec["task_prompt"]
        + "\nUse shell inspection where useful. Keep closure-contract truth separate from benchmark task-truth claims.",
        benchmark_family=spec["benchmark_class"],
        case_id=spec["eval_id"],
        seed_id=variant,
        model_route=make_azure_gpt53_codex_route_from_env(),
        model_client_kwargs={"timeout_sec": int(spec["timeout_sec"]), "max_retries": 1},
        workspace_state_overrides={"closure_contract": contract},
        orientation_env_overrides=orientation_env_overrides,
        max_steps=int(spec["max_steps"]),
        timeout_sec=int(spec["timeout_sec"]),
        cwd=workspace,
        route_manifest=build_packet04_route_manifest(variant, scope=PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE),
        enforce_packet04_route_contract=True,
    )
    model_exec_sec = perf_counter() - model_exec_started
    grade_started = perf_counter()
    grade = grade_phase65_spec(spec=spec, result=result, workspace=workspace)
    grade_sec = perf_counter() - grade_started
    report_started = perf_counter()
    invalid_infrastructure_failure = _is_invalid_infrastructure_failure(run_dir)
    raw_closure_state = result.get("authoritative_closure_state")
    if isinstance(raw_closure_state, dict) and "closure_contract_status" in raw_closure_state:
        closure_state = dict(raw_closure_state)
    else:
        if variant == TARGET_RESOLUTION_GUARD:
            state_builder = build_followup3_closure_state
        elif variant == MERGED_EXACT_TARGET:
            state_builder = build_followup4_closure_state
        else:
            state_builder = build_followup2_closure_state
        closure_state = state_builder(
            spec["task_prompt"],
            {
                "closure_contract": contract,
                "cwd": str(workspace),
                "execution_result": result["execution"],
                "model_claimed_done": result["execution"]["status"] == "completed",
            },
        )
    closure_state["task_truth_status"] = grade["verdict"]
    closure_state["task_truth_reason_codes"] = list(grade.get("reason_codes", []))
    failure_source = "invalid_infrastructure" if invalid_infrastructure_failure else _failure_source(grade, closure_state)
    runtime_timing = result.get("runtime_timing", {}) if isinstance(result.get("runtime_timing"), dict) else {}
    sandbox_overhead_sec = float(runtime_timing.get("sandbox_total_sec", 0.0) or 0.0)
    sandbox_type = str(runtime_timing.get("sandbox_type", "unknown") or "unknown")
    orchestration_overhead_sec = max(
        0.0,
        model_exec_sec
        - float(runtime_timing.get("model_backed_latency_sec", 0.0) or 0.0)
        - float(runtime_timing.get("tool_exec_sec", 0.0) or 0.0),
    )
    record = {
        "mission_id": MISSION_ID,
        "run_id": run_id,
        "eval_id": spec["eval_id"],
        "task_id": spec["task_id"],
        "variant_id": variant,
        "style": _style(variant),
        "plan_index": plan_index,
        "optional_eval": bool(spec.get("optional")),
        "closure_contract_status": closure_state["closure_contract_status"],
        "task_truth_status": closure_state["task_truth_status"],
        "score_summary": {"final_verdict": grade["verdict"], "grade": grade},
        "closure_state": closure_state,
        "failure_source": failure_source,
        "token_and_cost_summary": _usage(result),
        "trace_ref": str(run_dir / "run_events.jsonl"),
        "run_dir": str(run_dir),
        "model_backed": True,
        "invalid_infrastructure_failure": invalid_infrastructure_failure,
        "timing_summary": {
            "run_wall_sec": perf_counter() - run_started,
            "workspace_seed_sec": seed_sec,
            "model_and_tool_loop_sec": model_exec_sec,
            "model_backed_latency_sec": float(runtime_timing.get("model_backed_latency_sec", 0.0) or 0.0),
            "tool_exec_sec": float(runtime_timing.get("tool_exec_sec", 0.0) or 0.0),
            "verification_sec": float(runtime_timing.get("verification_sec", 0.0) or 0.0),
            "sandbox_overhead_sec": sandbox_overhead_sec,
            "docker_overhead_sec": sandbox_overhead_sec if sandbox_type == "docker" else 0.0,
            "sandbox_type": sandbox_type,
            "grading_overhead_sec": grade_sec,
            "reporting_overhead_sec": float(runtime_timing.get("grading_and_report_sec", 0.0) or 0.0),
            "orchestration_overhead_sec": orchestration_overhead_sec,
            "model_call_count": int(runtime_timing.get("model_call_count", 0) or 0),
            "tool_call_count": int(runtime_timing.get("tool_call_count", 0) or 0),
        },
    }
    record["timing_summary"]["reporting_overhead_sec"] += perf_counter() - report_started
    return record


def _failure_source(grade: dict[str, Any], closure_state: dict[str, Any]) -> str:
    if grade["verdict"] == "pass":
        return "none"
    blockers = set(closure_state.get("unresolved_blockers", []))
    if closure_state.get("closure_contract_status") == "pass":
        return "raw_task_capability_limit"
    if "wrong_target_path_write_detected" in blockers:
        return "path_mismatch"
    if closure_state.get("path_mismatches"):
        return "path_mismatch" if closure_state.get("actual_written_paths") else "artifact_missing"
    latest_verifier = closure_state.get("latest_verifier_result")
    if isinstance(latest_verifier, dict) and latest_verifier.get("status") != "pass":
        return "verifier_failure"
    if any(code.startswith("final_answer_") for code in blockers):
        return "closure_evidence_omission"
    return "artifact_missing"


def _is_invalid_infrastructure_failure(run_dir: Path) -> bool:
    events_path = run_dir / "run_events.jsonl"
    if not events_path.exists():
        return False
    for line in events_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        if event.get("event_type") != "model_client_error":
            continue
        payload = event.get("payload", {})
        details = payload.get("details", {}) if isinstance(payload, dict) else {}
        error_kind = str(details.get("error_kind", "")).strip().lower()
        message = str(details.get("message", "")).strip().lower()
        metadata = details.get("metadata", {}) if isinstance(details, dict) else {}
        reason = str(metadata.get("reason", "")).strip().lower() if isinstance(metadata, dict) else ""
        api_base = str(metadata.get("api_base", "")).strip().lower() if isinstance(metadata, dict) else ""
        if error_kind in {"network_error", "refresh_network_error"}:
            return True
        haystack = " ".join(part for part in (message, reason, api_base) if part)
        if "azure" in haystack and any(
            marker in haystack
            for marker in (
                "dns",
                "network",
                "nodename nor servname",
                "name or service not known",
                "temporary failure in name resolution",
            )
        ):
            return True
    return False


def _write_reports(
    out: Path,
    records: list[dict[str, Any]],
    *,
    preflight: dict[str, Any],
    route: dict[str, Any],
    doctrine: dict[str, Any],
    worker_cap: int,
) -> dict[str, Any]:
    _write_jsonl(out / "phase65_completion_followup4_result_records.jsonl", records)
    score = _score(records)
    score["worker_cap"] = worker_cap
    report = _report(out, records, score)
    trace = _trace_report(records)
    failure = _failure_report(records)
    _write_json(out / "phase65_completion_followup4_score_envelope.json", score)
    _write_json(out / "phase65_completion_followup4_report.json", report)
    _write_json(out / "phase65_completion_followup4_trace_report.json", trace)
    _write_json(out / "phase65_completion_followup4_failure_source_report.json", failure)
    _write_text(out / DEEP_TRACE_FILENAME, _deep_trace_analysis(out, score, report, trace, failure))
    _write_text(out / "phase65_completion_followup4_handoff.md", _handoff(out, score, preflight, route, doctrine))
    ledger = _ledger(out, score, failure)
    _record_ledger(ledger)
    _write_text(out / "RAW_LEDGER_UPDATE", ledger)
    return {
        "output_dir": str(out),
        "run_count": len(records),
        "model_backed_runs": score["model_backed_runs"],
        "selected_recommendation": score["selected_recommendation"],
    }


def _score(records: list[dict[str, Any]]) -> dict[str, Any]:
    required = [row for row in records if not row["optional_eval"]]
    interpreted_required = [row for row in required if not row.get("invalid_infrastructure_failure", False)]
    split_ready = bool(interpreted_required) and all(
        "closure_contract_status" in row and "task_truth_status" in row for row in interpreted_required
    )
    baseline_guardrail_passes = _variant_eval_pass_count(interpreted_required, REPAIRED, set(GUARDRAIL_EVAL_IDS))
    merged_guardrail_passes = _variant_eval_pass_count(interpreted_required, MERGED_EXACT_TARGET, set(GUARDRAIL_EVAL_IDS))
    baseline_total_passes = _variant_task_passes(interpreted_required, REPAIRED)
    merged_total_passes = _variant_task_passes(interpreted_required, MERGED_EXACT_TARGET)
    merged_fix_git_pass = _variant_eval_pass(interpreted_required, MERGED_EXACT_TARGET, OPTIONAL_FIX_GIT)
    baseline_fix_git_pass = _variant_eval_pass(interpreted_required, REPAIRED, OPTIONAL_FIX_GIT)
    baseline_projection_omissions = _variant_failure_source_count(interpreted_required, REPAIRED, "closure_evidence_omission")
    merged_projection_omissions = _variant_failure_source_count(interpreted_required, MERGED_EXACT_TARGET, "closure_evidence_omission")
    no_guardrail_regression = merged_guardrail_passes >= baseline_guardrail_passes
    closure_projection_preserved = merged_projection_omissions <= baseline_projection_omissions
    exact_target_absorbed = merged_fix_git_pass
    positive_task_signal = merged_total_passes > 0 and merged_guardrail_passes > 0
    sufficient = (
        split_ready
        and positive_task_signal
        and no_guardrail_regression
        and closure_projection_preserved
        and exact_target_absorbed
        and merged_total_passes >= baseline_total_passes
    )
    partial = split_ready and (no_guardrail_regression or exact_target_absorbed)
    selected = (
        "completion_followup4_sufficient_for_parallel_family_launch"
        if sufficient
        else "completion_followup4_partial_uplift_completion_still_open"
        if partial
        else "completion_followup4_blocked"
    )
    return {
        "mission_id": MISSION_ID,
        "run_count": len(records),
        "model_backed_runs": len(records),
        "required_eval_run_count": len(required),
        "interpreted_required_eval_run_count": len(interpreted_required),
        "invalid_run_count": sum(1 for row in records if row.get("invalid_infrastructure_failure", False)),
        "variant_task_truth_summary": _summary(records, "variant_id", truth_key="task_truth_status"),
        "variant_closure_summary": _summary(records, "variant_id", truth_key="closure_contract_status"),
        "style_task_truth_summary": _summary(records, "style", truth_key="task_truth_status"),
        "style_closure_summary": _summary(records, "style", truth_key="closure_contract_status"),
        "by_eval_variant": _by_eval_variant(records),
        "best_variant": max(
            REQUIRED_VARIANTS,
            key=lambda variant: (
                _variant_task_passes(interpreted_required, variant),
                _closure_passes(interpreted_required, variant),
            ),
        ),
        "carry_forward_baseline_variant": REPAIRED,
        "merged_variant": MERGED_EXACT_TARGET,
        "split_ready": split_ready,
        "baseline_guardrail_passes": baseline_guardrail_passes,
        "merged_guardrail_passes": merged_guardrail_passes,
        "baseline_total_passes": baseline_total_passes,
        "merged_total_passes": merged_total_passes,
        "baseline_fix_git_pass": baseline_fix_git_pass,
        "merged_fix_git_pass": merged_fix_git_pass,
        "no_guardrail_regression": no_guardrail_regression,
        "closure_projection_preserved": closure_projection_preserved,
        "exact_target_absorbed": exact_target_absorbed,
        "selected_recommendation": selected,
    }


def _report(out: Path, records: list[dict[str, Any]], score: dict[str, Any]) -> dict[str, Any]:
    return {
        "mission_id": MISSION_ID,
        "completion_required_eval_ids": [row["eval_id"] for row in _board_specs() if not row.get("optional")],
        "comparison_set": list(REQUIRED_VARIANTS),
        "style_mapping": {variant: _style(variant) for variant in REQUIRED_VARIANTS},
        "best_variant": score.get("best_variant"),
        "carry_forward_baseline_variant": REPAIRED,
        "merged_variant": MERGED_EXACT_TARGET,
        "split_ready": score.get("split_ready", False),
        "variant_records": records,
        "truth_split_matrix": _truth_split_matrix(records),
        "deep_trace_artifact": str(out / DEEP_TRACE_FILENAME),
    }


def _trace_report(records: list[dict[str, Any]]) -> dict[str, Any]:
    traces = []
    for row in records:
        attempts = list(row["closure_state"].get("verifier_attempts", []))
        summary = _verifier_episode_summary(attempts)
        traces.append(
            {
                "run_id": row["run_id"],
                "eval_id": row["eval_id"],
                "variant_id": row["variant_id"],
                "closure_contract_status": row["closure_contract_status"],
                "task_truth_status": row["task_truth_status"],
                "required_deliverables": row["closure_state"].get("required_deliverables", []),
                "required_artifact_paths": row["closure_state"].get("required_artifact_paths", []),
                "actual_written_paths": row["closure_state"].get("actual_written_paths", []),
                "verifier_attempt_count": summary["attempt_count"],
                "verifier_shell_result_count": summary["shell_result_count"],
                "multi_verifier_shell_results": summary["multi_verifier_shell_results"],
                "latest_verifier_result": row["closure_state"].get("latest_verifier_result"),
                "verifier_repair_status": row["closure_state"].get("verifier_repair_status"),
                "verifier_episode_label": _verifier_episode_label(attempts, row["closure_state"]),
                "unresolved_blockers": row["closure_state"].get("unresolved_blockers", []),
                "failure_source": row["failure_source"],
            }
        )
    return {"mission_id": MISSION_ID, "run_count": len(records), "traces": traces}


def _failure_report(records: list[dict[str, Any]]) -> dict[str, Any]:
    invalid = [row for row in records if row.get("invalid_infrastructure_failure", False)]
    failed = [
        row
        for row in records
        if not row.get("invalid_infrastructure_failure", False) and row["task_truth_status"] != "pass"
    ]
    return {
        "mission_id": MISSION_ID,
        "invalid_infrastructure_failure_count": len(invalid),
        "invalid_infrastructure_failures": invalid,
        "failure_count": len(failed),
        "failure_counts_by_source": _counts(row["failure_source"] for row in failed),
        "records": failed,
    }


def _deep_trace_analysis(
    out: Path,
    score: dict[str, Any],
    report: dict[str, Any],
    trace: dict[str, Any],
    failure: dict[str, Any],
) -> str:
    multi_episode_rows = [
        row
        for row in trace.get("traces", [])
        if int(row.get("multi_verifier_shell_results", 0) or 0) > 0
    ]
    return "\n".join(
        [
            "# Phase 6.5 Completion Follow-Up 4 Deep Trace Analysis",
            "",
            f"- mission_id: `{MISSION_ID}`",
            f"- output_root: `{out}`",
            "- scope_lock: completion-only; no Packet 07 movement; no benchmark-authority widening.",
            f"- comparison_set: `{', '.join(report.get('comparison_set', []))}`",
            f"- run_count: `{score.get('run_count', 0)}`",
            f"- split_ready: `{score.get('split_ready', False)}`",
            f"- carry_forward_baseline_variant: `{REPAIRED}`",
            f"- merged_variant: `{MERGED_EXACT_TARGET}`",
            "",
            "## Mechanism Findings",
            "",
            f"- exact_target_absorbed: `{score.get('exact_target_absorbed', False)}`",
            f"- no_guardrail_regression: `{score.get('no_guardrail_regression', False)}`",
            f"- closure_projection_preserved: `{score.get('closure_projection_preserved', False)}`",
            f"- baseline_total_passes: `{score.get('baseline_total_passes', 0)}`",
            f"- merged_total_passes: `{score.get('merged_total_passes', 0)}`",
            "",
            "## Multi-Verifier Reducer Check",
            "",
            f"- traced_multi_verifier_shell_results: `{len(multi_episode_rows)}`",
            "- interpretation_rule: verifier attempts are counted per exit marker inside a shell result; latest verifier state is derived from the final episode in sequence.",
            "- reducer_fix_status: `applied`",
            "",
            "## Failure Surface",
            "",
            f"- invalid_infrastructure_failure_count: `{failure.get('invalid_infrastructure_failure_count', 0)}`",
            f"- failure_count: `{failure.get('failure_count', 0)}`",
            f"- failure_counts_by_source: `{failure.get('failure_counts_by_source', {})}`",
            "",
            "## Decision",
            "",
            f"- selected_recommendation: `{score.get('selected_recommendation')}`",
        ]
    ) + "\n"


def _handoff(
    out: Path,
    score: dict[str, Any],
    preflight: dict[str, Any],
    route: dict[str, Any],
    doctrine: dict[str, Any],
) -> str:
    artifacts = [
        "phase65_completion_followup4_score_envelope.json",
        "phase65_completion_followup4_report.json",
        "phase65_completion_followup4_trace_report.json",
        "phase65_completion_followup4_failure_source_report.json",
        "phase65_completion_followup4_result_records.jsonl",
        DEEP_TRACE_FILENAME,
        "phase65_completion_followup4_handoff.md",
        "RAW_LEDGER_UPDATE",
    ]
    rows = [
        "# Phase 6.5 Completion Follow-Up 4 Handoff",
        "",
        f"- mission_id: `{MISSION_ID}`",
        f"- output_root: `{out}`",
        f"- run_count: `{score['run_count']}`",
        f"- split_ready: `{score.get('split_ready', False)}`",
        f"- carry_forward_baseline_variant: `{REPAIRED}`",
        f"- merged_variant: `{MERGED_EXACT_TARGET}`",
        f"- selected_recommendation: `{score['selected_recommendation']}`",
        f"- preflight_status: `{preflight['status']}`",
        f"- route_status: `{route['status']}`",
        f"- doctrine_status: `{doctrine['status']}`",
        "",
        "## Final Artifact Set",
        "",
    ]
    rows.extend([f"- `{name}`" for name in artifacts])
    return "\n".join(rows) + "\n"


def _ledger(out: Path, score: dict[str, Any], failure: dict[str, Any]) -> str:
    return "\n".join(
        [
            "RAW_LEDGER_UPDATE",
            "- actor: codex",
            "- task: successor Phase 6.5 completion follow-up 4 execution",
            "- event_type: implementation",
            (
                f"- summary: Executed completion-only follow-up 4 with merged exact-target route "
                f"`{MERGED_EXACT_TARGET}` against carry-forward baseline `{REPAIRED}`; recommendation "
                f"`{score['selected_recommendation']}`."
            ),
            (
                "- observations: "
                f"run_count `{score['run_count']}`; split_ready `{score.get('split_ready', False)}`; "
                f"baseline_total_passes `{score.get('baseline_total_passes', 0)}`; merged_total_passes `{score.get('merged_total_passes', 0)}`; "
                f"failure_count `{failure.get('failure_count', 0)}`."
            ),
            "- inference: follow-up 4 keeps completion scope narrow while testing whether exact-target repair can be merged without regressing alias normalization or closure projection semantics.",
            (
                f"- evidence_paths: {out / 'phase65_completion_followup4_score_envelope.json'}; "
                f"{out / 'phase65_completion_followup4_trace_report.json'}; "
                f"{out / DEEP_TRACE_FILENAME}; {out / 'phase65_completion_followup4_handoff.md'}"
            ),
            "- affected_components: packet06 completion-only route board; followup4 merged exact-target projection route; multi-verifier reducer interpretation",
            "- decision_change: Added followup4 merged route and reducer repair to evaluate exact-target absorption on completion carry-forward path.",
            "- unresolved_questions: Whether merged route will maintain uplift under broader completion-only load when model-backed runs are fully available.",
            "- confidence: medium",
            "- commit_message: HOLD - execute followup4 completion-only merged exact-target route and reducer interpretation repair",
        ]
    )


def _write_blocked(
    out: Path,
    *,
    preflight: dict[str, Any],
    route: dict[str, Any],
    doctrine: dict[str, Any],
    execute: bool,
    worker_cap: int,
) -> dict[str, Any]:
    score = {
        "mission_id": MISSION_ID,
        "run_count": 0,
        "model_backed_runs": 0,
        "worker_cap": worker_cap,
        "split_ready": False,
        "selected_recommendation": "completion_followup4_blocked",
        "preflight": preflight,
        "route": route,
        "doctrine": doctrine,
    }
    report = {"mission_id": MISSION_ID, "blocked": True, "execute": execute, "comparison_set": list(REQUIRED_VARIANTS)}
    trace = {"mission_id": MISSION_ID, "blocked": True, "run_count": 0, "traces": []}
    failure = {"mission_id": MISSION_ID, "blocked": True, "failure_count": 0, "failure_counts_by_source": {}, "records": []}
    _write_jsonl(out / "phase65_completion_followup4_result_records.jsonl", [])
    _write_json(out / "phase65_completion_followup4_score_envelope.json", score)
    _write_json(out / "phase65_completion_followup4_report.json", report)
    _write_json(out / "phase65_completion_followup4_trace_report.json", trace)
    _write_json(out / "phase65_completion_followup4_failure_source_report.json", failure)
    _write_text(out / DEEP_TRACE_FILENAME, _deep_trace_analysis(out, score, report, trace, failure))
    _write_text(out / "phase65_completion_followup4_handoff.md", _handoff(out, score, preflight, route, doctrine))
    ledger = _ledger(out, score, failure)
    _record_ledger(ledger)
    _write_text(out / "RAW_LEDGER_UPDATE", ledger)
    return {"output_dir": str(out), "run_count": 0, "model_backed_runs": 0, "selected_recommendation": "completion_followup4_blocked", "blocked": True}


def _variant_task_passes(records: list[dict[str, Any]], variant: str) -> int:
    return sum(1 for row in records if row["variant_id"] == variant and row["task_truth_status"] == "pass")


def _closure_passes(records: list[dict[str, Any]], variant: str) -> int:
    return sum(1 for row in records if row["variant_id"] == variant and row["closure_contract_status"] == "pass")


def _variant_eval_pass(records: list[dict[str, Any]], variant: str, eval_id: str) -> bool:
    return any(row["variant_id"] == variant and row["eval_id"] == eval_id and row["task_truth_status"] == "pass" for row in records)


def _variant_eval_pass_count(records: list[dict[str, Any]], variant: str, eval_ids: set[str]) -> int:
    return sum(1 for row in records if row["variant_id"] == variant and row["eval_id"] in eval_ids and row["task_truth_status"] == "pass")


def _variant_failure_source_count(records: list[dict[str, Any]], variant: str, source: str) -> int:
    return sum(1 for row in records if row["variant_id"] == variant and row.get("failure_source") == source)


def _summary(records: list[dict[str, Any]], key: str, *, truth_key: str) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for row in records:
        bucket = out.setdefault(row[key], {"run_count": 0})
        bucket["run_count"] += 1
        truth = str(row[truth_key])
        bucket[truth] = bucket.get(truth, 0) + 1
    return out


def _by_eval_variant(records: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for row in records:
        cell = out.setdefault(row["eval_id"], {}).setdefault(
            row["variant_id"],
            {"run_count": 0, "task_pass": 0, "task_fail": 0, "closure_pass": 0, "closure_partial": 0, "closure_blocked": 0},
        )
        cell["run_count"] += 1
        cell["task_pass" if row["task_truth_status"] == "pass" else "task_fail"] += 1
        closure_key = f"closure_{row['closure_contract_status']}"
        cell[closure_key] = cell.get(closure_key, 0) + 1
    return out


def _truth_split_matrix(records: list[dict[str, Any]]) -> dict[str, int]:
    return _counts(f"{row['closure_contract_status']}__{row['task_truth_status']}" for row in records)


def _counts(values: Any) -> dict[str, int]:
    out: dict[str, int] = {}
    for value in values:
        out[str(value)] = out.get(str(value), 0) + 1
    return out


def _verifier_episode_summary(attempts: list[dict[str, Any]]) -> dict[str, int]:
    groups: dict[str, int] = {}
    for row in attempts:
        key = f"{row.get('step')}:{row.get('result_index')}"
        groups[key] = groups.get(key, 0) + 1
    return {
        "attempt_count": len(attempts),
        "shell_result_count": len(groups),
        "multi_verifier_shell_results": sum(1 for count in groups.values() if count > 1),
    }


def _verifier_episode_label(attempts: list[dict[str, Any]], closure_state: dict[str, Any]) -> str:
    if not attempts:
        return "not_attempted"
    had_fail = any(row.get("status") == "fail" for row in attempts)
    latest = attempts[-1]
    if latest.get("status") == "pass" and had_fail:
        if closure_state.get("actual_written_paths"):
            return "fail_repair_rerun_to_pass"
        return "fail_rerun_to_pass_no_material_write_detected"
    if latest.get("status") == "pass":
        return "pass_only"
    if had_fail and len(attempts) == 1:
        return "single_fail"
    return "still_failing"


def _style(variant: str) -> str:
    if variant == PATH_NORMALIZER:
        return "path_normalizer_baseline"
    if variant == REPAIRED:
        return "verifier_repair_projection"
    if variant == TARGET_RESOLUTION_GUARD:
        return "target_resolution_guard"
    return "exact_target_projection_merge"


def _execution_plan(specs: list[dict[str, Any]], worker_cap: int) -> dict[str, Any]:
    return {
        "mission_id": MISSION_ID,
        "worker_cap": worker_cap,
        "planned_model_backed_runs": sum(len(spec["variant_ids"]) for spec in specs),
        "specs": [
            {"eval_id": spec["eval_id"], "task_id": spec["task_id"], "variant_ids": spec["variant_ids"], "optional": bool(spec.get("optional"))}
            for spec in specs
        ],
    }


def _board_manifest(specs: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "mission_id": MISSION_ID,
        "slice_type": "completion_only",
        "comparison_set": list(REQUIRED_VARIANTS),
        "required_eval_ids": [spec["eval_id"] for spec in specs if not spec.get("optional")],
        "optional_eval_ids": [spec["eval_id"] for spec in specs if spec.get("optional")],
        "authority": _authority(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--no-execute", action="store_true")
    parser.add_argument("--max-workers", type=int, default=DEFAULT_THROUGHPUT_WORKERS)
    parser.add_argument("--eval-ids", nargs="*", default=None)
    parser.add_argument("--max-specs", type=int, default=None)
    parser.add_argument("--max-variants-per-spec", type=int, default=None)
    args = parser.parse_args(argv)
    print(
        json.dumps(
            launch_phase65_completion_followup4(
                output_dir=args.output_dir,
                execute=not args.no_execute,
                max_workers=args.max_workers,
                selected_eval_ids=tuple(args.eval_ids) if args.eval_ids else None,
                max_specs=args.max_specs,
                max_variants_per_spec=args.max_variants_per_spec,
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
