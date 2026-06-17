"""Narrow Packet 07 fair-runtime rerun board for the two Letta rows."""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
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
    PRICE,
    _authority,
    _azure_dns_network_preflight,
    _context_specs,
    _counts,
    _docker_or_fallback_preflight,
    _grade_spec,
    _interpretation_class,
    _is_adapter_invalid,
    _is_infrastructure_invalid,
    _record_ledger,
    _seed_workspace,
    _usage,
    _write_json,
    _write_jsonl,
    _write_text,
    resolve_packet07_context_model_route,
)
from runner.packet07_golden_diagnostic import (
    APP_EVIDENCE_VARIANT,
    _build_route_manifest,
    _classify_root_cause,
    _orientation_env,
    _tool_trace_fields,
)

MISSION_ID = "packet07_fair_runtime_rerun_narrow"
DEFAULT_OUTPUT_DIR = Path(
    "tracking/collab/stage_03_execution_planning/packets/packet_06_paired_combo_variants/"
    "runs/2026-05-12_packet07_fair_runtime_rerun_narrow"
)
ROUTES = (BACKBONE_INCUMBENT, APP_EVIDENCE_VARIANT)
EVAL_IDS = ("letta_filesystem_001_easy", "letta_filesystem_002_medium")
MAIN_ARM = {
    "arm_id": "main_board_orientation_python3_steps12",
    "label": "main board orientation + python3 contract",
    "max_steps": 12,
    "inject_orientation": True,
    "python_contract": True,
}
RERUN_ARM = {
    "arm_id": "passing_pair_rerun_orientation_python3_steps7",
    "label": "passing-pair rerun orientation + python3 contract",
    "max_steps": 7,
    "inject_orientation": True,
    "python_contract": True,
}
INVALID_CLASSES = {"infrastructure_invalid_result", "adapter_invalid_result", "substrate_unavailable_result"}
PYTHON3_CONTRACT_PROMPT = (
    "\nUse source-grounded shell inspection. Python contract: when Python is needed, use `python3` explicitly."
)


def launch_narrow_fair_runtime_rerun(
    *,
    output_dir: str | Path,
    execute: bool = True,
    max_workers: int = 2,
    model_tier_selector: str = "screening_default",
) -> dict[str, Any]:
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    specs = _build_specs()
    board_manifest = {
        "mission_id": MISSION_ID,
        "comparison_set": list(ROUTES),
        "required_eval_ids": list(EVAL_IDS),
        "main_arm": dict(MAIN_ARM),
        "rerun_arm": dict(RERUN_ARM),
        "model_tier_selector": model_tier_selector,
        "authority": _authority(),
    }
    preflight = {
        "mission_id": MISSION_ID,
        "checks": {
            "route_availability": _route_availability_check(),
            "azure_dns_network_preflight": _azure_dns_network_preflight(),
            "docker_or_fallback": _docker_or_fallback_preflight(specs),
        },
    }
    blockers = _collect_preflight_blockers(preflight)
    preflight["status"] = "pass" if not blockers else "blocked"
    preflight["blockers"] = blockers
    preflight["planned_model_backed_runs"] = len(specs) * len(ROUTES)
    preflight["authority"] = _authority()
    _write_json(out / "packet07_fair_runtime_rerun_narrow_board_manifest.json", board_manifest)
    if not execute or preflight["status"] != "pass":
        return _write_artifacts(out, [], [], [], preflight, board_manifest, blocked=True)

    main_plan = [(idx, spec, variant) for idx, (spec, variant) in enumerate((s, v) for s in specs for v in ROUTES)]
    main_records, main_traces = _execute_plan(
        out=out,
        plan=main_plan,
        arm=MAIN_ARM,
        phase_id="main",
        max_workers=max_workers,
        model_tier_selector=model_tier_selector,
    )
    rerun_plan = _rerun_plan_from_main(specs, main_records)
    rerun_records, rerun_traces = _execute_plan(
        out=out,
        plan=rerun_plan,
        arm=RERUN_ARM,
        phase_id="rerun",
        max_workers=max_workers,
        model_tier_selector=model_tier_selector,
    )
    return _write_artifacts(
        out,
        main_records,
        rerun_records,
        [*main_traces, *rerun_traces],
        preflight,
        board_manifest,
        blocked=False,
    )


