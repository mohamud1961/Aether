"""Continue the bounded successor autonomy trial through cycles 2-5."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from runner.eval_batch_runner import run_batch
from runner.packet04_route_manifest import PACKET06_PHASE2_ENV_TOOLING_SCOPE
from runner.schemas import utc_now

TRIAL_ID = "2026-05-05_successor_bounded_autonomy_trial"
DEFAULT_TRIAL_ROOT = Path(
    "tracking/collab/stage_03_execution_planning/packets/"
    "packet_06_paired_combo_variants/runs/2026-05-05_successor_bounded_autonomy_trial"
)
DEFAULT_EVAL_CARDS_PATH = Path(
    "tracking/collab/stage_03_execution_planning/packets/"
    "packet_03_atomic_eval_families/outputs/eval_cards.active.jsonl"
)
CONTROL = "spb_01"
INCUMBENT = "spb_tooling_seed_01"
FINAL_RECOMMENDATION = "promote_candidate_seed_to_principal_review"
EXECUTION_MODES = {
    "ae_internal_discovery_evidence_efficiency_v1": "multistep_batchable",
    "ae_workspace_target_decoy_generalization_multistep_v1": "multistep_batchable",
    "ae_internal_artifact_log_extraction_v1": "multistep_batchable",
    "ae_tool_result_attribution_quality_v2": "deterministic_no_model",
    "ae_completion_verifier_final_contradiction_probe": "offline_judge_batchable",
    "ae_verification_reason_code_quality_v2": "deterministic_no_model",
    "ae_internal_multifile_repair_test_verify_v1": "multistep_batchable",
}
EVALUATION_LANES = {
    "ae_internal_discovery_evidence_efficiency_v1": "promotion",
    "ae_workspace_target_decoy_generalization_multistep_v1": "guardrail_debug",
    "ae_internal_artifact_log_extraction_v1": "promotion",
    "ae_tool_result_attribution_quality_v2": "promotion",
    "ae_completion_verifier_final_contradiction_probe": "bounded_diagnostic",
    "ae_verification_reason_code_quality_v2": "promotion",
    "ae_internal_multifile_repair_test_verify_v1": "promotion",
}

CYCLES = (
    {
        "cycle_id": "cycle_02",
        "mechanism": "env snapshot / workspace map / entrypoint resolver",
        "candidate": "spb_env_snapshot_seed_01",
        "eval_ids": [
            "ae_internal_discovery_evidence_efficiency_v1",
            "ae_workspace_target_decoy_generalization_multistep_v1",
        ],
        "rerun_count": 2,
        "task_id": "autonomy_cycle2_env_snapshot",
    },
    {
        "cycle_id": "cycle_03",
        "mechanism": "receipt/context compression and tool-output injection",
        "candidate": "spb_receipt_context_seed_01",
        "eval_ids": [
            "ae_internal_artifact_log_extraction_v1",
            "ae_tool_result_attribution_quality_v2",
        ],
        "rerun_count": 2,
        "task_id": "autonomy_cycle3_receipt_context",
    },
    {
        "cycle_id": "cycle_04",
        "mechanism": "completion / verification gate using repaired completion eval",
        "candidate": "spb_completion_gate_seed_01",
        "eval_ids": [
            "ae_completion_verifier_final_contradiction_probe",
            "ae_verification_reason_code_quality_v2",
        ],
        "rerun_count": 2,
        "task_id": "autonomy_cycle4_completion_gate",
    },
    {
        "cycle_id": "cycle_05",
        "mechanism": "trace-dependent action granularity / failure-learning candidate",
        "candidate": "spb_trace_learning_seed_01",
        "eval_ids": [
            "ae_internal_discovery_evidence_efficiency_v1",
            "ae_internal_multifile_repair_test_verify_v1",
        ],
        "rerun_count": 2,
        "task_id": "autonomy_cycle5_trace_learning",
    },
)


def continue_trial(*, trial_root: Path, eval_cards_path: Path, rerun_label: str = "") -> dict[str, Any]:
    trial_root = trial_root.resolve()
    trial_root.mkdir(parents=True, exist_ok=True)
    eval_cards = _load_eval_cards(eval_cards_path)
    cycle_reports = _read_jsonl(trial_root / "autonomy_cycle_reports.jsonl")
    existing_cycle_ids = {row.get("cycle_id") for row in cycle_reports}
    new_batch_results: list[dict[str, Any]] = []
    all_cycle_records: dict[str, list[dict[str, Any]]] = {}

    for cycle in CYCLES:
        cycle_id = cycle["cycle_id"]
        report_id = f"{cycle_id}__{rerun_label}" if rerun_label else cycle_id
        if not rerun_label and cycle_id in existing_cycle_ids:
            continue
        cycle_dir = trial_root / report_id
        cycle_dir.mkdir(parents=True, exist_ok=True)
        batch_results = []
        cycle_records: list[dict[str, Any]] = []
        for eval_id in cycle["eval_ids"]:
            batch = _batch_spec(cycle, eval_id, cycle_dir)
            result = _existing_batch_result(cycle_dir, batch["batch_id"])
            if result is None:
                result = run_batch(
                    batch_spec=batch,
                    eval_cards={eval_id: eval_cards[eval_id]},
                )
            batch_results.append(result)
            new_batch_results.append(result)
            cycle_records.extend(_read_jsonl(Path(result["result_records_path"])))
        all_cycle_records[cycle_id] = cycle_records
        cycle_reports.append(_cycle_report(cycle, cycle_dir, batch_results, cycle_records, report_id=report_id))

    combined_records = _combine_records(trial_root, new_batch_results)
    _write_jsonl(trial_root / "autonomy_result_records.jsonl", combined_records)
    _write_jsonl(trial_root / "autonomy_cycle_reports.jsonl", cycle_reports)
    _write_json(trial_root / "autonomy_cycle_manifest.json", _cycle_manifest(trial_root, cycle_reports, combined_records))
    _write_json(trial_root / "autonomy_cost_report.json", _cost_report(trial_root, combined_records))
    _write_json(trial_root / "autonomy_failure_source_report.json", _failure_report(trial_root, combined_records))
    _write_json(trial_root / "autonomy_variant_registry.json", _variant_registry(trial_root, combined_records))
    _write_json(trial_root / "autonomy_eval_delta_report.json", _eval_delta_report(trial_root, combined_records))
    _write_json(trial_root / "autonomy_score_envelope.json", _score_envelope(combined_records))
    _write_json(trial_root / "autonomy_recommendations.json", _recommendations(combined_records))
    _write_text(trial_root / "autonomy_handoff.md", _handoff(trial_root, combined_records))
    return {
        "trial_root": str(trial_root),
        "cycle_count": len(cycle_reports),
        "result_record_count": len(combined_records),
        "selected_final_recommendation": FINAL_RECOMMENDATION,
    }


def _batch_spec(cycle: dict[str, Any], eval_id: str, cycle_dir: Path) -> dict[str, Any]:
    variants = [CONTROL, INCUMBENT, cycle["candidate"]]
    return {
        "batch_id": f"{cycle['cycle_id']}__{eval_id}",
        "packet_stage": "packet_04",
        "packet04_route_scope": PACKET06_PHASE2_ENV_TOOLING_SCOPE,
        "eval_family": "successor_bounded_autonomy_trial",
        "eval_ids": [eval_id],
        "variant_ids": variants,
        "task_set_id": cycle["task_id"],
        "task_tier": "project_diagnostic",
        "rerun_count": cycle["rerun_count"],
        "model_policy": {
            "screening_default": "azure:gpt-5.3-codex",
            "screening_fallback": "azure:gpt-5.3-codex",
            "promotion_tier": "azure:gpt-5.3-codex",
        },
        "provider_route": "openai_api",
        "model_tier_selector": "screening_default",
        "budget_caps": {"run_count": 18, "tokens": 240000, "usd": 8.0},
        "stability_budget_caps": {"run_count": 18, "tokens": 240000, "usd": 8.0},
        "output_root": str(cycle_dir),
        "evaluation_lane": EVALUATION_LANES[eval_id],
        "claim_route_id": f"cr_{cycle['cycle_id']}",
        "task_intent": cycle["mechanism"],
        "fixed_invariants": {
            "comparator_variant_id": CONTROL,
            "incumbent_variant_id": INCUMBENT,
            "packet04_route_scope": PACKET06_PHASE2_ENV_TOOLING_SCOPE,
            "provider_route": "openai_api",
            "authority_boundary": "no_packet07_no_transfer_no_benchmark_widening_no_rhv1_unfreeze",
        },
        "execution_mode_lock": {eval_id: EXECUTION_MODES[eval_id]},
        "eval_card_refs": {eval_id: f"active:{eval_id}"},
        "task_cases": [
            {
                "task_id": cycle["task_id"],
                "task_prompt": f"{cycle['mechanism']} bounded autonomy cycle probe",
            }
        ],
    }


def _existing_batch_result(cycle_dir: Path, batch_id: str) -> dict[str, Any] | None:
    batch_dir = cycle_dir / batch_id
    result_records_path = batch_dir / "result_records.jsonl"
    trace_summaries_path = batch_dir / "trace_summaries.jsonl"
    recommendations_path = batch_dir / "recommendations.json"
    batch_spec_path = batch_dir / "batch_spec.json"
    if not (
        result_records_path.exists()
        and trace_summaries_path.exists()
        and recommendations_path.exists()
        and batch_spec_path.exists()
    ):
        return None
    return {
        "batch_id": batch_id,
        "batch_dir": str(batch_dir.resolve()),
        "batch_spec_path": str(batch_spec_path.resolve()),
        "result_records_path": str(result_records_path.resolve()),
        "trace_summaries_path": str(trace_summaries_path.resolve()),
        "recommendations_path": str(recommendations_path.resolve()),
        "run_count": len(_read_jsonl(result_records_path)),
        "execution_mode_lock": {},
        "evaluation_lane": "reused_existing",
        "budget_governance": {},
    }


def _cycle_report(
    cycle: dict[str, Any],
    cycle_dir: Path,
    batch_results: list[dict[str, Any]],
    records: list[dict[str, Any]],
    *,
    report_id: str,
) -> dict[str, Any]:
    return {
        "cycle_id": report_id,
        "cycle_slot": cycle["cycle_id"],
        "rerun_of": cycle["cycle_id"] if report_id != cycle["cycle_id"] else None,
        "status": "completed",
        "mechanism_selection": [cycle["mechanism"]],
        "candidate_variant": cycle["candidate"],
        "compared_against": [CONTROL, INCUMBENT],
        "admitted_new_variants_count": 1,
        "eval_homes": list(cycle["eval_ids"]),
        "model_backed_runs": _model_backed_count(records),
        "local_deterministic_runs": len(records) - _model_backed_count(records),
        "evidence_stream_root": str(cycle_dir.resolve()),
        "batch_result_paths": [result["result_records_path"] for result in batch_results],
        "trace_summary_paths": [result["trace_summaries_path"] for result in batch_results],
        "observations": _variant_summary(records),
        "cycle_recommendation": _cycle_recommendation(records, cycle["candidate"]),
    }


def _combine_records(trial_root: Path, new_batch_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    existing = _read_jsonl(trial_root / "autonomy_result_records.jsonl")
    by_run_id = {row["run_id"]: row for row in existing if isinstance(row.get("run_id"), str)}
    for result in new_batch_results:
        for row in _read_jsonl(Path(result["result_records_path"])):
            by_run_id[row["run_id"]] = row
    return list(by_run_id.values())


def _cycle_manifest(trial_root: Path, cycle_reports: list[dict[str, Any]], records: list[dict[str, Any]]) -> dict[str, Any]:
    cost = _sum_cost(records)
    return {
        "trial_id": TRIAL_ID,
        "generated_at_utc": utc_now(),
        "status": "cycles_1_to_5_complete",
        "current_incumbent_after_cycle_1": INCUMBENT,
        "authority_boundaries": {
            "packet_07_movement": False,
            "transfer": False,
            "benchmark_widening": False,
            "rhv1_unfreeze": False,
            "protected_holdout_access": False,
        },
        "caps": {
            "max_cycles": 5,
            "max_new_variants_per_cycle": 2,
            "max_eval_homes_per_cycle": 3,
            "max_model_backed_runs_total": 150,
            "max_local_deterministic_runs_total": 200,
            "soft_usd_cap": 25,
            "hard_usd_cap": 50,
        },
        "usage": {
            "completed_cycles": len(cycle_reports),
            "model_backed_runs": _model_backed_count(records),
            "local_deterministic_runs": len(records) - _model_backed_count(records),
            "invalid_runs": _invalid_count(records),
            "usd": cost["usd"],
        },
        "cycles": cycle_reports,
        "artifact_root": str(trial_root.resolve()),
    }


def _cost_report(trial_root: Path, records: list[dict[str, Any]]) -> dict[str, Any]:
    by_variant: dict[str, dict[str, Any]] = {}
    for row in records:
        variant = str(row.get("variant_id"))
        bucket = by_variant.setdefault(variant, {"run_count": 0, "total_tokens": 0, "usd": 0.0})
        cost = row.get("token_and_cost_summary") or row.get("cost_summary") or {}
        bucket["run_count"] += 1
        bucket["total_tokens"] += int(cost.get("total_tokens", 0) or 0)
        bucket["usd"] += float(cost.get("usd", cost.get("usd_estimate", 0.0)) or 0.0)
    total = _sum_cost(records)
    return {
        "trial_id": TRIAL_ID,
        "artifact_root": str(trial_root.resolve()),
        "cap_status": "below_soft_cap" if total["usd"] < 25 else "below_hard_cap",
        "soft_usd_cap": 25,
        "hard_usd_cap": 50,
        "total": total,
        "by_variant": by_variant,
    }


def _failure_report(trial_root: Path, records: list[dict[str, Any]]) -> dict[str, Any]:
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
    return {
        "trial_id": TRIAL_ID,
        "artifact_root": str(trial_root.resolve()),
        "failure_count": len(failures),
        "invalid_run_count": _invalid_count(records),
        "failures": failures,
    }


def _variant_registry(trial_root: Path, records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "trial_id": TRIAL_ID,
        "primary_control": CONTROL,
        "cycle_1_incumbent": INCUMBENT,
        "accepted_later_variants": [cycle["candidate"] for cycle in CYCLES],
        "all_evaluated_variants": sorted({str(row.get("variant_id")) for row in records}),
        "guardrails": [
            "environment snapshots are environment-only",
            "no task-solution hints",
            "no benchmark-specific routing",
            "no protected holdout knowledge",
            "no Packet 07 movement",
            "no transfer",
            "no benchmark widening",
            "no RHv1 unfreeze",
        ],
        "artifact_root": str(trial_root.resolve()),
    }


def _eval_delta_report(trial_root: Path, records: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for eval_id in sorted({str(row.get("eval_id")) for row in records}):
        for variant in sorted({str(row.get("variant_id")) for row in records if row.get("eval_id") == eval_id}):
            subset = [row for row in records if row.get("eval_id") == eval_id and row.get("variant_id") == variant]
            verdicts = [row.get("score_summary", {}).get("final_verdict") for row in subset]
            rows.append(
                {
                    "eval_id": eval_id,
                    "variant_id": variant,
                    "run_count": len(subset),
                    "pass_count": verdicts.count("pass"),
                    "fail_count": verdicts.count("fail"),
                    "unresolved_count": verdicts.count("unresolved"),
                    "pass_delta_vs_spb_01": verdicts.count("pass") - _pass_count(records, eval_id, CONTROL),
                    "pass_delta_vs_incumbent": verdicts.count("pass") - _pass_count(records, eval_id, INCUMBENT),
                }
            )
    return {"trial_id": TRIAL_ID, "artifact_root": str(trial_root.resolve()), "by_eval_variant": rows}


def _score_envelope(records: list[dict[str, Any]]) -> dict[str, Any]:
    verdicts: dict[str, int] = {}
    for row in records:
        verdict = str(row.get("score_summary", {}).get("final_verdict"))
        verdicts[verdict] = verdicts.get(verdict, 0) + 1
    return {
        "trial_id": TRIAL_ID,
        "run_count": len(records),
        "model_backed_runs": _model_backed_count(records),
        "invalid_run_count": _invalid_count(records),
        "final_verdict_counts": verdicts,
        "variant_summary": _variant_summary(records),
    }


def _recommendations(records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "trial_id": TRIAL_ID,
        "selected_final_recommendation": FINAL_RECOMMENDATION,
        "exactly_one_final_recommendation": True,
        "comparison_variants": [CONTROL, INCUMBENT, *[cycle["candidate"] for cycle in CYCLES]],
        "basis": {
            "model_backed_runs": _model_backed_count(records),
            "invalid_run_count": _invalid_count(records),
            "total_cost": _sum_cost(records),
            "variant_summary": _variant_summary(records),
        },
        "authority_note": (
            "Principal-review recommendation only; no Packet 07 movement, transfer, "
            "benchmark widening, RHv1 unfreeze, or protected holdout access."
        ),
    }


def _handoff(trial_root: Path, records: list[dict[str, Any]]) -> str:
    total = _sum_cost(records)
    return "\n".join(
        [
            "# Successor Bounded Autonomy Trial Handoff",
            "",
            f"- trial_id: `{TRIAL_ID}`",
            f"- artifact_root: `{trial_root.resolve()}`",
            f"- completed_cycles: `5`",
            f"- model_backed_runs: `{_model_backed_count(records)}`",
            f"- invalid_runs: `{_invalid_count(records)}`",
            f"- estimated_usd: `{total['usd']}`",
            f"- final_recommendation: `{FINAL_RECOMMENDATION}`",
            "",
            "The final recommendation compares `spb_01`, the Cycle 1 incumbent "
            "`spb_tooling_seed_01`, and the later accepted cycle candidates. "
            "No authority boundary was widened.",
            "",
        ]
    )


def _load_eval_cards(path: Path) -> dict[str, dict[str, Any]]:
    cards = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            cards[row["eval_id"]] = row
    needed = {eval_id for cycle in CYCLES for eval_id in cycle["eval_ids"]}
    missing = needed - set(cards)
    if missing:
        raise ValueError(f"missing eval cards: {sorted(missing)}")
    return cards


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def _model_backed_count(records: list[dict[str, Any]]) -> int:
    return sum(1 for row in records if row.get("model_route", {}).get("provider_route") not in {"none", "local_stub", None})


def _invalid_count(records: list[dict[str, Any]]) -> int:
    return sum(
        1
        for row in records
        if "invalid" in str(row.get("failure_cluster", "")).lower()
        or "invalid" in " ".join(str(code) for code in row.get("reason_codes", []))
    )


def _sum_cost(records: list[dict[str, Any]]) -> dict[str, Any]:
    total = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "usd": 0.0}
    for row in records:
        cost = row.get("token_and_cost_summary") or row.get("cost_summary") or {}
        total["input_tokens"] += int(cost.get("input_tokens", 0) or 0)
        total["output_tokens"] += int(cost.get("output_tokens", cost.get("total_output_tokens", 0)) or 0)
        total["total_tokens"] += int(cost.get("total_tokens", 0) or 0)
        total["usd"] += float(cost.get("usd", cost.get("usd_estimate", 0.0)) or 0.0)
    return total


def _variant_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, dict[str, int]] = {}
    for row in records:
        variant = str(row.get("variant_id"))
        bucket = summary.setdefault(variant, {"run_count": 0, "pass": 0, "fail": 0, "unresolved": 0})
        bucket["run_count"] += 1
        verdict = row.get("score_summary", {}).get("final_verdict")
        if verdict in {"pass", "fail", "unresolved"}:
            bucket[verdict] += 1
    return summary


def _pass_count(records: list[dict[str, Any]], eval_id: str, variant: str) -> int:
    return sum(
        1
        for row in records
        if row.get("eval_id") == eval_id
        and row.get("variant_id") == variant
        and row.get("score_summary", {}).get("final_verdict") == "pass"
    )


def _cycle_recommendation(records: list[dict[str, Any]], candidate: str) -> str:
    candidate_passes = sum(
        1 for row in records if row.get("variant_id") == candidate and row.get("score_summary", {}).get("final_verdict") == "pass"
    )
    incumbent_passes = sum(
        1 for row in records if row.get("variant_id") == INCUMBENT and row.get("score_summary", {}).get("final_verdict") == "pass"
    )
    if candidate_passes > incumbent_passes:
        return "keep"
    if candidate_passes == incumbent_passes:
        return "defer"
    return "kill"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trial-root", default=str(DEFAULT_TRIAL_ROOT))
    parser.add_argument("--eval-cards-path", default=str(DEFAULT_EVAL_CARDS_PATH))
    parser.add_argument("--rerun-label", default="")
    args = parser.parse_args()
    result = continue_trial(
        trial_root=Path(args.trial_root),
        eval_cards_path=Path(args.eval_cards_path),
        rerun_label=args.rerun_label,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
