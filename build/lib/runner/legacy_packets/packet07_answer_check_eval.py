"""Optional Packet 07 proper eval: answer support-check from reduced evidence."""

from __future__ import annotations

import argparse
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from time import perf_counter
from typing import Any

from runner.agent import run_reference_baseline
from runner.eval_runner_router import resolve_model_route_for_route
from runner.packet04_route_manifest import PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE, build_packet04_route_manifest
from runner.packet07_cycle1_context_targeted_autoresearch import _authority, _record_ledger, _usage, _write_json, _write_jsonl, _write_text

MISSION_ID = "packet07_answer_check_eval"
EVAL_ID = "answer_check_v1"
LANE_ID = "hard_row_answer_robustness_optional_second_eval"
ROUTE_ID = "candidate_plus_path_normalized_verifier_repair_projection_01"
DEFAULT_OUTPUT_DIR = Path("tracking/collab/stage_03_execution_planning/packets/packet_07_hard_row_answer_check/runs/answer_check_v1")
DEFAULT_MODEL = "gpt-5.4-mini"
COMPARISON_MODEL = "gpt-5.3-codex"


def launch_packet07_answer_check_eval(*, output_dir: str | Path, execute: bool = False, include_comparison: bool = True) -> dict[str, Any]:
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    spec = _spec()
    fixture_dir = out / "fixture_workspace"
    _seed_workspace(fixture_dir, spec["workspace_files"])
    ceiling = _deterministic_ceiling(fixture_dir)
    models = [DEFAULT_MODEL] + ([COMPARISON_MODEL] if include_comparison else [])
    run_spec = {
        "mission_id": MISSION_ID,
        "eval_id": EVAL_ID,
        "lane_id": LANE_ID,
        "purpose": spec["purpose"],
        "route_id": ROUTE_ID,
        "models": models,
        "contract": spec["task_contract"],
        "admission_level": spec["admission_level"],
        "ground_truth": {
            "expected_final_value": ceiling["expected_final_value"],
            "proposed_answer_supported": ceiling["proposed_answer_supported"],
        },
        "authority": _authority(),
        "ceiling_check": {"deterministic": True},
    }
    _write_json(out / f"{EVAL_ID}_run_spec.json", run_spec)
    records: list[dict[str, Any]] = [_record_for_ceiling(ceiling)]
    if execute:
        for model_id in models:
            records.append(_run_model(out=out, spec=spec, model_id=model_id, expected_final_value=ceiling["expected_final_value"]))
    score = _score_envelope(records=records, planned_model_runs=len(models), execute=execute, expected_final_value=ceiling["expected_final_value"])
    summary = _summary(records, score, ceiling)
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
    evidence = {
        "evidence": [
            {"evidence_id": "ev_a", "status": "grounded", "grounded": True, "weight": 0.58},
            {"evidence_id": "ev_b", "status": "grounded", "grounded": True, "weight": 0.72},
            {"evidence_id": "ev_c", "status": "grounded", "grounded": True, "weight": 0.65},
            {"evidence_id": "ev_d", "status": "retracted", "grounded": True, "weight": 0.95},
            {"evidence_id": "ev_e", "status": "disputed", "grounded": False, "weight": 0.91},
        ],
        "candidate_claims": [
            {"claim_id": "claim_1", "final_value": "41", "support_ids": ["ev_a", "ev_d"], "claim_rank": 3},
            {"claim_id": "claim_2", "final_value": "37", "support_ids": ["ev_b", "ev_c"], "claim_rank": 1},
            {"claim_id": "claim_3", "final_value": "39", "support_ids": ["ev_a", "ev_b"], "claim_rank": 2},
            {"claim_id": "claim_4", "final_value": "43", "support_ids": ["ev_b"], "claim_rank": 4},
        ],
    }
    proposed = {
        "proposed_claim_id": "claim_1",
        "proposed_final_value": "41",
        "proposed_support_ids": ["ev_a", "ev_d"],
        "note": "Proposed answer from a prior reduced pass. Must be verified against grounded evidence before acceptance.",
    }
    policy = {
        "support_requirements": {"min_grounded_support": 2, "disallowed_statuses": ["retracted", "conflicted", "disputed"]},
        "selection_rule": {"primary": "max_support_weight_sum", "tie_breaker": "lowest_claim_rank"},
        "answer_format": "Return only the final value, no explanation.",
    }
    prompt = "\n".join(
        [
            "Given a proposed final answer plus reduced supporting evidence, verify whether the proposal is supported.",
            "Workspace files: `reduced_evidence.json`, `candidate_answer.json`, `answer_policy.json`.",
            "If proposed answer is unsupported, return the corrected final value selected from supported claims under the policy.",
            "Return only the final value.",
        ]
    )
    return {
        "purpose": "Check whether a proposed answer is evidence-supported and return the correct final value.",
        "admission_level": "diagnostic",
        "task_contract": {"task_id": EVAL_ID, "task_prompt": prompt, "non_goals": ["No context traversal", "No fetching additional evidence"], "deterministic_grading": True},
        "workspace_files": {
            "reduced_evidence.json": json.dumps(evidence, indent=2, sort_keys=True) + "\n",
            "candidate_answer.json": json.dumps(proposed, indent=2, sort_keys=True) + "\n",
            "answer_policy.json": json.dumps(policy, indent=2, sort_keys=True) + "\n",
        },
    }


