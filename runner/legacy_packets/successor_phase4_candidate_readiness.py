"""Execute Phase 4 candidate-readiness and challenger-gauntlet board."""

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
    "tracking/collab/stage_03_execution_planning/packets/"
    "packet_03_atomic_eval_families/outputs/eval_cards.active.jsonl"
)

MISSION_ID = "successor_phase4_candidate_readiness_challenger_gauntlet"
CONTROL = "spb_01"
INCUMBENT = "spb_tooling_seed_01"
REQUIRED_CHALLENGERS = (
    "spb_tooling_seed_plus_receipt_context_01",
    "spb_tooling_seed_plus_completion_gate_01",
    "spb_tooling_seed_plus_receipt_and_completion_01",
)
OPTIONAL_CHEAP_CHALLENGERS = ("spb_trace_learning_seed_01",)
FINAL_OPTIONS = {
    "accept_candidate_seed_for_packet07_readiness_review",
    "accept_combined_seed_for_packet07_readiness_review",
    "run_one_targeted_repair_before_packet07_review",
    "keep_as_tooling_only_seed",
    "prefer_spb_01_baseline",
    "repair_eval_board_before_candidate_review",
}
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
LANES = {
    "ae_completion_verifier_final_contradiction_probe": "bounded_diagnostic",
}


def launch_phase4(
    *,
    output_dir: str | Path,
    eval_cards_path: str | Path = DEFAULT_EVAL_CARDS_PATH,
    rerun_count: int = 6,
    include_optional_trace_learning: bool = False,
) -> dict[str, Any]:
    output_root = Path(output_dir).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    eval_cards = _load_eval_cards(Path(eval_cards_path))

    variants = [CONTROL, INCUMBENT, *REQUIRED_CHALLENGERS]
    if include_optional_trace_learning:
        variants.extend(OPTIONAL_CHEAP_CHALLENGERS)
    _write_text(output_root / "candidate_readiness_plan.md", _plan(output_root, variants, rerun_count))
    board = _board_manifest(
        variants,
        rerun_count,
        include_optional_trace_learning=include_optional_trace_learning,
    )
    route_matrix = _route_matrix(variants)
    execution_plan = _execution_plan(output_root, variants, rerun_count)
    _write_json(output_root / "candidate_readiness_board_manifest.json", board)
    _write_json(output_root / "candidate_readiness_route_matrix.json", route_matrix)
    _write_json(output_root / "candidate_readiness_execution_plan.json", execution_plan)

    if route_matrix["status"] != "pass":
        return _write_blocked_outputs(output_root, route_matrix)

    batch_results = []
    for batch in execution_plan["batch_specs"]:
        result = run_batch(
            batch_spec=batch,
            eval_cards={eval_id: eval_cards[eval_id] for eval_id in batch["eval_ids"]},
        )
        batch_results.append(result)

    records = _read_jsonl_many([Path(result["result_records_path"]) for result in batch_results])
    traces = _read_jsonl_many([Path(result["trace_summaries_path"]) for result in batch_results])
    _write_jsonl(output_root / "candidate_readiness_result_records.jsonl", records)

    trace_report = _trace_report(records, traces)
    ablation_report = _ablation_report(records)
    generalization_report = _generalization_report(records)
    completion_report = _completion_report(records, traces)
    cost_report = _cost_report(records)
    failure_report = _failure_source_report(records)
    score_envelope = _score_envelope(records)
    recommendation = _recommendation(score_envelope, cost_report, failure_report)

    _write_json(output_root / "candidate_readiness_score_envelope.json", score_envelope)
    _write_json(output_root / "candidate_readiness_trace_report.json", trace_report)
    _write_json(output_root / "candidate_readiness_ablation_report.json", ablation_report)
    _write_json(output_root / "candidate_readiness_generalization_report.json", generalization_report)
    _write_json(output_root / "candidate_readiness_completion_report.json", completion_report)
    _write_json(output_root / "candidate_readiness_cost_report.json", cost_report)
    _write_json(output_root / "candidate_readiness_failure_source_report.json", failure_report)
    _write_json(output_root / "candidate_readiness_recommendations.json", recommendation)
    _write_text(output_root / "candidate_readiness_handoff.md", _handoff(output_root, score_envelope, recommendation))
    return {
        "output_dir": str(output_root),
        "run_count": len(records),
        "model_backed_runs": score_envelope["model_backed_runs"],
        "selected_recommendation": recommendation["selected_recommendation"],
    }


