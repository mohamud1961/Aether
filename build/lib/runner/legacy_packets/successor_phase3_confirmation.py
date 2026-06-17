"""Execute the bounded successor Phase 3 tooling confirmation mission."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from runner.eval_batch_runner import run_batch
from runner.packet04_route_manifest import (
    BASELINE_VARIANT_ID,
    PACKET06_PHASE2_ENV_TOOLING_SCOPE,
    build_packet04_route_manifest,
    load_runtime_callables,
    validate_independent_candidate_routing,
)
from runner.schemas import utc_now

DEFAULT_EVAL_CARDS_PATH = Path(
    "tracking/collab/stage_03_execution_planning/packets/packet_03_atomic_eval_families/outputs/eval_cards.active.jsonl"
)

MISSION_ID = "successor_phase3_confirmation"
SPB_VARIANT_ID = "spb_01"
TOOLCHAIN_VARIANT_ID = "v04_tb_01_tool_call_contract_classifier"
RECEIPT_VARIANT_ID = "v04_tb_02_permission_runtime_attribution_split"
SEED_VARIANT_ID = "spb_tooling_seed_01"
TOOLCHAIN_EVAL_ID = "ae_internal_toolchain_dependency_pressure_v1"
ARTIFACT_LOG_EVAL_ID = "ae_internal_artifact_log_extraction_v1"
FINAL_OPTIONS = {
    "confirm_spb_tooling_seed_for_candidate_assembly",
    "run_targeted_phase3_repair",
    "prefer_spb_01_continue",
    "repair_tooling_eval_board",
    "defer_tooling_seed_no_model_backed_signal",
}


def launch_phase3_confirmation(
    *,
    output_dir: str | Path,
    eval_cards_path: str | Path = DEFAULT_EVAL_CARDS_PATH,
) -> dict[str, Any]:
    output_root = Path(output_dir).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    eval_cards = _load_eval_cards(Path(eval_cards_path))

    _write_text(output_root / "phase3_mission_plan.md", _mission_plan(output_root))
    board_manifest = _board_manifest()
    route_matrix = _route_matrix(board_manifest)
    execution_plan = _execution_plan(output_root)
    _write_json(output_root / "phase3_board_manifest.json", board_manifest)
    _write_json(output_root / "phase3_route_matrix.json", route_matrix)
    _write_json(output_root / "phase3_execution_plan.json", execution_plan)

    batch_results = []
    for batch_spec in execution_plan["batch_specs"]:
        result = run_batch(
            batch_spec=batch_spec,
            eval_cards={eval_id: eval_cards[eval_id] for eval_id in batch_spec["eval_ids"]},
        )
        batch_results.append(result)

    records = _read_jsonl_many([Path(result["result_records_path"]) for result in batch_results])
    traces = _read_jsonl_many([Path(result["trace_summaries_path"]) for result in batch_results])
    _write_jsonl(output_root / "phase3_result_records.jsonl", records)

    model_report = _model_backed_trace_report(records, traces)
    tooling_report = _variant_eval_report(records, traces, eval_id=TOOLCHAIN_EVAL_ID)
    receipt_report = _variant_eval_report(records, traces, eval_id=ARTIFACT_LOG_EVAL_ID)
    cost_report = _cost_report(records)
    failure_report = _failure_source_report(records)
    score_envelope = _score_envelope(records, model_report, tooling_report, receipt_report)
    recommendation = _recommendation(score_envelope, model_report, cost_report, failure_report)

    _write_json(output_root / "phase3_score_envelope.json", score_envelope)
    _write_json(output_root / "phase3_model_backed_trace_report.json", model_report)
    _write_json(output_root / "phase3_tooling_mechanism_report.json", tooling_report)
    _write_json(output_root / "phase3_receipt_attribution_report.json", receipt_report)
    _write_json(output_root / "phase3_cost_report.json", cost_report)
    _write_json(output_root / "phase3_failure_source_report.json", failure_report)
    _write_json(output_root / "phase3_recommendations.json", recommendation)
    _write_text(output_root / "phase3_handoff.md", _handoff(recommendation, score_envelope, output_root))

    return {
        "output_dir": str(output_root),
        "run_count": len(records),
        "selected_recommendation": recommendation["selected_recommendation"],
        "phase3_recommendations": str(output_root / "phase3_recommendations.json"),
    }


def _mission_plan(output_root: Path) -> str:
    return "\n".join(
        [
            "# Phase 3 Confirmation Mission Plan",
            "",
            f"- mission_id: `{MISSION_ID}`",
            f"- output_root: `{output_root}`",
            f"- baseline/control: `{SPB_VARIANT_ID}`",
            f"- combined seed: `{SEED_VARIANT_ID}`",
            f"- route_scope: `{PACKET06_PHASE2_ENV_TOOLING_SCOPE}`",
            "- authority: no Packet 07, transfer, benchmark widening, RHv1 unfreeze, env_snapshot admission, or broad candidate admission.",
            "",
        ]
    )


def _board_manifest() -> dict[str, Any]:
    return {
        "mission_id": MISSION_ID,
        "status": "accepted_route_repaired_execution",
        "baseline_control": SPB_VARIANT_ID,
        "frozen_non_promotional": ["rhv1_ref_01"],
        "forbidden": [
            "packet_07",
            "transfer",
            "benchmark_widening",
            "rhv1_unfreeze",
            "broad_candidate_admission",
            "env_snapshot_tool",
            "multi_agent_dag_orchestration",
        ],
        "active_eval_homes": [
            {"eval_id": TOOLCHAIN_EVAL_ID, "role": "required_toolchain_home"},
            {"eval_id": ARTIFACT_LOG_EVAL_ID, "role": "required_artifact_log_home"},
        ],
        "variants": [
            {"variant_id": SPB_VARIANT_ID, "role": "baseline_control"},
            {"variant_id": TOOLCHAIN_VARIANT_ID, "role": "component_tool_call_classifier"},
            {"variant_id": RECEIPT_VARIANT_ID, "role": "component_receipt_attribution"},
            {"variant_id": SEED_VARIANT_ID, "role": "bounded_combined_seed"},
        ],
        "run_budget": {"target_min": 24, "target_max": 40, "hard_cap": 60},
    }


def _route_matrix(board_manifest: dict[str, Any]) -> dict[str, Any]:
    baseline = build_packet04_route_manifest(BASELINE_VARIANT_ID, scope=PACKET06_PHASE2_ENV_TOOLING_SCOPE)
    rows = []
    for row in board_manifest["variants"]:
        manifest = build_packet04_route_manifest(row["variant_id"], scope=PACKET06_PHASE2_ENV_TOOLING_SCOPE)
        load_runtime_callables(manifest)
        validate_independent_candidate_routing(candidate_manifest=manifest, baseline_manifest=baseline)
        rows.append(
            {
                "variant_id": row["variant_id"],
                "role": row["role"],
                "route_scope": manifest["route_scope"],
                "route_manifest_fingerprint": manifest["route_manifest_fingerprint"],
                "changed_runtime_keys": [
                    item["runtime_key"] for item in manifest["routed_modules"] if item.get("claimed_changed_surface")
                ],
            }
        )
    return {"mission_id": MISSION_ID, "routes": rows}


def _execution_plan(output_root: Path) -> dict[str, Any]:
    common = {
        "packet_stage": "packet_04",
        "packet04_route_scope": PACKET06_PHASE2_ENV_TOOLING_SCOPE,
        "eval_family": "packet_06_phase3_confirmation",
        "task_tier": "project_diagnostic",
        "rerun_count": 3,
        "model_policy": {
            "screening_default": "azure:gpt-5.3-codex",
            "screening_fallback": "azure:gpt-5.3-codex",
            "promotion_tier": "azure:gpt-5.3-codex",
        },
        "provider_route": "openai_api",
        "model_tier_selector": "screening_default",
        "budget_caps": {"run_count": 60, "tokens": 600000, "usd": 120.0},
        "stability_budget_caps": {"run_count": 60, "tokens": 600000, "usd": 120.0},
        "output_root": str(output_root),
        "evaluation_lane": "promotion",
        "claim_route_id": "cr_successor_phase3_confirmation",
        "task_intent": "phase3_model_backed_tooling_confirmation",
    }
    variants = [SPB_VARIANT_ID, TOOLCHAIN_VARIANT_ID, RECEIPT_VARIANT_ID, SEED_VARIANT_ID]
    return {
        "mission_id": MISSION_ID,
        "batch_specs": [
            {
                **common,
                "batch_id": "phase3_toolchain_dependency_pressure_api",
                "eval_ids": [TOOLCHAIN_EVAL_ID],
                "variant_ids": variants,
                "task_set_id": "phase3_toolchain_dependency_pressure",
                "fixed_invariants": {
                    "comparator_variant_id": SPB_VARIANT_ID,
                    "packet04_route_scope": PACKET06_PHASE2_ENV_TOOLING_SCOPE,
                    "provider_route": "openai_api",
                },
                "execution_mode_lock": {TOOLCHAIN_EVAL_ID: "multistep_batchable"},
                "eval_card_refs": {TOOLCHAIN_EVAL_ID: f"active:{TOOLCHAIN_EVAL_ID}"},
                "task_cases": [
                    {
                        "task_id": "phase3_toolchain_dependency_pressure",
                        "task_prompt": "Phase3 model-backed toolchain dependency pressure probe",
                    }
                ],
            },
            {
                **common,
                "batch_id": "phase3_artifact_log_extraction_api",
                "eval_ids": [ARTIFACT_LOG_EVAL_ID],
                "variant_ids": variants,
                "task_set_id": "phase3_artifact_log_extraction",
                "fixed_invariants": {
                    "comparator_variant_id": SPB_VARIANT_ID,
                    "packet04_route_scope": PACKET06_PHASE2_ENV_TOOLING_SCOPE,
                    "provider_route": "openai_api",
                },
                "execution_mode_lock": {ARTIFACT_LOG_EVAL_ID: "multistep_batchable"},
                "eval_card_refs": {ARTIFACT_LOG_EVAL_ID: f"active:{ARTIFACT_LOG_EVAL_ID}"},
                "task_cases": [
                    {
                        "task_id": "phase3_artifact_log_extraction",
                        "task_prompt": "Phase3 model-backed artifact log extraction and receipt attribution probe",
                    }
                ],
            },
        ],
    }


def _model_backed_trace_report(records: list[dict[str, Any]], traces: list[dict[str, Any]]) -> dict[str, Any]:
    provider_routes = sorted({row.get("model_route", {}).get("provider_route") for row in records})
    non_local = [
        row for row in records if row.get("model_route", {}).get("provider_route") not in {"none", "local_stub", None}
    ]
    seed_traces = [row for row in traces if row.get("variant_id") == SEED_VARIANT_ID]
    return {
        "mission_id": MISSION_ID,
        "run_count": len(records),
        "provider_routes": provider_routes,
        "non_local_model_backed_run_count": len(non_local),
        "model_backed_requirement_met": bool(non_local) and len(non_local) == len(records),
        "seed_trace_count": len(seed_traces),
        "seed_tool_signal_observed": any(_trace_has_tool_signal(row) for row in seed_traces),
        "seed_receipt_signal_observed": any(_trace_has_receipt_signal(row) for row in seed_traces),
    }


def _variant_eval_report(records: list[dict[str, Any]], traces: list[dict[str, Any]], *, eval_id: str) -> dict[str, Any]:
    by_variant = {}
    for variant_id in (SPB_VARIANT_ID, TOOLCHAIN_VARIANT_ID, RECEIPT_VARIANT_ID, SEED_VARIANT_ID):
        rows = [row for row in records if row.get("eval_id") == eval_id and row.get("variant_id") == variant_id]
        verdicts = [row.get("score_summary", {}).get("final_verdict") for row in rows]
        trace_rows = [row for row in traces if row.get("eval_id") == eval_id and row.get("variant_id") == variant_id]
        by_variant[variant_id] = {
            "run_count": len(rows),
            "pass_count": sum(1 for verdict in verdicts if verdict == "pass"),
            "fail_count": sum(1 for verdict in verdicts if verdict == "fail"),
            "unresolved_count": sum(1 for verdict in verdicts if verdict == "unresolved"),
            "verdicts": verdicts,
            "tool_signal_observed": any(_trace_has_tool_signal(row) for row in trace_rows),
            "receipt_signal_observed": any(_trace_has_receipt_signal(row) for row in trace_rows),
        }
    return {
        "mission_id": MISSION_ID,
        "eval_id": eval_id,
        "baseline_control": SPB_VARIANT_ID,
        "seed_variant_id": SEED_VARIANT_ID,
        "by_variant": by_variant,
        "seed_pass_delta_vs_spb": by_variant[SEED_VARIANT_ID]["pass_count"] - by_variant[SPB_VARIANT_ID]["pass_count"],
    }


def _score_envelope(
    records: list[dict[str, Any]],
    model_report: dict[str, Any],
    tooling_report: dict[str, Any],
    receipt_report: dict[str, Any],
) -> dict[str, Any]:
    return {
        "mission_id": MISSION_ID,
        "run_count": len(records),
        "final_verdict_counts": _counts(row.get("score_summary", {}).get("final_verdict") for row in records),
        "model_backed_requirement_met": model_report["model_backed_requirement_met"],
        "seed_tooling_delta_vs_spb": tooling_report["seed_pass_delta_vs_spb"],
        "seed_receipt_delta_vs_spb": receipt_report["seed_pass_delta_vs_spb"],
        "seed_tool_signal_observed": model_report["seed_tool_signal_observed"],
        "seed_receipt_signal_observed": model_report["seed_receipt_signal_observed"],
    }


def _recommendation(
    score_envelope: dict[str, Any],
    model_report: dict[str, Any],
    cost_report: dict[str, Any],
    failure_report: dict[str, Any],
) -> dict[str, Any]:
    invalid_count = failure_report["invalid_run_count"]
    if invalid_count:
        selected = "repair_tooling_eval_board"
    elif not model_report["model_backed_requirement_met"]:
        selected = "defer_tooling_seed_no_model_backed_signal"
    elif score_envelope["seed_tooling_delta_vs_spb"] > 0 and score_envelope["seed_receipt_delta_vs_spb"] >= 0 and model_report["seed_tool_signal_observed"] and model_report["seed_receipt_signal_observed"]:
        selected = "confirm_spb_tooling_seed_for_candidate_assembly"
    elif score_envelope["seed_tooling_delta_vs_spb"] >= 0 and score_envelope["seed_receipt_delta_vs_spb"] >= 0:
        selected = "run_targeted_phase3_repair"
    else:
        selected = "prefer_spb_01_continue"
    return {
        "mission_id": MISSION_ID,
        "selected_recommendation": selected,
        "final_recommendation_options": sorted(FINAL_OPTIONS),
        "basis": {
            "score_envelope": score_envelope,
            "model_backed_requirement_met": model_report["model_backed_requirement_met"],
            "invalid_run_count": invalid_count,
            "total_usd": cost_report["total"]["usd"],
        },
        "authority_note": "No Packet 07, transfer, benchmark widening, RHv1 unfreeze, env_snapshot admission, or broad candidate admission is implied.",
    }


def _failure_source_report(records: list[dict[str, Any]]) -> dict[str, Any]:
    failures = [
        {
            "run_id": row.get("run_id"),
            "eval_id": row.get("eval_id"),
            "variant_id": row.get("variant_id"),
            "failure_cluster": row.get("failure_cluster"),
            "reason_codes": row.get("reason_codes", []),
        }
        for row in records
        if row.get("score_summary", {}).get("final_verdict") != "pass"
    ]
    invalid = [
        row for row in failures if "invalid" in str(row.get("failure_cluster", "")).lower()
        or "invalid" in " ".join(str(code) for code in row.get("reason_codes", []))
    ]
    return {"mission_id": MISSION_ID, "failure_count": len(failures), "invalid_run_count": len(invalid), "failures": failures}


def _cost_report(records: list[dict[str, Any]]) -> dict[str, Any]:
    total = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "usd": 0.0}
    by_variant: dict[str, dict[str, Any]] = {}
    for row in records:
        cost = row.get("token_and_cost_summary") or row.get("cost_summary") or {}
        variant_id = str(row.get("variant_id"))
        bucket = by_variant.setdefault(variant_id, {"run_count": 0, "total_tokens": 0, "usd": 0.0})
        bucket["run_count"] += 1
        bucket["total_tokens"] += int(cost.get("total_tokens", 0) or 0)
        bucket["usd"] += float(cost.get("usd", cost.get("usd_estimate", 0.0)) or 0.0)
        total["input_tokens"] += int(cost.get("input_tokens", 0) or 0)
        total["output_tokens"] += int(cost.get("output_tokens", cost.get("total_output_tokens", 0)) or 0)
        total["total_tokens"] += int(cost.get("total_tokens", 0) or 0)
        total["usd"] += float(cost.get("usd", cost.get("usd_estimate", 0.0)) or 0.0)
    return {"mission_id": MISSION_ID, "run_count": len(records), "total": total, "by_variant": by_variant}


def _trace_has_tool_signal(trace: dict[str, Any]) -> bool:
    payload = json.dumps(trace.get("packet03_eval_summary", {}), sort_keys=True)
    return "tool_call_contract_class" in payload or "toolchain_pressure" in payload


def _trace_has_receipt_signal(trace: dict[str, Any]) -> bool:
    payload = json.dumps(trace.get("packet03_eval_summary", {}), sort_keys=True)
    return "attribution_trace" in payload or "artifact_log" in payload or "receipt" in payload


def _counts(values: Any) -> dict[str, int]:
    out: dict[str, int] = {}
    for value in values:
        key = str(value)
        out[key] = out.get(key, 0) + 1
    return out


def _handoff(recommendation: dict[str, Any], score_envelope: dict[str, Any], output_root: Path) -> str:
    return "\n".join(
        [
            "# Phase 3 Confirmation Handoff",
            "",
            f"- mission_id: `{MISSION_ID}`",
            f"- output_root: `{output_root}`",
            f"- run_count: `{score_envelope['run_count']}`",
            f"- selected_recommendation: `{recommendation['selected_recommendation']}`",
            "- authority: no Packet 07, transfer, benchmark widening, RHv1 unfreeze, env_snapshot admission, or broad candidate admission.",
            "",
        ]
    )


def _load_eval_cards(path: Path) -> dict[str, dict[str, Any]]:
    cards = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            card = json.loads(line)
            cards[card["eval_id"]] = card
    missing = {TOOLCHAIN_EVAL_ID, ARTIFACT_LOG_EVAL_ID} - set(cards)
    if missing:
        raise ValueError(f"missing active eval cards: {sorted(missing)}")
    return cards


def _read_jsonl_many(paths: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        rows.extend(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    return rows


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--eval-cards-path", default=str(DEFAULT_EVAL_CARDS_PATH))
    args = parser.parse_args()
    result = launch_phase3_confirmation(output_dir=args.output_dir, eval_cards_path=args.eval_cards_path)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