def _seed_workspace(workspace: Path, files: dict[str, str]) -> None:
    workspace.mkdir(parents=True, exist_ok=True)
    for rel, content in files.items():
        path = workspace / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def _deterministic_ceiling(workspace: Path) -> dict[str, Any]:
    evidence_doc = json.loads((workspace / "reduced_evidence.json").read_text(encoding="utf-8"))
    proposed = json.loads((workspace / "candidate_answer.json").read_text(encoding="utf-8"))
    policy = json.loads((workspace / "answer_policy.json").read_text(encoding="utf-8"))
    evidence_by_id = {row["evidence_id"]: row for row in evidence_doc["evidence"]}
    min_support = int(policy["support_requirements"]["min_grounded_support"])
    banned = {str(v) for v in policy["support_requirements"]["disallowed_statuses"]}

    def support_ok(support_ids: list[str]) -> tuple[bool, float]:
        if len(support_ids) < min_support:
            return False, 0.0
        total = 0.0
        for support_id in support_ids:
            row = evidence_by_id.get(support_id)
            if not row or not bool(row.get("grounded")) or str(row.get("status")) in banned:
                return False, 0.0
            total += float(row.get("weight", 0.0))
        return True, total

    winners: list[dict[str, Any]] = []
    for claim in evidence_doc["candidate_claims"]:
        ok, weight_sum = support_ok([str(s) for s in claim.get("support_ids", [])])
        if not ok:
            continue
        winners.append({**claim, "support_weight_sum": weight_sum})
    winner = sorted(winners, key=lambda r: (-float(r["support_weight_sum"]), int(r["claim_rank"])))[0]
    proposed_supported = any(
        str(c.get("claim_id")) == str(proposed.get("proposed_claim_id"))
        and str(c.get("final_value")) == str(proposed.get("proposed_final_value"))
        and support_ok([str(s) for s in c.get("support_ids", [])])[0]
        for c in evidence_doc["candidate_claims"]
    )
    return {"expected_final_value": str(winner["final_value"]), "winner_claim_id": str(winner["claim_id"]), "proposed_answer_supported": bool(proposed_supported), "supported_claim_count": len(winners)}


