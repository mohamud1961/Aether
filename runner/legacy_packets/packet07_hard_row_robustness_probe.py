"""Run a narrow Packet 07 hard-row robustness probe with fair-runtime constraints."""

from __future__ import annotations

import argparse
import json
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
    LETTA_ROOT,
    _authority,
    _azure_dns_network_preflight,
    _docker_or_fallback_preflight,
    _record_ledger,
    _seed_workspace,
    _usage,
    _write_json,
    _write_jsonl,
    _write_text,
)
from runner.packet07_golden_diagnostic import _build_route_manifest, _orientation_env, _tool_trace_fields
from runner.phase65_measurement_grading import grade_phase65_spec
from runner.schemas import utc_now

MISSION_ID = "packet07_hard_row_robustness_probe"
DEFAULT_OUTPUT_DIR = Path(
    "tracking/collab/stage_03_execution_planning/packets/packet_06_paired_combo_variants/"
    "runs/2026-05-12_packet07_hard_row_robustness_probe"
)
EVAL_ID = "letta_filesystem_008_hard"
ROUTE_ID = "candidate_plus_path_normalized_verifier_repair_projection_01"
MODELS = ("gpt-5.4-mini", "gpt-5.3-codex")
BUDGETS = (15, 25)
REPEATS = 3
PHASE1_ARM = {
    "arm_id": "phase1_safe_backbone_orientation_python3",
    "inject_orientation": True,
    "python_contract": True,
}
PYTHON3_CONTRACT_PROMPT = (
    "\nUse source-grounded shell inspection. Python contract: when Python is needed, use `python3` explicitly."
)
FAILURE_CLASSES = {
    "provider_runtime",
    "evidence_acquisition",
    "wrong_record_selection",
    "join_linking",
    "reduction_error",
    "premature_answer",
    "dispatch_failure",
    "unknown",
}


def launch_packet07_hard_row_robustness_probe(
    *,
    output_dir: str | Path,
    execute: bool = True,
    repeats: int = REPEATS,
) -> dict[str, Any]:
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    metadata = prepare_probe_metadata(repeats=repeats)
    preflight = {
        "mission_id": MISSION_ID,
        "checks": {
            "route_availability": _route_availability_check(),
            "azure_dns_network_preflight": _azure_dns_network_preflight(),
            "docker_or_fallback": _docker_or_fallback_preflight([metadata["spec"]]),
        },
    }
    blockers = _collect_preflight_blockers(preflight)
    preflight["status"] = "pass" if not blockers else "blocked"
    preflight["blockers"] = blockers
    preflight["planned_model_backed_runs"] = len(metadata["plan"])
    _write_json(out / "packet07_hard_row_robustness_probe_run_spec.json", metadata)
    _write_json(out / "packet07_hard_row_robustness_probe_preflight.json", preflight)

    if not execute or preflight["status"] != "pass":
        return _write_bundle(out=out, records=[], preflight=preflight, metadata=metadata, blocked=True)

    records = [_run_one(out=out, spec=metadata["spec"], plan_row=row) for row in metadata["plan"]]
    return _write_bundle(out=out, records=records, preflight=preflight, metadata=metadata, blocked=False)


def prepare_probe_metadata(*, repeats: int = REPEATS) -> dict[str, Any]:
    if repeats <= 0:
        raise ValueError("repeats_must_be_positive")
    spec = _build_hard_spec()
    plan: list[dict[str, Any]] = []
    for model_id in MODELS:
        for budget in BUDGETS:
            for run_index in range(1, repeats + 1):
                plan.append(
                    {
                        "eval_id": EVAL_ID,
                        "model_id": model_id,
                        "route_id": ROUTE_ID,
                        "budget": int(budget),
                        "run_index": run_index,
                    }
                )
    return {
        "mission_id": MISSION_ID,
        "phase": "phase1_only",
        "fair_runtime_only": True,
        "legacy_current_conditions_enabled": False,
        "authority": _authority(),
        "spec": spec,
        "plan": plan,
    }