def _board_manifest(
    variants: list[str],
    rerun_count: int,
    *,
    include_optional_trace_learning: bool,
) -> dict[str, Any]:
    return {
        "mission_id": MISSION_ID,
        "generated_at_utc": utc_now(),
        "status": "contracts_pass_execution_ready",
        "control": CONTROL,
        "incumbent": INCUMBENT,
        "required_challengers": list(REQUIRED_CHALLENGERS),
        "included_optional_challengers": list(OPTIONAL_CHEAP_CHALLENGERS)
        if include_optional_trace_learning
        else [],
        "eval_homes": list(REQUIRED_EVALS),
        "variants": variants,
        "rerun_count": rerun_count,
        "authority_boundaries": _authority_boundaries(),
        "run_budget": _budget_caps(),
    }


def _route_matrix(variants: list[str]) -> dict[str, Any]:
    baseline = build_packet04_route_manifest(BASELINE_VARIANT_ID, scope=PACKET06_PHASE2_ENV_TOOLING_SCOPE)
    rows = []
    blockers = []
    for variant in variants:
        try:
            manifest = build_packet04_route_manifest(variant, scope=PACKET06_PHASE2_ENV_TOOLING_SCOPE)
            load_runtime_callables(manifest)
            validate_independent_candidate_routing(candidate_manifest=manifest, baseline_manifest=baseline)
            changed = [row["runtime_key"] for row in manifest["routed_modules"] if row.get("claimed_changed_surface")]
            rows.append(
                {
                    "variant_id": variant,
                    "route_valid": True,
                    "route_scope": manifest["route_scope"],
                    "route_manifest_fingerprint": manifest["route_manifest_fingerprint"],
                    "changed_runtime_keys": changed,
                }
            )
        except Exception as exc:  # pragma: no cover - surfaced in artifact.
            blockers.append({"variant_id": variant, "error": str(exc)})
            rows.append({"variant_id": variant, "route_valid": False, "error": str(exc)})
    return {
        "mission_id": MISSION_ID,
        "route_scope": PACKET06_PHASE2_ENV_TOOLING_SCOPE,
        "status": "pass" if not blockers else "blocked",
        "routes": rows,
        "blockers": blockers,
    }


def _execution_plan(output_root: Path, variants: list[str], rerun_count: int) -> dict[str, Any]:
    common = {
        "packet_stage": "packet_04",
        "packet04_route_scope": PACKET06_PHASE2_ENV_TOOLING_SCOPE,
        "eval_family": MISSION_ID,
        "task_tier": "project_diagnostic",
        "rerun_count": rerun_count,
        "model_policy": {
            "screening_default": "azure:gpt-5.3-codex",
            "screening_fallback": "azure:gpt-5.3-codex",
            "promotion_tier": "azure:gpt-5.3-codex",
        },
        "provider_route": "openai_api",
        "model_tier_selector": "screening_default",
        "budget_caps": {"run_count": 60, "tokens": 750000, "usd": 30.0},
        "stability_budget_caps": {"run_count": 60, "tokens": 750000, "usd": 30.0},
        "output_root": str(output_root),
        "claim_route_id": "cr_successor_phase4_candidate_readiness",
        "fixed_invariants": {
            "comparator_variant_id": CONTROL,
            "incumbent_variant_id": INCUMBENT,
            "packet04_route_scope": PACKET06_PHASE2_ENV_TOOLING_SCOPE,
            "provider_route": "openai_api",
            "authority_boundary": "no_packet07_no_transfer_no_benchmark_widening_no_rhv1_unfreeze_no_holdouts",
        },
    }
    specs = []
    for eval_id in REQUIRED_EVALS:
        specs.append(
            {
                **common,
                "batch_id": f"phase4__{eval_id}",
                "eval_ids": [eval_id],
                "variant_ids": variants,
                "task_set_id": f"phase4_{eval_id}",
                "task_intent": f"phase4_candidate_readiness_{eval_id}",
                "evaluation_lane": LANES.get(eval_id, "promotion"),
                "execution_mode_lock": {eval_id: EXECUTION_MODES[eval_id]},
                "eval_card_refs": {eval_id: f"active:{eval_id}"},
                "task_cases": [
                    {
                        "task_id": f"phase4_{eval_id}",
                        "task_prompt": f"Phase4 candidate readiness gauntlet probe for {eval_id}",
                    }
                ],
            }
        )
    return {
        "mission_id": MISSION_ID,
        "planned_run_count": len(specs) * len(variants) * rerun_count,
        "planned_model_backed_runs": 4 * len(variants) * rerun_count,
        "batch_specs": specs,
    }


