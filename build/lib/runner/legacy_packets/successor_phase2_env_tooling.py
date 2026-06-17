"""Launch the bounded successor Phase 2 environment/tooling mission."""

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
)
from runner.schemas import utc_now

DEFAULT_EVAL_CARDS_PATH = Path(
    "tracking/collab/stage_03_execution_planning/packets/packet_03_atomic_eval_families/outputs/eval_cards.active.jsonl"
)

MISSION_ID = "successor_phase2_env_tooling"
SPB_VARIANT_ID = "spb_01"
TOOLCHAIN_VARIANT_ID = "v04_tb_01_tool_call_contract_classifier"
RECEIPT_VARIANT_ID = "v04_tb_02_permission_runtime_attribution_split"
TOOLCHAIN_EVAL_ID = "ae_internal_toolchain_dependency_pressure_v1"
ARTIFACT_LOG_EVAL_ID = "ae_internal_artifact_log_extraction_v1"
FINAL_OPTIONS = {
    "proceed_to_phase3_confirmation",
    "run_targeted_mechanism_repair",
    "freeze_phase2_mechanism",
    "prefer_spb_01_control",
    "repair_phase2_eval_board",
}


def launch_phase2_env_tooling(
    *,
    output_dir: str | Path,
    eval_cards_path: str | Path = DEFAULT_EVAL_CARDS_PATH,
) -> dict[str, Any]:
    output_root = Path(output_dir).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    eval_cards = _load_eval_cards(Path(eval_cards_path))

    mission_plan = _mission_plan(output_root)
    _write_text(output_root / "phase2_mission_plan.md", mission_plan)

    board_manifest = _board_manifest()
    route_matrix = _route_matrix(board_manifest)
    execution_plan = _execution_plan(output_root)
    _write_json(output_root / "phase2_board_manifest.json", board_manifest)
    _write_json(output_root / "phase2_route_matrix.json", route_matrix)
    _write_json(output_root / "phase2_execution_plan.json", execution_plan)

    batch_results = []
    for batch_spec in execution_plan["batch_specs"]:
        result = run_batch(
            batch_spec=batch_spec,
            eval_cards={eval_id: eval_cards[eval_id] for eval_id in batch_spec["eval_ids"]},
        )
        batch_results.append(result)

    records = _read_jsonl_many([Path(result["result_records_path"]) for result in batch_results])
    traces = _read_jsonl_many([Path(result["trace_summaries_path"]) for result in batch_results])
    recommendations = [_read_json(Path(result["recommendations_path"])) for result in batch_results]
    _write_jsonl(output_root / "result_records.jsonl", records)

    run_manifest = {
        "mission_id": MISSION_ID,
        "launched_at_utc": utc_now(),
        "route_scope": PACKET06_PHASE2_ENV_TOOLING_SCOPE,
        "batch_results": batch_results,
        "run_count": len(records),
        "status": "executed",
    }
    _write_json(output_root / "phase2_run_manifest.json", run_manifest)

    tooling_report = _tooling_report(records, traces)
    env_snapshot_report = _env_snapshot_report(records, traces)
    receipt_report = _receipt_compression_report(records, traces)
    marker_report = _mechanism_marker_report(records, traces)
    delta_report = _ablation_delta_report(records)
    failure_report = _failure_source_report(records)
    cost_report = _cost_report(records)
    invalid_report = _invalid_run_report(records)
    final_recommendation = _final_recommendation(
        tooling_report=tooling_report,
        env_snapshot_report=env_snapshot_report,
        receipt_report=receipt_report,
        invalid_report=invalid_report,
        batch_recommendations=recommendations,
    )

    _write_json(output_root / "tooling_mechanism_report.json", tooling_report)
    _write_json(output_root / "env_snapshot_report.json", env_snapshot_report)
    _write_json(output_root / "receipt_compression_report.json", receipt_report)
    _write_json(output_root / "mechanism_marker_report.json", marker_report)
    _write_json(output_root / "ablation_delta_report.json", delta_report)
    _write_json(output_root / "failure_source_report.json", failure_report)
    _write_json(output_root / "cost_report.json", cost_report)
    _write_json(output_root / "invalid_run_report.json", invalid_report)
    _write_json(output_root / "recommendations.json", final_recommendation)
    _write_text(output_root / "phase2_handoff.md", _handoff(final_recommendation, run_manifest))

    return {
        "output_dir": str(output_root),
        "run_manifest": str(output_root / "phase2_run_manifest.json"),
        "recommendations": str(output_root / "recommendations.json"),
        "final_recommendation": final_recommendation["selected_recommendation"],
    }


