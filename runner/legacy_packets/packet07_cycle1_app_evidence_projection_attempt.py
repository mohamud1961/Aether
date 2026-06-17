"""Run the backbone-only /app evidence projection Packet 07 attempt."""

from __future__ import annotations

import argparse
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from pathlib import Path
from time import perf_counter
from typing import Any

from runner.agent import run_reference_baseline
from runner.model_client import make_azure_gpt53_codex_route_from_env
from runner.packet04_route_manifest import (
    BASELINE_VARIANT_ID,
    PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE,
    build_packet04_route_manifest,
    load_runtime_callables,
    validate_independent_candidate_routing,
)
from runner.packet07_cycle1_context_targeted_autoresearch import (
    BACKBONE_INCUMBENT,
    CUSTOM_LONG_HANDOFF_EVAL_ID,
    LONG_ROW_EVAL_ID,
    PRICE,
    _authority,
    _azure_dns_network_preflight,
    _bfcl_specs,
    _completion_specs,
    _context_specs,
    _counts,
    _docker_or_fallback_preflight,
    _grade_spec,
    _interpretation_class,
    _is_adapter_invalid,
    _is_infrastructure_invalid,
    _long_horizon_spec,
    _record_ledger,
    _seed_workspace,
    _usage,
    _write_json,
    _write_jsonl,
    _write_text,
)

MISSION_ID = "packet07_cycle1_app_evidence_projection_attempt"
ATTEMPT_VARIANT = "candidate_plus_path_normalized_app_evidence_projection_01"
DEFAULT_OUTPUT_DIR = Path(
    "tracking/collab/stage_03_execution_planning/packets/packet_06_paired_combo_variants/"
    "runs/2026-05-09_packet07_cycle1_app_evidence_projection_attempt"
)
ROUTES = (BACKBONE_INCUMBENT, ATTEMPT_VARIANT)
ROUTE_ROLES = {
    BACKBONE_INCUMBENT: "backbone_incumbent",
    ATTEMPT_VARIANT: "backbone_app_evidence_projection_attempt",
}
LOCAL_ROUTE_OVERRIDES = {
    ATTEMPT_VARIANT: {
        "base_variant": BACKBONE_INCUMBENT,
        "modules": {
            "tools_getter": {
                "file_rel": "blocks/tools/app_evidence_projection_normalizer.py",
                "module_import_path": "blocks.tools.app_evidence_projection_normalizer:get_tools",
            },
            "tool_executor": {
                "file_rel": "blocks/tools/app_evidence_projection_normalizer.py",
                "module_import_path": "blocks.tools.app_evidence_projection_normalizer:execute_tool_call",
            },
        },
    }
}
FOCUSED_EVAL_IDS = (
    "contextbench_verified_03",
    "letta_filesystem_001_easy",
    "letta_filesystem_002_medium",
    CUSTOM_LONG_HANDOFF_EVAL_ID,
    LONG_ROW_EVAL_ID,
    "tb_style_verifier_fail_then_repair_v1",
    "bfcl_v3_strict_multi_turn_composite_97",
)


def launch_attempt(*, output_dir: str | Path, execute: bool = True, max_workers: int = 2) -> dict[str, Any]:
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    specs = _build_specs()
    board_manifest = {"mission_id": MISSION_ID, "comparison_set": list(ROUTES), "required_eval_ids": list(FOCUSED_EVAL_IDS)}
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
    _write_json(out / "packet07_cycle1_app_evidence_projection_board_manifest.json", board_manifest)
    if not execute or preflight["status"] != "pass":
        return _write_artifacts(out, [], [], preflight, board_manifest, blocked=True)
    records, traces = _execute_board(out, specs, max_workers=max_workers)
    return _write_artifacts(out, records, traces, preflight, board_manifest, blocked=False)


def _build_specs() -> list[dict[str, Any]]:
    library = {row["eval_id"]: row for row in [*_completion_specs(), *_context_specs(), *_bfcl_specs(), _long_horizon_spec()]}
    specs: list[dict[str, Any]] = []
    for eval_id in FOCUSED_EVAL_IDS:
        spec = dict(library[eval_id])
        if eval_id == LONG_ROW_EVAL_ID:
            lane = "long_running_internal_tb_style"
            admission = "diagnostic"
        elif eval_id == "tb_style_verifier_fail_then_repair_v1":
            lane = "completion_closure"
            admission = "certified"
        elif eval_id.startswith("bfcl_v3_"):
            lane = "tooling_bfcl"
            admission = "certified"
        else:
            lane = "context_handoff_answer_extraction"
            admission = "certified"
        spec["lane"] = lane
        spec["admission_level"] = admission
        spec["variant_ids"] = list(ROUTES)
        specs.append(spec)
    return specs