def _score_envelope(records: list[dict[str, Any]]) -> dict[str, Any]:
    by_variant = _variant_summary(records)
    return {
        "mission_id": MISSION_ID,
        "run_count": len(records),
        "model_backed_runs": _model_backed_count(records),
        "local_deterministic_runs": len(records) - _model_backed_count(records),
        "invalid_run_count": _invalid_count(records),
        "final_verdict_counts": _counts(row.get("score_summary", {}).get("final_verdict") for row in records),
        "variant_summary": by_variant,
        "by_eval_variant": _eval_variant_summary(records),
    }


def _trace_report(records: list[dict[str, Any]], traces: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "mission_id": MISSION_ID,
        "trace_count": len(traces),
        "model_backed_trace_count": _model_backed_count(records),
        "tool_signal_by_variant": {
            variant: any(_trace_has(row, ("toolchain", "tool_call_contract", "raw_bash")) for row in traces if row.get("variant_id") == variant)
            for variant in sorted({str(row.get("variant_id")) for row in traces})
        },
        "receipt_signal_by_variant": {
            variant: any(_trace_has(row, ("receipt", "artifact_log", "attribution_trace")) for row in traces if row.get("variant_id") == variant)
            for variant in sorted({str(row.get("variant_id")) for row in traces})
        },
        "completion_signal_by_variant": {
            variant: any(_trace_has(row, ("completion_gate", "contradiction", "final_acceptance")) for row in traces if row.get("variant_id") == variant)
            for variant in sorted({str(row.get("variant_id")) for row in traces})
        },
    }


def _ablation_report(records: list[dict[str, Any]]) -> dict[str, Any]:
    summary = _variant_summary(records)
    incumbent_pass = summary.get(INCUMBENT, {}).get("pass", 0)
    return {
        "mission_id": MISSION_ID,
        "incumbent": INCUMBENT,
        "ablation_rows": [
            {
                "variant_id": variant,
                "pass_delta_vs_incumbent": row["pass"] - incumbent_pass,
                "fail_delta_vs_incumbent": row["fail"] - summary.get(INCUMBENT, {}).get("fail", 0),
                "run_count": row["run_count"],
            }
            for variant, row in sorted(summary.items())
            if variant != INCUMBENT
        ],
    }


def _generalization_report(records: list[dict[str, Any]]) -> dict[str, Any]:
    evals = {
        "ae_internal_discovery_evidence_efficiency_v1",
        "ae_internal_multifile_repair_test_verify_v1",
    }
    subset = [row for row in records if row.get("eval_id") in evals]
    return {
        "mission_id": MISSION_ID,
        "generalization_eval_ids": sorted(evals),
        "by_variant": _variant_summary(subset),
    }


def _completion_report(records: list[dict[str, Any]], traces: list[dict[str, Any]]) -> dict[str, Any]:
    eval_id = "ae_completion_verifier_final_contradiction_probe"
    subset = [row for row in records if row.get("eval_id") == eval_id]
    return {
        "mission_id": MISSION_ID,
        "completion_probe_eval_id": eval_id,
        "by_variant": _variant_summary(subset),
        "completion_signal_by_variant": {
            variant: any(_trace_has(row, ("completion_gate", "contradiction", "final_acceptance")) for row in traces if row.get("variant_id") == variant and row.get("eval_id") == eval_id)
            for variant in sorted({str(row.get("variant_id")) for row in subset})
        },
    }


def _cost_report(records: list[dict[str, Any]]) -> dict[str, Any]:
    total = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "usd": 0.0}
    by_variant: dict[str, dict[str, Any]] = {}
    for row in records:
        cost = row.get("token_and_cost_summary") or row.get("cost_summary") or {}
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
        "cap_status": "below_soft_cap" if total["usd"] <= 75 else "below_hard_cap" if total["usd"] <= 150 else "hard_cap_exceeded",
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
        }
        for row in records
        if row.get("score_summary", {}).get("final_verdict") != "pass"
    ]
    return {
        "mission_id": MISSION_ID,
        "failure_count": len(failures),
        "invalid_run_count": _invalid_count(records),
        "failures": failures,
    }