def _mission_plan(output_root: Path) -> str:
    return "\n".join(
        [
            "# Phase 2 Env/Tooling Mission Plan",
            "",
            f"- mission_id: `{MISSION_ID}`",
            f"- output_root: `{output_root}`",
            f"- baseline/control: `{SPB_VARIANT_ID}`",
            "- authority: no Packet 07, transfer, benchmark widening, broad candidate admission, or RHv1 unfreeze",
            f"- primary home: `{TOOLCHAIN_EVAL_ID}`",
            f"- support home: `{ARTIFACT_LOG_EVAL_ID}`",
            f"- route_scope: `{PACKET06_PHASE2_ENV_TOOLING_SCOPE}`",
            "",
        ]
    )


def _board_manifest() -> dict[str, Any]:
    return {
        "mission_id": MISSION_ID,
        "status": "accepted_launched",
        "baseline_control": SPB_VARIANT_ID,
        "frozen_non_promotional": ["rhv1_ref_01"],
        "forbidden": ["packet_07", "transfer", "benchmark_widening", "broad_candidate_admission"],
        "active_eval_homes": [
            {"eval_id": TOOLCHAIN_EVAL_ID, "role": "primary_env_toolchain_home"},
            {"eval_id": ARTIFACT_LOG_EVAL_ID, "role": "support_artifact_log_home"},
        ],
        "variants": [
            {"variant_id": SPB_VARIANT_ID, "role": "baseline_control"},
            {"variant_id": TOOLCHAIN_VARIANT_ID, "role": "targeted_tooling_candidate"},
            {"variant_id": RECEIPT_VARIANT_ID, "role": "targeted_receipt_compression_candidate"},
        ],
    }


def _route_matrix(board_manifest: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for row in board_manifest["variants"]:
        manifest = build_packet04_route_manifest(row["variant_id"], scope=PACKET06_PHASE2_ENV_TOOLING_SCOPE)
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
        "eval_family": "packet_06_phase2_env_tooling",
        "task_tier": "project_diagnostic",
        "rerun_count": 2,
        "model_policy": {
            "screening_default": "no_model",
            "screening_fallback": "not_applicable",
            "promotion_tier": "not_applicable",
        },
        "provider_route": "local_stub",
        "budget_caps": {"run_count": 8, "tokens": 20000, "usd": 2.0},
        "stability_budget_caps": {"run_count": 8, "tokens": 20000, "usd": 2.0},
        "output_root": str(output_root),
        "evaluation_lane": "promotion",
        "claim_route_id": "cr_successor_phase2_env_tooling",
        "task_intent": "phase2_env_tooling_mechanism_test",
    }
    return {
        "mission_id": MISSION_ID,
        "batch_specs": [
            {
                **common,
                "batch_id": "phase2_toolchain_mechanism_local",
                "eval_ids": [TOOLCHAIN_EVAL_ID],
                "variant_ids": [SPB_VARIANT_ID, TOOLCHAIN_VARIANT_ID],
                "task_set_id": "phase2_toolchain_dependency_pressure",
                "fixed_invariants": {
                    "comparator_variant_id": SPB_VARIANT_ID,
                    "packet04_route_scope": PACKET06_PHASE2_ENV_TOOLING_SCOPE,
                },
                "execution_mode_lock": {TOOLCHAIN_EVAL_ID: "multistep_batchable"},
                "eval_card_refs": {TOOLCHAIN_EVAL_ID: f"active:{TOOLCHAIN_EVAL_ID}"},
                "task_cases": [
                    {
                        "task_id": "phase2_toolchain_dependency_pressure",
                        "task_prompt": "Phase2 toolchain dependency pressure local probe",
                    }
                ],
            },
            {
                **common,
                "batch_id": "phase2_receipt_compression_local",
                "eval_ids": [ARTIFACT_LOG_EVAL_ID],
                "variant_ids": [SPB_VARIANT_ID, RECEIPT_VARIANT_ID],
                "task_set_id": "phase2_artifact_log_receipt_compression",
                "fixed_invariants": {
                    "comparator_variant_id": SPB_VARIANT_ID,
                    "packet04_route_scope": PACKET06_PHASE2_ENV_TOOLING_SCOPE,
                },
                "execution_mode_lock": {ARTIFACT_LOG_EVAL_ID: "multistep_batchable"},
                "eval_card_refs": {ARTIFACT_LOG_EVAL_ID: f"active:{ARTIFACT_LOG_EVAL_ID}"},
                "task_cases": [
                    {
                        "task_id": "phase2_artifact_log_receipt_compression",
                        "task_prompt": "Phase2 artifact/log receipt compression local probe",
                    }
                ],
            },
        ],
    }


