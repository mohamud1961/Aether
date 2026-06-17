"""Packet 07 follow-up: hard-row answer-robustness helper vs control."""

from __future__ import annotations

import argparse
import hashlib
import json
from copy import deepcopy
from pathlib import Path
from time import perf_counter
from typing import Any

from runner.agent import run_reference_baseline
from runner.packet04_route_manifest import (
    BASELINE_VARIANT_ID,
    PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE,
    build_packet04_route_manifest,
    load_runtime_callables,
    validate_independent_candidate_routing,
)
from runner.packet07_cycle1_context_targeted_autoresearch import (
    BACKBONE_INCUMBENT,
    MODEL_TIER_SELECTORS,
    _authority,
    _azure_dns_network_preflight,
    _bfcl_specs,
    _context_specs,
    _docker_or_fallback_preflight,
    _is_adapter_invalid,
    _is_infrastructure_invalid,
    _record_ledger,
    _seed_workspace,
    _usage,
    _write_json,
    _write_jsonl,
    _write_text,
)
from runner.packet07_golden_diagnostic import _orientation_env, _tool_trace_fields
from runner.packet07_hard_row_robustness_probe import _build_hard_spec
from runner.packet07_original_surface_reduce_select_eval import (
    EVAL_ID as PROPER_EVAL_ID,
    _deterministic_ceiling as _proper_eval_deterministic_ceiling,
    _spec as _proper_eval_spec,
    grade_original_surface_reduce_select_answer,
)
from runner.phase65_measurement_grading import grade_phase65_spec
from runner.schemas import utc_now

MISSION_ID = "packet07_hard_row_answer_robustness_followup"
DEFAULT_OUTPUT_DIR = Path(
    "tracking/collab/stage_03_execution_planning/packets/packet_06_paired_combo_variants/"
    "runs/2026-05-13_packet07_hard_row_answer_robustness_followup"
)
MODEL_ID = "gpt-5.4-mini"
CONTROL_ROUTE_ID = str(BACKBONE_INCUMBENT)
HELPER_ROUTE_ID = "candidate_plus_path_normalized_reduction_discipline_guard_01"
ROUTE_IDS = (CONTROL_ROUTE_ID, HELPER_ROUTE_ID)
PRIMARY_EVAL_ID = "letta_filesystem_008_hard"
PROPER_EVAL_BUDGET = 15
PROPER_EVAL_REPEATS = 3
SENTINEL_EVAL_IDS = (
    "letta_filesystem_001_easy",
    "letta_filesystem_002_medium",
    "bfcl_v3_strict_multi_turn_composite_97",
)
PRIMARY_BUDGETS = (15, 25)
PRIMARY_REPEATS = 3
SENTINEL_REPEATS = 1
LETTA_ARM = {
    "arm_id": "fair_runtime_orientation_python3",
    "inject_orientation": True,
    "python_contract": True,
}
PLAIN_ARM = {
    "arm_id": "standard",
    "inject_orientation": False,
    "python_contract": False,
}
PYTHON3_CONTRACT_PROMPT = (
    "\nUse source-grounded shell inspection. Python contract: when Python is needed, use `python3` explicitly."
)
INVALID_INTERPRETATION_CLASSES = {"infrastructure_invalid_result", "adapter_invalid_result", "substrate_unavailable_result"}
FAILURE_CLASSES = {
    "provider_contaminated",
    "reduction_error",
    "dispatch_failure",
    "premature_answer",
    "evidence_acquisition",
    "unknown",
}
LOCAL_ROUTE_OVERRIDES = {
    HELPER_ROUTE_ID: {
        "base_variant": CONTROL_ROUTE_ID,
        "modules": {
            "orientation": {
                "file_rel": "blocks/orientation/packet07_hard_row_doctrine.py",
                "module_import_path": "blocks.orientation.packet07_hard_row_doctrine:orient",
            },
            "context": {
                "file_rel": "blocks/context/reduction_discipline_answer_guard.py",
                "module_import_path": "blocks.context.reduction_discipline_answer_guard:manage",
            },
        },
    }
}


