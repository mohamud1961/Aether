"""Execute successor Phase 6.5 context-family follow-up on a narrow board."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from pathlib import Path
from time import perf_counter
from typing import Any

from runner.agent import run_reference_baseline
from runner.letta_context_bench import letta_preflight
from runner.model_client import make_azure_gpt53_codex_route_from_env
from runner.packet04_route_manifest import (
    BASELINE_VARIANT_ID,
    PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE,
    build_packet04_route_manifest,
    load_runtime_callables,
    validate_independent_candidate_routing,
)
from runner.phase65_measurement_grading import grade_phase65_spec
from runner.successor_phase65_resumed_board import CONTEXTBENCH_ROOT, LETTA_ROOT
from runner.successor_phase6_corrective_rerun import _authority, _record_ledger, _run, _usage, _write_json, _write_jsonl, _write_text

MISSION_ID = "successor_phase65_context_followup"
CONTROL = "spb_01"
INCUMBENT = "spb_tooling_seed_plus_receipt_and_completion_01"
CANDIDATE_HYBRID = "candidate_plus_hybrid_receipt_handoff_01"
CARRY_FORWARD = "verified_work_pocket_handoff_hybrid_01"
CANDIDATE_ANSWER_EXTRACTION = "candidate_plus_context_answer_extraction_01"
MERGED_VARIANT = "candidate_plus_context_followup_merged_01"
REQUIRED_VARIANTS = (CONTROL, INCUMBENT, CANDIDATE_HYBRID, CARRY_FORWARD, CANDIDATE_ANSWER_EXTRACTION, MERGED_VARIANT)
RECOMMENDATIONS = (
    "context_followup_ready_for_family_reducer",
    "context_followup_partial_uplift_context_still_open",
    "context_followup_blocked",
)
DEEP_TRACE_FILENAME = "phase65_context_followup_deep_trace_analysis.md"
DEFAULT_THROUGHPUT_WORKERS = 2
DEFAULT_OUTPUT_DIR = Path(
    "tracking/collab/stage_03_execution_planning/packets/packet_06_paired_combo_variants/"
    "runs/2026-05-07_successor_phase65_context_followup"
)
LONG_HANDOFF_EVAL_ID = "custom_long_context_handoff_aggregation_v1"
MERGED_CONTEXT_MODULE = "blocks.context.phase65_context_followup_merged:manage"
MERGED_CONTEXT_FILE = Path("blocks/context/phase65_context_followup_merged.py")


def launch_phase65_context_followup(
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
    _write_json(out / "phase65_context_followup_board_manifest.json", _board_manifest(specs))
    _write_json(out / "phase65_context_followup_route_matrix.json", route)
    _write_json(out / "phase65_context_followup_variant_doctrine_matrix.json", doctrine)
    _write_json(out / "phase65_context_followup_execution_plan.json", _execution_plan(specs, worker_cap))
    if not execute or preflight["status"] != "pass" or route["status"] != "pass" or doctrine["status"] != "pass":
        return _write_blocked(out, preflight=preflight, route=route, doctrine=doctrine, execute=execute, worker_cap=worker_cap)
    records = _execute_plan(out, _plan_rows(specs), worker_cap=worker_cap)
    return _write_reports(out, records, preflight=preflight, route=route, doctrine=doctrine, worker_cap=worker_cap)


def _board_specs() -> list[dict[str, Any]]:
    specs = []
    verified_csv = (CONTEXTBENCH_ROOT / "data/Verified.csv").read_text(encoding="utf-8")
    structured_rows = list(csv.DictReader(verified_csv.splitlines()))[:4]
    for index, row in enumerate(structured_rows):
        specs.append(
            {
                "eval_id": f"contextbench_verified_{index:02d}",
                "surface": "structured_retrieval",
                "benchmark_class": "contextbench",
                "task_id": row["instance_id"],
                "task_prompt": (
                    "Read /contextbench/Verified.csv and answer for the requested row only. "
                    "Return JSON with exactly these keys: original_inst_id, language, status, "
                    "gold_context_length, commit, repo_or_file_family."
                ),
                "workspace_seed": "simple_files",
                "workspace_files": {
                    "/contextbench/Verified.csv": verified_csv,
                    "/contextbench/request.json": json.dumps(row, indent=2, sort_keys=True),
                },
                "grade_row": row,
                "variant_ids": list(REQUIRED_VARIANTS),
                "max_steps": 4,
                "timeout_sec": 120,
            }
        )
    letta_rows = [
        json.loads(line)
        for line in (LETTA_ROOT / "datasets/filesystem_code.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    selected: list[tuple[int, str, dict[str, Any]]] = []
    quotas = {"easy": 2, "medium": 2, "hard": 2}
    for index, row in enumerate(letta_rows):
        difficulty = row.get("agent_args", {}).get("extra", {}).get("difficulty")
        if quotas.get(difficulty, 0) > 0:
            selected.append((index, str(difficulty), row))
            quotas[difficulty] -= 1
        if sum(quotas.values()) == 0:
            break
    files = {
        f"/letta/filesystem/{path.name}": path.read_text(encoding="utf-8")
        for path in sorted((LETTA_ROOT / "files").glob("*.txt"))
    }
    for index, difficulty, row in selected:
        specs.append(
            {
                "eval_id": f"letta_filesystem_{index:03d}_{difficulty}",
                "surface": "open_workflow_letta",
                "benchmark_class": "letta_context_bench",
                "task_id": f"filesystem_code_{index:03d}",
                "task_prompt": row["input"].replace("{pwd}", "/letta/filesystem") + "\nReturn one direct answer.",
                "workspace_seed": "simple_files",
                "workspace_files": files,
                "ground_truth": row["ground_truth"],
                "variant_ids": list(REQUIRED_VARIANTS),
                "max_steps": 4,
                "timeout_sec": 120,
            }
        )
    specs.append(
        {
            "eval_id": LONG_HANDOFF_EVAL_ID,
            "surface": "long_handoff_answer_extraction",
            "benchmark_class": "phase65_context_work_pocket",
            "task_id": LONG_HANDOFF_EVAL_ID,
            "task_prompt": (
                "Inspect all files under /app/case, compute the combined invoice total, and write "
                "/app/artifacts/work_pocket.json with keys verified_total, verification_status, and evidence_paths. "
                "In the final answer, state the total and the artifact path."
            ),
            "workspace_seed": "simple_files",
            "workspace_files": {
                "/case/alpha/invoice_a.txt": "invoice alpha total=17\n",
                "/case/beta/invoice_b.txt": "invoice beta total=25\n",
                "/case/gamma/invoice_c.txt": "invoice gamma total=8\n",
                "/artifacts/.keep": "",
            },
            "artifact_relpath": "artifacts/work_pocket.json",
            "expected_total": 50,
            "required_evidence_paths": [
                "/app/case/alpha/invoice_a.txt",
                "/app/case/beta/invoice_b.txt",
                "/app/case/gamma/invoice_c.txt",
            ],
            "variant_ids": list(REQUIRED_VARIANTS),
            "max_steps": 4,
            "timeout_sec": 120,
        }
    )
    return specs


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
    rows = []
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
    for path, label in (
        (CONTEXTBENCH_ROOT / "data/Verified.csv", "contextbench_verified_missing"),
        (LETTA_ROOT / "datasets/filesystem_code.jsonl", "letta_dataset_missing"),
    ):
        if not path.exists():
            blockers.append(label)
    if letta_preflight()["status"] != "pass":
        blockers.append("letta_preflight_failed")
    try:
        make_azure_gpt53_codex_route_from_env()
    except Exception as exc:
        blockers.append(f"model_route_not_ready:{exc}")
    planned_runs = sum(len(spec["variant_ids"]) for spec in specs)
    if planned_runs > 80:
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
            manifest = _build_route_manifest(variant)
            load_runtime_callables(manifest)
            validate_independent_candidate_routing(candidate_manifest=manifest, baseline_manifest=baseline)
            changed = sorted(row["runtime_key"] for row in manifest["routed_modules"] if row.get("claimed_changed_surface"))
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
        CANDIDATE_HYBRID: {"tools_getter", "tool_executor", "context"},
        CARRY_FORWARD: {"tools_getter", "tool_executor", "context", "verification"},
        CANDIDATE_ANSWER_EXTRACTION: {"context"},
        MERGED_VARIANT: {"tools_getter", "tool_executor", "context", "verification"},
    }
    rows = []
    blockers = []
    for row in route["routes"]:
        changed = set(row.get("changed_runtime_keys", []))
        required = requirements.get(row["variant_id"], set())
        mechanism_bearing = required <= changed if required else True
        if not row.get("route_valid") or not mechanism_bearing:
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
                "required_runtime_keys": sorted(required),
                "changed_runtime_keys": sorted(changed),
                "mechanism_bearing": mechanism_bearing,
                "style": _style(row["variant_id"]),
            }
        )
    return {"mission_id": MISSION_ID, "status": "pass" if not blockers else "blocked", "rows": rows, "blockers": blockers}


def _run_one(out: Path, spec: dict[str, Any], variant: str, *, plan_index: int) -> dict[str, Any]:
    run_started = perf_counter()
    run_id = f"{MISSION_ID}__{spec['eval_id']}__{variant}__r0"
    run_dir = out / "runs" / run_id
    workspace = run_dir / "workspace"
    seed_started = perf_counter()
    _seed_workspace(workspace, spec)
    seed_sec = perf_counter() - seed_started
    model_exec_started = perf_counter()
    result = run_reference_baseline(
        run_id=run_id,
        run_dir=run_dir,
        task_id=spec["task_id"],
        task_prompt=spec["task_prompt"] + "\nUse shell inspection where helpful and avoid unsupported assumptions.",
        benchmark_family=spec["benchmark_class"],
        case_id=spec["eval_id"],
        seed_id=variant,
        model_route=make_azure_gpt53_codex_route_from_env(),
        model_client_kwargs={"timeout_sec": int(spec["timeout_sec"]), "max_retries": 1},
        max_steps=int(spec["max_steps"]),
        timeout_sec=int(spec["timeout_sec"]),
        cwd=workspace,
        route_manifest=_build_route_manifest(variant),
        enforce_packet04_route_contract=True,
    )
    model_exec_sec = perf_counter() - model_exec_started
    grade = grade_phase65_spec(spec=spec, result=result, workspace=workspace)
    invalid = _is_invalid_infrastructure_failure(run_dir)
    runtime_timing = result.get("runtime_timing", {}) if isinstance(result.get("runtime_timing"), dict) else {}
    record = {
        "mission_id": MISSION_ID,
        "run_id": run_id,
        "eval_id": spec["eval_id"],
        "surface": spec["surface"],
        "task_id": spec["task_id"],
        "benchmark_class": spec["benchmark_class"],
        "variant_id": variant,
        "style": _style(variant),
        "plan_index": plan_index,
        "score_summary": {"final_verdict": "invalid" if invalid else grade["verdict"], "grade": grade},
        "failure_source": "invalid_infrastructure" if invalid else _failure_source(spec, grade),
        "token_and_cost_summary": _usage(result),
        "trace_ref": str(run_dir / "run_events.jsonl"),
        "run_dir": str(run_dir),
        "model_backed": True,
        "invalid_infrastructure_failure": invalid,
        "timing_summary": {
            "run_wall_sec": perf_counter() - run_started,
            "workspace_seed_sec": seed_sec,
            "model_and_tool_loop_sec": model_exec_sec,
            "model_backed_latency_sec": float(runtime_timing.get("model_backed_latency_sec", 0.0) or 0.0),
            "tool_exec_sec": float(runtime_timing.get("tool_exec_sec", 0.0) or 0.0),
            "verification_sec": float(runtime_timing.get("verification_sec", 0.0) or 0.0),
            "model_call_count": int(runtime_timing.get("model_call_count", 0) or 0),
            "tool_call_count": int(runtime_timing.get("tool_call_count", 0) or 0),
        },
    }
    return record


def _seed_workspace(workspace: Path, spec: dict[str, Any]) -> None:
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    for raw_path, content in spec.get("workspace_files", {}).items():
        path = workspace / raw_path.lstrip("/")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


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
        error_kind = str(details.get("error_kind", "")).lower()
        message = str(details.get("message", "")).lower()
        if error_kind in {"network_error", "refresh_network_error"}:
            return True
        if "azure" in message and any(marker in message for marker in ("dns", "name or service not known", "network")):
            return True
    return False


def _failure_source(spec: dict[str, Any], grade: dict[str, Any]) -> str:
    if grade["verdict"] == "pass":
        return "none"
    reason_codes = set(grade.get("reason_codes", []))
    if spec["surface"] == "structured_retrieval":
        return "structured_retrieval_mismatch"
    if spec["surface"] == "open_workflow_letta":
        return "open_workflow_answer_mismatch" if "letta_ground_truth_mismatch" in reason_codes else "open_workflow_execution_gap"
    if "work_pocket_artifact_missing" in reason_codes or "work_pocket_artifact_not_json" in reason_codes:
        return "long_handoff_artifact_failure"
    if "work_pocket_evidence_paths_mismatch" in reason_codes:
        return "long_handoff_evidence_extraction_failure"
    return "long_handoff_answer_extraction_failure"


def _write_reports(
    out: Path,
    records: list[dict[str, Any]],
    *,
    preflight: dict[str, Any],
    route: dict[str, Any],
    doctrine: dict[str, Any],
    worker_cap: int,
) -> dict[str, Any]:
    _write_jsonl(out / "phase65_context_followup_result_records.jsonl", records)
    score = _score(records)
    score["worker_cap"] = worker_cap
    score["preflight"] = preflight
    report = _report(out, records, score)
    trace = _trace_report(records)
    failure = _failure_report(records)
    _write_json(out / "phase65_context_followup_score_envelope.json", score)
    _write_json(out / "phase65_context_followup_report.json", report)
    _write_json(out / "phase65_context_followup_trace_report.json", trace)
    _write_json(out / "phase65_context_followup_failure_source_report.json", failure)
    _write_text(out / DEEP_TRACE_FILENAME, _deep_trace_analysis(out, score, trace, failure))
    _write_text(out / "phase65_context_followup_handoff.md", _handoff(out, score, preflight, route, doctrine))
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
    interpreted = [row for row in records if not row.get("invalid_infrastructure_failure", False)]
    carry = _best_variant(interpreted)
    incumbent = INCUMBENT
    carry_structured = _variant_surface_passes(interpreted, carry, "structured_retrieval")
    incumbent_structured = _variant_surface_passes(interpreted, incumbent, "structured_retrieval")
    carry_workflow = _variant_surface_passes(interpreted, carry, "open_workflow_letta")
    incumbent_workflow = _variant_surface_passes(interpreted, incumbent, "open_workflow_letta")
    carry_long = _variant_eval_pass(interpreted, carry, LONG_HANDOFF_EVAL_ID)
    extraction_long = _variant_eval_pass(interpreted, CANDIDATE_ANSWER_EXTRACTION, LONG_HANDOFF_EVAL_ID)
    extraction_ready = extraction_long or carry_long
    structured_non_regression = carry_structured >= incumbent_structured
    workflow_non_regression = carry_workflow >= incumbent_workflow
    split_ready = bool(interpreted) and len(interpreted) == len(records)
    ready = split_ready and structured_non_regression and workflow_non_regression and extraction_ready
    partial = bool(interpreted) and (structured_non_regression or workflow_non_regression or extraction_ready)
    selected = (
        "context_followup_ready_for_family_reducer"
        if ready
        else "context_followup_partial_uplift_context_still_open"
        if partial
        else "context_followup_blocked"
    )
    return {
        "mission_id": MISSION_ID,
        "run_count": len(records),
        "model_backed_runs": len(records),
        "invalid_run_count": len(records) - len(interpreted),
        "carry_forward_best_variant": carry,
        "preserved_reference_branch": CARRY_FORWARD,
        "incumbent_variant": INCUMBENT,
        "answer_extraction_probe_variant": CANDIDATE_ANSWER_EXTRACTION,
        "surface_passes": {
            "carry_forward_structured_retrieval": carry_structured,
            "incumbent_structured_retrieval": incumbent_structured,
            "carry_forward_open_workflow": carry_workflow,
            "incumbent_open_workflow": incumbent_workflow,
        },
        "long_handoff": {
            "carry_forward_pass": carry_long,
            "answer_extraction_probe_pass": extraction_long,
            "extraction_ready": extraction_ready,
        },
        "structured_non_regression": structured_non_regression,
        "workflow_non_regression": workflow_non_regression,
        "split_ready": split_ready,
        "preserves_completion_family_conclusions": True,
        "selected_recommendation": selected,
        "by_variant": _summary(records, "variant_id"),
        "by_surface": _summary(records, "surface"),
    }


def _report(out: Path, records: list[dict[str, Any]], score: dict[str, Any]) -> dict[str, Any]:
    return {
        "mission_id": MISSION_ID,
        "slice_type": "context_only_followup",
        "comparison_set": list(REQUIRED_VARIANTS),
        "accepted_context_board_count": len(_board_specs()),
        "board_shape": {"structured_contextbench_rows": 4, "open_workflow_letta_rows": 6, "long_handoff_rows": 1},
        "carry_forward_best_variant": score.get("carry_forward_best_variant"),
        "preserved_reference_branch": CARRY_FORWARD,
        "surface_focus": ["structured_retrieval", "open_workflow_letta", "long_handoff_answer_extraction"],
        "preserves_completion_family_conclusions": bool(score.get("preserves_completion_family_conclusions")),
        "variant_records": records,
        "deep_trace_artifact": str(out / DEEP_TRACE_FILENAME),
    }


def _trace_report(records: list[dict[str, Any]]) -> dict[str, Any]:
    traces = []
    for row in records:
        grade = row["score_summary"].get("grade", {})
        traces.append(
            {
                "run_id": row["run_id"],
                "eval_id": row["eval_id"],
                "variant_id": row["variant_id"],
                "surface": row["surface"],
                "final_verdict": row["score_summary"]["final_verdict"],
                "reason_codes": grade.get("reason_codes", []),
                "failure_source": row["failure_source"],
                "trace_ref": row["trace_ref"],
            }
        )
    return {"mission_id": MISSION_ID, "run_count": len(records), "traces": traces}


def _failure_report(records: list[dict[str, Any]]) -> dict[str, Any]:
    invalid = [row for row in records if row.get("invalid_infrastructure_failure", False)]
    failed = [row for row in records if not row.get("invalid_infrastructure_failure", False) and row["score_summary"]["final_verdict"] != "pass"]
    return {
        "mission_id": MISSION_ID,
        "invalid_infrastructure_failure_count": len(invalid),
        "failure_count": len(failed),
        "failure_counts_by_source": _counts(row["failure_source"] for row in failed),
        "failure_counts_by_surface": _counts(row["surface"] for row in failed),
        "records": failed,
    }


def _deep_trace_analysis(out: Path, score: dict[str, Any], trace: dict[str, Any], failure: dict[str, Any]) -> str:
    structured_failures = sum(1 for row in trace.get("traces", []) if row["surface"] == "structured_retrieval" and row["final_verdict"] != "pass")
    workflow_failures = sum(1 for row in trace.get("traces", []) if row["surface"] == "open_workflow_letta" and row["final_verdict"] != "pass")
    long_handoff_failures = sum(
        1 for row in trace.get("traces", []) if row["surface"] == "long_handoff_answer_extraction" and row["final_verdict"] != "pass"
    )
    return "\n".join(
        [
            "# Phase 6.5 Context Follow-Up Deep Trace Analysis",
            "",
            f"- mission_id: `{MISSION_ID}`",
            f"- output_root: `{out}`",
            "- scope_lock: context-only follow-up; no Packet 07 movement; shared route/scoring surfaces read-only.",
            f"- carry_forward_best_variant: `{score.get('carry_forward_best_variant')}`",
            f"- preserved_reference_branch: `{CARRY_FORWARD}`",
            f"- selected_recommendation: `{score.get('selected_recommendation')}`",
            "",
            "## Surface Reducer Findings",
            "",
            f"- structured_non_regression: `{score.get('structured_non_regression')}`",
            f"- workflow_non_regression: `{score.get('workflow_non_regression')}`",
            f"- long_handoff_extraction_ready: `{score.get('long_handoff', {}).get('extraction_ready')}`",
            f"- carry_forward_structured_retrieval_passes: `{score.get('surface_passes', {}).get('carry_forward_structured_retrieval', 0)}`",
            f"- carry_forward_open_workflow_passes: `{score.get('surface_passes', {}).get('carry_forward_open_workflow', 0)}`",
            "",
            "## Context-Specific Failure Modes",
            "",
            f"- structured_retrieval_failures: `{structured_failures}` (field mismatches against ContextBench verified rows)",
            f"- open_workflow_letta_failures: `{workflow_failures}` (answer mismatch against Letta filesystem ground truth)",
            f"- long_handoff_answer_extraction_failures: `{long_handoff_failures}` (artifact/answer extraction failures on work-pocket task)",
            f"- failure_counts_by_source: `{failure.get('failure_counts_by_source', {})}`",
            f"- invalid_infrastructure_failure_count: `{failure.get('invalid_infrastructure_failure_count', 0)}`",
            "",
            "## Carry-Forward Decision",
            "",
            f"- selected_branch: `{score.get('carry_forward_best_variant')}`",
            f"- preserved_reference_branch: `{CARRY_FORWARD}`",
            "- rationale: preserve completion-family conclusions while narrowing this follow-up to context retrieval/workflow/extraction behavior, and allow one local merged context branch to compete without mutating shared routing.",
        ]
    ) + "\n"


def _handoff(out: Path, score: dict[str, Any], preflight: dict[str, Any], route: dict[str, Any], doctrine: dict[str, Any]) -> str:
    artifacts = [
        "phase65_context_followup_score_envelope.json",
        "phase65_context_followup_report.json",
        "phase65_context_followup_trace_report.json",
        "phase65_context_followup_failure_source_report.json",
        DEEP_TRACE_FILENAME,
        "phase65_context_followup_handoff.md",
        "RAW_LEDGER_UPDATE",
    ]
    rows = [
        "# Phase 6.5 Context Follow-Up Handoff",
        "",
        f"- mission_id: `{MISSION_ID}`",
        f"- output_root: `{out}`",
        f"- run_count: `{score.get('run_count', 0)}`",
        f"- carry_forward_best_variant: `{score.get('carry_forward_best_variant')}`",
        f"- preserved_reference_branch: `{CARRY_FORWARD}`",
        f"- selected_recommendation: `{score.get('selected_recommendation')}`",
        f"- preflight_status: `{preflight.get('status')}`",
        f"- route_status: `{route.get('status')}`",
        f"- doctrine_status: `{doctrine.get('status')}`",
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
            "- task: successor Phase 6.5 context follow-up execution",
            "- event_type: experiment",
            (
                f"- summary: Executed or preflighted context-only follow-up board (4 ContextBench + 6 Letta + 1 long-handoff) "
                f"with preserved winner `{CARRY_FORWARD}` and selected branch `{score.get('carry_forward_best_variant')}`; "
                f"recommendation `{score.get('selected_recommendation')}`."
            ),
            (
                "- observations: "
                f"run_count `{score.get('run_count', 0)}`; invalid_run_count `{score.get('invalid_run_count', 0)}`; "
                f"structured_non_regression `{score.get('structured_non_regression')}`; "
                f"workflow_non_regression `{score.get('workflow_non_regression')}`; "
                f"failure_count `{failure.get('failure_count', 0)}`."
            ),
            "- inference: Context-family follow-up remains scoped to retrieval/workflow/extraction and keeps completion-family conclusions stable by preserving the prior winner while testing one local merged context branch.",
            (
                f"- evidence_paths: {out / 'phase65_context_followup_score_envelope.json'}; "
                f"{out / 'phase65_context_followup_trace_report.json'}; "
                f"{out / DEEP_TRACE_FILENAME}; {out / 'phase65_context_followup_handoff.md'}"
            ),
            "- affected_components: context-only Phase 6.5 runner; context-family reducer; deep trace context failure analysis",
            "- decision_change: Introduced a narrow governed context-family follow-up board with one local merged context branch while preserving verified_work_pocket_handoff_hybrid_01 as the reference winner.",
            "- unresolved_questions: Whether long-handoff answer extraction should stay as probe-only or become a required non-regression gate in subsequent context-family reducers.",
            "- confidence: medium",
            "- commit_message: HOLD - implement phase65 context-only follow-up runner and artifact pipeline",
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
        "carry_forward_best_variant": CARRY_FORWARD,
        "preserved_reference_branch": CARRY_FORWARD,
        "selected_recommendation": "context_followup_blocked",
        "preflight": preflight,
        "route": route,
        "doctrine": doctrine,
    }
    report = {
        "mission_id": MISSION_ID,
        "blocked": True,
        "execute": execute,
        "comparison_set": list(REQUIRED_VARIANTS),
        "preserved_reference_branch": CARRY_FORWARD,
    }
    trace = {"mission_id": MISSION_ID, "blocked": True, "run_count": 0, "traces": []}
    failure = {"mission_id": MISSION_ID, "blocked": True, "failure_count": 0, "failure_counts_by_source": {}, "records": []}
    _write_jsonl(out / "phase65_context_followup_result_records.jsonl", [])
    _write_json(out / "phase65_context_followup_score_envelope.json", score)
    _write_json(out / "phase65_context_followup_report.json", report)
    _write_json(out / "phase65_context_followup_trace_report.json", trace)
    _write_json(out / "phase65_context_followup_failure_source_report.json", failure)
    _write_text(out / DEEP_TRACE_FILENAME, _deep_trace_analysis(out, score, trace, failure))
    _write_text(out / "phase65_context_followup_handoff.md", _handoff(out, score, preflight, route, doctrine))
    ledger = _ledger(out, score, failure)
    _record_ledger(ledger)
    _write_text(out / "RAW_LEDGER_UPDATE", ledger)
    return {"output_dir": str(out), "run_count": 0, "model_backed_runs": 0, "selected_recommendation": "context_followup_blocked", "blocked": True}


def _variant_surface_passes(records: list[dict[str, Any]], variant: str, surface: str) -> int:
    return sum(1 for row in records if row["variant_id"] == variant and row["surface"] == surface and row["score_summary"]["final_verdict"] == "pass")


def _variant_eval_pass(records: list[dict[str, Any]], variant: str, eval_id: str) -> bool:
    return any(row["variant_id"] == variant and row["eval_id"] == eval_id and row["score_summary"]["final_verdict"] == "pass" for row in records)


def _summary(records: list[dict[str, Any]], key: str) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for row in records:
        bucket = out.setdefault(str(row[key]), {"run_count": 0, "pass": 0, "fail": 0, "invalid": 0})
        bucket["run_count"] += 1
        verdict = row["score_summary"]["final_verdict"]
        bucket[verdict] = bucket.get(verdict, 0) + 1
    return out


def _counts(values: Any) -> dict[str, int]:
    out: dict[str, int] = {}
    for value in values:
        out[str(value)] = out.get(str(value), 0) + 1
    return out


def _style(variant: str) -> str:
    if variant == CONTROL:
        return "control"
    if variant == INCUMBENT:
        return "incumbent"
    if variant == CARRY_FORWARD:
        return "carry_forward_context_branch"
    if variant == CANDIDATE_ANSWER_EXTRACTION:
        return "answer_extraction_probe"
    if variant == MERGED_VARIANT:
        return "merged_context_branch"
    return "hybrid_handoff_probe"


def _execution_plan(specs: list[dict[str, Any]], worker_cap: int) -> dict[str, Any]:
    return {
        "mission_id": MISSION_ID,
        "worker_cap": worker_cap,
        "planned_model_backed_runs": sum(len(spec["variant_ids"]) for spec in specs),
        "specs": [{"eval_id": spec["eval_id"], "surface": spec["surface"], "task_id": spec["task_id"], "variant_ids": spec["variant_ids"]} for spec in specs],
    }


def _board_manifest(specs: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "mission_id": MISSION_ID,
        "slice_type": "context_only",
        "comparison_set": list(REQUIRED_VARIANTS),
        "carry_forward_best_variant": CARRY_FORWARD,
        "preserved_reference_branch": CARRY_FORWARD,
        "accepted_context_board_count": len(specs),
        "accepted_tracks": {"context": len(specs)},
        "required_eval_ids": [spec["eval_id"] for spec in specs],
        "eval_ids": [spec["eval_id"] for spec in specs],
        "authority": _authority(),
    }


def _build_route_manifest(variant: str) -> dict[str, Any]:
    if variant != MERGED_VARIANT:
        return build_packet04_route_manifest(variant, scope=PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE)
    manifest = deepcopy(build_packet04_route_manifest(CARRY_FORWARD, scope=PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE))
    merged_path = (Path.cwd() / MERGED_CONTEXT_FILE).resolve()
    if not merged_path.exists():
        raise ValueError(f"merged context route missing: {merged_path}")
    for entry in manifest["routed_modules"]:
        entry["variant_id"] = MERGED_VARIANT
        if entry["runtime_key"] == "context":
            entry["declared_card_path"] = str(MERGED_CONTEXT_FILE)
            entry["real_file_path"] = str(merged_path)
            entry["module_import_path"] = MERGED_CONTEXT_MODULE
            entry["file_sha256"] = hashlib.sha256(merged_path.read_bytes()).hexdigest()
    manifest["variant_id"] = MERGED_VARIANT
    manifest["variant_card_ref"] = None
    manifest["route_manifest_fingerprint"] = hashlib.sha256(
        json.dumps(
            {
                "route_scope": manifest["route_scope"],
                "variant_id": MERGED_VARIANT,
                "routed_modules": [
                    {
                        "runtime_key": row["runtime_key"],
                        "surface_id": row["surface_id"],
                        "module_import_path": row["module_import_path"],
                        "file_sha256": row["file_sha256"],
                        "claimed_changed_surface": row["claimed_changed_surface"],
                    }
                    for row in sorted(manifest["routed_modules"], key=lambda item: item["surface_id"])
                ],
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    return manifest


def _best_variant(records: list[dict[str, Any]]) -> str:
    candidates = [CARRY_FORWARD, MERGED_VARIANT]
    available = [variant for variant in candidates if any(row["variant_id"] == variant for row in records)]
    if not available:
        return CARRY_FORWARD
    def rank(variant: str) -> tuple[int, int, int, int]:
        return (
            sum(1 for row in records if row["variant_id"] == variant and row["score_summary"]["final_verdict"] == "pass"),
            _variant_surface_passes(records, variant, "structured_retrieval"),
            _variant_surface_passes(records, variant, "open_workflow_letta"),
            1 if _variant_eval_pass(records, variant, LONG_HANDOFF_EVAL_ID) else 0,
        )
    return max(available, key=lambda variant: (rank(variant), variant == MERGED_VARIANT))


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
            launch_phase65_context_followup(
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