def _build_specs() -> list[dict[str, Any]]:
    library = {row["eval_id"]: row for row in _context_specs()}
    specs: list[dict[str, Any]] = []
    for eval_id in EVAL_IDS:
        spec = dict(library[eval_id])
        spec["lane"] = "context_handoff_answer_extraction"
        spec["admission_level"] = "certified"
        spec["variant_ids"] = list(ROUTES)
        specs.append(spec)
    return specs


def _route_availability_check() -> dict[str, Any]:
    baseline = build_packet04_route_manifest(BASELINE_VARIANT_ID, scope=PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE)
    rows, blockers = [], []
    for variant in ROUTES:
        for arm in (MAIN_ARM, RERUN_ARM):
            try:
                manifest = _build_route_manifest(variant, arm)
                load_runtime_callables(manifest)
                validate_independent_candidate_routing(candidate_manifest=manifest, baseline_manifest=baseline)
                rows.append({"variant_id": variant, "arm_id": arm["arm_id"], "status": "pass"})
            except Exception as exc:  # pragma: no cover - preflight surface only
                rows.append({"variant_id": variant, "arm_id": arm["arm_id"], "status": "fail", "error": str(exc)})
                blockers.append(f"route_unavailable:{variant}:{arm['arm_id']}")
    return {"status": "pass" if not blockers else "fail", "blockers": blockers, "rows": rows}


def _collect_preflight_blockers(preflight: dict[str, Any]) -> list[dict[str, Any]]:
    blockers = []
    for name, check in preflight.get("checks", {}).items():
        if check.get("status") == "pass":
            continue
        for item in check.get("blockers", ["unspecified"]):
            cls = "infrastructure_invalid_result" if name == "azure_dns_network_preflight" else "adapter_invalid_result"
            if name == "docker_or_fallback":
                cls = "substrate_unavailable_result"
            blockers.append({"check": name, "blocker": item, "interpretation_class": cls})
    return blockers


def _rerun_plan_from_main(specs: list[dict[str, Any]], main_records: list[dict[str, Any]]) -> list[tuple[int, dict[str, Any], str]]:
    spec_by_eval = {spec["eval_id"]: spec for spec in specs}
    passing_pairs = sorted({(row["eval_id"], row["variant_id"]) for row in main_records if row["scoreboard_verdict"] == "pass"})
    return [(idx, spec_by_eval[eval_id], variant_id) for idx, (eval_id, variant_id) in enumerate(passing_pairs)]