def launch_packet07_hard_row_answer_robustness(
    *,
    output_dir: str | Path,
    execute: bool = True,
    repeats: int = PRIMARY_REPEATS,
) -> dict[str, Any]:
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    metadata = prepare_followup_metadata(repeats=repeats)
    preflight = {
        "mission_id": MISSION_ID,
        "checks": {
            "route_availability": _route_availability_check(),
            "azure_dns_network_preflight": _azure_dns_network_preflight(),
            "docker_or_fallback": _docker_or_fallback_preflight(metadata["specs"]),
        },
    }
    blockers = _collect_preflight_blockers(preflight)
    preflight["status"] = "pass" if not blockers else "blocked"
    preflight["blockers"] = blockers
    preflight["planned_model_backed_runs"] = len(metadata["plan"])
    _write_json(out / "packet07_hard_row_answer_robustness_run_spec.json", metadata)
    _write_json(out / "packet07_hard_row_answer_robustness_preflight.json", preflight)

    if not execute or preflight["status"] != "pass":
        return _write_bundle(out=out, metadata=metadata, preflight=preflight, records=[], blocked=True)

    records = [_run_one(out=out, spec_map=metadata["spec_map"], plan_row=row) for row in metadata["plan"]]
    return _write_bundle(out=out, metadata=metadata, preflight=preflight, records=records, blocked=False)


def prepare_followup_metadata(*, repeats: int = PRIMARY_REPEATS) -> dict[str, Any]:
    if repeats <= 0:
        raise ValueError("repeats_must_be_positive")
    spec_map = _build_spec_map()
    plan = _prepare_plan(spec_map=spec_map, repeats=repeats)
    return {
        "mission_id": MISSION_ID,
        "model_id": MODEL_ID,
        "control_route_id": CONTROL_ROUTE_ID,
        "helper_route_id": HELPER_ROUTE_ID,
        "spec_map": spec_map,
        "specs": [
            spec_map[PROPER_EVAL_ID],
            spec_map[PRIMARY_EVAL_ID],
            *(spec_map[eval_id] for eval_id in SENTINEL_EVAL_IDS),
        ],
        "plan": plan,
        "authority": _authority(),
    }


def _build_spec_map() -> dict[str, dict[str, Any]]:
    specs = {row["eval_id"]: dict(row) for row in [*_context_specs(), *_bfcl_specs()]}
    proper_eval_contract = _proper_eval_spec()
    specs[PROPER_EVAL_ID] = {
        "eval_id": PROPER_EVAL_ID,
        "task_id": PROPER_EVAL_ID,
        "task_prompt": str(proper_eval_contract["task_contract"]["task_prompt"]),
        "workspace_files": dict(proper_eval_contract["workspace_files"]),
        "benchmark_class": "packet07_original_surface",
        "max_steps": PROPER_EVAL_BUDGET,
        "timeout_sec": 120,
        "lane": "proper_eval_original_surface",
    }
    hard = _build_hard_spec()
    hard["lane"] = "primary_hard_row"
    specs[PRIMARY_EVAL_ID] = hard
    return specs


def _prepare_plan(*, spec_map: dict[str, dict[str, Any]], repeats: int) -> list[dict[str, Any]]:
    plan: list[dict[str, Any]] = []
    for route_id in ROUTE_IDS:
        for run_index in range(1, PROPER_EVAL_REPEATS + 1):
            plan.append(
                {
                    "eval_id": PROPER_EVAL_ID,
                    "model_id": MODEL_ID,
                    "route_id": route_id,
                    "budget": PROPER_EVAL_BUDGET,
                    "run_index": run_index,
                    "segment": "proper_eval_original_surface",
                    "fair_runtime": False,
                }
            )
        for budget in PRIMARY_BUDGETS:
            for run_index in range(1, repeats + 1):
                plan.append(
                    {
                        "eval_id": PRIMARY_EVAL_ID,
                        "model_id": MODEL_ID,
                        "route_id": route_id,
                        "budget": int(budget),
                        "run_index": run_index,
                        "segment": "primary_hard_row",
                        "fair_runtime": True,
                    }
                )
        for eval_id in SENTINEL_EVAL_IDS:
            spec = spec_map[eval_id]
            fair_runtime = bool(eval_id.startswith("letta_filesystem_"))
            budget = 15 if fair_runtime else int(spec.get("max_steps", 4))
            for run_index in range(1, SENTINEL_REPEATS + 1):
                plan.append(
                    {
                        "eval_id": eval_id,
                        "model_id": MODEL_ID,
                        "route_id": route_id,
                        "budget": int(budget),
                        "run_index": run_index,
                        "segment": "regression_sentinel",
                        "fair_runtime": fair_runtime,
                    }
                )
    return plan


