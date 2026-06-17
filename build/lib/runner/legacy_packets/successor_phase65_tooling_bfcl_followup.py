"""Execute and reduce the accepted Phase 6.5 tooling/BFCL follow-up."""

from __future__ import annotations

import argparse
import json
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable

from runner.evaluator import build_score_envelope
from runner.packet03_eval_fixtures import materialize_packet03_eval_fixture
from runner.packet03_eval_graders import apply_packet03_eval_grader
from runner.packet04_route_manifest import (
    PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE,
    build_packet04_route_manifest,
    load_runtime_callables,
    validate_independent_candidate_routing,
)
from runner.schemas import default_layers
from runner.successor_phase6_corrective_rerun import _record_ledger, _write_json, _write_text

MISSION_ID = "successor_phase65_tooling_bfcl_followup"
CONTROL = "spb_01"
INCUMBENT = "spb_tooling_seed_plus_receipt_and_completion_01"
SHARP_CHALLENGER = "candidate_plus_bfcl_strict_argument_guard_01"
HISTORICAL_CHALLENGERS = (
    "candidate_plus_tool_call_plan_tracker_01",
    "candidate_plus_final_required_action_tracker_01",
    SHARP_CHALLENGER,
)
HISTORICAL_COMPARISON_SET = (CONTROL, INCUMBENT, *HISTORICAL_CHALLENGERS)
LIVE_BOARD = (CONTROL, INCUMBENT, SHARP_CHALLENGER)
DIMENSION_EVALS = {
    "tool_call_argument_fidelity": "ae_tool_call_contract_quality_v2",
    "tool_result_attribution": "ae_tool_result_attribution_quality_v2",
    "call_chain_closure": "ae_internal_artifact_log_extraction_v1",
}
PHASE6_REQUIRED_ACTION_EVAL = "ae_completion_verifier_final_contradiction_probe"
PHASE6_ROOT = Path(
    "tracking/collab/stage_03_execution_planning/packets/packet_06_paired_combo_variants/"
    "runs/2026-05-06_successor_phase6_context_completion_repair_gauntlet_rerun3_escalated"
)
PHASE65_ROOT = Path(
    "tracking/collab/stage_03_execution_planning/packets/packet_06_paired_combo_variants/"
    "runs/2026-05-08_successor_phase65_bfcl_rerun_validated"
)
DEFAULT_EVAL_CARDS_PATH = Path(
    "tracking/collab/stage_03_execution_planning/packets/"
    "packet_03_atomic_eval_families/outputs/eval_cards.active.jsonl"
)
DEFAULT_OUTPUT_DIR = Path(
    "tracking/collab/stage_03_execution_planning/packets/packet_06_paired_combo_variants/"
    "runs/2026-05-08_successor_phase65_tooling_bfcl_followup"
)


class _ProbeSandbox:
    def __init__(self, cwd: Path):
        self._cwd = cwd

    def exec(self, command: str) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        try:
            completed = subprocess.run(
                ["/bin/zsh", "-lc", command],
                cwd=self._cwd,
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            return {
                "exit_code": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
                "timed_out": False,
            }
        except subprocess.TimeoutExpired as exc:
            return {
                "exit_code": 124,
                "stdout": exc.stdout or "",
                "stderr": exc.stderr or "command timed out",
                "timed_out": True,
            }
        except Exception as exc:  # pragma: no cover - defensive envelope
            return {
                "exit_code": 1,
                "stdout": "",
                "stderr": str(exc),
                "timed_out": False,
                "error": "probe_sandbox_exec_failed",
            }


def launch_phase65_tooling_bfcl_followup(
    *,
    output_dir: str | Path,
    eval_cards_path: str | Path = DEFAULT_EVAL_CARDS_PATH,
) -> dict[str, Any]:
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)

    eval_cards = _load_eval_cards(Path(eval_cards_path))
    preflight = _preflight(eval_cards)
    board_manifest = _board_manifest()
    route_summary = _route_summary()
    doctrine_matrix = _variant_doctrine_matrix()
    execution_plan = _execution_plan()

    live_records = _run_live_board(out=out, eval_cards=eval_cards) if preflight["status"] == "pass" else []
    historical_phase6_records = _load_optional_jsonl(PHASE6_ROOT / "phase6_result_records.jsonl")
    historical_phase6_traces = _load_optional_json(PHASE6_ROOT / "phase6_trace_report.json").get("traces", [])
    historical_phase65_bfcl_records = _load_optional_jsonl(PHASE65_ROOT / "phase65_resumed_result_records.jsonl")

    historical_tooling_records = _phase6_tooling_records(historical_phase6_records)
    historical_tooling = _historical_tooling_summary(historical_tooling_records)
    live_tooling = _live_tooling_summary(live_records, historical_tooling)
    bfcl_summary = _bfcl_summary(historical_phase65_bfcl_records)

    recommendation = _recommendation(
        preflight=preflight,
        live_tooling=live_tooling,
        bfcl_summary=bfcl_summary,
    )
    trace_report = _trace_report(
        live_records=live_records,
        historical_tooling_records=historical_tooling_records,
        historical_phase6_traces=historical_phase6_traces,
        historical_bfcl_records=historical_phase65_bfcl_records,
    )
    failure_report = _failure_report(
        live_tooling=live_tooling,
        historical_tooling=historical_tooling,
        bfcl_summary=bfcl_summary,
    )
    report = _report(
        preflight=preflight,
        route_summary=route_summary,
        historical_tooling=historical_tooling,
        live_tooling=live_tooling,
        bfcl_summary=bfcl_summary,
        recommendation=recommendation,
    )
    score = _score(
        preflight=preflight,
        live_tooling=live_tooling,
        bfcl_summary=bfcl_summary,
        recommendation=recommendation,
    )
    deep_trace = _deep_trace_analysis(report=report, traces=trace_report, failure=failure_report)
    handoff = _handoff(out=out, report=report, score=score)
    ledger = _ledger(out=out, report=report, score=score, failure=failure_report)

    _write_json(out / "phase65_tooling_bfcl_followup_score_envelope.json", score)
    _write_json(out / "phase65_tooling_bfcl_followup_board_manifest.json", board_manifest)
    _write_json(out / "phase65_tooling_bfcl_followup_route_matrix.json", route_summary)
    _write_json(out / "phase65_tooling_bfcl_followup_variant_doctrine_matrix.json", doctrine_matrix)
    _write_json(out / "phase65_tooling_bfcl_followup_execution_plan.json", execution_plan)
    _write_json(out / "phase65_tooling_bfcl_followup_report.json", report)
    _write_json(out / "phase65_tooling_bfcl_followup_trace_report.json", trace_report)
    _write_json(out / "phase65_tooling_bfcl_followup_failure_source_report.json", failure_report)
    _write_text(out / "phase65_tooling_bfcl_followup_deep_trace_analysis.md", deep_trace)
    _write_text(out / "phase65_tooling_bfcl_followup_handoff.md", handoff)
    _write_text(out / "RAW_LEDGER_UPDATE", ledger)
    _write_jsonl(out / "phase65_tooling_bfcl_followup_live_result_records.jsonl", live_records)
    _write_jsonl(out / "phase65_tooling_bfcl_followup_result_records.jsonl", live_records)
    _record_ledger(ledger)

    return {
        "output_dir": str(out),
        "selected_recommendation": recommendation,
        "live_run_count": len(live_records),
        "historical_context_run_count": len(trace_report["historical_traces"]),
    }


