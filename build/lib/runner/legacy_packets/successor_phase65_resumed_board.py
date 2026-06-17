"""Execute the reduced resumed Phase 6.5 board under the repaired measurement stack."""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
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
from runner.phase65_measurement_contracts import load_regex_log_contract
from runner.phase65_measurement_grading import grade_phase65_spec
from runner.successor_phase65_measurement_repair import _seed_financial_workspace
from runner.successor_phase6_corrective_rerun import (
    BFCL_PATH,
    CONTEXTBENCH_ROOT,
    LETTA_ROOT,
    PRICE,
    TERMINALBENCH_ROOT,
    _authority,
    _patch_score,
    _record_ledger,
    _run,
    _usage,
    _write_json,
    _write_jsonl,
    _write_text,
)

MISSION_ID = "successor_phase65_resumed_board"
CONTROL = "spb_01"
INCUMBENT = "spb_tooling_seed_plus_receipt_and_completion_01"
SHARP_BFCL_CHALLENGER = "candidate_plus_bfcl_strict_argument_guard_01"
TRACK1_VARIANTS = (
    CONTROL,
    INCUMBENT,
    SHARP_BFCL_CHALLENGER,
)
TRACK2_VARIANTS = (
    CONTROL,
    INCUMBENT,
    "artifact_and_verifier_hard_gate_01",
    "checkpoint_verify_01",
)
TRACK3_VARIANTS = (
    CONTROL,
    INCUMBENT,
    "candidate_plus_hybrid_receipt_handoff_01",
    "verified_work_pocket_handoff_hybrid_01",
    "candidate_plus_context_answer_extraction_01",
)
ALL_VARIANTS = tuple(dict.fromkeys((*TRACK1_VARIANTS, *TRACK2_VARIANTS, *TRACK3_VARIANTS)))
DEFAULT_OUTPUT_DIR = Path(
    "tracking/collab/stage_03_execution_planning/packets/packet_06_paired_combo_variants/"
    "runs/2026-05-06_successor_phase65_resumed_board"
)
MEASUREMENT_REPAIR_REPORT = Path(
    "tracking/collab/stage_03_execution_planning/packets/packet_06_paired_combo_variants/"
    "runs/2026-05-06_successor_phase65_measurement_repair/phase65_measurement_repair_score_envelope.json"
)
MEASUREMENT_FOLLOWUP_REPORT = Path(
    "tracking/collab/stage_03_execution_planning/packets/packet_06_paired_combo_variants/"
    "runs/2026-05-06_successor_phase65_measurement_followup/phase65_measurement_followup_contract_report.json"
)
EXTRACT_VIDEO_MIRROR = Path(
    "tracking/collab/stage_03_execution_planning/packets/packet_06_paired_combo_variants/"
    "runs/2026-05-05_terminalbench_failure_probe_extract_moves_from_video_repaired/runs/"
    "terminalbench_failure_probe_extract_moves_from_video__extract-moves-from-video__spb_01__r0/workspace/video.mp4"
)
RECOMMENDATIONS = (
    "candidate_repaired_and_ready_for_packet07_readiness_review",
    "candidate_needs_toolcall_repair",
    "candidate_needs_completion_repair",
    "candidate_needs_context_workflow_repair",
    "incumbent_still_best_run_single_family_autoresearch_loop",
    "prefer_spb_01_or_pause_successor",
)
ROUTE_REQUIREMENTS = {
    SHARP_BFCL_CHALLENGER: {"tools_getter", "tool_executor"},
    "artifact_and_verifier_hard_gate_01": {"verification"},
    "checkpoint_verify_01": {"context", "verification"},
    "candidate_plus_hybrid_receipt_handoff_01": {"tools_getter", "tool_executor", "context"},
    "verified_work_pocket_handoff_hybrid_01": {"tools_getter", "tool_executor", "context", "verification"},
    "candidate_plus_context_answer_extraction_01": {"context"},
}
TRACK_TO_FAMILY = {"bfcl": "BFCL/tool-call completeness", "completion": "completion/closure", "context": "context/workflow"}
DEFAULT_THROUGHPUT_WORKERS = 2


def launch_phase65_resumed_board(
    *,
    output_dir: str | Path,
    execute: bool = True,
    max_workers: int = 1,
    selected_tracks: tuple[str, ...] | None = None,
    max_specs_per_track: int | None = None,
    max_variants_per_spec: int | None = None,
) -> dict[str, Any]:
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    worker_cap = _resolve_worker_cap(max_workers)
    include_terminalbench_regression = _should_include_terminalbench_regression(selected_tracks)
    specs = _slice_specs(
        _board_specs(),
        selected_tracks=selected_tracks,
        max_specs_per_track=max_specs_per_track,
        max_variants_per_spec=max_variants_per_spec,
    )
    preflight = _preflight(specs, include_terminalbench_regression=include_terminalbench_regression)
    route = _route_matrix()
    doctrine = _variant_doctrine_matrix(route)
    _write_text(
        out / "phase65_resumed_plan.md",
        _plan(out, specs, preflight, route, doctrine, worker_cap, include_terminalbench_regression=include_terminalbench_regression),
    )
    _write_json(
        out / "phase65_resumed_board_manifest.json",
        _board_manifest(specs, include_terminalbench_regression=include_terminalbench_regression),
    )
    _write_json(out / "phase65_resumed_route_matrix.json", route)
    _write_json(out / "phase65_resumed_variant_doctrine_matrix.json", doctrine)
    _write_json(
        out / "phase65_resumed_execution_plan.json",
        _execution_plan(specs, worker_cap, include_terminalbench_regression=include_terminalbench_regression),
    )
    if not execute or preflight["status"] != "pass" or route["status"] != "pass" or doctrine["status"] != "pass":
        return _write_blocked(out, preflight, route, doctrine, execute, worker_cap=worker_cap)

    records, traces = _execute_plan(
        out,
        _plan_rows(specs, tracks=("bfcl", "completion", "context")),
        worker_cap=worker_cap,
    )
    _enforce_caps(records)

    best_candidate = None
    if include_terminalbench_regression:
        best_candidate = _select_best_repaired_candidate(records)
        regression_records, regression_traces = _execute_plan(
            out,
            _plan_rows(_regression_specs(best_candidate), tracks=("terminalbench",)),
            worker_cap=worker_cap,
        )
        records.extend(regression_records)
        traces.extend(regression_traces)
        _enforce_caps(records)

    return _write_reports(
        out,
        records=records,
        traces=traces,
        preflight=preflight,
        route=route,
        doctrine=doctrine,
        best_regression_candidate=best_candidate,
        worker_cap=worker_cap,
    )