def _recommendation(score: dict[str, Any], cost: dict[str, Any], failures: dict[str, Any]) -> dict[str, Any]:
    summary = score["variant_summary"]
    control = summary.get(CONTROL, {})
    incumbent = summary.get(INCUMBENT, {})
    combined = summary.get("spb_tooling_seed_plus_receipt_and_completion_01", {})
    best_required = max((summary.get(variant, {"pass": 0, "fail": 0}) | {"variant_id": variant} for variant in REQUIRED_CHALLENGERS), key=lambda row: (row.get("pass", 0), -row.get("fail", 0)))
    unresolved_count = score["final_verdict_counts"].get("unresolved", 0)
    pass_count = score["final_verdict_counts"].get("pass", 0)
    if (
        failures["invalid_run_count"]
        or cost["cap_status"] == "hard_cap_exceeded"
        or (unresolved_count and not pass_count)
    ):
        selected = "repair_eval_board_before_candidate_review"
    elif combined.get("pass", 0) >= incumbent.get("pass", 0) and combined.get("fail", 0) <= incumbent.get("fail", 0):
        selected = "accept_combined_seed_for_packet07_readiness_review"
    elif best_required.get("pass", 0) > incumbent.get("pass", 0) and best_required.get("fail", 0) <= incumbent.get("fail", 0):
        selected = "accept_candidate_seed_for_packet07_readiness_review"
    elif incumbent.get("pass", 0) > control.get("pass", 0):
        selected = "keep_as_tooling_only_seed"
    elif control.get("pass", 0) >= incumbent.get("pass", 0):
        selected = "prefer_spb_01_baseline"
    else:
        selected = "run_one_targeted_repair_before_packet07_review"
    return {
        "mission_id": MISSION_ID,
        "selected_recommendation": selected,
        "exactly_one_final_recommendation": True,
        "final_recommendation_options": sorted(FINAL_OPTIONS),
        "basis": {
            "score_envelope": score,
            "cost_report": cost,
            "invalid_run_count": failures["invalid_run_count"],
            "best_required_challenger": best_required,
        },
        "authority_note": "Readiness-review recommendation only; no Packet 07 movement, transfer, benchmark widening, RHv1 unfreeze, full RHv1 revival, or protected holdout access occurred.",
    }


def _write_blocked_outputs(output_root: Path, route_matrix: dict[str, Any]) -> dict[str, Any]:
    empty_score = {
        "mission_id": MISSION_ID,
        "run_count": 0,
        "model_backed_runs": 0,
        "invalid_run_count": 0,
        "final_verdict_counts": {},
        "variant_summary": {},
        "route_matrix": route_matrix,
    }
    recommendation = {
        "mission_id": MISSION_ID,
        "selected_recommendation": "repair_eval_board_before_candidate_review",
        "exactly_one_final_recommendation": True,
        "basis": {"route_matrix": route_matrix},
    }
    _write_jsonl(output_root / "candidate_readiness_result_records.jsonl", [])
    _write_json(output_root / "candidate_readiness_score_envelope.json", empty_score)
    _write_json(output_root / "candidate_readiness_trace_report.json", {"mission_id": MISSION_ID, "blocked": True})
    _write_json(output_root / "candidate_readiness_ablation_report.json", {"mission_id": MISSION_ID, "blocked": True})
    _write_json(output_root / "candidate_readiness_generalization_report.json", {"mission_id": MISSION_ID, "blocked": True})
    _write_json(output_root / "candidate_readiness_completion_report.json", {"mission_id": MISSION_ID, "blocked": True})
    _write_json(output_root / "candidate_readiness_cost_report.json", {"mission_id": MISSION_ID, "total": {"usd": 0.0}})
    _write_json(output_root / "candidate_readiness_failure_source_report.json", {"mission_id": MISSION_ID, "blockers": route_matrix["blockers"]})
    _write_json(output_root / "candidate_readiness_recommendations.json", recommendation)
    _write_text(output_root / "candidate_readiness_handoff.md", _handoff(output_root, empty_score, recommendation))
    return {"output_dir": str(output_root), "run_count": 0, "selected_recommendation": recommendation["selected_recommendation"]}