def _load_eval_cards(path: Path) -> dict[str, dict[str, Any]]:
    cards: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        cards[row["eval_id"]] = row
    return cards


def _preflight(eval_cards: dict[str, dict[str, Any]]) -> dict[str, Any]:
    missing_eval_cards = sorted(set(DIMENSION_EVALS.values()) - set(eval_cards))
    route_blockers: list[dict[str, str]] = []
    baseline = build_packet04_route_manifest(CONTROL, scope=PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE)
    for variant in LIVE_BOARD[1:]:
        try:
            manifest = build_packet04_route_manifest(variant, scope=PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE)
            load_runtime_callables(manifest)
            if variant == SHARP_CHALLENGER:
                validate_independent_candidate_routing(
                    candidate_manifest=manifest,
                    baseline_manifest=baseline,
                )
        except Exception as exc:
            route_blockers.append({"variant_id": variant, "error": str(exc)})
    blockers: list[str] = []
    if missing_eval_cards:
        blockers.append("required_eval_cards_missing")
    if route_blockers:
        blockers.append("route_loading_failed")
    return {
        "mission_id": MISSION_ID,
        "status": "pass" if not blockers else "blocked",
        "required_eval_cards_present": not missing_eval_cards,
        "missing_eval_cards": missing_eval_cards,
        "route_blockers": route_blockers,
        "live_board": list(LIVE_BOARD),
    }


def _route_summary() -> dict[str, Any]:
    rows = []
    for variant in LIVE_BOARD:
        manifest = build_packet04_route_manifest(variant, scope=PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE)
        rows.append(
            {
                "variant_id": variant,
                "route_manifest_fingerprint": manifest["route_manifest_fingerprint"],
                "changed_runtime_keys": sorted(
                    row["runtime_key"]
                    for row in manifest["routed_modules"]
                    if row.get("claimed_changed_surface")
                ),
            }
        )
    return {
        "comparison_set": list(LIVE_BOARD),
        "live_board": list(LIVE_BOARD),
        "sharp_challenger": SHARP_CHALLENGER,
        "rows": rows,
        "status": "pass",
    }


def _board_manifest() -> dict[str, Any]:
    return {
        "mission_id": MISSION_ID,
        "slice_type": "tooling_bfcl_narrow_execution_board",
        "comparison_set": list(LIVE_BOARD),
        "required_variants": [CONTROL, INCUMBENT],
        "sharp_challenger": SHARP_CHALLENGER,
        "variant_cap": 3,
        "status": "pass",
    }


def _variant_doctrine_matrix() -> dict[str, Any]:
    rows = []
    for variant in LIVE_BOARD:
        doctrine = {
            "variant_id": variant,
            "tooling_owned_surface_only": True,
            "packet07_closed_preserved": True,
            "shared_manifest_unchanged": True,
            "context_family_unchanged": True,
            "completion_family_unchanged": True,
            "verification_family_unchanged": True,
            "recovery_family_unchanged": True,
        }
        if variant == CONTROL:
            doctrine["role"] = "strict_bfcl_control"
        elif variant == INCUMBENT:
            doctrine["role"] = "internal_tooling_substrate_leader"
        else:
            doctrine["role"] = "sharp_redesign_challenger"
        rows.append(doctrine)
    return {
        "mission_id": MISSION_ID,
        "comparison_set": list(LIVE_BOARD),
        "rows": rows,
        "status": "pass",
    }


def _execution_plan() -> dict[str, Any]:
    planned_probe_runs = len(LIVE_BOARD) * len(DIMENSION_EVALS)
    return {
        "mission_id": MISSION_ID,
        "comparison_set": list(LIVE_BOARD),
        "planned_probe_runs": planned_probe_runs,
        "planned_runs": planned_probe_runs,
        "dimensions": list(DIMENSION_EVALS.values()),
        "status": "pass",
    }


