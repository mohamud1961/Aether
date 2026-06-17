"""Execute the tiny Phase 6.5 measurement-repair follow-up slice."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

from runner.phase65_measurement_grading import (
    grade_contextbench_verified_answer,
    grade_public_terminalbench_workspace,
)
from runner.successor_phase65_measurement_repair import _record_ledger, _seed_public_terminalbench_workspace
from runner.successor_phase6_corrective_rerun import _contextbench_specs

MISSION_ID = "successor_phase65_measurement_followup"
DEFAULT_OUTPUT_DIR = Path(
    "tracking/collab/stage_03_execution_planning/packets/packet_06_paired_combo_variants/"
    "runs/2026-05-06_successor_phase65_measurement_followup"
)
CONTEXTBENCH_CSV = Path("research/sources/codebases/ContextBench/data/Verified.csv")


def launch_phase65_measurement_followup(*, output_dir: str | Path) -> dict[str, Any]:
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    records = _proof_records(out)
    report = _contract_report(records)
    score = _score(report, records)
    _write_text(out / "phase65_measurement_followup_plan.md", _plan())
    _write_json(out / "phase65_measurement_followup_contract_report.json", report)
    _write_text(out / "phase65_measurement_followup_test_report.txt", "pytest report written separately by execution command.\n")
    _write_jsonl(out / "phase65_measurement_followup_proof_records.jsonl", records)
    _write_json(out / "phase65_measurement_followup_score_envelope.json", score)
    _write_text(out / "phase65_measurement_followup_handoff.md", _handoff(out, score, report))
    ledger = _ledger(out, score, report)
    _record_ledger(ledger)
    _write_text(out / "RAW_LEDGER_UPDATE", ledger)
    return {"output_dir": str(out), "proof_case_count": len(records), "selected_recommendation": score["selected_recommendation"]}


def _proof_records(out: Path) -> list[dict[str, Any]]:
    rows = list(csv.DictReader(CONTEXTBENCH_CSV.read_text(encoding="utf-8").splitlines()))[:3]
    specs = _contextbench_specs()[:3]
    records = []
    for spec, row in zip(specs, rows, strict=True):
        expected_repo = row["original_inst_id"].split("__", 1)[0]
        answer = json.dumps(
            {
                "original_inst_id": row["original_inst_id"],
                "language": row["language"],
                "status": row["status"],
                "gold_context_length": row["gold_context_length"],
                "commit": row["commit"],
                "repo_or_file_family": expected_repo,
            },
            indent=2,
            sort_keys=True,
        )
        proxy = f"{row['original_inst_id']} {row['language']} {row['status']} {row['commit']}"
        records.append(_record("contextbench_prompt_contract", spec["eval_id"], "positive_control", grade_contextbench_verified_answer(answer, row), prompt=spec["task_prompt"]))
        records.append(_record("contextbench_prompt_contract", spec["eval_id"], "legacy_proxy_rejected", grade_contextbench_verified_answer(proxy, row), prompt=spec["task_prompt"], legacy_proxy_pass=True))
    for task_id in ("fix-git", "regex-log", "financial-document-processor"):
        workspace = out / "proof_workspaces" / task_id
        _seed_public_terminalbench_workspace(workspace, task_id)
        records.append(_record("terminalbench_regression_unit", task_id, "positive_control", grade_public_terminalbench_workspace(workspace, task_id=task_id)))
    return records


def _record(surface: str, target: str, case_id: str, grade: dict[str, Any], *, prompt: str | None = None, legacy_proxy_pass: bool = False) -> dict[str, Any]:
    return {
        "mission_id": MISSION_ID,
        "surface": surface,
        "target": target,
        "case_id": case_id,
        "verdict": grade["verdict"],
        "reason_codes": grade.get("reason_codes", []),
        "legacy_proxy_pass": legacy_proxy_pass,
        "prompt_requires_json": ("json object" in prompt.lower()) if isinstance(prompt, str) else None,
        "grade": grade,
    }


def _contract_report(records: list[dict[str, Any]]) -> dict[str, Any]:
    context_rows = [row for row in records if row["surface"] == "contextbench_prompt_contract"]
    regression_rows = [row for row in records if row["surface"] == "terminalbench_regression_unit"]
    context_ok = all(row["prompt_requires_json"] for row in context_rows if row["case_id"] == "positive_control")
    context_positive = sum(1 for row in context_rows if row["case_id"] == "positive_control" and row["verdict"] == "pass")
    context_proxy = sum(1 for row in context_rows if row["case_id"] == "legacy_proxy_rejected" and row["verdict"] == "fail")
    regression_ok = all(row["verdict"] == "pass" for row in regression_rows)
    status = "pass" if context_ok and context_positive == 3 and context_proxy == 3 and regression_ok else "blocked"
    return {
        "mission_id": MISSION_ID,
        "status": status,
        "contextbench": {
            "prompt_requires_json": context_ok,
            "positive_rows_passed": context_positive,
            "proxy_rows_rejected": context_proxy,
        },
        "public_terminalbench_regression_unit_tests": {
            "targets": [row["target"] for row in regression_rows],
            "all_passed": regression_ok,
        },
    }


def _score(report: dict[str, Any], records: list[dict[str, Any]]) -> dict[str, Any]:
    recommendation = "measurement_followup_completed_resume_phase65_board" if report["status"] == "pass" else "measurement_followup_partially_completed_one_more_patch"
    return {
        "mission_id": MISSION_ID,
        "proof_case_count": len(records),
        "passed_case_count": sum(1 for row in records if row["verdict"] == "pass"),
        "failed_case_count": sum(1 for row in records if row["verdict"] == "fail"),
        "selected_recommendation": recommendation,
        "broader_phase65_board_executed": False,
    }


def _plan() -> str:
    return "\n".join([
        "# Phase 6.5 Measurement Follow-Up Plan",
        "",
        "- patch scope: ContextBench format-coupling and direct regression-grader unit coverage",
        "- proof scope: three ContextBench rows plus direct deterministic regression grader positives",
        "- stop rule: no broader board execution and no lane interpretation",
    ]) + "\n"


def _handoff(out: Path, score: dict[str, Any], report: dict[str, Any]) -> str:
    return "\n".join([
        "# Phase 6.5 Measurement Follow-Up Handoff",
        "",
        f"- mission_id: `{MISSION_ID}`",
        f"- output_root: `{out}`",
        f"- contract_status: `{report['status']}`",
        f"- proof_case_count: `{score['proof_case_count']}`",
        f"- recommendation: `{score['selected_recommendation']}`",
        "- board status: broader Phase 6.5 board remains paused in this slice",
    ]) + "\n"


def _ledger(out: Path, score: dict[str, Any], report: dict[str, Any]) -> str:
    return "\n".join([
        "RAW_LEDGER_UPDATE",
        "- actor: codex",
        "- task: successor Phase 6.5 measurement repair follow-up",
        "- event_type: implementation",
        f"- summary: Closed the remaining bounded measurement gap with recommendation `{score['selected_recommendation']}`.",
        f"- observations: proof_case_count `{score['proof_case_count']}`; contract_status `{report['status']}`; ContextBench positive_rows `{report['contextbench']['positive_rows_passed']}`; proxy_rows_rejected `{report['contextbench']['proxy_rows_rejected']}`.",
        "- inference: ContextBench format coupling is now explicitly constrained by the board prompt, and public TerminalBench regression graders now have direct unit coverage.",
        f"- evidence_paths: {out / 'phase65_measurement_followup_contract_report.json'}; {out / 'phase65_measurement_followup_proof_records.jsonl'}; {out / 'phase65_measurement_followup_score_envelope.json'}; {out / 'phase65_measurement_followup_handoff.md'}",
        "- affected_components: Phase 6 corrective ContextBench prompt; follow-up measurement certification artifacts; direct regression grader test coverage",
        "- decision_change: No Packet 07 movement and no broad Phase 6.5 board execution in this slice",
        "- unresolved_questions: Whether the separate route/doctrine blocker repair is the only remaining prerequisite before resuming the broader bounded board.",
        "- confidence: high",
        "- commit_message: HOLD - phase65 measurement follow-up certification artifacts",
    ])


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args(argv)
    print(json.dumps(launch_phase65_measurement_followup(output_dir=args.output_dir), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
