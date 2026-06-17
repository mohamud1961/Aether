from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .closure_truth_state import actual_paths_from_workspace, final_text_from_execution, required_paths_from_task, written_paths
from .verifier_episode_parser import parse_verifier_attempts

_VERIFY_EXEC_RE = re.compile(
    r"(?:(?:^|[;&|]\s*|&&\s*|\|\|\s*)(?:bash|sh)\s+\S*verify[^ \n;&|]*\.sh\b)|"
    r"(?:(?:^|[;&|]\s*|&&\s*|\|\|\s*)\S*verify[^ \n;&|]*\.sh\b)|"
    r"(?:\bpython(?:3)?\s+-m\s+pytest\b)|(?:\bpytest\b)|(?:\bpython(?:3)?\s+-m\s+unittest\b)|(?:\bunittest\b)"
)
_EXIT_RE = re.compile(r"(?:VERIFY_EXIT|EXIT):(?P<code>-?\d+)")
_PATH_RE = re.compile(r"(?:/app/)?[A-Za-z0-9_./-]+\.(?:json|txt|csv|sh|md|html)")


def build_followup3_closure_state(task: str, workspace_state: dict[str, Any]) -> dict[str, Any]:
    contract = dict(workspace_state.get("closure_contract") or {})
    cwd = Path(str(workspace_state.get("cwd", "."))).resolve()
    required_paths = required_paths_from_task(task, contract)
    actual_paths = actual_paths_from_workspace(cwd)
    actual_written = written_paths(actual_paths, contract.get("initial_workspace_fingerprints"))
    attempts = _verifier_attempts(workspace_state.get("execution_result"), str(cwd))
    latest = attempts[-1] if attempts else None
    final_text = final_text_from_execution(workspace_state.get("execution_result"))
    actual_set = {row["app_path"] for row in actual_paths}
    path_mismatches = [path for path in required_paths if path not in actual_set]
    target_resolution = _target_resolution(required_paths, actual_set, actual_written)
    wrong_target_writes = sorted({hit for row in target_resolution for hit in row["sibling_written_paths"]})
    projection = _final_projection(final_text, required_paths, latest, str(cwd))
    repair_status = _repair_status(contract, attempts, actual_written)
    blockers = _blockers(contract, path_mismatches, wrong_target_writes, attempts, latest, projection, repair_status)
    closure_status = "pass" if not blockers else ("partial" if actual_written or latest else "blocked")
    reason_codes = _reason_codes(blockers, path_mismatches, wrong_target_writes, latest, actual_written, repair_status)
    return {
        "schema_version": "phase65_completion_followup3_state.v1",
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
        "required_target_resolution": target_resolution,
        "wrong_target_written_paths": wrong_target_writes,
        "path_mismatches": path_mismatches,
        "verifier_repair_status": repair_status,
        "reason_codes": reason_codes,
        "status": closure_status,
    }


def _verifier_attempts(execution_result: Any, cwd: str) -> list[dict[str, Any]]:
    return parse_verifier_attempts(execution_result, cwd=cwd, verify_exec_re=_VERIFY_EXEC_RE, exit_re=_EXIT_RE)


def _target_resolution(required_paths: list[str], actual_set: set[str], actual_written: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for required in required_paths:
        basename = required.rsplit("/", 1)[-1]
        sibling_written = sorted(path for path in actual_written if path != required and path.rsplit("/", 1)[-1] == basename)
        rows.append(
            {
                "required_path": required,
                "exists_in_workspace": required in actual_set,
                "written_in_workspace": required in actual_written,
                "sibling_written_paths": sibling_written,
            }
        )
    return rows


def _final_projection(final_text: str, required_paths: list[str], latest: dict[str, Any] | None, cwd: str) -> dict[str, Any]:
    lowered = final_text.lower()
    mentioned = _mentioned_paths(final_text, cwd)
    required_set = set(required_paths)
    mentions = {path: path in mentioned for path in required_paths}
    latest_truth_ok = True
    if latest is not None:
        expected = latest["status"]
        has_verifier = "verifier" in lowered or "verify" in lowered
        pass_mentioned = "pass" in lowered
        fail_mentioned = "fail" in lowered
        expected_mentioned = pass_mentioned if expected == "pass" else fail_mentioned
        contradictory = bool(re.search(r"latest\s+(?:verifier\s+)?(?:status\s+)?(?:is\s+)?fail", lowered)) if expected == "pass" else bool(
            re.search(r"latest\s+(?:verifier\s+)?(?:status\s+)?(?:is\s+)?pass", lowered)
        )
        latest_truth_ok = bool(has_verifier and expected_mentioned and not contradictory)
    return {
        "required_artifact_paths_mentioned": all(mentions.values()) if mentions else True,
        "required_artifact_path_mentions": mentions,
        "latest_truthful_verifier_state_mentioned": latest_truth_ok,
        "mentioned_paths": sorted(mentioned),
        "non_required_path_mentions": sorted(path for path in mentioned if path not in required_set),
        "final_text": final_text,
    }


def _mentioned_paths(text: str, cwd: str) -> set[str]:
    prefix = cwd.rstrip("/")
    paths: set[str] = set()
    for match in _PATH_RE.finditer(text):
        token = match.group(0).rstrip(".,;:)]}")
        if token.startswith("/app/"):
            paths.add(token)
        elif token.startswith("/") and prefix and token.startswith(prefix):
            paths.add(f"/app/{token[len(prefix):].lstrip('/')}")
        else:
            paths.add(f"/app/{token.lstrip('/')}")
    return paths


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
    return "still_failing"


def _blockers(contract: dict[str, Any], mismatches: list[str], wrong_writes: list[str], attempts: list[dict[str, Any]], latest: dict[str, Any] | None, projection: dict[str, Any], repair_status: str) -> list[str]:
    blockers: list[str] = []
    if mismatches:
        blockers.append("required_artifact_missing")
    if wrong_writes:
        blockers.append("wrong_target_path_write_detected")
    if contract.get("requires_verifier") and not attempts:
        blockers.append("verifier_not_attempted")
    if latest and latest["status"] != "pass":
        blockers.append("verifier_latest_failed")
    if contract.get("requires_verifier") and repair_status == "failed_without_rerun":
        blockers.append("verifier_repair_loop_incomplete")
    if not projection["required_artifact_paths_mentioned"]:
        blockers.append("final_answer_missing_required_target_path")
    if contract.get("requires_verifier") and not projection["latest_truthful_verifier_state_mentioned"]:
        blockers.append("final_answer_missing_or_incorrect_latest_verifier_state")
    return blockers


def _reason_codes(blockers: list[str], mismatches: list[str], wrong_writes: list[str], latest: dict[str, Any] | None, actual_written: list[str], repair_status: str) -> list[str]:
    codes: list[str] = []
    if mismatches:
        codes.append("closure_required_artifact_missing")
    if wrong_writes:
        codes.append("closure_wrong_target_write_detected")
    if latest and latest["status"] != "pass":
        codes.append("closure_verifier_failed")
    if repair_status == "failed_without_rerun":
        codes.append("closure_repair_loop_incomplete")
    if any(code.startswith("final_answer_") for code in blockers):
        codes.append("closure_evidence_omission")
    if not actual_written and latest is None:
        codes.append("closure_no_material_progress")
    return codes or ["closure_contract_pass"]
