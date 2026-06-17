"""Execute the bounded successor Phase 6 context+completion repair gauntlet."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from runner.eval_batch_runner import run_batch
from runner.letta_context_bench import letta_preflight, selected_letta_filesystem_specs
from runner.packet04_route_manifest import (
    BASELINE_VARIANT_ID,
    PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE,
    build_packet04_route_manifest,
    load_runtime_callables,
    validate_independent_candidate_routing,
)
from runner.schemas import utc_now

DEFAULT_OUTPUT_DIR = Path(
    "tracking/collab/stage_03_execution_planning/packets/packet_06_paired_combo_variants/"
    "runs/2026-05-06_successor_phase6_context_completion_repair_gauntlet"
)
DEFAULT_EVAL_CARDS_PATH = Path(
    "tracking/collab/stage_03_execution_planning/packets/"
    "packet_03_atomic_eval_families/outputs/eval_cards.active.jsonl"
)
MISSION_ID = "successor_phase6_context_completion_repair_gauntlet"
CONTROL = "spb_01"
INCUMBENT = "spb_tooling_seed_plus_receipt_and_completion_01"
CONTEXT_VARIANTS = (
    "candidate_plus_model_led_compaction_01",
    "candidate_plus_codex_style_handoff_compaction_01",
    "candidate_plus_hybrid_receipt_handoff_01",
    "candidate_plus_context_answer_extraction_01",
    "candidate_plus_context_budget_guard_01",
)
COMPLETION_VARIANTS = (
    "candidate_plus_artifact_existence_gate_01",
    "candidate_plus_verifier_backed_completion_gate_01",
    "candidate_plus_completion_repair_loop_01",
    "candidate_plus_required_deliverable_tracker_01",
)
BFCL_VARIANTS = (
    "candidate_plus_tool_call_plan_tracker_01",
    "candidate_plus_final_required_action_tracker_01",
    "candidate_plus_bfcl_strict_argument_guard_01",
)
REQUIRED_VARIANTS = (CONTROL, INCUMBENT, *CONTEXT_VARIANTS, *COMPLETION_VARIANTS, *BFCL_VARIANTS)
DOCTRINE_VARIANTS = (*CONTEXT_VARIANTS, *COMPLETION_VARIANTS, *BFCL_VARIANTS)
RECOMMENDATIONS = (
    "candidate_repaired_and_ready_for_packet07_readiness_review",
    "candidate_needs_one_more_completion_repair",
    "candidate_needs_context_repair",
    "candidate_needs_toolcall_repair",
    "benchmark_adapter_still_invalid",
    "internal_eval_suite_needs_harder_tasks",
    "prefer_spb_01_or_pause_successor",
)
TERMINALBENCH_ROOT = Path("/Users/mohamud/Downloads/terminalbench")
CONTEXTBENCH_ROOT = Path("/Users/mohamud/Downloads/harnesseng/research/sources/codebases/ContextBench")
CONTEXTBENCH_PYTHON = Path("/Users/mohamud/Downloads/harnesseng/.venv/bin/python")
BFCL_PATH = Path(
    "research/sources/codebases/deepagents/libs/evals/tests/evals/data/benchmark_samples/bfcl_v3_final.json"
)
TRACK_EVALS = {
    "context": ["ae_internal_discovery_evidence_efficiency_v1", "ae_internal_multifile_repair_test_verify_v1"],
    "completion": ["ae_completion_verifier_final_contradiction_probe", "ae_internal_artifact_log_extraction_v1"],
    "bfcl": ["ae_tool_call_contract_quality_v2", "ae_tool_result_attribution_quality_v2"],
    "terminalbench": ["ae_internal_toolchain_dependency_pressure_v1"],
}
REQUIRED_EVALS = tuple(eval_id for ids in TRACK_EVALS.values() for eval_id in ids)
ACCEPTED_PHASE6_REQUIRED_LANES = {
    "completion": [
        "extract-moves-from-video",
        "internal_partial_progress_false_completion_v1",
        "internal_verifier_fail_repair_rerun_v1",
    ],
    "context": [
        "coding_contextbench_verified_richer_4_8_rows",
        "letta_context_bench_filesystem_6_rows",
        "internal_long_context_handoff_aggregation_v1",
    ],
    "bfcl": ["bfcl_v3_strict_5_10_cases_including_multi_turn_composite_97"],
    "regression": ["fix-git", "regex-log", "financial-document-processor"],
}
EXECUTION_MODES = {
    "ae_internal_discovery_evidence_efficiency_v1": "multistep_batchable",
    "ae_internal_multifile_repair_test_verify_v1": "multistep_batchable",
    "ae_completion_verifier_final_contradiction_probe": "offline_judge_batchable",
    "ae_internal_artifact_log_extraction_v1": "multistep_batchable",
    "ae_tool_call_contract_quality_v2": "deterministic_no_model",
    "ae_tool_result_attribution_quality_v2": "deterministic_no_model",
    "ae_internal_toolchain_dependency_pressure_v1": "multistep_batchable",
}
LANES = {
    "ae_completion_verifier_final_contradiction_probe": "bounded_diagnostic",
}


def launch_phase6(
    *,
    output_dir: str | Path,
    eval_cards_path: str | Path = DEFAULT_EVAL_CARDS_PATH,
    rerun_count: int = 2,
    execute: bool = True,
) -> dict[str, Any]:
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    eval_cards = _load_eval_cards(Path(eval_cards_path))
    preflight = _preflight(eval_cards)
    route_matrix = _route_matrix(list(REQUIRED_VARIANTS))
    doctrine_matrix = _doctrine_matrix(route_matrix)
    execution_plan = _execution_plan(out, list(REQUIRED_VARIANTS), rerun_count)
    _write_text(out / "phase6_plan.md", _plan(out, rerun_count, preflight, route_matrix, doctrine_matrix))
    _write_json(out / "phase6_board_manifest.json", _board_manifest(rerun_count))
    _write_json(out / "phase6_route_matrix.json", route_matrix)
    _write_json(out / "phase6_variant_doctrine_matrix.json", doctrine_matrix)
    _write_text(out / "phase6_eval_design_report.md", _eval_design_report())
    _write_text(out / "phase6_internal_tb_style_eval_spec.md", _internal_eval_spec())
    _write_json(out / "phase6_execution_plan.json", execution_plan)
    if (
        not execute
        or preflight["status"] != "pass"
        or route_matrix["status"] != "pass"
        or doctrine_matrix["status"] != "pass"
    ):
        return _write_blocked(
            out,
            preflight=preflight,
            route_matrix=route_matrix,
            doctrine_matrix=doctrine_matrix,
            execute=execute,
        )

    records: list[dict[str, Any]] = []
    traces: list[dict[str, Any]] = []
    for spec in execution_plan["batch_specs"]:
        batch_dir = out / spec["batch_id"]
        existing_records = batch_dir / "result_records.jsonl"
        existing_traces = batch_dir / "trace_summaries.jsonl"
        if existing_records.exists() and existing_traces.exists():
            batch = {
                "result_records_path": str(existing_records),
                "trace_summaries_path": str(existing_traces),
            }
        else:
            batch = run_batch(
                batch_spec=spec,
                eval_cards={eval_id: eval_cards[eval_id] for eval_id in spec["eval_ids"]},
            )
        records.extend(_read_jsonl(Path(batch["result_records_path"])))
        traces.extend(_read_jsonl(Path(batch["trace_summaries_path"])))

    _write_jsonl(out / "phase6_result_records.jsonl", records)
    score = _score(records)
    context = _track_report("context", records, TRACK_EVALS["context"])
    completion = _track_report("completion", records, TRACK_EVALS["completion"])
    bfcl = _track_report("bfcl", records, TRACK_EVALS["bfcl"])
    terminalbench = _track_report("terminalbench", records, TRACK_EVALS["terminalbench"])
    trace = {"mission_id": MISSION_ID, "run_count": len(traces), "traces": traces}
    cost = _cost(records)
    failure = _failure(records)
    scope = _scope_contract(records)
    recommendation = _recommendation(score, context, completion, bfcl, cost, scope)
    score["selected_recommendation"] = recommendation["selected_recommendation"]
    score["accepted_mission_scope"] = scope
    _write_json(out / "phase6_score_envelope.json", score)
    _write_json(out / "phase6_context_report.json", context)
    _write_json(out / "phase6_completion_report.json", completion)
    _write_json(out / "phase6_bfcl_report.json", bfcl)
    _write_json(out / "phase6_terminalbench_report.json", terminalbench)
    _write_json(out / "phase6_trace_report.json", trace)
    _write_json(out / "phase6_cost_report.json", cost)
    _write_json(out / "phase6_failure_source_report.json", failure)
    _write_json(out / "phase6_recommendations.json", recommendation)
    _write_text(out / "phase6_handoff.md", _handoff(out, score, recommendation))
    ledger = _ledger_update(out, recommendation["selected_recommendation"], run_count=len(records))
    _record_ledger(ledger)
    _write_text(out / "RAW_LEDGER_UPDATE.txt", ledger)
    return {
        "output_dir": str(out),
        "run_count": len(records),
        "model_backed_runs": score["model_backed_runs"],
        "selected_recommendation": recommendation["selected_recommendation"],
    }


def _preflight(eval_cards: dict[str, dict[str, Any]]) -> dict[str, Any]:
    blockers: list[str] = []
    docker = _run(["docker", "info"], cwd=Path.cwd(), timeout=60)
    if docker["returncode"] != 0 or "Server:" not in docker["stdout"]:
        blockers.append("docker_unhealthy")
    missing_evals = sorted(set(REQUIRED_EVALS) - set(eval_cards))
    if missing_evals:
        blockers.append("required_eval_cards_missing")
    contextbench_parser = CONTEXTBENCH_ROOT / "contextbench/parsers/custom_parser.py"
    if not CONTEXTBENCH_ROOT.exists():
        blockers.append("contextbench_root_missing")
    if not contextbench_parser.exists():
        blockers.append("contextbench_custom_parser_missing")
    if not BFCL_PATH.exists():
        blockers.append("bfcl_mirror_missing")
    bfcl_has_required_case = _bfcl_has_case("multi_turn_composite_97")
    if BFCL_PATH.exists() and not bfcl_has_required_case:
        blockers.append("bfcl_required_case_missing")
    if not TERMINALBENCH_ROOT.exists():
        blockers.append("terminalbench_root_missing")
    letta = letta_preflight()
    blockers.extend(letta["blockers"])
    letta_selected_specs_count = 0
    if letta["status"] == "pass":
        try:
            letta_selected_specs_count = len(selected_letta_filesystem_specs())
        except Exception:
            blockers.append("letta_selected_specs_invalid")
    return {
        "status": "pass" if not blockers else "blocked",
        "blockers": blockers,
        "docker_info_live_server": docker["returncode"] == 0 and "Server:" in docker["stdout"],
        "required_eval_cards_missing": missing_evals,
        "contextbench_root": str(CONTEXTBENCH_ROOT),
        "contextbench_custom_parser": str(contextbench_parser),
        "contextbench_python": str(CONTEXTBENCH_PYTHON),
        "letta_context_bench": letta,
        "letta_selected_specs_count": letta_selected_specs_count,
        "bfcl_path": str(BFCL_PATH.resolve()),
        "bfcl_contains_multi_turn_composite_97": bfcl_has_required_case,
        "terminalbench_root": str(TERMINALBENCH_ROOT),
        "budget_caps": _budget_caps(),
    }


def _route_matrix(variants: list[str]) -> dict[str, Any]:
    baseline = build_packet04_route_manifest(BASELINE_VARIANT_ID, scope=PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE)
    rows = []
    blockers = []
    for variant in variants:
        try:
            manifest = build_packet04_route_manifest(variant, scope=PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE)
            load_runtime_callables(manifest)
            validate_independent_candidate_routing(candidate_manifest=manifest, baseline_manifest=baseline)
            rows.append(
                {
                    "variant_id": variant,
                    "route_valid": True,
                    "route_scope": manifest["route_scope"],
                    "route_manifest_fingerprint": manifest["route_manifest_fingerprint"],
                    "orientation_module": next(
                        row["module_import_path"]
                        for row in manifest["routed_modules"]
                        if row["runtime_key"] == "orientation"
                    ),
                }
            )
        except Exception as exc:
            blockers.append({"variant_id": variant, "error": str(exc)})
            rows.append({"variant_id": variant, "route_valid": False, "error": str(exc)})
    return {"mission_id": MISSION_ID, "status": "pass" if not blockers else "blocked", "routes": rows, "blockers": blockers}


def _doctrine_matrix(route_matrix: dict[str, Any]) -> dict[str, Any]:
    rows = []
    blockers = []
    required_fields = [
        "unit_of_work",
        "allowed_actions",
        "stopping_rule",
        "handoff_state_output",
        "evidence_receipts",
        "completion_rule",
        "failure_handling",
        "uncertainty_handling",
    ]
    for row in route_matrix["routes"]:
        variant = row["variant_id"]
        required = variant in DOCTRINE_VARIANTS
        route_valid = bool(row.get("route_valid"))
        doctrine_bound = route_valid and "phase6_doctrine" in str(row.get("orientation_module", ""))
        matrix_row = {
            "variant_id": variant,
            "doctrine_required": required,
            "route_valid": route_valid,
            "doctrine_bound": doctrine_bound if required else True,
            "required_fields": required_fields if required else [],
        }
        if required and (not route_valid or not doctrine_bound):
            blockers.append(
                {
                    "variant_id": variant,
                    "error": "missing_doctrine_contract_binding"
                    if route_valid
                    else "route_contract_missing_for_doctrine_check",
                }
            )
        rows.append(matrix_row)
    return {"mission_id": MISSION_ID, "status": "pass" if not blockers else "blocked", "rows": rows, "blockers": blockers}


def _execution_plan(output_root: Path, variants: list[str], rerun_count: int) -> dict[str, Any]:
    batch_specs = []
    common = {
        "packet_stage": "packet_04",
        "packet04_route_scope": PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE,
        "eval_family": MISSION_ID,
        "task_tier": "project_owned_tb_style_phase6",
        "rerun_count": rerun_count,
        "model_policy": {
            "screening_default": "azure:gpt-5.3-codex",
            "screening_fallback": "azure:gpt-5.3-codex",
            "promotion_tier": "azure:gpt-5.3-codex",
        },
        "provider_route": "openai_api",
        "model_tier_selector": "screening_default",
        "budget_caps": {"run_count": 350, "tokens": 3000000, "usd": 200.0},
        "stability_budget_caps": {"run_count": 350, "tokens": 3000000, "usd": 200.0},
        "output_root": str(output_root),
        "claim_route_id": "cr_successor_phase6_context_completion_repair_gauntlet",
        "fixed_invariants": {
            "comparator_variant_id": CONTROL,
            "incumbent_variant_id": INCUMBENT,
            "packet04_route_scope": PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE,
            "provider_route": "openai_api",
            "authority_boundary": "no_packet07_no_transfer_no_benchmark_widening_no_rhv1_unfreeze_no_holdouts",
        },
    }
    for eval_id in REQUIRED_EVALS:
        batch_specs.append(
            {
                **common,
                "batch_id": f"phase6__{eval_id}",
                "eval_ids": [eval_id],
                "variant_ids": variants,
                "task_set_id": f"phase6_{eval_id}",
                "task_intent": f"phase6_{eval_id}",
                "evaluation_lane": LANES.get(eval_id, "promotion"),
                "execution_mode_lock": {eval_id: EXECUTION_MODES[eval_id]},
                "eval_card_refs": {eval_id: f"active:{eval_id}"},
                "task_cases": [{"task_id": f"phase6_{eval_id}", "task_prompt": f"Phase6 eval probe for {eval_id}"}],
            }
        )
    model_backed_evals = [
        eval_id
        for eval_id in REQUIRED_EVALS
        if EXECUTION_MODES[eval_id] not in {"offline_judge_batchable", "deterministic_no_model"}
    ]
    return {
        "mission_id": MISSION_ID,
        "planned_run_count": len(batch_specs) * len(variants) * rerun_count,
        "planned_model_backed_runs": len(model_backed_evals) * len(variants) * rerun_count,
        "planned_local_deterministic_runs": (len(REQUIRED_EVALS) - len(model_backed_evals)) * len(variants) * rerun_count,
        "batch_specs": batch_specs,
    }


def _score(records: list[dict[str, Any]]) -> dict[str, Any]:
    model_backed_runs = _model_backed_count(records)
    return {
        "mission_id": MISSION_ID,
        "run_count": len(records),
        "model_backed_runs": model_backed_runs,
        "local_deterministic_runs": len(records) - model_backed_runs,
        "invalid_run_count": sum(1 for row in records if row.get("governed_terminal_status") == "invalid"),
        "final_verdict_counts": _counts(str(row.get("score_summary", {}).get("final_verdict")) for row in records),
        "variant_summary": _summary(records, "variant_id"),
        "by_eval_variant": _by_eval_variant(records),
    }


def _track_report(name: str, records: list[dict[str, Any]], eval_ids: list[str]) -> dict[str, Any]:
    subset = [row for row in records if row.get("eval_id") in set(eval_ids)]
    return {"mission_id": MISSION_ID, "report_id": name, "eval_ids": eval_ids, "run_count": len(subset), "by_variant": _summary(subset, "variant_id")}


def _cost(records: list[dict[str, Any]]) -> dict[str, Any]:
    total = {"total_tokens": 0, "usd": 0.0}
    by_variant: dict[str, dict[str, Any]] = {}
    for row in records:
        cost = row.get("token_and_cost_summary") or {}
        variant = str(row.get("variant_id"))
        bucket = by_variant.setdefault(variant, {"run_count": 0, "total_tokens": 0, "usd": 0.0})
        bucket["run_count"] += 1
        bucket["total_tokens"] += int(cost.get("total_tokens", 0) or 0)
        bucket["usd"] += float(cost.get("usd", cost.get("usd_estimate", 0.0)) or 0.0)
        total["total_tokens"] += int(cost.get("total_tokens", 0) or 0)
        total["usd"] += float(cost.get("usd", cost.get("usd_estimate", 0.0)) or 0.0)
    cap = "below_soft_cap" if total["usd"] <= 100 else "below_hard_cap" if total["usd"] <= 200 else "hard_cap_exceeded"
    return {"mission_id": MISSION_ID, "budget_caps": _budget_caps(), "cap_status": cap, "total": total, "by_variant": by_variant}


def _failure(records: list[dict[str, Any]]) -> dict[str, Any]:
    failing = [row for row in records if str(row.get("score_summary", {}).get("final_verdict")) != "pass"]
    return {"mission_id": MISSION_ID, "failure_count": len(failing), "failures": failing}


def _recommendation(
    score: dict[str, Any],
    context: dict[str, Any],
    completion: dict[str, Any],
    bfcl: dict[str, Any],
    cost: dict[str, Any],
    scope: dict[str, Any],
) -> dict[str, Any]:
    internal_board_recommendation = _internal_board_recommendation(score, context, completion, bfcl, cost)
    if scope["status"] != "complete":
        selected = "benchmark_adapter_still_invalid"
    elif score["invalid_run_count"] or cost["cap_status"] == "hard_cap_exceeded":
        selected = "benchmark_adapter_still_invalid"
    else:
        selected = internal_board_recommendation
    return {
        "mission_id": MISSION_ID,
        "selected_recommendation": selected,
        "exactly_one_final_recommendation": True,
        "final_recommendation_options": list(RECOMMENDATIONS),
        "basis": {
            "accepted_mission_scope_status": scope["status"],
            "internal_board_recommendation": internal_board_recommendation,
            "scope_caveat": scope["caveat"],
        },
    }


def _internal_board_recommendation(
    score: dict[str, Any],
    context: dict[str, Any],
    completion: dict[str, Any],
    bfcl: dict[str, Any],
    cost: dict[str, Any],
) -> str:
    if score["invalid_run_count"] or cost["cap_status"] == "hard_cap_exceeded":
        return "benchmark_adapter_still_invalid"
    elif _all_variants_all_pass(score) and score["run_count"] >= 150:
        return "internal_eval_suite_needs_harder_tasks"
    elif _best_repair_rate(context) < _pass_rate(context, INCUMBENT):
        return "candidate_needs_context_repair"
    elif _best_repair_rate(completion) < _pass_rate(completion, INCUMBENT):
        return "candidate_needs_one_more_completion_repair"
    elif _best_repair_rate(bfcl) < _pass_rate(bfcl, INCUMBENT):
        return "candidate_needs_toolcall_repair"
    elif _pass_rate(context, INCUMBENT) < 0.8:
        return "candidate_needs_context_repair"
    elif _pass_rate(completion, INCUMBENT) < 0.8:
        return "candidate_needs_one_more_completion_repair"
    elif _pass_rate(bfcl, INCUMBENT) < 0.8:
        return "candidate_needs_toolcall_repair"
    elif _pass_rate(context, INCUMBENT) == 1.0 and _pass_rate(completion, INCUMBENT) == 1.0 and _pass_rate(bfcl, INCUMBENT) == 1.0:
        return "candidate_repaired_and_ready_for_packet07_readiness_review"
    return "prefer_spb_01_or_pause_successor"


def _scope_contract(records: list[dict[str, Any]]) -> dict[str, Any]:
    executed = sorted({str(row.get("eval_id")) for row in records})
    missing = dict(ACCEPTED_PHASE6_REQUIRED_LANES)
    internal_homes = {eval_id for eval_ids in TRACK_EVALS.values() for eval_id in eval_ids}
    external_or_new_homes_executed = sorted(set(executed) - internal_homes)
    return {
        "status": "complete" if not missing else "incomplete",
        "executed_eval_ids": executed,
        "executed_external_or_new_eval_ids": external_or_new_homes_executed,
        "missing_accepted_scope": missing,
        "caveat": (
            "Final run executed the internal Phase 6 board homes and validated local mirrors, "
            "but did not execute the accepted richer ContextBench, Letta, BFCL strict, "
            "extract-moves, or newly designed TerminalBench-style eval lanes."
        ),
    }


def _write_blocked(out: Path, *, preflight: dict[str, Any], route_matrix: dict[str, Any], doctrine_matrix: dict[str, Any], execute: bool) -> dict[str, Any]:
    score = {"mission_id": MISSION_ID, "run_count": 0, "model_backed_runs": 0, "invalid_run_count": 0, "preflight": preflight, "route_matrix": route_matrix, "doctrine_matrix": doctrine_matrix}
    recommendation = {"mission_id": MISSION_ID, "selected_recommendation": "benchmark_adapter_still_invalid", "exactly_one_final_recommendation": True, "final_recommendation_options": list(RECOMMENDATIONS), "basis": {"execute": execute}}
    _write_jsonl(out / "phase6_result_records.jsonl", [])
    _write_json(out / "phase6_score_envelope.json", score)
    for name in ("phase6_context_report.json", "phase6_completion_report.json", "phase6_bfcl_report.json", "phase6_terminalbench_report.json", "phase6_trace_report.json", "phase6_cost_report.json", "phase6_failure_source_report.json"):
        _write_json(out / name, {"mission_id": MISSION_ID, "blocked": True, "execute": execute, "preflight": preflight, "route_matrix": route_matrix, "doctrine_matrix": doctrine_matrix})
    _write_json(out / "phase6_recommendations.json", recommendation)
    _write_text(out / "phase6_handoff.md", _handoff(out, score, recommendation))
    ledger = _ledger_update(out, recommendation["selected_recommendation"], run_count=0)
    _record_ledger(ledger)
    _write_text(out / "RAW_LEDGER_UPDATE.txt", ledger)
    return {"output_dir": str(out), "run_count": 0, "selected_recommendation": recommendation["selected_recommendation"]}


def _board_manifest(rerun_count: int) -> dict[str, Any]:
    return {
        "mission_id": MISSION_ID,
        "generated_at_utc": utc_now(),
        "route_scope": PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE,
        "control": CONTROL,
        "incumbent": INCUMBENT,
        "required_variants": list(REQUIRED_VARIANTS),
        "tracks": TRACK_EVALS,
        "accepted_mission_scope_status": "incomplete_internal_board_only",
        "accepted_mission_required_lanes_not_executed_by_this_runner": ACCEPTED_PHASE6_REQUIRED_LANES,
        "rerun_count": rerun_count,
        "authority_boundaries": {
            "packet07_movement": False,
            "benchmark_authority_widening": False,
            "leaderboard_submission": False,
            "transfer_movement": False,
            "protected_holdouts": False,
            "rhv1_unfreeze": False,
            "full_rhv1_revival": False,
            "task_id_routing": False,
        },
        "run_budget": _budget_caps(),
    }


def _plan(out: Path, rerun_count: int, preflight: dict[str, Any], route_matrix: dict[str, Any], doctrine_matrix: dict[str, Any]) -> str:
    return "\n".join([
        "# Phase 6 Context + Completion Repair Gauntlet Plan",
        "",
        f"- mission_id: `{MISSION_ID}`",
        f"- output_root: `{out}`",
        f"- route_scope: `{PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE}`",
        f"- rerun_count_per_eval_variant: `{rerun_count}`",
        f"- preflight_status: `{preflight['status']}`",
        f"- route_status: `{route_matrix['status']}`",
        f"- doctrine_status: `{doctrine_matrix['status']}`",
        f"- required_variants: `{', '.join(REQUIRED_VARIANTS)}`",
        f"- required_evals: `{', '.join(REQUIRED_EVALS)}`",
    ])


def _eval_design_report() -> str:
    return "\n".join([
        "# Phase 6 Eval Design Report",
        "",
        "- Completion lane uses `ae_completion_verifier_final_contradiction_probe` and `ae_internal_artifact_log_extraction_v1` for false-completion and closure checks.",
        "- Context lane uses `ae_internal_discovery_evidence_efficiency_v1` and `ae_internal_multifile_repair_test_verify_v1` for long-context retrieval and aggregation.",
        "- BFCL lane uses `ae_tool_call_contract_quality_v2` and `ae_tool_result_attribution_quality_v2` for strict multi-turn tool-call completeness.",
        "- TerminalBench regression lane uses `ae_internal_toolchain_dependency_pressure_v1` as the bounded TB-style regression home.",
        "- Mirrors validated in preflight: local ContextBench, local Letta Filesystem suite, and local BFCL v3 mirror with `multi_turn_composite_97`.",
    ])


def _internal_eval_spec() -> str:
    return "\n".join([
        "# Phase 6 Internal TB-Style Eval Spec",
        "",
        "1. Required-artifact closure: candidate must leave required artifacts present before completion.",
        "2. Toolchain recovery + post-download validation: candidate must validate outputs after dependency/tooling actions.",
        "3. Multi-file context aggregation: candidate must preserve context and answer extraction fidelity.",
        "4. Verifier-fail -> repair -> rerun: candidate must use verifier evidence and repair to true completion.",
        "5. Final gating: completion claim must be rejected if any required action or deliverable remains open.",
    ])


def _handoff(out: Path, score: dict[str, Any], recommendation: dict[str, Any]) -> str:
    return "\n".join([
        "# Phase 6 Handoff",
        "",
        f"- mission_id: `{MISSION_ID}`",
        f"- output_root: `{out}`",
        f"- run_count: `{score.get('run_count', 0)}`",
        f"- model_backed_runs: `{score.get('model_backed_runs', 0)}`",
        f"- invalid_run_count: `{score.get('invalid_run_count', 0)}`",
        f"- final_recommendation: `{recommendation['selected_recommendation']}`",
        f"- internal_board_recommendation: `{recommendation.get('basis', {}).get('internal_board_recommendation', recommendation['selected_recommendation'])}`",
        f"- accepted_mission_scope_status: `{recommendation.get('basis', {}).get('accepted_mission_scope_status', 'unknown')}`",
        f"- scope_caveat: {recommendation.get('basis', {}).get('scope_caveat', 'not recorded')}",
        "- authority: no Packet07 movement, no benchmark-authority widening, no transfer movement, no protected holdouts, no RHv1 unfreeze, and no task-id routing.",
    ])


def _ledger_update(out: Path, recommendation: str, *, run_count: int) -> str:
    return "\n".join([
        "RAW_LEDGER_UPDATE",
        "- actor: codex",
        "- task: successor phase6 context+completion repair gauntlet runner execution",
        "- event_type: implementation",
        f"- summary: Produced bounded Phase6 internal-board artifacts with strict preflight/route/doctrine gates and recommendation `{recommendation}` because the accepted external/new-eval scope was not fully executed.",
        f"- observations: Phase6 run_count `{run_count}`; contracts fail closed when preflight/route/doctrine blockers are present; the internal board completed but richer ContextBench, Letta, BFCL strict, extract-moves, and new TerminalBench-style eval lanes were not executed by this runner.",
        "- inference: Phase6 governance is executable without widening authority, but this artifact stream is internal-board evidence rather than the complete accepted Phase6 repair gauntlet.",
        f"- evidence_paths: {out / 'phase6_plan.md'}; {out / 'phase6_board_manifest.json'}; {out / 'phase6_route_matrix.json'}; {out / 'phase6_variant_doctrine_matrix.json'}; {out / 'phase6_execution_plan.json'}; {out / 'phase6_score_envelope.json'}; {out / 'phase6_handoff.md'}",
        "- affected_components: packet06 paired combo variants; phase6 bounded runner; route/doctrine/preflight contract gating",
        "- decision_change: NONE - implementation and bounded evidence only",
        "- unresolved_questions: Whether to run the missing accepted external/new-eval lanes and implement candidate_plus repairs as real runtime mechanisms rather than orientation-only doctrines.",
        "- confidence: medium",
        "- commit_message: HOLD - correct Phase6 internal-board scope interpretation",
    ])


def _summary(records: list[dict[str, Any]], key: str) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for row in records:
        bucket = out.setdefault(str(row.get(key)), {"run_count": 0, "pass": 0, "fail": 0, "unresolved": 0})
        bucket["run_count"] += 1
        verdict = str(row.get("score_summary", {}).get("final_verdict"))
        bucket[verdict if verdict in {"pass", "fail", "unresolved"} else "unresolved"] += 1
    return out


def _by_eval_variant(records: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, int]]]:
    out: dict[str, dict[str, dict[str, int]]] = {}
    for row in records:
        eval_bucket = out.setdefault(str(row.get("eval_id")), {})
        variant_bucket = eval_bucket.setdefault(str(row.get("variant_id")), {"run_count": 0, "pass": 0, "fail": 0, "unresolved": 0})
        variant_bucket["run_count"] += 1
        verdict = str(row.get("score_summary", {}).get("final_verdict"))
        variant_bucket[verdict if verdict in {"pass", "fail", "unresolved"} else "unresolved"] += 1
    return out


def _pass_rate(report: dict[str, Any], variant: str) -> float:
    row = report.get("by_variant", {}).get(variant, {})
    return _rate(row)


def _rate(row: dict[str, Any]) -> float:
    count = int(row.get("run_count", 0) or 0)
    return float(row.get("pass", 0) or 0) / count if count else 0.0


def _model_backed_count(records: list[dict[str, Any]]) -> int:
    return sum(
        1
        for row in records
        if row.get("model_route", {}).get("model_name") not in {None, "none", "local_deterministic_contract"}
    )


def _all_variants_all_pass(score: dict[str, Any]) -> bool:
    return bool(score.get("variant_summary")) and all(
        row.get("fail", 0) == 0 and row.get("unresolved", 0) == 0
        for row in score["variant_summary"].values()
    )


def _best_repair_rate(report: dict[str, Any]) -> float:
    return max(
        (
            _rate(row)
            for variant, row in report.get("by_variant", {}).items()
            if str(variant).startswith("candidate_plus_")
        ),
        default=0.0,
    )


def _load_eval_cards(path: Path) -> dict[str, dict[str, Any]]:
    cards = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            card = json.loads(line)
            cards[card["eval_id"]] = card
    return cards


def _bfcl_has_case(case_id: str) -> bool:
    if not BFCL_PATH.exists():
        return False
    rows = json.loads(BFCL_PATH.read_text(encoding="utf-8"))
    return any(str(row.get("id")) == case_id for row in rows if isinstance(row, dict))


def _run(cmd: list[str], *, cwd: Path, timeout: int) -> dict[str, Any]:
    completed = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=timeout, check=False)
    return {"cmd": " ".join(cmd), "returncode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr}


def _budget_caps() -> dict[str, Any]:
    return {"target_model_backed_runs": [150, 250], "hard_model_backed_cap": 350, "local_deterministic_cap": 300, "soft_cost_cap_usd": 100.0, "hard_cost_cap_usd": 200.0}


def _counts(values: Any) -> dict[str, int]:
    out: dict[str, int] = {}
    for value in values:
        out[str(value)] = out.get(str(value), 0) + 1
    return out


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _record_ledger(raw: str) -> None:
    proc = subprocess.run([sys.executable, "tracking/ledger/tools/record_update.py"], input=raw, text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"ledger update failed: {proc.stderr}")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.write_text(text + ("\n" if text and not text.endswith("\n") else ""), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--eval-cards-path", default=str(DEFAULT_EVAL_CARDS_PATH))
    parser.add_argument("--rerun-count", type=int, default=2)
    parser.add_argument("--no-execute", action="store_true")
    args = parser.parse_args(argv)
    print(
        json.dumps(
            launch_phase6(
                output_dir=args.output_dir,
                eval_cards_path=args.eval_cards_path,
                rerun_count=args.rerun_count,
                execute=not args.no_execute,
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