def _route_availability_check() -> dict[str, Any]:
    rows = []
    blockers = []
    baseline = build_packet04_route_manifest(BASELINE_VARIANT_ID, scope=PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE)
    for route_id in ROUTES:
        try:
            manifest = _build_route_manifest(route_id)
            load_runtime_callables(manifest)
            validate_independent_candidate_routing(candidate_manifest=manifest, baseline_manifest=baseline)
            rows.append({"route_id": route_id, "status": "pass", "route_manifest_fingerprint": manifest["route_manifest_fingerprint"]})
        except Exception as exc:
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
    manifest["route_manifest_fingerprint"] = hashlib.sha256(json.dumps(manifest["routed_modules"], sort_keys=True, default=str).encode("utf-8")).hexdigest()
    return manifest


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


def _execute_board(out: Path, specs: list[dict[str, Any]], *, max_workers: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    plan = [(index, spec, route) for index, (spec, route) in enumerate((spec, route) for spec in specs for route in ROUTES)]
    completed: list[tuple[int, dict[str, Any], dict[str, Any]]] = []
    with ThreadPoolExecutor(max_workers=max(1, min(max_workers, 2))) as executor:
        future_map = {executor.submit(_run_one, out, spec, route, index): index for index, spec, route in plan}
        for future in as_completed(future_map):
            completed.append((future_map[future], *future.result()))
    completed.sort(key=lambda row: row[0])
    return [row[1] for row in completed], [row[2] for row in completed]


def _run_one(out: Path, spec: dict[str, Any], variant: str, plan_index: int) -> tuple[dict[str, Any], dict[str, Any]]:
    run_id = f"{MISSION_ID}__{spec['eval_id']}__{variant}__r0"
    run_dir = out / "runs" / run_id
    workspace = run_dir / "workspace"
    run_started = perf_counter()
    _seed_workspace(workspace, spec)
    result = run_reference_baseline(
        run_id=run_id,
        run_dir=run_dir,
        task_id=spec["task_id"],
        task_prompt=spec["task_prompt"] + "\nUse shell inspection and edits where needed. Do not close early.",
        benchmark_family=spec["benchmark_class"],
        case_id=spec["eval_id"],
        seed_id=variant,
        model_route=make_azure_gpt53_codex_route_from_env(),
        model_client_kwargs={"timeout_sec": int(spec["timeout_sec"]), "max_retries": 1},
        max_steps=int(spec["max_steps"]),
        timeout_sec=int(spec["timeout_sec"]),
        cwd=workspace,
        route_manifest=_build_route_manifest(variant),
        enforce_packet04_route_contract=True,
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
    record = {
        "mission_id": MISSION_ID,
        "run_id": run_id,
        "eval_id": spec["eval_id"],
        "lane": spec["lane"],
        "benchmark_class": spec["benchmark_class"],
        "task_id": spec["task_id"],
        "variant_id": variant,
        "route_role": ROUTE_ROLES[variant],
        "attempt": 0,
        "plan_index": plan_index,
        "admission_level": spec["admission_level"],
        "diagnostic_only": bool(spec["eval_id"] == LONG_ROW_EVAL_ID),
        "model_backed": True,
        "run_dir": str(run_dir),
        "trace_ref": str(run_dir / "run_events.jsonl"),
        "score_summary": {"final_verdict": verdict, "grade": grade},
        "scoreboard_verdict": verdict,
        "interpretation_class": _interpretation_class(spec, grade, infra_invalid=infra_invalid, adapter_invalid=adapter_invalid),
        "reason_codes": reason_codes,
        "token_and_cost_summary": _usage(result),
        "authority": _authority(),
        "timing_summary": {"run_wall_sec": perf_counter() - run_started},
    }
    trace = {
        "run_id": run_id,
        "eval_id": spec["eval_id"],
        "variant_id": variant,
        "route_role": ROUTE_ROLES[variant],
        "trace_ref": str(run_dir / "run_events.jsonl"),
        "scoreboard_verdict": verdict,
        "interpretation_class": record["interpretation_class"],
        "reason_codes": reason_codes,
    }
    return record, trace


def _write_artifacts(
    out: Path,
    records: list[dict[str, Any]],
    traces: list[dict[str, Any]],
    preflight: dict[str, Any],
    board_manifest: dict[str, Any],
    *,
    blocked: bool,
) -> dict[str, Any]:
    _write_jsonl(out / "packet07_cycle1_app_evidence_projection_result_records.jsonl", records)
    score = _score_envelope(records, preflight, board_manifest, blocked=blocked)
    variant_delta = _variant_delta(records)
    trace_report = {"mission_id": MISSION_ID, "run_count": len(traces), "traces": traces, "preflight_blockers": preflight.get("blockers", [])}
    cost_report = _cost_report(records)
    recommendation = _recommendation(score, variant_delta)
    deep_trace = _deep_trace(score, variant_delta, records)
    handoff = _handoff(score, variant_delta)
    ledger = _raw_ledger_update(out, score, variant_delta)
    _write_json(out / "packet07_cycle1_app_evidence_projection_score_envelope.json", score)
    _write_json(out / "packet07_cycle1_app_evidence_projection_trace_report.json", trace_report)
    _write_json(out / "packet07_cycle1_app_evidence_projection_variant_delta_report.json", variant_delta)
    _write_json(out / "packet07_cycle1_app_evidence_projection_cost_report.json", cost_report)
    _write_text(out / "packet07_cycle1_app_evidence_projection_recommendation.md", recommendation)
    _write_text(out / "packet07_cycle1_app_evidence_projection_deep_trace_analysis.md", deep_trace)
    _write_text(out / "packet07_cycle1_app_evidence_projection_handoff.md", handoff)
    _write_text(out / "RAW_LEDGER_UPDATE", ledger)
    _record_ledger(ledger)
    return {"output_dir": str(out), "run_count": len(records), "model_backed_runs": score["model_backed_runs"], "selected_recommendation": score["selected_recommendation"], "blocked": blocked}


def _score_envelope(records: list[dict[str, Any]], preflight: dict[str, Any], board_manifest: dict[str, Any], *, blocked: bool) -> dict[str, Any]:
    admitted = [row for row in records if row["interpretation_class"] not in {"infrastructure_invalid_result", "adapter_invalid_result", "substrate_unavailable_result"}]
    certified = [row for row in admitted if row["admission_level"] == "certified"]
    return {
        "mission_id": MISSION_ID,
        "run_count": len(records),
        "model_backed_runs": sum(1 for row in records if row.get("model_backed")),
        "behaviorally_admissible_run_count": len(admitted),
        "selected_recommendation": "context_measurement_or_eval_blocked" if blocked else _selected_recommendation(certified),
        "route_summary_certified_only": {route: _route_eval_summary(certified, route) for route in ROUTES},
        "preflight": preflight,
        "board_manifest": board_manifest,
    }


def _variant_delta(records: list[dict[str, Any]]) -> dict[str, Any]:
    certified = [row for row in records if row["admission_level"] == "certified"]
    backbone = _route_eval_summary(certified, BACKBONE_INCUMBENT)
    attempt = _route_eval_summary(certified, ATTEMPT_VARIANT)
    return {
        "mission_id": MISSION_ID,
        "backbone": backbone,
        "attempt": attempt,
        "attempt_status": "earned_carry_forward"
        if attempt["context_pass"] > backbone["context_pass"] and attempt["completion_regression_fail"] == 0 and attempt["bfcl_regression_fail"] == 0
        else "partial_signal"
        if attempt["context_pass"] >= backbone["context_pass"] or attempt["custom_long_handoff_pass"] > backbone["custom_long_handoff_pass"]
        else "not_earned",
    }


def _route_eval_summary(records: list[dict[str, Any]], route_id: str) -> dict[str, int]:
    scoped = [row for row in records if row["variant_id"] == route_id]
    return {
        "certified_pass": sum(1 for row in scoped if row["scoreboard_verdict"] == "pass"),
        "certified_fail": sum(1 for row in scoped if row["scoreboard_verdict"] != "pass"),
        "context_pass": sum(1 for row in scoped if row["lane"] == "context_handoff_answer_extraction" and row["scoreboard_verdict"] == "pass"),
        "completion_regression_fail": sum(1 for row in scoped if row["eval_id"] == "tb_style_verifier_fail_then_repair_v1" and row["scoreboard_verdict"] != "pass"),
        "bfcl_regression_fail": sum(1 for row in scoped if row["eval_id"] == "bfcl_v3_strict_multi_turn_composite_97" and row["scoreboard_verdict"] != "pass"),
        "custom_long_handoff_pass": sum(1 for row in scoped if row["eval_id"] == CUSTOM_LONG_HANDOFF_EVAL_ID and row["scoreboard_verdict"] == "pass"),
    }


def _selected_recommendation(certified: list[dict[str, Any]]) -> str:
    if not certified:
        return "context_measurement_or_eval_blocked"
    backbone = _route_eval_summary(certified, BACKBONE_INCUMBENT)
    attempt = _route_eval_summary(certified, ATTEMPT_VARIANT)
    if attempt["context_pass"] > backbone["context_pass"] and attempt["completion_regression_fail"] == 0 and attempt["bfcl_regression_fail"] == 0:
        return "context_repair_viable_continue_packet07"
    if attempt["context_pass"] >= backbone["context_pass"] or attempt["custom_long_handoff_pass"] > backbone["custom_long_handoff_pass"]:
        return "context_repair_partial_continue_one_more_context_cycle"
    return "context_no_signal_shift_target"


def _cost_report(records: list[dict[str, Any]]) -> dict[str, Any]:
    tokens = sum(int(row.get("token_and_cost_summary", {}).get("total_tokens", 0) or 0) for row in records)
    usd = sum(float(row.get("token_and_cost_summary", {}).get("usd_estimate", 0.0) or 0.0) for row in records)
    return {"mission_id": MISSION_ID, "run_count": len(records), "total_tokens": tokens, "total_usd_estimate": usd, "price_table": PRICE}


def _recommendation(score: dict[str, Any], variant_delta: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Packet 07 Cycle 1 App Evidence Projection Attempt",
            "",
            f"- recommendation: `{score['selected_recommendation']}`",
            f"- attempt_status: `{variant_delta['attempt_status']}`",
            "",
            "## Golden Nuggets",
            "",
            "- This attempt preserves the backbone doctrine and changes only the tool surface that rewrites artifact evidence paths.",
            "- The board is focused on the real context failures plus the locked completion and BFCL anchors.",
        ]
    ) + "\n"


def _deep_trace(score: dict[str, Any], variant_delta: dict[str, Any], records: list[dict[str, Any]]) -> str:
    failures = [row for row in records if row["scoreboard_verdict"] != "pass"]
    return "\n".join(
        [
            "# Packet 07 Cycle 1 App Evidence Projection Deep Trace",
            "",
            f"- selected_recommendation: `{score['selected_recommendation']}`",
            f"- backbone_summary: `{variant_delta['backbone']}`",
            f"- attempt_summary: `{variant_delta['attempt']}`",
            f"- failure_counts_by_interpretation_class: `{_counts(row['interpretation_class'] for row in failures)}`",
            "",
            "## Golden Nuggets",
            "",
            f"- context_rows_failed: `{[row['run_id'] for row in failures if row['lane'] == 'context_handoff_answer_extraction']}`",
            f"- regression_rows_failed: `{[row['run_id'] for row in failures if row['lane'] in {'completion_closure', 'tooling_bfcl'}]}`",
        ]
    ) + "\n"


def _handoff(score: dict[str, Any], variant_delta: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Packet 07 Cycle 1 App Evidence Projection Handoff",
            "",
            f"- mission_id: `{MISSION_ID}`",
            f"- selected_recommendation: `{score['selected_recommendation']}`",
            f"- attempt_status: `{variant_delta['attempt_status']}`",
        ]
    ) + "\n"


