"""Execute the accepted successor Phase 6.5 completion-closure loop."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from time import perf_counter
from typing import Any

from blocks.verification.closure_truth_state import build_closure_state, fingerprint
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
from runner.successor_phase65_measurement_repair import _seed_public_terminalbench_workspace
from runner.successor_phase65_resumed_board import EXTRACT_VIDEO_MIRROR
from runner.successor_phase6_corrective_rerun import (
    _authority,
    _record_ledger,
    _run,
    _usage,
    _write_json,
    _write_jsonl,
    _write_text,
)

MISSION_ID = "successor_phase65_completion_closure"
CONTROL = "spb_01"
INCUMBENT = "spb_tooling_seed_plus_receipt_and_completion_01"
HARNESS_STYLES = ("artifact_and_verifier_hard_gate_01", "checkpoint_verify_01")
HYBRID_STYLES = (
    "candidate_plus_closure_truth_ledger_01",
    "candidate_plus_closure_evidence_projection_01",
    "candidate_plus_app_workspace_path_normalizer_01",
)
ALL_VARIANTS = (CONTROL, INCUMBENT, *HARNESS_STYLES, *HYBRID_STYLES)
DEFAULT_OUTPUT_DIR = Path(
    "tracking/collab/stage_03_execution_planning/packets/packet_06_paired_combo_variants/"
    "runs/2026-05-07_successor_phase65_completion_closure"
)
RECOMMENDATIONS = (
    "completion_closure_repair_sufficient_for_mixed_confirmation",
    "completion_closure_repair_showed_partial_uplift_run_context_followup_next",
    "completion_closure_repair_still_blocked",
)
TERMINALBENCH_ROOT = Path("/Users/mohamud/Downloads/terminalbench/official_tasks")
OPTIONAL_FIX_GIT = "terminalbench_public_fix-git"
DEFAULT_THROUGHPUT_WORKERS = 2


def launch_phase65_completion_closure(
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
    _write_text(out / "phase65_completion_closure_plan.md", _plan(out, preflight, route, doctrine, specs, worker_cap))
    _write_json(out / "phase65_completion_closure_board_manifest.json", _board_manifest(specs))
    _write_json(out / "phase65_completion_closure_route_matrix.json", route)
    _write_json(out / "phase65_completion_closure_variant_doctrine_matrix.json", doctrine)
    _write_json(out / "phase65_completion_closure_execution_plan.json", _execution_plan(specs, worker_cap))
    if not execute or preflight["status"] != "pass" or route["status"] != "pass" or doctrine["status"] != "pass":
        return _write_blocked(out, preflight, route, doctrine, execute, worker_cap=worker_cap)
    records = _execute_plan(out, _plan_rows(specs), worker_cap=worker_cap)
    return _write_reports(out, records, preflight, route, doctrine, worker_cap=worker_cap)


def _board_specs() -> list[dict[str, Any]]:
    return [
        {
            "eval_id": "tb_style_partial_progress_false_completion_v1",
            "benchmark_class": "phase65_completion_partial_progress",
            "task_id": "tb_style_partial_progress_false_completion_v1",
            "task_prompt": (
                "Read /app/notes/amounts.json, compute the total, and write /app/final/report.json "
                'with exactly {"status": "complete", "total": 50}. Only close after that file exists, '
                "and state the path plus the total."
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
            "variant_ids": list(ALL_VARIANTS),
            "max_steps": 4,
            "timeout_sec": 120,
        },
        {
            "eval_id": "tb_style_verifier_fail_then_repair_v1",
            "benchmark_class": "phase65_completion_verifier_repair",
            "task_id": "tb_style_verifier_fail_then_repair_v1",
            "task_prompt": "Run /app/verify.sh, repair /app/output.txt until the verifier passes, rerun the verifier, and then close.",
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
            "variant_ids": list(ALL_VARIANTS),
            "max_steps": 4,
            "timeout_sec": 120,
        },
        {
            "eval_id": "extract_moves_from_video_repaired_closure",
            "benchmark_class": "terminalbench_repaired_closure",
            "task_id": "extract-moves-from-video",
            "task_prompt": (
                "Use the local mirrored /app/video.mp4 instead of any remote download. "
                "Transcribe the player moves into /app/solution.txt, one move per line, and only close after the file exists."
            ),
            "workspace_seed": "extract_moves",
            "closure_contract": {
                "required_deliverables": ["/app/solution.txt"],
                "required_artifact_paths": ["/app/solution.txt"],
                "requires_verifier": False,
            },
            "variant_ids": list(ALL_VARIANTS),
            "max_steps": 6,
            "timeout_sec": 240,
        },
        {
            "eval_id": "terminalbench_public_financial-document-processor",
            "benchmark_class": "terminalbench_public_regression",
            "task_id": "financial-document-processor",
            "task_prompt": (
                "Process the files under /app/documents into /app/invoices and /app/other, then write /app/invoices/summary.csv "
                "with the required totals. Only close after /app/documents is empty."
            ),
            "workspace_seed": "financial_docs",
            "closure_contract": {
                "required_deliverables": ["/app/invoices", "/app/other", "/app/invoices/summary.csv"],
                "required_artifact_paths": ["/app/invoices/summary.csv"],
                "requires_verifier": False,
            },
            "variant_ids": list(ALL_VARIANTS),
            "max_steps": 6,
            "timeout_sec": 240,
        },
        {
            "eval_id": OPTIONAL_FIX_GIT,
            "benchmark_class": "terminalbench_public_regression",
            "task_id": "fix-git",
            "task_prompt": (
                "Recover the missing site changes into the local workspace. The required file state lives under /app/resources/patch_files "
                "and the working tree lives under /app/personal-site."
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
            "variant_ids": list(ALL_VARIANTS),
            "max_steps": 6,
            "timeout_sec": 180,
            "optional": True,
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
        records: list[dict[str, Any]] = []
        for row in plan_rows:
            records.append(_run_one(out, row["spec"], row["variant"], plan_index=row["plan_index"]))
        return records

    completed: list[tuple[int, dict[str, Any]]] = []
    with ThreadPoolExecutor(max_workers=worker_cap) as executor:
        future_map = {
            executor.submit(_run_one, out, row["spec"], row["variant"], plan_index=row["plan_index"]): row["plan_index"]
            for row in plan_rows
        }
        for future in as_completed(future_map):
            plan_index = future_map[future]
            completed.append((plan_index, future.result()))
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
    if planned_runs > 35:
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
    for variant in ALL_VARIANTS:
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
        "artifact_and_verifier_hard_gate_01": {"verification"},
        "checkpoint_verify_01": {"context", "verification"},
        "candidate_plus_closure_truth_ledger_01": {"context", "verification"},
        "candidate_plus_closure_evidence_projection_01": {"context", "verification"},
        "candidate_plus_app_workspace_path_normalizer_01": {"tools_getter", "tool_executor", "context", "verification"},
    }
    rows = []
    blockers = []
    for row in route["routes"]:
        changed = set(row.get("changed_runtime_keys", []))
        required = requirements.get(row["variant_id"], set())
        style = _style(row["variant_id"])
        mechanism = bool(not required or required <= changed)
        if required and not mechanism:
            blockers.append({"variant_id": row["variant_id"], "required_runtime_keys": sorted(required), "changed_runtime_keys": sorted(changed)})
        rows.append(
            {
                "variant_id": row["variant_id"],
                "style": style,
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
    model_exec_started = perf_counter()
    result = run_reference_baseline(
        run_id=run_id,
        run_dir=run_dir,
        task_id=spec["task_id"],
        task_prompt=spec["task_prompt"] + "\nUse shell inspection where useful. Final answer must match the latest truthful closure state.",
        benchmark_family=spec["benchmark_class"],
        case_id=spec["eval_id"],
        seed_id=variant,
        model_route=make_azure_gpt53_codex_route_from_env(),
        model_client_kwargs={"timeout_sec": int(spec["timeout_sec"]), "max_retries": 1},
        workspace_state_overrides={"closure_contract": contract},
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
    closure_state = result.get("authoritative_closure_state") or build_closure_state(
        spec["task_prompt"],
        {
            "closure_contract": contract,
            "cwd": str(workspace),
            "execution_result": result["execution"],
            "model_claimed_done": result["execution"]["status"] == "completed",
        },
    )
    failure_source = _failure_source(grade, closure_state)
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
        "score_summary": {"final_verdict": grade["verdict"], "grade": grade},
        "closure_state": closure_state,
        "failure_source": failure_source,
        "token_and_cost_summary": _usage(result),
        "trace_ref": str(run_dir / "run_events.jsonl"),
        "run_dir": str(run_dir),
        "model_backed": True,
        "invalid_infrastructure_failure": False,
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


def _seed_workspace(workspace: Path, spec: dict[str, Any]) -> None:
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    seed = spec["workspace_seed"]
    if seed == "simple_files":
        for raw_path, content in spec.get("workspace_files", {}).items():
            path = workspace / raw_path.lstrip("/")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        return
    if seed == "extract_moves":
        shutil.copy2(EXTRACT_VIDEO_MIRROR, workspace / "video.mp4")
        return
    if seed == "financial_docs":
        shutil.copytree(
            TERMINALBENCH_ROOT / "financial-document-processor/environment/documents",
            workspace / "documents",
        )
        return
    if seed == "fix_git":
        _seed_public_terminalbench_workspace(workspace, "fix-git")
        broken = workspace / "personal-site/_includes/about.md"
        broken.write_text("broken about page\n", encoding="utf-8")
        (workspace / "personal-site/_layouts/default.html").write_text("<html>broken</html>\n", encoding="utf-8")
        return
    raise ValueError(f"unsupported_workspace_seed:{seed}")


def _workspace_fingerprints(workspace: Path) -> dict[str, str]:
    return {path.relative_to(workspace).as_posix(): fingerprint(path) for path in workspace.rglob("*") if path.is_file()}


def _failure_source(grade: dict[str, Any], closure_state: dict[str, Any]) -> str:
    if grade["verdict"] == "pass":
        return "none"
    blockers = set(closure_state.get("unresolved_blockers", []))
    if "required_artifact_missing" in blockers and not closure_state.get("actual_written_paths"):
        return "artifact_missing"
    if closure_state.get("path_mismatches"):
        return "path_mismatch"
    latest_verifier = closure_state.get("latest_verifier_result")
    if isinstance(latest_verifier, dict) and latest_verifier.get("status") != "pass":
        return "verifier_failure"
    if "final_answer_missing_artifact_path" in blockers or "final_answer_missing_verifier_evidence" in blockers:
        return "closure_evidence_omission"
    return "raw_task_capability_limit"


def _write_reports(
    out: Path,
    records: list[dict[str, Any]],
    preflight: dict[str, Any],
    route: dict[str, Any],
    doctrine: dict[str, Any],
    *,
    worker_cap: int,
) -> dict[str, Any]:
    _write_jsonl(out / "phase65_completion_closure_result_records.jsonl", records)
    score = _score(records)
    score["worker_cap"] = worker_cap
    report = _report(records, score)
    trace = _trace_report(records)
    failure = _failure_report(records)
    cost = _cost_report(records)
    runtime_profile = _runtime_profile(records, worker_cap=worker_cap)
    _write_json(out / "phase65_completion_closure_score_envelope.json", score)
    _write_json(out / "phase65_completion_closure_report.json", report)
    _write_json(out / "phase65_completion_closure_trace_report.json", trace)
    _write_json(out / "phase65_completion_closure_failure_source_report.json", failure)
    _write_json(out / "phase65_completion_closure_cost_report.json", cost)
    _write_json(out / "phase65_completion_closure_runtime_profile.json", runtime_profile)
    _write_text(out / "phase65_completion_closure_handoff.md", _handoff(out, score, report, preflight, route, doctrine))
    ledger = _ledger(out, score, report)
    _record_ledger(ledger)
    _write_text(out / "RAW_LEDGER_UPDATE", ledger)
    return {
        "output_dir": str(out),
        "run_count": len(records),
        "model_backed_runs": score["model_backed_runs"],
        "selected_recommendation": score["selected_recommendation"],
    }


def _score(records: list[dict[str, Any]]) -> dict[str, Any]:
    required_records = [row for row in records if not row["optional_eval"]]
    incumbent_required = _variant_passes(required_records, INCUMBENT)
    hybrid_best = max((_variant_passes(required_records, variant) for variant in HYBRID_STYLES), default=0)
    hybrid_best_variant = max(HYBRID_STYLES, key=lambda variant: _variant_passes(required_records, variant))
    extract_failures = [row for row in required_records if row["eval_id"] == "extract_moves_from_video_repaired_closure" and row["score_summary"]["final_verdict"] != "pass"]
    selected = _recommendation(required_records, incumbent_required, hybrid_best, extract_failures, hybrid_best_variant)
    return {
        "mission_id": MISSION_ID,
        "run_count": len(records),
        "model_backed_runs": len(records),
        "required_eval_run_count": len(required_records),
        "variant_summary": _summary(records, "variant_id"),
        "style_summary": _summary(records, "style"),
        "by_eval_variant": _by_eval_variant(records),
        "best_hybrid_variant": hybrid_best_variant,
        "selected_recommendation": selected,
    }


def _report(records: list[dict[str, Any]], score: dict[str, Any]) -> dict[str, Any]:
    return {
        "mission_id": MISSION_ID,
        "completion_required_eval_ids": [row["eval_id"] for row in _board_specs() if not row.get("optional")],
        "comparison_set": list(ALL_VARIANTS),
        "style_mapping": {variant: _style(variant) for variant in ALL_VARIANTS},
        "best_hybrid_variant": score.get("best_hybrid_variant"),
        "variant_records": records,
    }


def _trace_report(records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "mission_id": MISSION_ID,
        "run_count": len(records),
        "traces": [
            {
                "run_id": row["run_id"],
                "eval_id": row["eval_id"],
                "variant_id": row["variant_id"],
                "required_deliverables": row["closure_state"].get("required_deliverables", []),
                "required_artifact_paths": row["closure_state"].get("required_artifact_paths", []),
                "actual_written_paths": row["closure_state"].get("actual_written_paths", []),
                "latest_verifier_result": row["closure_state"].get("latest_verifier_result"),
                "unresolved_blockers": row["closure_state"].get("unresolved_blockers", []),
                "closure_status": row["closure_state"].get("status"),
            }
            for row in records
        ],
    }


def _failure_report(records: list[dict[str, Any]]) -> dict[str, Any]:
    failed = [row for row in records if row["score_summary"]["final_verdict"] != "pass"]
    extract = [row for row in failed if row["eval_id"] == "extract_moves_from_video_repaired_closure"]
    return {
        "mission_id": MISSION_ID,
        "failure_count": len(failed),
        "failure_counts_by_source": _counts(row["failure_source"] for row in failed),
        "extract_moves_from_video_failure_classification": [
            {
                "variant_id": row["variant_id"],
                "failure_source": row["failure_source"],
                "closure_status": row["closure_state"].get("status"),
                "unresolved_blockers": row["closure_state"].get("unresolved_blockers", []),
            }
            for row in extract
        ],
        "records": failed,
    }


def _cost_report(records: list[dict[str, Any]]) -> dict[str, Any]:
    total_tokens = sum(int(row["token_and_cost_summary"].get("total_tokens", 0) or 0) for row in records)
    total_usd = sum(float(row["token_and_cost_summary"].get("usd", 0.0) or 0.0) for row in records)
    return {
        "mission_id": MISSION_ID,
        "budget_caps": {"hard_model_backed_cap": 35, "soft_cost_cap_usd": 35, "hard_cost_cap_usd": 70},
        "total": {"total_tokens": total_tokens, "usd": total_usd},
        "cap_status": "below_soft_cap" if total_usd <= 35 else "below_hard_cap" if total_usd <= 70 else "hard_cap_exceeded",
    }


def _runtime_profile(records: list[dict[str, Any]], *, worker_cap: int) -> dict[str, Any]:
    model_runs = [row for row in records if row.get("model_backed")]
    breakdown = {
        "total_run_wall_sec": 0.0,
        "model_backed_latency_sec": 0.0,
        "tool_exec_sec": 0.0,
        "orchestration_overhead_sec": 0.0,
        "verification_sec": 0.0,
        "grading_reporting_overhead_sec": 0.0,
        "sandbox_overhead_sec": 0.0,
        "docker_overhead_sec": 0.0,
    }
    for row in model_runs:
        timing = row.get("timing_summary", {})
        breakdown["total_run_wall_sec"] += float(timing.get("run_wall_sec", 0.0) or 0.0)
        breakdown["model_backed_latency_sec"] += float(timing.get("model_backed_latency_sec", 0.0) or 0.0)
        breakdown["tool_exec_sec"] += float(timing.get("tool_exec_sec", 0.0) or 0.0)
        breakdown["orchestration_overhead_sec"] += float(timing.get("orchestration_overhead_sec", 0.0) or 0.0)
        breakdown["verification_sec"] += float(timing.get("verification_sec", 0.0) or 0.0)
        breakdown["grading_reporting_overhead_sec"] += float(timing.get("grading_overhead_sec", 0.0) or 0.0) + float(
            timing.get("reporting_overhead_sec", 0.0) or 0.0
        )
        breakdown["sandbox_overhead_sec"] += float(timing.get("sandbox_overhead_sec", 0.0) or 0.0)
        breakdown["docker_overhead_sec"] += float(timing.get("docker_overhead_sec", 0.0) or 0.0)
    return {
        "mission_id": MISSION_ID,
        "worker_cap": worker_cap,
        "run_count": len(model_runs),
        "breakdown_sec": breakdown,
    }


def _recommendation(
    required_records: list[dict[str, Any]],
    incumbent_required: int,
    hybrid_best: int,
    extract_failures: list[dict[str, Any]],
    hybrid_best_variant: str,
) -> str:
    if hybrid_best >= incumbent_required + 1 and not extract_failures:
        return "completion_closure_repair_sufficient_for_mixed_confirmation"
    if hybrid_best > incumbent_required or (
        hybrid_best_variant == "candidate_plus_closure_truth_ledger_01"
        and any(row["failure_source"] != "raw_task_capability_limit" for row in extract_failures)
    ):
        return "completion_closure_repair_showed_partial_uplift_run_context_followup_next"
    return "completion_closure_repair_still_blocked"


def _variant_passes(records: list[dict[str, Any]], variant: str) -> int:
    return sum(1 for row in records if row["variant_id"] == variant and row["score_summary"]["final_verdict"] == "pass")


def _summary(records: list[dict[str, Any]], key: str) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for row in records:
        bucket = out.setdefault(row[key], {"run_count": 0, "pass": 0, "fail": 0})
        bucket["run_count"] += 1
        bucket[row["score_summary"]["final_verdict"]] += 1
    return out


def _by_eval_variant(records: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for row in records:
        cell = out.setdefault(row["eval_id"], {}).setdefault(row["variant_id"], {"run_count": 0, "pass": 0, "fail": 0})
        cell["run_count"] += 1
        cell[row["score_summary"]["final_verdict"]] += 1
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
        return "model_led_ish"
    if variant in HARNESS_STYLES:
        return "harness_led_ish"
    return "hybrid"


def _execution_plan(specs: list[dict[str, Any]], worker_cap: int) -> dict[str, Any]:
    return {
        "mission_id": MISSION_ID,
        "worker_cap": worker_cap,
        "planned_model_backed_runs": sum(len(spec["variant_ids"]) for spec in specs),
        "specs": [
            {
                "eval_id": spec["eval_id"],
                "task_id": spec["task_id"],
                "variant_ids": spec["variant_ids"],
                "optional": bool(spec.get("optional")),
            }
            for spec in specs
        ],
    }


def _board_manifest(specs: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "mission_id": MISSION_ID,
        "slice_type": "completion_only",
        "comparison_set": list(ALL_VARIANTS),
        "required_eval_ids": [spec["eval_id"] for spec in specs if not spec.get("optional")],
        "optional_eval_ids": [spec["eval_id"] for spec in specs if spec.get("optional")],
        "authority": _authority(),
    }


def _plan(
    out: Path,
    preflight: dict[str, Any],
    route: dict[str, Any],
    doctrine: dict[str, Any],
    specs: list[dict[str, Any]],
    worker_cap: int,
) -> str:
    return "\n".join(
        [
            "# Phase 6.5 Completion Closure Plan",
            "",
            f"- mission_id: `{MISSION_ID}`",
            f"- output_root: `{out}`",
            "- locked_scope: completion-only; no Packet 07 movement; no benchmark widening; no broad context or BFCL rerun.",
            f"- preflight_status: `{preflight['status']}`",
            f"- route_status: `{route['status']}`",
            f"- doctrine_status: `{doctrine['status']}`",
            f"- worker_cap: `{worker_cap}`",
            f"- planned_model_backed_runs: `{sum(len(spec['variant_ids']) for spec in specs)}`",
            "- completion_eval_set: tb_style_partial_progress_false_completion_v1, tb_style_verifier_fail_then_repair_v1, extract_moves_from_video_repaired_closure, terminalbench_public_financial-document-processor, optional terminalbench_public_fix-git.",
        ]
    )


def _handoff(
    out: Path,
    score: dict[str, Any],
    report: dict[str, Any],
    preflight: dict[str, Any],
    route: dict[str, Any],
    doctrine: dict[str, Any],
) -> str:
    return "\n".join(
        [
            "# Phase 6.5 Completion Closure Handoff",
            "",
            f"- mission_id: `{MISSION_ID}`",
            f"- output_root: `{out}`",
            f"- run_count: `{score['run_count']}`",
            f"- best_hybrid_variant: `{score.get('best_hybrid_variant')}`",
            f"- selected_recommendation: `{score['selected_recommendation']}`",
            f"- preflight_status: `{preflight['status']}`",
            f"- route_status: `{route['status']}`",
            f"- doctrine_status: `{doctrine['status']}`",
            "- closure_truth_focus: required deliverables, required artifact paths, actual written paths, verifier attempts/latest result, unresolved blockers, and final answer projection.",
            f"- comparison_styles: `{report['style_mapping']}`",
        ]
    )


def _ledger(out: Path, score: dict[str, Any], report: dict[str, Any]) -> str:
    return "\n".join(
        [
            "RAW_LEDGER_UPDATE",
            "- actor: codex",
            "- task: successor Phase 6.5 completion closure loop",
            "- event_type: experiment",
            f"- summary: Executed the bounded completion-closure board and selected `{score['selected_recommendation']}` with `{score.get('best_hybrid_variant')}` as the best hybrid candidate.",
            f"- observations: run_count `{score['run_count']}`; model_backed_runs `{score['model_backed_runs']}`; comparison_set `{', '.join(report['comparison_set'])}`.",
            "- inference: Authoritative closure truth is now compared directly against model-led-ish and harness-led-ish completion mechanisms on the certified completion eval set.",
            f"- evidence_paths: {out / 'phase65_completion_closure_score_envelope.json'}; {out / 'phase65_completion_closure_failure_source_report.json'}; {out / 'phase65_completion_closure_handoff.md'}",
            "- affected_components: Packet06 route admission; completion closure verification; completion-only Phase 6.5 board",
            "- decision_change: completion-only closure slice executed without reopening throughput, Packet 07, or benchmark authority",
            "- unresolved_questions: Whether remaining extract-moves failures are path/closure issues or raw task-capability limits, and whether mixed confirmation is now justified.",
            "- confidence: medium",
            "- commit_message: HOLD - phase65 completion closure board artifacts",
        ]
    )


def _write_blocked(
    out: Path,
    preflight: dict[str, Any],
    route: dict[str, Any],
    doctrine: dict[str, Any],
    execute: bool,
    *,
    worker_cap: int,
) -> dict[str, Any]:
    score = {
        "mission_id": MISSION_ID,
        "run_count": 0,
        "model_backed_runs": 0,
        "worker_cap": worker_cap,
        "selected_recommendation": "completion_closure_repair_still_blocked",
        "preflight": preflight,
        "route": route,
        "doctrine": doctrine,
    }
    _write_jsonl(out / "phase65_completion_closure_result_records.jsonl", [])
    _write_json(out / "phase65_completion_closure_score_envelope.json", score)
    _write_json(out / "phase65_completion_closure_report.json", {"mission_id": MISSION_ID, "blocked": True, "execute": execute})
    _write_json(out / "phase65_completion_closure_trace_report.json", {"mission_id": MISSION_ID, "blocked": True})
    _write_json(out / "phase65_completion_closure_failure_source_report.json", {"mission_id": MISSION_ID, "blocked": True})
    _write_json(out / "phase65_completion_closure_cost_report.json", {"mission_id": MISSION_ID, "blocked": True})
    _write_json(out / "phase65_completion_closure_runtime_profile.json", {"mission_id": MISSION_ID, "blocked": True, "worker_cap": worker_cap})
    _write_text(out / "phase65_completion_closure_handoff.md", _handoff(out, score, _report([], score), preflight, route, doctrine))
    ledger = _ledger(out, score, _report([], score))
    _record_ledger(ledger)
    _write_text(out / "RAW_LEDGER_UPDATE", ledger)
    return {
        "output_dir": str(out),
        "run_count": 0,
        "model_backed_runs": 0,
        "selected_recommendation": "completion_closure_repair_still_blocked",
        "blocked": True,
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
            launch_phase65_completion_closure(
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
