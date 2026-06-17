"""Merged follow-up 4 closure state: keep repair projection, add exact-target guard."""

from __future__ import annotations

import re
from typing import Any

from .followup3_closure_truth_state import build_followup3_closure_state


def build_followup4_closure_state(task: str, workspace_state: dict[str, Any]) -> dict[str, Any]:
    state = dict(build_followup3_closure_state(task, workspace_state))
    contract = dict(workspace_state.get("closure_contract") or {})
    required_paths = list(state.get("required_artifact_paths", []))
    latest = state.get("latest_verifier_result")
    final_text = str(dict(state.get("final_answer_projection") or {}).get("final_text", ""))
    projection = _final_projection(final_text, required_paths, latest)
    blockers = _merged_blockers(state.get("unresolved_blockers", []), contract, projection)
    actual_written = list(state.get("actual_written_paths", []))
    closure_status = "pass" if not blockers else ("partial" if actual_written or latest else "blocked")
    state["schema_version"] = "phase65_completion_followup4_state.v1"
    state["final_answer_projection"] = projection
    state["unresolved_blockers"] = blockers
    state["closure_contract_status"] = closure_status
    state["status"] = closure_status
    state["reason_codes"] = _reason_codes(
        blockers=blockers,
        mismatches=list(state.get("path_mismatches", [])),
        wrong_writes=list(state.get("wrong_target_written_paths", [])),
        latest=latest,
        actual_written=actual_written,
        repair_status=str(state.get("verifier_repair_status", "")),
    )
    state["verifier_episode_summary"] = _verifier_episode_summary(list(state.get("verifier_attempts", [])))
    return state


def _final_projection(final_text: str, required_paths: list[str], latest: dict[str, Any] | None) -> dict[str, Any]:
    lowered = final_text.lower()
    path_mentions = {path: path in final_text or path.removeprefix("/app/") in final_text for path in required_paths}
    verifier_mentioned = True
    if latest is not None:
        expected = str(latest.get("status", ""))
        expected_mentioned = expected in lowered
        contradictory = bool(re.search(r"latest\s+(?:verifier\s+)?(?:status\s+)?(?:is\s+)?fail", lowered)) if expected == "pass" else bool(
            re.search(r"latest\s+(?:verifier\s+)?(?:status\s+)?(?:is\s+)?pass", lowered)
        )
        verifier_mentioned = expected_mentioned and not contradictory
    blocker_mentioned = any(token in lowered for token in ("blocker", "open", "not complete", "not closing", "missing"))
    return {
        "artifact_paths_mentioned": all(path_mentions.values()) if path_mentions else True,
        "artifact_path_mentions": path_mentions,
        "verifier_outcome_mentioned": verifier_mentioned,
        "blocker_state_mentioned": blocker_mentioned,
        "final_text": final_text,
    }


def _merged_blockers(existing: list[str], contract: dict[str, Any], projection: dict[str, Any]) -> list[str]:
    blockers = [
        code
        for code in existing
        if code not in {"final_answer_missing_required_target_path", "final_answer_missing_or_incorrect_latest_verifier_state"}
    ]
    if not projection["artifact_paths_mentioned"]:
        blockers.append("final_answer_missing_artifact_path")
    if contract.get("requires_verifier") and not projection["verifier_outcome_mentioned"]:
        blockers.append("final_answer_missing_verifier_evidence")
    return _dedupe(blockers)


def _reason_codes(
    *,
    blockers: list[str],
    mismatches: list[str],
    wrong_writes: list[str],
    latest: dict[str, Any] | None,
    actual_written: list[str],
    repair_status: str,
) -> list[str]:
    codes: list[str] = []
    if mismatches:
        codes.append("closure_required_artifact_missing")
    if wrong_writes:
        codes.append("closure_wrong_target_write_detected")
    if latest and latest.get("status") != "pass":
        codes.append("closure_verifier_failed")
    if repair_status == "failed_without_rerun":
        codes.append("closure_repair_loop_incomplete")
    if any(code.startswith("final_answer_") for code in blockers):
        codes.append("closure_evidence_omission")
    if not actual_written and latest is None:
        codes.append("closure_no_material_progress")
    return codes or ["closure_contract_pass"]


def _verifier_episode_summary(attempts: list[dict[str, Any]]) -> dict[str, int]:
    groups: dict[str, int] = {}
    for row in attempts:
        key = f"{row.get('step')}:{row.get('result_index')}"
        groups[key] = groups.get(key, 0) + 1
    return {
        "attempt_count": len(attempts),
        "shell_result_count": len(groups),
        "multi_verifier_shell_results": sum(1 for count in groups.values() if count > 1),
    }


def _dedupe(values: list[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered
