"""Packet 07 proper eval: grounded bundle -> reduce/select -> final scalar."""

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

MISSION_ID = "packet07_grounded_bundle_reduce_select_eval"
EVAL_ID = "grounded_bundle_reduce_select_v1"
ROUTE_ID = "candidate_plus_path_normalized_verifier_repair_projection_01"
DEFAULT_OUTPUT_DIR = Path("tracking/collab/stage_03_execution_planning/packets/packet_07_hard_row_grounded_bundle/runs/grounded_bundle_reduce_select_v1")
DEFAULT_MODEL = "gpt-5.4-mini"
COMPARISON_MODEL = "gpt-5.3-codex"


def launch_grounded_bundle_reduce_select_eval(*, output_dir: str | Path, execute: bool = False, include_comparison: bool = True) -> dict[str, Any]:
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    spec = _spec()
    fixture = out / "fixture_workspace"
    _seed_workspace(fixture, spec["workspace_files"])
    ceiling = _deterministic_ceiling(fixture)
    models = [DEFAULT_MODEL] + ([COMPARISON_MODEL] if include_comparison else [])
    run_spec = {
        "mission_id": MISSION_ID,
        "eval_id": EVAL_ID,
        "purpose": spec["purpose"],
        "route_id": ROUTE_ID,
        "models": models,
        "contract": spec["task_contract"],
        "admission_level": spec["admission_level"],
        "ground_truth": {"final_scalar": ceiling["expected_scalar"]},
        "authority": _authority(),
        "ceiling_check": {"deterministic": True},
    }
    _write_json(out / f"{EVAL_ID}_run_spec.json", run_spec)
    records: list[dict[str, Any]] = [_record_for_ceiling(ceiling)]
    if execute:
        for model_id in models:
            records.append(_run_model(out=out, spec=spec, model_id=model_id, expected_scalar=ceiling["expected_scalar"]))
    score = _score_envelope(records=records, planned_model_runs=len(models), execute=execute, expected_scalar=ceiling["expected_scalar"])
    summary = _summary(records, score)
    _write_jsonl(out / f"{EVAL_ID}_result_records.jsonl", records)
    _write_json(out / f"{EVAL_ID}_score_envelope.json", score)
    _write_json(out / f"{EVAL_ID}_summary.json", summary)
    _write_text(out / f"{EVAL_ID}_summary_table.md", _summary_table(summary))
    _write_text(out / f"{EVAL_ID}_decision_memo.md", _decision_memo(score))
    _write_text(out / f"{EVAL_ID}_handoff.md", _handoff(out, summary))
    ledger = _ledger(out, summary, score)
    _write_text(out / "RAW_LEDGER_UPDATE", ledger)
    _record_ledger(ledger)
    return {"mission_id": MISSION_ID, "eval_id": EVAL_ID, "status": "executed" if execute else "prepared", "output_dir": str(out), "record_count": len(records), "score_envelope_path": str(out / f"{EVAL_ID}_score_envelope.json")}


