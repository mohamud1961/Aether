"""Packet 07 fair rerun: main arm + short-budget rerun on passing pairs only."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path
from time import perf_counter
from typing import Any

from runner.agent import run_reference_baseline
from runner.packet07_cycle1_context_targeted_autoresearch import (
    MODEL_TIER_SELECTORS,
    _authority,
    _context_specs,
    _grade_spec,
    _seed_workspace,
    _usage,
    _write_json,
    _write_jsonl,
    _write_text,
    resolve_packet07_context_model_route,
)
from runner.packet07_golden_diagnostic import (
    APP_EVIDENCE_VARIANT,
    BACKBONE_INCUMBENT,
    _build_route_manifest,
    _classify_root_cause,
    _orientation_env,
    _tool_trace_fields,
)

MISSION_ID = "packet07_golden_diagnostic_fair_rerun"
DEFAULT_OUTPUT_DIR = Path(
    "tracking/collab/stage_03_execution_planning/packets/packet_06_paired_combo_variants/"
    "runs/2026-05-12_packet07_golden_diagnostic_fair_rerun"
)
EVAL_IDS = ("letta_filesystem_001_easy", "letta_filesystem_002_medium")
ROUTES = (BACKBONE_INCUMBENT, APP_EVIDENCE_VARIANT)
MAIN_ARM = {"arm_id": "main_12", "max_steps": 12, "inject_orientation": True, "python_contract": True}
RERUN_ARM = {"arm_id": "rerun_7", "max_steps": 7, "inject_orientation": True, "python_contract": True}


def launch_packet07_golden_diagnostic_fair_rerun(
    *,
    output_dir: str | Path,
    execute: bool = False,
    model_tier_selector: str = "screening_default",
) -> dict[str, Any]:
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    specs = _specs_for_evals()
    run_spec = {
        "mission_id": MISSION_ID,
        "eval_ids": list(EVAL_IDS),
        "variants": list(ROUTES),
        "arms": [dict(MAIN_ARM), dict(RERUN_ARM)],
        "model_tier_selector": model_tier_selector,
        "authority": _authority(),
    }
    _write_json(out / "score_envelope.json", {"mission_id": MISSION_ID, "status": "prepared", "run_spec": run_spec})
    if not execute:
        return {"mission_id": MISSION_ID, "status": "prepared", "output_dir": str(out)}

    rows: list[dict[str, Any]] = []
    main_rows: list[dict[str, Any]] = []
    for spec in specs:
        for variant in ROUTES:
            row = _run_one(out, spec, variant, MAIN_ARM, model_tier_selector=model_tier_selector)
            rows.append(row)
            main_rows.append(row)
    passing_pairs = {(r["eval_id"], r["variant_id"]) for r in main_rows if r["exact_grade"].get("verdict") == "pass"}
    for spec in specs:
        for variant in ROUTES:
            if (spec["eval_id"], variant) not in passing_pairs:
                continue
            rows.append(_run_one(out, spec, variant, RERUN_ARM, model_tier_selector=model_tier_selector))
    _write_bundle(out, rows, run_spec)
    return {"mission_id": MISSION_ID, "status": "executed", "output_dir": str(out), "record_count": len(rows)}


def _specs_for_evals() -> list[dict[str, Any]]:
    lookup = {row["eval_id"]: row for row in _context_specs()}
    return [dict(lookup[eval_id]) for eval_id in EVAL_IDS]


def _run_one(
    out: Path,
    spec: dict[str, Any],
    variant: str,
    arm: dict[str, Any],
    *,
    model_tier_selector: str,
) -> dict[str, Any]:
    run_id = f"{MISSION_ID}__{spec['eval_id']}__{arm['arm_id']}__{variant}__r0"
    run_dir = out / "runs" / run_id
    workspace = run_dir / "workspace"
    _seed_workspace(workspace, spec)
    started = perf_counter()
    model_route = resolve_packet07_context_model_route(model_tier_selector=model_tier_selector)
    result = run_reference_baseline(
        run_id=run_id,
        run_dir=run_dir,
        task_id=str(spec["task_id"]),
        task_prompt=str(spec["task_prompt"]),
        benchmark_family=str(spec["benchmark_class"]),
        model_route=model_route,
        max_steps=int(arm["max_steps"]),
        timeout_sec=int(spec["timeout_sec"]),
        cwd=workspace,
        route_manifest=_build_route_manifest(variant, arm),
        enforce_packet04_route_contract=True,
        orientation_env_overrides=_orientation_env(workspace, arm),
    )
    grade = _grade_spec(spec, result, workspace)
    commands, exit_codes = _tool_trace_fields(result.get("run_events", []))
    final_answer = str(result.get("execution", {}).get("last_completion", {}).get("text") or "")
    model_id = str(model_route.get("request_settings", {}).get("pricing_model_id") or model_route.get("model_name") or "")
    step_count = int(result.get("execution", {}).get("step_count", 0) or 0)
    return {
        "mission_id": MISSION_ID,
        "run_id": run_id,
        "eval_id": spec["eval_id"],
        "task_id": spec["task_id"],
        "arm_id": arm["arm_id"],
        "variant_id": variant,
        "model_id": model_id,
        "max_steps": int(arm["max_steps"]),
        "trace_path": str(run_dir / "run_events.jsonl"),
        "final_answer": final_answer,
        "exact_grade": grade,
        "step_count": step_count,
        "tool_commands": commands,
        "exit_codes": exit_codes,
        "token_and_cost_summary": _usage(result),
        "root_cause_classification": _classify_root_cause(
            grade=grade, commands=commands, exit_codes=exit_codes, final_answer=final_answer, max_steps=int(arm["max_steps"]), step_count=step_count
        ),
        "timing_summary": {"run_wall_sec": perf_counter() - started},
    }


def _write_bundle(out: Path, rows: list[dict[str, Any]], run_spec: dict[str, Any]) -> None:
    _write_jsonl(out / "result_records.jsonl", rows)
    verdict_counts = Counter(str(r.get("exact_grade", {}).get("verdict", "unknown")) for r in rows)
    arm_variant_scores: dict[str, dict[str, dict[str, float]]] = defaultdict(lambda: defaultdict(dict))
    for r in rows:
        arm_variant_scores[r["arm_id"]][r["eval_id"]][r["variant_id"]] = 1.0 if r["exact_grade"].get("verdict") == "pass" else 0.0
    failures = Counter(str(r.get("root_cause_classification", "unknown")) for r in rows if r["exact_grade"].get("verdict") != "pass")
    _write_json(out / "score_envelope.json", {"mission_id": MISSION_ID, "run_spec": run_spec, "record_count": len(rows), "verdict_counts": dict(verdict_counts)})
    _write_json(out / "trace_report.json", {"mission_id": MISSION_ID, "rows": [{"run_id": r["run_id"], "trace_path": r["trace_path"]} for r in rows]})
    _write_json(out / "failure_source_report.json", {"mission_id": MISSION_ID, "failure_source_counts": dict(failures)})
    _write_json(out / "arm_comparison_report.json", {"mission_id": MISSION_ID, "arm_eval_variant_scores": arm_variant_scores})
    _write_json(
        out / "cost_report.json",
        {
            "mission_id": MISSION_ID,
            "total_tokens": sum(int(r.get("token_and_cost_summary", {}).get("total_tokens", 0) or 0) for r in rows),
            "usd_estimate": sum(float(r.get("token_and_cost_summary", {}).get("usd_estimate", 0.0) or 0.0) for r in rows),
        },
    )
    _write_text(out / "recommendation.md", _recommendation_md(rows))
    _write_text(out / "deep_trace_analysis.md", _deep_trace_analysis_md(rows))
    _write_text(out / "handoff.md", _handoff_md(rows))
    _write_text(out / "RAW_LEDGER_UPDATE", _raw_ledger_update(rows))


def _recommendation_md(rows: list[dict[str, Any]]) -> str:
    passes = sum(1 for r in rows if r["exact_grade"].get("verdict") == "pass")
    return f"# Recommendation\n\n- mission_id: `{MISSION_ID}`\n- total_runs: {len(rows)}\n- pass_runs: {passes}\n- recommendation: keep incumbent unless candidate pass-rate exceeds incumbent on both arms\n"


def _deep_trace_analysis_md(rows: list[dict[str, Any]]) -> str:
    return "# Deep Trace Analysis\n\n" + "\n".join(
        f"- `{r['run_id']}` verdict={r['exact_grade'].get('verdict')} root_cause={r['root_cause_classification']} steps={r['step_count']}/{r['max_steps']}"
        for r in rows
    ) + "\n"


def _handoff_md(rows: list[dict[str, Any]]) -> str:
    return f"# Handoff\n\n- mission_id: `{MISSION_ID}`\n- rows: {len(rows)}\n- artifact_bundle: result_records.jsonl, score_envelope.json, trace_report.json, failure_source_report.json, arm_comparison_report.json, cost_report.json, recommendation.md, deep_trace_analysis.md, handoff.md, RAW_LEDGER_UPDATE\n"


def _raw_ledger_update(rows: list[dict[str, Any]]) -> str:
    return (
        "RAW_LEDGER_UPDATE\n"
        "- actor: codex\n"
        "- task: packet07 golden diagnostic fair rerun\n"
        "- event_type: implementation\n"
        "- summary: added dedicated fair rerun runner with governed screening_default model tier and pass-only short-budget reruns\n"
        f"- observations: produced {len(rows)} total records across main and rerun arms\n"
        "- inference: rerun fairness is controlled by using identical orientation/python contract conditions with reduced max_steps\n"
        "- evidence_paths: runner/packet07_golden_diagnostic_fair_rerun.py\n"
        "- affected_components: runner\n"
        "- decision_change: none\n"
        "- unresolved_questions: none\n"
        "- confidence: medium\n"
        "- commit_message: HOLD - waiting for user review\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--model-tier-selector", choices=MODEL_TIER_SELECTORS, default="screening_default")
    args = parser.parse_args()
    launch_packet07_golden_diagnostic_fair_rerun(
        output_dir=args.output_dir,
        execute=bool(args.execute),
        model_tier_selector=str(args.model_tier_selector),
    )


if __name__ == "__main__":
    main()
