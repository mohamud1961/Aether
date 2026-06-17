"""Execute Packet 07 Cycle 1 context-targeted autoresearch."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from pathlib import Path
from time import perf_counter
from typing import Any
from urllib.parse import urlparse

from runner.agent import run_reference_baseline
from runner.eval_runner_router import resolve_model_route_for_route
from runner.letta_context_bench import letta_preflight
from runner.packet04_route_manifest import (
    BASELINE_VARIANT_ID,
    PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE,
    build_packet04_route_manifest,
    load_runtime_callables,
    validate_independent_candidate_routing,
)
from runner.phase65_measurement_contracts import load_regex_log_contract
from runner.phase65_measurement_grading import grade_phase65_spec
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

MISSION_ID = "packet07_cycle1_context_targeted_autoresearch"
DEFAULT_OUTPUT_DIR = Path(
    "tracking/collab/stage_03_execution_planning/packets/packet_06_paired_combo_variants/"
    "runs/2026-05-09_packet07_cycle1_context_targeted_autoresearch"
)
SYNTH_ROOT = Path(
    "tracking/collab/stage_03_execution_planning/packets/packet_06_paired_combo_variants/synthesis"
)
CANDIDATE_SET_PATH = SYNTH_ROOT / "packet07_cycle1_context_candidate_set_2026_05_09.json"
EVAL_ROWS_PATH = SYNTH_ROOT / "packet07_cycle1_context_eval_rows_2026_05_09.json"
MUTATION_POLICY_PATH = SYNTH_ROOT / "packet07_cycle1_context_mutation_policy_2026_05_09.json"
MEASUREMENT_POLICY_PATH = SYNTH_ROOT / "packet07_measurement_policy_2026_05_08.md"
INFRA_POLICY_PATH = SYNTH_ROOT / "packet07_infra_validity_policy_2026_05_08.md"

DEFAULT_MAX_WORKERS = 2
LONG_ROW_EVAL_ID = "tb_style_long_horizon_artifact_repair_and_verify_v1"
CUSTOM_LONG_HANDOFF_EVAL_ID = "custom_long_context_handoff_aggregation_v1"

CONTEXT_ROUTE_FAMILY = json.loads(CANDIDATE_SET_PATH.read_text(encoding="utf-8"))
BACKBONE_INCUMBENT = str(CONTEXT_ROUTE_FAMILY["fixed_routes"][0]["route_id"])
BACKBONE_INcUMBENT = BACKBONE_INCUMBENT
GOVERNED_CONTEXT_REFERENCE = str(CONTEXT_ROUTE_FAMILY["fixed_routes"][1]["route_id"])
FROZEN_EXPERIMENTAL_REFERENCE = str(CONTEXT_ROUTE_FAMILY["fixed_routes"][2]["route_id"])
MUTATION_VARIANTS = tuple(str(row["route_id"]) for row in CONTEXT_ROUTE_FAMILY["mutation_slots"])
ROUTES = (
    BACKBONE_INcUMBENT,
    GOVERNED_CONTEXT_REFERENCE,
    FROZEN_EXPERIMENTAL_REFERENCE,
    *MUTATION_VARIANTS,
)

ROUTE_ROLES = {
    BACKBONE_INcUMBENT: "backbone_incumbent",
    GOVERNED_CONTEXT_REFERENCE: "governed_context_reference",
    FROZEN_EXPERIMENTAL_REFERENCE: "frozen_experimental_reference",
    MUTATION_VARIANTS[0]: "work_pocket_answer_projection",
    MUTATION_VARIANTS[1]: "context_answer_closure_guard",
}

LOCAL_ROUTE_OVERRIDES = {
    FROZEN_EXPERIMENTAL_REFERENCE: {
        "base_variant": GOVERNED_CONTEXT_REFERENCE,
        "modules": {
            "context": {
                "file_rel": "blocks/context/phase65_context_followup_merged.py",
                "module_import_path": "blocks.context.phase65_context_followup_merged:manage",
            }
        },
    },
    MUTATION_VARIANTS[0]: {
        "base_variant": GOVERNED_CONTEXT_REFERENCE,
        "modules": {
            "orientation": {
                "file_rel": "blocks/orientation/packet07_context_doctrine.py",
                "module_import_path": "blocks.orientation.packet07_context_doctrine:orient_work_pocket_answer_projection",
            },
            "context": {
                "file_rel": "blocks/context/work_pocket_answer_projection.py",
                "module_import_path": "blocks.context.work_pocket_answer_projection:manage",
            },
        },
    },
    MUTATION_VARIANTS[1]: {
        "base_variant": GOVERNED_CONTEXT_REFERENCE,
        "modules": {
            "orientation": {
                "file_rel": "blocks/orientation/packet07_context_doctrine.py",
                "module_import_path": "blocks.orientation.packet07_context_doctrine:orient_context_answer_closure_guard",
            },
            "context": {
                "file_rel": "blocks/context/context_answer_closure_guard.py",
                "module_import_path": "blocks.context.context_answer_closure_guard:manage",
            },
        },
    },
}

ALLOWED_RECOMMENDATIONS = (
    "context_repair_viable_continue_packet07",
    "context_repair_partial_continue_one_more_context_cycle",
    "context_measurement_or_eval_blocked",
    "context_no_signal_shift_target",
)
MODEL_TIER_SELECTORS = ("screening_default", "screening_fallback", "promotion_tier")
PACKET07_CONTEXT_MODEL_POLICY = {
    "screening_default": "azure:gpt-5.4-mini",
    "screening_fallback": "azure:gpt-5.4-mini",
    "promotion_tier": "azure:gpt-5.3-codex",
}


def launch_packet07_cycle1(
    *,
    output_dir: str | Path,
    execute: bool = True,
    max_workers: int = DEFAULT_MAX_WORKERS,
    model_tier_selector: str = "screening_default",
) -> dict[str, Any]:
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)

    locked_eval_rows = _load_json(EVAL_ROWS_PATH)
    mutation_policy = _load_json(MUTATION_POLICY_PATH)
    specs = _build_specs_from_locked_rows(locked_eval_rows)
    board_manifest = _board_manifest(specs, mutation_policy)

    route_check = _route_availability_check()
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

    _write_json(out / "packet07_cycle1_context_board_manifest.json", board_manifest)

    if not execute or preflight["status"] != "pass":
        return _write_blocked_artifacts(out, preflight=preflight, board_manifest=board_manifest)

    records, traces = _execute_board(
        out=out,
        specs=specs,
        max_workers=_resolve_worker_cap(max_workers),
        model_tier_selector=model_tier_selector,
    )
    return _write_success_artifacts(
        out=out,
        records=records,
        traces=traces,
        preflight=preflight,
        board_manifest=board_manifest,
    )


def _build_specs_from_locked_rows(locked_eval_rows: dict[str, Any]) -> list[dict[str, Any]]:
    rows = list(locked_eval_rows.get("context_target_rows", [])) + list(locked_eval_rows.get("regression_rows", []))
    specs_by_eval = _spec_library()
    specs: list[dict[str, Any]] = []
    for row in rows:
        eval_id = str(row["eval_id"])
        if eval_id not in specs_by_eval:
            raise ValueError(f"unsupported_locked_eval:{eval_id}")
        spec = dict(specs_by_eval[eval_id])
        if eval_id == LONG_ROW_EVAL_ID:
            lane = "long_running_internal_tb_style"
        elif eval_id == "tb_style_verifier_fail_then_repair_v1":
            lane = "completion_closure"
        elif eval_id.startswith("bfcl_v3_"):
            lane = "tooling_bfcl"
        else:
            lane = "context_handoff_answer_extraction"
        spec["lane"] = lane
        spec["admission_level"] = str(row.get("admission_level", "certified"))
        spec["failure_target"] = str(row.get("failure_target", ""))
        spec["positive_capability_target"] = str(row.get("positive_capability_target", ""))
        spec["variant_ids"] = list(ROUTES)
        specs.append(spec)
    return specs


def _spec_library() -> dict[str, dict[str, Any]]:
    specs: dict[str, dict[str, Any]] = {}
    specs.update({row["eval_id"]: row for row in _completion_specs()})
    specs.update({row["eval_id"]: row for row in _context_specs()})
    specs.update({row["eval_id"]: row for row in _bfcl_specs()})
    specs[LONG_ROW_EVAL_ID] = _long_horizon_spec()
    return specs


def _completion_specs() -> list[dict[str, Any]]:
    return [
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
        }
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
    files = {
        f"/letta/filesystem/{path.name}": path.read_text(encoding="utf-8")
        for path in sorted((LETTA_ROOT / "files").glob("*.txt"))
    }
    for index, expected_diff in ((1, "easy"), (2, "medium")):
        row = letta_rows[index]
        difficulty = row.get("agent_args", {}).get("extra", {}).get("difficulty")
        if difficulty != expected_diff:
            raise ValueError(f"locked eval {index} expected {expected_diff}, saw {difficulty}")
        specs.append(
            {
                "eval_id": f"letta_filesystem_{index:03d}_{difficulty}",
                "benchmark_class": "letta_context_bench",
                "task_id": f"filesystem_code_{index:03d}",
                "task_prompt": row["input"].replace("{pwd}", "/letta/filesystem") + "\nReturn one direct answer.",
                "workspace_seed": "simple_files",
                "workspace_files": files,
                "ground_truth": row["ground_truth"],
                "max_steps": 4,
                "timeout_sec": 120,
            }
        )

    specs.append(
        {
            "eval_id": CUSTOM_LONG_HANDOFF_EVAL_ID,
            "benchmark_class": "phase65_context_work_pocket",
            "task_id": CUSTOM_LONG_HANDOFF_EVAL_ID,
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
            "max_steps": 4,
            "timeout_sec": 120,
        }
    )
    return specs


def _bfcl_specs() -> list[dict[str, Any]]:
    rows = json.loads(BFCL_PATH.read_text(encoding="utf-8"))
    by_id = {row["id"]: row for row in rows}
    row = by_id["multi_turn_composite_97"]
    return [
        {
            "eval_id": "bfcl_v3_strict_multi_turn_composite_97",
            "benchmark_class": "bfcl_strict_ground_truth",
            "task_id": row["id"],
            "task_prompt": row["prompt"],
            "workspace_seed": "simple_files",
            "workspace_files": dict(row["files"]),
            "ground_truth": row["ground_truth"],
            "max_steps": 4,
            "timeout_sec": 180,
        }
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


def _route_availability_check() -> dict[str, Any]:
    rows = []
    blockers = []
    baseline = build_packet04_route_manifest(BASELINE_VARIANT_ID, scope=PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE)
    for route_id in ROUTES:
        try:
            manifest = _build_route_manifest(route_id)
            load_runtime_callables(manifest)
            validate_independent_candidate_routing(candidate_manifest=manifest, baseline_manifest=baseline)
            changed = sorted({row["runtime_key"] for row in manifest["routed_modules"] if row.get("claimed_changed_surface")})
            rows.append(
                {
                    "route_id": route_id,
                    "route_role": ROUTE_ROLES[route_id],
                    "status": "pass",
                    "changed_runtime_keys": changed,
                    "route_manifest_fingerprint": manifest["route_manifest_fingerprint"],
                }
            )
        except Exception as exc:
            rows.append({"route_id": route_id, "route_role": ROUTE_ROLES[route_id], "status": "fail", "error": str(exc)})
            blockers.append(f"route_unavailable:{route_id}")
    return {"status": "pass" if not blockers else "fail", "blockers": blockers, "rows": rows}


def _eval_row_availability_check(locked_eval_rows: dict[str, Any], specs: list[dict[str, Any]]) -> dict[str, Any]:
    blockers = []
    locked_ids = [str(row["eval_id"]) for row in locked_eval_rows.get("context_target_rows", [])] + [
        str(row["eval_id"]) for row in locked_eval_rows.get("regression_rows", [])
    ]
    spec_ids = [spec["eval_id"] for spec in specs]
    if locked_ids != spec_ids:
        blockers.append("locked_eval_order_mismatch")
    if len(specs) != 8:
        blockers.append("locked_eval_count_not_8")
    lane_counts = _counts(spec["lane"] for spec in specs)
    expected_lane_counts = {
        "context_handoff_answer_extraction": 5,
        "long_running_internal_tb_style": 1,
        "completion_closure": 1,
        "tooling_bfcl": 1,
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
        missing = []
        for key in ("eval_id", "benchmark_class", "task_id", "task_prompt", "workspace_seed", "variant_ids", "max_steps", "timeout_sec"):
            if key not in spec:
                missing.append(key)
        status = "pass" if not missing else "fail"
        rows.append({"eval_id": spec["eval_id"], "status": status, "missing_fields": missing})
        if missing:
            blockers.append(f"adapter_spec_invalid:{spec['eval_id']}")
    return {"status": "pass" if not blockers else "fail", "blockers": blockers, "rows": rows}


def _execution_mode_disclosure() -> dict[str, Any]:
    return {
        "status": "pass",
        "execution_mode": "sandbox_default",
        "mode_details": {
            "network_restrictions_possible": True,
            "docker_required_for_board": False,
            "outside_sandbox_rerun_applied": False,
            "azure_route_preserved": True,
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
        resolve_packet07_context_model_route()
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
            if name == "azure_dns_network_preflight":
                cls = "infrastructure_invalid_result"
            elif name == "docker_or_fallback":
                cls = "substrate_unavailable_result"
            blockers.append({"check": name, "blocker": item, "interpretation_class": cls})
    return blockers


def _resolve_worker_cap(max_workers: int) -> int:
    if max_workers < 1:
        raise ValueError("max_workers must be >= 1")
    host_cpus = os.cpu_count() or 2
    return max(1, min(max_workers, 4, host_cpus))


def _execute_board(
    out: Path,
    specs: list[dict[str, Any]],
    *,
    max_workers: int,
    model_tier_selector: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
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
            record, trace = _run_with_retry(
                out,
                row["spec"],
                row["variant"],
                model_tier_selector=model_tier_selector,
                plan_index=row["plan_index"],
            )
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
                model_tier_selector=model_tier_selector,
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


def _run_with_retry(
    out: Path,
    spec: dict[str, Any],
    variant: str,
    *,
    model_tier_selector: str,
    plan_index: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    last_record: dict[str, Any] | None = None
    last_trace: dict[str, Any] | None = None
    for attempt in range(2):
        record, trace = _run_one(
            out,
            spec,
            variant,
            attempt=attempt,
            model_tier_selector=model_tier_selector,
            plan_index=plan_index,
        )
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
    model_tier_selector: str,
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
        model_route=resolve_packet07_context_model_route(model_tier_selector=model_tier_selector),
        model_client_kwargs={"timeout_sec": int(spec["timeout_sec"]), "max_retries": 1},
        max_steps=int(spec["max_steps"]),
        timeout_sec=int(spec["timeout_sec"]),
        cwd=workspace,
        route_manifest=_build_route_manifest(variant),
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
        "route_role": ROUTE_ROLES[variant],
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
        "route_role": ROUTE_ROLES[variant],
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


def resolve_packet07_context_model_route(*, model_tier_selector: str = "screening_default") -> dict[str, Any]:
    return resolve_model_route_for_route(
        {
            "execution_mode": "sync_interactive",
            "model_tier_policy": PACKET07_CONTEXT_MODEL_POLICY,
        },
        model_tier_selector=model_tier_selector,
    )


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
        if {
            "verifier_script_missing",
            "missing_solution_file",
            "closure_required_artifact_missing",
            "closure_evidence_omission",
        } & reason_codes:
            return "closure_contract_failure"
        return "task_truth_failure"

    if lane == "context_handoff_answer_extraction":
        if "contextbench_repo_or_file_family_mismatch" in reason_codes:
            row = spec.get("grade_row") or {}
            source_repo = str(row.get("repo_or_file_family", "") or "").strip().lower()
            if source_repo in {"", "none", "null", "nan"}:
                return "derived_field_policy_failure"
        if {"work_pocket_artifact_missing", "work_pocket_artifact_not_json", "work_pocket_final_answer_missing_artifact_path", "work_pocket_final_answer_missing_total"} & reason_codes:
            return "closure_contract_failure"
        if "work_pocket_evidence_paths_mismatch" in reason_codes:
            return "source_grounded_extraction_failure"
        if any(code.startswith("contextbench_") for code in reason_codes) or "letta_ground_truth_mismatch" in reason_codes:
            return "source_grounded_extraction_failure"
        if {"work_pocket_total_mismatch", "work_pocket_not_verified"} & reason_codes:
            return "task_truth_failure"
        return "task_truth_failure"

    if lane == "tooling_bfcl":
        return "task_truth_failure"

    if lane == "long_running_internal_tb_style":
        if {"long_horizon_artifact_missing", "long_horizon_final_answer_missing_artifact_path"} & reason_codes:
            return "closure_contract_failure"
        return "proxy_shaped_failure"

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


def _write_success_artifacts(*, out: Path, records: list[dict[str, Any]], traces: list[dict[str, Any]], preflight: dict[str, Any], board_manifest: dict[str, Any]) -> dict[str, Any]:
    _write_jsonl(out / "packet07_cycle1_context_result_records.jsonl", records)
    score = _score_envelope(records, preflight=preflight, board_manifest=board_manifest)
    trace_report = {"mission_id": MISSION_ID, "run_count": len(traces), "traces": traces}
    failure_report = _failure_source_report(records)
    variant_delta = _variant_delta_report(records, score)
    cost_report = _cost_report(records)
    recommendation = _recommendation_markdown(score, failure_report, variant_delta)
    deep_trace = _deep_trace_analysis(score, failure_report, variant_delta)
    handoff = _handoff(score, failure_report, variant_delta)
    ledger = _raw_ledger_update(out, score, failure_report, variant_delta)

    _write_json(out / "packet07_cycle1_context_score_envelope.json", score)
    _write_json(out / "packet07_cycle1_context_trace_report.json", trace_report)
    _write_json(out / "packet07_cycle1_context_failure_source_report.json", failure_report)
    _write_json(out / "packet07_cycle1_context_variant_delta_report.json", variant_delta)
    _write_json(out / "packet07_cycle1_context_cost_report.json", cost_report)
    _write_text(out / "packet07_cycle1_context_recommendation.md", recommendation)
    _write_text(out / "packet07_cycle1_context_deep_trace_analysis.md", deep_trace)
    _write_text(out / "packet07_cycle1_context_handoff.md", handoff)
    _record_ledger(ledger)
    _write_text(out / "RAW_LEDGER_UPDATE", ledger)
    return {
        "output_dir": str(out),
        "run_count": len(records),
        "model_backed_runs": score["model_backed_runs"],
        "selected_recommendation": score["selected_recommendation"],
    }


def _write_blocked_artifacts(out: Path, *, preflight: dict[str, Any], board_manifest: dict[str, Any]) -> dict[str, Any]:
    _write_jsonl(out / "packet07_cycle1_context_result_records.jsonl", [])
    selected = (
        "context_measurement_or_eval_blocked"
        if any(
            blocker["interpretation_class"] in {"adapter_invalid_result", "substrate_unavailable_result"}
            for blocker in preflight.get("blockers", [])
        )
        else "context_no_signal_shift_target"
    )
    if any(blocker["interpretation_class"] == "infrastructure_invalid_result" for blocker in preflight.get("blockers", [])):
        selected = "context_measurement_or_eval_blocked"
    score = {
        "mission_id": MISSION_ID,
        "run_count": 0,
        "model_backed_runs": 0,
        "planned_model_backed_runs": preflight.get("planned_model_backed_runs", 0),
        "behaviorally_admissible_run_count": 0,
        "invalid_class_counts": _counts(blocker["interpretation_class"] for blocker in preflight.get("blockers", [])),
        "backbone_incumbent": BACKBONE_INcUMBENT,
        "selected_recommendation": selected,
        "preflight": preflight,
        "board_manifest": board_manifest,
    }
    trace_report = {"mission_id": MISSION_ID, "run_count": 0, "traces": [], "preflight_blockers": preflight.get("blockers", [])}
    failure_report = {
        "mission_id": MISSION_ID,
        "blocked": True,
        "dominant_failure_lane": "preflight_blocked",
        "failure_counts_by_interpretation_class": _counts(blocker["interpretation_class"] for blocker in preflight.get("blockers", [])),
        "measurement_blocked_rows": [],
        "infra_blocked_rows": [],
        "records": [],
    }
    variant_delta = {
        "mission_id": MISSION_ID,
        "blocked": True,
        "backbone_incumbent": BACKBONE_INcUMBENT,
        "route_rows": [],
        "new_variant_carry_forward_status": {variant: "not_executed" for variant in MUTATION_VARIANTS},
        "frozen_experimental_status": "not_executed",
    }
    cost_report = {"mission_id": MISSION_ID, "run_count": 0, "total_tokens": 0, "total_usd_estimate": 0.0}
    recommendation = _recommendation_markdown(score, failure_report, variant_delta)
    deep_trace = _deep_trace_analysis(score, failure_report, variant_delta)
    handoff = _handoff(score, failure_report, variant_delta)
    ledger = _raw_ledger_update(out, score, failure_report, variant_delta)

    _write_json(out / "packet07_cycle1_context_score_envelope.json", score)
    _write_json(out / "packet07_cycle1_context_trace_report.json", trace_report)
    _write_json(out / "packet07_cycle1_context_failure_source_report.json", failure_report)
    _write_json(out / "packet07_cycle1_context_variant_delta_report.json", variant_delta)
    _write_json(out / "packet07_cycle1_context_cost_report.json", cost_report)
    _write_text(out / "packet07_cycle1_context_recommendation.md", recommendation)
    _write_text(out / "packet07_cycle1_context_deep_trace_analysis.md", deep_trace)
    _write_text(out / "packet07_cycle1_context_handoff.md", handoff)
    _record_ledger(ledger)
    _write_text(out / "RAW_LEDGER_UPDATE", ledger)
    return {"output_dir": str(out), "run_count": 0, "model_backed_runs": 0, "selected_recommendation": selected, "blocked": True}


def _score_envelope(records: list[dict[str, Any]], *, preflight: dict[str, Any], board_manifest: dict[str, Any]) -> dict[str, Any]:
    admitted = [
        row
        for row in records
        if row["interpretation_class"]
        in {
            "behavioral_pass",
            "closure_contract_failure",
            "task_truth_failure",
            "source_grounded_extraction_failure",
            "derived_field_policy_failure",
            "proxy_shaped_failure",
        }
    ]
    certified = [row for row in admitted if row.get("admission_level") == "certified"]
    route_summary = _route_summary(certified)
    lane_pass_rates = _lane_pass_rates(certified)
    selected_recommendation = _selected_recommendation(certified)
    return {
        "mission_id": MISSION_ID,
        "run_count": len(records),
        "model_backed_runs": sum(1 for row in records if row.get("model_backed")),
        "planned_model_backed_runs": preflight.get("planned_model_backed_runs", 0),
        "behaviorally_admissible_run_count": len(admitted),
        "invalid_class_counts": _counts(
            row["interpretation_class"]
            for row in records
            if row["interpretation_class"] in {"infrastructure_invalid_result", "adapter_invalid_result", "substrate_unavailable_result"}
        ),
        "scoreboard_verdict_counts": _counts(row["scoreboard_verdict"] for row in records),
        "certified_lane_pass_rates": lane_pass_rates,
        "route_summary_certified_only": route_summary,
        "backbone_incumbent": BACKBONE_INcUMBENT,
        "selected_recommendation": selected_recommendation,
        "preflight": preflight,
        "board_manifest": board_manifest,
    }


def _failure_source_report(records: list[dict[str, Any]]) -> dict[str, Any]:
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
            row["run_id"]
            for row in records
            if row["interpretation_class"] in {"infrastructure_invalid_result", "substrate_unavailable_result", "adapter_invalid_result"}
        ],
        "real_context_failure_rows": [
            row["run_id"]
            for row in records
            if row["lane"] == "context_handoff_answer_extraction"
            and row["interpretation_class"] in {"closure_contract_failure", "source_grounded_extraction_failure", "task_truth_failure"}
        ],
        "diagnostic_long_row_ids": [row["run_id"] for row in records if row["eval_id"] == LONG_ROW_EVAL_ID],
    }


def _variant_delta_report(records: list[dict[str, Any]], score: dict[str, Any]) -> dict[str, Any]:
    certified = [row for row in records if row.get("admission_level") == "certified"]
    backbone_summary = _route_eval_summary(certified, BACKBONE_INcUMBENT)
    rows = []
    carry_forward_status: dict[str, str] = {}
    for route_id in ROUTES:
        summary = _route_eval_summary(certified, route_id)
        row = {
            "route_id": route_id,
            "route_role": ROUTE_ROLES[route_id],
            "certified_pass": summary["certified_pass"],
            "certified_fail": summary["certified_fail"],
            "context_certified_pass": summary["context_pass"],
            "completion_regression_pass": summary["completion_regression_pass"],
            "completion_regression_fail": summary["completion_regression_fail"],
            "bfcl_regression_pass": summary["bfcl_regression_pass"],
            "bfcl_regression_fail": summary["bfcl_regression_fail"],
            "custom_long_handoff_pass": summary["custom_long_handoff_pass"],
            "delta_vs_backbone_context_pass": summary["context_pass"] - backbone_summary["context_pass"],
            "delta_vs_backbone_total_pass": summary["certified_pass"] - backbone_summary["certified_pass"],
        }
        rows.append(row)
        if route_id in MUTATION_VARIANTS:
            carry_forward_status[route_id] = (
                "earned_carry_forward"
                if row["delta_vs_backbone_context_pass"] > 0
                and row["completion_regression_fail"] == 0
                and row["bfcl_regression_fail"] == 0
                else "partial_signal"
                if row["delta_vs_backbone_context_pass"] >= 0 or row["custom_long_handoff_pass"]
                else "not_earned"
            )
    frozen_summary = _route_eval_summary(certified, FROZEN_EXPERIMENTAL_REFERENCE)
    governed_summary = _route_eval_summary(certified, GOVERNED_CONTEXT_REFERENCE)
    frozen_status = (
        "improved_enough_to_reconsider"
        if frozen_summary["context_pass"] > governed_summary["context_pass"]
        and frozen_summary["completion_regression_fail"] == 0
        and frozen_summary["bfcl_regression_fail"] == 0
        else "confirm_freeze"
    )
    return {
        "mission_id": MISSION_ID,
        "backbone_incumbent": BACKBONE_INcUMBENT,
        "route_rows": rows,
        "new_variant_carry_forward_status": carry_forward_status,
        "frozen_experimental_status": frozen_status,
    }


def _cost_report(records: list[dict[str, Any]]) -> dict[str, Any]:
    total_tokens = 0
    total_usd = 0.0
    by_route: dict[str, dict[str, float]] = defaultdict(lambda: {"total_tokens": 0.0, "total_usd_estimate": 0.0})
    for row in records:
        usage = row.get("token_and_cost_summary", {})
        tokens = int(usage.get("total_tokens", 0) or 0)
        usd = float(usage.get("usd_estimate", usage.get("usd", 0.0)) or 0.0)
        total_tokens += tokens
        total_usd += usd
        by_route[row["variant_id"]]["total_tokens"] += tokens
        by_route[row["variant_id"]]["total_usd_estimate"] += usd
    return {
        "mission_id": MISSION_ID,
        "run_count": len(records),
        "total_tokens": total_tokens,
        "total_usd_estimate": total_usd,
        "by_route": by_route,
    }


def _recommendation_markdown(score: dict[str, Any], failure_report: dict[str, Any], variant_delta: dict[str, Any]) -> str:
    route_rows = {row["route_id"]: row for row in variant_delta.get("route_rows", [])}
    work_pocket = route_rows.get(MUTATION_VARIANTS[0], {})
    closure_guard = route_rows.get(MUTATION_VARIANTS[1], {})
    frozen_status = variant_delta.get("frozen_experimental_status", "confirm_freeze")
    selected = score.get("selected_recommendation", "context_no_signal_shift_target")
    best_new = _best_new_variant(variant_delta)
    context_viable = selected in {
        "context_repair_viable_continue_packet07",
        "context_repair_partial_continue_one_more_context_cycle",
    }
    real_context_failures = failure_report.get("real_context_failure_rows", [])
    measurement_rows = failure_report.get("measurement_blocked_rows", [])
    lines = [
        "# Packet 07 Cycle 1 Context Recommendation",
        "",
        f"1. Is context repair viable? {'Yes, but only partially so far.' if context_viable else 'No clear viable shift this cycle.'}",
        f"2. Which new context variant, if any, earned carry-forward status? {best_new or 'None.'}",
        f"3. Did work-pocket + answer projection help? {'Yes.' if work_pocket_helped(work_pocket) else 'No material help.'}",
        f"4. Did answer-closure guard help? {'Yes.' if work_pocket_helped(closure_guard) else 'No material help.'}",
        f"5. Did the frozen experimental Structured Observation Register route remain frozen, improve enough to reconsider, or confirm freeze? {frozen_status}.",
        f"6. Which failures were real context failures? {len(real_context_failures)} rows classified as closure-contract, source-grounded extraction, or task-truth failures in the context lane.",
        f"7. Which failures were measurement-shaped? {len(measurement_rows)} rows classified as derived-field policy or proxy-shaped failures.",
        f"8. Did the new context work regress completion or BFCL? {'Yes.' if _has_regression(variant_delta) else 'No certified completion/BFCL regression on the admitted new variants.'}",
        f"9. What should Packet 07 do next? {selected}.",
        "",
        selected,
    ]
    return "\n".join(lines) + "\n"


def _deep_trace_analysis(score: dict[str, Any], failure_report: dict[str, Any], variant_delta: dict[str, Any]) -> str:
    route_rows = {row["route_id"]: row for row in variant_delta.get("route_rows", [])}
    lines = [
        "# Packet 07 Cycle 1 Context Deep Trace Analysis",
        "",
        f"- backbone_incumbent: `{BACKBONE_INcUMBENT}`",
        f"- governed_context_reference: `{GOVERNED_CONTEXT_REFERENCE}`",
        f"- frozen_experimental_reference: `{FROZEN_EXPERIMENTAL_REFERENCE}`",
        f"- selected_recommendation: `{score.get('selected_recommendation')}`",
        "",
        "## Context Viability",
        "",
        f"- behaviorally_admissible_run_count: `{score.get('behaviorally_admissible_run_count')}`",
        f"- failure_counts_by_interpretation_class: `{failure_report.get('failure_counts_by_interpretation_class')}`",
        f"- real_context_failure_rows: `{len(failure_report.get('real_context_failure_rows', []))}`",
        f"- measurement_blocked_rows: `{len(failure_report.get('measurement_blocked_rows', []))}`",
        "",
        "## Variant Deltas",
        "",
        f"- work_pocket_answer_projection: `{route_rows.get(MUTATION_VARIANTS[0], {})}`",
        f"- context_answer_closure_guard: `{route_rows.get(MUTATION_VARIANTS[1], {})}`",
        f"- frozen_experimental_status: `{variant_delta.get('frozen_experimental_status')}`",
        "",
        "## Regression Guard",
        "",
        f"- completion_lane_pass_rates: `{score.get('certified_lane_pass_rates', {}).get('completion_closure')}`",
        f"- bfcl_lane_pass_rates: `{score.get('certified_lane_pass_rates', {}).get('tooling_bfcl')}`",
        "",
        "## Required Final Answers",
        "",
        f"1. context repair viable: `{score.get('selected_recommendation') in {'context_repair_viable_continue_packet07', 'context_repair_partial_continue_one_more_context_cycle'}}`",
        f"2. carry-forward new variant: `{_best_new_variant(variant_delta)}`",
        f"3. work-pocket answer projection helped: `{work_pocket_helped(route_rows.get(MUTATION_VARIANTS[0], {}))}`",
        f"4. answer-closure guard helped: `{work_pocket_helped(route_rows.get(MUTATION_VARIANTS[1], {}))}`",
        f"5. frozen route status: `{variant_delta.get('frozen_experimental_status')}`",
        f"6. real context failure rows: `{len(failure_report.get('real_context_failure_rows', []))}`",
        f"7. measurement-shaped rows: `{len(failure_report.get('measurement_blocked_rows', []))}`",
        f"8. certified regression detected: `{_has_regression(variant_delta)}`",
        f"9. next packet recommendation: `{score.get('selected_recommendation')}`",
    ]
    return "\n".join(lines) + "\n"


def _handoff(score: dict[str, Any], failure_report: dict[str, Any], variant_delta: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Packet 07 Cycle 1 Context Handoff",
            "",
            f"- mission_id: `{MISSION_ID}`",
            f"- run_count: `{score.get('run_count')}`",
            f"- model_backed_runs: `{score.get('model_backed_runs')}`",
            f"- behaviorally_admissible_run_count: `{score.get('behaviorally_admissible_run_count')}`",
            f"- selected_recommendation: `{score.get('selected_recommendation')}`",
            f"- backbone_incumbent: `{BACKBONE_INcUMBENT}`",
            f"- best_new_variant: `{_best_new_variant(variant_delta)}`",
            f"- dominant_failure_lane: `{failure_report.get('dominant_failure_lane')}`",
            "",
            "Required artifacts produced:",
            "- packet07_cycle1_context_result_records.jsonl",
            "- packet07_cycle1_context_score_envelope.json",
            "- packet07_cycle1_context_trace_report.json",
            "- packet07_cycle1_context_failure_source_report.json",
            "- packet07_cycle1_context_variant_delta_report.json",
            "- packet07_cycle1_context_cost_report.json",
            "- packet07_cycle1_context_recommendation.md",
            "- packet07_cycle1_context_deep_trace_analysis.md",
            "- packet07_cycle1_context_handoff.md",
            "- RAW_LEDGER_UPDATE",
        ]
    ) + "\n"


def _raw_ledger_update(out: Path, score: dict[str, Any], failure_report: dict[str, Any], variant_delta: dict[str, Any]) -> str:
    return "\n".join(
        [
            "RAW_LEDGER_UPDATE",
            "- actor: codex",
            "- task: Packet 07 Cycle 1 context targeted autoresearch",
            "- event_type: experiment",
            (
                f"- summary: Executed or preflight-blocked Packet 07 Cycle 1 context board with recommendation "
                f"`{score.get('selected_recommendation')}`."
            ),
            (
                "- observations: "
                f"run_count `{score.get('run_count', 0)}`; model_backed_runs `{score.get('model_backed_runs', 0)}`; "
                f"behaviorally_admissible_run_count `{score.get('behaviorally_admissible_run_count', 0)}`; "
                f"real_context_failure_rows `{len(failure_report.get('real_context_failure_rows', []))}`; "
                f"measurement_blocked_rows `{len(failure_report.get('measurement_blocked_rows', []))}`; "
                f"best_new_variant `{_best_new_variant(variant_delta)}`."
            ),
            "- inference: Cycle 1 tests whether bounded context-targeted projection and closure-guard variants can improve context behavior without regressing the backbone completion/BFCL anchors.",
            (
                f"- evidence_paths: {out / 'packet07_cycle1_context_result_records.jsonl'}; "
                f"{out / 'packet07_cycle1_context_score_envelope.json'}; "
                f"{out / 'packet07_cycle1_context_failure_source_report.json'}; "
                f"{out / 'packet07_cycle1_context_variant_delta_report.json'}; "
                f"{out / 'packet07_cycle1_context_recommendation.md'}; "
                f"{out / 'packet07_cycle1_context_handoff.md'}"
            ),
            "- affected_components: Packet07 Cycle1 runner; local context-route overrides; context-targeted measurement outputs",
            "- decision_change: Admitted two bounded context-targeted variants focused on work-pocket answer projection and answer-closure discipline while keeping the frozen experimental route as reference only.",
            "- unresolved_questions: Whether one more bounded context cycle should favor the stronger of the two new variants alone or combine the winner with a narrower long-handoff exactness import.",
            "- confidence: medium",
            "- commit_message: HOLD - implement Packet 07 Cycle 1 context-targeted runner and artifacts",
        ]
    )


def _route_summary(records: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for row in records:
        bucket = out.setdefault(row["variant_id"], {"run_count": 0, "pass": 0, "fail": 0, "invalid": 0})
        bucket["run_count"] += 1
        bucket[row["scoreboard_verdict"]] = bucket.get(row["scoreboard_verdict"], 0) + 1
    return out


def _lane_pass_rates(records: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        grouped[row["lane"]].append(row)
    out: dict[str, dict[str, float]] = {}
    for lane, rows in grouped.items():
        passes = sum(1 for row in rows if row["scoreboard_verdict"] == "pass")
        out[lane] = {"pass_count": passes, "run_count": len(rows), "pass_rate": passes / len(rows) if rows else 0.0}
    return out


def _route_eval_summary(records: list[dict[str, Any]], route_id: str) -> dict[str, int]:
    scoped = [row for row in records if row["variant_id"] == route_id]
    return {
        "certified_pass": sum(1 for row in scoped if row["scoreboard_verdict"] == "pass"),
        "certified_fail": sum(1 for row in scoped if row["scoreboard_verdict"] == "fail"),
        "context_pass": sum(
            1 for row in scoped if row["lane"] == "context_handoff_answer_extraction" and row["scoreboard_verdict"] == "pass"
        ),
        "completion_regression_pass": sum(
            1 for row in scoped if row["eval_id"] == "tb_style_verifier_fail_then_repair_v1" and row["scoreboard_verdict"] == "pass"
        ),
        "completion_regression_fail": sum(
            1 for row in scoped if row["eval_id"] == "tb_style_verifier_fail_then_repair_v1" and row["scoreboard_verdict"] != "pass"
        ),
        "bfcl_regression_pass": sum(
            1 for row in scoped if row["eval_id"] == "bfcl_v3_strict_multi_turn_composite_97" and row["scoreboard_verdict"] == "pass"
        ),
        "bfcl_regression_fail": sum(
            1 for row in scoped if row["eval_id"] == "bfcl_v3_strict_multi_turn_composite_97" and row["scoreboard_verdict"] != "pass"
        ),
        "custom_long_handoff_pass": sum(
            1 for row in scoped if row["eval_id"] == CUSTOM_LONG_HANDOFF_EVAL_ID and row["scoreboard_verdict"] == "pass"
        ),
    }


def _selected_recommendation(certified: list[dict[str, Any]]) -> str:
    if not certified:
        return "context_measurement_or_eval_blocked"
    measurement_blocked = [
        row
        for row in certified
        if row["lane"] == "context_handoff_answer_extraction"
        and row["interpretation_class"] in {"derived_field_policy_failure", "proxy_shaped_failure"}
    ]
    context_rows = [row for row in certified if row["lane"] == "context_handoff_answer_extraction"]
    if context_rows and len(measurement_blocked) >= max(1, len(context_rows) // 2):
        return "context_measurement_or_eval_blocked"
    by_route = {route: _route_eval_summary(certified, route) for route in ROUTES}
    viable = []
    partial = []
    for route in MUTATION_VARIANTS:
        summary = by_route[route]
        if (
            summary["context_pass"] > by_route[BACKBONE_INcUMBENT]["context_pass"]
            and summary["completion_regression_fail"] == 0
            and summary["bfcl_regression_fail"] == 0
        ):
            viable.append(route)
        elif (
            summary["context_pass"] >= by_route[BACKBONE_INcUMBENT]["context_pass"]
            or summary["custom_long_handoff_pass"] > 0
        ):
            partial.append(route)
    if viable:
        return "context_repair_viable_continue_packet07"
    if partial:
        return "context_repair_partial_continue_one_more_context_cycle"
    return "context_no_signal_shift_target"


def _best_new_variant(variant_delta: dict[str, Any]) -> str | None:
    rows = [row for row in variant_delta.get("route_rows", []) if row["route_id"] in MUTATION_VARIANTS]
    if not rows:
        return None
    ranked = max(
        rows,
        key=lambda row: (
            row["context_certified_pass"],
            row["custom_long_handoff_pass"],
            row["completion_regression_pass"],
            row["bfcl_regression_pass"],
            row["route_id"] == MUTATION_VARIANTS[0],
        ),
    )
    status = variant_delta.get("new_variant_carry_forward_status", {}).get(ranked["route_id"])
    if status == "not_earned" and ranked["context_certified_pass"] == 0 and ranked["custom_long_handoff_pass"] == 0:
        return None
    return ranked["route_id"]


def work_pocket_helped(route_row: dict[str, Any]) -> bool:
    return bool(
        route_row
        and (
            route_row.get("delta_vs_backbone_context_pass", 0) > 0
            or route_row.get("custom_long_handoff_pass", 0) > 0
        )
    )


def _has_regression(variant_delta: dict[str, Any]) -> bool:
    for row in variant_delta.get("route_rows", []):
        if row["route_id"] not in MUTATION_VARIANTS:
            continue
        if row["completion_regression_fail"] > 0 or row["bfcl_regression_fail"] > 0:
            return True
    return False


def _grader_available_for_spec(spec: dict[str, Any]) -> bool:
    return spec["benchmark_class"] in {
        "contextbench",
        "letta_context_bench",
        "phase65_context_work_pocket",
        "phase65_completion_verifier_repair",
        "bfcl_strict_ground_truth",
        "packet07_internal_long_horizon_diagnostic",
    }


def _counts(values: Any) -> dict[str, int]:
    out: dict[str, int] = {}
    for value in values:
        out[str(value)] = out.get(str(value), 0) + 1
    return out


def _board_manifest(specs: list[dict[str, Any]], mutation_policy: dict[str, Any]) -> dict[str, Any]:
    return {
        "mission_id": MISSION_ID,
        "comparison_set": list(ROUTES),
        "route_roles": ROUTE_ROLES,
        "required_eval_ids": [spec["eval_id"] for spec in specs],
        "context_target_eval_ids": [spec["eval_id"] for spec in specs if spec["lane"] in {"context_handoff_answer_extraction", "long_running_internal_tb_style"}],
        "regression_eval_ids": [spec["eval_id"] for spec in specs if spec["lane"] in {"completion_closure", "tooling_bfcl"}],
        "max_new_variants": mutation_policy.get("max_new_variants"),
        "must_target_lane": mutation_policy.get("must_target_lane"),
        "authority": _authority(),
    }


def _build_route_manifest(route_id: str) -> dict[str, Any]:
    if route_id not in LOCAL_ROUTE_OVERRIDES:
        return build_packet04_route_manifest(route_id, scope=PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE)
    override = LOCAL_ROUTE_OVERRIDES[route_id]
    manifest = deepcopy(build_packet04_route_manifest(override["base_variant"], scope=PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE))
    for entry in manifest["routed_modules"]:
        entry["variant_id"] = route_id
        module_override = override["modules"].get(entry["runtime_key"])
        if not module_override:
            continue
        file_rel = Path(module_override["file_rel"])
        real_path = (Path.cwd() / file_rel).resolve()
        if not real_path.exists():
            raise ValueError(f"local route surface missing: {real_path}")
        entry["declared_card_path"] = str(file_rel)
        entry["real_file_path"] = str(real_path)
        entry["module_import_path"] = str(module_override["module_import_path"])
        entry["file_sha256"] = hashlib.sha256(real_path.read_bytes()).hexdigest()
    manifest["variant_id"] = route_id
    manifest["variant_card_ref"] = None
    manifest["route_manifest_fingerprint"] = hashlib.sha256(
        json.dumps(
            {
                "route_scope": manifest["route_scope"],
                "variant_id": route_id,
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


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--no-execute", action="store_true")
    parser.add_argument("--max-workers", type=int, default=DEFAULT_MAX_WORKERS)
    parser.add_argument("--model-tier-selector", choices=MODEL_TIER_SELECTORS, default="screening_default")
    args = parser.parse_args(argv)
    print(
        json.dumps(
            launch_packet07_cycle1(
                output_dir=args.output_dir,
                execute=not args.no_execute,
                max_workers=args.max_workers,
                model_tier_selector=args.model_tier_selector,
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