def _raw_ledger_update(out: Path, score: dict[str, Any], variant_delta: dict[str, Any]) -> str:
    return "\n".join(
        [
            "RAW_LEDGER_UPDATE",
            "- actor: codex",
            "- task: Packet 07 Cycle 1 app evidence projection attempt",
            "- event_type: experiment",
            f"- summary: Ran the backbone-only /app evidence projection attempt with recommendation `{score['selected_recommendation']}`.",
            f"- observations: run_count `{score['run_count']}`; attempt_status `{variant_delta['attempt_status']}`; backbone `{variant_delta['backbone']}`; attempt `{variant_delta['attempt']}`.",
            "- inference: A narrow tool-surface patch can test whether exact /app evidence-path projection fixes the long-handoff blocker without changing the backbone doctrine.",
            f"- evidence_paths: {out / 'packet07_cycle1_app_evidence_projection_result_records.jsonl'}; {out / 'packet07_cycle1_app_evidence_projection_score_envelope.json'}; {out / 'packet07_cycle1_app_evidence_projection_variant_delta_report.json'}; {out / 'packet07_cycle1_app_evidence_projection_deep_trace_analysis.md'}",
            "- affected_components: blocks/tools/app_evidence_projection_normalizer.py; runner/packet07_cycle1_app_evidence_projection_attempt.py; tests/test_packet07_cycle1_app_evidence_projection_attempt.py",
            "- decision_change: Tried the backbone-only /app evidence projection variant on the focused Packet 07 context board.",
            "- unresolved_questions: Whether exact artifact evidence-path projection alone is enough, or whether direct-answer closure still has to be imported separately.",
            "- confidence: medium",
            "- commit_message: HOLD - run Packet 07 app evidence projection attempt",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--no-execute", action="store_true")
    parser.add_argument("--max-workers", type=int, default=2)
    args = parser.parse_args(argv)
    print(json.dumps(launch_attempt(output_dir=args.output_dir, execute=not args.no_execute, max_workers=args.max_workers), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