def _route_availability_check() -> dict[str, Any]:
    baseline = build_packet04_route_manifest(BASELINE_VARIANT_ID, scope=PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE)
    rows: list[dict[str, Any]] = []
    blockers: list[str] = []
    for route_id in ROUTE_IDS:
        try:
            manifest = _build_route_manifest(route_id)
            load_runtime_callables(manifest)
            validate_independent_candidate_routing(candidate_manifest=manifest, baseline_manifest=baseline)
            rows.append({"route_id": route_id, "status": "pass", "route_manifest_fingerprint": manifest["route_manifest_fingerprint"]})
        except Exception as exc:  # pragma: no cover - preflight-only branch
            rows.append({"route_id": route_id, "status": "fail", "error": str(exc)})
            blockers.append(f"route_unavailable:{route_id}")
    return {"status": "pass" if not blockers else "fail", "blockers": blockers, "rows": rows}


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
        entry["declared_card_path"] = str(file_rel)
        entry["real_file_path"] = str(real_path)
        entry["module_import_path"] = str(module_override["module_import_path"])
        entry["file_sha256"] = hashlib.sha256(real_path.read_bytes()).hexdigest()
    manifest["variant_id"] = route_id
    manifest["variant_card_ref"] = None
    manifest["route_manifest_fingerprint"] = hashlib.sha256(
        json.dumps(manifest["routed_modules"], sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    return manifest


def _collect_preflight_blockers(preflight: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for name, check in preflight.get("checks", {}).items():
        if check.get("status") == "pass":
            continue
        for item in check.get("blockers", ["unspecified"]):
            cls = "infrastructure_invalid_result" if name == "azure_dns_network_preflight" else "adapter_invalid_result"
            if name == "docker_or_fallback":
                cls = "substrate_unavailable_result"
            blockers.append({"check": name, "blocker": item, "interpretation_class": cls})
    return blockers


def _run_one(*, out: Path, spec_map: dict[str, dict[str, Any]], plan_row: dict[str, Any]) -> dict[str, Any]:
    spec = spec_map[str(plan_row["eval_id"])]
    route_id = str(plan_row["route_id"])
    budget = int(plan_row["budget"])
    run_index = int(plan_row["run_index"])
    fair_runtime = bool(plan_row["fair_runtime"])
    arm = LETTA_ARM if fair_runtime else PLAIN_ARM
    run_id = f"{MISSION_ID}__{plan_row['eval_id']}__{route_id}__b{budget}__r{run_index}"
    run_dir = out / "runs" / run_id
    workspace = run_dir / "workspace"
    seed_spec = spec
    if "workspace_seed" not in spec and "workspace_files" in spec:
        seed_spec = dict(spec)
        seed_spec["workspace_seed"] = "simple_files"
    _seed_workspace(workspace, seed_spec)
    prompt = str(spec["task_prompt"]) + (PYTHON3_CONTRACT_PROMPT if fair_runtime else "")
    final_answer = ""
    started = perf_counter()
    result = run_reference_baseline(
        run_id=run_id,
        run_dir=run_dir,
        task_id=str(spec["task_id"]),
        task_prompt=prompt,
        benchmark_family=str(spec["benchmark_class"]),
        case_id=str(spec["eval_id"]),
        seed_id=route_id,
        model_route=_model_route(str(plan_row["model_id"])),
        model_client_kwargs={"timeout_sec": int(spec.get("timeout_sec", 120)), "max_retries": 1},
        max_steps=budget,
        timeout_sec=int(spec.get("timeout_sec", 120)),
        cwd=workspace,
        route_manifest=_build_route_manifest(route_id),
        enforce_packet04_route_contract=True,
        orientation_env_overrides=_orientation_env(workspace, arm) if fair_runtime else None,
    )
    final_answer = str(result.get("execution", {}).get("last_completion", {}).get("text") or "")
    grade = _grade_eval_row(eval_id=str(plan_row["eval_id"]), spec=spec, result=result, workspace=workspace, final_answer=final_answer)
    step_count = int(result.get("execution", {}).get("step_count", 0) or 0)
    commands, exit_codes = _tool_trace_fields(result.get("run_events", []))
    infra_invalid = _is_infrastructure_invalid(run_dir)
    adapter_invalid = _is_adapter_invalid(run_dir)
    interpretation_class = (
        "infrastructure_invalid_result"
        if infra_invalid
        else "adapter_invalid_result"
        if adapter_invalid
        else "behavioral_pass"
        if grade.get("verdict") == "pass"
        else "behavioral_fail"
    )
    failure_class = _classify_failure(
        interpretation_class=interpretation_class,
        grade=grade,
        final_answer=final_answer,
        commands=commands,
        step_count=step_count,
        budget=budget,
    )
    return _normalize_record(
        raw={
            "run_id": run_id,
            "eval_id": str(plan_row["eval_id"]),
            "model_id": str(plan_row["model_id"]),
            "route_id": route_id,
            "budget": budget,
            "run_index": run_index,
            "segment": str(plan_row["segment"]),
            "final_answer": final_answer,
            "exact_grade": grade,
            "step_count": step_count,
            "tool_commands": commands,
            "exit_codes": exit_codes,
            "trace_path": str(run_dir / "run_events.jsonl"),
            "failure_class": failure_class,
            "interpretation_class": interpretation_class,
            "notes": "fair_runtime_only_for_letta_rows" if fair_runtime else "sentinel_standard_runtime",
            "timing_sec": perf_counter() - started,
            "token_and_cost_summary": _usage(result),
        }
    )


def _grade_eval_row(
    *,
    eval_id: str,
    spec: dict[str, Any],
    result: dict[str, Any],
    workspace: Path,
    final_answer: str,
) -> dict[str, Any]:
    if eval_id == PROPER_EVAL_ID:
        expected_scalar = str(_proper_eval_deterministic_ceiling(workspace).get("expected_scalar") or "")
        return grade_original_surface_reduce_select_answer(final_answer=final_answer, expected_scalar=expected_scalar)
    return grade_phase65_spec(spec=spec, result=result, workspace=workspace)


def _model_route(model_id: str) -> dict[str, Any]:
    from runner.eval_runner_router import resolve_model_route_for_route

    policy = {key: f"azure:{model_id}" for key in ("screening_default", "screening_fallback", "promotion_tier")}
    return resolve_model_route_for_route(
        {"execution_mode": "sync_interactive", "model_tier_policy": policy},
        model_tier_selector="screening_default",
    )


def _classify_failure(
    *,
    interpretation_class: str,
    grade: dict[str, Any],
    final_answer: str,
    commands: list[str],
    step_count: int,
    budget: int,
) -> list[str]:
    if interpretation_class in INVALID_INTERPRETATION_CLASSES:
        return ["provider_contaminated"]
    if grade.get("verdict") == "pass":
        return ["unknown"]
    reasons = {str(code) for code in grade.get("reason_codes", []) if isinstance(code, str)}
    classes: set[str] = set()
    if not commands:
        classes.add("evidence_acquisition")
    if not final_answer.strip():
        classes.add("dispatch_failure")
    if final_answer.strip() and grade.get("verdict") != "pass":
        classes.add("reduction_error")
    if step_count < budget and final_answer.strip() and "ground_truth_mismatch" in " ".join(reasons):
        classes.add("premature_answer")
    return sorted(classes or {"unknown"})


def _normalize_record(*, raw: dict[str, Any]) -> dict[str, Any]:
    grade = raw.get("exact_grade") if isinstance(raw.get("exact_grade"), dict) else {}
    interpretation_class = str(raw.get("interpretation_class") or "behavioral_fail")
    pass_fail: bool | None
    if interpretation_class in INVALID_INTERPRETATION_CLASSES:
        pass_fail = None
        verdict = "excluded_provider_contaminated"
    else:
        pass_fail = bool(grade.get("verdict") == "pass")
        verdict = "pass" if pass_fail else "fail"
    failure_class = raw.get("failure_class")
    normalized = [str(item) for item in failure_class] if isinstance(failure_class, list) else ["unknown"]
    clean_classes = sorted({label for label in normalized if label in FAILURE_CLASSES} or {"unknown"})
    return {
        "mission_id": MISSION_ID,
        "timestamp_utc": utc_now(),
        "run_id": str(raw.get("run_id") or ""),
        "eval_id": str(raw.get("eval_id") or ""),
        "model_id": str(raw.get("model_id") or ""),
        "route_id": str(raw.get("route_id") or ""),
        "budget": int(raw.get("budget", 0) or 0),
        "run_index": int(raw.get("run_index", 0) or 0),
        "segment": str(raw.get("segment") or ""),
        "final_answer": str(raw.get("final_answer") or ""),
        "exact_grade": grade,
        "pass_fail": pass_fail,
        "scoreboard_verdict": verdict,
        "step_count": int(raw.get("step_count", 0) or 0),
        "tool_commands": list(raw.get("tool_commands") or []),
        "exit_codes": list(raw.get("exit_codes") or []),
        "trace_path": str(raw.get("trace_path") or ""),
        "failure_class": clean_classes,
        "interpretation_class": interpretation_class,
        "notes": str(raw.get("notes") or ""),
        "timing_sec": float(raw.get("timing_sec", 0.0) or 0.0),
        "token_and_cost_summary": raw.get("token_and_cost_summary") if isinstance(raw.get("token_and_cost_summary"), dict) else {},
    }


def _write_bundle(
    *,
    out: Path,
    metadata: dict[str, Any],
    preflight: dict[str, Any],
    records: list[dict[str, Any]],
    blocked: bool,
) -> dict[str, Any]:
    result_path = out / "packet07_hard_row_answer_robustness_result_records.jsonl"
    summary_json_path = out / "packet07_hard_row_answer_robustness_summary.json"
    summary_table_path = out / "packet07_hard_row_answer_robustness_summary_table.md"
    failure_path = out / "packet07_hard_row_answer_robustness_failure_classification_report.json"
    decision_path = out / "packet07_hard_row_answer_robustness_decision_memo.md"
    handoff_path = out / "packet07_hard_row_answer_robustness_handoff.md"
    ledger_path = out / "RAW_LEDGER_UPDATE"

    _write_jsonl(result_path, records)
    summary = _score_summary(records=records, metadata=metadata, preflight=preflight, blocked=blocked)
    failure = _failure_report(records=records)
    _write_json(summary_json_path, summary)
    _write_text(summary_table_path, _summary_table(summary))
    _write_json(failure_path, failure)
    _write_text(decision_path, _decision_memo(summary, failure, blocked=blocked))
    _write_text(handoff_path, _handoff(summary, failure))
    ledger = _raw_ledger_update(out=out, summary=summary, failure=failure, blocked=blocked)
    _write_text(ledger_path, ledger)
    try:
        _record_ledger(ledger)
    except Exception:
        pass
    return {
        "mission_id": MISSION_ID,
        "status": "blocked" if blocked else "executed",
        "output_dir": str(out),
        "planned_run_count": len(metadata["plan"]),
        "record_count": len(records),
        "summary_path": str(summary_json_path),
    }


def _score_summary(*, records: list[dict[str, Any]], metadata: dict[str, Any], preflight: dict[str, Any], blocked: bool) -> dict[str, Any]:
    admitted = [row for row in records if row["interpretation_class"] not in INVALID_INTERPRETATION_CLASSES]
    excluded = [row for row in records if row["interpretation_class"] in INVALID_INTERPRETATION_CLASSES]
    proper_eval = [row for row in admitted if row["eval_id"] == PROPER_EVAL_ID]
    primary = [row for row in admitted if row["eval_id"] == PRIMARY_EVAL_ID]
    proper_by_route: dict[str, dict[str, int]] = {}
    for route_id in ROUTE_IDS:
        route_rows = [row for row in proper_eval if row["route_id"] == route_id]
        proper_by_route[route_id] = {
            "run_count": len(route_rows),
            "pass": sum(1 for row in route_rows if row["pass_fail"] is True),
            "fail": sum(1 for row in route_rows if row["pass_fail"] is False),
        }
    by_route_budget: dict[str, dict[str, Any]] = {}
    for row in primary:
        key = f"{row['route_id']}|b{row['budget']}"
        bucket = by_route_budget.setdefault(key, {"run_count": 0, "pass": 0, "fail": 0, "mean_steps": 0.0})
        bucket["run_count"] += 1
        bucket["pass"] += 1 if row["pass_fail"] else 0
        bucket["fail"] += 0 if row["pass_fail"] else 1
        bucket["mean_steps"] += float(row.get("step_count", 0) or 0)
    for bucket in by_route_budget.values():
        run_count = int(bucket["run_count"] or 0)
        bucket["pass_rate"] = (bucket["pass"] / run_count) if run_count else 0.0
        bucket["mean_steps"] = (bucket["mean_steps"] / run_count) if run_count else 0.0
    return {
        "mission_id": MISSION_ID,
        "blocked": blocked,
        "planned_run_count": len(metadata["plan"]),
        "run_count": len(records),
        "behaviorally_admissible_run_count": len(admitted),
        "excluded_provider_contaminated_run_count": len(excluded),
        "pass_count": sum(1 for row in admitted if row["pass_fail"] is True),
        "fail_count": sum(1 for row in admitted if row["pass_fail"] is False),
        "proper_eval_original_surface_by_route": proper_by_route,
        "primary_hard_row_by_route_budget": by_route_budget,
        "route_summary": {route_id: _route_eval_summary(admitted, route_id) for route_id in ROUTE_IDS},
        "selected_route": _selected_route(admitted),
        "preflight": preflight,
        "authority": _authority(),
    }


def _route_eval_summary(records: list[dict[str, Any]], route_id: str) -> dict[str, int]:
    scoped = [row for row in records if row["route_id"] == route_id]
    return {
        "admissible_runs": len(scoped),
        "pass": sum(1 for row in scoped if row["pass_fail"] is True),
        "fail": sum(1 for row in scoped if row["pass_fail"] is False),
        "proper_eval_pass": sum(1 for row in scoped if row["eval_id"] == PROPER_EVAL_ID and row["pass_fail"] is True),
        "proper_eval_fail": sum(1 for row in scoped if row["eval_id"] == PROPER_EVAL_ID and row["pass_fail"] is False),
        "hard_row_pass": sum(1 for row in scoped if row["eval_id"] == PRIMARY_EVAL_ID and row["pass_fail"] is True),
        "hard_row_fail": sum(1 for row in scoped if row["eval_id"] == PRIMARY_EVAL_ID and row["pass_fail"] is False),
        "sentinel_fail": sum(1 for row in scoped if row["eval_id"] in SENTINEL_EVAL_IDS and row["pass_fail"] is False),
    }


def _selected_route(records: list[dict[str, Any]]) -> str:
    rows = []
    for route_id in ROUTE_IDS:
        summary = _route_eval_summary(records, route_id)
        rows.append(
            (
                route_id,
                summary["proper_eval_pass"],
                -summary["proper_eval_fail"],
                summary["hard_row_pass"],
                -summary["hard_row_fail"],
                -summary["sentinel_fail"],
            )
        )
    rows.sort(key=lambda item: (item[1], item[2], item[3], item[4], item[5], item[0]), reverse=True)
    return rows[0][0] if rows else CONTROL_ROUTE_ID


def _failure_report(*, records: list[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for row in records:
        if row["pass_fail"] is True:
            continue
        for label in row["failure_class"]:
            counts[label] = counts.get(label, 0) + 1
    return {
        "mission_id": MISSION_ID,
        "failure_class_counts": dict(sorted(counts.items())),
        "rows": [
            {
                "run_id": row["run_id"],
                "eval_id": row["eval_id"],
                "segment": row["segment"],
                "route_id": row["route_id"],
                "budget": row["budget"],
                "run_index": row["run_index"],
                "scoreboard_verdict": row["scoreboard_verdict"],
                "failure_class": row["failure_class"],
            }
            for row in records
            if row["pass_fail"] is not True
        ],
    }


def _summary_table(summary: dict[str, Any]) -> str:
    rows = [
        "# Packet 07 Hard-Row Answer Robustness Summary",
        "",
        f"- mission_id: `{MISSION_ID}`",
        f"- selected_route: `{summary['selected_route']}`",
        f"- behaviorally_admissible_run_count: `{summary['behaviorally_admissible_run_count']}`",
        f"- excluded_provider_contaminated_run_count: `{summary['excluded_provider_contaminated_run_count']}`",
        "",
        "| route_id | admissible_runs | pass | fail | proper_eval_pass | proper_eval_fail | hard_row_pass | hard_row_fail | sentinel_fail |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for route_id in ROUTE_IDS:
        bucket = summary["route_summary"][route_id]
        rows.append(
            f"| `{route_id}` | {bucket['admissible_runs']} | {bucket['pass']} | {bucket['fail']} | "
            f"{bucket['proper_eval_pass']} | {bucket['proper_eval_fail']} | "
            f"{bucket['hard_row_pass']} | {bucket['hard_row_fail']} | {bucket['sentinel_fail']} |"
        )
    return "\n".join(rows) + "\n"


def _decision_memo(summary: dict[str, Any], failure: dict[str, Any], *, blocked: bool) -> str:
    decision = "hold_blocked" if blocked else "review_helper_vs_control_for_hard_row_promotion"
    return "\n".join(
        [
            "# Packet 07 Hard-Row Answer Robustness Decision Memo",
            "",
            f"- decision: `{decision}`",
            f"- selected_route: `{summary['selected_route']}`",
            f"- admissible_runs: `{summary['behaviorally_admissible_run_count']}`",
            f"- excluded_provider_contaminated_runs: `{summary['excluded_provider_contaminated_run_count']}`",
            f"- failure_class_counts: `{failure['failure_class_counts']}`",
        ]
    ) + "\n"


def _handoff(summary: dict[str, Any], failure: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Packet 07 Hard-Row Answer Robustness Handoff",
            "",
            f"- mission_id: `{MISSION_ID}`",
            f"- selected_route: `{summary['selected_route']}`",
            f"- run_count: `{summary['run_count']}`",
            f"- admissible_run_count: `{summary['behaviorally_admissible_run_count']}`",
            f"- excluded_provider_contaminated_run_count: `{summary['excluded_provider_contaminated_run_count']}`",
            f"- failure_class_counts: `{failure['failure_class_counts']}`",
            "- artifact_bundle: result records, summary table/json, failure classification report, decision memo, handoff, RAW_LEDGER_UPDATE",
        ]
    ) + "\n"


def _raw_ledger_update(*, out: Path, summary: dict[str, Any], failure: dict[str, Any], blocked: bool) -> str:
    return "\n".join(
        [
            "RAW_LEDGER_UPDATE",
            "- actor: codex",
            "- task: Packet 07 hard-row answer-robustness helper follow-up",
            "- event_type: implementation",
            f"- summary: Added helper route `{HELPER_ROUTE_ID}` vs control `{CONTROL_ROUTE_ID}` follow-up runner with hard-row plus sentinel plan and provider-contamination exclusion.",
            f"- observations: run_count `{summary['run_count']}`; admissible `{summary['behaviorally_admissible_run_count']}`; excluded_provider_contaminated `{summary['excluded_provider_contaminated_run_count']}`; blocked `{blocked}`; selected_route `{summary['selected_route']}`.",
            "- inference: The helper can be evaluated as behavioral signal only when provider-contaminated runs are excluded from pass/fail accounting.",
            f"- evidence_paths: {out / 'packet07_hard_row_answer_robustness_result_records.jsonl'}; {out / 'packet07_hard_row_answer_robustness_summary.json'}; {out / 'packet07_hard_row_answer_robustness_summary_table.md'}; {out / 'packet07_hard_row_answer_robustness_failure_classification_report.json'}; {out / 'packet07_hard_row_answer_robustness_decision_memo.md'}; {out / 'packet07_hard_row_answer_robustness_handoff.md'}",
            "- affected_components: blocks/context/reduction_discipline_answer_guard.py; blocks/orientation/packet07_hard_row_doctrine.py; runner/packet07_hard_row_answer_robustness.py; tests/test_packet07_hard_row_answer_robustness.py",
            "- decision_change: Introduced a narrow hard-row follow-up route and evaluation harness with explicit control-vs-helper comparison and sentinel checks.",
            "- unresolved_questions: Whether the helper increases hard-row pass stability at both 15 and 25 budgets without sentinel regressions.",
            "- confidence: medium",
            "- commit_message: HOLD - add Packet 07 hard-row answer-robustness helper route and follow-up runner",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--no-execute", action="store_true")
    parser.add_argument("--repeats", type=int, default=PRIMARY_REPEATS)
    args = parser.parse_args(argv)
    print(
        json.dumps(
            launch_packet07_hard_row_answer_robustness(
                output_dir=args.output_dir,
                execute=not args.no_execute,
                repeats=int(args.repeats),
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
