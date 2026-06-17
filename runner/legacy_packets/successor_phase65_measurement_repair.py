"""Execute the bounded successor Phase 6.5 measurement-repair slice."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from runner.phase65_measurement_contracts import (
    load_extract_moves_contract,
    load_financial_document_contract,
)
from runner.phase65_measurement_grading import (
    grade_contextbench_verified_answer,
    grade_extract_moves_workspace,
    grade_public_terminalbench_workspace,
)

MISSION_ID = "successor_phase65_measurement_repair"
CONTROL = "spb_01"
INCUMBENT = "spb_tooling_seed_plus_receipt_and_completion_01"
TERMINALBENCH_ROOT = Path("/Users/mohamud/Downloads/terminalbench/official_tasks")
CONTEXTBENCH_CSV = Path("research/sources/codebases/ContextBench/data/Verified.csv")
PRIOR_RUN_ROOT = Path(
    "tracking/collab/stage_03_execution_planning/packets/packet_06_paired_combo_variants/"
    "runs/2026-05-06_successor_phase6_corrective_rerun/runs"
)
DEFAULT_OUTPUT_DIR = Path(
    "tracking/collab/stage_03_execution_planning/packets/packet_06_paired_combo_variants/"
    "runs/2026-05-06_successor_phase65_measurement_repair"
)
RECOMMENDATIONS = (
    "measurement_repair_completed_resume_phase65_board",
    "measurement_repair_partially_completed_one_more_repair_slice",
    "measurement_repair_still_blocked",
)


def launch_phase65_measurement_repair(*, output_dir: str | Path) -> dict[str, Any]:
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    records = _proof_records(out)
    contract_matrix = _contract_matrix(records)
    score = _score(records, contract_matrix)
    trace = _trace_report(records)
    cost = _cost_report(records)
    _write_text(out / "phase65_measurement_repair_plan.md", _plan())
    _write_text(out / "phase65_measurement_repair_scope_report.md", _scope_report())
    _write_json(out / "phase65_measurement_repair_contract_matrix.json", contract_matrix)
    _write_text(out / "phase65_measurement_repair_test_report.txt", "pytest report written separately by execution command.\n")
    _write_jsonl(out / "phase65_measurement_repair_proof_records.jsonl", records)
    _write_json(out / "phase65_measurement_repair_score_envelope.json", score)
    _write_json(out / "phase65_measurement_repair_trace_report.json", trace)
    _write_json(out / "phase65_measurement_repair_cost_report.json", cost)
    _write_text(out / "phase65_measurement_repair_handoff.md", _handoff(out, score, contract_matrix))
    ledger = _ledger(out, score)
    _record_ledger(ledger)
    _write_text(out / "RAW_LEDGER_UPDATE", ledger)
    return {
        "output_dir": str(out),
        "proof_case_count": len(records),
        "selected_recommendation": score["selected_recommendation"],
    }


def _proof_records(out: Path) -> list[dict[str, Any]]:
    row = next(csv.DictReader(CONTEXTBENCH_CSV.read_text(encoding="utf-8").splitlines()))
    records = []
    records.extend(_contextbench_records(row))
    records.extend(_extract_moves_records(out))
    for task_id in ("fix-git", "regex-log", "financial-document-processor"):
        records.extend(_public_terminalbench_records(out, task_id))
    return records


def _contextbench_records(row: dict[str, str]) -> list[dict[str, Any]]:
    expected_repo = row["original_inst_id"].split("__", 1)[0]
    passing = json.dumps(
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
    pass_grade = grade_contextbench_verified_answer(passing, row)
    proxy_grade = grade_contextbench_verified_answer(proxy, row)
    return [
        _record("contextbench", "positive_control", pass_grade, legacy_proxy_pass=False),
        _record("contextbench", "legacy_proxy_rejected", proxy_grade, legacy_proxy_pass=True),
    ]


def _extract_moves_records(out: Path) -> list[dict[str, Any]]:
    good = out / "proof_workspaces/extract_moves_pass"
    bad = _old_proxy_workspace("*terminalbench_extract_moves_repaired_closure*")
    _reset_dir(good)
    contract = load_extract_moves_contract(str(TERMINALBENCH_ROOT / "extract-moves-from-video"))
    (good / "solution.txt").write_text(contract["expected_solution"], encoding="utf-8")
    return [
        _record("extract-moves-from-video", "positive_control", grade_extract_moves_workspace(good, task_id="extract-moves-from-video"), legacy_proxy_pass=False, workspace=good),
        _record("extract-moves-from-video", "old_proxy_pass_now_fail", grade_extract_moves_workspace(bad, task_id="extract-moves-from-video"), legacy_proxy_pass=True, workspace=bad),
    ]


def _public_terminalbench_records(out: Path, task_id: str) -> list[dict[str, Any]]:
    good = out / "proof_workspaces" / f"{task_id}_pass"
    _seed_public_terminalbench_workspace(good, task_id)
    bad = _old_proxy_workspace(f"*terminalbench_public_{task_id}*")
    return [
        _record(task_id, "positive_control", grade_public_terminalbench_workspace(good, task_id=task_id), legacy_proxy_pass=False, workspace=good),
        _record(task_id, "old_proxy_pass_now_fail", grade_public_terminalbench_workspace(bad, task_id=task_id), legacy_proxy_pass=True, workspace=bad),
    ]


def _seed_public_terminalbench_workspace(workspace: Path, task_id: str) -> None:
    _reset_dir(workspace)
    if task_id == "fix-git":
        resources = TERMINALBENCH_ROOT / task_id / "environment/resources/patch_files"
        about = resources / "about.md"
        default = resources / "default.html"
        _copy_text(about, workspace / "resources/patch_files/about.md")
        _copy_text(default, workspace / "resources/patch_files/default.html")
        _copy_text(about, workspace / "personal-site/_includes/about.md")
        _copy_text(default, workspace / "personal-site/_layouts/default.html")
        return
    if task_id == "regex-log":
        solution = (TERMINALBENCH_ROOT / task_id / "solution/solve.sh").read_text(encoding="utf-8")
        pattern = solution.split("cat << 'EOF' > /app/regex.txt\n", 1)[1].split("\nEOF", 1)[0]
        (workspace / "regex.txt").write_text(pattern + "\n", encoding="utf-8")
        return
    if task_id == "financial-document-processor":
        _seed_financial_workspace(workspace)
        return
    raise ValueError(f"unsupported_task:{task_id}")


def _seed_financial_workspace(workspace: Path) -> None:
    contracts = load_financial_document_contract(str(TERMINALBENCH_ROOT / "financial-document-processor"))
    documents_root = TERMINALBENCH_ROOT / "financial-document-processor/environment/documents"
    invoices_dir = workspace / "invoices"
    other_dir = workspace / "other"
    documents_dir = workspace / "documents"
    invoices_dir.mkdir(parents=True, exist_ok=True)
    other_dir.mkdir(parents=True, exist_ok=True)
    documents_dir.mkdir(parents=True, exist_ok=True)
    expected_data = contracts["expected_data"]
    rows = []
    for source in sorted(documents_root.iterdir()):
        digest = _sha512(source)
        if digest in contracts["invoice_hashes"]:
            destination = invoices_dir / source.name
            shutil.copy2(source, destination)
            item = expected_data[digest]
            rows.append(
                {
                    "filename": source.name,
                    "total_amount": f"{float(item['total_amount']):.2f}",
                    "vat_amount": "" if item["vat_amount"] == "" else f"{float(item['vat_amount']):.2f}",
                }
            )
        elif digest in contracts["other_hashes"]:
            shutil.copy2(source, other_dir / source.name)
    rows.append(
        {
            "filename": "total",
            "total_amount": f"{float(expected_data['total']['total_amount']):.2f}",
            "vat_amount": f"{float(expected_data['total']['vat_amount']):.2f}",
        }
    )
    with (invoices_dir / "summary.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["filename", "total_amount", "vat_amount"])
        writer.writeheader()
        writer.writerows(rows)


def _old_proxy_workspace(pattern: str) -> Path:
    for score_path in PRIOR_RUN_ROOT.glob(f"{pattern}/score_envelope.json"):
        score = json.loads(score_path.read_text(encoding="utf-8"))
        if score.get("aggregate", {}).get("final_verdict") == "pass":
            workspace = score_path.parent / "workspace"
            if workspace.exists():
                return workspace
    raise FileNotFoundError(f"old_proxy_workspace_missing:{pattern}")


def _contract_matrix(records: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for target in ("contextbench", "extract-moves-from-video", "fix-git", "regex-log", "financial-document-processor"):
        subset = [row for row in records if row["target"] == target]
        positive = any(row["case_id"] == "positive_control" and row["verdict"] == "pass" for row in subset)
        proxy = any(row["case_id"] != "positive_control" and row["verdict"] == "fail" and row["legacy_proxy_pass"] for row in subset)
        rows.append({"target": target, "contract_implemented": True, "positive_control_passed": positive, "old_proxy_pass_now_fails": proxy, "status": "pass" if positive and proxy else "blocked"})
    status = "pass" if all(row["status"] == "pass" for row in rows) else "blocked"
    return {"mission_id": MISSION_ID, "status": status, "rows": rows}


def _score(records: list[dict[str, Any]], matrix: dict[str, Any]) -> dict[str, Any]:
    selected = "measurement_repair_completed_resume_phase65_board" if matrix["status"] == "pass" else "measurement_repair_partially_completed_one_more_repair_slice"
    return {
        "mission_id": MISSION_ID,
        "proof_case_count": len(records),
        "passed_case_count": sum(1 for row in records if row["verdict"] == "pass"),
        "failed_case_count": sum(1 for row in records if row["verdict"] == "fail"),
        "selected_recommendation": selected,
        "control": CONTROL,
        "incumbent": INCUMBENT,
        "lane_winner_interpretation_authorized": False,
    }


def _trace_report(records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "mission_id": MISSION_ID,
        "proof_cases": records,
        "by_target": {
            target: [row["reason_codes"] for row in records if row["target"] == target]
            for target in sorted({row["target"] for row in records})
        },
    }


def _cost_report(records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "mission_id": MISSION_ID,
        "model_backed_runs": 0,
        "local_deterministic_proof_cases": len(records),
        "usd_estimate": 0.0,
    }


def _record(target: str, case_id: str, grade: dict[str, Any], *, legacy_proxy_pass: bool, workspace: Path | None = None) -> dict[str, Any]:
    return {
        "mission_id": MISSION_ID,
        "target": target,
        "case_id": case_id,
        "verdict": grade["verdict"],
        "reason_codes": grade.get("reason_codes", []),
        "legacy_proxy_pass": legacy_proxy_pass,
        "workspace_ref": str(workspace) if workspace is not None else None,
        "grade": grade,
    }


def _plan() -> str:
    return "\n".join([
        "# Phase 6.5 Measurement Repair Plan",
        "",
        "- scope: repair grading only",
        "- surfaces: ContextBench-style grading, extract-moves closure, public TerminalBench regression",
        "- proof: positive deterministic controls plus old proxy-pass rejection cases",
        "- stop rule: no lane interpretation and no broader board execution",
    ]) + "\n"


def _scope_report() -> str:
    return "\n".join([
        "# Phase 6.5 Measurement Repair Scope Report",
        "",
        "- broader Phase 6.5 board remains out of scope for this slice",
        "- this slice rewires only the blocked Track 0 grading surfaces",
        "- proof is deterministic and artifact-aware; no benchmark authority claims are made here",
    ]) + "\n"


def _handoff(out: Path, score: dict[str, Any], matrix: dict[str, Any]) -> str:
    return "\n".join([
        "# Phase 6.5 Measurement Repair Handoff",
        "",
        f"- mission_id: `{MISSION_ID}`",
        f"- output_root: `{out}`",
        f"- contract_matrix_status: `{matrix['status']}`",
        f"- proof_case_count: `{score['proof_case_count']}`",
        f"- recommendation: `{score['selected_recommendation']}`",
        "- lane interpretation: not authorized in this slice",
    ]) + "\n"


def _ledger(out: Path, score: dict[str, Any]) -> str:
    return "\n".join([
        "RAW_LEDGER_UPDATE",
        "- actor: codex",
        "- task: successor Phase 6.5 measurement repair",
        "- event_type: implementation",
        f"- summary: Repaired the bounded Phase 6.5 Track 0 grading surfaces and produced deterministic proof artifacts with recommendation `{score['selected_recommendation']}`.",
        f"- observations: proof_case_count `{score['proof_case_count']}`; passed_case_count `{score['passed_case_count']}`; failed_case_count `{score['failed_case_count']}`.",
        "- inference: The measurement slice now uses artifact-aware or contract-aware grading instead of snippet-only proxy passing on the targeted surfaces.",
        f"- evidence_paths: {out / 'phase65_measurement_repair_contract_matrix.json'}; {out / 'phase65_measurement_repair_proof_records.jsonl'}; {out / 'phase65_measurement_repair_score_envelope.json'}; {out / 'phase65_measurement_repair_handoff.md'}",
        "- affected_components: Phase 6.5 measurement grading; successor Phase 6 corrective grading dispatch; bounded proof artifacts",
        "- decision_change: No Packet 07 movement and no lane-winner interpretation in this slice",
        "- unresolved_questions: Whether any non-measurement route or doctrine blockers still need a separate bounded repair before the broader board resumes.",
        "- confidence: high",
        "- commit_message: HOLD - phase65 measurement repair contracts and proof artifacts",
    ])


def _record_ledger(raw: str) -> None:
    import subprocess

    proc = subprocess.run([sys.executable, "tracking/ledger/tools/record_update.py"], input=raw, text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr)


def _reset_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _copy_text(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")


def _sha512(path: Path) -> str:
    import hashlib

    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha512").hexdigest()


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
    print(json.dumps(launch_phase65_measurement_repair(output_dir=args.output_dir), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