def _run_model(*, out: Path, spec: dict[str, Any], model_id: str, expected_final_value: str) -> dict[str, Any]:
    run_id = f"{MISSION_ID}__{EVAL_ID}__{model_id}"
    run_dir = out / "runs" / run_id
    workspace = run_dir / "workspace"
    _seed_workspace(workspace, spec["workspace_files"])
    route = resolve_model_route_for_route({"execution_mode": "sync_interactive", "model_tier_policy": {k: f"azure:{model_id}" for k in ("screening_default", "screening_fallback", "promotion_tier")}})
    started = perf_counter()
    result = run_reference_baseline(run_id=run_id, run_dir=run_dir, task_id=EVAL_ID, task_prompt=spec["task_contract"]["task_prompt"], benchmark_family="packet07_answer_check", case_id=EVAL_ID, seed_id=ROUTE_ID, model_route=route, model_client_kwargs={"timeout_sec": 120, "max_retries": 1}, max_steps=12, timeout_sec=120, cwd=workspace, route_manifest=build_packet04_route_manifest(ROUTE_ID, scope=PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE), enforce_packet04_route_contract=True)
    final_answer = str(result.get("execution", {}).get("last_completion", {}).get("text") or "")
    grade = grade_answer_check_response(final_answer=final_answer, expected_final_value=expected_final_value)
    return {"run_id": run_id, "eval_id": EVAL_ID, "row_type": "model_run", "model_id": model_id, "route_id": ROUTE_ID, "final_answer": final_answer, "expected_final_value": expected_final_value, "grade": grade, "pass_fail": bool(grade["verdict"] == "pass"), "step_count": int(result.get("execution", {}).get("step_count", 0) or 0), "trace_path": str(run_dir / "run_events.jsonl"), "timing_sec": perf_counter() - started, "token_and_cost_summary": _usage(result)}


def _normalize_numeric(value: str) -> str:
    try:
        dec = Decimal(str(value))
    except InvalidOperation:
        return ""
    normalized = format(dec.normalize(), "f")
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    return "0" if normalized in {"-0", ""} else normalized


def grade_answer_check_response(*, final_answer: str, expected_final_value: str) -> dict[str, Any]:
    match = re.search(r"-?\d+(?:\.\d+)?", final_answer)
    if not match:
        return {"verdict": "fail", "reason_codes": ["no_final_value_found"]}
    observed = _normalize_numeric(match.group(0))
    expected = _normalize_numeric(expected_final_value)
    if observed != expected:
        return {"verdict": "fail", "reason_codes": ["final_value_mismatch"], "observed_final_value": observed}
    return {"verdict": "pass", "reason_codes": [], "observed_final_value": observed}


def _record_for_ceiling(ceiling: dict[str, Any]) -> dict[str, Any]:
    return {"run_id": f"{MISSION_ID}__{EVAL_ID}__deterministic_ceiling", "eval_id": EVAL_ID, "row_type": "deterministic_ceiling", "model_id": "deterministic_solver", "route_id": "deterministic", "final_answer": str(ceiling["expected_final_value"]), "expected_final_value": str(ceiling["expected_final_value"]), "grade": {"verdict": "pass", "reason_codes": []}, "pass_fail": True, "winner_claim_id": str(ceiling["winner_claim_id"]), "proposed_answer_supported": bool(ceiling["proposed_answer_supported"]), "supported_claim_count": int(ceiling["supported_claim_count"]), "trace_path": None}


def _score_envelope(*, records: list[dict[str, Any]], planned_model_runs: int, execute: bool, expected_final_value: str) -> dict[str, Any]:
    model_rows = [r for r in records if r["row_type"] == "model_run"]
    pass_count = sum(1 for r in model_rows if r["pass_fail"])
    return {"mission_id": MISSION_ID, "eval_id": EVAL_ID, "execute_mode": "run" if execute else "prepare", "expected_final_value": expected_final_value, "planned_model_runs": planned_model_runs, "executed_model_runs": len(model_rows), "model_pass_count": pass_count, "model_fail_count": len(model_rows) - pass_count, "model_pass_rate": (pass_count / len(model_rows)) if model_rows else None, "ceiling_pass": any(r["row_type"] == "deterministic_ceiling" and r["pass_fail"] for r in records), "score_rows": [{"run_id": r["run_id"], "row_type": r["row_type"], "model_id": r["model_id"], "pass_fail": r["pass_fail"]} for r in records]}


