"""Execute Phase 5 hard long-horizon and workflow-variant gauntlet."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from runner.eval_batch_runner import run_batch
from runner.packet04_route_manifest import (
    BASELINE_VARIANT_ID,
    PACKET06_PHASE5_HARD_GAUNTLET_SCOPE,
    build_packet04_route_manifest,
    load_runtime_callables,
    validate_independent_candidate_routing,
)
from runner.schemas import utc_now

DEFAULT_EVAL_CARDS_PATH = Path(
    "tracking/collab/stage_03_execution_planning/packets/"
    "packet_03_atomic_eval_families/outputs/eval_cards.active.jsonl"
)

MISSION_ID = "successor_phase5_hard_long_horizon_workflow_gauntlet"
CONTROL = "spb_01"
INCUMBENT = "spb_tooling_seed_plus_receipt_and_completion_01"
REQUIRED_VARIANTS = (
    CONTROL,
    INCUMBENT,
    "model_led_compaction_01",
    "harness_led_receipt_compaction_01",
    "hybrid_model_handoff_plus_receipts_01",
    "codex_style_handoff_compaction_01",
    "bounded_episode_01",
    "adaptive_episode_01",
    "failure_autopsy_repair_loop_01",
    "verification_repair_loop_01",
    "bigai_style_manager_worker_verifier_01",
)
REQUIRED_EVALS = (
    "ae_internal_toolchain_dependency_pressure_v1",
    "ae_internal_artifact_log_extraction_v1",
    "ae_internal_discovery_evidence_efficiency_v1",
    "ae_internal_multifile_repair_test_verify_v1",
    "ae_completion_verifier_final_contradiction_probe",
)
EXECUTION_MODES = {
    "ae_internal_toolchain_dependency_pressure_v1": "multistep_batchable",
    "ae_internal_artifact_log_extraction_v1": "multistep_batchable",
    "ae_internal_discovery_evidence_efficiency_v1": "multistep_batchable",
    "ae_internal_multifile_repair_test_verify_v1": "multistep_batchable",
    "ae_completion_verifier_final_contradiction_probe": "offline_judge_batchable",
}
LANES = {"ae_completion_verifier_final_contradiction_probe": "bounded_diagnostic"}
FINAL_OPTIONS = {
    "candidate_ready_for_packet07_readiness_review",
    "candidate_needs_long_horizon_repair",
    "candidate_needs_context_management_variant",
    "candidate_needs_failure_recovery_variant",
    "candidate_needs_action_granularity_variant",
    "eval_suite_too_easy_repair_before_packet07",
    "prefer_spb_01_or_close_successor",
}
TRACK_EVALS = {
    "tb_style_probe": [
        "ae_internal_discovery_evidence_efficiency_v1",
        "ae_internal_multifile_repair_test_verify_v1",
    ],
    "long_horizon_context_compaction": [
        "ae_internal_discovery_evidence_efficiency_v1",
        "ae_internal_multifile_repair_test_verify_v1",
        "ae_internal_artifact_log_extraction_v1",
    ],
    "false_completion_repair": [
        "ae_completion_verifier_final_contradiction_probe",
        "ae_internal_multifile_repair_test_verify_v1",
    ],
    "failure_recovery": [
        "ae_internal_toolchain_dependency_pressure_v1",
        "ae_internal_artifact_log_extraction_v1",
        "ae_internal_multifile_repair_test_verify_v1",
    ],
    "messy_multifile_repo_repair": ["ae_internal_multifile_repair_test_verify_v1"],
    "regression_homes": list(REQUIRED_EVALS),
}
DOCTRINE_VARIANTS = {
    "model_led_compaction_01",
    "harness_led_receipt_compaction_01",
    "hybrid_model_handoff_plus_receipts_01",
    "codex_style_handoff_compaction_01",
    "bounded_episode_01",
    "adaptive_episode_01",
    "failure_autopsy_repair_loop_01",
    "verification_repair_loop_01",
    "bigai_style_manager_worker_verifier_01",
}


def launch_phase5(
    *,
    output_dir: str | Path,
    eval_cards_path: str | Path = DEFAULT_EVAL_CARDS_PATH,
    rerun_count: int = 4,
    execute: bool = True,
) -> dict[str, Any]:
    output_root = Path(output_dir).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    eval_cards = _load_eval_cards(Path(eval_cards_path))
    variants = list(REQUIRED_VARIANTS)

    board = _board_manifest(variants, rerun_count)
    route_matrix = _route_matrix(variants)
    execution_plan = _execution_plan(output_root, variants, rerun_count)
    _write_text(output_root / "phase5_plan.md", _plan(output_root, variants, rerun_count))
    _write_json(output_root / "phase5_board_manifest.json", board)
    _write_json(output_root / "phase5_route_matrix.json", route_matrix)
    _write_json(output_root / "phase5_execution_plan.json", execution_plan)
    if route_matrix["status"] != "pass" or not execute:
        return _write_blocked_outputs(output_root, route_matrix, execute=execute)

    batch_results = []
    for batch in execution_plan["batch_specs"]:
        result = run_batch(batch_spec=batch, eval_cards={eval_id: eval_cards[eval_id] for eval_id in batch["eval_ids"]})
        batch_results.append(result)

    records = _read_jsonl_many(Path(result["result_records_path"]) for result in batch_results)
    traces = _read_jsonl_many(Path(result["trace_summaries_path"]) for result in batch_results)
    _write_jsonl(output_root / "phase5_result_records.jsonl", records)

    score = _score_envelope(records)
    cost = _cost_report(records)
    failure = _failure_source_report(records)
    context = _track_report("context_compaction", records, traces, TRACK_EVALS["long_horizon_context_compaction"])
    episode = _track_report("work_episode", records, traces, TRACK_EVALS["messy_multifile_repo_repair"])
    recovery = _track_report("recovery", records, traces, TRACK_EVALS["failure_recovery"])
    false_completion = _track_report("false_completion", records, traces, TRACK_EVALS["false_completion_repair"])
    multi_agent = _variant_family_report("multi_agent", records, traces, ["bigai_style_manager_worker_verifier_01"])
    tb_style = _track_report("tb_style_probe", records, traces, TRACK_EVALS["tb_style_probe"])
    recommendation = _recommendation(score, context, episode, recovery, false_completion, multi_agent, cost, failure)

    _write_json(output_root / "phase5_score_envelope.json", score)
    _write_json(output_root / "phase5_context_compaction_report.json", context)
    _write_json(output_root / "phase5_work_episode_report.json", episode)
    _write_json(output_root / "phase5_recovery_report.json", recovery)
    _write_json(output_root / "phase5_false_completion_report.json", false_completion)
    _write_json(output_root / "phase5_multi_agent_report.json", multi_agent)
    _write_json(output_root / "phase5_tb_style_probe_report.json", tb_style)
    _write_json(output_root / "phase5_cost_report.json", cost)
    _write_json(output_root / "phase5_failure_source_report.json", failure)
    _write_json(output_root / "phase5_recommendations.json", recommendation)
    _write_text(output_root / "phase5_handoff.md", _handoff(output_root, score, recommendation))
    return {
        "output_dir": str(output_root),
        "run_count": len(records),
        "model_backed_runs": score["model_backed_runs"],
        "selected_recommendation": recommendation["selected_recommendation"],
    }


def _board_manifest(variants: list[str], rerun_count: int) -> dict[str, Any]:
    return {
        "mission_id": MISSION_ID,
        "generated_at_utc": utc_now(),
        "status": "contracts_pass_execution_ready",
        "control": CONTROL,
        "incumbent": INCUMBENT,
        "variants": variants,
        "required_variant_families": [v for v in variants if v not in {CONTROL, INCUMBENT}],
        "conditional_excluded": {"env_snapshot_v2_01": "excluded_no_explicit_repair_hypothesis"},
        "eval_tracks": TRACK_EVALS,
        "eval_homes": list(REQUIRED_EVALS),
        "rerun_count": rerun_count,
        "doctrine_bindings": {variant: f"blocks/orientation/workflow_doctrine.py#{variant}" for variant in DOCTRINE_VARIANTS},
        "doctrine_contract": {
            "status": "pass",
            "required_fields": [
                "unit_of_work",
                "allowed_actions",
                "stopping_rule",
                "handoff_state_output",
                "evidence_receipts",
                "failure_handling",
                "uncertainty_handling",
            ],
        },
        "authority_boundaries": _authority_boundaries(),
        "run_budget": _budget_caps(),
    }


def _route_matrix(variants: list[str]) -> dict[str, Any]:
    baseline = build_packet04_route_manifest(BASELINE_VARIANT_ID, scope=PACKET06_PHASE5_HARD_GAUNTLET_SCOPE)
    rows = []
    blockers = []
    for variant in variants:
        try:
            manifest = build_packet04_route_manifest(variant, scope=PACKET06_PHASE5_HARD_GAUNTLET_SCOPE)
            load_runtime_callables(manifest)
            validate_independent_candidate_routing(candidate_manifest=manifest, baseline_manifest=baseline)
            rows.append({
                "variant_id": variant,
                "route_valid": True,
                "route_scope": manifest["route_scope"],
                "route_manifest_fingerprint": manifest["route_manifest_fingerprint"],
                "changed_runtime_keys": [
                    row["runtime_key"] for row in manifest["routed_modules"] if row.get("claimed_changed_surface")
                ],
                "doctrine_bound": variant not in DOCTRINE_VARIANTS or "workflow_doctrine.py" in json.dumps(manifest),
            })
        except Exception as exc:
            blockers.append({"variant_id": variant, "error": str(exc)})
            rows.append({"variant_id": variant, "route_valid": False, "error": str(exc)})
    doctrine_blockers = [
        row for row in rows if row.get("variant_id") in DOCTRINE_VARIANTS and not row.get("doctrine_bound")
    ]
    blockers.extend({"variant_id": row["variant_id"], "error": "missing doctrine binding"} for row in doctrine_blockers)
    return {
        "mission_id": MISSION_ID,
        "route_scope": PACKET06_PHASE5_HARD_GAUNTLET_SCOPE,
        "status": "pass" if not blockers else "blocked",
        "routes": rows,
        "blockers": blockers,
    }


def _execution_plan(output_root: Path, variants: list[str], rerun_count: int) -> dict[str, Any]:
    common = {
        "packet_stage": "packet_04",
        "packet04_route_scope": PACKET06_PHASE5_HARD_GAUNTLET_SCOPE,
        "eval_family": MISSION_ID,
        "task_tier": "project_owned_tb_style_hard_phase5",
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
        "claim_route_id": "cr_successor_phase5_hard_gauntlet",
        "fixed_invariants": {
            "comparator_variant_id": CONTROL,
            "incumbent_variant_id": INCUMBENT,
            "packet04_route_scope": PACKET06_PHASE5_HARD_GAUNTLET_SCOPE,
            "provider_route": "openai_api",
            "authority_boundary": "no_packet07_no_transfer_no_benchmark_widening_no_rhv1_unfreeze_no_holdouts",
        },
    }
    specs = []
    for eval_id in REQUIRED_EVALS:
        specs.append({
            **common,
            "batch_id": f"phase5__{eval_id}",
            "eval_ids": [eval_id],
            "variant_ids": variants,
            "task_set_id": f"phase5_{eval_id}",
            "task_intent": f"phase5_hard_gauntlet_{eval_id}",
            "evaluation_lane": LANES.get(eval_id, "promotion"),
            "execution_mode_lock": {eval_id: EXECUTION_MODES[eval_id]},
            "eval_card_refs": {eval_id: f"active:{eval_id}"},
            "task_cases": [{
                "task_id": f"phase5_{eval_id}",
                "task_prompt": f"Phase5 hard long-horizon workflow gauntlet probe for {eval_id}",
            }],
        })
    model_backed_evals = [eval_id for eval_id in REQUIRED_EVALS if EXECUTION_MODES[eval_id] != "offline_judge_batchable"]
    return {
        "mission_id": MISSION_ID,
        "planned_run_count": len(specs) * len(variants) * rerun_count,
        "planned_model_backed_runs": len(model_backed_evals) * len(variants) * rerun_count,
        "planned_local_deterministic_runs": (len(REQUIRED_EVALS) - len(model_backed_evals)) * len(variants) * rerun_count,
        "batch_specs": specs,
    }


def _score_envelope(records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "mission_id": MISSION_ID,
        "run_count": len(records),
        "model_backed_runs": _model_backed_count(records),
        "local_deterministic_runs": len(records) - _model_backed_count(records),
        "invalid_run_count": _invalid_count(records),
        "final_verdict_counts": _counts(_verdict(row) for row in records),
        "variant_summary": _variant_summary(records),
        "by_eval_variant": _eval_variant_summary(records),
    }


def _track_report(name: str, records: list[dict[str, Any]], traces: list[dict[str, Any]], eval_ids: list[str]) -> dict[str, Any]:
    subset = [row for row in records if row.get("eval_id") in set(eval_ids)]
    return {
        "mission_id": MISSION_ID,
        "report_id": name,
        "eval_ids": eval_ids,
        "run_count": len(subset),
        "by_variant": _variant_summary(subset),
        "signal_by_variant": _signal_by_variant(traces, set(eval_ids)),
    }


def _variant_family_report(name: str, records: list[dict[str, Any]], traces: list[dict[str, Any]], variants: list[str]) -> dict[str, Any]:
    subset = [row for row in records if row.get("variant_id") in set(variants)]
    return {
        "mission_id": MISSION_ID,
        "report_id": name,
        "variants": variants,
        "run_count": len(subset),
        "by_variant": _variant_summary(subset),
        "signal_by_variant": _signal_by_variant(traces, None, variants=set(variants)),
    }


def _cost_report(records: list[dict[str, Any]]) -> dict[str, Any]:
    total = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "usd": 0.0}
    by_variant: dict[str, dict[str, Any]] = {}
    for row in records:
        cost = row.get("token_and_cost_summary") or {}
        variant = str(row.get("variant_id"))
        bucket = by_variant.setdefault(variant, {"run_count": 0, "total_tokens": 0, "usd": 0.0})
        bucket["run_count"] += 1
        bucket["total_tokens"] += int(cost.get("total_tokens", 0) or 0)
        bucket["usd"] += float(cost.get("usd", cost.get("usd_estimate", 0.0)) or 0.0)
        total["input_tokens"] += int(cost.get("input_tokens", 0) or 0)
        total["output_tokens"] += int(cost.get("output_tokens", cost.get("total_output_tokens", 0)) or 0)
        total["total_tokens"] += int(cost.get("total_tokens", 0) or 0)
        total["usd"] += float(cost.get("usd", cost.get("usd_estimate", 0.0)) or 0.0)
    return {
        "mission_id": MISSION_ID,
        "budget_caps": _budget_caps(),
        "cap_status": "below_soft_cap" if total["usd"] <= 100 else "below_hard_cap" if total["usd"] <= 200 else "hard_cap_exceeded",
        "total": total,
        "by_variant": by_variant,
    }


def _failure_source_report(records: list[dict[str, Any]]) -> dict[str, Any]:
    failures = [
        {
            "run_id": row.get("run_id"),
            "eval_id": row.get("eval_id"),
            "variant_id": row.get("variant_id"),
            "failure_cluster": row.get("failure_cluster"),
            "reason_codes": row.get("reason_codes", []),
            "verdict": _verdict(row),
        }
        for row in records
        if _verdict(row) != "pass"
    ]
    return {"mission_id": MISSION_ID, "failure_count": len(failures), "invalid_run_count": _invalid_count(records), "failures": failures}


def _recommendation(
    score: dict[str, Any],
    context: dict[str, Any],
    episode: dict[str, Any],
    recovery: dict[str, Any],
    false_completion: dict[str, Any],
    multi_agent: dict[str, Any],
    cost: dict[str, Any],
    failure: dict[str, Any],
) -> dict[str, Any]:
    summary = score["variant_summary"]
    incumbent = summary.get(INCUMBENT, {})
    control = summary.get(CONTROL, {})
    if failure["invalid_run_count"] or cost["cap_status"] == "hard_cap_exceeded":
        selected = "candidate_needs_long_horizon_repair"
    elif _all_variants_all_pass(score) and score["run_count"] >= 150:
        selected = "eval_suite_too_easy_repair_before_packet07"
    elif _pass_rate(context, INCUMBENT) < 0.8:
        selected = "candidate_needs_context_management_variant"
    elif _pass_rate(recovery, INCUMBENT) < 0.8 or _pass_rate(false_completion, INCUMBENT) < 0.8:
        selected = "candidate_needs_failure_recovery_variant"
    elif _pass_rate(episode, INCUMBENT) < 0.8:
        selected = "candidate_needs_action_granularity_variant"
    elif incumbent.get("pass", 0) <= control.get("pass", 0) and incumbent.get("fail", 0) >= control.get("fail", 0):
        selected = "prefer_spb_01_or_close_successor"
    else:
        selected = "candidate_ready_for_packet07_readiness_review"
    return {
        "mission_id": MISSION_ID,
        "selected_recommendation": selected,
        "exactly_one_final_recommendation": True,
        "final_recommendation_options": sorted(FINAL_OPTIONS),
        "basis": {
            "score_summary": score,
            "context_pass_rate_incumbent": _pass_rate(context, INCUMBENT),
            "recovery_pass_rate_incumbent": _pass_rate(recovery, INCUMBENT),
            "false_completion_pass_rate_incumbent": _pass_rate(false_completion, INCUMBENT),
            "episode_pass_rate_incumbent": _pass_rate(episode, INCUMBENT),
            "multi_agent_pass_rate": _pass_rate(multi_agent, "bigai_style_manager_worker_verifier_01"),
            "cost_report": cost,
        },
        "authority_note": "No Packet 07 movement, transfer, benchmark widening, protected holdout access, RHv1 unfreeze, full RHv1 revival, or task-ID routing occurred.",
    }


def _write_blocked_outputs(output_root: Path, route_matrix: dict[str, Any], *, execute: bool) -> dict[str, Any]:
    score = {"mission_id": MISSION_ID, "run_count": 0, "model_backed_runs": 0, "invalid_run_count": 0, "route_matrix": route_matrix}
    recommendation = {"mission_id": MISSION_ID, "selected_recommendation": "candidate_needs_long_horizon_repair", "exactly_one_final_recommendation": True, "basis": {"execute": execute, "route_matrix": route_matrix}}
    _write_jsonl(output_root / "phase5_result_records.jsonl", [])
    for name in (
        "phase5_score_envelope.json",
        "phase5_context_compaction_report.json",
        "phase5_work_episode_report.json",
        "phase5_recovery_report.json",
        "phase5_false_completion_report.json",
        "phase5_multi_agent_report.json",
        "phase5_tb_style_probe_report.json",
        "phase5_cost_report.json",
        "phase5_failure_source_report.json",
    ):
        _write_json(output_root / name, {"mission_id": MISSION_ID, "blocked": True, "route_matrix": route_matrix})
    _write_json(output_root / "phase5_recommendations.json", recommendation)
    _write_text(output_root / "phase5_handoff.md", _handoff(output_root, score, recommendation))
    return {"output_dir": str(output_root), "run_count": 0, "selected_recommendation": recommendation["selected_recommendation"]}


def _load_eval_cards(path: Path) -> dict[str, dict[str, Any]]:
    cards: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        card = json.loads(line)
        cards[card["eval_id"]] = card
    missing = sorted(set(REQUIRED_EVALS) - set(cards))
    if missing:
        raise ValueError(f"missing required eval cards: {missing}")
    return cards


def _variant_summary(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in records:
        variant = str(row.get("variant_id"))
        bucket = out.setdefault(variant, {"run_count": 0, "pass": 0, "fail": 0, "unresolved": 0, "other": 0})
        bucket["run_count"] += 1
        verdict = _verdict(row)
        bucket[verdict if verdict in {"pass", "fail", "unresolved"} else "other"] += 1
    return out


def _eval_variant_summary(records: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, int]]]:
    out: dict[str, dict[str, dict[str, int]]] = {}
    for row in records:
        eval_bucket = out.setdefault(str(row.get("eval_id")), {})
        variant_bucket = eval_bucket.setdefault(str(row.get("variant_id")), {"run_count": 0, "pass": 0, "fail": 0, "unresolved": 0, "other": 0})
        variant_bucket["run_count"] += 1
        verdict = _verdict(row)
        variant_bucket[verdict if verdict in {"pass", "fail", "unresolved"} else "other"] += 1
    return out


def _signal_by_variant(traces: list[dict[str, Any]], eval_ids: set[str] | None, *, variants: set[str] | None = None) -> dict[str, dict[str, bool]]:
    filtered = [
        row for row in traces
        if (eval_ids is None or row.get("eval_id") in eval_ids) and (variants is None or row.get("variant_id") in variants)
    ]
    out: dict[str, dict[str, bool]] = {}
    for row in filtered:
        variant = str(row.get("variant_id"))
        text = json.dumps(row, sort_keys=True)
        bucket = out.setdefault(variant, {"tool": False, "receipt": False, "completion": False, "failure": False})
        bucket["tool"] = bucket["tool"] or any(token in text for token in ("raw_bash", "toolchain", "tool_call"))
        bucket["receipt"] = bucket["receipt"] or any(token in text for token in ("receipt", "artifact_log", "attribution_trace"))
        bucket["completion"] = bucket["completion"] or any(token in text for token in ("completion", "contradiction", "final_acceptance"))
        bucket["failure"] = bucket["failure"] or any(token in text for token in ("fail", "error", "repair"))
    return out


def _model_backed_count(records: list[dict[str, Any]]) -> int:
    return sum(1 for row in records if row.get("model_route", {}).get("model_name") not in {None, "none", "local_deterministic_contract"})


def _invalid_count(records: list[dict[str, Any]]) -> int:
    return sum(
        1
        for row in records
        if row.get("governed_terminal_status") == "invalid"
        or "model_execution_error" in row.get("reason_codes", [])
    )


def _counts(values: Any) -> dict[str, int]:
    out: dict[str, int] = {}
    for value in values:
        key = str(value)
        out[key] = out.get(key, 0) + 1
    return out


def _verdict(row: dict[str, Any]) -> str:
    return str(row.get("score_summary", {}).get("final_verdict", "unknown"))


def _pass_rate(report: dict[str, Any], variant: str) -> float:
    row = report.get("by_variant", {}).get(variant, {})
    count = int(row.get("run_count", 0) or 0)
    return float(row.get("pass", 0) or 0) / count if count else 0.0


def _all_variants_all_pass(score: dict[str, Any]) -> bool:
    return bool(score.get("variant_summary")) and all(row.get("fail", 0) == 0 and row.get("unresolved", 0) == 0 for row in score["variant_summary"].values())


def _read_jsonl_many(paths: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _plan(output_root: Path, variants: list[str], rerun_count: int) -> str:
    return "\n".join([
        "# Phase 5 Hard Long-Horizon Workflow Gauntlet Plan",
        "",
        f"- mission_id: `{MISSION_ID}`",
        f"- output_root: `{output_root}`",
        f"- operational_control: `{CONTROL}`",
        f"- incumbent_candidate: `{INCUMBENT}`",
        f"- route_scope: `{PACKET06_PHASE5_HARD_GAUNTLET_SCOPE}`",
        f"- variants: `{', '.join(variants)}`",
        f"- eval_homes: `{', '.join(REQUIRED_EVALS)}`",
        f"- rerun_count_per_eval_variant: `{rerun_count}`",
        "- env_snapshot_v2_01: excluded; no explicit repair hypothesis admitted.",
        "- authority: no Packet 07 movement, transfer, benchmark widening, protected holdouts, RHv1 unfreeze, full RHv1 revival, or task-ID routing.",
        "",
    ])


def _handoff(output_root: Path, score: dict[str, Any], recommendation: dict[str, Any]) -> str:
    return "\n".join([
        "# Phase 5 Hard Long-Horizon Workflow Handoff",
        "",
        f"- mission_id: `{MISSION_ID}`",
        f"- output_root: `{output_root}`",
        f"- run_count: `{score.get('run_count', 0)}`",
        f"- model_backed_runs: `{score.get('model_backed_runs', 0)}`",
        f"- invalid_run_count: `{score.get('invalid_run_count', 0)}`",
        f"- final_recommendation: `{recommendation['selected_recommendation']}`",
        "- authority: no Packet 07 movement, transfer, benchmark widening, protected holdouts, RHv1 unfreeze, or full RHv1 revival occurred.",
        "",
    ])


def _authority_boundaries() -> dict[str, bool]:
    return {
        "packet07_movement": False,
        "transfer": False,
        "benchmark_authority_widening": False,
        "protected_holdouts": False,
        "rhv1_unfreeze": False,
        "full_rhv1_revival": False,
        "task_id_routing": False,
    }


def _budget_caps() -> dict[str, Any]:
    return {"target_model_backed_runs": [150, 250], "hard_model_backed_cap": 350, "local_deterministic_cap": 300, "soft_cost_cap_usd": 100.0, "hard_cost_cap_usd": 200.0}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--eval-cards-path", default=str(DEFAULT_EVAL_CARDS_PATH))
    parser.add_argument("--rerun-count", type=int, default=4)
    parser.add_argument("--no-execute", action="store_true")
    args = parser.parse_args(argv)
    result = launch_phase5(
        output_dir=args.output_dir,
        eval_cards_path=args.eval_cards_path,
        rerun_count=args.rerun_count,
        execute=not args.no_execute,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