def _plan(output_root: Path, variants: list[str], rerun_count: int) -> str:
    return "\n".join(
        [
            "# Phase 4 Candidate Readiness Plan",
            "",
            f"- mission_id: `{MISSION_ID}`",
            f"- output_root: `{output_root}`",
            f"- operational_control: `{CONTROL}`",
            f"- incumbent_confirmed_seed: `{INCUMBENT}`",
            f"- route_scope: `{PACKET06_PHASE2_ENV_TOOLING_SCOPE}`",
            f"- variants: `{', '.join(variants)}`",
            f"- eval_homes: `{', '.join(REQUIRED_EVALS)}`",
            f"- rerun_count_per_eval_variant: `{rerun_count}`",
            "- authority: no Packet 07 movement, transfer, benchmark widening, protected holdouts, RHv1 unfreeze, full RHv1 revival, or broad challenger admission by implication.",
            "",
        ]
    )


def _handoff(output_root: Path, score: dict[str, Any], recommendation: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Phase 4 Candidate Readiness Handoff",
            "",
            f"- mission_id: `{MISSION_ID}`",
            f"- output_root: `{output_root}`",
            f"- run_count: `{score['run_count']}`",
            f"- model_backed_runs: `{score.get('model_backed_runs', 0)}`",
            f"- invalid_run_count: `{score.get('invalid_run_count', 0)}`",
            f"- final_recommendation: `{recommendation['selected_recommendation']}`",
            "- authority: no Packet 07 movement, transfer, benchmark widening, protected holdouts, RHv1 unfreeze, or full RHv1 revival occurred.",
            "",
        ]
    )


def _authority_boundaries() -> dict[str, bool]:
    return {
        "successor_named": False,
        "packet07_movement": False,
        "transfer": False,
        "benchmark_widening": False,
        "protected_holdout_access": False,
        "rhv1_unfreeze": False,
        "full_rhv1_revival": False,
        "broad_challenger_family_admission": False,
    }


def _budget_caps() -> dict[str, Any]:
    return {
        "target_model_backed_runs_min": 150,
        "target_model_backed_runs_max": 220,
        "hard_model_backed_cap": 300,
        "local_deterministic_cap": 300,
        "soft_usd_cap": 75,
        "hard_usd_cap": 150,
    }


def _variant_summary(records: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    summary: dict[str, dict[str, int]] = {}
    for row in records:
        variant = str(row.get("variant_id"))
        bucket = summary.setdefault(variant, {"run_count": 0, "pass": 0, "fail": 0, "unresolved": 0})
        bucket["run_count"] += 1
        verdict = row.get("score_summary", {}).get("final_verdict")
        if verdict in {"pass", "fail", "unresolved"}:
            bucket[verdict] += 1
    return summary


def _eval_variant_summary(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
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
                }
            )
    return rows


def _model_backed_count(records: list[dict[str, Any]]) -> int:
    return sum(1 for row in records if row.get("model_route", {}).get("provider_route") not in {"none", "local_stub", None})


def _invalid_count(records: list[dict[str, Any]]) -> int:
    return sum(
        1
        for row in records
        if "invalid" in str(row.get("failure_cluster", "")).lower()
        or "invalid" in " ".join(str(code) for code in row.get("reason_codes", []))
    )


def _trace_has(trace: dict[str, Any], needles: tuple[str, ...]) -> bool:
    payload = json.dumps(trace, sort_keys=True)
    return any(needle in payload for needle in needles)


def _counts(values: Any) -> dict[str, int]:
    out: dict[str, int] = {}
    for value in values:
        key = str(value)
        out[key] = out.get(key, 0) + 1
    return out


def _load_eval_cards(path: Path) -> dict[str, dict[str, Any]]:
    cards = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            cards[row["eval_id"]] = row
    missing = set(REQUIRED_EVALS) - set(cards)
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
    parser.add_argument("--rerun-count", type=int, default=6)
    parser.add_argument("--include-optional-trace-learning", action="store_true")
    args = parser.parse_args()
    result = launch_phase4(
        output_dir=args.output_dir,
        eval_cards_path=args.eval_cards_path,
        rerun_count=args.rerun_count,
        include_optional_trace_learning=args.include_optional_trace_learning,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