def _build_hard_spec() -> dict[str, Any]:
    rows = [
        json.loads(line)
        for line in (LETTA_ROOT / "datasets/filesystem_code.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len(rows) <= 8:
        raise ValueError("letta_dataset_missing_row_008")
    row = rows[8]
    difficulty = row.get("agent_args", {}).get("extra", {}).get("difficulty")
    if difficulty != "hard":
        raise ValueError(f"letta_row_008_expected_hard_saw_{difficulty}")
    files = {
        f"/letta/filesystem/{path.name}": path.read_text(encoding="utf-8")
        for path in sorted((LETTA_ROOT / "files").glob("*.txt"))
    }
    return {
        "eval_id": EVAL_ID,
        "benchmark_class": "letta_context_bench",
        "task_id": "filesystem_code_008",
        "task_prompt": row["input"].replace("{pwd}", "/letta/filesystem") + "\nReturn one direct answer.",
        "workspace_seed": "simple_files",
        "workspace_files": files,
        "ground_truth": row["ground_truth"],
        "timeout_sec": 180,
    }


def _route_availability_check() -> dict[str, Any]:
    baseline = build_packet04_route_manifest(BASELINE_VARIANT_ID, scope=PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE)
    try:
        manifest = _build_route_manifest(ROUTE_ID, PHASE1_ARM)
        load_runtime_callables(manifest)
        validate_independent_candidate_routing(candidate_manifest=manifest, baseline_manifest=baseline)
    except Exception as exc:  # pragma: no cover - preflight-only surface
        return {"status": "fail", "blockers": [f"route_unavailable:{ROUTE_ID}"], "rows": [{"status": "fail", "error": str(exc)}]}
    return {"status": "pass", "blockers": [], "rows": [{"status": "pass", "route_id": ROUTE_ID}]}


def _collect_preflight_blockers(preflight: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for check_name, payload in preflight.get("checks", {}).items():
        if payload.get("status") == "pass":
            continue
        for item in payload.get("blockers", ["unspecified"]):
            blockers.append({"check": check_name, "blocker": item})
    return blockers


def _run_one(*, out: Path, spec: dict[str, Any], plan_row: dict[str, Any]) -> dict[str, Any]:
    budget = int(plan_row["budget"])
    run_index = int(plan_row["run_index"])
    model_id = str(plan_row["model_id"])
    run_id = f"{MISSION_ID}__{spec['eval_id']}__{model_id}__b{budget}__r{run_index}"
    run_dir = out / "runs" / run_id
    workspace = run_dir / "workspace"
    _seed_workspace(workspace, spec)
    started = perf_counter()
    result = run_reference_baseline(
        run_id=run_id,
        run_dir=run_dir,
        task_id=str(spec["task_id"]),
        task_prompt=str(spec["task_prompt"]) + PYTHON3_CONTRACT_PROMPT,
        benchmark_family=str(spec["benchmark_class"]),
        case_id=str(spec["eval_id"]),
        seed_id=ROUTE_ID,
        model_route=_model_route(model_id),
        model_client_kwargs={"timeout_sec": int(spec["timeout_sec"]), "max_retries": 1},
        max_steps=budget,
        timeout_sec=int(spec["timeout_sec"]),
        cwd=workspace,
        route_manifest=_build_route_manifest(ROUTE_ID, PHASE1_ARM),
        enforce_packet04_route_contract=True,
        orientation_env_overrides=_orientation_env(workspace, PHASE1_ARM),
    )
    grade = grade_phase65_spec(spec=spec, result=result, workspace=workspace)
    final_answer = str(result.get("execution", {}).get("last_completion", {}).get("text") or "")
    step_count = int(result.get("execution", {}).get("step_count", 0) or 0)
    commands, exit_codes = _tool_trace_fields(result.get("run_events", []))
    trace_path = run_dir / "run_events.jsonl"
    score_row_path = run_dir / "score_envelope.json"
    failure_class = _classify_failure_classes(
        result=result,
        grade=grade,
        final_answer=final_answer,
        step_count=step_count,
        budget=budget,
        commands=commands,
    )
    return _normalize_record(
        raw={
            "run_id": run_id,
            "eval_id": spec["eval_id"],
            "model_id": model_id,
            "route_id": ROUTE_ID,
            "budget": budget,
            "run_index": run_index,
            "final_answer": final_answer,
            "exact_grade": grade,
            "step_count": step_count,
            "tool_commands": commands,
            "exit_codes": exit_codes,
            "trace_path": str(trace_path),
            "score_row_path": str(score_row_path) if score_row_path.exists() else None,
            "failure_class": failure_class,
            "pass_fail": bool(grade.get("verdict") == "pass"),
            "timing_sec": perf_counter() - started,
            "token_and_cost_summary": _usage(result),
        }
    )


def _model_route(model_id: str) -> dict[str, Any]:
    from runner.eval_runner_router import resolve_model_route_for_route

    policy = {key: f"azure:{model_id}" for key in ("screening_default", "screening_fallback", "promotion_tier")}
    return resolve_model_route_for_route(
        {"execution_mode": "sync_interactive", "model_tier_policy": policy},
        model_tier_selector="screening_default",
    )


def _normalize_record(*, raw: dict[str, Any]) -> dict[str, Any]:
    grade = raw.get("exact_grade") if isinstance(raw.get("exact_grade"), dict) else {}
    verdict = str(grade.get("verdict", "fail"))
    failure_class = raw.get("failure_class")
    normalized_classes = [str(item) for item in failure_class] if isinstance(failure_class, list) else ["unknown"]
    clean_classes = sorted({item for item in normalized_classes if item in FAILURE_CLASSES} or {"unknown"})
    return {
        "mission_id": MISSION_ID,
        "timestamp_utc": utc_now(),
        "run_id": str(raw.get("run_id") or ""),
        "eval_id": str(raw.get("eval_id") or ""),
        "model_id": str(raw.get("model_id") or ""),
        "route_id": str(raw.get("route_id") or ""),
        "budget": int(raw.get("budget", 0) or 0),
        "run_index": int(raw.get("run_index", 0) or 0),
        "final_answer": str(raw.get("final_answer") or ""),
        "exact_grade": grade,
        "pass_fail": bool(raw.get("pass_fail", verdict == "pass")),
        "scoreboard_verdict": "pass" if verdict == "pass" else "fail",
        "step_count": int(raw.get("step_count", 0) or 0),
        "tool_commands": list(raw.get("tool_commands") or []),
        "exit_codes": list(raw.get("exit_codes") or []),
        "trace_path": str(raw.get("trace_path") or ""),
        "score_row_path": str(raw["score_row_path"]) if raw.get("score_row_path") else None,
        "failure_class": clean_classes,
        "notes": str(raw.get("notes") or f"phase1_fair_runtime_only;route={ROUTE_ID}"),
        "timing_sec": float(raw.get("timing_sec", 0.0) or 0.0),
        "token_and_cost_summary": raw.get("token_and_cost_summary") if isinstance(raw.get("token_and_cost_summary"), dict) else {},
    }


def _classify_failure_classes(
    *,
    result: dict[str, Any],
    grade: dict[str, Any],
    final_answer: str,
    step_count: int,
    budget: int,
    commands: list[str],
) -> list[str]:
    classes: set[str] = set()
    if grade.get("verdict") == "pass":
        return ["unknown"]
    reason_codes = {str(code) for code in grade.get("reason_codes", []) if isinstance(code, str)}
    command_blob = "\n".join(commands).lower()
    for event in result.get("run_events", []):
        if event.get("event_type") == "model_client_error":
            classes.add("provider_runtime")
            break
    if not result.get("run_events"):
        classes.add("evidence_acquisition")
    if "letta_ground_truth_mismatch" in reason_codes:
        classes.add("wrong_record_selection")
    if any(token in reason_codes for token in ("work_pocket_evidence_paths_mismatch", "contextbench_repo_or_file_family_mismatch")):
        classes.add("join_linking")
    if final_answer.strip() and grade.get("verdict") != "pass":
        classes.add("reduction_error")
    if step_count < budget and final_answer.strip() and not command_blob:
        classes.add("premature_answer")
    if not final_answer.strip():
        classes.add("dispatch_failure")
    return sorted(classes or {"unknown"})


def _write_bundle(
    *,
    out: Path,
    records: list[dict[str, Any]],
    preflight: dict[str, Any],
    metadata: dict[str, Any],
    blocked: bool,
) -> dict[str, Any]:
    result_path = out / "packet07_hard_row_robustness_probe_result_records.jsonl"
    trace_path = out / "packet07_hard_row_robustness_probe_trace_report.json"
    score_path = out / "packet07_hard_row_robustness_probe_score_envelope.json"
    failure_path = out / "packet07_hard_row_robustness_probe_failure_classification_report.json"
    comparison_path = out / "packet07_hard_row_robustness_probe_comparison_memo.md"
    decision_path = out / "packet07_hard_row_robustness_probe_decision_memo.md"
    handoff_path = out / "packet07_hard_row_robustness_probe_handoff.md"
    ledger_path = out / "RAW_LEDGER_UPDATE"

    _write_jsonl(result_path, records)
    score = _score_envelope(records=records, preflight=preflight, metadata=metadata, blocked=blocked)
    failure = _failure_report(records)
    trace = {"mission_id": MISSION_ID, "run_count": len(records), "traces": [_trace_row(row) for row in records]}
    _write_json(score_path, score)
    _write_json(failure_path, failure)
    _write_json(trace_path, trace)
    _write_text(comparison_path, _comparison_memo(score))
    _write_text(decision_path, _decision_memo(score, failure, blocked=blocked))
    _write_text(handoff_path, _handoff(score, failure))
    ledger = _raw_ledger_update(out=out, score=score, failure=failure, blocked=blocked)
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
        "score_envelope_path": str(score_path),
    }


def _trace_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": row["run_id"],
        "eval_id": row["eval_id"],
        "model_id": row["model_id"],
        "budget": row["budget"],
        "run_index": row["run_index"],
        "trace_path": row["trace_path"],
        "scoreboard_verdict": row["scoreboard_verdict"],
        "failure_class": row["failure_class"],
    }


def _score_envelope(
    *,
    records: list[dict[str, Any]],
    preflight: dict[str, Any],
    metadata: dict[str, Any],
    blocked: bool,
) -> dict[str, Any]:
    by_cell: dict[str, dict[str, Any]] = {}
    for row in records:
        key = f"{row['model_id']}|{row['budget']}"
        bucket = by_cell.setdefault(key, {"run_count": 0, "pass": 0, "fail": 0, "mean_step_count": 0.0})
        bucket["run_count"] += 1
        bucket["pass"] += 1 if row["pass_fail"] else 0
        bucket["fail"] += 0 if row["pass_fail"] else 1
        bucket["mean_step_count"] += float(row.get("step_count", 0) or 0)
    for bucket in by_cell.values():
        run_count = int(bucket["run_count"] or 0)
        bucket["pass_rate"] = (bucket["pass"] / run_count) if run_count else 0.0
        bucket["mean_step_count"] = (bucket["mean_step_count"] / run_count) if run_count else 0.0
    selected_cell = max(
        by_cell.items(),
        key=lambda item: (item[1]["pass"], -item[1]["fail"], -item[1]["mean_step_count"], item[0]),
        default=("none", {"pass_rate": 0.0}),
    )[0]
    return {
        "mission_id": MISSION_ID,
        "blocked": blocked,
        "planned_run_count": len(metadata["plan"]),
        "run_count": len(records),
        "pass_count": sum(1 for row in records if row["pass_fail"]),
        "fail_count": sum(1 for row in records if not row["pass_fail"]),
        "by_model_budget_cell": by_cell,
        "selected_cell": selected_cell,
        "preflight": preflight,
        "authority": _authority(),
    }


def _failure_report(records: list[dict[str, Any]]) -> dict[str, Any]:
    failed = [row for row in records if not row["pass_fail"]]
    counts: dict[str, int] = {}
    for row in failed:
        for label in row["failure_class"]:
            counts[label] = counts.get(label, 0) + 1
    return {
        "mission_id": MISSION_ID,
        "failed_run_count": len(failed),
        "failure_class_counts": dict(sorted(counts.items())),
        "rows": [
            {
                "run_id": row["run_id"],
                "model_id": row["model_id"],
                "budget": row["budget"],
                "run_index": row["run_index"],
                "failure_class": row["failure_class"],
                "exact_grade": row["exact_grade"],
            }
            for row in failed
        ],
    }


def _comparison_memo(score: dict[str, Any]) -> str:
    lines = [
        "# Packet 07 Hard-Row Robustness Comparison Memo",
        "",
        f"- mission_id: `{MISSION_ID}`",
        f"- run_count: `{score['run_count']}` / planned `{score['planned_run_count']}`",
        f"- selected_cell: `{score['selected_cell']}`",
        "- by_model_budget_cell:",
    ]
    for key, bucket in sorted(score["by_model_budget_cell"].items()):
        lines.append(
            f"  - `{key}`: pass `{bucket['pass']}` fail `{bucket['fail']}` "
            f"pass_rate `{bucket['pass_rate']:.3f}` mean_step_count `{bucket['mean_step_count']:.2f}`"
        )
    return "\n".join(lines) + "\n"


def _decision_memo(score: dict[str, Any], failure: dict[str, Any], *, blocked: bool) -> str:
    decision = "hold_blocked" if blocked else "iterate_or_promote_after_review"
    return "\n".join(
        [
            "# Packet 07 Hard-Row Robustness Decision Memo",
            "",
            f"- decision: `{decision}`",
            f"- blocked: `{blocked}`",
            f"- selected_cell: `{score['selected_cell']}`",
            f"- failed_run_count: `{failure['failed_run_count']}`",
            f"- failure_class_counts: `{failure['failure_class_counts']}`",
        ]
    ) + "\n"


def _handoff(score: dict[str, Any], failure: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Packet 07 Hard-Row Robustness Handoff",
            "",
            f"- mission_id: `{MISSION_ID}`",
            f"- run_count: `{score['run_count']}`",
            f"- pass_count: `{score['pass_count']}`",
            f"- fail_count: `{score['fail_count']}`",
            f"- selected_cell: `{score['selected_cell']}`",
            f"- failure_class_counts: `{failure['failure_class_counts']}`",
        ]
    ) + "\n"