def _tooling_report(records: list[dict[str, Any]], traces: list[dict[str, Any]]) -> dict[str, Any]:
    return _variant_eval_report(records, traces, eval_id=TOOLCHAIN_EVAL_ID, candidate_id=TOOLCHAIN_VARIANT_ID)


def _env_snapshot_report(records: list[dict[str, Any]], traces: list[dict[str, Any]]) -> dict[str, Any]:
    report = _variant_eval_report(records, traces, eval_id=TOOLCHAIN_EVAL_ID, candidate_id=TOOLCHAIN_VARIANT_ID)
    report["mechanism_label"] = "env_snapshot_tool/workspace_env_map"
    report["status_note"] = "Executed via active environment/toolchain home; no broad candidate admission."
    return report


def _receipt_compression_report(records: list[dict[str, Any]], traces: list[dict[str, Any]]) -> dict[str, Any]:
    report = _variant_eval_report(records, traces, eval_id=ARTIFACT_LOG_EVAL_ID, candidate_id=RECEIPT_VARIANT_ID)
    report["mechanism_label"] = "tool-result classifier / receipt-based output compression"
    return report


def _variant_eval_report(
    records: list[dict[str, Any]],
    traces: list[dict[str, Any]],
    *,
    eval_id: str,
    candidate_id: str,
) -> dict[str, Any]:
    subset = [row for row in records if row.get("eval_id") == eval_id]
    by_variant = {}
    for variant_id in {SPB_VARIANT_ID, candidate_id}:
        rows = [row for row in subset if row.get("variant_id") == variant_id]
        verdicts = [row.get("score_summary", {}).get("final_verdict") for row in rows]
        by_variant[variant_id] = {
            "run_count": len(rows),
            "pass_count": sum(1 for verdict in verdicts if verdict == "pass"),
            "fail_count": sum(1 for verdict in verdicts if verdict == "fail"),
            "verdicts": verdicts,
        }
    trace_subset = [row for row in traces if row.get("eval_id") == eval_id and row.get("variant_id") == candidate_id]
    return {
        "eval_id": eval_id,
        "candidate_variant_id": candidate_id,
        "baseline_control": SPB_VARIANT_ID,
        "by_variant": by_variant,
        "candidate_trace_keys": sorted(
            {
                key
                for row in trace_subset
                for key in row.get("packet03_eval_summary", {}).keys()
                if isinstance(key, str)
            }
        ),
        "candidate_beats_spb": by_variant[candidate_id]["pass_count"] > by_variant[SPB_VARIANT_ID]["pass_count"],
    }


def _mechanism_marker_report(records: list[dict[str, Any]], traces: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "mission_id": MISSION_ID,
        "trace_count": len(traces),
        "mechanism_visibility_by_run": [
            {
                "run_id": row.get("run_id"),
                "eval_id": row.get("eval_id"),
                "variant_id": row.get("variant_id"),
                "mechanism_visibility_complete": row.get("packet03_eval_summary", {}).get(
                    "mechanism_visibility_complete"
                ),
                "schema_complete_for_promotion": row.get("packet03_eval_summary", {}).get(
                    "schema_complete_for_promotion"
                ),
            }
            for row in traces
        ],
        "result_count": len(records),
    }


def _ablation_delta_report(records: list[dict[str, Any]]) -> dict[str, Any]:
    deltas = []
    for eval_id, candidate_id in (
        (TOOLCHAIN_EVAL_ID, TOOLCHAIN_VARIANT_ID),
        (ARTIFACT_LOG_EVAL_ID, RECEIPT_VARIANT_ID),
    ):
        baseline_passes = _pass_count(records, eval_id=eval_id, variant_id=SPB_VARIANT_ID)
        candidate_passes = _pass_count(records, eval_id=eval_id, variant_id=candidate_id)
        deltas.append(
            {
                "eval_id": eval_id,
                "candidate_variant_id": candidate_id,
                "baseline_passes": baseline_passes,
                "candidate_passes": candidate_passes,
                "pass_delta_vs_spb": candidate_passes - baseline_passes,
            }
        )
    return {"mission_id": MISSION_ID, "deltas": deltas}


