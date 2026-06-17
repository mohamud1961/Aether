"""Packet 07 proper eval: original-surface reduce/select."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from collections import defaultdict
from pathlib import Path
from time import perf_counter
from typing import Any

from runner.agent import run_reference_baseline
from runner.eval_runner_router import resolve_model_route_for_route
from runner.packet04_route_manifest import (
    PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE,
    build_packet04_route_manifest,
)
from runner.packet07_cycle1_context_targeted_autoresearch import (
    _authority,
    _record_ledger,
    _usage,
    _write_json,
    _write_jsonl,
    _write_text,
)
from runner.packet07_hard_row_robustness_probe import _build_hard_spec

MISSION_ID = "packet07_original_surface_reduce_select_eval"
EVAL_ID = "original_surface_reduce_select_v1"
ROUTE_ID = "candidate_plus_path_normalized_verifier_repair_projection_01"
DEFAULT_OUTPUT_DIR = Path(
    "tracking/collab/stage_03_execution_planning/packets/"
    "packet_06_paired_combo_variants/runs/2026-05-13_packet07_hard_row_answer_robustness/"
    "original_surface_reduce_select_v1"
)
DEFAULT_MODEL = "gpt-5.4-mini"
COMPARISON_MODEL = "gpt-5.3-codex"
REDUCE_SELECT_FILES = (
    "pets.txt",
    "addresses.txt",
    "bank_accounts.txt",
    "credit_cards.txt",
    "vehicles.txt",
    "insurance_policies.txt",
)
HEADER_RE = re.compile(r"^###\s+([^\n]+?)\s+\(owner:\s*(pers-\d+)\)\s*$", re.MULTILINE)


def launch_original_surface_reduce_select_eval(
    *, output_dir: str | Path, execute: bool = False, include_comparison: bool = True
) -> dict[str, Any]:
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
        "purpose": spec["purpose"],
        "route_id": ROUTE_ID,
        "models": models,
        "contract": spec["task_contract"],
        "admission_level": spec["admission_level"],
        "ground_truth": {"winner_owner_id": ceiling["winner_owner_id"], "final_scalar": ceiling["expected_scalar"]},
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
    ledger = _ledger(out, score)
    _write_text(out / "RAW_LEDGER_UPDATE", ledger)
    _record_ledger(ledger)
    return {"mission_id": MISSION_ID, "eval_id": EVAL_ID, "status": "executed" if execute else "prepared", "output_dir": str(out), "record_count": len(records), "score_envelope_path": str(out / f"{EVAL_ID}_score_envelope.json")}


def _spec() -> dict[str, Any]:
    hard_spec = _build_hard_spec()
    return {
        "purpose": "Original-surface hard-row reduce/select eval with full source workspace and original prompt.",
        "admission_level": "diagnostic",
        "task_contract": {
            "task_id": EVAL_ID,
            "task_prompt": str(hard_spec["task_prompt"]),
            "non_goals": ["No fixture reduction", "No helper route usage", "No workspace normalization"],
            "deterministic_grading": True,
        },
        "workspace_files": dict(hard_spec["workspace_files"]),
    }


def _parse_blocks(text: str) -> list[dict[str, str]]:
    matches = list(HEADER_RE.finditer(text))
    blocks: list[dict[str, str]] = []
    for idx, match in enumerate(matches):
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        blocks.append({"owner_id": match.group(2).strip(), "block": text[start:end].strip() + "\n"})
    return blocks


def _field_value(block: str, key: str) -> str | None:
    match = re.search(rf"^{re.escape(key)}:\s*(.+)$", block, re.MULTILINE)
    return match.group(1).strip() if match else None


def _seed_workspace(workspace: Path, files: dict[str, str]) -> None:
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    for raw_path, content in files.items():
        path = workspace / raw_path.lstrip("/")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def _deterministic_ceiling(workspace: Path) -> dict[str, Any]:
    blocks = {
        name: _parse_blocks((workspace / "letta" / "filesystem" / name).read_text(encoding="utf-8"))
        for name in REDUCE_SELECT_FILES
    }
    ebony_owner = next((b["owner_id"] for b in blocks["pets.txt"] if _field_value(b["block"], "name") == "Ebony"), "")
    target_state = next((_field_value(b["block"], "state") for b in blocks["addresses.txt"] if b["owner_id"] == ebony_owner and _field_value(b["block"], "state")), "")
    candidates = {b["owner_id"] for b in blocks["addresses.txt"] if _field_value(b["block"], "state") == target_state}
    balances: dict[str, float] = defaultdict(float)
    for block in blocks["bank_accounts.txt"]:
        if block["owner_id"] in candidates:
            balances[block["owner_id"]] += float(_field_value(block["block"], "balance") or 0.0)
    winner_owner_id = sorted(balances.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
    total_count = sum(1 for name in ("bank_accounts.txt", "credit_cards.txt", "vehicles.txt", "insurance_policies.txt") for block in blocks[name] if block["owner_id"] == winner_owner_id)
    return {"expected_scalar": str(total_count), "winner_owner_id": winner_owner_id, "target_state": target_state, "ebony_owner_id": ebony_owner}


def grade_original_surface_reduce_select_answer(*, final_answer: str, expected_scalar: str) -> dict[str, Any]:
    match = re.search(r"-?\d+", final_answer)
    if not match:
        return {"verdict": "fail", "reason_codes": ["no_scalar_found"]}
    observed = str(int(match.group(0)))
    if observed != str(expected_scalar):
        return {"verdict": "fail", "reason_codes": ["scalar_mismatch"], "observed_scalar": observed}
    return {"verdict": "pass", "reason_codes": [], "observed_scalar": observed}


def _run_model(*, out: Path, spec: dict[str, Any], model_id: str, expected_scalar: str) -> dict[str, Any]:
    run_id = f"{MISSION_ID}__{EVAL_ID}__{model_id}"
    run_dir = out / "runs" / run_id
    workspace = run_dir / "workspace"
    _seed_workspace(workspace, spec["workspace_files"])
    route = resolve_model_route_for_route({"execution_mode": "sync_interactive", "model_tier_policy": {k: f"azure:{model_id}" for k in ("screening_default", "screening_fallback", "promotion_tier")}})
    started = perf_counter()
    result = run_reference_baseline(run_id=run_id, run_dir=run_dir, task_id=EVAL_ID, task_prompt=spec["task_contract"]["task_prompt"], benchmark_family="packet07_original_surface", case_id=EVAL_ID, seed_id=ROUTE_ID, model_route=route, model_client_kwargs={"timeout_sec": 120, "max_retries": 1}, max_steps=15, timeout_sec=120, cwd=workspace, route_manifest=build_packet04_route_manifest(ROUTE_ID, scope=PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE), enforce_packet04_route_contract=True)
    final_answer = str(result.get("execution", {}).get("last_completion", {}).get("text") or "")
    grade = grade_original_surface_reduce_select_answer(final_answer=final_answer, expected_scalar=expected_scalar)
    return {"run_id": run_id, "eval_id": EVAL_ID, "row_type": "model_run", "model_id": model_id, "route_id": ROUTE_ID, "final_answer": final_answer, "expected_scalar": expected_scalar, "grade": grade, "pass_fail": bool(grade["verdict"] == "pass"), "step_count": int(result.get("execution", {}).get("step_count", 0) or 0), "trace_path": str(run_dir / "run_events.jsonl"), "timing_sec": perf_counter() - started, "token_and_cost_summary": _usage(result)}


def _record_for_ceiling(ceiling: dict[str, Any]) -> dict[str, Any]:
    return {"run_id": f"{MISSION_ID}__{EVAL_ID}__deterministic_ceiling", "eval_id": EVAL_ID, "row_type": "deterministic_ceiling", "model_id": "deterministic_solver", "route_id": "deterministic", "final_answer": str(ceiling["expected_scalar"]), "expected_scalar": str(ceiling["expected_scalar"]), "grade": {"verdict": "pass", "reason_codes": []}, "pass_fail": True, "winner_owner_id": str(ceiling["winner_owner_id"]), "target_state": str(ceiling["target_state"]), "ebony_owner_id": str(ceiling["ebony_owner_id"]), "trace_path": None}


def _score_envelope(*, records: list[dict[str, Any]], planned_model_runs: int, execute: bool, expected_scalar: str) -> dict[str, Any]:
    model_rows = [row for row in records if row["row_type"] == "model_run"]
    pass_count = sum(1 for row in model_rows if row["pass_fail"])
    return {"mission_id": MISSION_ID, "eval_id": EVAL_ID, "execute_mode": "run" if execute else "prepare", "expected_scalar": expected_scalar, "planned_model_runs": planned_model_runs, "executed_model_runs": len(model_rows), "model_pass_count": pass_count, "model_fail_count": len(model_rows) - pass_count, "model_pass_rate": (pass_count / len(model_rows)) if model_rows else None, "ceiling_pass": any(row["row_type"] == "deterministic_ceiling" and row["pass_fail"] for row in records), "score_rows": [{"run_id": row["run_id"], "row_type": row["row_type"], "model_id": row["model_id"], "pass_fail": row["pass_fail"]} for row in records]}


def _summary(records: list[dict[str, Any]], score: dict[str, Any]) -> dict[str, Any]:
    return {"mission_id": MISSION_ID, "eval_id": EVAL_ID, "records": len(records), "ceiling_pass": bool(score["ceiling_pass"]), "model_pass_rate": score["model_pass_rate"], "status": "ready_for_model_runs" if score["executed_model_runs"] == 0 else "scored"}


def _summary_table(summary: dict[str, Any]) -> str:
    return "\n".join(["# Original Surface Reduce-Select Summary", "", "| metric | value |", "|---|---|", f"| eval_id | {summary['eval_id']} |", f"| records | {summary['records']} |", f"| ceiling_pass | {summary['ceiling_pass']} |", f"| model_pass_rate | {summary['model_pass_rate']} |", f"| status | {summary['status']} |"])


def _decision_memo(score: dict[str, Any]) -> str:
    return "\n".join(["# Decision Memo", "", f"- eval_id: `{EVAL_ID}`", "- admission_level: `diagnostic`", f"- expected_scalar: `{score['expected_scalar']}`", f"- executed_model_runs: `{score['executed_model_runs']}`", f"- recommendation: `{'proceed_with_model_board' if score['ceiling_pass'] else 'fix_eval_contract'}`"])


def _handoff(out: Path, summary: dict[str, Any]) -> str:
    return "\n".join(["# Handoff", "", f"- mission_id: `{MISSION_ID}`", f"- eval_id: `{EVAL_ID}`", f"- status: `{summary['status']}`", f"- output_root: `{out}`"])


def _ledger(out: Path, score: dict[str, Any]) -> str:
    return "\n".join(["RAW_LEDGER_UPDATE", "- actor: codex", "- task: implement original-surface proper eval for packet07 hard-row answer robustness lane", "- event_type: implementation", f"- summary: Added `{EVAL_ID}` with full hard-row workspace surface and original prompt contract.", f"- observations: ceiling_pass `{score['ceiling_pass']}`; executed_model_runs `{score['executed_model_runs']}`; expected_scalar `{score['expected_scalar']}`.", "- inference: A faithful original-surface reduce/select eval is available with deterministic ceiling+grader and no helper-specific grading logic.", f"- evidence_paths: {out / f'{EVAL_ID}_run_spec.json'}; {out / f'{EVAL_ID}_score_envelope.json'}; {out / f'{EVAL_ID}_decision_memo.md'}", "- affected_components: packet07 hard-row answer robustness original-surface proper-eval lane", "- decision_change: no promotion decision; eval prepared for baseline+comparison scoring", "- unresolved_questions: Whether original-surface context pressure widens baseline gap relative to semistructured rows.", "- confidence: high", "- commit_message: HOLD - add original_surface_reduce_select_v1 proper eval runner"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--no-comparison", action="store_true")
    args = parser.parse_args(argv)
    print(json.dumps(launch_original_surface_reduce_select_eval(output_dir=args.output_dir, execute=bool(args.execute), include_comparison=not bool(args.no_comparison)), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