def _board_specs() -> list[dict[str, Any]]:
    return [
        *_bfcl_specs(),
        *_completion_specs(),
        *_context_specs(),
    ]


def _should_include_terminalbench_regression(selected_tracks: tuple[str, ...] | None) -> bool:
    if selected_tracks is None:
        return True
    return set(selected_tracks) == {"bfcl", "completion", "context"}


def _resolve_worker_cap(max_workers: int) -> int:
    if max_workers < 1:
        raise ValueError("max_workers must be >= 1")
    host_cpus = os.cpu_count() or 2
    return max(1, min(max_workers, 4, host_cpus))


def _slice_specs(
    specs: list[dict[str, Any]],
    *,
    selected_tracks: tuple[str, ...] | None,
    max_specs_per_track: int | None,
    max_variants_per_spec: int | None,
) -> list[dict[str, Any]]:
    allowed_tracks = set(selected_tracks) if selected_tracks else None
    counters: dict[str, int] = {}
    selected: list[dict[str, Any]] = []
    for spec in specs:
        track = spec["track"]
        if allowed_tracks is not None and track not in allowed_tracks:
            continue
        counters.setdefault(track, 0)
        if isinstance(max_specs_per_track, int) and max_specs_per_track > 0 and counters[track] >= max_specs_per_track:
            continue
        counters[track] += 1
        row = dict(spec)
        if isinstance(max_variants_per_spec, int) and max_variants_per_spec > 0:
            row["variant_ids"] = list(row["variant_ids"][:max_variants_per_spec])
        selected.append(row)
    return selected