def _spec() -> dict[str, Any]:
    prompt = "\n".join(
        [
            "Compute the final scalar from already-grounded, already-reduced workspace files only.",
            "Use `anchor_profile.json` to get target state, then evaluate candidates in provided files.",
            "Pick the owner in the target state with greatest total bank balance (sum of account balances).",
            "For that owner, return only the scalar count of bank_accounts + credit_cards + vehicles + insurance_policies.",
        ]
    )
    return {
        "purpose": "Preserve late-stage reduce/select brittleness on grounded bundle snapshots.",
        "admission_level": "diagnostic",
        "task_contract": {"task_id": EVAL_ID, "task_prompt": prompt, "non_goals": ["No helper route use", "No context traversal", "No data acquisition outside provided files"], "deterministic_grading": True},
        "workspace_files": {
            "anchor_profile.json": json.dumps({"anchor_person_id": "pers-0482", "target_state": "Indiana", "candidate_owner_ids": ["pers-0406", "pers-0101", "pers-0408", "pers-0142", "pers-0090"]}, indent=2, sort_keys=True) + "\n",
            "residents.jsonl": _jsonl(
                [
                    {"owner_id": "pers-0406", "resident_id": "res-0406-a", "addresses": [{"state": "Ohio"}, {"state": "Indiana"}]},
                    {"owner_id": "pers-0101", "resident_id": "res-0101-a", "addresses": [{"state": "Indiana"}]},
                    {"owner_id": "pers-0408", "resident_id": "res-0408-a", "addresses": [{"state": "Michigan"}, {"state": "Indiana"}]},
                    {"owner_id": "pers-0142", "resident_id": "res-0142-a", "addresses": [{"state": "Illinois"}]},
                    {"owner_id": "pers-0090", "resident_id": "res-0090-a", "addresses": [{"state": "Kentucky"}, {"state": "Missouri"}]},
                ]
            ),
            "bank_accounts.jsonl": _jsonl(
                [
                    {"owner_id": "pers-0406", "account_id": "ba-1", "balance": 19000.0},
                    {"owner_id": "pers-0406", "account_id": "ba-2", "balance": 18250.0},
                    {"owner_id": "pers-0406", "account_id": "ba-3", "balance": 16400.0},
                    {"owner_id": "pers-0406", "account_id": "ba-4", "balance": 13700.0},
                    {"owner_id": "pers-0101", "account_id": "ba-5", "balance": 53000.0},
                    {"owner_id": "pers-0408", "account_id": "ba-6", "balance": 15000.0},
                    {"owner_id": "pers-0408", "account_id": "ba-7", "balance": 14000.0},
                    {"owner_id": "pers-0408", "account_id": "ba-8", "balance": 13000.0},
                    {"owner_id": "pers-0408", "account_id": "ba-9", "balance": 12000.0},
                    {"owner_id": "pers-0408", "account_id": "ba-10", "balance": 11000.0},
                    {"owner_id": "pers-0142", "account_id": "ba-11", "balance": 98000.0},
                    {"owner_id": "pers-0090", "account_id": "ba-12", "balance": 88000.0},
                ]
            ),
            "credit_cards.jsonl": _jsonl(_owned("pers-0406", "cc", 4) + _owned("pers-0408", "cc", 5) + _owned("pers-0101", "cc", 1)),
            "vehicles.jsonl": _jsonl(_owned("pers-0406", "vh", 3) + _owned("pers-0408", "vh", 4) + _owned("pers-0142", "vh", 1)),
            "insurance_policies.jsonl": _jsonl(_owned("pers-0406", "ip", 3) + _owned("pers-0408", "ip", 4) + _owned("pers-0090", "ip", 2)),
        },
    }


def _owned(owner_id: str, prefix: str, n: int) -> list[dict[str, str]]:
    return [{"owner_id": owner_id, "record_id": f"{prefix}-{i:02d}"} for i in range(1, n + 1)]


def _jsonl(rows: list[dict[str, Any]]) -> str:
    return "\n".join(json.dumps(r, sort_keys=True) for r in rows) + "\n"


def _seed_workspace(workspace: Path, files: dict[str, str]) -> None:
    workspace.mkdir(parents=True, exist_ok=True)
    for rel, content in files.items():
        (workspace / rel).write_text(content, encoding="utf-8")