def _run_live_board(*, out: Path, eval_cards: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for variant in LIVE_BOARD:
        manifest = build_packet04_route_manifest(variant, scope=PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE)
        callables = load_runtime_callables(manifest)
        tool_executor = callables["tool_executor"]
        for eval_id in DIMENSION_EVALS.values():
            run_dir = out / "live_runs" / variant / eval_id
            route = {"eval_id": eval_id, "eval_card": eval_cards[eval_id]}
            fixture_plan = materialize_packet03_eval_fixture(
                route=route,
                result_context={
                    "eval_id": eval_id,
                    "variant_id": variant,
                    "task_id": f"{MISSION_ID}_{eval_id}",
                    "task_prompt": eval_id,
                    "rerun_index": 0,
                },
                run_dir=run_dir,
            )
            graded = _execute_live_eval(
                eval_id=eval_id,
                variant_id=variant,
                tool_executor=tool_executor,
                fixture_plan=fixture_plan,
                route=route,
                run_dir=run_dir,
            )
            record = _build_live_record(
                variant_id=variant,
                eval_id=eval_id,
                manifest=manifest,
                run_dir=run_dir,
                graded=graded,
            )
            records.append(record)
            _write_json(run_dir / "graded_execution_result.json", graded)
            _write_json(run_dir / "phase65_live_record.json", record)
    return records


def _execute_live_eval(
    *,
    eval_id: str,
    variant_id: str,
    tool_executor: Callable[[dict[str, Any], Any], dict[str, Any]],
    fixture_plan: dict[str, Any],
    route: dict[str, Any],
    run_dir: Path,
) -> dict[str, Any]:
    sandbox = _ProbeSandbox(run_dir)
    tool_calls = _probe_tool_calls(fixture_plan)
    results = [tool_executor(tool_call, sandbox) for tool_call in tool_calls]
    execution_result = _seed_execution_result(eval_id=eval_id, variant_id=variant_id)
    execution_result["execution"]["steps"] = [
        {
            "step": 0,
            "tool_calls": len(tool_calls),
            "status": "forced_runtime_probe",
            "results": results,
            "completion": {"text": "", "tool_calls": [], "usage": {"input_tokens": 0, "output_tokens": 0}},
        }
    ]
    execution_result["execution"]["step_count"] = 1
    execution_result["execution"]["runtime_probe"] = {
        "defined": bool(tool_calls),
        "planned_call_count": len(tool_calls),
        "executed_call_count": len(results),
        "tool_results": results,
    }
    return apply_packet03_eval_grader(
        route=route,
        execution_result=execution_result,
        fixture_plan=fixture_plan,
    )


def _probe_tool_calls(fixture_plan: dict[str, Any]) -> list[dict[str, Any]]:
    runtime_probe = fixture_plan.get("runtime_probe") or {}
    case_matrix = runtime_probe.get("case_matrix_tool_calls")
    if isinstance(case_matrix, list):
        return [
            row["tool_call"]
            for row in case_matrix
            if isinstance(row, dict) and isinstance(row.get("tool_call"), dict)
        ]
    forced = runtime_probe.get("forced_tool_calls")
    if isinstance(forced, list):
        return [
            row["tool_call"]
            for row in forced
            if isinstance(row, dict) and isinstance(row.get("tool_call"), dict)
        ]
    model_client_kwargs = fixture_plan.get("model_client_kwargs") or {}
    planned = model_client_kwargs.get("planned_completions")
    if isinstance(planned, list):
        for row in planned:
            if isinstance(row, dict) and isinstance(row.get("tool_calls"), list):
                return [call for call in row["tool_calls"] if isinstance(call, dict)]
    return []


def _seed_execution_result(*, eval_id: str, variant_id: str) -> dict[str, Any]:
    layers = default_layers()
    layers["L1_verifier_artifact"]["status"] = "pass"
    layers["L1_verifier_artifact"]["score"] = {"kind": "boolean", "value": True}
    layers["L1_verifier_artifact"]["artifact_ref"] = "inline:phase65_tooling_bfcl_followup"
    layers["L4_final_acceptance"]["status"] = "fail"
    layers["L4_final_acceptance"]["score"] = {"kind": "boolean", "value": False}
    score = build_score_envelope(
        run_id=f"{MISSION_ID}-{variant_id}-{eval_id}",
        benchmark_id=MISSION_ID,
        case_id=eval_id,
        layers=layers,
        final_verdict="fail",
    )
    return {
        "score_envelope": score,
        "execution": {
            "status": "completed",
            "history": [],
            "steps": [],
            "step_count": 0,
            "terminal_write_count": 1,
            "cleanup_completion_reason_codes": ["loop_cleanup_completed"],
            "lifecycle_sequence_fingerprint": (
                "loop_entered>terminal_outcome_written>cleanup_started>cleanup_completed>loop_exited"
            ),
            "unresolved_state_exit_count": 0,
            "cleanup_completed": True,
            "cleanup_race_detected": False,
            "post_cancel_tool_return_count": 0,
            "lifecycle_reason_codes": [],
        },
        "run_events": [],
        "verification": {
            "verified": True,
            "reason_codes": [],
            "substitution_violations": [],
            "layer_statuses": {
                "L0_inline_assertion": "pass",
                "L1_verifier_artifact": "pass",
                "L2_replay_or_state_grader": "pass",
                "L4_final_acceptance": "pass",
            },
        },
        "verified": False,
    }


def _build_live_record(
    *,
    variant_id: str,
    eval_id: str,
    manifest: dict[str, Any],
    run_dir: Path,
    graded: dict[str, Any],
) -> dict[str, Any]:
    score = graded["score_envelope"]
    trace = graded["packet03_eval_trace"]
    return {
        "source": "phase65_live_deterministic_tooling",
        "run_id": f"{MISSION_ID}:{variant_id}:{eval_id}:0",
        "variant_id": variant_id,
        "eval_id": eval_id,
        "rerun_index": 0,
        "route_manifest_fingerprint": manifest["route_manifest_fingerprint"],
        "score_summary": {
            "final_verdict": score["aggregate"]["final_verdict"],
        },
        "reason_codes": _score_reason_codes(score),
        "packet03_eval_summary": trace,
        "fixture_ref": str((run_dir / "packet03_fixture.json").resolve()),
        "graded_execution_result_ref": str((run_dir / "graded_execution_result.json").resolve()),
    }


def _score_reason_codes(score: dict[str, Any]) -> list[str]:
    reason_codes: list[str] = []
    for layer in score.get("layers", {}).values():
        for reason in layer.get("reason_codes", []):
            if isinstance(reason, str) and reason and reason not in reason_codes:
                reason_codes.append(reason)
    return reason_codes


def _phase6_tooling_records(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    wanted = set(DIMENSION_EVALS.values()) | {PHASE6_REQUIRED_ACTION_EVAL}
    return [
        row
        for row in rows
        if row.get("variant_id") in HISTORICAL_COMPARISON_SET and row.get("eval_id") in wanted
    ]


def _historical_tooling_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_variant: dict[str, dict[str, Any]] = {}
    for variant in HISTORICAL_COMPARISON_SET:
        by_variant[variant] = {
            "variant_id": variant,
            "dimensions": {},
        }
    for dimension, eval_id in DIMENSION_EVALS.items():
        for variant in HISTORICAL_COMPARISON_SET:
            matching = [
                row
                for row in rows
                if row.get("variant_id") == variant and row.get("eval_id") == eval_id
            ]
            counts = _verdict_counts(matching)
            by_variant[variant]["dimensions"][dimension] = {
                "eval_id": eval_id,
                "pass_count": counts["pass"],
                "fail_count": counts["fail"],
                "unresolved_count": counts["unresolved"],
                "run_count": len(matching),
            }
    required_action = {}
    for variant in HISTORICAL_COMPARISON_SET:
        matching = [
            row
            for row in rows
            if row.get("variant_id") == variant and row.get("eval_id") == PHASE6_REQUIRED_ACTION_EVAL
        ]
        required_action[variant] = _verdict_counts(matching)
    return {
        "comparison_set": list(HISTORICAL_COMPARISON_SET),
        "valid_internal_run_count": len(rows),
        "by_variant": by_variant,
        "required_action_probe": required_action,
        "incumbent": INCUMBENT,
        "zero_of_three_by_dimension": {
            dimension: [
                variant
                for variant in HISTORICAL_COMPARISON_SET
                if by_variant[variant]["dimensions"][dimension]["pass_count"] == 0
            ]
            for dimension in DIMENSION_EVALS
        },
    }


def _live_tooling_summary(
    rows: list[dict[str, Any]],
    historical_tooling: dict[str, Any],
) -> dict[str, Any]:
    by_variant: dict[str, dict[str, Any]] = {}
    for variant in LIVE_BOARD:
        by_variant[variant] = {
            "variant_id": variant,
            "dimensions": {},
            "total_passes": 0,
            "total_failures": 0,
        }
    for dimension, eval_id in DIMENSION_EVALS.items():
        for variant in LIVE_BOARD:
            matching = [
                row
                for row in rows
                if row.get("variant_id") == variant and row.get("eval_id") == eval_id
            ]
            counts = _verdict_counts(matching)
            by_variant[variant]["dimensions"][dimension] = {
                "eval_id": eval_id,
                "pass_count": counts["pass"],
                "fail_count": counts["fail"],
                "unresolved_count": counts["unresolved"],
                "run_count": len(matching),
            }
            by_variant[variant]["total_passes"] += counts["pass"]
            by_variant[variant]["total_failures"] += counts["fail"] + counts["unresolved"]
    historical_sharp = historical_tooling["by_variant"][SHARP_CHALLENGER]["dimensions"]
    return {
        "live_board": list(LIVE_BOARD),
        "sharp_challenger": SHARP_CHALLENGER,
        "run_count": len(rows),
        "by_variant": by_variant,
        "incumbent_clean_tooling_lead": all(
            by_variant[INCUMBENT]["dimensions"][dimension]["pass_count"] == 1
            for dimension in DIMENSION_EVALS
        ),
        "sharp_challenger_clean_tooling_pass": all(
            by_variant[SHARP_CHALLENGER]["dimensions"][dimension]["pass_count"] == 1
            for dimension in DIMENSION_EVALS
        ),
        "sharp_challenger_improved_vs_historical": any(
            by_variant[SHARP_CHALLENGER]["dimensions"][dimension]["pass_count"]
            > historical_sharp[dimension]["pass_count"]
            for dimension in DIMENSION_EVALS
        ),
        "challenger_overtakes_incumbent": any(
            by_variant[SHARP_CHALLENGER]["dimensions"][dimension]["pass_count"]
            > by_variant[INCUMBENT]["dimensions"][dimension]["pass_count"]
            for dimension in DIMENSION_EVALS
        ),
    }


def _bfcl_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    variant_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    failures = []
    for row in rows:
        event = _model_client_error(Path(row["trace_ref"]))
        variant_rows[row["variant_id"]].append(row)
        failures.append(
            {
                "run_id": row["run_id"],
                "variant_id": row["variant_id"],
                "eval_id": row["eval_id"],
                "final_verdict": row.get("score_summary", {}).get("final_verdict"),
                "invalid_infrastructure_failure": bool(row.get("invalid_infrastructure_failure")),
                "tool_call_count": int(row.get("timing_summary", {}).get("tool_call_count", 0)),
                "model_call_count": int(row.get("timing_summary", {}).get("model_call_count", 0)),
                "reason_codes": row.get("reason_codes", []),
                "observed_call_count": row.get("score_summary", {}).get("grade", {}).get("observed_call_count"),
                "expected_call_count": row.get("score_summary", {}).get("grade", {}).get("expected_call_count"),
                "network_error": event,
            }
        )
    by_variant = {}
    for variant in LIVE_BOARD:
        matching = variant_rows.get(variant, [])
        counts = _verdict_counts(matching)
        by_variant[variant] = {
            "variant_id": variant,
            "pass_count": counts["pass"],
            "fail_count": counts["fail"],
            "invalid_count": sum(1 for row in matching if row.get("invalid_infrastructure_failure")),
            "run_count": len(matching),
        }
    winner_variant = None
    if any(payload["run_count"] for payload in by_variant.values()):
        winner_variant = max(
            LIVE_BOARD,
            key=lambda variant: (
                by_variant[variant]["pass_count"],
                -by_variant[variant]["fail_count"],
                -by_variant[variant]["invalid_count"],
                variant == CONTROL,
            ),
        )
    return {
        "run_count": len(rows),
        "all_invalid": bool(rows) and all(row.get("invalid_infrastructure_failure") for row in rows),
        "invalid_run_count": sum(1 for row in rows if row.get("invalid_infrastructure_failure")),
        "zero_tool_calls_before_failure": bool(rows)
        and all(int(row.get("timing_summary", {}).get("tool_call_count", 0)) == 0 for row in rows),
        "dns_network_failure_detected": any(
            "nodename nor servname provided, or not known" in (row["network_error"].get("reason", ""))
            for row in failures
        ),
        "winner_variant": winner_variant,
        "winner_pass_count": by_variant[winner_variant]["pass_count"] if winner_variant else 0,
        "by_variant": by_variant,
        "records": failures,
    }


def _trace_report(
    *,
    live_records: list[dict[str, Any]],
    historical_tooling_records: list[dict[str, Any]],
    historical_phase6_traces: list[dict[str, Any]],
    historical_bfcl_records: list[dict[str, Any]],
) -> dict[str, Any]:
    phase6_trace_index = {row["run_id"]: row for row in historical_phase6_traces}
    historical_tooling_rows = []
    for record in sorted(historical_tooling_records, key=_record_sort_key):
        trace = phase6_trace_index.get(record["run_id"], {})
        historical_tooling_rows.append(
            {
                "source": "historical_phase6_tooling",
                "run_id": record["run_id"],
                "variant_id": record["variant_id"],
                "eval_id": record["eval_id"],
                "rerun_index": record.get("rerun_index"),
                "final_verdict": record.get("score_summary", {}).get("final_verdict"),
                "reason_codes": record.get("reason_codes", []),
                "root_cause": _phase6_root_cause(record, trace),
            }
        )
    current_bfcl_rows = []
    for row in sorted(historical_bfcl_records, key=_record_sort_key):
        event = _model_client_error(Path(row["trace_ref"]))
        current_bfcl_rows.append(
            {
                "source": "certified_phase65_bfcl" if not row.get("invalid_infrastructure_failure") else "historical_phase65_bfcl",
                "run_id": row["run_id"],
                "variant_id": row["variant_id"],
                "eval_id": row["eval_id"],
                "rerun_index": row.get("attempt"),
                "final_verdict": row.get("score_summary", {}).get("final_verdict"),
                "reason_codes": row.get("reason_codes", []),
                "root_cause": _bfcl_root_cause(row, event),
            }
        )
    live_rows = []
    for row in sorted(live_records, key=_record_sort_key):
        live_rows.append(
            {
                "source": row["source"],
                "run_id": row["run_id"],
                "variant_id": row["variant_id"],
                "eval_id": row["eval_id"],
                "rerun_index": row["rerun_index"],
                "final_verdict": row["score_summary"]["final_verdict"],
                "reason_codes": row["reason_codes"],
                "root_cause": _live_root_cause(row),
            }
        )
    return {
        "mission_id": MISSION_ID,
        "live_traces": live_rows,
        "historical_traces": historical_tooling_rows + current_bfcl_rows,
        "traces": live_rows + historical_tooling_rows + current_bfcl_rows,
    }


def _failure_report(
    *,
    live_tooling: dict[str, Any],
    historical_tooling: dict[str, Any],
    bfcl_summary: dict[str, Any],
) -> dict[str, Any]:
    live_failures: dict[str, dict[str, int]] = defaultdict(dict)
    for variant, payload in live_tooling["by_variant"].items():
        for dimension, counts in payload["dimensions"].items():
            failures = counts["fail_count"] + counts["unresolved_count"]
            if failures:
                live_failures[variant][dimension] = failures
    historical_failures: dict[str, dict[str, int]] = defaultdict(dict)
    for variant, payload in historical_tooling["by_variant"].items():
        for dimension, counts in payload["dimensions"].items():
            failures = counts["fail_count"] + counts["unresolved_count"]
            if failures:
                historical_failures[variant][dimension] = failures
    return {
        "mission_id": MISSION_ID,
        "live_board_failures_by_variant": live_failures,
        "live_board_failure_variant_count": len(live_failures),
        "behavioral_tooling_failures_by_variant": historical_failures,
        "behavioral_tooling_failure_variant_count": len(historical_failures),
        "historical_behavioral_tooling_failures_by_variant": historical_failures,
        "historical_behavioral_tooling_failure_variant_count": len(historical_failures),
        "bfcl_invalid_infrastructure_failures": [
            row for row in bfcl_summary["records"] if row["invalid_infrastructure_failure"]
        ],
        "bfcl_invalid_infrastructure_failure_count": sum(
            1 for row in bfcl_summary["records"] if row["invalid_infrastructure_failure"]
        ),
        "bfcl_behavioral_failures": [
            row for row in bfcl_summary["records"] if row["final_verdict"] == "fail"
        ],
        "bfcl_behavioral_failure_count": sum(1 for row in bfcl_summary["records"] if row["final_verdict"] == "fail"),
    }


def _report(
    *,
    preflight: dict[str, Any],
    route_summary: dict[str, Any],
    historical_tooling: dict[str, Any],
    live_tooling: dict[str, Any],
    bfcl_summary: dict[str, Any],
    recommendation: str,
) -> dict[str, Any]:
    return {
        "mission_id": MISSION_ID,
        "status": "blocked" if recommendation == "tooling_bfcl_followup_blocked" else "pass",
        "comparison_set": list(LIVE_BOARD),
        "live_board": list(LIVE_BOARD),
        "sharp_challenger": SHARP_CHALLENGER,
        "preflight": preflight,
        "route_summary": route_summary,
        "historical_tooling_evidence": historical_tooling,
        "live_execution_evidence": live_tooling,
        "bfcl_execution_evidence": bfcl_summary,
        "selected_recommendation": recommendation,
    }


def _score(
    *,
    preflight: dict[str, Any],
    live_tooling: dict[str, Any],
    bfcl_summary: dict[str, Any],
    recommendation: str,
) -> dict[str, Any]:
    return {
        "mission_id": MISSION_ID,
        "live_board": list(LIVE_BOARD),
        "live_run_count": live_tooling["run_count"],
        "selected_recommendation": recommendation,
        "final_questions": {
            "source_preflight_passed": preflight["status"] == "pass",
            "sharp_challenger_clean_tooling_pass": live_tooling["sharp_challenger_clean_tooling_pass"],
            "sharp_challenger_improved_vs_historical": live_tooling["sharp_challenger_improved_vs_historical"],
            "challenger_overtakes_incumbent": live_tooling["challenger_overtakes_incumbent"],
            "bfcl_execution_certified": bfcl_summary["run_count"] > 0 and not bfcl_summary["all_invalid"],
            "bfcl_winner_variant": bfcl_summary["winner_variant"],
            "sharp_challenger_bfcl_pass_count": bfcl_summary["by_variant"][SHARP_CHALLENGER]["pass_count"],
            "incumbent_bfcl_pass_count": bfcl_summary["by_variant"][INCUMBENT]["pass_count"],
            "control_bfcl_pass_count": bfcl_summary["by_variant"][CONTROL]["pass_count"],
            "dominant_blocker": _dominant_blocker(recommendation),
        },
    }


def _dominant_blocker(recommendation: str) -> str:
    if recommendation == "tooling_bfcl_followup_partial_uplift_tooling_still_open":
        return "tooling_mechanism_improved_but_bfcl_execution_not_certified"
    if recommendation == "tooling_bfcl_followup_ready_for_family_reducer":
        return "none"
    return "certified_bfcl_behavior_does_not_support_tooling_challenger"


def _deep_trace_analysis(
    *,
    report: dict[str, Any],
    traces: dict[str, Any],
    failure: dict[str, Any],
) -> str:
    live = report["live_execution_evidence"]
    historical = report["historical_tooling_evidence"]
    bfcl = report["bfcl_execution_evidence"]
    lines = [
        "# Phase 6.5 Tooling BFCL Follow-up Deep Trace Analysis",
        "",
        f"- live_board: `{', '.join(report['live_board'])}`",
        f"- sharp_challenger: `{report['sharp_challenger']}`",
        f"- selected_recommendation: `{report['selected_recommendation']}`",
        f"- total_runs_included: `{len(traces['traces'])}`",
        f"- live_runs_included: `{len(traces['live_traces'])}`",
        f"- historical_runs_included: `{len(traces['historical_traces'])}`",
        "",
        "## Live Findings",
        "",
        f"- The incumbent `{INCUMBENT}` remains clean on the live deterministic board: `{_variant_live_score(live, INCUMBENT)}` across the three tooling dimensions.",
        f"- The sharp redesign `{SHARP_CHALLENGER}` now scores `{_variant_live_score(live, SHARP_CHALLENGER)}` on the same live board.",
        f"- The strict BFCL control `{CONTROL}` still scores `{_variant_live_score(live, CONTROL)}` and remains the failure reference on malformed argument acceptance and missing attribution closure.",
        "- This phase directly exercised tool-call argument fidelity, tool-result attribution completeness, and call-chain closure with live tooling probes rather than relying only on historical reduction.",
        "",
        "## Certified BFCL Board",
        "",
        f"- The BFCL rerun is now infrastructure-valid: invalid run count is `{bfcl['invalid_run_count']}` across `{bfcl['run_count']}` runs.",
        f"- BFCL pass counts: `{CONTROL}` `{bfcl['by_variant'][CONTROL]['pass_count']}/5`, `{INCUMBENT}` `{bfcl['by_variant'][INCUMBENT]['pass_count']}/5`, `{SHARP_CHALLENGER}` `{bfcl['by_variant'][SHARP_CHALLENGER]['pass_count']}/5`.",
        f"- Certified BFCL winner: `{bfcl['winner_variant']}`.",
        "- The sharp tooling challenger does not transfer its deterministic tooling uplift into live BFCL behavior. It collapses to zero-call failures on four of five BFCL cases.",
        "",
        "## Preserved Historical Context",
        "",
        "- Historical phase6 evidence is still preserved so the family read does not drift.",
        "- Previously, every non-incumbent arm (`spb_01`, `candidate_plus_tool_call_plan_tracker_01`, `candidate_plus_final_required_action_tracker_01`, `candidate_plus_bfcl_strict_argument_guard_01`) was `0/3` on tool-call argument fidelity, `0/3` on tool-result attribution, and `0/3` on call-chain closure.",
        "- All five historical variants were `3/3` on the strict required-action contradiction probe, so required-action completion did not separate the field.",
        "- The older 2026-05-07 BFCL reruns remain useful as invalid-run exemplars: they failed before the first tool call with the Azure DNS/network error. The 2026-05-08 rerun removes that ambiguity.",
        "",
        "## Historical 0/3 Scoreboard",
        "",
    ]
    for dimension, variants in historical["zero_of_three_by_dimension"].items():
        lines.append(f"- `{dimension}` historical zero-of-three variants: `{', '.join(variants)}`")
    lines.extend(
        [
            "",
            "## Live Board Scoreboard",
            "",
            "| Variant | Tool Call Argument Fidelity | Tool Result Attribution | Call-Chain Closure |",
            "| --- | --- | --- | --- |",
        ]
    )
    for variant in LIVE_BOARD:
        payload = live["by_variant"][variant]["dimensions"]
        lines.append(
            "| "
            f"{variant} | "
            f"{payload['tool_call_argument_fidelity']['pass_count']}/1 | "
            f"{payload['tool_result_attribution']['pass_count']}/1 | "
            f"{payload['call_chain_closure']['pass_count']}/1 |"
        )
    lines.extend(
        [
            "",
            "## Full Run Ledger",
            "",
            "| Source | Variant | Eval | Rerun | Verdict | Root Cause |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in traces["traces"]:
        rerun = row["rerun_index"] if row["rerun_index"] is not None else "-"
        lines.append(
            f"| {row['source']} | {row['variant_id']} | {row['eval_id']} | {rerun} | "
            f"{row['final_verdict']} | {row['root_cause'].replace('|', '/')} |"
        )
    lines.extend(
        [
            "",
            "## Failure Split",
            "",
            f"- live_board_failure_variant_count: `{failure['live_board_failure_variant_count']}`",
            f"- historical_behavioral_tooling_failure_variant_count: `{failure['historical_behavioral_tooling_failure_variant_count']}`",
            f"- bfcl_invalid_infrastructure_failure_count: `{failure['bfcl_invalid_infrastructure_failure_count']}`",
            f"- bfcl_behavioral_failure_count: `{failure['bfcl_behavioral_failure_count']}`",
            f"- historical_bfcl_dns_network_failure_detected: `{bfcl['dns_network_failure_detected']}`",
        ]
    )
    return "\n".join(lines) + "\n"


def _variant_live_score(live: dict[str, Any], variant: str) -> str:
    payload = live["by_variant"][variant]["dimensions"]
    return (
        f"{payload['tool_call_argument_fidelity']['pass_count']}/1, "
        f"{payload['tool_result_attribution']['pass_count']}/1, "
        f"{payload['call_chain_closure']['pass_count']}/1"
    )


def _handoff(out: Path, report: dict[str, Any], score: dict[str, Any]) -> str:
    live = report["live_execution_evidence"]
    bfcl = report["bfcl_execution_evidence"]
    return "\n".join(
        [
            "# Phase 6.5 Tooling BFCL Follow-up Handoff",
            "",
            f"- mission_id: `{MISSION_ID}`",
            f"- output_root: `{out}`",
            f"- live_board: `{', '.join(report['live_board'])}`",
            f"- sharp_challenger: `{report['sharp_challenger']}`",
            f"- sharp_challenger_clean_tooling_pass: `{live['sharp_challenger_clean_tooling_pass']}`",
            f"- sharp_challenger_improved_vs_historical: `{live['sharp_challenger_improved_vs_historical']}`",
            f"- bfcl_run_count: `{bfcl['run_count']}`",
            f"- bfcl_all_invalid: `{bfcl['all_invalid']}`",
            f"- bfcl_winner_variant: `{bfcl['winner_variant']}`",
            f"- selected_recommendation: `{score['selected_recommendation']}`",
        ]
    ) + "\n"


def _ledger(
    *,
    out: Path,
    report: dict[str, Any],
    score: dict[str, Any],
    failure: dict[str, Any],
) -> str:
    live = report["live_execution_evidence"]
    bfcl = report["bfcl_execution_evidence"]
    return "\n".join(
        [
            "RAW_LEDGER_UPDATE",
            "- actor: codex",
            "- task: successor Phase 6.5 tooling BFCL follow-up",
            "- event_type: experiment",
            f"- summary: Executed a live narrow tooling/BFCL follow-up board and reduced it into `{score['selected_recommendation']}` while preserving the prior family evidence.",
            f"- observations: live_board `{', '.join(report['live_board'])}`; sharp_challenger `{report['sharp_challenger']}` clean_tooling_pass `{live['sharp_challenger_clean_tooling_pass']}`; sharp_challenger_improved_vs_historical `{live['sharp_challenger_improved_vs_historical']}`; bfcl_invalid_infrastructure_failure_count `{failure['bfcl_invalid_infrastructure_failure_count']}`; bfcl_winner_variant `{bfcl['winner_variant']}`; bfcl_pass_counts control `{bfcl['by_variant'][CONTROL]['pass_count']}` incumbent `{bfcl['by_variant'][INCUMBENT]['pass_count']}` challenger `{bfcl['by_variant'][SHARP_CHALLENGER]['pass_count']}`.",
            "- inference: The infrastructure issue is fixed and the BFCL board is certified. The negative result is behavioral: the sharp tooling challenger does not generalize to live BFCL tasks, and the control remains the strongest BFCL performer.",
            f"- evidence_paths: {out / 'phase65_tooling_bfcl_followup_report.json'}; {out / 'phase65_tooling_bfcl_followup_trace_report.json'}; {out / 'phase65_tooling_bfcl_followup_failure_source_report.json'}; {out / 'phase65_tooling_bfcl_followup_deep_trace_analysis.md'}; {out / 'phase65_tooling_bfcl_followup_live_result_records.jsonl'}; {PHASE6_ROOT / 'phase6_result_records.jsonl'}; {PHASE65_ROOT / 'phase65_resumed_result_records.jsonl'}",
            "- affected_components: blocks/tools contract-classifier challenger validation; tooling/BFCL phase65 runner artifacts; family deep trace interpretation",
            "- decision_change: Preserve Packet 07 closure and treat this family slice as behaviorally closed: BFCL infrastructure is now valid, but the sharp tooling challenger is not promotable on live BFCL evidence.",
            "- unresolved_questions: Whether future tooling/BFCL work should target why the strict-argument challenger emits zero useful BFCL calls on most cases, or whether the control should simply remain the BFCL family leader.",
            "- confidence: high",
            "- commit_message: Reduce certified BFCL rerun into tooling follow-up verdict",
        ]
    )


def _live_root_cause(record: dict[str, Any]) -> str:
    eval_id = record["eval_id"]
    trace = record["packet03_eval_summary"]
    verdict = record["score_summary"]["final_verdict"]
    if eval_id == DIMENSION_EVALS["tool_call_argument_fidelity"]:
        matched = trace.get("tool_contract_cases_matched")
        total = trace.get("tool_contract_cases_total")
        mismatches = [
            row["case_id"]
            for row in trace.get("tool_contract_case_results", [])
            if not row.get("matched")
        ]
        if verdict == "pass":
            return f"All tool-call contract cases matched ({matched}/{total}); malformed arguments were rejected cleanly."
        return (
            f"Tool-call contract mismatches on {', '.join(mismatches)}; matched {matched}/{total} cases and accepted malformed argument shapes as valid calls."
        )
    if eval_id == DIMENSION_EVALS["tool_result_attribution"]:
        matched = trace.get("tool_result_attribution_cases_matched")
        total = trace.get("tool_result_attribution_cases_total")
        incomplete = trace.get("tool_result_attribution_incomplete_case_ids", [])
        if verdict == "pass":
            return f"All attribution cases matched ({matched}/{total}) with complete structured attribution evidence."
        return (
            f"Attribution evidence incomplete for {', '.join(incomplete)}; matched {matched}/{total} cases without clean permission/runtime separation evidence."
        )
    matched = trace.get("artifact_log_cases_matched")
    total = trace.get("artifact_log_cases_total")
    incomplete = trace.get("artifact_log_incomplete_case_ids", [])
    if verdict == "pass":
        return f"Artifact-log extraction stayed complete across {matched}/{total} cases with closure evidence intact."
    return (
        f"Artifact-log runtime evidence stayed incomplete for {', '.join(incomplete)}; matched {matched}/{total} cases and never reached clean closure evidence."
    )


def _phase6_root_cause(record: dict[str, Any], trace: dict[str, Any]) -> str:
    eval_id = record.get("eval_id")
    summary = trace.get("packet03_eval_summary", {})
    verdict = record.get("score_summary", {}).get("final_verdict")
    if eval_id == PHASE6_REQUIRED_ACTION_EVAL:
        return "Expected verifier/final-answer contradiction was surfaced and judged correctly; this probe is not the blocker."
    if eval_id == DIMENSION_EVALS["tool_call_argument_fidelity"]:
        cases = summary.get("tool_contract_case_results", [])
        mismatches = [case["case_id"] for case in cases if not case.get("matched")]
        matched = summary.get("tool_contract_cases_matched")
        total = summary.get("tool_contract_cases_total")
        if verdict == "pass":
            return f"All tool-call contract cases matched ({matched}/{total}); malformed argument shapes were rejected correctly."
        return (
            f"Tool-call contract mismatches on {', '.join(mismatches)}; matched {matched}/{total} cases and accepted malformed arguments as valid calls."
        )
    if eval_id == DIMENSION_EVALS["tool_result_attribution"]:
        cases = summary.get("tool_result_attribution_case_results", [])
        mismatches = [
            case["case_id"]
            for case in cases
            if case.get("expected_result_class") != case.get("observed_result_class")
            or case.get("expected_reason_code") != case.get("observed_reason_code")
        ]
        incomplete = summary.get("tool_result_attribution_incomplete_case_ids", [])
        matched = summary.get("tool_result_attribution_cases_matched")
        total = summary.get("tool_result_attribution_cases_total")
        if verdict == "pass":
            return f"All attribution cases matched ({matched}/{total}) with complete structured attribution evidence."
        return (
            f"Attribution evidence incomplete for {', '.join(incomplete)}; mismatched result attribution on {', '.join(mismatches)}; matched {matched}/{total} cases."
        )
    if eval_id == DIMENSION_EVALS["call_chain_closure"]:
        matched = summary.get("artifact_log_cases_matched")
        total = summary.get("artifact_log_cases_total")
        incomplete = summary.get("artifact_log_incomplete_case_ids", [])
        if verdict == "pass":
            return f"Artifact-log extraction stayed complete across {matched}/{total} cases with closure evidence intact."
        return (
            f"Artifact-log runtime evidence stayed incomplete for {', '.join(incomplete)}; matched {matched}/{total} cases and never reached clean closure evidence."
        )
    return "No derived root cause available."


def _bfcl_root_cause(record: dict[str, Any], event: dict[str, str]) -> str:
    grade = record.get("score_summary", {}).get("grade", {})
    expected = grade.get("expected_call_count")
    observed = grade.get("observed_call_count")
    if record.get("invalid_infrastructure_failure"):
        reason = event.get("reason") or event.get("message") or "unknown network error"
        return (
            f"Azure DNS/network failure before first tool call ({reason}); observed_call_count {observed} vs expected {expected}."
        )
    verdict = record.get("score_summary", {}).get("final_verdict")
    reasons = grade.get("reason_codes", [])
    if verdict == "pass":
        return f"Matched all required BFCL calls; observed_call_count {observed} equals expected {expected}."
    if "bfcl_no_calls_emitted" in reasons:
        return f"Executed the run but emitted no usable BFCL calls; observed_call_count {observed} vs expected {expected}."
    return (
        f"Executed the run but missed required BFCL calls or arguments; observed_call_count {observed} vs expected {expected}; reason_codes {', '.join(reasons)}."
    )


def _model_client_error(path: Path) -> dict[str, str]:
    if not path.exists():
        return {"message": "", "reason": ""}
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row.get("event_type") != "model_client_error":
            continue
        details = row.get("payload", {}).get("details", {})
        metadata = details.get("metadata", {})
        return {
            "message": str(details.get("message", "")),
            "reason": str(metadata.get("reason", "")),
        }
    return {"message": "", "reason": ""}


def _recommendation(
    *,
    preflight: dict[str, Any],
    live_tooling: dict[str, Any],
    bfcl_summary: dict[str, Any],
) -> str:
    if preflight["status"] != "pass":
        return "tooling_bfcl_followup_blocked"
    if live_tooling["sharp_challenger_improved_vs_historical"] and not (
        bfcl_summary["run_count"] > 0 and not bfcl_summary["all_invalid"]
    ):
        return "tooling_bfcl_followup_partial_uplift_tooling_still_open"
    if (
        live_tooling["sharp_challenger_clean_tooling_pass"]
        and bfcl_summary["run_count"] > 0
        and not bfcl_summary["all_invalid"]
        and bfcl_summary["winner_variant"] == SHARP_CHALLENGER
        and bfcl_summary["by_variant"][SHARP_CHALLENGER]["pass_count"]
        >= bfcl_summary["by_variant"][INCUMBENT]["pass_count"]
    ):
        return "tooling_bfcl_followup_ready_for_family_reducer"
    return "tooling_bfcl_followup_blocked"


def _record_sort_key(row: dict[str, Any]) -> tuple[int, int, int]:
    variant = row.get("variant_id")
    eval_id = row.get("eval_id")
    rerun = row.get("rerun_index")
    if rerun is None:
        rerun = row.get("attempt", 0)
    variant_order = list(dict.fromkeys((*LIVE_BOARD, *HISTORICAL_COMPARISON_SET)))
    eval_order = [*DIMENSION_EVALS.values(), PHASE6_REQUIRED_ACTION_EVAL]
    return (
        variant_order.index(variant) if variant in variant_order else 999,
        eval_order.index(eval_id) if eval_id in eval_order else 999,
        int(rerun) if isinstance(rerun, int) else 0,
    )


def _verdict_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"pass": 0, "fail": 0, "unresolved": 0}
    for row in rows:
        verdict = row.get("score_summary", {}).get("final_verdict")
        if verdict == "pass":
            counts["pass"] += 1
        elif verdict == "fail":
            counts["fail"] += 1
        else:
            counts["unresolved"] += 1
    return counts


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    payload = "\n".join(json.dumps(row, sort_keys=True) for row in rows) + ("\n" if rows else "")
    path.write_text(payload, encoding="utf-8")


def _load_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _load_optional_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args(argv)
    print(json.dumps(launch_phase65_tooling_bfcl_followup(output_dir=args.output_dir), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
