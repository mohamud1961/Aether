"""Execute Packet 07 Cycle 0 mixed confirmation board."""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from time import perf_counter
from typing import Any
from urllib.parse import urlparse

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
from runner.phase65_measurement_contracts import (
    load_regex_log_contract,
)
from runner.phase65_measurement_grading import grade_phase65_spec
from runner.successor_phase65_context_followup import _build_route_manifest as build_context_followup_merged_manifest
from runner.successor_phase65_resumed_board import EXTRACT_VIDEO_MIRROR
from runner.successor_phase6_corrective_rerun import (
    BFCL_PATH,
    CONTEXTBENCH_ROOT,
    LETTA_ROOT,
    PRICE,
    TERMINALBENCH_ROOT,
    _authority,
    _record_ledger,
    _run,
    _write_json,
    _write_jsonl,
    _write_text,
)

MISSION_ID = "packet07_cycle0_mixed_confirmation"
DEFAULT_OUTPUT_DIR = Path(
    "tracking/collab/stage_03_execution_planning/packets/packet_06_paired_combo_variants/"
    "runs/2026-05-08_packet07_cycle0_mixed_confirmation"
)
SYNTH_ROOT = Path(
    "tracking/collab/stage_03_execution_planning/packets/packet_06_paired_combo_variants/synthesis"
)
LOCKED_EVAL_ROWS_PATH = SYNTH_ROOT / "packet07_cycle0_eval_rows_2026_05_08.json"
LOCKED_ROUTE_MATRIX_PATH = SYNTH_ROOT / "packet07_cycle0_route_matrix_2026_05_08.json"
LOCKED_EVAL_QUALITY_PATH = SYNTH_ROOT / "packet07_cycle0_eval_quality_report_2026_05_08.md"
LOCKED_MEASUREMENT_POLICY_PATH = SYNTH_ROOT / "packet07_measurement_policy_2026_05_08.md"
LOCKED_INFRA_POLICY_PATH = SYNTH_ROOT / "packet07_infra_validity_policy_2026_05_08.md"

ROUTES = (
    "spb_01",
    "spb_tooling_seed_plus_receipt_and_completion_01",
    "candidate_plus_path_normalized_verifier_repair_projection_01",
    "verified_work_pocket_handoff_hybrid_01",
    "candidate_plus_context_followup_merged_01",
)

RECOMMENDATIONS = (
    "cycle1_target_completion",
    "cycle1_target_context",
    "cycle1_target_bfcl_tooling",
    "cycle1_target_mixed",
    "measurement_blocked",
    "infra_blocked",
    "no_valid_signal",
)

LONG_ROW_EVAL_ID = "tb_style_long_horizon_artifact_repair_and_verify_v1"
DEFAULT_MAX_WORKERS = 2


def launch_packet07_cycle0(
    *,
    output_dir: str | Path,
    execute: bool = True,
    max_workers: int = DEFAULT_MAX_WORKERS,
) -> dict[str, Any]:
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)

    locked_eval_rows = _read_json(LOCKED_EVAL_ROWS_PATH)
    locked_route_matrix = _read_json(LOCKED_ROUTE_MATRIX_PATH)
    specs = _build_specs_from_locked_rows(locked_eval_rows)

    eval_quality_result = _evaluate_long_row_gate(LOCKED_EVAL_QUALITY_PATH)
    route_check = _route_availability_check(locked_route_matrix)
    eval_row_check = _eval_row_availability_check(locked_eval_rows, specs)
    grader_check = _grader_availability_check(specs)
    adapter_check = _adapter_validity_check(specs)
    exec_mode = _execution_mode_disclosure()
    network = _azure_dns_network_preflight()
    docker = _docker_or_fallback_preflight(specs)

    preflight = {
        "mission_id": MISSION_ID,
        "checks": {
            "route_availability": route_check,
            "eval_row_availability": eval_row_check,
            "grader_availability": grader_check,
            "adapter_validity": adapter_check,
            "execution_mode_disclosure": exec_mode,
            "azure_dns_network_preflight": network,
            "docker_or_fallback": docker,
        },
    }
    blockers = _collect_preflight_blockers(preflight)
    preflight["status"] = "pass" if not blockers else "blocked"
    preflight["blockers"] = blockers
    preflight["planned_model_backed_runs"] = len(specs) * len(ROUTES)
    preflight["authority"] = _authority()

    _write_json(out / "packet07_cycle0_eval_quality_result.json", eval_quality_result)

    if not execute or preflight["status"] != "pass":
        return _write_blocked_artifacts(
            out,
            preflight=preflight,
            eval_quality_result=eval_quality_result,
            locked_eval_rows=locked_eval_rows,
        )

    records, traces = _execute_board(
        out=out,
        specs=specs,
        max_workers=_resolve_worker_cap(max_workers),
    )
    return _write_success_artifacts(
        out=out,
        records=records,
        traces=traces,
        preflight=preflight,
        eval_quality_result=eval_quality_result,
        locked_eval_rows=locked_eval_rows,
    )


def _build_specs_from_locked_rows(locked_eval_rows: dict[str, Any]) -> list[dict[str, Any]]:
    rows = locked_eval_rows.get("model_backed_eval_rows", [])
    if not isinstance(rows, list):
        raise ValueError("locked eval rows missing model_backed_eval_rows")
    specs_by_eval = _spec_library()
    specs: list[dict[str, Any]] = []
    for row in rows:
        eval_id = str(row["eval_id"])
        if eval_id not in specs_by_eval:
            raise ValueError(f"unsupported_locked_eval:{eval_id}")
        spec = dict(specs_by_eval[eval_id])
        spec["lane"] = str(row["lane"])
        spec["admission_level"] = str(row.get("admission_level", "certified"))
        spec["failure_target"] = str(row.get("failure_target", ""))
        spec["positive_capability_target"] = str(row.get("positive_capability_target", ""))
        spec["score_interpretation_rule"] = row.get("score_interpretation_rule")
        spec["variant_ids"] = list(ROUTES)
        specs.append(spec)
    return specs


def _spec_library() -> dict[str, dict[str, Any]]:
    specs: dict[str, dict[str, Any]] = {}
    specs.update({row["eval_id"]: row for row in _completion_specs()})
    specs.update({row["eval_id"]: row for row in _context_specs()})
    specs.update({row["eval_id"]: row for row in _bfcl_specs()})
    specs.update({row["eval_id"]: row for row in _terminalbench_specs()})
    specs[LONG_ROW_EVAL_ID] = _long_horizon_spec()
    return specs