def _failure_source_report(records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "mission_id": MISSION_ID,
        "failures": [
            {
                "run_id": row.get("run_id"),
                "eval_id": row.get("eval_id"),
                "variant_id": row.get("variant_id"),
                "failure_cluster": row.get("failure_cluster"),
                "reason_codes": row.get("reason_codes", []),
            }
            for row in records
            if row.get("score_summary", {}).get("final_verdict") != "pass"
        ],
    }


def _cost_report(records: list[dict[str, Any]]) -> dict[str, Any]:
    total = {"input_tokens": 0, "output_tokens": 0, "usd": 0.0}
    for row in records:
        cost = row.get("cost_summary", {})
        total["input_tokens"] += int(cost.get("input_tokens", 0) or 0)
        total["output_tokens"] += int(cost.get("output_tokens", 0) or 0)
        total["usd"] += float(cost.get("usd_estimate", 0.0) or 0.0)
    return {"mission_id": MISSION_ID, "run_count": len(records), "total": total}


def _invalid_run_report(records: list[dict[str, Any]]) -> dict[str, Any]:
    invalid = [
        row
        for row in records
        if "invalid" in str(row.get("failure_cluster", "")).lower()
        or "invalid" in " ".join(str(code) for code in row.get("reason_codes", []))
    ]
    return {"mission_id": MISSION_ID, "invalid_run_count": len(invalid), "invalid_run_ids": [row["run_id"] for row in invalid]}


def _final_recommendation(
    *,
    tooling_report: dict[str, Any],
    env_snapshot_report: dict[str, Any],
    receipt_report: dict[str, Any],
    invalid_report: dict[str, Any],
    batch_recommendations: list[dict[str, Any]],
) -> dict[str, Any]:
    if invalid_report["invalid_run_count"]:
        selected = "repair_phase2_eval_board"
    elif tooling_report["candidate_beats_spb"] and receipt_report["candidate_beats_spb"]:
        selected = "proceed_to_phase3_confirmation"
    elif tooling_report["candidate_beats_spb"] or receipt_report["candidate_beats_spb"]:
        selected = "run_targeted_mechanism_repair"
    else:
        selected = "prefer_spb_01_control"
    if selected not in FINAL_OPTIONS:
        selected = "repair_phase2_eval_board"
    return {
        "mission_id": MISSION_ID,
        "selected_recommendation": selected,
        "final_recommendation_options": sorted(FINAL_OPTIONS),
        "basis": {
            "tooling_candidate_beats_spb": tooling_report["candidate_beats_spb"],
            "env_snapshot_candidate_beats_spb": env_snapshot_report["candidate_beats_spb"],
            "receipt_candidate_beats_spb": receipt_report["candidate_beats_spb"],
            "invalid_run_count": invalid_report["invalid_run_count"],
        },
        "batch_recommendation_refs": [
            recommendation.get("recommendation_id", recommendation.get("batch_id")) for recommendation in batch_recommendations
        ],
        "authority_note": "No Packet 07, transfer, benchmark widening, broad admission, or RHv1 unfreeze is implied.",
    }


def _handoff(recommendation: dict[str, Any], run_manifest: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Phase 2 Env/Tooling Handoff",
            "",
            f"- mission_id: `{MISSION_ID}`",
            f"- run_count: `{run_manifest['run_count']}`",
            f"- selected_recommendation: `{recommendation['selected_recommendation']}`",
            "- authority: no Packet 07, transfer, benchmark widening, broad candidate admission, or RHv1 unfreeze.",
            "",
        ]
    )


def _pass_count(records: list[dict[str, Any]], *, eval_id: str, variant_id: str) -> int:
    return sum(
        1
        for row in records
        if row.get("eval_id") == eval_id
        and row.get("variant_id") == variant_id
        and row.get("score_summary", {}).get("final_verdict") == "pass"
    )


def _load_eval_cards(path: Path) -> dict[str, dict[str, Any]]:
    cards = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        card = json.loads(line)
        cards[card["eval_id"]] = card
    missing = {TOOLCHAIN_EVAL_ID, ARTIFACT_LOG_EVAL_ID} - set(cards)
    if missing:
        raise ValueError(f"missing active eval cards: {sorted(missing)}")
    return cards


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


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
    result = launch_phase2_env_tooling(output_dir=args.output_dir, eval_cards_path=args.eval_cards_path)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
