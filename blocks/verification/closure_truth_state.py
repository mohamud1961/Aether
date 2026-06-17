"""Helpers for authoritative completion-closure state."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

_PATH_RE = re.compile(r"(?:/app/)?[A-Za-z0-9_./-]+\.(?:json|txt|csv|sh|md)")
_VERIFIER_HINT_RE = re.compile(r"(verify|pytest|unittest|reward)", re.IGNORECASE)


def build_closure_state(task: str, workspace_state: dict[str, Any]) -> dict[str, Any]:
    contract = workspace_state.get("closure_contract")
    contract = dict(contract) if isinstance(contract, dict) else {}
    cwd = Path(str(workspace_state.get("cwd", "."))).resolve()
    required_paths = required_paths_from_task(task, contract)
    actual_paths = actual_paths_from_workspace(cwd)
    actual_written_paths = written_paths(actual_paths, contract.get("initial_workspace_fingerprints"))
    verifier_attempts = verifier_attempts_from_execution(workspace_state.get("execution_result"), cwd)
    latest_verifier = verifier_attempts[-1] if verifier_attempts else None
    final_text = final_text_from_execution(workspace_state.get("execution_result"))
    path_mismatches = [path for path in required_paths if path not in {row["app_path"] for row in actual_paths}]
    blockers = blockers_from_state(contract, path_mismatches, verifier_attempts, latest_verifier, final_text, required_paths)
    projection = final_answer_projection(final_text, required_paths, latest_verifier)
    status = closure_status(blockers, actual_written_paths, latest_verifier, contract)
    return {
        "schema_version": "phase65_completion_closure_state.v1",
        "status": status,
        "required_deliverables": list(contract.get("required_deliverables", required_paths)),
        "required_artifact_paths": required_paths,
        "actual_written_paths": actual_written_paths,
        "actual_workspace_paths": actual_paths,
        "verifier_attempts": verifier_attempts,
        "latest_verifier_result": latest_verifier,
        "unresolved_blockers": blockers,
        "final_answer_projection": projection,
        "path_mismatches": path_mismatches,
        "reason_codes": reason_codes(blockers, path_mismatches, latest_verifier, actual_written_paths),
    }


def required_paths_from_task(task: str, contract: dict[str, Any]) -> list[str]:
    explicit = contract.get("required_artifact_paths")
    if isinstance(explicit, list) and explicit:
        return [str(path) for path in explicit if isinstance(path, str) and path]
    seen: set[str] = set()
    ordered: list[str] = []
    for match in _PATH_RE.finditer(task or ""):
        path = match.group(0)
        if not path.startswith("/app/"):
            path = f"/app/{path.lstrip('/')}"
        if path not in seen:
            seen.add(path)
            ordered.append(path)
    return ordered


def actual_paths_from_workspace(cwd: Path) -> list[dict[str, Any]]:
    rows = []
    for path in sorted(p for p in cwd.rglob("*") if p.is_file()):
        rel = path.relative_to(cwd).as_posix()
        rows.append({"app_path": f"/app/{rel}", "workspace_path": str(path), "fingerprint": fingerprint(path)})
    return rows


def written_paths(actual_paths: list[dict[str, Any]], initial: Any) -> list[str]:
    initial_map = dict(initial) if isinstance(initial, dict) else {}
    return [
        row["app_path"]
        for row in actual_paths
        if initial_map.get(row["app_path"].removeprefix("/app/")) != row["fingerprint"]
    ]


def verifier_attempts_from_execution(execution_result: Any, cwd: Path) -> list[dict[str, Any]]:
    attempts: list[dict[str, Any]] = []
    steps = execution_result.get("steps", []) if isinstance(execution_result, dict) else []
    for step in steps:
        for result in step.get("results", []):
            command = str(result.get("command", ""))
            if not _VERIFIER_HINT_RE.search(command):
                continue
            exit_code = result.get("exit_code", 1)
            if not isinstance(exit_code, int):
                try:
                    exit_code = int(exit_code)
                except Exception:
                    exit_code = 1
            attempts.append(
                {
                    "step": step.get("step"),
                    "command": command,
                    "status": "pass" if exit_code == 0 else "fail",
                    "exit_code": exit_code,
                    "stdout": str(result.get("stdout", "")),
                    "stderr": str(result.get("stderr", "")),
                    "normalized_command": command.replace(str(cwd), "/app"),
                }
            )
    return attempts


def final_text_from_execution(execution_result: Any) -> str:
    completion = execution_result.get("last_completion") if isinstance(execution_result, dict) else None
    if isinstance(completion, dict) and isinstance(completion.get("text"), str):
        return completion["text"]
    return ""


def final_answer_projection(final_text: str, required_paths: list[str], latest_verifier: dict[str, Any] | None) -> dict[str, Any]:
    lowered = final_text.lower()
    path_mentions = {path: path in final_text or path.removeprefix("/app/") in final_text for path in required_paths}
    verifier_mentioned = latest_verifier is None or "pass" in lowered or "fail" in lowered or "verify" in lowered
    return {
        "artifact_paths_mentioned": all(path_mentions.values()) if path_mentions else True,
        "artifact_path_mentions": path_mentions,
        "verifier_outcome_mentioned": verifier_mentioned,
        "final_text": final_text,
    }


def blockers_from_state(
    contract: dict[str, Any],
    path_mismatches: list[str],
    verifier_attempts: list[dict[str, Any]],
    latest_verifier: dict[str, Any] | None,
    final_text: str,
    required_paths: list[str],
) -> list[str]:
    blockers = []
    projection = final_answer_projection(final_text, required_paths, latest_verifier)
    if path_mismatches:
        blockers.append("required_artifact_missing")
    if contract.get("requires_verifier") and not verifier_attempts:
        blockers.append("verifier_not_attempted")
    if latest_verifier and latest_verifier["status"] != "pass":
        blockers.append("verifier_latest_failed")
    if not projection["artifact_paths_mentioned"]:
        blockers.append("final_answer_missing_artifact_path")
    if contract.get("requires_verifier") and not projection["verifier_outcome_mentioned"]:
        blockers.append("final_answer_missing_verifier_evidence")
    return blockers


def closure_status(
    blockers: list[str],
    actual_written_paths: list[str],
    latest_verifier: dict[str, Any] | None,
    contract: dict[str, Any],
) -> str:
    if not blockers and (actual_written_paths or not contract.get("required_artifact_paths")):
        return "solved"
    if actual_written_paths or latest_verifier is not None:
        return "partial"
    return "blocked"


def reason_codes(
    blockers: list[str],
    path_mismatches: list[str],
    latest_verifier: dict[str, Any] | None,
    actual_written_paths: list[str],
) -> list[str]:
    codes: list[str] = []
    if path_mismatches:
        codes.append("closure_required_artifact_missing")
    if blockers and "verifier_latest_failed" in blockers:
        codes.append("closure_verifier_failed")
    if blockers and "final_answer_missing_artifact_path" in blockers:
        codes.append("closure_evidence_omission")
    if not actual_written_paths and latest_verifier is None:
        codes.append("closure_no_material_progress")
    if not codes and blockers:
        codes.append("closure_state_blocked")
    return codes


def fingerprint(path: Path) -> str:
    if path.stat().st_size > 5_000_000:
        return f"large:{path.stat().st_size}"
    return hashlib.sha256(path.read_bytes()).hexdigest()