def _completion_specs() -> list[dict[str, Any]]:
    return [
        {
            "eval_id": "tb_style_partial_progress_false_completion_v1",
            "benchmark_class": "phase65_completion_partial_progress",
            "task_id": "tb_style_partial_progress_false_completion_v1",
            "task_prompt": (
                "Read /app/notes/amounts.json, compute the total, and write /app/final/report.json "
                "with exactly {\"status\": \"complete\", \"total\": 50}. Only close after the file exists "
                "and include both the artifact path and total in the final response."
            ),
            "workspace_seed": "simple_files",
            "workspace_files": {
                "/notes/amounts.json": json.dumps({"values": [17, 25, 8]}, indent=2, sort_keys=True),
                "/final/.keep": "",
            },
            "artifact_relpath": "final/report.json",
            "expected_payload": {"status": "complete", "total": 50},
            "max_steps": 4,
            "timeout_sec": 120,
        },
        {
            "eval_id": "tb_style_verifier_fail_then_repair_v1",
            "benchmark_class": "phase65_completion_verifier_repair",
            "task_id": "tb_style_verifier_fail_then_repair_v1",
            "task_prompt": (
                "Run /app/verify.sh, repair /app/output.txt until the verifier passes, rerun the verifier, "
                "and then close with explicit rerun confirmation."
            ),
            "workspace_seed": "simple_files",
            "workspace_files": {
                "/output.txt": "status=partial\n",
                "/verify.sh": (
                    "#!/bin/bash\n"
                    "if [ \"$(cat /app/output.txt)\" = \"status=complete\" ]; then echo PASS; exit 0; fi\n"
                    "echo FAIL\n"
                    "exit 1\n"
                ),
            },
            "verifier_relpath": "verify.sh",
            "max_steps": 4,
            "timeout_sec": 120,
        },
        {
            "eval_id": "extract_moves_from_video_repaired_closure",
            "benchmark_class": "terminalbench_repaired_closure",
            "task_id": "extract-moves-from-video",
            "task_prompt": (
                "Use local /app/video.mp4 only. Transcribe player moves to /app/solution.txt one move per line "
                "and close only after solution.txt exists and verifier-style confidence checks are complete."
            ),
            "workspace_seed": "extract_moves",
            "max_steps": 6,
            "timeout_sec": 240,
        },
    ]


