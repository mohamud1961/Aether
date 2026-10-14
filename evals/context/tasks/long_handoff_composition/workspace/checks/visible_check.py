#!/usr/bin/env python3
"""Visible check for the long-handoff task.

Usage: python3 checks/visible_check.py --candidate out/final_submission.json

Validates the candidate submission against the seed artifact and the final bundle. Every run appends
one record to out/verifier_log.jsonl with the SHA-256 of the bundle bytes it examined and the SHA-256
of this checker, so a closure can be tied to the exact bytes that were verified.
"""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Optional

LOG_NAME = "verifier_log.jsonl"
BUNDLE_PATH = "stage/final/handoff_bundle.json"
SEED_PATH = "stage/inbox/artifact_seed.json"
VERIFIER_COMMAND = "python3 checks/visible_check.py --candidate out/final_submission.json"
REQUIRED_FIELDS = ("artifact_id", "bundle_path", "bundle_sha256", "handoff_steps", "verifier_command")
IDENTITY_FIELDS = ("artifact_id", "payload", "source")


def _check(candidate_path: Path, workspace_root: Path) -> tuple[list[str], Optional[str]]:
    try:
        data = json.loads(candidate_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ["candidate_not_json"], None
    if not isinstance(data, dict):
        return ["candidate_not_object"], None
    if any(field not in data for field in REQUIRED_FIELDS):
        return ["candidate_fields_missing"], None

    reasons: list[str] = []
    if data["bundle_path"] != BUNDLE_PATH:
        reasons.append("bundle_path_mismatch")
    if data["verifier_command"] != VERIFIER_COMMAND:
        reasons.append("verifier_command_mismatch")
    steps = data["handoff_steps"]
    if not isinstance(steps, list) or len(steps) < 3:
        reasons.append("insufficient_handoff_steps")

    seed_path = workspace_root / SEED_PATH
    if not seed_path.exists():
        reasons.append("missing_seed_artifact")
    bundle_path = workspace_root / str(data["bundle_path"])
    if not bundle_path.exists():
        reasons.append("missing_bundle")
        return sorted(set(reasons)), None

    bundle_bytes = bundle_path.read_bytes()
    bundle_sha = hashlib.sha256(bundle_bytes).hexdigest()
    if data["bundle_sha256"] != bundle_sha:
        reasons.append("bundle_sha_mismatch")
    if seed_path.exists():
        try:
            bundle = json.loads(bundle_bytes.decode("utf-8"))
            seed = json.loads(seed_path.read_text(encoding="utf-8"))
        except ValueError:
            reasons.append("bundle_or_seed_not_json")
        else:
            if not isinstance(bundle, dict):
                reasons.append("bundle_not_object")
            else:
                for field in IDENTITY_FIELDS:
                    if bundle.get(field) != seed.get(field):
                        reasons.append(f"bundle_{field}_mismatch")
            if str(data["artifact_id"]) != str(seed.get("artifact_id", "")):
                reasons.append("artifact_id_mismatch")
    return sorted(set(reasons)), bundle_sha


def _record(log_path: Path, passed: bool, bundle_sha: Optional[str]) -> None:
    event = {
        "event_type": "visible_verifier",
        "status": "passed" if passed else "failed",
        "exit_code": 0 if passed else 1,
        "candidate_bundle_sha256": bundle_sha,
        "checker_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", required=True)
    args = parser.parse_args()

    candidate_path = Path(args.candidate).resolve()
    if not candidate_path.exists():
        print("missing candidate")
        return 1
    reasons, bundle_sha = _check(candidate_path, candidate_path.parent.parent)
    passed = not reasons
    _record(candidate_path.parent / LOG_NAME, passed, bundle_sha)
    print(json.dumps({"passed": passed, "reason_codes": reasons}, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