def _summary(records: list[dict[str, Any]], score: dict[str, Any], ceiling: dict[str, Any]) -> dict[str, Any]:
    return {"mission_id": MISSION_ID, "eval_id": EVAL_ID, "records": len(records), "ceiling_pass": bool(score["ceiling_pass"]), "proposed_answer_supported_in_fixture": bool(ceiling["proposed_answer_supported"]), "expected_final_value": str(ceiling["expected_final_value"]), "model_pass_rate": score["model_pass_rate"], "status": "ready_for_model_runs" if score["executed_model_runs"] == 0 else "scored"}


def _summary_table(summary: dict[str, Any]) -> str:
    return "\n".join(["# Answer Check Summary", "", "| metric | value |", "|---|---|", f"| eval_id | {summary['eval_id']} |", f"| records | {summary['records']} |", f"| ceiling_pass | {summary['ceiling_pass']} |", f"| proposed_answer_supported_in_fixture | {summary['proposed_answer_supported_in_fixture']} |", f"| expected_final_value | {summary['expected_final_value']} |", f"| model_pass_rate | {summary['model_pass_rate']} |", f"| status | {summary['status']} |"])


def _decision_memo(summary: dict[str, Any], score: dict[str, Any]) -> str:
    recommendation = "proceed_with_model_board" if summary["ceiling_pass"] else "fix_eval_contract"
    return "\n".join(["# Decision Memo", "", f"- eval_id: `{EVAL_ID}`", f"- admission_level: `diagnostic`", f"- route_id: `{ROUTE_ID}`", f"- expected_final_value: `{score['expected_final_value']}`", f"- executed_model_runs: `{score['executed_model_runs']}`", f"- recommendation: `{recommendation}`"])


def _handoff(out: Path, summary: dict[str, Any]) -> str:
    return "\n".join(["# Handoff", "", f"- mission_id: `{MISSION_ID}`", f"- eval_id: `{EVAL_ID}`", f"- lane_id: `{LANE_ID}`", f"- status: `{summary['status']}`", f"- output_root: `{out}`"])


def _ledger(out: Path, summary: dict[str, Any], score: dict[str, Any]) -> str:
    return "\n".join(["RAW_LEDGER_UPDATE", "- actor: codex", "- task: implement optional second proper eval for hard-row answer robustness lane", "- event_type: implementation", f"- summary: Added `{EVAL_ID}` to verify proposed answers against reduced evidence with deterministic ceiling and scored model rows.", f"- observations: ceiling_pass `{score['ceiling_pass']}`; executed_model_runs `{score['executed_model_runs']}`; expected_final_value `{score['expected_final_value']}`; status `{summary['status']}`.", "- inference: The lane can now measure answer-support verification without context traversal and without ground-truth leakage in prompt instructions.", f"- evidence_paths: {out / f'{EVAL_ID}_run_spec.json'}; {out / f'{EVAL_ID}_score_envelope.json'}; {out / f'{EVAL_ID}_decision_memo.md'}; {out / f'{EVAL_ID}_handoff.md'}", "- affected_components: packet07 hard-row answer robustness optional second proper eval lane", "- decision_change: no promotion decision; eval prepared for governed model-backed scoring", "- unresolved_questions: Whether answer_check_v1 should become a promotion gate after baseline+comparison evidence accrues.", "- confidence: high", "- commit_message: HOLD - add answer_check_v1 proper eval runner with deterministic grading bundle"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--no-comparison", action="store_true")
    args = parser.parse_args(argv)
    print(json.dumps(launch_packet07_answer_check_eval(output_dir=args.output_dir, execute=bool(args.execute), include_comparison=not bool(args.no_comparison)), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