def _execute_plan(
    *,
    out: Path,
    plan: list[tuple[int, dict[str, Any], str]],
    arm: dict[str, Any],
    phase_id: str,
    max_workers: int,
    model_tier_selector: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not plan:
        return [], []
    completed: list[tuple[int, dict[str, Any], dict[str, Any]]] = []
    with ThreadPoolExecutor(max_workers=max(1, min(max_workers, 2))) as executor:
        future_map = {
            executor.submit(_run_one, out, spec, variant, idx, arm=arm, phase_id=phase_id, model_tier_selector=model_tier_selector): idx
            for idx, spec, variant in plan
        }
        for future in as_completed(future_map):
            completed.append((future_map[future], *future.result()))
    completed.sort(key=lambda row: row[0])
    return [row[1] for row in completed], [row[2] for row in completed]


def _run_one(
    out: Path,
    spec: dict[str, Any],
    variant: str,
    plan_index: int,
    *,
    arm: dict[str, Any],
    phase_id: str,
    model_tier_selector: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    run_id = f"{MISSION_ID}__{phase_id}__{spec['eval_id']}__{variant}__r0"
    run_dir = out / "runs" / run_id
    workspace = run_dir / "workspace"
    run_started = perf_counter()
    _seed_workspace(workspace, spec)
    model_route = resolve_packet07_context_model_route(model_tier_selector=model_tier_selector)
    result = run_reference_baseline(
        run_id=run_id,
        run_dir=run_dir,
        task_id=spec["task_id"],
        task_prompt=spec["task_prompt"] + PYTHON3_CONTRACT_PROMPT,
        benchmark_family=spec["benchmark_class"],
        case_id=spec["eval_id"],
        seed_id=variant,
        model_route=model_route,
        model_client_kwargs={"timeout_sec": int(spec["timeout_sec"]), "max_retries": 1},
        max_steps=int(arm["max_steps"]),
        timeout_sec=int(spec["timeout_sec"]),
        cwd=workspace,
        route_manifest=_build_route_manifest(variant, arm),
        enforce_packet04_route_contract=True,
        orientation_env_overrides=_orientation_env(workspace, arm),
    )
    grade = _grade_spec(spec, result, workspace)
    infra_invalid = _is_infrastructure_invalid(run_dir)
    adapter_invalid = _is_adapter_invalid(run_dir)
    verdict = "invalid" if infra_invalid or adapter_invalid else grade.get("verdict", "fail")
    reason_codes = list(grade.get("reason_codes", []))
    if infra_invalid:
        reason_codes = sorted(set(reason_codes + ["model_or_network_infra_failure"]))
    if adapter_invalid:
        reason_codes = sorted(set(reason_codes + ["adapter_contract_invalid"]))
    commands, exit_codes = _tool_trace_fields(result.get("run_events", []))
    final_answer = str(result.get("execution", {}).get("last_completion", {}).get("text") or "")
    step_count = int(result.get("execution", {}).get("step_count", 0) or 0)
    model_id = str(model_route.get("request_settings", {}).get("pricing_model_id") or model_route.get("model_name") or "")
    record = {
        "mission_id": MISSION_ID,
        "run_id": run_id,
        "phase_id": phase_id,
        "pair_id": f"{spec['eval_id']}::{variant}",
        "eval_id": spec["eval_id"],
        "lane": spec["lane"],
        "benchmark_class": spec["benchmark_class"],
        "task_id": spec["task_id"],
        "variant_id": variant,
        "arm_id": arm["arm_id"],
        "admission_level": spec["admission_level"],
        "attempt": 0,
        "plan_index": plan_index,
        "model_backed": True,
        "model_id": model_id,
        "max_steps": int(arm["max_steps"]),
        "environment_flags": {
            "orientation_injected": bool(arm["inject_orientation"]),
            "python_contract_explicit": bool(arm["python_contract"]),
            "max_steps": int(arm["max_steps"]),
        },
        "run_dir": str(run_dir),
        "trace_ref": str(run_dir / "run_events.jsonl"),
        "score_summary": {"final_verdict": verdict, "grade": grade},
        "scoreboard_verdict": verdict,
        "interpretation_class": _interpretation_class(spec, grade, infra_invalid=infra_invalid, adapter_invalid=adapter_invalid),
        "reason_codes": reason_codes,
        "final_answer": final_answer,
        "step_count": step_count,
        "tool_commands": commands,
        "exit_codes": exit_codes,
        "token_and_cost_summary": _usage(result),
        "root_cause_classification": _classify_root_cause(
            grade=grade,
            commands=commands,
            exit_codes=exit_codes,
            final_answer=final_answer,
            max_steps=int(arm["max_steps"]),
            step_count=step_count,
        ),
        "authority": _authority(),
        "timing_summary": {"run_wall_sec": perf_counter() - run_started},
    }
    trace = {
        "run_id": run_id,
        "phase_id": phase_id,
        "eval_id": spec["eval_id"],
        "variant_id": variant,
        "arm_id": arm["arm_id"],
        "trace_ref": record["trace_ref"],
        "scoreboard_verdict": verdict,
        "interpretation_class": record["interpretation_class"],
        "reason_codes": reason_codes,
    }
    return record, trace


def _write_artifacts(
    out: Path,
    main_records: list[dict[str, Any]],
    rerun_records: list[dict[str, Any]],
    traces: list[dict[str, Any]],
    preflight: dict[str, Any],
    board_manifest: dict[str, Any],
    *,
    blocked: bool,
) -> dict[str, Any]:
    records = [*main_records, *rerun_records]
    _write_jsonl(out / "packet07_fair_runtime_rerun_narrow_result_records.jsonl", records)
    score = _score_envelope(main_records, rerun_records, records, preflight, board_manifest, blocked=blocked)
    failure_report = _failure_source_report(records)
    arm_comparison = _arm_comparison_report(main_records, rerun_records)
    trace_report = {
        "mission_id": MISSION_ID,
        "run_count": len(traces),
        "main_run_count": len(main_records),
        "rerun_run_count": len(rerun_records),
        "traces": traces,
        "preflight_blockers": preflight.get("blockers", []),
    }
    cost_report = _cost_report(records)
    recommendation = _recommendation(score, arm_comparison)
    deep_trace = _deep_trace(score, failure_report, arm_comparison)
    handoff = _handoff(score, arm_comparison)
    ledger = _raw_ledger_update(out, score, failure_report, arm_comparison)
    _write_json(out / "packet07_fair_runtime_rerun_narrow_score_envelope.json", score)
    _write_json(out / "packet07_fair_runtime_rerun_narrow_trace_report.json", trace_report)
    _write_json(out / "packet07_fair_runtime_rerun_narrow_failure_source_report.json", failure_report)
    _write_json(out / "packet07_fair_runtime_rerun_narrow_arm_comparison_report.json", arm_comparison)
    _write_json(out / "packet07_fair_runtime_rerun_narrow_cost_report.json", cost_report)
    _write_text(out / "packet07_fair_runtime_rerun_narrow_recommendation.md", recommendation)
    _write_text(out / "packet07_fair_runtime_rerun_narrow_deep_trace_analysis.md", deep_trace)
    _write_text(out / "packet07_fair_runtime_rerun_narrow_handoff.md", handoff)
    _write_text(out / "RAW_LEDGER_UPDATE", ledger)
    _record_ledger(ledger)
    return {
        "output_dir": str(out),
        "run_count": len(records),
        "main_run_count": len(main_records),
        "rerun_run_count": len(rerun_records),
        "selected_recommendation": score["selected_recommendation"],
        "blocked": blocked,
    }


def _score_envelope(
    main_records: list[dict[str, Any]],
    rerun_records: list[dict[str, Any]],
    records: list[dict[str, Any]],
    preflight: dict[str, Any],
    board_manifest: dict[str, Any],
    *,
    blocked: bool,
) -> dict[str, Any]:
    admitted = [row for row in records if row["interpretation_class"] not in INVALID_CLASSES]
    main_pass_pairs = {(row["eval_id"], row["variant_id"]) for row in main_records if row["scoreboard_verdict"] == "pass"}
    rerun_pass_pairs = {(row["eval_id"], row["variant_id"]) for row in rerun_records if row["scoreboard_verdict"] == "pass"}
    stable_pairs = main_pass_pairs & rerun_pass_pairs
    selected = "context_measurement_or_eval_blocked" if blocked else _selected_recommendation(main_pass_pairs, stable_pairs, rerun_records)
    return {
        "mission_id": MISSION_ID,
        "run_count": len(records),
        "model_backed_runs": sum(1 for row in records if row.get("model_backed")),
        "behaviorally_admissible_run_count": len(admitted),
        "main_board_pass_pair_count": len(main_pass_pairs),
        "rerun_pass_pair_count": len(rerun_pass_pairs),
        "stable_pass_pair_count": len(stable_pairs),
        "selected_recommendation": selected,
        "route_summary_main": {route: _route_arm_summary(main_records, route, MAIN_ARM["arm_id"]) for route in ROUTES},
        "route_summary_rerun": {route: _route_arm_summary(rerun_records, route, RERUN_ARM["arm_id"]) for route in ROUTES},
        "preflight": preflight,
        "board_manifest": board_manifest,
    }


def _route_arm_summary(records: list[dict[str, Any]], route_id: str, arm_id: str) -> dict[str, int]:
    scoped = [row for row in records if row["variant_id"] == route_id and row["arm_id"] == arm_id]
    return {
        "run_count": len(scoped),
        "pass": sum(1 for row in scoped if row["scoreboard_verdict"] == "pass"),
        "fail": sum(1 for row in scoped if row["scoreboard_verdict"] == "fail"),
        "invalid": sum(1 for row in scoped if row["scoreboard_verdict"] == "invalid"),
    }


def _selected_recommendation(
    main_pass_pairs: set[tuple[str, str]],
    stable_pairs: set[tuple[str, str]],
    rerun_records: list[dict[str, Any]],
) -> str:
    if not main_pass_pairs:
        return "fair_runtime_no_main_pass_pairs"
    if not rerun_records:
        return "fair_runtime_rerun_not_triggered"
    if stable_pairs == main_pass_pairs:
        return "fair_runtime_stable_on_passing_pairs"
    return "fair_runtime_regression_detected_on_passing_pairs"


def _failure_source_report(records: list[dict[str, Any]]) -> dict[str, Any]:
    failures = [row for row in records if row["scoreboard_verdict"] != "pass"]
    return {
        "mission_id": MISSION_ID,
        "failure_count": len(failures),
        "dominant_failure_arm": max(_counts(row["arm_id"] for row in failures).items(), key=lambda item: (item[1], item[0]))[0]
        if failures
        else "none",
        "failure_counts_by_interpretation_class": _counts(row["interpretation_class"] for row in failures),
        "failure_counts_by_root_cause": _counts(row["root_cause_classification"] for row in failures),
        "main_fail_rows": [row["run_id"] for row in failures if row["arm_id"] == MAIN_ARM["arm_id"]],
        "rerun_fail_rows": [row["run_id"] for row in failures if row["arm_id"] == RERUN_ARM["arm_id"]],
    }


def _arm_comparison_report(main_records: list[dict[str, Any]], rerun_records: list[dict[str, Any]]) -> dict[str, Any]:
    main_index = {(row["eval_id"], row["variant_id"]): row for row in main_records if row["scoreboard_verdict"] == "pass"}
    rerun_index = {(row["eval_id"], row["variant_id"]): row for row in rerun_records}
    rows = []
    for pair in sorted(main_index):
        main_row = main_index[pair]
        rerun_row = rerun_index.get(pair)
        rerun_verdict = rerun_row["scoreboard_verdict"] if rerun_row else "missing"
        rows.append(
            {
                "eval_id": pair[0],
                "variant_id": pair[1],
                "main_verdict": main_row["scoreboard_verdict"],
                "rerun_verdict": rerun_verdict,
                "main_step_count": int(main_row.get("step_count", 0) or 0),
                "rerun_step_count": int((rerun_row or {}).get("step_count", 0) or 0),
                "stable_pass": rerun_verdict == "pass",
                "regressed": rerun_verdict in {"fail", "invalid", "missing"},
            }
        )
    return {
        "mission_id": MISSION_ID,
        "compared_pair_count": len(rows),
        "stable_pass_count": sum(1 for row in rows if row["stable_pass"]),
        "regressed_pair_count": sum(1 for row in rows if row["regressed"]),
        "rows": rows,
    }


def _cost_report(records: list[dict[str, Any]]) -> dict[str, Any]:
    by_arm = {
        arm_id: {
            "run_count": len([row for row in records if row["arm_id"] == arm_id]),
            "total_tokens": sum(
                int(row.get("token_and_cost_summary", {}).get("total_tokens", 0) or 0)
                for row in records
                if row["arm_id"] == arm_id
            ),
            "total_usd_estimate": sum(
                float(row.get("token_and_cost_summary", {}).get("usd_estimate", 0.0) or 0.0)
                for row in records
                if row["arm_id"] == arm_id
            ),
        }
        for arm_id in (MAIN_ARM["arm_id"], RERUN_ARM["arm_id"])
    }
    return {
        "mission_id": MISSION_ID,
        "run_count": len(records),
        "total_tokens": sum(int(row.get("token_and_cost_summary", {}).get("total_tokens", 0) or 0) for row in records),
        "total_usd_estimate": sum(float(row.get("token_and_cost_summary", {}).get("usd_estimate", 0.0) or 0.0) for row in records),
        "price_table": PRICE,
        "by_arm": by_arm,
    }


def _recommendation(score: dict[str, Any], arm_comparison: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Packet 07 Narrow Fair-Runtime Rerun Recommendation",
            "",
            f"- selected_recommendation: `{score['selected_recommendation']}`",
            f"- main_board_pass_pair_count: `{score['main_board_pass_pair_count']}`",
            f"- compared_pair_count: `{arm_comparison['compared_pair_count']}`",
            f"- stable_pass_count: `{arm_comparison['stable_pass_count']}`",
            f"- regressed_pair_count: `{arm_comparison['regressed_pair_count']}`",
        ]
    ) + "\n"


def _deep_trace(score: dict[str, Any], failure_report: dict[str, Any], arm_comparison: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Packet 07 Narrow Fair-Runtime Rerun Deep Trace Analysis",
            "",
            f"- selected_recommendation: `{score['selected_recommendation']}`",
            f"- route_summary_main: `{score['route_summary_main']}`",
            f"- route_summary_rerun: `{score['route_summary_rerun']}`",
            f"- failure_counts_by_interpretation_class: `{failure_report['failure_counts_by_interpretation_class']}`",
            f"- failure_counts_by_root_cause: `{failure_report['failure_counts_by_root_cause']}`",
            f"- arm_comparison_rows: `{arm_comparison['rows']}`",
        ]
    ) + "\n"