def _raw_ledger_update(*, out: Path, score: dict[str, Any], failure: dict[str, Any], blocked: bool) -> str:
    return "\n".join(
        [
            "RAW_LEDGER_UPDATE",
            "- actor: codex",
            "- task: Packet 07 hard-row robustness probe (phase1-only fair-runtime)",
            "- event_type: experiment",
            f"- summary: Executed or prepared a 12-run hard-row robustness probe on `{EVAL_ID}` for `{ROUTE_ID}` with selected cell `{score['selected_cell']}`.",
            f"- observations: run_count `{score['run_count']}`; pass_count `{score['pass_count']}`; fail_count `{score['fail_count']}`; blocked `{blocked}`; failure_class_counts `{failure['failure_class_counts']}`.",
            "- inference: This slice isolates model/budget robustness on the hard row under orientation+python3 fair-runtime constraints without current-conditions arms.",
            f"- evidence_paths: {out / 'packet07_hard_row_robustness_probe_result_records.jsonl'}; {out / 'packet07_hard_row_robustness_probe_score_envelope.json'}; {out / 'packet07_hard_row_robustness_probe_trace_report.json'}; {out / 'packet07_hard_row_robustness_probe_failure_classification_report.json'}; {out / 'packet07_hard_row_robustness_probe_comparison_memo.md'}; {out / 'packet07_hard_row_robustness_probe_decision_memo.md'}; {out / 'packet07_hard_row_robustness_probe_handoff.md'}",
            "- affected_components: runner/packet07_hard_row_robustness_probe.py; tests/test_packet07_hard_row_robustness_probe.py; packet07 hard-row robustness probe artifacts",
            "- decision_change: Added a narrow phase1-only hard-row robustness probe runner with fixed model-budget-repeat matrix and normalized records.",
            "- unresolved_questions: Whether failures on this row cluster by provider-runtime substrate versus reduction/dispatch behavior under 15 vs 25 step budgets.",
            "- confidence: medium",
            "- commit_message: HOLD - add Packet 07 hard-row robustness probe runner and focused test",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--no-execute", action="store_true")
    parser.add_argument("--repeats", type=int, default=REPEATS)
    args = parser.parse_args(argv)
    print(
        json.dumps(
            launch_packet07_hard_row_robustness_probe(
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