def _deterministic_ceiling(workspace: Path) -> dict[str, Any]:
    anchor = json.loads((workspace / "anchor_profile.json").read_text(encoding="utf-8"))
    target = str(anchor["target_state"])
    candidates = {str(v) for v in anchor["candidate_owner_ids"]}
    residents = [json.loads(x) for x in (workspace / "residents.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    accounts = [json.loads(x) for x in (workspace / "bank_accounts.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    in_state = {r["owner_id"] for r in residents if r["owner_id"] in candidates and any(str(a.get("state")) == target for a in r.get("addresses", []))}
    balances = {owner: 0.0 for owner in in_state}
    for row in accounts:
        owner = str(row["owner_id"])
        if owner in balances:
            balances[owner] += float(row.get("balance", 0.0))
    winner = sorted(balances.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
    total_count = 0
    for name in ("bank_accounts.jsonl", "credit_cards.jsonl", "vehicles.jsonl", "insurance_policies.jsonl"):
        rows = [json.loads(x) for x in (workspace / name).read_text(encoding="utf-8").splitlines() if x.strip()]
        total_count += sum(1 for r in rows if str(r.get("owner_id")) == winner)
    return {"expected_scalar": str(total_count), "winner_owner_id": winner, "target_state": target}


def grade_grounded_bundle_reduce_select_answer(*, final_answer: str, expected_scalar: str) -> dict[str, Any]:
    match = re.search(r"-?\d+", final_answer)
    if not match:
        return {"verdict": "fail", "reason_codes": ["no_scalar_found"]}
    observed = str(int(match.group(0)))
    return {"verdict": "pass", "reason_codes": [], "observed_scalar": observed} if observed == str(expected_scalar) else {"verdict": "fail", "reason_codes": ["scalar_mismatch"], "observed_scalar": observed}


def _run_model(*, out: Path, spec: dict[str, Any], model_id: str, expected_scalar: str) -> dict[str, Any]:
    run_id = f"{MISSION_ID}__{EVAL_ID}__{model_id}"
    run_dir = out / "runs" / run_id
    workspace = run_dir / "workspace"
    _seed_workspace(workspace, spec["workspace_files"])
    route = resolve_model_route_for_route({"execution_mode": "sync_interactive", "model_tier_policy": {k: f"azure:{model_id}" for k in ("screening_default", "screening_fallback", "promotion_tier")}})
    started = perf_counter()
    result = run_reference_baseline(run_id=run_id, run_dir=run_dir, task_id=EVAL_ID, task_prompt=spec["task_contract"]["task_prompt"], benchmark_family="packet07_grounded_bundle", case_id=EVAL_ID, seed_id=ROUTE_ID, model_route=route, model_client_kwargs={"timeout_sec": 120, "max_retries": 1}, max_steps=12, timeout_sec=120, cwd=workspace, route_manifest=build_packet04_route_manifest(ROUTE_ID, scope=PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE), enforce_packet04_route_contract=True)
    final_answer = str(result.get("execution", {}).get("last_completion", {}).get("text") or "")
    grade = grade_grounded_bundle_reduce_select_answer(final_answer=final_answer, expected_scalar=expected_scalar)
    return {"run_id": run_id, "eval_id": EVAL_ID, "row_type": "model_run", "model_id": model_id, "route_id": ROUTE_ID, "final_answer": final_answer, "expected_scalar": expected_scalar, "grade": grade, "pass_fail": bool(grade["verdict"] == "pass"), "step_count": int(result.get("execution", {}).get("step_count", 0) or 0), "trace_path": str(run_dir / "run_events.jsonl"), "timing_sec": perf_counter() - started, "token_and_cost_summary": _usage(result)}


def _record_for_ceiling(ceiling: dict[str, Any]) -> dict[str, Any]:
    return {"run_id": f"{MISSION_ID}__{EVAL_ID}__deterministic_ceiling", "eval_id": EVAL_ID, "row_type": "deterministic_ceiling", "model_id": "deterministic_solver", "route_id": "deterministic", "final_answer": str(ceiling["expected_scalar"]), "expected_scalar": str(ceiling["expected_scalar"]), "grade": {"verdict": "pass", "reason_codes": []}, "pass_fail": True, "winner_owner_id": str(ceiling["winner_owner_id"]), "target_state": str(ceiling["target_state"]), "trace_path": None}


def _score_envelope(*, records: list[dict[str, Any]], planned_model_runs: int, execute: bool, expected_scalar: str) -> dict[str, Any]:
    model_rows = [r for r in records if r["row_type"] == "model_run"]
    passes = sum(1 for r in model_rows if r["pass_fail"])
    return {"mission_id": MISSION_ID, "eval_id": EVAL_ID, "execute_mode": "run" if execute else "prepare", "expected_scalar": expected_scalar, "planned_model_runs": planned_model_runs, "executed_model_runs": len(model_rows), "model_pass_count": passes, "model_fail_count": len(model_rows) - passes, "model_pass_rate": (passes / len(model_rows)) if model_rows else None, "ceiling_pass": any(r["row_type"] == "deterministic_ceiling" and r["pass_fail"] for r in records), "score_rows": [{"run_id": r["run_id"], "row_type": r["row_type"], "model_id": r["model_id"], "pass_fail": r["pass_fail"]} for r in records]}


def _summary(records: list[dict[str, Any]], score: dict[str, Any]) -> dict[str, Any]:
    return {"mission_id": MISSION_ID, "eval_id": EVAL_ID, "records": len(records), "ceiling_pass": bool(score["ceiling_pass"]), "model_pass_rate": score["model_pass_rate"], "status": "ready_for_model_runs" if score["executed_model_runs"] == 0 else "scored"}


def _summary_table(summary: dict[str, Any]) -> str:
    return "\n".join(["# Grounded Bundle Reduce-Select Summary", "", "| metric | value |", "|---|---|", f"| eval_id | {summary['eval_id']} |", f"| records | {summary['records']} |", f"| ceiling_pass | {summary['ceiling_pass']} |", f"| model_pass_rate | {summary['model_pass_rate']} |", f"| status | {summary['status']} |"])


def _decision_memo(score: dict[str, Any]) -> str:
    return "\n".join(["# Decision Memo", "", f"- eval_id: `{EVAL_ID}`", "- admission_level: `diagnostic`", f"- expected_scalar: `{score['expected_scalar']}`", f"- executed_model_runs: `{score['executed_model_runs']}`", f"- recommendation: `{'proceed_with_model_board' if score['ceiling_pass'] else 'fix_eval_contract'}`"])


def _handoff(out: Path, summary: dict[str, Any]) -> str:
    return "\n".join(["# Handoff", "", f"- mission_id: `{MISSION_ID}`", f"- eval_id: `{EVAL_ID}`", f"- status: `{summary['status']}`", f"- output_root: `{out}`"])


def _ledger(out: Path, summary: dict[str, Any], score: dict[str, Any]) -> str:
    return "\n".join(["RAW_LEDGER_UPDATE", "- actor: codex", "- task: implement grounded bundle hard-row reduce-select eval", "- event_type: implementation", f"- summary: Added `{EVAL_ID}` proper eval runner with deterministic ceiling and score envelope; status `{summary['status']}`.", f"- observations: ceiling_pass `{score['ceiling_pass']}`; executed_model_runs `{score['executed_model_runs']}`; expected_scalar `{score['expected_scalar']}`.", "- inference: This eval stresses late-stage winner selection under multi-address distractors without context traversal.", f"- evidence_paths: {out / f'{EVAL_ID}_run_spec.json'}; {out / f'{EVAL_ID}_score_envelope.json'}; {out / f'{EVAL_ID}_decision_memo.md'}", "- affected_components: packet07 hard-row answer-robustness proper eval lane", "- decision_change: no promotion decision; eval prepared for scored execution", "- unresolved_questions: Should tie-break policy vary by lane once first model scores are captured.", "- confidence: high", "- commit_message: HOLD - add grounded_bundle_reduce_select_v1 proper eval runner"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--no-comparison", action="store_true")
    args = parser.parse_args(argv)
    print(json.dumps(launch_grounded_bundle_reduce_select_eval(output_dir=args.output_dir, execute=bool(args.execute), include_comparison=not bool(args.no_comparison)), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