def _handoff(score: dict[str, Any], arm_comparison: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Packet 07 Narrow Fair-Runtime Rerun Handoff",
            "",
            f"- mission_id: `{MISSION_ID}`",
            f"- selected_recommendation: `{score['selected_recommendation']}`",
            f"- compared_pair_count: `{arm_comparison['compared_pair_count']}`",
            f"- stable_pass_count: `{arm_comparison['stable_pass_count']}`",
            f"- regressed_pair_count: `{arm_comparison['regressed_pair_count']}`",
        ]
    ) + "\n"


def _raw_ledger_update(
    out: Path,
    score: dict[str, Any],
    failure_report: dict[str, Any],
    arm_comparison: dict[str, Any],
) -> str:
    return "\n".join(
        [
            "RAW_LEDGER_UPDATE",
            "- actor: codex",
            "- task: Packet 07 narrow fair-runtime rerun",
            "- event_type: experiment",
            f"- summary: Ran a narrow Packet 07 fair-runtime rerun on two Letta evals with recommendation `{score['selected_recommendation']}`.",
            f"- observations: run_count `{score['run_count']}`; main_board_pass_pair_count `{score['main_board_pass_pair_count']}`; stable_pass_count `{arm_comparison['stable_pass_count']}`; regressed_pair_count `{arm_comparison['regressed_pair_count']}`; failure_count `{failure_report['failure_count']}`.",
            "- inference: This slice isolates whether main-board winners remain stable under a tighter fair-runtime budget while preserving orientation injection and explicit python3 execution contract.",
            f"- evidence_paths: {out / 'packet07_fair_runtime_rerun_narrow_result_records.jsonl'}; {out / 'packet07_fair_runtime_rerun_narrow_score_envelope.json'}; {out / 'packet07_fair_runtime_rerun_narrow_trace_report.json'}; {out / 'packet07_fair_runtime_rerun_narrow_failure_source_report.json'}; {out / 'packet07_fair_runtime_rerun_narrow_arm_comparison_report.json'}; {out / 'packet07_fair_runtime_rerun_narrow_deep_trace_analysis.md'}",
            "- affected_components: runner/packet07_fair_runtime_rerun_narrow.py; tests/test_packet07_fair_runtime_rerun_narrow.py; fair-runtime rerun artifacts",
            "- decision_change: Added a narrow Packet 07 fair-runtime rerun driver that rechecks only passing eval/variant pairs at lower step budget.",
            "- unresolved_questions: Whether any pair regressions are runtime-budget sensitivity or path/closure mechanics that still need route-level adjustment.",
            "- confidence: medium",
            "- commit_message: HOLD - add Packet 07 narrow fair-runtime rerun driver and tests",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--no-execute", action="store_true")
    parser.add_argument("--max-workers", type=int, default=2)
    parser.add_argument("--model-tier-selector", choices=MODEL_TIER_SELECTORS, default="screening_default")
    args = parser.parse_args(argv)
    print(
        json.dumps(
            launch_narrow_fair_runtime_rerun(
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
