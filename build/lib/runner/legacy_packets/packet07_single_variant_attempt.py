"""Run one focused Packet 07 backbone-derived variant attempt."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from pathlib import Path
from time import perf_counter
from typing import Any

from runner import packet07_cycle1_context_targeted_autoresearch as cycle1

MISSION_ID = "packet07_single_variant_attempt"
BACKBONE = "candidate_plus_path_normalized_verifier_repair_projection_01"
ATTEMPT_VARIANT = "candidate_plus_path_normalized_context_closure_projection_01"
ROUTES = (BACKBONE, ATTEMPT_VARIANT)
DEFAULT_OUTPUT_DIR = Path(
    "tracking/collab/stage_03_execution_planning/packets/packet_06_paired_combo_variants/"
    "runs/2026-05-09_packet07_single_variant_attempt"
)
EVAL_IDS = (
    "contextbench_verified_00",
    "contextbench_verified_03",
    "letta_filesystem_001_easy",
    "letta_filesystem_002_medium",
    "custom_long_context_handoff_aggregation_v1",
    "tb_style_verifier_fail_then_repair_v1",
    "bfcl_v3_strict_multi_turn_composite_97",
)


def launch_attempt(*, output_dir: str | Path, execute: bool = True, max_workers: int = 2) -> dict[str, Any]:
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    specs = [spec for spec in cycle1._build_specs_from_locked_rows(cycle1._load_json(cycle1.EVAL_ROWS_PATH)) if spec["eval_id"] in EVAL_IDS]
    preflight = _preflight(specs)
    _write_json(out / "packet07_single_variant_attempt_manifest.json", _manifest(specs, preflight, max_workers))
    if not execute or preflight["status"] != "pass":
        return _write_blocked(out, preflight)
    records, traces = _execute(out, specs, max_workers=max_workers)
    return _write_reports(out, records, traces, preflight)


def _preflight(specs: list[dict[str, Any]]) -> dict[str, Any]:
    preflight = {
        "mission_id": MISSION_ID,
        "checks": {
            "route_availability": _route_availability_check(),
            "grader_availability": cycle1._grader_availability_check(specs),
            "adapter_validity": cycle1._adapter_validity_check(specs),
            "execution_mode_disclosure": cycle1._execution_mode_disclosure(),
            "azure_dns_network_preflight": cycle1._azure_dns_network_preflight(),
            "docker_or_fallback": cycle1._docker_or_fallback_preflight(specs),
        },
    }
    blockers = cycle1._collect_preflight_blockers(preflight)
    preflight["status"] = "pass" if not blockers else "blocked"
    preflight["blockers"] = blockers
    preflight["planned_model_backed_runs"] = len(specs) * len(ROUTES)
    preflight["authority"] = cycle1._authority()
    return preflight


def _route_availability_check() -> dict[str, Any]:
    rows = []
    blockers = []
    baseline = cycle1.build_packet04_route_manifest(cycle1.BASELINE_VARIANT_ID, scope=cycle1.PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE)
    for route_id in ROUTES:
        try:
            manifest = _build_route_manifest(route_id)
            cycle1.load_runtime_callables(manifest)
            cycle1.validate_independent_candidate_routing(candidate_manifest=manifest, baseline_manifest=baseline)
            changed = sorted({row["runtime_key"] for row in manifest["routed_modules"] if row.get("claimed_changed_surface")})
            rows.append({"route_id": route_id, "status": "pass", "changed_runtime_keys": changed})
        except Exception as exc:
            rows.append({"route_id": route_id, "status": "fail", "error": str(exc)})
            blockers.append(f"route_unavailable:{route_id}")
    return {"status": "pass" if not blockers else "fail", "blockers": blockers, "rows": rows}


def _build_route_manifest(route_id: str) -> dict[str, Any]:
    if route_id == BACKBONE:
        return cycle1.build_packet04_route_manifest(route_id, scope=cycle1.PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE)
    manifest = deepcopy(cycle1.build_packet04_route_manifest(BACKBONE, scope=cycle1.PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE))
    for entry in manifest["routed_modules"]:
        entry["variant_id"] = route_id
        if entry["runtime_key"] == "context":
            rel = Path("blocks/context/path_normalized_context_closure_projection.py")
            real = (Path.cwd() / rel).resolve()
            entry["declared_card_path"] = str(rel)
            entry["real_file_path"] = str(real)
            entry["module_import_path"] = "blocks.context.path_normalized_context_closure_projection:manage"
            entry["file_sha256"] = hashlib.sha256(real.read_bytes()).hexdigest()
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


def _execute(out: Path, specs: list[dict[str, Any]], *, max_workers: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    plan = []
    idx = 0
    for spec in specs:
        for route in ROUTES:
            plan.append((idx, spec, route))
            idx += 1
    completed: list[tuple[int, dict[str, Any], dict[str, Any]]] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {
            executor.submit(_run_with_retry, out, spec, route, idx): idx
            for idx, spec, route in plan
        }
        for future in as_completed(future_map):
            completed.append((future_map[future], *future.result()))
    completed.sort(key=lambda row: row[0])
    return [row[1] for row in completed], [row[2] for row in completed]


def _run_with_retry(out: Path, spec: dict[str, Any], route: str, plan_index: int) -> tuple[dict[str, Any], dict[str, Any]]:
    last_record = None
    last_trace = None
    for attempt in range(2):
        record, trace = _run_one(out, spec, route, attempt, plan_index)
        last_record, last_trace = record, trace
        if record["interpretation_class"] != "infrastructure_invalid_result":
            break
    return last_record, last_trace


def _run_one(out: Path, spec: dict[str, Any], route: str, attempt: int, plan_index: int) -> tuple[dict[str, Any], dict[str, Any]]:
    run_started = perf_counter()
    run_id = f"{MISSION_ID}__{spec['eval_id']}__{route}__r{attempt}"
    run_dir = out / "runs" / run_id
    workspace = run_dir / "workspace"
    seed_started = perf_counter()
    cycle1._seed_workspace(workspace, spec)
    seed_sec = perf_counter() - seed_started
    model_exec_started = perf_counter()
    result = cycle1.run_reference_baseline(
        run_id=run_id,
        run_dir=run_dir,
        task_id=spec["task_id"],
        task_prompt=spec["task_prompt"] + "\nUse shell inspection and edits where needed. Do not close early.",
        benchmark_family=spec["benchmark_class"],
        case_id=spec["eval_id"],
        seed_id=route,
        model_route=cycle1.make_azure_gpt53_codex_route_from_env(),
        model_client_kwargs={"timeout_sec": int(spec["timeout_sec"]), "max_retries": 1},
        max_steps=int(spec["max_steps"]),
        timeout_sec=int(spec["timeout_sec"]),
        cwd=workspace,
        route_manifest=_build_route_manifest(route),
        enforce_packet04_route_contract=True,
    )
    model_exec_sec = perf_counter() - model_exec_started
    grade = cycle1._grade_spec(spec, result, workspace)
    infra_invalid = cycle1._is_infrastructure_invalid(run_dir)
    adapter_invalid = cycle1._is_adapter_invalid(run_dir)
    scoreboard_verdict = "invalid" if infra_invalid or adapter_invalid else grade.get("verdict", "fail")
    interpretation_class = cycle1._interpretation_class(spec, grade, infra_invalid=infra_invalid, adapter_invalid=adapter_invalid)
    usage = cycle1._usage(result)
    runtime_timing = result.get("runtime_timing", {}) if isinstance(result.get("runtime_timing"), dict) else {}
    record = {
        "mission_id": MISSION_ID,
        "run_id": run_id,
        "eval_id": spec["eval_id"],
        "lane": spec["lane"],
        "variant_id": route,
        "attempt": attempt,
        "plan_index": plan_index,
        "admission_level": spec.get("admission_level"),
        "scoreboard_verdict": scoreboard_verdict,
        "interpretation_class": interpretation_class,
        "reason_codes": list(grade.get("reason_codes", [])),
        "trace_ref": str(run_dir / "run_events.jsonl"),
        "run_dir": str(run_dir),
        "token_and_cost_summary": usage,
        "timing_summary": {
            "run_wall_sec": perf_counter() - run_started,
            "workspace_seed_sec": seed_sec,
            "model_and_tool_loop_sec": model_exec_sec,
            "model_backed_latency_sec": float(runtime_timing.get("model_backed_latency_sec", 0.0) or 0.0),
            "tool_exec_sec": float(runtime_timing.get("tool_exec_sec", 0.0) or 0.0),
            "verification_sec": float(runtime_timing.get("verification_sec", 0.0) or 0.0),
        },
    }
    trace = {
        "run_id": run_id,
        "eval_id": spec["eval_id"],
        "variant_id": route,
        "scoreboard_verdict": scoreboard_verdict,
        "interpretation_class": interpretation_class,
        "reason_codes": list(grade.get("reason_codes", [])),
        "trace_ref": str(run_dir / "run_events.jsonl"),
    }
    return record, trace


def _write_reports(out: Path, records: list[dict[str, Any]], traces: list[dict[str, Any]], preflight: dict[str, Any]) -> dict[str, Any]:
    _write_jsonl(out / "packet07_single_variant_attempt_result_records.jsonl", records)
    score = _score(records, preflight)
    trace = {"mission_id": MISSION_ID, "run_count": len(traces), "traces": traces}
    recommendation = _recommendation(score)
    deep_trace = _deep_trace(records, score)
    handoff = _handoff(score, recommendation)
    ledger = _ledger(out, score, recommendation)
    _write_json(out / "packet07_single_variant_attempt_score_envelope.json", score)
    _write_json(out / "packet07_single_variant_attempt_trace_report.json", trace)
    _write_text(out / "packet07_single_variant_attempt_recommendation.md", recommendation)
    _write_text(out / "packet07_single_variant_attempt_deep_trace_analysis.md", deep_trace)
    _write_text(out / "packet07_single_variant_attempt_handoff.md", handoff)
    cycle1._record_ledger(ledger)
    _write_text(out / "RAW_LEDGER_UPDATE", ledger)
    return {"output_dir": str(out), "run_count": len(records), "selected_recommendation": score["selected_recommendation"]}


def _score(records: list[dict[str, Any]], preflight: dict[str, Any]) -> dict[str, Any]:
    by_route = defaultdict(lambda: {"pass": 0, "fail": 0})
    by_eval_route = {}
    for row in records:
        by_route[row["variant_id"]][row["scoreboard_verdict"]] += 1
        by_eval_route[(row["eval_id"], row["variant_id"])] = row
    improved_long_handoff = by_eval_route[("custom_long_context_handoff_aggregation_v1", ATTEMPT_VARIANT)]["scoreboard_verdict"] == "pass"
    improved_letta = any(
        by_eval_route[(eval_id, ATTEMPT_VARIANT)]["scoreboard_verdict"] == "pass"
        and by_eval_route[(eval_id, BACKBONE)]["scoreboard_verdict"] != "pass"
        for eval_id in ("letta_filesystem_001_easy", "letta_filesystem_002_medium")
    )
    no_completion_regression = by_eval_route[("tb_style_verifier_fail_then_repair_v1", ATTEMPT_VARIANT)]["scoreboard_verdict"] == "pass"
    no_bfcl_regression = by_eval_route[("bfcl_v3_strict_multi_turn_composite_97", ATTEMPT_VARIANT)]["scoreboard_verdict"] == "pass"
    selected = (
        "attempt_variant_promising"
        if improved_long_handoff and no_completion_regression and no_bfcl_regression
        else "attempt_variant_partial_signal"
        if improved_long_handoff or improved_letta
        else "attempt_variant_not_earned"
    )
    return {
        "mission_id": MISSION_ID,
        "run_count": len(records),
        "by_route": by_route,
        "selected_recommendation": selected,
        "improved_long_handoff": improved_long_handoff,
        "improved_letta": improved_letta,
        "no_completion_regression": no_completion_regression,
        "no_bfcl_regression": no_bfcl_regression,
        "preflight": preflight,
    }


def _recommendation(score: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Packet 07 Single Variant Attempt",
            "",
            f"- selected_recommendation: `{score['selected_recommendation']}`",
            f"- improved_long_handoff: `{score['improved_long_handoff']}`",
            f"- improved_letta: `{score['improved_letta']}`",
            f"- no_completion_regression: `{score['no_completion_regression']}`",
            f"- no_bfcl_regression: `{score['no_bfcl_regression']}`",
        ]
    ) + "\n"


def _deep_trace(records: list[dict[str, Any]], score: dict[str, Any]) -> str:
    by_eval = defaultdict(list)
    for row in records:
        by_eval[row["eval_id"]].append((row["variant_id"], row["scoreboard_verdict"], row["interpretation_class"], row["reason_codes"]))
    lines = ["# Packet 07 Single Variant Attempt Deep Trace", ""]
    for eval_id in EVAL_IDS:
        lines.append(f"## {eval_id}")
        for item in by_eval[eval_id]:
            lines.append(f"- `{item[0]}` => `{item[1]}` / `{item[2]}` / `{item[3]}`")
        lines.append("")
    lines.append(f"- selected_recommendation: `{score['selected_recommendation']}`")
    return "\n".join(lines) + "\n"


def _handoff(score: dict[str, Any], recommendation: str) -> str:
    return "\n".join(
        [
            "# Packet 07 Single Variant Attempt Handoff",
            "",
            f"- mission_id: `{MISSION_ID}`",
            f"- selected_recommendation: `{score['selected_recommendation']}`",
            "",
            "Artifacts:",
            "- packet07_single_variant_attempt_result_records.jsonl",
            "- packet07_single_variant_attempt_score_envelope.json",
            "- packet07_single_variant_attempt_trace_report.json",
            "- packet07_single_variant_attempt_recommendation.md",
            "- packet07_single_variant_attempt_deep_trace_analysis.md",
            "- packet07_single_variant_attempt_handoff.md",
            "- RAW_LEDGER_UPDATE",
        ]
    ) + "\n"


def _ledger(out: Path, score: dict[str, Any], recommendation: str) -> str:
    return "\n".join(
        [
            "RAW_LEDGER_UPDATE",
            "- actor: codex",
            "- task: Packet 07 single new variant attempt",
            "- event_type: experiment",
            f"- summary: Executed one backbone-derived context variant attempt with recommendation `{score['selected_recommendation']}`.",
            f"- observations: run_count `{score['run_count']}`; improved_long_handoff `{score['improved_long_handoff']}`; improved_letta `{score['improved_letta']}`; no_completion_regression `{score['no_completion_regression']}`; no_bfcl_regression `{score['no_bfcl_regression']}`.",
            "- inference: The single attempt tests whether a backbone-preserving context surface can fix /app projection and direct-answer closure without reopening broad family search.",
            f"- evidence_paths: {out / 'packet07_single_variant_attempt_score_envelope.json'}; {out / 'packet07_single_variant_attempt_trace_report.json'}; {out / 'packet07_single_variant_attempt_recommendation.md'}; {out / 'packet07_single_variant_attempt_handoff.md'}",
            "- affected_components: Packet07 context attempt runner; backbone-derived context surface",
            "- decision_change: Admitted one narrow backbone-derived context variant attempt after Cycle 1 closed with no carry-forward context repair.",
            "- unresolved_questions: Whether any future context work should target Letta exact-answer closure separately from long-handoff /app projection.",
            "- confidence: medium",
            "- commit_message: HOLD - run one Packet 07 backbone-derived context variant attempt",
        ]
    )


def _write_blocked(out: Path, preflight: dict[str, Any]) -> dict[str, Any]:
    score = {"mission_id": MISSION_ID, "run_count": 0, "selected_recommendation": "attempt_variant_blocked", "preflight": preflight}
    _write_jsonl(out / "packet07_single_variant_attempt_result_records.jsonl", [])
    _write_json(out / "packet07_single_variant_attempt_score_envelope.json", score)
    _write_text(out / "packet07_single_variant_attempt_recommendation.md", "# Packet 07 Single Variant Attempt\n\n- selected_recommendation: `attempt_variant_blocked`\n")
    _write_text(out / "packet07_single_variant_attempt_deep_trace_analysis.md", "# Packet 07 Single Variant Attempt Deep Trace\n")
    _write_text(out / "packet07_single_variant_attempt_handoff.md", _handoff(score, ""))
    ledger = _ledger(out, {**score, "improved_long_handoff": False, "improved_letta": False, "no_completion_regression": False, "no_bfcl_regression": False}, "")
    cycle1._record_ledger(ledger)
    _write_text(out / "RAW_LEDGER_UPDATE", ledger)
    return {"output_dir": str(out), "run_count": 0, "selected_recommendation": "attempt_variant_blocked", "blocked": True}


def _manifest(specs: list[dict[str, Any]], preflight: dict[str, Any], max_workers: int) -> dict[str, Any]:
    return {
        "mission_id": MISSION_ID,
        "comparison_set": list(ROUTES),
        "eval_ids": [spec["eval_id"] for spec in specs],
        "planned_model_backed_runs": len(specs) * len(ROUTES),
        "max_workers": max_workers,
        "preflight": preflight,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    cycle1._write_json(path, payload)


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    cycle1._write_jsonl(path, rows)


def _write_text(path: Path, text: str) -> None:
    cycle1._write_text(path, text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--no-execute", action="store_true")
    parser.add_argument("--max-workers", type=int, default=2)
    args = parser.parse_args(argv)
    print(
        json.dumps(
            launch_attempt(output_dir=args.output_dir, execute=not args.no_execute, max_workers=args.max_workers),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
