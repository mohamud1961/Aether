#!/usr/bin/env python3
"""Run BFCL native adapter smoke rows and aggregate scoreboard output."""

from __future__ import annotations

import argparse
import ast
import json
import shutil
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from runner.benchmark_adapter_bfcl_native import (
    ADAPTER_AUTHORITY_DETAIL,
    ADAPTER_AUTHORITY_LABEL,
    ADAPTER_LABEL,
    build_benchmark_case,
    build_result_row_for_grade,
    build_task_pack,
    flatten_ground_truth_calls,
    grade_bfcl_case_native,
    load_official_curated_cases,
    native_grader_preflight,
    supported_case,
)
from runner.eval_substrate_contracts import validate_task_pack
from runner.eval_substrate_scoreboard import aggregate_result_rows

DEFAULT_OUTPUT_ROOT = Path("tracking/collab/native_bfcl_adapter_upgrade/smoke_v1")
DEFAULT_CASE_ID = "multi_turn_composite_97"
CONTROL_CASES = ("pass", "known_bad", "ceiling")


def run_benchmark_adapter_bfcl_native_smoke(
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    *,
    case_id: str = DEFAULT_CASE_ID,
) -> dict[str, Any]:
    output_root = output_root.resolve()
    if output_root.exists():
        shutil.rmtree(output_root)
    (output_root / "result_rows").mkdir(parents=True, exist_ok=True)

    preflight = native_grader_preflight()
    preflight_path = _write_json(output_root / "native_grader_preflight.json", preflight)

    cases = load_official_curated_cases()
    case = cases.get(case_id)
    if case is None:
        raise ValueError(f"bfcl official curated case not found: {case_id}")
    if not supported_case(case):
        raise ValueError(f"bfcl official curated case uses unsupported classes: {case_id}")

    task_pack = build_task_pack(task_pack_id="bfcl-native-v3-smoke", case_id=case_id)
    validate_task_pack(task_pack)
    task_pack_path = _write_json(output_root / "task_pack.json", task_pack)
    benchmark_case_path = _write_json(
        output_root / "benchmark_case_contract.json",
        build_benchmark_case(case_id=case_id, task_pack_id=task_pack["task_id"]),
    )
    expected_calls = flatten_ground_truth_calls(case)

    rows: list[dict[str, Any]] = []
    for control_label in CONTROL_CASES:
        run_root = output_root / "runs" / control_label
        observed_calls = _observed_calls_for_control(control_label, expected_calls)
        grade = grade_bfcl_case_native(case, observed_calls)
        verifier_ref = _write_json(
            run_root / "artifacts" / "verifier_output.json",
            {
                "control_label": control_label,
                "observed_call_count": len(observed_calls),
                "observed_calls_hash": grade.get("observed_calls_hash"),
                "native_runtime_mode": preflight["native_runtime_mode"],
                "authority_label": ADAPTER_AUTHORITY_LABEL,
                "authority_detail": ADAPTER_AUTHORITY_DETAIL,
            },
        )
        grader_ref = _write_json(
            run_root / "artifacts" / "grader_output.json",
            {
                "control_label": control_label,
                "grade": grade,
                "authority_label": ADAPTER_AUTHORITY_LABEL,
                "authority_detail": ADAPTER_AUTHORITY_DETAIL,
            },
        )
        trace_ref = _write_json(
            run_root / "traces" / "trace.json",
            {
                "control_label": control_label,
                "tool_io": [{"tool": "bfcl_native_adapter", "observed_call_count": len(observed_calls)}],
                "visible_model_messages": ["BFCL native adapter smoke; official state-replay grading"],
            },
        )
        artifact_bundle_ref = _write_json(
            run_root / "artifacts" / "artifact_bundle.json",
            {
                "control_label": control_label,
                "adapter_label": ADAPTER_LABEL,
                "authority_label": ADAPTER_AUTHORITY_LABEL,
                "authority_detail": ADAPTER_AUTHORITY_DETAIL,
                "hidden_truth_ref": task_pack["benchmark_adapter_contract"]["hidden_truth_ref"],
                "native_grader_preflight_ref": str(preflight_path),
                "environment_manifest_ref": "debug://local_no_sandbox",
                "verifier_ref": str(verifier_ref),
                "grader_ref": str(grader_ref),
                "trace_refs": [str(trace_ref)],
            },
        )
        row = build_result_row_for_grade(
            run_id=f"bfcl-native-smoke-{control_label}",
            eval_id="bfcl-native-adapter-smoke",
            task_pack_id=task_pack["task_id"],
            case_id=case_id,
            control_label=control_label,
            environment_ref="debug://local_no_sandbox",
            artifact_refs=[str(artifact_bundle_ref)],
            trace_refs=[str(trace_ref)],
            verifier_ref=str(verifier_ref),
            grader_ref=str(grader_ref),
            grade=grade,
        )
        if control_label == "ceiling" and row["task_truth_status"] == "pass":
            row["reason_codes"] = ["ceiling_passed"]
        _write_json(output_root / "result_rows" / f"{control_label}.json", row)
        rows.append(row)

    scoreboard = aggregate_result_rows(rows)
    scoreboard_path = _write_json(output_root / "scoreboard.json", scoreboard)
    summary = {
        "adapter_label": ADAPTER_LABEL,
        "authority_mode": ADAPTER_AUTHORITY_LABEL,
        "task_pack_path": str(task_pack_path),
        "benchmark_case_contract_path": str(benchmark_case_path),
        "native_grader_preflight_path": str(preflight_path),
        "result_row_dir": str(output_root / "result_rows"),
        "scoreboard_output_path": str(scoreboard_path),
        "row_count": len(rows),
        "output_authority_label": ADAPTER_AUTHORITY_LABEL,
        "output_authority_detail": ADAPTER_AUTHORITY_DETAIL,
        "certification_claim": "none; BFCL native adapter debug run is non-certifying",
    }
    _write_json(output_root / "run_summary.json", summary)
    return summary


def _observed_calls_for_control(control_label: str, expected_calls: list[str]) -> list[str]:
    if control_label == "ceiling":
        return list(expected_calls)
    if control_label == "pass":
        return list(expected_calls)
    return []


def _render_semantic_variant(raw_call: str) -> str:
    parsed = ast.parse(raw_call.strip(), mode="eval")
    if not isinstance(parsed.body, ast.Call) or not isinstance(parsed.body.func, ast.Name):
        return raw_call
    call = parsed.body
    arg_parts: list[str] = []
    for node in call.args:
        arg_parts.append(ast.unparse(node))
    keyword_nodes = list(call.keywords)
    keyword_nodes.reverse()
    for keyword in keyword_nodes:
        if keyword.arg is None:
            return raw_call
        arg_parts.append(f"{keyword.arg} = {ast.unparse(keyword.value)}")
    rendered = ", ".join(arg_parts)
    return f"{call.func.id}( {rendered} )"


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--case-id", default=DEFAULT_CASE_ID)
    args = parser.parse_args()
    summary = run_benchmark_adapter_bfcl_native_smoke(Path(args.output_root), case_id=args.case_id)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
