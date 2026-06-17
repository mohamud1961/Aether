"""Reduction-focused Packet 07 eval: reduced records -> correct final scalar."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from time import perf_counter
from typing import Any

from runner.agent import run_reference_baseline
from runner.eval_runner_router import resolve_model_route_for_route
from runner.packet04_route_manifest import PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE, build_packet04_route_manifest
from runner.packet07_cycle1_context_targeted_autoresearch import _authority, _record_ledger, _usage, _write_json, _write_jsonl, _write_text

MISSION_ID = "packet07_reduce_and_select_eval"
EVAL_ID = "reduce_and_select_v1"
ROUTE_ID = "candidate_plus_path_normalized_verifier_repair_projection_01"
DEFAULT_OUTPUT_DIR = Path("tracking/collab/stage_03_execution_planning/packets/packet_07_hard_row_reduce_select/runs/reduce_and_select_v1")
DEFAULT_MODEL = "gpt-5.4-mini"
COMPARISON_MODEL = "gpt-5.3-codex"


def launch_reduce_and_select_eval(*, output_dir: str | Path, execute: bool = False, include_comparison: bool = True) -> dict[str, Any]:
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    spec = _spec()
    fixture_dir = out / "fixture_workspace"
    _seed_workspace(fixture_dir, spec["workspace_files"])
    ceiling = _deterministic_ceiling(fixture_dir)
    planned_models = [DEFAULT_MODEL] + ([COMPARISON_MODEL] if include_comparison else [])
    run_spec = {"mission_id": MISSION_ID, "eval_id": EVAL_ID, "purpose": spec["purpose"], "route_id": ROUTE_ID, "models": planned_models, "contract": spec["task_contract"], "admission_level": spec["admission_level"], "ground_truth": {"final_scalar": ceiling["expected_scalar"]}, "authority": _authority(), "ceiling_check": {"deterministic": True}}
    _write_json(out / f"{EVAL_ID}_run_spec.json", run_spec)
    records = [_record_for_ceiling(ceiling)]
    if execute:
        for model_id in planned_models:
            records.append(_run_model(out=out, fixture_files=spec["workspace_files"], model_id=model_id, expected_scalar=ceiling["expected_scalar"]))
    score = _score_envelope(records=records, planned_model_runs=len(planned_models), execute=execute, expected_scalar=ceiling["expected_scalar"])
    summary = _summary(records, score)
    _write_jsonl(out / f"{EVAL_ID}_result_records.jsonl", records)
    _write_json(out / f"{EVAL_ID}_score_envelope.json", score)
    _write_json(out / f"{EVAL_ID}_summary.json", summary)
    _write_text(out / f"{EVAL_ID}_summary_table.md", _summary_table(summary))
    _write_text(out / f"{EVAL_ID}_decision_memo.md", _decision_memo(summary, score))
    _write_text(out / f"{EVAL_ID}_handoff.md", _handoff(out, summary))
    ledger = _ledger(out, summary, score)
    _write_text(out / "RAW_LEDGER_UPDATE", ledger)
    _record_ledger(ledger)
    return {"mission_id": MISSION_ID, "eval_id": EVAL_ID, "status": "executed" if execute else "prepared", "output_dir": str(out), "record_count": len(records), "score_envelope_path": str(out / f"{EVAL_ID}_score_envelope.json")}


def _spec() -> dict[str, Any]:
    rows = [
        {"candidate_id": "c01", "grounded": True, "evidence_count": 3, "candidate_rank": 3, "base_value": 30.412, "penalty": 4.0, "bonus": 1.111},
        {"candidate_id": "c02", "grounded": True, "evidence_count": 2, "candidate_rank": 2, "base_value": 27.25, "penalty": 0.25, "bonus": 2.375},
        {"candidate_id": "c03", "grounded": True, "evidence_count": 4, "candidate_rank": 1, "base_value": 31.003, "penalty": 3.126, "bonus": 0.145},
        {"candidate_id": "c04", "grounded": False, "evidence_count": 8, "candidate_rank": 0, "base_value": 90.0, "penalty": 0.0, "bonus": 0.0},
        {"candidate_id": "c05", "grounded": True, "evidence_count": 1, "candidate_rank": 4, "base_value": 70.0, "penalty": 0.0, "bonus": 0.0},
        {"candidate_id": "c06", "grounded": True, "evidence_count": 2, "candidate_rank": 5, "base_value": 29.2, "penalty": 2.0, "bonus": 0.555},
    ]
    policy = {"eligibility": {"grounded": True, "min_evidence_count": 2}, "score_formula": "adjusted = base_value - penalty + bonus", "selection": {"key": "max_adjusted", "tie_breaker": "lowest_candidate_rank"}, "answer_format": "Return only the final scalar with exactly three decimal places."}
    prompt = "\n".join(["Compute the final scalar from the already-reduced grounded records in this workspace.", "Read `grounded_records.jsonl` and `reduction_policy.json`.", "Apply the policy exactly and output only the scalar (three decimal places)."])
    return {"purpose": "Given grounded/reduced records in workspace, compute the correct final scalar/value.", "admission_level": "diagnostic", "task_contract": {"task_id": EVAL_ID, "task_prompt": prompt, "non_goals": ["No context traversal", "No data acquisition outside provided reduced files"], "deterministic_grading": True}, "workspace_files": {"grounded_records.jsonl": "\n".join(json.dumps(r, sort_keys=True) for r in rows) + "\n", "reduction_policy.json": json.dumps(policy, indent=2, sort_keys=True) + "\n"}}


def _seed_workspace(workspace: Path, files: dict[str, str]) -> None:
    workspace.mkdir(parents=True, exist_ok=True)
    for rel, content in files.items():
        path = workspace / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def _deterministic_ceiling(workspace: Path) -> dict[str, Any]:
    policy = json.loads((workspace / "reduction_policy.json").read_text(encoding="utf-8"))
    rows = [json.loads(line) for line in (workspace / "grounded_records.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    eligible = [r for r in rows if bool(r.get("grounded")) is bool(policy["eligibility"]["grounded"]) and int(r.get("evidence_count", 0)) >= int(policy["eligibility"]["min_evidence_count"])]
    scored = [{**r, "adjusted": float(r["base_value"]) - float(r["penalty"]) + float(r["bonus"])} for r in eligible]
    winner = sorted(scored, key=lambda r: (-r["adjusted"], int(r["candidate_rank"])))[0]
    return {"expected_scalar": f"{winner['adjusted']:.3f}", "winner_candidate_id": winner["candidate_id"], "eligible_count": len(eligible)}


def _run_model(*, out: Path, fixture_files: dict[str, str], model_id: str, expected_scalar: str) -> dict[str, Any]:
    run_id = f"{MISSION_ID}__{EVAL_ID}__{model_id}"
    run_dir = out / "runs" / run_id
    workspace = run_dir / "workspace"
    _seed_workspace(workspace, fixture_files)
    model_route = resolve_model_route_for_route({"execution_mode": "sync_interactive", "model_tier_policy": {k: f"azure:{model_id}" for k in ("screening_default", "screening_fallback", "promotion_tier")}})
    started = perf_counter()
    result = run_reference_baseline(run_id=run_id, run_dir=run_dir, task_id=EVAL_ID, task_prompt=_spec()["task_contract"]["task_prompt"], benchmark_family="packet07_reduce_select", case_id=EVAL_ID, seed_id=ROUTE_ID, model_route=model_route, model_client_kwargs={"timeout_sec": 120, "max_retries": 1}, max_steps=12, timeout_sec=120, cwd=workspace, route_manifest=build_packet04_route_manifest(ROUTE_ID, scope=PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE), enforce_packet04_route_contract=True)
    final_answer = str(result.get("execution", {}).get("last_completion", {}).get("text") or "")
    grade = grade_reduce_and_select_answer(final_answer=final_answer, expected_scalar=expected_scalar)
    return {"run_id": run_id, "eval_id": EVAL_ID, "row_type": "model_run", "model_id": model_id, "route_id": ROUTE_ID, "final_answer": final_answer, "expected_scalar": expected_scalar, "grade": grade, "pass_fail": bool(grade["verdict"] == "pass"), "step_count": int(result.get("execution", {}).get("step_count", 0) or 0), "trace_path": str(run_dir / "run_events.jsonl"), "timing_sec": perf_counter() - started, "token_and_cost_summary": _usage(result)}


def _record_for_ceiling(ceiling: dict[str, Any]) -> dict[str, Any]:
    return {"run_id": f"{MISSION_ID}__{EVAL_ID}__deterministic_ceiling", "eval_id": EVAL_ID, "row_type": "deterministic_ceiling", "model_id": "deterministic_solver", "route_id": "deterministic", "final_answer": str(ceiling["expected_scalar"]), "expected_scalar": str(ceiling["expected_scalar"]), "grade": {"verdict": "pass", "reason_codes": []}, "pass_fail": True, "winner_candidate_id": str(ceiling["winner_candidate_id"]), "eligible_count": int(ceiling["eligible_count"]), "trace_path": None}


def grade_reduce_and_select_answer(*, final_answer: str, expected_scalar: str) -> dict[str, Any]:
    match = re.search(r"-?\d+(?:\.\d+)?", final_answer)
    if not match:
        return {"verdict": "fail", "reason_codes": ["no_scalar_found"]}
    observed = f"{float(match.group(0)):.3f}"
    if observed != expected_scalar:
        return {"verdict": "fail", "reason_codes": ["scalar_mismatch"], "observed_scalar": observed}
    return {"verdict": "pass", "reason_codes": [], "observed_scalar": observed}


def _score_envelope(*, records: list[dict[str, Any]], planned_model_runs: int, execute: bool, expected_scalar: str) -> dict[str, Any]:
    model_rows = [r for r in records if r["row_type"] == "model_run"]
    pass_count = sum(1 for r in model_rows if r["pass_fail"])
    return {"mission_id": MISSION_ID, "eval_id": EVAL_ID, "execute_mode": "run" if execute else "prepare", "expected_scalar": expected_scalar, "planned_model_runs": planned_model_runs, "executed_model_runs": len(model_rows), "model_pass_count": pass_count, "model_fail_count": len(model_rows) - pass_count, "model_pass_rate": (pass_count / len(model_rows)) if model_rows else None, "ceiling_pass": any(r["row_type"] == "deterministic_ceiling" and r["pass_fail"] for r in records), "score_rows": [{"run_id": r["run_id"], "row_type": r["row_type"], "model_id": r["model_id"], "pass_fail": r["pass_fail"]} for r in records]}


def _summary(records: list[dict[str, Any]], score: dict[str, Any]) -> dict[str, Any]:
    return {"mission_id": MISSION_ID, "eval_id": EVAL_ID, "records": len(records), "ceiling_pass": bool(score["ceiling_pass"]), "model_pass_rate": score["model_pass_rate"], "status": "ready_for_model_runs" if score["executed_model_runs"] == 0 else "scored"}


def _summary_table(summary: dict[str, Any]) -> str:
    return "\n".join(["# Reduce And Select Summary", "", "| metric | value |", "|---|---|", f"| eval_id | {summary['eval_id']} |", f"| records | {summary['records']} |", f"| ceiling_pass | {summary['ceiling_pass']} |", f"| model_pass_rate | {summary['model_pass_rate']} |", f"| status | {summary['status']} |"])


def _decision_memo(summary: dict[str, Any], score: dict[str, Any]) -> str:
    recommendation = "proceed_with_route_check" if summary["ceiling_pass"] else "fix_deterministic_contract"
    return "\n".join(["# Decision Memo", "", f"- eval_id: `{EVAL_ID}`", f"- admission_level: `diagnostic`", f"- expected_scalar: `{score['expected_scalar']}`", f"- executed_model_runs: `{score['executed_model_runs']}`", f"- recommendation: `{recommendation}`"])


def _handoff(out: Path, summary: dict[str, Any]) -> str:
    return "\n".join(["# Handoff", "", f"- mission_id: `{MISSION_ID}`", f"- eval_id: `{EVAL_ID}`", f"- status: `{summary['status']}`", f"- output_root: `{out}`"])


def _ledger(out: Path, summary: dict[str, Any], score: dict[str, Any]) -> str:
    return "\n".join(["RAW_LEDGER_UPDATE", "- actor: codex", "- task: implement reduce-and-select hard-row eval", "- event_type: implementation", f"- summary: Added `{EVAL_ID}` with deterministic ceiling and model score rows; status `{summary['status']}`.", f"- observations: ceiling_pass `{score['ceiling_pass']}`; executed_model_runs `{score['executed_model_runs']}`; expected_scalar `{score['expected_scalar']}`.", "- inference: This isolates reduction/select capability without context traversal and provides deterministic admission scaffolding.", f"- evidence_paths: {out / f'{EVAL_ID}_run_spec.json'}; {out / f'{EVAL_ID}_score_envelope.json'}; {out / f'{EVAL_ID}_decision_memo.md'}", "- affected_components: runner packet07 reduction-focused eval lane; scoreboard-ready artifacts", "- decision_change: no promotion decision; eval lane prepared for governed model-backed scoring", "- unresolved_questions: Should this eval become certified after baseline+comparison model evidence.", "- confidence: high", "- commit_message: HOLD - add reduce_and_select_v1 eval runner and deterministic grading bundle"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--no-comparison", action="store_true")
    args = parser.parse_args(argv)
    print(json.dumps(launch_reduce_and_select_eval(output_dir=args.output_dir, execute=bool(args.execute), include_comparison=not bool(args.no_comparison)), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
