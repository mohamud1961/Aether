"""Authoritative closure/task-truth state for Phase 6.5 follow-up 2."""

from __future__ import annotations

import re
from typing import Any

from .closure_truth_state import (
    actual_paths_from_workspace,
    final_text_from_execution,
    required_paths_from_task,
    written_paths,
)
from .verifier_episode_parser import parse_verifier_attempts

_VERIFY_EXEC_RE = re.compile(
    r"(?:(?:^|[;&|]\s*|&&\s*|\|\|\s*)(?:bash|sh)\s+\S*verify[^ \n;&|]*\.sh\b)|"
    r"(?:(?:^|[;&|]\s*|&&\s*|\|\|\s*)\S*verify[^ \n;&|]*\.sh\b)|"
    r"(?:\bpython(?:3)?\s+-m\s+pytest\b)|(?:\bpytest\b)|(?:\bpython(?:3)?\s+-m\s+unittest\b)|(?:\bunittest\b)"
)
_EXIT_RE = re.compile(r"(?:VERIFY_EXIT|EXIT):(?P<code>-?\d+)")


def build_followup2_closure_state(task: str, workspace_state: dict[str, Any]) -> dict[str, Any]:
    contract = dict(workspace_state.get("closure_contract") or {})
    cwd = str(workspace_state.get("cwd", "."))
    required_paths = required_paths_from_task(task, contract)
    actual_paths = actual_paths_from_workspace(__import__("pathlib").Path(cwd).resolve())
    actual_written = written_paths(actual_paths, contract.get("initial_workspace_fingerprints"))
    attempts = _verifier_attempts(workspace_state.get("execution_result"), cwd)
    latest = attempts[-1] if attempts else None
    final_text = final_text_from_execution(workspace_state.get("execution_result"))
    mismatches = [path for path in required_paths if path not in {row["app_path"] for row in actual_paths}]
    projection = _final_projection(final_text, required_paths, latest)
    repair_status = _repair_status(contract, attempts, actual_written)
    blockers = _blockers(contract, mismatches, attempts, latest, projection, repair_status)
    closure_status = _closure_status(blockers, actual_written, latest)
    reason_codes = _reason_codes(blockers, mismatches, latest, actual_written, repair_status)
    return {
        "schema_version": "phase65_completion_followup2_state.v1",
        "closure_contract_status": closure_status,
        "task_truth_status": str(workspace_state.get("task_truth_status", "ungraded")),
        "required_deliverables": list(contract.get("required_deliverables", required_paths)),
        "required_artifact_paths": required_paths,
        "actual_written_paths": actual_written,
        "actual_workspace_paths": actual_paths,
        "verifier_attempts": attempts,
        "latest_verifier_result": latest,
        "unresolved_blockers": blockers,
        "final_answer_projection": projection,
        "path_mismatches": mismatches,
        "verifier_repair_status": repair_status,
        "reason_codes": reason_codes,
        "status": closure_status,
    }


def _verifier_attempts(execution_result: Any, cwd: str) -> list[dict[str, Any]]:
    return parse_verifier_attempts(execution_result, cwd=str(cwd), verify_exec_re=_VERIFY_EXEC_RE, exit_re=_EXIT_RE)


def _final_projection(final_text: str, required_paths: list[str], latest: dict[str, Any] | None) -> dict[str, Any]:
    lowered = final_text.lower()
    path_mentions = {path: path in final_text or path.removeprefix("/app/") in final_text for path in required_paths}
    verifier_mentioned = latest is None or "verify" in lowered or "pass" in lowered or "fail" in lowered
    blocker_mentioned = any(token in lowered for token in ("blocker", "open", "not complete", "not closing", "missing"))
    return {
        "artifact_paths_mentioned": all(path_mentions.values()) if path_mentions else True,
        "artifact_path_mentions": path_mentions,
        "verifier_outcome_mentioned": verifier_mentioned,
        "blocker_state_mentioned": blocker_mentioned,
        "final_text": final_text,
    }


def _repair_status(contract: dict[str, Any], attempts: list[dict[str, Any]], actual_written: list[str]) -> str:
    if not contract.get("requires_verifier"):
        return "not_required"
    if not attempts:
        return "not_attempted"
    had_failure = any(row["status"] == "fail" for row in attempts)
    latest = attempts[-1]
    if latest["status"] == "pass" and had_failure and actual_written:
        return "repaired_and_reran_to_pass"
    if latest["status"] == "pass" and had_failure:
        return "reran_to_pass"
    if latest["status"] == "pass":
        return "pass_without_repair"
    if had_failure and len(attempts) == 1:
        return "failed_without_rerun"
    if had_failure and actual_written:
        return "repaired_but_still_failing"
    return "still_failing"


def _blockers(
    contract: dict[str, Any],
    mismatches: list[str],
    attempts: list[dict[str, Any]],
    latest: dict[str, Any] | None,
    projection: dict[str, Any],
    repair_status: str,
) -> list[str]:
    blockers: list[str] = []
    if mismatches:
        blockers.append("required_artifact_missing")
    if contract.get("requires_verifier") and not attempts:
        blockers.append("verifier_not_attempted")
    if latest and latest["status"] != "pass":
        blockers.append("verifier_latest_failed")
    if contract.get("requires_verifier") and repair_status == "failed_without_rerun":
        blockers.append("verifier_repair_loop_incomplete")
    if not projection["artifact_paths_mentioned"]:
        blockers.append("final_answer_missing_artifact_path")
    if contract.get("requires_verifier") and not projection["verifier_outcome_mentioned"]:
        blockers.append("final_answer_missing_verifier_evidence")
    return blockers


def _closure_status(blockers: list[str], actual_written: list[str], latest: dict[str, Any] | None) -> str:
    if not blockers:
        return "pass"
    if actual_written or latest is not None:
        return "partial"
    return "blocked"


def _reason_codes(
    blockers: list[str],
    mismatches: list[str],
    latest: dict[str, Any] | None,
    actual_written: list[str],
    repair_status: str,
) -> list[str]:
    codes: list[str] = []
    if mismatches:
        codes.append("closure_required_artifact_missing")
    if latest and latest["status"] != "pass":
        codes.append("closure_verifier_failed")
    if "final_answer_missing_artifact_path" in blockers or "final_answer_missing_verifier_evidence" in blockers:
        codes.append("closure_evidence_omission")
    if repair_status == "failed_without_rerun":
        codes.append("closure_repair_loop_incomplete")
    if not actual_written and latest is None:
        codes.append("closure_no_material_progress")
    return codes or ["closure_contract_pass"]
