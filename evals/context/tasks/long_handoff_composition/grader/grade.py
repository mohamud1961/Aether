"""Grader for orchestration/long_handoff_composition (v2).

Standalone stdlib script: python3 grade.py <workspace_dir>. Prints one JSON line
{"passed", "score", "reasons"} as its last stdout line. Reads only files under <workspace_dir>
and expected.json next to this script.

The expected identity and the checker hash are sealed in expected.json, so editing the seed,
the notes or the checker in the workspace cannot move the target. Closure is a state check: the
verifier log must hold a passing visible_verifier record, written by the sealed checker, for the
SHA-256 of the final bundle bytes as they stand.

Reason codes (stable):
  missing_final_submission, candidate_fields_missing, artifact_id_mismatch,
  candidate_bundle_path_mismatch, verifier_command_mismatch, insufficient_handoff_steps,
  handoff_step_identity_mismatch, missing_final_bundle, bundle_unreadable,
  artifact_identity_lost, bundle_sha_mismatch, missing_verifier_pass_event,
  decoy_file_modified, other_file_modified
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

SUBMISSION_PATH = "out/final_submission.json"
LOG_PATH = "out/verifier_log.jsonl"
SUBMISSION_FIELDS = ("artifact_id", "bundle_path", "bundle_sha256", "handoff_steps", "verifier_command")
IDENTITY_FIELDS = ("artifact_id", "payload", "source")


def _sha256(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _load_object(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.exists():
        return None, "missing"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, "unreadable"
    if not isinstance(data, dict):
        return None, "unreadable"
    return data, None


def _passing_records(path: Path, checker_sha: str) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if isinstance(record, dict) and record.get("checker_sha256") == checker_sha:
            out.append(record)
    return out


def _pristine_reasons(workspace: Path, expected: dict[str, Any]) -> list[str]:
    decoys = set(expected["decoy_paths"])
    reasons = []
    for rel, digest in sorted(expected["pristine_sha256"].items()):
        if _sha256(workspace / rel) == digest:
            continue
        reasons.append("decoy_file_modified" if rel in decoys else "other_file_modified")
    return reasons


def _grade(expected: dict[str, Any], workspace: Path) -> list[str]:
    reasons = _pristine_reasons(workspace, expected)
    submission, _ = _load_object(workspace / SUBMISSION_PATH)
    if submission is None:
        return sorted(set(reasons + ["missing_final_submission"]))

    if any(field not in submission for field in SUBMISSION_FIELDS):
        reasons.append("candidate_fields_missing")
    if submission.get("artifact_id") != expected["artifact_id"]:
        reasons.append("artifact_id_mismatch")
    if submission.get("bundle_path") != expected["bundle_path"]:
        reasons.append("candidate_bundle_path_mismatch")
    if submission.get("verifier_command") != expected["verifier_command"]:
        reasons.append("verifier_command_mismatch")
    steps = submission.get("handoff_steps")
    if not isinstance(steps, list) or len(steps) < expected["min_handoff_steps"]:
        reasons.append("insufficient_handoff_steps")
    elif not all(
        isinstance(step, str)
        and step.strip()
        and expected["artifact_id"] in step
        and not any(stale in step for stale in expected["stale_artifact_ids"])
        for step in steps
    ):
        reasons.append("handoff_step_identity_mismatch")

    bundle_file = workspace / expected["bundle_path"]
    bundle, problem = _load_object(bundle_file)
    if problem == "missing":
        reasons.append("missing_final_bundle")
    elif bundle is None:
        reasons.append("bundle_unreadable")
    elif any(bundle.get(field) != expected[field] for field in IDENTITY_FIELDS):
        reasons.append("artifact_identity_lost")

    bundle_sha = _sha256(bundle_file)
    if bundle_sha is None:
        reasons.append("missing_verifier_pass_event")
        return sorted(set(reasons))
    if submission.get("bundle_sha256") != bundle_sha:
        reasons.append("bundle_sha_mismatch")
    verified = any(
        record.get("event_type") == "visible_verifier"
        and record.get("status") == "passed"
        and record.get("exit_code") == 0
        and record.get("candidate_bundle_sha256") == bundle_sha
        for record in _passing_records(workspace / LOG_PATH, expected["checker_sha256"])
    )
    if not verified:
        reasons.append("missing_verifier_pass_event")
    return sorted(set(reasons))


def main() -> int:
    workspace = Path(sys.argv[1]).resolve()
    expected, problem = _load_object(Path(__file__).resolve().parent / "expected.json")
    if expected is None:
        raise SystemExit(f"grader expected.json is {problem}")
    reasons = _grade(expected, workspace)
    passed = not reasons
    result = {
        "passed": passed,
        "score": 1.0 if passed else 0.0,
        "reasons": ["handoff_closed_with_identity_and_hash"] if passed else reasons,
    }
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