def _plan_rows(specs: list[dict[str, Any]], *, tracks: tuple[str, ...]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    plan_index = 0
    for track in tracks:
        for spec in [row for row in specs if row["track"] == track]:
            for variant in spec["variant_ids"]:
                rows.append({"plan_index": plan_index, "spec": spec, "variant": variant})
                plan_index += 1
    return rows


def _execute_plan(
    out: Path,
    plan_rows: list[dict[str, Any]],
    *,
    worker_cap: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not plan_rows:
        return [], []
    if worker_cap == 1:
        records: list[dict[str, Any]] = []
        traces: list[dict[str, Any]] = []
        for row in plan_rows:
            record, trace = _run_with_retry(out, row["spec"], row["variant"], plan_index=row["plan_index"])
            records.append(record)
            traces.append(trace)
        return records, traces

    completed: list[tuple[int, dict[str, Any], dict[str, Any]]] = []
    with ThreadPoolExecutor(max_workers=worker_cap) as executor:
        future_map = {
            executor.submit(
                _run_with_retry,
                out,
                row["spec"],
                row["variant"],
                plan_index=row["plan_index"],
            ): row["plan_index"]
            for row in plan_rows
        }
        for future in as_completed(future_map):
            plan_index = future_map[future]
            record, trace = future.result()
            completed.append((plan_index, record, trace))
    completed.sort(key=lambda row: row[0])
    return [row[1] for row in completed], [row[2] for row in completed]


def _bfcl_specs() -> list[dict[str, Any]]:
    rows = json.loads(BFCL_PATH.read_text(encoding="utf-8"))
    selected_ids = (
        "multi_turn_composite_97",
        "multi_turn_composite_116",
        "multi_turn_composite_199",
        "multi_turn_miss_func_55",
        "multi_turn_miss_param_55",
    )
    by_id = {row["id"]: row for row in rows}
    specs = []
    for eval_id in selected_ids:
        row = by_id[eval_id]
        specs.append(
            {
                "eval_id": f"bfcl_v3_strict_{eval_id}",
                "track": "bfcl",
                "benchmark_class": "bfcl_strict_ground_truth",
                "task_id": row["id"],
                "task_prompt": row["prompt"],
                "workspace_seed": "simple_files",
                "workspace_files": dict(row["files"]),
                "ground_truth": row["ground_truth"],
                "variant_ids": list(TRACK1_VARIANTS),
                "max_steps": 4,
                "timeout_sec": 180,
            }
        )
    return specs


def _completion_specs() -> list[dict[str, Any]]:
    return [
        {
            "eval_id": "extract_moves_from_video_repaired_closure",
            "track": "completion",
            "benchmark_class": "terminalbench_repaired_closure",
            "task_id": "extract-moves-from-video",
            "task_prompt": (
                "Use the local mirrored /app/video.mp4 instead of any remote download. "
                "Transcribe the player moves into /app/solution.txt, one move per line, and only close after the file exists."
            ),
            "workspace_seed": "extract_moves",
            "variant_ids": list(TRACK2_VARIANTS),
            "max_steps": 6,
            "timeout_sec": 240,
        },
        {
            "eval_id": "tb_style_partial_progress_false_completion_v1",
            "track": "completion",
            "benchmark_class": "phase65_completion_partial_progress",
            "task_id": "tb_style_partial_progress_false_completion_v1",
            "task_prompt": (
                "Read /app/notes/amounts.json, compute the total, and write /app/final/report.json "
                "with exactly {\"status\": \"complete\", \"total\": 50}. Only close after that file exists, and state the path plus the total."
            ),
            "workspace_seed": "simple_files",
            "workspace_files": {
                "/notes/amounts.json": json.dumps({"values": [17, 25, 8]}, indent=2, sort_keys=True),
                "/final/.keep": "",
            },
            "artifact_relpath": "final/report.json",
            "expected_payload": {"status": "complete", "total": 50},
            "variant_ids": list(TRACK2_VARIANTS),
            "max_steps": 4,
            "timeout_sec": 120,
        },
        {
            "eval_id": "tb_style_verifier_fail_then_repair_v1",
            "track": "completion",
            "benchmark_class": "phase65_completion_verifier_repair",
            "task_id": "tb_style_verifier_fail_then_repair_v1",
            "task_prompt": (
                "Run /app/verify.sh, repair /app/output.txt until the verifier passes, rerun the verifier, and then close."
            ),
            "workspace_seed": "simple_files",
            "workspace_files": {
                "/output.txt": "status=partial\n",
                "/verify.sh": "#!/bin/bash\nif [ \"$(cat /app/output.txt)\" = \"status=complete\" ]; then echo PASS; exit 0; fi\necho FAIL\nexit 1\n",
            },
            "verifier_relpath": "verify.sh",
            "variant_ids": list(TRACK2_VARIANTS),
            "max_steps": 4,
            "timeout_sec": 120,
        },
    ]


def _context_specs() -> list[dict[str, Any]]:
    specs = []
    rows = list(csv.DictReader((CONTEXTBENCH_ROOT / "data/Verified.csv").read_text(encoding="utf-8").splitlines()))[:4]
    csv_text = (CONTEXTBENCH_ROOT / "data/Verified.csv").read_text(encoding="utf-8")
    for index, row in enumerate(rows):
        specs.append(
            {
                "eval_id": f"contextbench_verified_{index:02d}",
                "track": "context",
                "benchmark_class": "contextbench",
                "task_id": row["instance_id"],
                "task_prompt": (
                    "Read /contextbench/Verified.csv and answer for the requested row only. "
                    "Return a JSON object with exactly these keys: original_inst_id, language, status, "
                    "gold_context_length, commit, repo_or_file_family."
                ),
                "workspace_seed": "simple_files",
                "workspace_files": {
                    "/contextbench/Verified.csv": csv_text,
                    "/contextbench/request.json": json.dumps(row, indent=2, sort_keys=True),
                },
                "grade_row": row,
                "variant_ids": list(TRACK3_VARIANTS),
                "max_steps": 4,
                "timeout_sec": 120,
            }
        )
    rows = [
        json.loads(line)
        for line in (LETTA_ROOT / "datasets/filesystem_code.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    selected = []
    quotas = {"easy": 2, "medium": 2, "hard": 2}
    for index, row in enumerate(rows):
        difficulty = row.get("agent_args", {}).get("extra", {}).get("difficulty")
        if quotas.get(difficulty, 0) > 0:
            selected.append((index, difficulty, row))
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
                "track": "context",
                "benchmark_class": "letta_context_bench",
                "task_id": f"filesystem_code_{index:03d}",
                "task_prompt": row["input"].replace("{pwd}", "/letta/filesystem") + "\nReturn one direct answer.",
                "workspace_seed": "simple_files",
                "workspace_files": files,
                "ground_truth": row["ground_truth"],
                "variant_ids": list(TRACK3_VARIANTS),
                "max_steps": 4,
                "timeout_sec": 120,
            }
        )
    specs.append(
        {
            "eval_id": "custom_long_context_handoff_aggregation_v1",
            "track": "context",
            "benchmark_class": "phase65_context_work_pocket",
            "task_id": "custom_long_context_handoff_aggregation_v1",
            "task_prompt": (
                "Inspect all files under /app/case, compute the combined invoice total, and write /app/artifacts/work_pocket.json "
                "with keys verified_total, verification_status, and evidence_paths. In the final answer, state the total and the artifact path."
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
            "variant_ids": list(TRACK3_VARIANTS),
            "max_steps": 4,
            "timeout_sec": 120,
        }
    )
    return specs


def _regression_specs(best_candidate: str) -> list[dict[str, Any]]:
    variants = [CONTROL, INCUMBENT, best_candidate]
    return [
        {
            "eval_id": "terminalbench_public_fix-git",
            "track": "terminalbench",
            "benchmark_class": "terminalbench_public_regression",
            "task_id": "fix-git",
            "task_prompt": (
                "Recover the missing site changes into the local workspace. The required file state lives under /app/resources/patch_files "
                "and the working tree lives under /app/personal-site."
            ),
            "workspace_seed": "fix_git",
            "variant_ids": variants,
            "max_steps": 6,
            "timeout_sec": 180,
        },
        {
            "eval_id": "terminalbench_public_regex-log",
            "track": "terminalbench",
            "benchmark_class": "terminalbench_public_regression",
            "task_id": "regex-log",
            "task_prompt": (
                "Inspect /app/log.txt and write the required regex to /app/regex.txt. "
                "The regex must match only the last valid YYYY-MM-DD on lines that contain a valid IPv4 address."
            ),
            "workspace_seed": "regex_log",
            "variant_ids": variants,
            "max_steps": 4,
            "timeout_sec": 120,
        },
        {
            "eval_id": "terminalbench_public_financial-document-processor",
            "track": "terminalbench",
            "benchmark_class": "terminalbench_public_regression",
            "task_id": "financial-document-processor",
            "task_prompt": (
                "Process the files under /app/documents into /app/invoices and /app/other, then write /app/invoices/summary.csv "
                "with the required totals. Only close after /app/documents is empty."
            ),
            "workspace_seed": "financial_docs",
            "variant_ids": variants,
            "max_steps": 6,
            "timeout_sec": 240,
        },
    ]


def _preflight(specs: list[dict[str, Any]], *, include_terminalbench_regression: bool) -> dict[str, Any]:
    blockers = []
    docker = _run(["docker", "info"], cwd=Path.cwd(), timeout=60)
    docker_available = docker["returncode"] == 0 and "Server:" in docker["stdout"]
    for path, label in (
        (MEASUREMENT_REPAIR_REPORT, "measurement_repair_report_missing"),
        (MEASUREMENT_FOLLOWUP_REPORT, "measurement_followup_report_missing"),
        (CONTEXTBENCH_ROOT / "data/Verified.csv", "contextbench_verified_missing"),
        (LETTA_ROOT / "datasets/filesystem_code.jsonl", "letta_dataset_missing"),
        (BFCL_PATH, "bfcl_mirror_missing"),
        (EXTRACT_VIDEO_MIRROR, "extract_video_mirror_missing"),
    ):
        if not path.exists():
            blockers.append(label)
    if not blockers:
        if json.loads(MEASUREMENT_REPAIR_REPORT.read_text(encoding="utf-8"))["selected_recommendation"] != "measurement_repair_completed_resume_phase65_board":
            blockers.append("measurement_repair_not_certified")
        if json.loads(MEASUREMENT_FOLLOWUP_REPORT.read_text(encoding="utf-8"))["status"] != "pass":
            blockers.append("measurement_followup_not_certified")
    if letta_preflight()["status"] != "pass":
        blockers.append("letta_preflight_failed")
    try:
        make_azure_gpt53_codex_route_from_env()
    except Exception as exc:
        blockers.append(f"model_route_not_ready:{exc}")
    planned_model_runs = sum(len(spec["variant_ids"]) for spec in specs) + (9 if include_terminalbench_regression else 0)
    if planned_model_runs > 40:
        blockers.append("hard_model_backed_cap_projected")
    return {
        "mission_id": MISSION_ID,
        "status": "pass" if not blockers else "blocked",
        "blockers": blockers,
        "docker_available": docker_available,
        "planned_model_backed_runs": planned_model_runs,
        "planned_local_deterministic_runs": 0,
        "authority": _authority(),
        "measurement_contract_ready": not any("measurement_" in item for item in blockers),
    }


def _route_matrix() -> dict[str, Any]:
    baseline = build_packet04_route_manifest(BASELINE_VARIANT_ID, scope=PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE)
    rows = []
    blockers = []
    signatures: dict[tuple[tuple[str, str], ...], str] = {}
    for variant in ALL_VARIANTS:
        try:
            manifest = build_packet04_route_manifest(variant, scope=PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE)
            load_runtime_callables(manifest)
            validate_independent_candidate_routing(candidate_manifest=manifest, baseline_manifest=baseline)
            changed_rows = [row for row in manifest["routed_modules"] if row.get("claimed_changed_surface")]
            signature = tuple(sorted((row["runtime_key"], row["module_import_path"]) for row in changed_rows))
            duplicate_of = signatures.get(signature)
            if duplicate_of is None:
                signatures[signature] = variant
            else:
                blockers.append({"variant_id": variant, "error": f"route_duplicate_of:{duplicate_of}"})
            rows.append(
                {
                    "variant_id": variant,
                    "route_valid": True,
                    "changed_runtime_keys": sorted(row["runtime_key"] for row in changed_rows),
                    "changed_surface_signature": list(signature),
                    "route_manifest_fingerprint": manifest["route_manifest_fingerprint"],
                    "routed_modules": manifest["routed_modules"],
                }
            )
        except Exception as exc:
            rows.append({"variant_id": variant, "route_valid": False, "error": str(exc)})
            blockers.append({"variant_id": variant, "error": str(exc)})
    return {"mission_id": MISSION_ID, "status": "pass" if not blockers else "blocked", "routes": rows, "blockers": blockers}


def _variant_doctrine_matrix(route: dict[str, Any]) -> dict[str, Any]:
    rows = []
    blockers = []
    for row in route["routes"]:
        variant = row["variant_id"]
        changed = set(row.get("changed_runtime_keys", []))
        required = ROUTE_REQUIREMENTS.get(variant, set())
        doctrine_present = row.get("route_valid", False)
        mechanism_pass = required <= changed if required else True
        if not doctrine_present or not mechanism_pass:
            blockers.append(
                {
                    "variant_id": variant,
                    "error": "doctrine_or_mechanism_contract_failed",
                    "required_runtime_keys": sorted(required),
                    "changed_runtime_keys": sorted(changed),
                }
            )
        rows.append(
            {
                "variant_id": variant,
                "doctrine_present": doctrine_present,
                "required_runtime_keys": sorted(required),
                "changed_runtime_keys": sorted(changed),
                "mechanism_bearing": mechanism_pass,
                "intended_lane": _variant_lane(variant),
            }
        )
    return {"mission_id": MISSION_ID, "status": "pass" if not blockers else "blocked", "rows": rows, "blockers": blockers}


def _variant_lane(variant: str) -> str:
    if variant in TRACK1_VARIANTS:
        return "bfcl"
    if variant in TRACK2_VARIANTS:
        return "completion"
    if variant in TRACK3_VARIANTS:
        return "context"
    return "shared"


def _run_with_retry(out: Path, spec: dict[str, Any], variant: str, *, plan_index: int) -> tuple[dict[str, Any], dict[str, Any]]:
    last_record = None
    last_trace = None
    for attempt in range(2):
        record, trace = _run_one(out, spec, variant, attempt=attempt, plan_index=plan_index)
        last_record, last_trace = record, trace
        if not record["invalid_infrastructure_failure"]:
            break
    return last_record, last_trace


def _run_one(
    out: Path,
    spec: dict[str, Any],
    variant: str,
    *,
    attempt: int,
    plan_index: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    run_started = perf_counter()
    run_id = f"{MISSION_ID}__{spec['eval_id']}__{variant}__r{attempt}"
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
        task_prompt=spec["task_prompt"] + "\nUse shell inspection and edits where needed. Do not close early.",
        benchmark_family=spec["benchmark_class"],
        case_id=spec["eval_id"],
        seed_id=variant,
        model_route=make_azure_gpt53_codex_route_from_env(),
        model_client_kwargs={"timeout_sec": spec["timeout_sec"], "max_retries": 1},
        max_steps=spec["max_steps"],
        timeout_sec=spec["timeout_sec"],
        cwd=workspace,
        route_manifest=build_packet04_route_manifest(variant, scope=PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE),
        enforce_packet04_route_contract=True,
    )
    model_exec_sec = perf_counter() - model_exec_started
    grade_started = perf_counter()
    grade = grade_phase65_spec(spec=spec, result=result, workspace=workspace)
    grade_sec = perf_counter() - grade_started
    report_started = perf_counter()
    invalid = _is_invalid_infrastructure(run_dir)
    usage = _usage(result)
    runtime_timing = result.get("runtime_timing", {}) if isinstance(result.get("runtime_timing"), dict) else {}
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
        "track": spec["track"],
        "benchmark_class": spec["benchmark_class"],
        "task_id": spec["task_id"],
        "variant_id": variant,
        "attempt": attempt,
        "plan_index": plan_index,
        "model_backed": True,
        "run_dir": str(run_dir),
        "trace_ref": str(run_dir / "run_events.jsonl"),
        "score_summary": {"final_verdict": "invalid" if invalid else grade["verdict"], "grade": grade},
        "token_and_cost_summary": usage,
        "governed_terminal_status": "invalid" if invalid else "valid",
        "invalid_infrastructure_failure": invalid,
        "reason_codes": ["invalid_infrastructure_failure"] if invalid else grade.get("reason_codes", []),
        "authority": _authority(),
        "timing_summary": {
            "run_wall_sec": perf_counter() - run_started,
            "workspace_seed_sec": seed_sec,
            "model_and_tool_loop_sec": model_exec_sec,
            "model_backed_latency_sec": float(runtime_timing.get("model_backed_latency_sec", 0.0) or 0.0),
            "docker_overhead_sec": float(runtime_timing.get("sandbox_total_sec", 0.0) or 0.0),
            "tool_exec_sec": float(runtime_timing.get("tool_exec_sec", 0.0) or 0.0),
            "verification_sec": float(runtime_timing.get("verification_sec", 0.0) or 0.0),
            "grading_overhead_sec": grade_sec,
            "reporting_overhead_sec": float(runtime_timing.get("grading_and_report_sec", 0.0) or 0.0),
            "orchestration_overhead_sec": orchestration_overhead_sec,
            "model_call_count": int(runtime_timing.get("model_call_count", 0) or 0),
            "tool_call_count": int(runtime_timing.get("tool_call_count", 0) or 0),
        },
    }
    _patch_score(run_dir, grade)
    trace = {
        "mission_id": MISSION_ID,
        "run_id": run_id,
        "eval_id": spec["eval_id"],
        "track": spec["track"],
        "variant_id": variant,
        "attempt": attempt,
        "plan_index": plan_index,
        "trace_ref": record["trace_ref"],
        "invalid_infrastructure_failure": invalid,
    }
    report_sec = perf_counter() - report_started
    record["timing_summary"]["reporting_overhead_sec"] += report_sec
    return record, trace


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
    if seed == "regex_log":
        contract = load_regex_log_contract(str(TERMINALBENCH_ROOT / "official_tasks/regex-log"))
        (workspace / "log.txt").write_text("\n".join(contract["sample_logs"]) + "\n", encoding="utf-8")
        return
    if seed == "financial_docs":
        documents_root = TERMINALBENCH_ROOT / "official_tasks/financial-document-processor/environment/documents"
        shutil.copytree(documents_root, workspace / "documents")
        return
    if seed == "fix_git":
        resources = TERMINALBENCH_ROOT / "official_tasks/fix-git/environment/resources/patch_files"
        _copy_text(resources / "about.md", workspace / "resources/patch_files/about.md")
        _copy_text(resources / "default.html", workspace / "resources/patch_files/default.html")
        _copy_text(resources / "about.md", workspace / "personal-site/_includes/about.md")
        _copy_text(resources / "default.html", workspace / "personal-site/_layouts/default.html")
        (workspace / "personal-site/_includes/about.md").write_text("broken about page\n", encoding="utf-8")
        (workspace / "personal-site/_layouts/default.html").write_text("<html>broken</html>\n", encoding="utf-8")
        return
    raise ValueError(f"unsupported_workspace_seed:{seed}")


def _copy_text(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")


def _is_invalid_infrastructure(run_dir: Path) -> bool:
    events_path = run_dir / "run_events.jsonl"
    if not events_path.exists():
        return False
    for line in events_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        if event.get("event_type") == "model_client_error":
            return True
    return False


def _enforce_caps(records: list[dict[str, Any]]) -> None:
    model_runs = sum(1 for row in records if row["model_backed"])
    cost = sum(float(row["token_and_cost_summary"].get("usd", 0.0) or 0.0) for row in records)
    if model_runs > 40:
        raise SystemExit("hard_model_backed_cap_exceeded")
    if cost > 35:
        raise SystemExit("hard_cost_cap_exceeded")


def _select_best_repaired_candidate(records: list[dict[str, Any]]) -> str:
    variants = [variant for variant in ALL_VARIANTS if variant not in {CONTROL, INCUMBENT}]
    incumbent_by_eval = {
        row["eval_id"]: row["score_summary"]["final_verdict"]
        for row in records
        if row["variant_id"] == INCUMBENT and row["track"] in {"bfcl", "completion", "context"}
    }
    scored = []
    for variant in variants:
        subset = [row for row in records if row["variant_id"] == variant and row["track"] in {"bfcl", "completion", "context"}]
        wins = sum(
            1
            for row in subset
            if row["score_summary"]["final_verdict"] == "pass" and incumbent_by_eval.get(row["eval_id"]) != "pass"
        )
        passes = sum(1 for row in subset if row["score_summary"]["final_verdict"] == "pass")
        scored.append((wins, passes, -len(subset), variant))
    return max(scored)[-1]


def _write_reports(
    out: Path,
    *,
    records: list[dict[str, Any]],
    traces: list[dict[str, Any]],
    preflight: dict[str, Any],
    route: dict[str, Any],
    doctrine: dict[str, Any],
    best_regression_candidate: str | None,
    worker_cap: int,
) -> dict[str, Any]:
    _write_jsonl(out / "phase65_resumed_result_records.jsonl", records)
    score = _score(records, best_regression_candidate)
    score["preflight"] = preflight
    score["worker_cap"] = worker_cap
    score["selected_recommendation"] = _recommendation(score)
    runtime_profile = _runtime_profile(records, worker_cap=worker_cap)
    for name, payload in {
        "phase65_resumed_score_envelope.json": score,
        "phase65_resumed_bfcl_report.json": _track_report(records, "bfcl"),
        "phase65_resumed_completion_report.json": _track_report(records, "completion"),
        "phase65_resumed_context_report.json": _track_report(records, "context"),
        "phase65_resumed_terminalbench_report.json": _track_report(records, "terminalbench"),
        "phase65_resumed_trace_report.json": {
            "mission_id": MISSION_ID,
            "run_count": len(traces),
            "traces": traces,
            "best_regression_candidate": best_regression_candidate,
        },
        "phase65_resumed_failure_source_report.json": _failure_report(records),
        "phase65_resumed_cost_report.json": _cost_report(records),
        "phase65_resumed_runtime_profile.json": runtime_profile,
    }.items():
        _write_json(out / name, payload)
    _write_text(out / "phase65_resumed_handoff.md", _handoff(out, score, best_regression_candidate))
    ledger = _ledger(out, score, best_regression_candidate)
    _record_ledger(ledger)
    _write_text(out / "RAW_LEDGER_UPDATE", ledger)
    return {
        "output_dir": str(out),
        "run_count": len(records),
        "model_backed_runs": score["model_backed_runs"],
        "selected_recommendation": score["selected_recommendation"],
    }


def _score(records: list[dict[str, Any]], best_regression_candidate: str | None) -> dict[str, Any]:
    track_winners = {track: _track_winner(records, track) for track in ("bfcl", "completion", "context", "terminalbench")}
    dominant = _dominant_blocker(records)
    best_repaired = _select_best_repaired_candidate(records)
    certified_beats_incumbent = any(
        winner["winner_variant"] not in {None, CONTROL, INCUMBENT}
        and winner["winner_passes"] > winner["incumbent_passes"]
        for winner in track_winners.values()
        if winner["track"] in {"bfcl", "completion", "context"}
    )
    next_loop = None
    if dominant != "incumbent still best without enough repair uplift":
        next_loop = dominant.split("/", 1)[0]
    return {
        "mission_id": MISSION_ID,
        "run_count": len(records),
        "model_backed_runs": sum(1 for row in records if row["model_backed"]),
        "local_deterministic_runs": 0,
        "invalid_run_count": sum(1 for row in records if row["invalid_infrastructure_failure"]),
        "track_winners": track_winners,
        "best_repaired_candidate": best_repaired,
        "best_regression_candidate": best_regression_candidate,
        "final_questions": {
            "dominant_remaining_blocker": dominant,
            "best_repaired_mechanism_branch": best_repaired,
            "any_repaired_branch_beat_incumbent_on_certified_lanes": certified_beats_incumbent,
            "single_family_autoresearch_loop": next_loop,
        },
    }


def _track_winner(records: list[dict[str, Any]], track: str) -> dict[str, Any]:
    subset = [row for row in records if row["track"] == track]
    variants = sorted({row["variant_id"] for row in subset})
    scores = {
        variant: sum(1 for row in subset if row["variant_id"] == variant and row["score_summary"]["final_verdict"] == "pass")
        for variant in variants
    }
    if not scores:
        return {"track": track, "winner_variant": None, "winner_passes": 0, "incumbent_passes": 0}
    winner_variant = max(scores.items(), key=lambda item: (item[1], item[0]))[0]
    return {
        "track": track,
        "winner_variant": winner_variant,
        "winner_passes": scores[winner_variant],
        "incumbent_passes": scores.get(INCUMBENT, 0),
        "scores": scores,
    }


def _dominant_blocker(records: list[dict[str, Any]]) -> str:
    if not _any_repaired_lane_win(records):
        return "incumbent still best without enough repair uplift"
    pass_rates = {
        "BFCL/tool-call completeness": _best_repaired_pass_rate(records, "bfcl"),
        "completion/closure": _best_repaired_pass_rate(records, "completion"),
        "context/workflow": _best_repaired_pass_rate(records, "context"),
    }
    return min(pass_rates.items(), key=lambda item: (item[1], item[0]))[0]


def _any_repaired_lane_win(records: list[dict[str, Any]]) -> bool:
    for track in ("bfcl", "completion", "context"):
        winner = _track_winner(records, track)
        if winner["winner_variant"] not in {None, CONTROL, INCUMBENT} and winner["winner_passes"] > winner["incumbent_passes"]:
            return True
    return False


def _best_repaired_pass_rate(records: list[dict[str, Any]], track: str) -> float:
    subset = [row for row in records if row["track"] == track]
    eval_ids = {row["eval_id"] for row in subset}
    if not eval_ids:
        return 0.0
    best = 0
    for variant in {row["variant_id"] for row in subset if row["variant_id"] not in {CONTROL, INCUMBENT}}:
        passes = sum(1 for row in subset if row["variant_id"] == variant and row["score_summary"]["final_verdict"] == "pass")
        best = max(best, passes)
    return best / len(eval_ids)


def _recommendation(score: dict[str, Any]) -> str:
    if score["invalid_run_count"]:
        return "prefer_spb_01_or_pause_successor"
    blocker = score["final_questions"]["dominant_remaining_blocker"]
    if score["final_questions"]["any_repaired_branch_beat_incumbent_on_certified_lanes"]:
        terminalbench = score["track_winners"]["terminalbench"]
        completion = score["track_winners"]["completion"]
        if (
            terminalbench["winner_variant"] not in {CONTROL, INCUMBENT, None}
            and terminalbench["winner_passes"] >= terminalbench["incumbent_passes"]
            and completion["winner_passes"] > 0
            and completion["winner_passes"] > completion["incumbent_passes"]
        ):
            return "candidate_repaired_and_ready_for_packet07_readiness_review"
    if blocker == "BFCL/tool-call completeness":
        return "candidate_needs_toolcall_repair"
    if blocker == "completion/closure":
        return "candidate_needs_completion_repair"
    if blocker == "context/workflow":
        return "candidate_needs_context_workflow_repair"
    control_passes = score["track_winners"]["terminalbench"]["scores"].get(CONTROL, 0) if score["track_winners"]["terminalbench"].get("scores") else 0
    incumbent_passes = score["track_winners"]["terminalbench"]["scores"].get(INCUMBENT, 0) if score["track_winners"]["terminalbench"].get("scores") else 0
    if control_passes >= incumbent_passes:
        return "prefer_spb_01_or_pause_successor"
    return "incumbent_still_best_run_single_family_autoresearch_loop"


def _track_report(records: list[dict[str, Any]], track: str) -> dict[str, Any]:
    subset = [row for row in records if row["track"] == track]
    return {
        "mission_id": MISSION_ID,
        "track": track,
        "run_count": len(subset),
        "winner": _track_winner(records, track),
        "records": subset,
    }


def _failure_report(records: list[dict[str, Any]]) -> dict[str, Any]:
    invalid = [row for row in records if row["invalid_infrastructure_failure"]]
    behavior = [row for row in records if not row["invalid_infrastructure_failure"] and row["score_summary"]["final_verdict"] == "fail"]
    return {
        "mission_id": MISSION_ID,
        "invalid_infrastructure_failures": invalid,
        "behavioral_failures": behavior,
    }


def _cost_report(records: list[dict[str, Any]]) -> dict[str, Any]:
    total_tokens = sum(int(row["token_and_cost_summary"].get("total_tokens", 0) or 0) for row in records)
    usd = sum(float(row["token_and_cost_summary"].get("usd", 0.0) or 0.0) for row in records)
    if usd <= 15:
        cap_status = "below_soft_cap"
    elif usd <= 35:
        cap_status = "below_hard_cap"
    else:
        cap_status = "hard_cap_exceeded"
    return {
        "mission_id": MISSION_ID,
        "budget_caps": {
            "target_model_backed_runs": [0, 30],
            "hard_model_backed_cap": 40,
            "local_deterministic_cap": 120,
            "soft_cost_cap_usd": 15,
            "hard_cost_cap_usd": 35,
        },
        "cap_status": cap_status,
        "total": {"total_tokens": total_tokens, "usd": usd},
    }


def _runtime_profile(records: list[dict[str, Any]], *, worker_cap: int) -> dict[str, Any]:
    model_runs = [row for row in records if row.get("model_backed")]
    total_wall_sec = sum(float(row.get("timing_summary", {}).get("run_wall_sec", 0.0) or 0.0) for row in model_runs)
    orchestration_sec = sum(float(row.get("timing_summary", {}).get("orchestration_overhead_sec", 0.0) or 0.0) for row in model_runs)
    model_sec = sum(float(row.get("timing_summary", {}).get("model_backed_latency_sec", 0.0) or 0.0) for row in model_runs)
    grading_reporting_sec = sum(
        float(row.get("timing_summary", {}).get("grading_overhead_sec", 0.0) or 0.0)
        + float(row.get("timing_summary", {}).get("reporting_overhead_sec", 0.0) or 0.0)
        for row in model_runs
    )
    docker_sec = sum(float(row.get("timing_summary", {}).get("docker_overhead_sec", 0.0) or 0.0) for row in model_runs)
    return {
        "mission_id": MISSION_ID,
        "worker_cap": worker_cap,
        "run_count": len(model_runs),
        "breakdown_sec": {
            "orchestration_overhead_sec": orchestration_sec,
            "model_backed_latency_sec": model_sec,
            "grading_reporting_overhead_sec": grading_reporting_sec,
            "docker_backed_overhead_sec": docker_sec,
            "total_run_wall_sec": total_wall_sec,
        },
    }


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
        "invalid_run_count": 0,
        "worker_cap": worker_cap,
        "selected_recommendation": "prefer_spb_01_or_pause_successor",
        "preflight": preflight,
        "route_matrix": route,
        "variant_doctrine_matrix": doctrine,
    }
    _write_jsonl(out / "phase65_resumed_result_records.jsonl", [])
    for name in (
        "phase65_resumed_score_envelope.json",
        "phase65_resumed_bfcl_report.json",
        "phase65_resumed_completion_report.json",
        "phase65_resumed_context_report.json",
        "phase65_resumed_terminalbench_report.json",
        "phase65_resumed_trace_report.json",
        "phase65_resumed_failure_source_report.json",
        "phase65_resumed_cost_report.json",
        "phase65_resumed_runtime_profile.json",
    ):
        _write_json(out / name, {"mission_id": MISSION_ID, "blocked": True, "execute": execute, "score": score})
    _write_text(out / "phase65_resumed_handoff.md", _handoff(out, score, None))
    ledger = _ledger(out, score, None)
    _record_ledger(ledger)
    _write_text(out / "RAW_LEDGER_UPDATE", ledger)
    return {
        "output_dir": str(out),
        "run_count": 0,
        "model_backed_runs": 0,
        "selected_recommendation": "prefer_spb_01_or_pause_successor",
        "blocked": True,
    }


def _execution_plan(specs: list[dict[str, Any]], worker_cap: int, *, include_terminalbench_regression: bool) -> dict[str, Any]:
    return {
        "mission_id": MISSION_ID,
        "worker_cap": worker_cap,
        "planned_model_backed_runs": sum(len(spec["variant_ids"]) for spec in specs) + (9 if include_terminalbench_regression else 0),
        "terminalbench_regression_enabled": include_terminalbench_regression,
        "track4_candidate_policy": "best_repaired_candidate_from_tracks_1_to_3",
        "specs": [{key: value for key, value in spec.items() if key not in {"workspace_files", "ground_truth", "grade_row"}} for spec in specs],
    }


def _board_manifest(specs: list[dict[str, Any]], *, include_terminalbench_regression: bool) -> dict[str, Any]:
    return {
        "mission_id": MISSION_ID,
        "control": CONTROL,
        "incumbent": INCUMBENT,
        "reduced_scope_variants": list(ALL_VARIANTS),
        "accepted_tracks": {
            "bfcl": len([row for row in specs if row["track"] == "bfcl"]),
            "completion": len([row for row in specs if row["track"] == "completion"]),
            "context": len([row for row in specs if row["track"] == "context"]),
            "terminalbench": 3 if include_terminalbench_regression else 0,
        },
        "eval_ids": [row["eval_id"] for row in specs],
        "authority": _authority(),
    }


def _plan(
    out: Path,
    specs: list[dict[str, Any]],
    preflight: dict[str, Any],
    route: dict[str, Any],
    doctrine: dict[str, Any],
    worker_cap: int,
    *,
    include_terminalbench_regression: bool,
) -> str:
    planned_model_runs = sum(len(spec["variant_ids"]) for spec in specs) + (9 if include_terminalbench_regression else 0)
    return "\n".join(
        [
            "# Phase 6.5 Resumed Plan",
            "",
            f"- mission_id: `{MISSION_ID}`",
            f"- output_root: `{out}`",
            f"- preflight_status: `{preflight['status']}`",
            f"- route_status: `{route['status']}`",
            f"- doctrine_status: `{doctrine['status']}`",
            f"- worker_cap: `{worker_cap}`",
            f"- planned_model_backed_runs: `{planned_model_runs}`",
            f"- terminalbench_regression_enabled: `{include_terminalbench_regression}`",
            "- measurement stack: certified repaired grading only",
            "- board scope: reduced Phase 6.5 only; no Packet 07 movement or benchmark widening",
        ]
    ) + "\n"


def _handoff(out: Path, score: dict[str, Any], best_regression_candidate: str | None) -> str:
    questions = score.get("final_questions", {})
    return "\n".join(
        [
            "# Phase 6.5 Resumed Handoff",
            "",
            f"- mission_id: `{MISSION_ID}`",
            f"- output_root: `{out}`",
            f"- run_count: `{score.get('run_count', 0)}`",
            f"- model_backed_runs: `{score.get('model_backed_runs', 0)}`",
            f"- invalid_run_count: `{score.get('invalid_run_count', 0)}`",
            f"- best_regression_candidate: `{best_regression_candidate}`",
            f"- dominant_remaining_blocker: `{questions.get('dominant_remaining_blocker')}`",
            f"- best_repaired_mechanism_branch: `{questions.get('best_repaired_mechanism_branch')}`",
            f"- repaired_branch_beat_incumbent_on_certified_lanes: `{questions.get('any_repaired_branch_beat_incumbent_on_certified_lanes')}`",
            f"- single_family_autoresearch_loop: `{questions.get('single_family_autoresearch_loop')}`",
            f"- final_recommendation: `{score.get('selected_recommendation')}`",
        ]
    ) + "\n"


def _ledger(out: Path, score: dict[str, Any], best_regression_candidate: str | None) -> str:
    questions = score.get("final_questions", {})
    return "\n".join(
        [
            "RAW_LEDGER_UPDATE",
            "- actor: codex",
            "- task: successor Phase 6.5 reduced resumed board",
            "- event_type: experiment",
            f"- summary: Executed or preflighted the reduced resumed Phase 6.5 board with recommendation `{score.get('selected_recommendation')}`.",
            f"- observations: run_count `{score.get('run_count', 0)}`; model_backed_runs `{score.get('model_backed_runs', 0)}`; invalid_run_count `{score.get('invalid_run_count', 0)}`; best_regression_candidate `{best_regression_candidate}`.",
            f"- inference: Dominant remaining blocker is `{questions.get('dominant_remaining_blocker')}` and best repaired mechanism branch is `{questions.get('best_repaired_mechanism_branch')}` under the certified reduced board.",
            f"- evidence_paths: {out / 'phase65_resumed_board_manifest.json'}; {out / 'phase65_resumed_score_envelope.json'}; {out / 'phase65_resumed_handoff.md'}",
            "- affected_components: reduced Phase 6.5 board runner; Phase 6 route admission; strict BFCL grading; completion/context benchmark fixtures",
            "- decision_change: Packet 07 remains closed and the board stayed within the reduced Phase 6.5 scope",
            "- unresolved_questions: Whether the next iteration should focus on BFCL/tool-call completeness, completion/closure, context/workflow, or pause behind the incumbent.",
            "- confidence: medium",
            "- commit_message: HOLD - phase65 resumed board artifacts",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--no-execute", action="store_true")
    parser.add_argument("--max-workers", type=int, default=1)
    parser.add_argument("--tracks", nargs="*", choices=("bfcl", "completion", "context"), default=None)
    parser.add_argument("--max-specs-per-track", type=int, default=None)
    parser.add_argument("--max-variants-per-spec", type=int, default=None)
    args = parser.parse_args(argv)
    print(
        json.dumps(
            launch_phase65_resumed_board(
                output_dir=args.output_dir,
                execute=not args.no_execute,
                max_workers=args.max_workers,
                selected_tracks=tuple(args.tracks) if args.tracks else None,
                max_specs_per_track=args.max_specs_per_track,
                max_variants_per_spec=args.max_variants_per_spec,
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