def _context_specs() -> list[dict[str, Any]]:
    specs = []
    verified_csv_path = CONTEXTBENCH_ROOT / "data/Verified.csv"
    verified_csv = verified_csv_path.read_text(encoding="utf-8")
    rows = list(csv.DictReader(verified_csv.splitlines()))
    for index in (0, 3):
        row = rows[index]
        specs.append(
            {
                "eval_id": f"contextbench_verified_{index:02d}",
                "benchmark_class": "contextbench",
                "task_id": row["instance_id"],
                "task_prompt": (
                    "Read /contextbench/Verified.csv and answer for the requested row only. "
                    "Return a JSON object with exactly these keys: original_inst_id, language, status, "
                    "gold_context_length, commit, repo_or_file_family."
                ),
                "workspace_seed": "simple_files",
                "workspace_files": {
                    "/contextbench/Verified.csv": verified_csv,
                    "/contextbench/request.json": json.dumps(row, indent=2, sort_keys=True),
                },
                "grade_row": row,
                "max_steps": 4,
                "timeout_sec": 120,
            }
        )

    letta_rows = [
        json.loads(line)
        for line in (LETTA_ROOT / "datasets/filesystem_code.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    target_index = 1
    target = letta_rows[target_index]
    difficulty = target.get("agent_args", {}).get("extra", {}).get("difficulty")
    if difficulty != "easy":
        raise ValueError("locked eval letta_filesystem_001_easy not available as easy difficulty")
    files = {
        f"/letta/filesystem/{path.name}": path.read_text(encoding="utf-8")
        for path in sorted((LETTA_ROOT / "files").glob("*.txt"))
    }
    specs.append(
        {
            "eval_id": "letta_filesystem_001_easy",
            "benchmark_class": "letta_context_bench",
            "task_id": "filesystem_code_001",
            "task_prompt": target["input"].replace("{pwd}", "/letta/filesystem") + "\nReturn one direct answer.",
            "workspace_seed": "simple_files",
            "workspace_files": files,
            "ground_truth": target["ground_truth"],
            "max_steps": 4,
            "timeout_sec": 120,
        }
    )
    return specs


def _bfcl_specs() -> list[dict[str, Any]]:
    rows = json.loads(BFCL_PATH.read_text(encoding="utf-8"))
    by_id = {row["id"]: row for row in rows}
    selected = ("multi_turn_composite_97", "multi_turn_composite_116", "multi_turn_composite_199")
    specs = []
    for task_id in selected:
        row = by_id[task_id]
        specs.append(
            {
                "eval_id": f"bfcl_v3_strict_{task_id}",
                "benchmark_class": "bfcl_strict_ground_truth",
                "task_id": row["id"],
                "task_prompt": row["prompt"],
                "workspace_seed": "simple_files",
                "workspace_files": dict(row["files"]),
                "ground_truth": row["ground_truth"],
                "max_steps": 4,
                "timeout_sec": 180,
            }
        )
    return specs


def _terminalbench_specs() -> list[dict[str, Any]]:
    return [
        {
            "eval_id": "terminalbench_public_fix-git",
            "benchmark_class": "terminalbench_public_regression",
            "task_id": "fix-git",
            "task_prompt": (
                "Recover missing site changes in the local workspace. Required file truth is under "
                "/app/resources/patch_files and the working tree is /app/personal-site."
            ),
            "workspace_seed": "fix_git",
            "max_steps": 6,
            "timeout_sec": 180,
        },
        {
            "eval_id": "terminalbench_public_financial-document-processor",
            "benchmark_class": "terminalbench_public_regression",
            "task_id": "financial-document-processor",
            "task_prompt": (
                "Process /app/documents into /app/invoices and /app/other, then write /app/invoices/summary.csv "
                "with required totals. Close only after /app/documents is empty."
            ),
            "workspace_seed": "financial_docs",
            "max_steps": 6,
            "timeout_sec": 240,
        },
    ]


def _long_horizon_spec() -> dict[str, Any]:
    return {
        "eval_id": LONG_ROW_EVAL_ID,
        "benchmark_class": "packet07_internal_long_horizon_diagnostic",
        "task_id": LONG_ROW_EVAL_ID,
        "task_prompt": (
            "Inspect all files under /app/case, repair /app/artifacts/final_report.json to contain truthful totals, "
            "run /app/verify.sh until it passes, rerun it once after passing, and close only with artifact path plus verifier status."
        ),
        "workspace_seed": "simple_files",
        "workspace_files": {
            "/case/alpha/invoice_a.txt": "invoice alpha total=17\n",
            "/case/beta/invoice_b.txt": "invoice beta total=25\n",
            "/case/gamma/invoice_c.txt": "invoice gamma total=8\n",
            "/artifacts/final_report.json": json.dumps(
                {
                    "status": "partial",
                    "total": 40,
                    "repaired": False,
                    "evidence_paths": ["/app/case/alpha/invoice_a.txt"],
                },
                indent=2,
                sort_keys=True,
            ),
            "/verify.sh": (
                "#!/bin/bash\n"
                "set -euo pipefail\n"
                "python3 - <<'PY'\n"
                "import json\n"
                "from pathlib import Path\n"
                "p=Path('/app/artifacts/final_report.json')\n"
                "obj=json.loads(p.read_text())\n"
                "ok=(obj.get('status')=='complete' and int(obj.get('total',-1))==50 and obj.get('repaired') is True)\n"
                "print('PASS' if ok else 'FAIL')\n"
                "raise SystemExit(0 if ok else 1)\n"
                "PY\n"
            ),
        },
        "artifact_relpath": "artifacts/final_report.json",
        "verifier_relpath": "verify.sh",
        "expected_total": 50,
        "required_evidence_paths": [
            "/app/case/alpha/invoice_a.txt",
            "/app/case/beta/invoice_b.txt",
            "/app/case/gamma/invoice_c.txt",
        ],
        "max_steps": 10,
        "timeout_sec": 360,
    }


def _route_availability_check(locked_route_matrix: dict[str, Any]) -> dict[str, Any]:
    rows = []
    blockers = []
    baseline = build_packet04_route_manifest(BASELINE_VARIANT_ID, scope=PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE)
    locked_routes = [str(row["route_id"]) for row in locked_route_matrix.get("routes", [])]
    if locked_routes != list(ROUTES):
        blockers.append("locked_route_matrix_mismatch")
    for route_id in ROUTES:
        try:
            manifest = _route_manifest(route_id)
            load_runtime_callables(manifest)
            validate_independent_candidate_routing(candidate_manifest=manifest, baseline_manifest=baseline)
            changed = sorted({row["runtime_key"] for row in manifest["routed_modules"] if row.get("claimed_changed_surface")})
            rows.append(
                {
                    "route_id": route_id,
                    "status": "pass",
                    "changed_runtime_keys": changed,
                    "route_manifest_fingerprint": manifest["route_manifest_fingerprint"],
                }
            )
        except Exception as exc:
            rows.append({"route_id": route_id, "status": "fail", "error": str(exc)})
            blockers.append(f"route_unavailable:{route_id}")
    return {"status": "pass" if not blockers else "fail", "blockers": blockers, "rows": rows}


def _eval_row_availability_check(locked_eval_rows: dict[str, Any], specs: list[dict[str, Any]]) -> dict[str, Any]:
    blockers = []
    locked_ids = [str(row["eval_id"]) for row in locked_eval_rows.get("model_backed_eval_rows", [])]
    spec_ids = [spec["eval_id"] for spec in specs]
    if locked_ids != spec_ids:
        blockers.append("locked_eval_order_mismatch")
    if len(specs) != 12:
        blockers.append("locked_eval_count_not_12")
    lane_counts = _counts(spec["lane"] for spec in specs)
    expected_lane_counts = {
        "completion_closure": 3,
        "context_handoff_answer_extraction": 3,
        "tooling_bfcl": 3,
        "terminalbench_regression_benchmark_anchors": 2,
        "long_running_internal_tb_style": 1,
    }
    if lane_counts != expected_lane_counts:
        blockers.append("locked_lane_distribution_mismatch")
    return {"status": "pass" if not blockers else "fail", "blockers": blockers, "locked_eval_ids": locked_ids, "lane_counts": lane_counts}


def _grader_availability_check(specs: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    blockers = []
    for spec in specs:
        eval_id = spec["eval_id"]
        available = _grader_available_for_spec(spec)
        rows.append({"eval_id": eval_id, "status": "pass" if available else "fail"})
        if not available:
            blockers.append(f"grader_unavailable:{eval_id}")
    return {"status": "pass" if not blockers else "fail", "blockers": blockers, "rows": rows}


def _adapter_validity_check(specs: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    blockers = []
    for spec in specs:
        eval_id = spec["eval_id"]
        missing = []
        for key in ("eval_id", "benchmark_class", "task_id", "task_prompt", "workspace_seed", "variant_ids", "max_steps", "timeout_sec"):
            if key not in spec:
                missing.append(key)
        status = "pass" if not missing else "fail"
        rows.append({"eval_id": eval_id, "status": status, "missing_fields": missing})
        if missing:
            blockers.append(f"adapter_spec_invalid:{eval_id}")
    return {"status": "pass" if not blockers else "fail", "blockers": blockers, "rows": rows}


def _execution_mode_disclosure() -> dict[str, Any]:
    mode = "sandbox_default"
    return {
        "status": "pass",
        "execution_mode": mode,
        "mode_details": {
            "network_restrictions_possible": True,
            "docker_required_for_board": False,
            "outside_sandbox_rerun_applied": False,
        },
    }


def _azure_dns_network_preflight() -> dict[str, Any]:
    blockers = []
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "").strip()
    if not endpoint:
        return {"status": "fail", "blockers": ["azure_endpoint_missing"], "endpoint_host": None, "dns_check": None, "tcp_check": None}
    host = urlparse(endpoint).hostname or ""
    dns = _run(["nslookup", host], cwd=Path.cwd(), timeout=20)
    dns_ok = dns["returncode"] == 0 and host in (dns.get("stdout", "") + dns.get("stderr", ""))
    if not dns_ok:
        blockers.append("azure_dns_lookup_failed")
    tcp = _run(
        [
            "python3",
            "-c",
            (
                "import socket,sys;"
                f"h='{host}';"
                "s=socket.socket();s.settimeout(5);"
                "code=0\n"
                "try:\n s.connect((h,443))\n"
                "except Exception:\n code=1\n"
                "s.close();sys.exit(code)"
            ),
        ],
        cwd=Path.cwd(),
        timeout=20,
    )
    if tcp["returncode"] != 0:
        blockers.append("azure_tcp_443_unreachable")
    model_route_ready = True
    model_route_error = None
    try:
        make_azure_gpt53_codex_route_from_env()
    except Exception as exc:
        model_route_ready = False
        model_route_error = str(exc)
        blockers.append("model_route_not_ready")
    return {
        "status": "pass" if not blockers else "fail",
        "blockers": blockers,
        "endpoint_host": host,
        "dns_check": {"returncode": dns["returncode"], "timed_out": dns.get("timed_out", False)},
        "tcp_check": {"returncode": tcp["returncode"], "timed_out": tcp.get("timed_out", False)},
        "model_route_ready": model_route_ready,
        "model_route_error": model_route_error,
    }


def _docker_or_fallback_preflight(specs: list[dict[str, Any]]) -> dict[str, Any]:
    docker = _run(["docker", "info"], cwd=Path.cwd(), timeout=30)
    available = docker["returncode"] == 0 and "Server:" in docker.get("stdout", "")
    requires_docker = any(bool(spec.get("requires_docker")) for spec in specs)
    blockers = []
    if requires_docker and not available:
        blockers.append("docker_required_but_unavailable")
    return {
        "status": "pass" if not blockers else "fail",
        "blockers": blockers,
        "docker_available": available,
        "requires_docker_for_locked_board": requires_docker,
        "fallback_status": "non_docker_local_supported" if not requires_docker else ("none" if available else "unavailable"),
    }


def _collect_preflight_blockers(preflight: dict[str, Any]) -> list[dict[str, Any]]:
    blockers = []
    for name, check in preflight.get("checks", {}).items():
        if check.get("status") == "pass":
            continue
        for item in check.get("blockers", ["unspecified"]):
            cls = "adapter_invalid_result"
            if name in {"azure_dns_network_preflight"}:
                cls = "infrastructure_invalid_result"
            elif name in {"docker_or_fallback"}:
                cls = "substrate_unavailable_result"
            blockers.append({"check": name, "blocker": item, "interpretation_class": cls})
    return blockers


def _resolve_worker_cap(max_workers: int) -> int:
    if max_workers < 1:
        raise ValueError("max_workers must be >= 1")
    host_cpus = os.cpu_count() or 2
    return max(1, min(max_workers, 4, host_cpus))


def _execute_board(out: Path, specs: list[dict[str, Any]], *, max_workers: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    plan_rows = []
    plan_index = 0
    for spec in specs:
        for variant in ROUTES:
            plan_rows.append({"plan_index": plan_index, "spec": spec, "variant": variant})
            plan_index += 1
    if max_workers == 1:
        records = []
        traces = []
        for row in plan_rows:
            record, trace = _run_with_retry(out, row["spec"], row["variant"], plan_index=row["plan_index"])
            records.append(record)
            traces.append(trace)
        return records, traces
    completed: list[tuple[int, dict[str, Any], dict[str, Any]]] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
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
            idx = future_map[future]
            record, trace = future.result()
            completed.append((idx, record, trace))
    completed.sort(key=lambda row: row[0])
    return [row[1] for row in completed], [row[2] for row in completed]


def _run_with_retry(out: Path, spec: dict[str, Any], variant: str, *, plan_index: int) -> tuple[dict[str, Any], dict[str, Any]]:
    last_record: dict[str, Any] | None = None
    last_trace: dict[str, Any] | None = None
    for attempt in range(2):
        record, trace = _run_one(out, spec, variant, attempt=attempt, plan_index=plan_index)
        last_record = record
        last_trace = trace
        if record["interpretation_class"] != "infrastructure_invalid_result":
            break
    assert last_record is not None and last_trace is not None
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
        model_client_kwargs={"timeout_sec": int(spec["timeout_sec"]), "max_retries": 1},
        max_steps=int(spec["max_steps"]),
        timeout_sec=int(spec["timeout_sec"]),
        cwd=workspace,
        route_manifest=_route_manifest(variant),
        enforce_packet04_route_contract=True,
    )
    model_exec_sec = perf_counter() - model_exec_started
    grade = _grade_spec(spec, result, workspace)
    infra_invalid = _is_infrastructure_invalid(run_dir)
    adapter_invalid = _is_adapter_invalid(run_dir)

    scoreboard_verdict = "invalid" if infra_invalid or adapter_invalid else grade.get("verdict", "fail")
    interpretation_class = _interpretation_class(spec, grade, infra_invalid=infra_invalid, adapter_invalid=adapter_invalid)
    reason_codes = list(grade.get("reason_codes", []))
    if infra_invalid:
        reason_codes = sorted(set(reason_codes + ["model_or_network_infra_failure"]))
    if adapter_invalid:
        reason_codes = sorted(set(reason_codes + ["adapter_contract_invalid"]))

    usage = _usage(result)
    runtime_timing = result.get("runtime_timing", {}) if isinstance(result.get("runtime_timing"), dict) else {}
    record = {
        "mission_id": MISSION_ID,
        "run_id": run_id,
        "eval_id": spec["eval_id"],
        "lane": spec["lane"],
        "benchmark_class": spec["benchmark_class"],
        "task_id": spec["task_id"],
        "variant_id": variant,
        "attempt": attempt,
        "plan_index": plan_index,
        "admission_level": spec.get("admission_level"),
        "diagnostic_only": bool(spec["eval_id"] == LONG_ROW_EVAL_ID),
        "model_backed": True,
        "run_dir": str(run_dir),
        "trace_ref": str(run_dir / "run_events.jsonl"),
        "score_summary": {"final_verdict": scoreboard_verdict, "grade": grade},
        "scoreboard_verdict": scoreboard_verdict,
        "interpretation_class": interpretation_class,
        "reason_codes": reason_codes,
        "token_and_cost_summary": usage,
        "authority": _authority(),
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
    trace = {
        "run_id": run_id,
        "eval_id": spec["eval_id"],
        "lane": spec["lane"],
        "variant_id": variant,
        "attempt": attempt,
        "trace_ref": str(run_dir / "run_events.jsonl"),
        "scoreboard_verdict": scoreboard_verdict,
        "interpretation_class": interpretation_class,
        "reason_codes": reason_codes,
    }
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
    if seed == "regex_log":
        contract = load_regex_log_contract(str(TERMINALBENCH_ROOT / "official_tasks/regex-log"))
        (workspace / "log.txt").write_text("\n".join(contract["sample_logs"]) + "\n", encoding="utf-8")
        return
    raise ValueError(f"unsupported_workspace_seed:{seed}")


def _copy_text(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")


def _grade_spec(spec: dict[str, Any], result: dict[str, Any], workspace: Path) -> dict[str, Any]:
    if spec["eval_id"] == LONG_ROW_EVAL_ID:
        return _grade_long_horizon_diagnostic(spec, result, workspace)
    return grade_phase65_spec(spec=spec, result=result, workspace=workspace)


def _grade_long_horizon_diagnostic(spec: dict[str, Any], result: dict[str, Any], workspace: Path) -> dict[str, Any]:
    reason_codes: list[str] = []
    artifact_path = workspace / spec["artifact_relpath"]
    payload: dict[str, Any] = {}
    if not artifact_path.exists():
        reason_codes.append("long_horizon_artifact_missing")
    else:
        try:
            payload = json.loads(artifact_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            reason_codes.append("long_horizon_artifact_not_json")
    if payload:
        if payload.get("status") != "complete":
            reason_codes.append("long_horizon_status_not_complete")
        if int(payload.get("total", -1)) != int(spec["expected_total"]):
            reason_codes.append("long_horizon_total_mismatch")
        if payload.get("repaired") is not True:
            reason_codes.append("long_horizon_repaired_flag_missing")
        evidence = payload.get("evidence_paths")
        if not isinstance(evidence, list) or sorted(str(item) for item in evidence) != sorted(spec["required_evidence_paths"]):
            reason_codes.append("long_horizon_evidence_paths_mismatch")
    verifier = _run(["bash", str(workspace / spec["verifier_relpath"])], cwd=workspace, timeout=20)
    if verifier["returncode"] != 0:
        reason_codes.append("long_horizon_verifier_rerun_failed")
    answer = _assistant_text(result)
    if spec["artifact_relpath"] not in answer:
        reason_codes.append("long_horizon_final_answer_missing_artifact_path")
    if "pass" not in answer.lower() and "verified" not in answer.lower():
        reason_codes.append("long_horizon_final_answer_missing_verifier_signal")
    return {
        "verdict": "pass" if not reason_codes else "fail",
        "reason_codes": reason_codes,
        "artifact_path": str(artifact_path),
        "verifier_returncode": verifier["returncode"],
    }


def _assistant_text(result: dict[str, Any]) -> str:
    last = result.get("execution", {}).get("last_completion")
    if isinstance(last, dict) and isinstance(last.get("text"), str):
        return last["text"]
    text = ""
    for step in result.get("execution", {}).get("steps", []):
        completion = step.get("completion") if isinstance(step, dict) else None
        candidate = completion.get("text") if isinstance(completion, dict) else None
        if isinstance(candidate, str):
            text = candidate
    return text


def _is_infrastructure_invalid(run_dir: Path) -> bool:
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
        kind = str(details.get("error_kind", "")).lower()
        message = str(details.get("message", "")).lower()
        if kind in {"network_error", "refresh_network_error", "timeout_error"}:
            return True
        if any(token in message for token in ("dns", "name or service not known", "temporarily unavailable", "connection")):
            return True
        return True
    return False


def _is_adapter_invalid(run_dir: Path) -> bool:
    score_path = run_dir / "score_envelope.json"
    header_path = run_dir / "run_header.json"
    if not score_path.exists() or not header_path.exists():
        return True
    try:
        score = json.loads(score_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return True
    aggregate = score.get("aggregate")
    return not isinstance(aggregate, dict) or "final_verdict" not in aggregate


def _interpretation_class(spec: dict[str, Any], grade: dict[str, Any], *, infra_invalid: bool, adapter_invalid: bool) -> str:
    if infra_invalid:
        return "infrastructure_invalid_result"
    if adapter_invalid:
        return "adapter_invalid_result"
    if grade.get("verdict") == "pass":
        return "behavioral_pass"
    reason_codes = set(str(code) for code in grade.get("reason_codes", []))
    lane = spec["lane"]

    if lane == "completion_closure":
        closure_markers = {
            "partial_progress_required_artifact_missing",
            "partial_progress_final_answer_missing_artifact_path",
            "partial_progress_final_answer_missing_total",
            "verifier_script_missing",
            "missing_solution_file",
        }
        if reason_codes & closure_markers:
            return "closure_contract_failure"
        return "task_truth_failure"

    if lane == "context_handoff_answer_extraction":
        if "contextbench_repo_or_file_family_mismatch" in reason_codes:
            row = spec.get("grade_row") or {}
            source_repo = str(row.get("repo_or_file_family", "") or "").strip().lower()
            if source_repo in {"", "none", "null", "nan"}:
                return "derived_field_policy_failure"
        if any(code.startswith("contextbench_") for code in reason_codes) or "letta_ground_truth_mismatch" in reason_codes:
            return "source_grounded_extraction_failure"
        if "work_pocket_artifact_missing" in reason_codes or "work_pocket_artifact_not_json" in reason_codes:
            return "closure_contract_failure"
        if "work_pocket_evidence_paths_mismatch" in reason_codes:
            return "source_grounded_extraction_failure"
        return "task_truth_failure"

    if lane == "tooling_bfcl":
        return "task_truth_failure"

    if lane == "long_running_internal_tb_style":
        if any(code.startswith("long_horizon_") for code in reason_codes):
            if {"long_horizon_artifact_missing", "long_horizon_final_answer_missing_artifact_path"} & reason_codes:
                return "closure_contract_failure"
            return "proxy_shaped_failure"
        return "task_truth_failure"

    if lane == "terminalbench_regression_benchmark_anchors":
        if "fix_git_required_files_missing" in reason_codes or "financial_required_paths_missing" in reason_codes:
            return "closure_contract_failure"
        return "task_truth_failure"

    return "task_truth_failure"


def _usage(result: dict[str, Any]) -> dict[str, Any]:
    totals = {"input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    for step in result.get("execution", {}).get("steps", []):
        usage = (step.get("completion") or {}).get("usage") or {}
        totals["input_tokens"] += int(usage.get("input_tokens", usage.get("prompt_tokens", 0)) or 0)
        totals["cached_input_tokens"] += int(usage.get("cached_tokens", usage.get("cached_input_tokens", 0)) or 0)
        totals["output_tokens"] += int(usage.get("output_tokens", usage.get("completion_tokens", 0)) or 0)
        totals["total_tokens"] += int(usage.get("total_tokens", 0) or 0)
    usd = (
        max(totals["input_tokens"] - totals["cached_input_tokens"], 0) * PRICE["input"]
        + totals["cached_input_tokens"] * PRICE["cached_input"]
        + totals["output_tokens"] * PRICE["output"]
    )
    return {**totals, "usd": usd, "usd_estimate": usd}


def _write_success_artifacts(
    *,
    out: Path,
    records: list[dict[str, Any]],
    traces: list[dict[str, Any]],
    preflight: dict[str, Any],
    eval_quality_result: dict[str, Any],
    locked_eval_rows: dict[str, Any],
) -> dict[str, Any]:
    _write_jsonl(out / "packet07_cycle0_result_records.jsonl", records)
    score = _score_envelope(records, preflight, eval_quality_result)
    trace_report = {"mission_id": MISSION_ID, "run_count": len(traces), "traces": traces}
    failure_report = _failure_source_report(records, eval_quality_result)
    variant_delta = _variant_delta_report(records, score)
    cost_report = _cost_report(records)
    recommendations = _recommendations(records, score, failure_report, eval_quality_result, locked_eval_rows)
    deep_trace = _deep_trace_analysis(score, failure_report, variant_delta, recommendations)
    handoff = _handoff(score, failure_report, variant_delta, recommendations)

    _write_json(out / "packet07_cycle0_score_envelope.json", score)
    _write_json(out / "packet07_cycle0_trace_report.json", trace_report)
    _write_json(out / "packet07_cycle0_failure_source_report.json", failure_report)
    _write_json(out / "packet07_cycle0_variant_delta_report.json", variant_delta)
    _write_json(out / "packet07_cycle0_cost_report.json", cost_report)
    _write_json(out / "packet07_cycle0_recommendations.json", recommendations)
    _write_text(out / "packet07_cycle0_deep_trace_analysis.md", deep_trace)
    _write_text(out / "packet07_cycle0_handoff.md", handoff)

    ledger = _raw_ledger_update(out, score, failure_report, recommendations)
    _record_ledger(ledger)
    _write_text(out / "RAW_LEDGER_UPDATE", ledger)
    return {
        "output_dir": str(out),
        "run_count": len(records),
        "model_backed_runs": score["model_backed_runs"],
        "selected_recommendation": recommendations["selected_recommendation"],
    }


def _write_blocked_artifacts(
    out: Path,
    *,
    preflight: dict[str, Any],
    eval_quality_result: dict[str, Any],
    locked_eval_rows: dict[str, Any],
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    _write_jsonl(out / "packet07_cycle0_result_records.jsonl", records)
    score = {
        "mission_id": MISSION_ID,
        "run_count": 0,
        "model_backed_runs": 0,
        "planned_model_backed_runs": 60,
        "behaviorally_admissible_run_count": 0,
        "invalid_class_counts": _counts(blocker["interpretation_class"] for blocker in preflight.get("blockers", [])),
        "preflight": preflight,
        "selected_recommendation": "infra_blocked"
        if any(blocker["interpretation_class"] == "infrastructure_invalid_result" for blocker in preflight.get("blockers", []))
        else "measurement_blocked"
        if any(blocker["interpretation_class"] == "adapter_invalid_result" for blocker in preflight.get("blockers", []))
        else "no_valid_signal",
    }
    trace_report = {"mission_id": MISSION_ID, "run_count": 0, "traces": [], "preflight_blockers": preflight.get("blockers", [])}
    failure_report = {
        "mission_id": MISSION_ID,
        "blocked": True,
        "dominant_failure_lane": "preflight_blocked",
        "failure_counts_by_interpretation_class": _counts(blocker["interpretation_class"] for blocker in preflight.get("blockers", [])),
        "preflight_blockers": preflight.get("blockers", []),
    }
    variant_delta = {
        "mission_id": MISSION_ID,
        "blocked": True,
        "safest_incumbent": None,
        "experimental_context_mechanism_delta": "not_executed",
        "route_actions": {route: "freeze_pending_infra_or_adapter_recovery" for route in ROUTES},
    }
    cost_report = {
        "mission_id": MISSION_ID,
        "run_count": 0,
        "total_tokens": 0,
        "total_usd_estimate": 0.0,
    }
    recommendations = _recommendations(records, score, failure_report, eval_quality_result, locked_eval_rows)
    deep_trace = _deep_trace_analysis(score, failure_report, variant_delta, recommendations)
    handoff = _handoff(score, failure_report, variant_delta, recommendations)

    _write_json(out / "packet07_cycle0_score_envelope.json", score)
    _write_json(out / "packet07_cycle0_trace_report.json", trace_report)
    _write_json(out / "packet07_cycle0_failure_source_report.json", failure_report)
    _write_json(out / "packet07_cycle0_variant_delta_report.json", variant_delta)
    _write_json(out / "packet07_cycle0_cost_report.json", cost_report)
    _write_json(out / "packet07_cycle0_recommendations.json", recommendations)
    _write_text(out / "packet07_cycle0_deep_trace_analysis.md", deep_trace)
    _write_text(out / "packet07_cycle0_handoff.md", handoff)

    ledger = _raw_ledger_update(out, score, failure_report, recommendations)
    _record_ledger(ledger)
    _write_text(out / "RAW_LEDGER_UPDATE", ledger)
    return {
        "output_dir": str(out),
        "run_count": 0,
        "model_backed_runs": 0,
        "selected_recommendation": recommendations["selected_recommendation"],
        "blocked": True,
    }


def _score_envelope(records: list[dict[str, Any]], preflight: dict[str, Any], eval_quality_result: dict[str, Any]) -> dict[str, Any]:
    admitted = [row for row in records if row["interpretation_class"] == "behavioral_pass" or row["interpretation_class"] in {
        "closure_contract_failure",
        "task_truth_failure",
        "source_grounded_extraction_failure",
        "derived_field_policy_failure",
        "proxy_shaped_failure",
    }]
    certified = [row for row in admitted if row.get("admission_level") == "certified"]
    by_route = _route_summary(certified)
    safest_incumbent = _select_safest_incumbent(by_route)
    return {
        "mission_id": MISSION_ID,
        "run_count": len(records),
        "model_backed_runs": sum(1 for row in records if row.get("model_backed")),
        "planned_model_backed_runs": 60,
        "behaviorally_admissible_run_count": len(admitted),
        "invalid_class_counts": _counts(
            row["interpretation_class"]
            for row in records
            if row["interpretation_class"] in {"infrastructure_invalid_result", "adapter_invalid_result", "substrate_unavailable_result"}
        ),
        "scoreboard_verdict_counts": _counts(row["scoreboard_verdict"] for row in records),
        "certified_lane_pass_rates": _lane_pass_rates(certified),
        "route_summary_certified_only": by_route,
        "safest_incumbent": safest_incumbent,
        "experimental_row_gate_clear": bool(eval_quality_result.get("long_row_gate_clear")),
        "preflight": preflight,
    }


def _failure_source_report(records: list[dict[str, Any]], eval_quality_result: dict[str, Any]) -> dict[str, Any]:
    certified_rows = [row for row in records if row.get("admission_level") == "certified"]
    certified_failures = [row for row in certified_rows if row["scoreboard_verdict"] != "pass"]
    failure_by_lane = _counts(row["lane"] for row in certified_failures)
    dominant_lane = "none"
    if failure_by_lane:
        dominant_lane = max(failure_by_lane.items(), key=lambda item: (item[1], item[0]))[0]
    return {
        "mission_id": MISSION_ID,
        "failure_count": len([row for row in records if row["scoreboard_verdict"] != "pass"]),
        "certified_failure_count": len(certified_failures),
        "dominant_failure_lane": dominant_lane,
        "failure_counts_by_lane": failure_by_lane,
        "failure_counts_by_interpretation_class": _counts(row["interpretation_class"] for row in records if row["scoreboard_verdict"] != "pass"),
        "measurement_blocked_rows": [
            row["run_id"] for row in records if row["interpretation_class"] in {"derived_field_policy_failure", "proxy_shaped_failure"}
        ],
        "infra_blocked_rows": [
            row["run_id"] for row in records if row["interpretation_class"] in {"infrastructure_invalid_result", "substrate_unavailable_result", "adapter_invalid_result"}
        ],
        "long_row_diagnostic_only": not bool(eval_quality_result.get("long_row_gate_clear")),
    }


def _variant_delta_report(records: list[dict[str, Any]], score: dict[str, Any]) -> dict[str, Any]:
    certified = [row for row in records if row.get("admission_level") == "certified"]
    safest = score.get("safest_incumbent")
    route_summary = _route_summary(certified)
    incumbent_stats = route_summary.get(safest or "", {})
    delta_rows = []
    for route_id in ROUTES:
        stats = route_summary.get(route_id, {"pass": 0, "fail": 0, "invalid": 0, "run_count": 0})
        delta_rows.append(
            {
                "route_id": route_id,
                "certified_pass": stats.get("pass", 0),
                "certified_fail": stats.get("fail", 0),
                "certified_invalid": stats.get("invalid", 0),
                "delta_vs_safest_incumbent_pass": stats.get("pass", 0) - incumbent_stats.get("pass", 0),
            }
        )
    experimental = next((row for row in delta_rows if row["route_id"] == "candidate_plus_context_followup_merged_01"), None)
    reference = next((row for row in delta_rows if row["route_id"] == "verified_work_pocket_handoff_hybrid_01"), None)
    helped = False
    if experimental and reference:
        helped = experimental["certified_pass"] > reference["certified_pass"]
    actions = {}
    for row in delta_rows:
        route_id = row["route_id"]
        if route_id == safest:
            actions[route_id] = "carry_forward"
        elif route_id == "candidate_plus_context_followup_merged_01":
            actions[route_id] = "carry_forward_experimental" if helped else "freeze_experimental"
        elif row["certified_pass"] == 0 and row["certified_fail"] > 0:
            actions[route_id] = "kill"
        else:
            actions[route_id] = "freeze"
    return {
        "mission_id": MISSION_ID,
        "safest_incumbent": safest,
        "deltas": delta_rows,
        "experimental_context_mechanism_helped": helped,
        "route_actions": actions,
    }


def _cost_report(records: list[dict[str, Any]]) -> dict[str, Any]:
    total_tokens = 0
    total_usd = 0.0
    for row in records:
        usage = row.get("token_and_cost_summary", {})
        total_tokens += int(usage.get("total_tokens", 0) or 0)
        total_usd += float(usage.get("usd_estimate", usage.get("usd", 0.0)) or 0.0)
    return {"mission_id": MISSION_ID, "run_count": len(records), "total_tokens": total_tokens, "total_usd_estimate": total_usd}


def _recommendations(
    records: list[dict[str, Any]],
    score: dict[str, Any],
    failure_report: dict[str, Any],
    eval_quality_result: dict[str, Any],
    locked_eval_rows: dict[str, Any],
) -> dict[str, Any]:
    recommendation = "no_valid_signal"
    invalid_counts = score.get("invalid_class_counts", {})
    infra_invalid = (
        invalid_counts.get("infrastructure_invalid_result", 0) + invalid_counts.get("substrate_unavailable_result", 0) + invalid_counts.get("adapter_invalid_result", 0)
    )
    if infra_invalid > 0 and score.get("behaviorally_admissible_run_count", 0) == 0:
        recommendation = "infra_blocked"
    else:
        measurement_blocked_rows = failure_report.get("measurement_blocked_rows", [])
        certified_rows = [row for row in records if row.get("admission_level") == "certified"]
        if certified_rows and len(measurement_blocked_rows) >= len(certified_rows) // 2 and len(measurement_blocked_rows) > 0:
            recommendation = "measurement_blocked"
        else:
            lane = failure_report.get("dominant_failure_lane", "none")
            lane_map = {
                "completion_closure": "cycle1_target_completion",
                "context_handoff_answer_extraction": "cycle1_target_context",
                "tooling_bfcl": "cycle1_target_bfcl_tooling",
                "terminalbench_regression_benchmark_anchors": "cycle1_target_mixed",
                "none": "no_valid_signal",
            }
            recommendation = lane_map.get(lane, "cycle1_target_mixed")
    if recommendation not in RECOMMENDATIONS:
        recommendation = "no_valid_signal"
    infra_blockers_present = bool(failure_report.get("infra_blocked_rows"))
    if not infra_blockers_present:
        infra_blockers_present = bool(score.get("invalid_class_counts", {}).get("infrastructure_invalid_result", 0))
        infra_blockers_present = infra_blockers_present or bool(
            score.get("invalid_class_counts", {}).get("substrate_unavailable_result", 0)
        )
        infra_blockers_present = infra_blockers_present or bool(
            score.get("invalid_class_counts", {}).get("adapter_invalid_result", 0)
        )
    measurement_blockers_present = bool(failure_report.get("measurement_blocked_rows"))
    if not measurement_blockers_present:
        measurement_blockers_present = recommendation == "measurement_blocked"
    return {
        "mission_id": MISSION_ID,
        "selected_recommendation": recommendation,
        "safest_incumbent": score.get("safest_incumbent"),
        "dominant_failure_lane": failure_report.get("dominant_failure_lane"),
        "structured_observation_register_helped": _did_experimental_help(records),
        "kill_freeze_carry_forward": _kill_freeze_carry(records, score),
        "measurement_blockers_present": measurement_blockers_present,
        "infra_blockers_present": infra_blockers_present,
        "cycle1_target_basis": {
            "eval_rows_locked": len(locked_eval_rows.get("model_backed_eval_rows", [])),
            "long_row_gate_clear": bool(eval_quality_result.get("long_row_gate_clear")),
        },
    }


def _did_experimental_help(records: list[dict[str, Any]]) -> bool:
    cert = [row for row in records if row.get("admission_level") == "certified"]
    exp_pass = sum(
        1
        for row in cert
        if row["variant_id"] == "candidate_plus_context_followup_merged_01" and row["scoreboard_verdict"] == "pass"
    )
    ref_pass = sum(
        1
        for row in cert
        if row["variant_id"] == "verified_work_pocket_handoff_hybrid_01" and row["scoreboard_verdict"] == "pass"
    )
    return exp_pass > ref_pass


def _kill_freeze_carry(records: list[dict[str, Any]], score: dict[str, Any]) -> dict[str, str]:
    certified = [row for row in records if row.get("admission_level") == "certified"]
    summary = _route_summary(certified)
    safest = score.get("safest_incumbent")
    out = {}
    for route in ROUTES:
        stats = summary.get(route, {"pass": 0, "fail": 0, "invalid": 0})
        if route == safest:
            out[route] = "carry_forward"
        elif route == "candidate_plus_context_followup_merged_01":
            out[route] = "carry_forward_experimental" if _did_experimental_help(records) else "freeze_experimental"
        elif stats["pass"] == 0 and stats["fail"] > 0:
            out[route] = "kill"
        else:
            out[route] = "freeze"
    return out


def _deep_trace_analysis(score: dict[str, Any], failure_report: dict[str, Any], variant_delta: dict[str, Any], recommendations: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Packet 07 Cycle 0 Deep Trace Analysis",
            "",
            "## Required answers",
            "",
            f"1. safest incumbent: `{recommendations.get('safest_incumbent')}`",
            f"2. dominant blocker lane: `{recommendations.get('dominant_failure_lane')}`",
            f"3. Structured Observation Register helped: `{recommendations.get('structured_observation_register_helped')}`",
            f"4. kill/freeze/carry: `{recommendations.get('kill_freeze_carry_forward')}`",
            f"5. measurement blocked rows present: `{recommendations.get('measurement_blockers_present')}`",
            f"6. infra blocked rows present: `{recommendations.get('infra_blockers_present')}`",
            f"7. Cycle 1 target: `{recommendations.get('selected_recommendation')}`",
            "",
            "## Score summary",
            "",
            f"- run_count: `{score.get('run_count')}`",
            f"- model_backed_runs: `{score.get('model_backed_runs')}`",
            f"- behaviorally_admissible_run_count: `{score.get('behaviorally_admissible_run_count')}`",
            f"- invalid_class_counts: `{score.get('invalid_class_counts')}`",
            "",
            "## Failure sources",
            "",
            f"- dominant_failure_lane: `{failure_report.get('dominant_failure_lane')}`",
            f"- failure_counts_by_lane: `{failure_report.get('failure_counts_by_lane')}`",
            f"- failure_counts_by_interpretation_class: `{failure_report.get('failure_counts_by_interpretation_class')}`",
            "",
            "## Route deltas",
            "",
            f"- safest_incumbent: `{variant_delta.get('safest_incumbent')}`",
            f"- experimental_context_mechanism_helped: `{variant_delta.get('experimental_context_mechanism_helped')}`",
            f"- route_actions: `{variant_delta.get('route_actions')}`",
        ]
    ) + "\n"


def _handoff(score: dict[str, Any], failure_report: dict[str, Any], variant_delta: dict[str, Any], recommendations: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Packet 07 Cycle 0 Handoff",
            "",
            f"- mission_id: `{MISSION_ID}`",
            f"- run_count: `{score.get('run_count')}`",
            f"- model_backed_runs: `{score.get('model_backed_runs')}`",
            f"- behaviorally_admissible_run_count: `{score.get('behaviorally_admissible_run_count')}`",
            f"- selected_recommendation: `{recommendations.get('selected_recommendation')}`",
            f"- safest_incumbent: `{recommendations.get('safest_incumbent')}`",
            f"- dominant_failure_lane: `{recommendations.get('dominant_failure_lane')}`",
            f"- structured_observation_register_helped: `{recommendations.get('structured_observation_register_helped')}`",
            f"- route_actions: `{variant_delta.get('route_actions')}`",
            f"- measurement_blockers_present: `{recommendations.get('measurement_blockers_present')}`",
            f"- infra_blockers_present: `{recommendations.get('infra_blockers_present')}`",
            "",
            "Required artifacts produced:",
            "- packet07_cycle0_result_records.jsonl",
            "- packet07_cycle0_score_envelope.json",
            "- packet07_cycle0_trace_report.json",
            "- packet07_cycle0_failure_source_report.json",
            "- packet07_cycle0_variant_delta_report.json",
            "- packet07_cycle0_eval_quality_result.json",
            "- packet07_cycle0_cost_report.json",
            "- packet07_cycle0_recommendations.json",
            "- packet07_cycle0_deep_trace_analysis.md",
            "- packet07_cycle0_handoff.md",
            "- RAW_LEDGER_UPDATE",
        ]
    ) + "\n"


def _raw_ledger_update(out: Path, score: dict[str, Any], failure_report: dict[str, Any], recommendations: dict[str, Any]) -> str:
    return "\n".join(
        [
            "RAW_LEDGER_UPDATE",
            "- actor: codex",
            "- task: Packet 07 Cycle 0 mixed confirmation board execution",
            "- event_type: experiment",
            (
                f"- summary: Executed or preflight-blocked Packet 07 Cycle 0 mixed board with recommendation "
                f"`{recommendations.get('selected_recommendation')}`."
            ),
            (
                "- observations: "
                f"run_count `{score.get('run_count', 0)}`; model_backed_runs `{score.get('model_backed_runs', 0)}`; "
                f"behaviorally_admissible_run_count `{score.get('behaviorally_admissible_run_count', 0)}`; "
                f"dominant_failure_lane `{failure_report.get('dominant_failure_lane')}`; "
                f"safest_incumbent `{recommendations.get('safest_incumbent')}`."
            ),
            "- inference: Cycle 0 establishes the starting truth under Packet 07 measurement and infra-validity policies without mutating routes.",
            (
                f"- evidence_paths: {out / 'packet07_cycle0_result_records.jsonl'}; "
                f"{out / 'packet07_cycle0_score_envelope.json'}; "
                f"{out / 'packet07_cycle0_failure_source_report.json'}; "
                f"{out / 'packet07_cycle0_variant_delta_report.json'}; "
                f"{out / 'packet07_cycle0_recommendations.json'}; "
                f"{out / 'packet07_cycle0_handoff.md'}"
            ),
            "- affected_components: Packet07 Cycle0 execution runner; mixed-lane board evidence; measurement/infra classification outputs",
            "- decision_change: Packet07 Cycle0 completed as designed; Cycle1 target set from dominant blocker classification.",
            "- unresolved_questions: Whether long-horizon row scorer should be promoted beyond diagnostic-only before Cycle1 interpretation.",
            "- confidence: medium",
            "- commit_message: HOLD - execute Packet07 Cycle0 mixed confirmation board and emit required artifacts",
        ]
    )


def _route_summary(records: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for row in records:
        route = row["variant_id"]
        bucket = out.setdefault(route, {"run_count": 0, "pass": 0, "fail": 0, "invalid": 0})
        bucket["run_count"] += 1
        verdict = row["scoreboard_verdict"]
        if verdict not in bucket:
            bucket[verdict] = 0
        bucket[verdict] += 1
    return out


def _select_safest_incumbent(by_route: dict[str, dict[str, int]]) -> str | None:
    ranked = []
    for route in ROUTES:
        stats = by_route.get(route, {"pass": 0, "fail": 0, "invalid": 0, "run_count": 0})
        ranked.append((stats["pass"], -stats["fail"], -stats["invalid"], route))
    if not ranked:
        return None
    return max(ranked)[-1]


def _lane_pass_rates(records: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    by_lane = {}
    for row in records:
        lane = row["lane"]
        bucket = by_lane.setdefault(lane, {"run_count": 0, "pass": 0})
        bucket["run_count"] += 1
        if row["scoreboard_verdict"] == "pass":
            bucket["pass"] += 1
    for lane, counts in by_lane.items():
        run_count = counts["run_count"]
        out[lane] = {
            "run_count": run_count,
            "pass_count": counts["pass"],
            "pass_rate": float(counts["pass"]) / float(run_count) if run_count else 0.0,
        }
    return out


def _counts(values: Any) -> dict[str, int]:
    out: dict[str, int] = {}
    for value in values:
        out[str(value)] = out.get(str(value), 0) + 1
    return out


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _route_manifest(variant: str) -> dict[str, Any]:
    if variant == "candidate_plus_context_followup_merged_01":
        return build_context_followup_merged_manifest(variant)
    return build_packet04_route_manifest(variant, scope=PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE)


def _grader_available_for_spec(spec: dict[str, Any]) -> bool:
    supported = {
        "letta_context_bench",
        "contextbench",
        "bfcl_strict_ground_truth",
        "terminalbench_repaired_closure",
        "terminalbench_public_regression",
        "phase65_completion_partial_progress",
        "phase65_completion_verifier_repair",
        "phase65_context_work_pocket",
        "packet07_internal_long_horizon_diagnostic",
    }
    return spec.get("benchmark_class") in supported


def _evaluate_long_row_gate(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    checks = {
        "clear_task_contract": _section_status_is_pass(text, "Clear task contract"),
        "explicit_failure_target": _section_status_is_pass(text, "Explicit failure target"),
        "explicit_positive_capability_target": _section_status_is_pass(text, "Explicit positive-capability target"),
        "faithful_grader_not_proxy_shaped": _section_status_is_pass(text, "Faithful grader, not proxy-shaped"),
        "negative_controls": _section_status_is_pass(text, "Negative controls or explicit bad-output cases"),
        "adapter_validity": _section_status_is_pass(text, "Adapter validity"),
        "trace_sufficiency": _section_status_is_pass(text, "Trace sufficiency"),
        "baseline_sanity_check": _section_status_is_pass(text, "Baseline sanity check"),
    }
    pending_count = text.count("status: `pending`")
    gate_clear = all(checks.values()) and pending_count == 0
    return {
        "mission_id": MISSION_ID,
        "eval_id": LONG_ROW_EVAL_ID,
        "source_report": str(path),
        "checks": checks,
        "pending_count": pending_count,
        "long_row_gate_clear": gate_clear,
        "long_row_interpretation": "scored" if gate_clear else "diagnostic_only",
    }


def _section_status_is_pass(text: str, heading: str) -> bool:
    marker = f"### {heading}"
    start = text.find(marker)
    if start < 0:
        return False
    end = text.find("\n### ", start + len(marker))
    if end < 0:
        end = len(text)
    block = text[start:end]
    return "status: `pass`" in block


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--no-execute", action="store_true")
    parser.add_argument("--max-workers", type=int, default=DEFAULT_MAX_WORKERS)
    args = parser.parse_args(argv)
    print(
        json.dumps(
            launch_packet07_cycle0(
                output_dir=args.output_dir,
                execute=not args.no_execute,
                max_workers=args.max_workers,
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
