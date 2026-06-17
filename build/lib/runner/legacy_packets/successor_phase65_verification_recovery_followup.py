"""Reduce Phase 6.5 completion follow-up evidence into verification/recovery outputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from runner.successor_phase6_corrective_rerun import _record_ledger, _write_json, _write_jsonl, _write_text

MISSION_ID = "successor_phase65_verification_recovery_followup"
SOURCE_MISSION_ID = "successor_phase65_completion_followup4"
SOURCE_OUTPUT_DIR = Path(
    "tracking/collab/stage_03_execution_planning/packets/packet_06_paired_combo_variants/"
    "runs/2026-05-07_successor_phase65_completion_followup4_rerun2"
)
DEFAULT_OUTPUT_DIR = Path(
    "tracking/collab/stage_03_execution_planning/packets/packet_06_paired_combo_variants/"
    "runs/2026-05-07_successor_phase65_verification_recovery_followup"
)
RESULT_RECORDS = "phase65_completion_followup4_result_records.jsonl"
SOURCE_SCORE = "phase65_completion_followup4_score_envelope.json"
SOURCE_REPORT = "phase65_completion_followup4_report.json"
SOURCE_FAILURE = "phase65_completion_followup4_failure_source_report.json"
RECOMMENDATIONS = (
    "verification_recovery_followup_ready_for_family_reducer",
    "verification_recovery_followup_partial_uplift_verification_still_open",
    "verification_recovery_followup_blocked",
)


def launch_phase65_verification_recovery_followup(
    *,
    output_dir: str | Path,
    source_dir: str | Path = SOURCE_OUTPUT_DIR,
    execute: bool = True,
) -> dict[str, Any]:
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    source = Path(source_dir).resolve()
    preflight = _preflight(source)
    if not execute or preflight["status"] != "pass":
        return _write_blocked(out, preflight=preflight, execute=execute)
    records = _load_records(source / RESULT_RECORDS)
    source_score = _read_json(source / SOURCE_SCORE)
    source_report = _read_json(source / SOURCE_REPORT)
    source_failure = _read_json(source / SOURCE_FAILURE)
    _write_jsonl(out / "phase65_verification_recovery_followup_result_records.jsonl", records)
    score = _score(records, source_score=source_score)
    report = _report(out, source, records, score, source_score=source_score, source_report=source_report)
    trace = _trace_report(records)
    failure = _failure_report(records, source_failure=source_failure)
    _write_json(out / "phase65_verification_recovery_followup_score_envelope.json", score)
    _write_json(out / "phase65_verification_recovery_followup_report.json", report)
    _write_json(out / "phase65_verification_recovery_followup_trace_report.json", trace)
    _write_json(out / "phase65_verification_recovery_followup_failure_source_report.json", failure)
    _write_text(out / "phase65_verification_recovery_followup_deep_trace_analysis.md", _deep_trace_analysis(out, score, report, trace, failure))
    _write_text(out / "phase65_verification_recovery_followup_handoff.md", _handoff(out, source, score, preflight))
    ledger = _ledger(out, source, score, failure)
    _record_ledger(ledger)
    _write_text(out / "RAW_LEDGER_UPDATE", ledger)
    return {"output_dir": str(out), "source_dir": str(source), "run_count": len(records), "selected_recommendation": score["selected_recommendation"]}


def _preflight(source: Path) -> dict[str, Any]:
    required = [RESULT_RECORDS, SOURCE_SCORE, SOURCE_REPORT, SOURCE_FAILURE]
    missing = [name for name in required if not (source / name).exists()]
    return {"mission_id": MISSION_ID, "source_dir": str(source), "status": "pass" if not missing else "blocked", "missing_source_artifacts": missing}


def _load_records(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _score(records: list[dict[str, Any]], *, source_score: dict[str, Any]) -> dict[str, Any]:
    verification_rows = [row for row in records if _verification_owned(row)]
    truthful_partials = [row for row in verification_rows if _truthful_partial(row)]
    disciplined_repairs = [row for row in verification_rows if _disciplined_repair_pass(row)]
    verifier_failures = [row for row in verification_rows if row.get("failure_source") == "verifier_failure"]
    evidence_omissions = [row for row in verification_rows if _has_final_answer_blocker(row)]
    verification_blocked_rows = [row for row in verification_rows if row["closure_contract_status"] == "blocked"]
    verification_partial_rows = [row for row in verification_rows if row["closure_contract_status"] == "partial"]
    external_failures = [row for row in records if row.get("failure_source") == "raw_task_capability_limit"]
    multi_verifier_shell_results = sum(_multi_verifier_shell_results(row) for row in verification_rows)
    verifier_ready_variants = sorted({row["variant_id"] for row in disciplined_repairs if row["closure_contract_status"] == "pass" and row["task_truth_status"] == "pass"})
    partial_truthful_variants = sorted({row["variant_id"] for row in truthful_partials})
    ready = bool(verification_rows) and bool(verifier_ready_variants) and not verifier_failures and not verification_partial_rows and not verification_blocked_rows and not source_score.get("invalid_run_count", 0)
    partial = bool(verification_rows) and (bool(verifier_ready_variants) or bool(truthful_partials))
    selected = RECOMMENDATIONS[0] if ready else RECOMMENDATIONS[1] if partial else RECOMMENDATIONS[2]
    return {
        "mission_id": MISSION_ID,
        "source_mission_id": SOURCE_MISSION_ID,
        "source_selected_recommendation": source_score.get("selected_recommendation"),
        "run_count": len(records),
        "source_split_ready": bool(source_score.get("split_ready", False)),
        "verification_run_count": len(verification_rows),
        "verification_eval_ids": sorted({row["eval_id"] for row in verification_rows}),
        "verifier_ready_variants": verifier_ready_variants,
        "truthful_partial_variant_ids": partial_truthful_variants,
        "truthful_partial_count": len(truthful_partials),
        "verification_partial_count": len(verification_partial_rows),
        "verification_blocked_count": len(verification_blocked_rows),
        "repair_discipline_pass_count": len(disciplined_repairs),
        "multi_verifier_shell_results": multi_verifier_shell_results,
        "verifier_failure_count": len(verifier_failures),
        "closure_evidence_omission_count": len(evidence_omissions),
        "external_raw_task_capability_limit_count": len(external_failures),
        "owned_failure_count": len(verifier_failures) + len(verification_blocked_rows) + len(verification_partial_rows),
        "selected_recommendation": selected,
    }


def _report(
    out: Path,
    source: Path,
    records: list[dict[str, Any]],
    score: dict[str, Any],
    *,
    source_score: dict[str, Any],
    source_report: dict[str, Any],
) -> dict[str, Any]:
    verification_rows = [row for row in records if _verification_owned(row)]
    external_failures = [row for row in records if row.get("failure_source") == "raw_task_capability_limit"]
    return {
        "mission_id": MISSION_ID,
        "source_output_root": str(source),
        "source_completion_recommendation": source_score.get("selected_recommendation"),
        "comparison_set": list(source_report.get("comparison_set", [])),
        "carry_forward_baseline_variant": source_report.get("carry_forward_baseline_variant"),
        "merged_variant": source_report.get("merged_variant"),
        "verification_required_eval_ids": score["verification_eval_ids"],
        "verifier_ready_variants": score["verifier_ready_variants"],
        "truthful_partial_variant_ids": score["truthful_partial_variant_ids"],
        "external_failure_eval_ids": sorted({row["eval_id"] for row in external_failures}),
        "verification_records": verification_rows,
        "external_failures": external_failures,
        "deep_trace_artifact": str(out / "phase65_verification_recovery_followup_deep_trace_analysis.md"),
    }


def _trace_report(records: list[dict[str, Any]]) -> dict[str, Any]:
    traces = []
    for row in records:
        closure_state = dict(row.get("closure_state") or {})
        traces.append(
            {
                "run_id": row["run_id"],
                "eval_id": row["eval_id"],
                "variant_id": row["variant_id"],
                "verification_owned_signal": _verification_owned(row),
                "closure_contract_status": row["closure_contract_status"],
                "task_truth_status": row["task_truth_status"],
                "truth_split_class": f"{row['closure_contract_status']}__{row['task_truth_status']}",
                "verifier_repair_status": closure_state.get("verifier_repair_status"),
                "verifier_attempt_count": len(closure_state.get("verifier_attempts", [])),
                "latest_verifier_result": closure_state.get("latest_verifier_result"),
                "unresolved_blockers": closure_state.get("unresolved_blockers", []),
                "failure_source": row.get("failure_source"),
            }
        )
    return {"mission_id": MISSION_ID, "run_count": len(records), "traces": traces}


def _failure_report(records: list[dict[str, Any]], *, source_failure: dict[str, Any]) -> dict[str, Any]:
    owned_failures = [row for row in records if _verification_owned(row) and row.get("failure_source") == "verifier_failure"]
    external_failures = [row for row in records if row.get("failure_source") == "raw_task_capability_limit"]
    return {
        "mission_id": MISSION_ID,
        "source_failure_count": int(source_failure.get("failure_count", 0) or 0),
        "owned_failure_count": len(owned_failures),
        "owned_failures": owned_failures,
        "external_failure_count": len(external_failures),
        "external_failure_counts_by_source": _counts(row.get("failure_source") for row in external_failures),
        "external_failures": external_failures,
    }


def _deep_trace_analysis(out: Path, score: dict[str, Any], report: dict[str, Any], trace: dict[str, Any], failure: dict[str, Any]) -> str:
    truthful_partials = [row for row in trace.get("traces", []) if row["verification_owned_signal"] and row["closure_contract_status"] == "partial" and row["task_truth_status"] == "pass"]
    lines = [
        "# Phase 6.5 Verification Recovery Follow-up Deep Trace Analysis",
        "",
        f"- mission_id: `{MISSION_ID}`",
        f"- output_root: `{out}`",
        f"- source_output_root: `{report['source_output_root']}`",
        "- scope_lock: verification/recovery only; completion outputs treated as read-only evidence; no Packet 07 movement.",
        f"- source_completion_recommendation: `{score.get('source_selected_recommendation')}`",
        "",
        "## Verification Findings",
        "",
        f"- verification_run_count: `{score.get('verification_run_count', 0)}`",
        f"- repair_discipline_pass_count: `{score.get('repair_discipline_pass_count', 0)}`",
        f"- verifier_ready_variants: `{score.get('verifier_ready_variants', [])}`",
        f"- verifier_failure_count: `{score.get('verifier_failure_count', 0)}`",
        "",
        "## Truthful Partial Reporting",
        "",
        f"- truthful_partial_count: `{score.get('truthful_partial_count', 0)}`",
        f"- truthful_partial_variant_ids: `{score.get('truthful_partial_variant_ids', [])}`",
        f"- partial_rows_with_explicit_blockers: `{len(truthful_partials)}`",
        f"- verification_blocked_count: `{score.get('verification_blocked_count', 0)}`",
        f"- multi_verifier_shell_results: `{score.get('multi_verifier_shell_results', 0)}`",
        "",
        "## External Failure Boundary",
        "",
        f"- external_raw_task_capability_limit_count: `{score.get('external_raw_task_capability_limit_count', 0)}`",
        f"- source_failure_count: `{failure.get('source_failure_count', 0)}`",
        "- interpretation_rule: raw task capability limits remain visible in the family report but do not count as verification/recovery-owned regressions when closure truth and failure typing are correct.",
        "",
        "## Per-Run Trace Review",
        "",
    ]
    for row in report.get("verification_records", []):
        lines.extend(_format_run_trace(row, verification_owned=True))
    for row in report.get("external_failures", []):
        lines.extend(_format_run_trace(row, verification_owned=False))
    other_rows = [
        row
        for row in trace.get("traces", [])
        if row["run_id"] not in {record["run_id"] for record in report.get("verification_records", [])}
        and row["run_id"] not in {record["run_id"] for record in report.get("external_failures", [])}
    ]
    if other_rows:
        lines.extend(["## Other Passing Completion-Carryforward Rows", ""])
        for row in other_rows:
            lines.extend(
                [
                    f"### `{row['run_id']}`",
                    f"- eval_id: `{row['eval_id']}`",
                    f"- variant_id: `{row['variant_id']}`",
                    f"- result: `{row['truth_split_class']}`",
                    f"- root_cause: `{_root_cause_from_trace_row(row)}`",
                    "",
                ]
            )
    lines.extend(
        [
            "## Decision",
            "",
            f"- selected_recommendation: `{score.get('selected_recommendation')}`",
        ]
    )
    return "\n".join(lines) + "\n"


def _format_run_trace(row: dict[str, Any], *, verification_owned: bool) -> list[str]:
    closure_state = dict(row.get("closure_state") or {})
    latest = dict(closure_state.get("latest_verifier_result") or {})
    attempts = list(closure_state.get("verifier_attempts", []))
    lines = [
        f"### `{row['run_id']}`",
        f"- eval_id: `{row['eval_id']}`",
        f"- variant_id: `{row['variant_id']}`",
        f"- verification_owned_signal: `{verification_owned}`",
        f"- closure_contract_status: `{row['closure_contract_status']}`",
        f"- task_truth_status: `{row['task_truth_status']}`",
        f"- failure_source: `{row.get('failure_source')}`",
        f"- verifier_repair_status: `{closure_state.get('verifier_repair_status')}`",
        f"- verifier_attempt_count: `{len(attempts)}`",
        f"- latest_verifier_status: `{latest.get('status')}`",
        f"- unresolved_blockers: `{closure_state.get('unresolved_blockers', [])}`",
        f"- task_truth_reason_codes: `{closure_state.get('task_truth_reason_codes', [])}`",
        f"- root_cause: `{_root_cause_from_record(row)}`",
        f"- interpretation: `{_interpretation_from_record(row)}`",
        "",
    ]
    return lines


def _root_cause_from_record(row: dict[str, Any]) -> str:
    closure_state = dict(row.get("closure_state") or {})
    blockers = list(closure_state.get("unresolved_blockers", []))
    task_reasons = list(closure_state.get("task_truth_reason_codes", []))
    failure_source = str(row.get("failure_source") or "none")
    repair_status = str(closure_state.get("verifier_repair_status") or "unknown")
    if row["task_truth_status"] == "pass" and row["closure_contract_status"] == "pass":
        if repair_status == "repaired_and_reran_to_pass":
            return "verifier_fail_then_repair_rerun_succeeded"
        return "clean_pass_no_verification_regression"
    if failure_source == "raw_task_capability_limit":
        return ",".join(task_reasons or ["raw_task_capability_limit"])
    if blockers:
        return ",".join(blockers)
    if failure_source != "none":
        return failure_source
    return "no_explicit_failure_root_cause_recorded"


def _interpretation_from_record(row: dict[str, Any]) -> str:
    closure_state = dict(row.get("closure_state") or {})
    repair_status = str(closure_state.get("verifier_repair_status") or "unknown")
    if row["closure_contract_status"] == "partial" and row["task_truth_status"] == "pass":
        return "truthful partial: work product and latest verifier were sufficient for task truth, but closure reporting omitted required evidence."
    if row.get("failure_source") == "raw_task_capability_limit":
        return "external capability failure: closure contract was satisfied, but grader rejected task truth on benchmark semantics outside verification/recovery ownership."
    if repair_status == "repaired_and_reran_to_pass":
        return "verification-ready path: verifier failure was repaired, rerun, and closed truthfully."
    if row["task_truth_status"] == "pass":
        return "clean pass with no owned verification/recovery issue."
    return "non-pass row requires further investigation."


def _root_cause_from_trace_row(row: dict[str, Any]) -> str:
    blockers = list(row.get("unresolved_blockers", []))
    failure_source = str(row.get("failure_source") or "none")
    if blockers:
        return ",".join(blockers)
    return failure_source if failure_source != "none" else "clean_pass_no_verification_regression"


def _handoff(out: Path, source: Path, score: dict[str, Any], preflight: dict[str, Any]) -> str:
    artifacts = [
        "phase65_verification_recovery_followup_score_envelope.json",
        "phase65_verification_recovery_followup_report.json",
        "phase65_verification_recovery_followup_trace_report.json",
        "phase65_verification_recovery_followup_failure_source_report.json",
        "phase65_verification_recovery_followup_deep_trace_analysis.md",
        "phase65_verification_recovery_followup_handoff.md",
        "RAW_LEDGER_UPDATE",
    ]
    rows = [
        "# Phase 6.5 Verification Recovery Follow-up Handoff",
        "",
        f"- mission_id: `{MISSION_ID}`",
        f"- output_root: `{out}`",
        f"- source_output_root: `{source}`",
        f"- preflight_status: `{preflight['status']}`",
        f"- selected_recommendation: `{score['selected_recommendation']}`",
        f"- verifier_ready_variants: `{score.get('verifier_ready_variants', [])}`",
        f"- truthful_partial_variant_ids: `{score.get('truthful_partial_variant_ids', [])}`",
        "",
        "## Final Artifact Set",
        "",
    ]
    rows.extend(f"- `{name}`" for name in artifacts)
    return "\n".join(rows) + "\n"


def _ledger(out: Path, source: Path, score: dict[str, Any], failure: dict[str, Any]) -> str:
    return "\n".join(
        [
            "RAW_LEDGER_UPDATE",
            "- actor: codex",
            "- task: successor Phase 6.5 verification recovery follow-up execution",
            "- event_type: implementation",
            f"- summary: Reduced `{SOURCE_MISSION_ID}` evidence into verification/recovery family artifacts with recommendation `{score['selected_recommendation']}`.",
            (
                "- observations: "
                f"verification_run_count `{score.get('verification_run_count', 0)}`; "
                f"repair_discipline_pass_count `{score.get('repair_discipline_pass_count', 0)}`; "
                f"truthful_partial_count `{score.get('truthful_partial_count', 0)}`; "
                f"external_raw_task_capability_limit_count `{score.get('external_raw_task_capability_limit_count', 0)}`."
            ),
            "- inference: verification/recovery readiness is carried by variants that rerun verifier-backed repairs to a passing latest state, while non-winning variants still provide truthful partial reporting instead of false closure.",
            (
                f"- evidence_paths: {out / 'phase65_verification_recovery_followup_score_envelope.json'}; "
                f"{out / 'phase65_verification_recovery_followup_trace_report.json'}; "
                f"{out / 'phase65_verification_recovery_followup_deep_trace_analysis.md'}; "
                f"{source / SOURCE_REPORT}"
            ),
            "- affected_components: verification/recovery follow-up reducer; phase65 family reporting; recovery interface discipline",
            "- decision_change: Added a dedicated verification/recovery family reducer that interprets completion follow-up evidence without reopening completion ownership.",
            "- unresolved_questions: Whether future verification-owned variants should convert the truthful partial verifier rows into full closure passes without changing completion scope.",
            "- confidence: medium",
            "- commit_message: HOLD - add verification recovery follow-up reducer and artifact synthesis",
        ]
    )


def _write_blocked(out: Path, *, preflight: dict[str, Any], execute: bool) -> dict[str, Any]:
    score = {"mission_id": MISSION_ID, "run_count": 0, "selected_recommendation": RECOMMENDATIONS[2], "preflight": preflight}
    report = {"mission_id": MISSION_ID, "blocked": True, "execute": execute, "source_output_root": preflight["source_dir"]}
    trace = {"mission_id": MISSION_ID, "blocked": True, "run_count": 0, "traces": []}
    failure = {"mission_id": MISSION_ID, "blocked": True, "owned_failure_count": 0, "external_failure_count": 0}
    _write_json(out / "phase65_verification_recovery_followup_score_envelope.json", score)
    _write_json(out / "phase65_verification_recovery_followup_report.json", report)
    _write_json(out / "phase65_verification_recovery_followup_trace_report.json", trace)
    _write_json(out / "phase65_verification_recovery_followup_failure_source_report.json", failure)
    _write_text(out / "phase65_verification_recovery_followup_deep_trace_analysis.md", _deep_trace_analysis(out, score, {"source_output_root": preflight["source_dir"]}, trace, {"source_failure_count": 0}))
    _write_text(out / "phase65_verification_recovery_followup_handoff.md", _handoff(out, Path(preflight["source_dir"]), score, preflight))
    ledger = _ledger(out, Path(preflight["source_dir"]), score, {"source_failure_count": 0})
    _record_ledger(ledger)
    _write_text(out / "RAW_LEDGER_UPDATE", ledger)
    return {"output_dir": str(out), "run_count": 0, "selected_recommendation": RECOMMENDATIONS[2], "blocked": True}


def _verification_owned(row: dict[str, Any]) -> bool:
    closure_state = dict(row.get("closure_state") or {})
    required = set(closure_state.get("required_deliverables", []))
    return "/app/verify.sh" in required or bool(closure_state.get("verifier_attempts")) or closure_state.get("verifier_repair_status") not in {None, "", "not_required"}


def _truthful_partial(row: dict[str, Any]) -> bool:
    closure_state = dict(row.get("closure_state") or {})
    latest = dict(closure_state.get("latest_verifier_result") or {})
    return row["closure_contract_status"] == "partial" and row["task_truth_status"] == "pass" and bool(closure_state.get("unresolved_blockers")) and latest.get("status") == "pass"


def _disciplined_repair_pass(row: dict[str, Any]) -> bool:
    closure_state = dict(row.get("closure_state") or {})
    latest = dict(closure_state.get("latest_verifier_result") or {})
    return closure_state.get("verifier_repair_status") == "repaired_and_reran_to_pass" and latest.get("status") == "pass"


def _has_final_answer_blocker(row: dict[str, Any]) -> bool:
    blockers = list(dict(row.get("closure_state") or {}).get("unresolved_blockers", []))
    return any(str(code).startswith("final_answer_") for code in blockers)


def _multi_verifier_shell_results(row: dict[str, Any]) -> int:
    attempts = list(dict(row.get("closure_state") or {}).get("verifier_attempts", []))
    groups: dict[str, int] = {}
    for attempt in attempts:
        key = f"{attempt.get('step')}:{attempt.get('result_index')}"
        groups[key] = groups.get(key, 0) + 1
    return sum(1 for count in groups.values() if count > 1)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _counts(values: Any) -> dict[str, int]:
    out: dict[str, int] = {}
    for value in values:
        key = str(value)
        out[key] = out.get(key, 0) + 1
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--source-dir", default=str(SOURCE_OUTPUT_DIR))
    parser.add_argument("--no-execute", action="store_true")
    args = parser.parse_args(argv)
    result = launch_phase65_verification_recovery_followup(output_dir=args.output_dir, source_dir=args.source_dir, execute=not args.no_execute)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
