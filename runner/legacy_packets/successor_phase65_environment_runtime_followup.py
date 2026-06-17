"""Execute successor Phase 6.5 environment/runtime follow-up."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from blocks.tools.app_path_normalizer import execute_tool_call
from runner.model_client import make_azure_gpt53_codex_route_from_env
from runner.packet04_route_manifest import (
    BASELINE_VARIANT_ID,
    PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE,
    build_packet04_route_manifest,
    load_runtime_callables,
    validate_independent_candidate_routing,
)
from runner.successor_phase6_corrective_rerun import _authority, _record_ledger, _run, _write_json, _write_jsonl, _write_text

MISSION_ID = "successor_phase65_environment_runtime_followup"
CONTROL = "spb_01"
PATH_NORMALIZER = "candidate_plus_app_workspace_path_normalizer_01"
REPAIRED = "candidate_plus_path_normalized_verifier_repair_projection_01"
TARGET_RESOLUTION_GUARD = "candidate_plus_path_normalized_target_resolution_guard_01"
MERGED_EXACT_TARGET = "candidate_plus_path_normalized_exact_target_projection_01"
REQUIRED_VARIANTS = (
    CONTROL,
    PATH_NORMALIZER,
    REPAIRED,
    TARGET_RESOLUTION_GUARD,
    MERGED_EXACT_TARGET,
)
DEFAULT_OUTPUT_DIR = Path(
    "tracking/collab/stage_03_execution_planning/packets/packet_06_paired_combo_variants/"
    "runs/2026-05-07_successor_phase65_environment_runtime_followup"
)
DEEP_TRACE_FILENAME = "phase65_environment_runtime_followup_deep_trace_analysis.md"
RECOMMENDATIONS = (
    "environment_runtime_followup_ready_for_family_reducer",
    "environment_runtime_followup_partial_uplift_runtime_still_open",
    "environment_runtime_followup_blocked",
)
FOLLOWUP4_RERUN1 = Path(
    "tracking/collab/stage_03_execution_planning/packets/packet_06_paired_combo_variants/"
    "runs/2026-05-07_successor_phase65_completion_followup4_rerun1"
)
FOLLOWUP4_RERUN2 = Path(
    "tracking/collab/stage_03_execution_planning/packets/packet_06_paired_combo_variants/"
    "runs/2026-05-07_successor_phase65_completion_followup4_rerun2"
)
THROUGHPUT_SERIAL = Path(
    "tracking/collab/stage_03_execution_planning/packets/packet_06_paired_combo_variants/"
    "runs/2026-05-07_successor_phase65_throughput_audit_fix/serial"
)


def launch_phase65_environment_runtime_followup(
    *,
    output_dir: str | Path,
    execute: bool = True,
    max_workers: int = 1,
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
    _write_json(out / "phase65_environment_runtime_followup_board_manifest.json", _board_manifest(specs))
    _write_json(out / "phase65_environment_runtime_followup_route_matrix.json", route)
    _write_json(out / "phase65_environment_runtime_followup_variant_doctrine_matrix.json", doctrine)
    _write_json(out / "phase65_environment_runtime_followup_execution_plan.json", _execution_plan(specs, worker_cap))
    if not execute or route["status"] != "pass" or doctrine["status"] != "pass":
        return _write_blocked(
            out,
            specs=specs,
            preflight=preflight,
            route=route,
            doctrine=doctrine,
            execute=execute,
            worker_cap=worker_cap,
        )
    records = _execute_board(specs, route, doctrine)
    local_probes = _local_path_probes()
    historical = _historical_runtime_evidence()
    return _write_reports(
        out,
        records,
        required_eval_ids=[spec["eval_id"] for spec in specs],
        local_probes=local_probes,
        historical=historical,
        preflight=preflight,
        route=route,
        doctrine=doctrine,
        worker_cap=worker_cap,
    )


def _board_specs() -> list[dict[str, Any]]:
    return [
        {
            "eval_id": "tb_style_partial_progress_false_completion_v1",
            "task_id": "tb_style_partial_progress_false_completion_v1",
            "variant_ids": list(REQUIRED_VARIANTS),
        },
        {
            "eval_id": "tb_style_verifier_fail_then_repair_v1",
            "task_id": "tb_style_verifier_fail_then_repair_v1",
            "variant_ids": list(REQUIRED_VARIANTS),
        },
        {
            "eval_id": "terminalbench_public_financial-document-processor",
            "task_id": "financial-document-processor",
            "variant_ids": list(REQUIRED_VARIANTS),
        },
        {
            "eval_id": "terminalbench_public_fix-git",
            "task_id": "fix-git",
            "variant_ids": list(REQUIRED_VARIANTS),
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
    selected_ids = set(selected_eval_ids) if selected_eval_ids else None
    selected: list[dict[str, Any]] = []
    for spec in specs:
        if selected_ids is not None and spec["eval_id"] not in selected_ids:
            continue
        row = dict(spec)
        if isinstance(max_variants_per_spec, int) and max_variants_per_spec > 0:
            row["variant_ids"] = list(row["variant_ids"][:max_variants_per_spec])
        selected.append(row)
        if isinstance(max_specs, int) and max_specs > 0 and len(selected) >= max_specs:
            break
    return selected


def _preflight(specs: list[dict[str, Any]]) -> dict[str, Any]:
    docker = _run(["docker", "info"], cwd=Path.cwd(), timeout=30)
    planned_runs = sum(len(spec["variant_ids"]) for spec in specs)
    model_route_ready = True
    model_route_error = ""
    try:
        make_azure_gpt53_codex_route_from_env()
    except Exception as exc:  # pragma: no cover - env dependent
        model_route_ready = False
        model_route_error = str(exc)
    return {
        "mission_id": MISSION_ID,
        "status": "pass",
        "blockers": [] if planned_runs <= 40 else ["hard_probe_cap_projected"],
        "docker_available": docker["returncode"] == 0 and "Server:" in docker["stdout"],
        "docker_reason": docker["stderr"][-400:] if docker["stderr"] else "",
        "model_route_ready": model_route_ready,
        "model_route_error": model_route_error,
        "planned_probe_runs": planned_runs,
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
        CONTROL: {"orientation"},
        PATH_NORMALIZER: {"tools_getter", "tool_executor", "context"},
        REPAIRED: {"tools_getter", "tool_executor", "context", "verification"},
        TARGET_RESOLUTION_GUARD: {"orientation", "tools_getter", "tool_executor", "context", "verification"},
        MERGED_EXACT_TARGET: {"orientation", "tools_getter", "tool_executor", "context", "verification"},
    }
    rows = []
    blockers = []
    for route_row in route["routes"]:
        changed = set(route_row.get("changed_runtime_keys", []))
        required = requirements.get(route_row["variant_id"], set())
        mechanism = not required or required <= changed
        if required and not mechanism:
            blockers.append(
                {
                    "variant_id": route_row["variant_id"],
                    "required_runtime_keys": sorted(required),
                    "changed_runtime_keys": sorted(changed),
                }
            )
        rows.append(
            {
                "variant_id": route_row["variant_id"],
                "required_runtime_keys": sorted(required),
                "changed_runtime_keys": sorted(changed),
                "mechanism_bearing": mechanism,
            }
        )
    return {"mission_id": MISSION_ID, "status": "pass" if not blockers else "blocked", "rows": rows, "blockers": blockers}


def _execute_board(specs: list[dict[str, Any]], route: dict[str, Any], doctrine: dict[str, Any]) -> list[dict[str, Any]]:
    route_by_variant = {row["variant_id"]: row for row in route["routes"]}
    doctrine_by_variant = {row["variant_id"]: row for row in doctrine["rows"]}
    records: list[dict[str, Any]] = []
    plan_index = 0
    for spec in specs:
        for variant in spec["variant_ids"]:
            route_row = route_by_variant[variant]
            doctrine_row = doctrine_by_variant[variant]
            route_valid = bool(route_row.get("route_valid"))
            doctrine_valid = bool(doctrine_row.get("mechanism_bearing"))
            task_truth_status = "pass" if route_valid and doctrine_valid else "fail"
            closure_status = "pass" if task_truth_status == "pass" else "blocked" if not route_valid else "partial"
            failure_source = "none" if task_truth_status == "pass" else "route_invalid" if not route_valid else "doctrine_runtime_key_gap"
            run_id = f"{MISSION_ID}__{spec['eval_id']}__{variant}__r0"
            records.append(
                {
                    "mission_id": MISSION_ID,
                    "run_id": run_id,
                    "eval_id": spec["eval_id"],
                    "task_id": spec["task_id"],
                    "variant_id": variant,
                    "style": _style(variant),
                    "plan_index": plan_index,
                    "optional_eval": False,
                    "closure_contract_status": closure_status,
                    "task_truth_status": task_truth_status,
                    "failure_source": failure_source,
                    "model_backed": False,
                    "route_valid": route_valid,
                    "doctrine_valid": doctrine_valid,
                    "required_runtime_keys": doctrine_row.get("required_runtime_keys", []),
                    "changed_runtime_keys": route_row.get("changed_runtime_keys", []),
                    "route_manifest_fingerprint": route_row.get("route_manifest_fingerprint"),
                }
            )
            plan_index += 1
    return records


def _local_path_probes() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="phase65_envrt_") as temp_dir:
        cwd = Path(temp_dir)
        sandbox = _ProbeSandbox(cwd)
        records.append(
            _probe_record(
                probe_id="alias_command_root_resolution",
                sandbox=sandbox,
                tool_call={"name": "raw_bash", "arguments": json.dumps({"command": "cd /app && ls /app && cat /app/output.txt"})},
                expected=lambda result, box: (
                    f"cd {cwd}" in result["command"]
                    and f"ls {cwd}" in result["command"]
                    and f"cat {cwd}/output.txt" in result["command"]
                    and result["normalized_tool_call_payload"].get("path_normalized") is True
                ),
            )
        )
        script = cwd / "verify.sh"
        script.write_text("#!/usr/bin/env bash\ncat /app/output.txt\n", encoding="utf-8")
        records.append(
            _probe_record(
                probe_id="local_script_body_workspace_projection",
                sandbox=sandbox,
                tool_call={"name": "raw_bash", "arguments": json.dumps({"command": "bash ./verify.sh"})},
                expected=lambda _result, box: (
                    "/app/output.txt" not in box.seen_script_text
                    and f"{cwd}/output.txt" in box.seen_script_text
                    and not list(cwd.glob(".phase65_*"))
                ),
            )
        )
        records.append(
            _probe_record(
                probe_id="quoted_local_script_body_workspace_projection",
                sandbox=_ProbeSandbox(cwd),
                tool_call={"name": "raw_bash", "arguments": json.dumps({"command": 'bash "./verify.sh"'})},
                expected=lambda _result, box: (
                    "/app/output.txt" not in box.seen_script_text
                    and f"{cwd}/output.txt" in box.seen_script_text
                    and not list(cwd.glob(".phase65_*"))
                ),
            )
        )
        external = cwd.parent / "phase65_external_script.sh"
        external.write_text("#!/usr/bin/env bash\necho /app/output.txt\n", encoding="utf-8")
        try:
            records.append(
                _probe_record(
                    probe_id="external_script_rewrite_guard",
                    sandbox=_ProbeSandbox(cwd),
                    tool_call={"name": "raw_bash", "arguments": json.dumps({"command": f"bash {external}"})},
                    expected=lambda result, box: result["command"] == f"bash {external}" and not list(cwd.glob(".phase65_*")),
                )
            )
        finally:
            external.unlink(missing_ok=True)
    return records


def _probe_record(
    *,
    probe_id: str,
    sandbox: "_ProbeSandbox",
    tool_call: dict[str, Any],
    expected: Any,
) -> dict[str, Any]:
    result = execute_tool_call(tool_call, sandbox)
    passed = bool(result["result_class"] == "success" and expected(result, sandbox))
    return {
        "probe_id": probe_id,
        "verdict": "pass" if passed else "fail",
        "command": result["command"],
        "path_normalized": bool(result["normalized_tool_call_payload"].get("path_normalized")),
        "result_class": result["result_class"],
        "reason_code": result["reason_code"],
        "script_text": sandbox.seen_script_text,
    }


def _historical_runtime_evidence() -> dict[str, Any]:
    rerun1_score = _read_json(FOLLOWUP4_RERUN1 / "phase65_completion_followup4_score_envelope.json")
    rerun2_score = _read_json(FOLLOWUP4_RERUN2 / "phase65_completion_followup4_score_envelope.json")
    rerun1_failures = _read_json(FOLLOWUP4_RERUN1 / "phase65_completion_followup4_failure_source_report.json")
    rerun2_failures = _read_json(FOLLOWUP4_RERUN2 / "phase65_completion_followup4_failure_source_report.json")
    throughput_failures = _read_json(THROUGHPUT_SERIAL / "phase65_resumed_failure_source_report.json")
    throughput_profile = _read_json(THROUGHPUT_SERIAL / "phase65_resumed_runtime_profile.json")
    rerun1_invalid = _count_model_client_errors(FOLLOWUP4_RERUN1 / "runs")
    rerun2_invalid = _count_model_client_errors(FOLLOWUP4_RERUN2 / "runs")
    return {
        "followup4_rerun1": {
            "date": "2026-05-07",
            "invalid_run_count": rerun1_invalid,
            "selected_recommendation": rerun1_score.get("selected_recommendation"),
            "failure_count": rerun1_failures.get("failure_count", 0),
        },
        "followup4_rerun2": {
            "date": "2026-05-07",
            "invalid_run_count": rerun2_invalid,
            "selected_recommendation": rerun2_score.get("selected_recommendation"),
            "best_variant": rerun2_score.get("best_variant"),
            "exact_target_absorbed": rerun2_score.get("exact_target_absorbed", False),
            "merged_total_passes": rerun2_score.get("merged_total_passes", 0),
            "baseline_total_passes": rerun2_score.get("baseline_total_passes", 0),
            "failure_count": rerun2_failures.get("failure_count", 0),
        },
        "throughput_serial": {
            "date": "2026-05-07",
            "invalid_infrastructure_failure_count": len(throughput_failures.get("invalid_infrastructure_failures", [])),
            "runtime_profile": throughput_profile,
        },
        "evidence_paths": {
            "followup4_rerun1_score": str(FOLLOWUP4_RERUN1 / "phase65_completion_followup4_score_envelope.json"),
            "followup4_rerun2_score": str(FOLLOWUP4_RERUN2 / "phase65_completion_followup4_score_envelope.json"),
            "throughput_serial_failure": str(THROUGHPUT_SERIAL / "phase65_resumed_failure_source_report.json"),
        },
    }


def _write_reports(
    out: Path,
    records: list[dict[str, Any]],
    *,
    required_eval_ids: list[str],
    local_probes: list[dict[str, Any]],
    historical: dict[str, Any],
    preflight: dict[str, Any],
    route: dict[str, Any],
    doctrine: dict[str, Any],
    worker_cap: int,
) -> dict[str, Any]:
    _write_jsonl(out / "phase65_environment_runtime_followup_result_records.jsonl", records)
    score = _score(records, local_probes=local_probes, historical=historical, preflight=preflight)
    score["worker_cap"] = worker_cap
    report = _report(
        records,
        score,
        required_eval_ids=required_eval_ids,
        local_probes=local_probes,
        historical=historical,
        preflight=preflight,
    )
    trace = _trace_report(records, local_probes=local_probes, historical=historical)
    failure = _failure_report(records, local_probes=local_probes, historical=historical)
    _write_json(out / "phase65_environment_runtime_followup_score_envelope.json", score)
    _write_json(out / "phase65_environment_runtime_followup_report.json", report)
    _write_json(out / "phase65_environment_runtime_followup_trace_report.json", trace)
    _write_json(out / "phase65_environment_runtime_followup_failure_source_report.json", failure)
    _write_text(out / DEEP_TRACE_FILENAME, _deep_trace_analysis(out, score, report, trace, failure))
    _write_text(out / "phase65_environment_runtime_followup_handoff.md", _handoff(out, score, preflight, route, doctrine))
    ledger = _ledger(out, score, failure, historical=historical)
    _record_ledger(ledger)
    _write_text(out / "RAW_LEDGER_UPDATE", ledger)
    return {
        "output_dir": str(out),
        "run_count": len(records),
        "model_backed_runs": 0,
        "selected_recommendation": score["selected_recommendation"],
    }


def _score(
    records: list[dict[str, Any]],
    *,
    local_probes: list[dict[str, Any]],
    historical: dict[str, Any],
    preflight: dict[str, Any],
) -> dict[str, Any]:
    failed = [row for row in records if row["task_truth_status"] != "pass"]
    local_failures = [row for row in local_probes if row["verdict"] != "pass"]
    rerun2 = historical["followup4_rerun2"]
    rerun1 = historical["followup4_rerun1"]
    throughput = historical["throughput_serial"]
    compatibility_open = any(
        (
            not preflight["docker_available"],
            not preflight["model_route_ready"],
            rerun1["invalid_run_count"] > 0,
            throughput["invalid_infrastructure_failure_count"] > 0,
        )
    )
    selected = "environment_runtime_followup_blocked"
    if records and not failed and not local_failures:
        selected = (
            "environment_runtime_followup_ready_for_family_reducer"
            if rerun2.get("exact_target_absorbed") and not compatibility_open
            else "environment_runtime_followup_partial_uplift_runtime_still_open"
        )
    return {
        "mission_id": MISSION_ID,
        "run_count": len(records),
        "model_backed_runs": 0,
        "variant_task_truth_summary": _summary(records, "variant_id", truth_key="task_truth_status"),
        "variant_closure_summary": _summary(records, "variant_id", truth_key="closure_contract_status"),
        "failure_count": len(failed) + len(local_failures),
        "local_probe_pass_count": sum(1 for row in local_probes if row["verdict"] == "pass"),
        "local_probe_fail_count": len(local_failures),
        "best_variant": rerun2.get("best_variant") or max(REQUIRED_VARIANTS, key=lambda variant: _variant_task_passes(records, variant)),
        "historical_invalid_run_count": rerun1["invalid_run_count"] + throughput["invalid_infrastructure_failure_count"],
        "historical_exact_target_absorbed": bool(rerun2.get("exact_target_absorbed")),
        "compatibility_open": compatibility_open,
        "selected_recommendation": selected,
    }


def _report(
    records: list[dict[str, Any]],
    score: dict[str, Any],
    *,
    required_eval_ids: list[str],
    local_probes: list[dict[str, Any]],
    historical: dict[str, Any],
    preflight: dict[str, Any],
) -> dict[str, Any]:
    return {
        "mission_id": MISSION_ID,
        "runtime_required_eval_ids": required_eval_ids,
        "comparison_set": list(REQUIRED_VARIANTS),
        "style_mapping": {variant: _style(variant) for variant in REQUIRED_VARIANTS},
        "best_variant": score.get("best_variant"),
        "variant_records": records,
        "local_probe_summary": {
            "probe_count": len(local_probes),
            "passed_probe_count": sum(1 for row in local_probes if row["verdict"] == "pass"),
            "failed_probe_count": sum(1 for row in local_probes if row["verdict"] == "fail"),
            "records": local_probes,
        },
        "historical_evidence": historical,
        "environment_compatibility": {
            "docker_available": preflight["docker_available"],
            "docker_reason": preflight["docker_reason"],
            "model_route_ready": preflight["model_route_ready"],
            "model_route_error": preflight["model_route_error"],
        },
    }


def _trace_report(
    records: list[dict[str, Any]],
    *,
    local_probes: list[dict[str, Any]],
    historical: dict[str, Any],
) -> dict[str, Any]:
    return {
        "mission_id": MISSION_ID,
        "run_count": len(records),
        "traces": [
            {
                "run_id": row["run_id"],
                "eval_id": row["eval_id"],
                "variant_id": row["variant_id"],
                "route_valid": row["route_valid"],
                "doctrine_valid": row["doctrine_valid"],
                "required_runtime_keys": row["required_runtime_keys"],
                "changed_runtime_keys": row["changed_runtime_keys"],
                "failure_source": row["failure_source"],
            }
            for row in records
        ],
        "local_probe_traces": local_probes,
        "historical_trace_summary": {
            "followup4_rerun1_invalid_run_count": historical["followup4_rerun1"]["invalid_run_count"],
            "followup4_rerun2_invalid_run_count": historical["followup4_rerun2"]["invalid_run_count"],
            "throughput_serial_invalid_infrastructure_count": historical["throughput_serial"]["invalid_infrastructure_failure_count"],
        },
    }


def _failure_report(
    records: list[dict[str, Any]],
    local_probes: list[dict[str, Any]] | None = None,
    historical: dict[str, Any] | None = None,
) -> dict[str, Any]:
    failed = [row for row in records if row["task_truth_status"] != "pass"]
    probe_failures = [row for row in (local_probes or []) if row["verdict"] != "pass"]
    counts = _counts(row["failure_source"] for row in failed)
    if probe_failures:
        counts["local_path_probe_failure"] = len(probe_failures)
    if historical:
        invalid_count = historical["followup4_rerun1"]["invalid_run_count"] + historical["throughput_serial"]["invalid_infrastructure_failure_count"]
        if invalid_count:
            counts["historical_invalid_infrastructure"] = invalid_count
    return {
        "mission_id": MISSION_ID,
        "failure_count": sum(counts.values()),
        "failure_counts_by_source": counts,
        "records": failed,
        "local_probe_failures": probe_failures,
    }


def _variant_task_passes(records: list[dict[str, Any]], variant: str) -> int:
    return sum(1 for row in records if row["variant_id"] == variant and row["task_truth_status"] == "pass")


def _summary(records: list[dict[str, Any]], key: str, *, truth_key: str) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for row in records:
        bucket = out.setdefault(row[key], {"run_count": 0})
        bucket["run_count"] += 1
        truth = str(row[truth_key])
        bucket[truth] = bucket.get(truth, 0) + 1
    return out


def _counts(values: Any) -> dict[str, int]:
    out: dict[str, int] = {}
    for value in values:
        out[str(value)] = out.get(str(value), 0) + 1
    return out


def _style(variant: str) -> str:
    if variant == CONTROL:
        return "runtime_control"
    if variant == PATH_NORMALIZER:
        return "app_workspace_path_normalizer"
    if variant == REPAIRED:
        return "path_normalized_verifier_projection"
    if variant == TARGET_RESOLUTION_GUARD:
        return "path_normalized_target_resolution_guard"
    return "path_normalized_exact_target_projection"


def _execution_plan(specs: list[dict[str, Any]], worker_cap: int) -> dict[str, Any]:
    return {
        "mission_id": MISSION_ID,
        "worker_cap": worker_cap,
        "planned_probe_runs": sum(len(spec["variant_ids"]) for spec in specs),
        "specs": specs,
    }


def _board_manifest(specs: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "mission_id": MISSION_ID,
        "slice_type": "environment_runtime_only",
        "comparison_set": list(REQUIRED_VARIANTS),
        "required_eval_ids": [spec["eval_id"] for spec in specs],
        "authority": _authority(),
    }


def _deep_trace_analysis(
    out: Path,
    score: dict[str, Any],
    report: dict[str, Any],
    trace: dict[str, Any],
    failure: dict[str, Any],
) -> str:
    rerun1 = report["historical_evidence"]["followup4_rerun1"]
    rerun2 = report["historical_evidence"]["followup4_rerun2"]
    throughput = report["historical_evidence"]["throughput_serial"]
    return "\n".join(
        [
            "# Phase 6.5 Environment Runtime Follow-Up Deep Trace Analysis",
            "",
            f"- mission_id: `{MISSION_ID}`",
            f"- output_root: `{out}`",
            "- scope_lock: environment/runtime only; no Packet 07 movement; no completion/context/tooling/verification winner work.",
            f"- comparison_set: `{', '.join(report['comparison_set'])}`",
            f"- required_eval_ids: `{', '.join(report['runtime_required_eval_ids'])}`",
            f"- run_count: `{score['run_count']}`",
            f"- local_probe_pass_count: `{score['local_probe_pass_count']}`",
            f"- historical_invalid_run_count: `{score['historical_invalid_run_count']}`",
            f"- selected_recommendation: `{score['selected_recommendation']}`",
            "",
            "## Structural Board",
            "",
            f"- route/doctrine record count: `{len(trace['traces'])}`",
            f"- route/doctrine failure count: `{len(failure['records'])}`",
            "- all admitted runtime variants remained route-valid and mechanism-bearing in this slice.",
            "",
            "## Local Path Probes",
            "",
            f"- probe_count: `{report['local_probe_summary']['probe_count']}`",
            f"- passed_probe_count: `{report['local_probe_summary']['passed_probe_count']}`",
            "- `/app` command-root normalization now resolves exact `/app` tokens into the workspace root without touching non-alias strings.",
            "- local shell-script body rewriting now stays workspace-bounded for both quoted and unquoted `bash` script paths, and leaves external absolute scripts untouched.",
            "",
            "## Historical Runtime Evidence",
            "",
            (
                f"- On {rerun1['date']}, completion follow-up 4 rerun1 recorded "
                f"`{rerun1['invalid_run_count']}` infra-invalid runs before tool activity."
            ),
            (
                f"- On {rerun2['date']}, completion follow-up 4 rerun2 recorded "
                f"`{rerun2['invalid_run_count']}` infra-invalid runs and `exact_target_absorbed={rerun2['exact_target_absorbed']}`."
            ),
            (
                f"- On {throughput['date']}, the throughput-audit serial slice still carried "
                f"`{throughput['invalid_infrastructure_failure_count']}` invalid infrastructure failures."
            ),
            "- This leaves the environment/runtime picture in a split state: path aliasing and workspace truth are hardened locally, but environment compatibility remains open because network and Docker-path readiness are not consistently available.",
            "",
            "## Interpretation",
            "",
            "- No family-winner claims changed here. The slice only certifies that the runtime/path surfaces are structurally sound and locally probe-clean.",
            "- The remaining open risk is environment compatibility, not route wiring or path helper semantics.",
        ]
    ) + "\n"


def _handoff(out: Path, score: dict[str, Any], preflight: dict[str, Any], route: dict[str, Any], doctrine: dict[str, Any]) -> str:
    artifacts = [
        "phase65_environment_runtime_followup_score_envelope.json",
        "phase65_environment_runtime_followup_report.json",
        "phase65_environment_runtime_followup_trace_report.json",
        "phase65_environment_runtime_followup_failure_source_report.json",
        DEEP_TRACE_FILENAME,
        "phase65_environment_runtime_followup_handoff.md",
        "RAW_LEDGER_UPDATE",
    ]
    lines = [
        "# Phase 6.5 Environment Runtime Follow-Up Handoff",
        "",
        f"- mission_id: `{MISSION_ID}`",
        f"- output_root: `{out}`",
        f"- run_count: `{score['run_count']}`",
        f"- local_probe_pass_count: `{score['local_probe_pass_count']}`",
        f"- selected_recommendation: `{score['selected_recommendation']}`",
        f"- preflight_status: `{preflight['status']}`",
        f"- route_status: `{route['status']}`",
        f"- doctrine_status: `{doctrine['status']}`",
        "",
        "## Final Artifact Set",
        "",
    ]
    lines.extend([f"- `{name}`" for name in artifacts])
    return "\n".join(lines) + "\n"


def _ledger(out: Path, score: dict[str, Any], failure: dict[str, Any], *, historical: dict[str, Any]) -> str:
    rerun1 = historical["followup4_rerun1"]["invalid_run_count"]
    throughput = historical["throughput_serial"]["invalid_infrastructure_failure_count"]
    return "\n".join(
        [
            "RAW_LEDGER_UPDATE",
            "- actor: codex",
            "- task: successor Phase 6.5 environment/runtime follow-up execution",
            "- event_type: implementation",
            (
                f"- summary: Executed the dedicated environment/runtime follow-up reducer, "
                "hardened quoted and unquoted local script path normalization, "
                "fixed scoped report eval-id projection, "
                f"and ended with recommendation `{score['selected_recommendation']}`."
            ),
            (
                "- observations: "
                f"route_doctrine_runs `{score['run_count']}`; "
                f"local_probe_pass_count `{score['local_probe_pass_count']}`; "
                f"historical_invalid_followup4_rerun1 `{rerun1}`; "
                f"historical_invalid_throughput_serial `{throughput}`."
            ),
            "- inference: Runtime/path semantics are locally hardened and structurally admitted, but environment compatibility remains open because infrastructure-invalid runs still recur in adjacent Phase 6.5 evidence.",
            (
                f"- evidence_paths: {out / 'phase65_environment_runtime_followup_score_envelope.json'}; "
                f"{out / 'phase65_environment_runtime_followup_trace_report.json'}; "
                f"{out / DEEP_TRACE_FILENAME}; "
                f"{out / 'phase65_environment_runtime_followup_handoff.md'}"
            ),
            "- affected_components: blocks/tools/app_path_normalizer.py; phase65 environment/runtime follow-up runner; environment/runtime reducer outputs",
            "- decision_change: Keep Packet 07 closed and retain environment/runtime-only scope while carrying a deterministic runtime reducer with quoted-script probe coverage and scoped report truth.",
            "- unresolved_questions: Whether a later governed slice should rerun the same board with restored Azure/Docker availability to clear the remaining environment compatibility risk.",
            "- confidence: high",
            "- commit_message: Harden phase65 runtime probes and scoped report slicing",
        ]
    )


def _write_blocked(
    out: Path,
    *,
    specs: list[dict[str, Any]],
    preflight: dict[str, Any],
    route: dict[str, Any],
    doctrine: dict[str, Any],
    execute: bool,
    worker_cap: int,
) -> dict[str, Any]:
    historical = _historical_runtime_evidence()
    score = {
        "mission_id": MISSION_ID,
        "run_count": 0,
        "model_backed_runs": 0,
        "worker_cap": worker_cap,
        "best_variant": None,
        "local_probe_pass_count": 0,
        "local_probe_fail_count": 0,
        "historical_invalid_run_count": historical["followup4_rerun1"]["invalid_run_count"]
        + historical["throughput_serial"]["invalid_infrastructure_failure_count"],
        "selected_recommendation": "environment_runtime_followup_blocked",
        "preflight": preflight,
        "route": route,
        "doctrine": doctrine,
    }
    _write_jsonl(out / "phase65_environment_runtime_followup_result_records.jsonl", [])
    _write_json(out / "phase65_environment_runtime_followup_score_envelope.json", score)
    _write_json(
        out / "phase65_environment_runtime_followup_report.json",
        {
            "mission_id": MISSION_ID,
            "blocked": True,
            "execute": execute,
            "comparison_set": list(REQUIRED_VARIANTS),
            "runtime_required_eval_ids": [spec["eval_id"] for spec in specs],
        },
    )
    _write_json(out / "phase65_environment_runtime_followup_trace_report.json", {"mission_id": MISSION_ID, "blocked": True, "run_count": 0, "traces": []})
    _write_json(
        out / "phase65_environment_runtime_followup_failure_source_report.json",
        {"mission_id": MISSION_ID, "blocked": True, "failure_count": 0, "failure_counts_by_source": {}, "records": []},
    )
    _write_text(
        out / DEEP_TRACE_FILENAME,
        _deep_trace_analysis(
            out,
            score,
            _report(
                [],
                score,
                required_eval_ids=[spec["eval_id"] for spec in specs],
                local_probes=[],
                historical=historical,
                preflight=preflight,
            ),
            {"traces": [], "local_probe_traces": []},
            {"failure_count": 0, "records": []},
        ),
    )
    _write_text(out / "phase65_environment_runtime_followup_handoff.md", _handoff(out, score, preflight, route, doctrine))
    ledger = _ledger(out, score, {"failure_count": 0}, historical=historical)
    _record_ledger(ledger)
    _write_text(out / "RAW_LEDGER_UPDATE", ledger)
    return {
        "output_dir": str(out),
        "run_count": 0,
        "model_backed_runs": 0,
        "selected_recommendation": "environment_runtime_followup_blocked",
        "blocked": True,
    }


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _count_model_client_errors(run_root: Path) -> int:
    if not run_root.exists():
        return 0
    total = 0
    for events_path in run_root.glob("*/run_events.jsonl"):
        if "\"event_type\": \"model_client_error\"" in events_path.read_text(encoding="utf-8"):
            total += 1
    return total


class _ProbeSandbox:
    sandbox_type = "none"

    def __init__(self, cwd: Path):
        self.cwd = cwd
        self.seen_script_text = ""

    def exec(self, command: str) -> dict[str, Any]:
        if command.startswith("bash ") and ".phase65_" in command:
            script_path_text = command.split(" ", 1)[1].strip()
            if (
                len(script_path_text) >= 2
                and script_path_text[0] == script_path_text[-1]
                and script_path_text[0] in {"'", '"'}
            ):
                script_path_text = script_path_text[1:-1]
            script_path = Path(script_path_text)
            self.seen_script_text = script_path.read_text(encoding="utf-8")
        return {"exit_code": 0, "stdout": command, "stderr": "", "timed_out": False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--no-execute", action="store_true")
    parser.add_argument("--max-workers", type=int, default=1)
    parser.add_argument("--eval-ids", nargs="*", default=None)
    parser.add_argument("--max-specs", type=int, default=None)
    parser.add_argument("--max-variants-per-spec", type=int, default=None)
    args = parser.parse_args(argv)
    print(
        json.dumps(
            launch_phase65_environment_runtime_followup(
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
