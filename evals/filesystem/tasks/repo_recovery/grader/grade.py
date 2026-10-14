#!/usr/bin/env python3
"""Grader for the repo_recovery task (v2).

Standalone stdlib script: python3 grade.py <workspace_dir>. Prints one JSON line
{"passed", "score", "reasons"} as its last stdout line.

Reads only files under <workspace_dir> and truth.json next to this file. The expected
bundle values are derived from the workspace evidence (checkpoints, handoff manifest,
ops chat). Every file other than the repaired runtime config must keep its pristine bytes.

Reason codes (stable):
  missing_recovery_bundle        bundle file absent or not a JSON object
  bundle_field_mismatch          a required bundle field differs from the evidence-derived value
  runtime_env_mismatch           runtime.env differs from the required runtime values
  candidate_output_path_mismatch out/final_submission.json absent, malformed or differs
  missing_verifier_pass_event    out/verifier_receipt.json absent, malformed or not a pass
  verifier_receipt_stale         the receipt's hashes differ from the current bundle or config
  decoy_file_modified            a stale decoy file was edited
  other_file_modified            an out-of-scope file was edited
"""

import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUNDLE_FIELDS = ("closure_ticket", "runtime_host", "queue_name", "token_suffix", "commit_marker")
SUBMISSION_PATH = "out/final_submission.json"
RECEIPT_PATH = "out/verifier_receipt.json"


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _try_json(path: Path):
    try:
        value = _load_json(path)
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _sha256(path: Path):
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _parse_env(path: Path) -> dict:
    data = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return data
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip()
    return data


def _expected_values(workspace: Path) -> dict:
    checkpoint_a = _load_json(workspace / "data" / "checkpoints" / "checkpoint_a.json")
    checkpoint_b = _load_json(workspace / "data" / "checkpoints" / "checkpoint_b.json")
    checkpoint_c = _load_json(workspace / "data" / "checkpoints" / "checkpoint_c.json")
    manifest = _load_json(workspace / "ops" / "release" / "handoff_manifest.json")
    chat = (workspace / "reports" / "incident" / "ops_chat_excerpt.log").read_text(encoding="utf-8")
    mode_match = re.search(r"recovery mode must be `(\w+)`", chat)
    return {
        "closure_ticket": f"{manifest['ticket_prefix']}{str(checkpoint_c['closure_ticket_suffix']).strip()}",
        "runtime_host": str(checkpoint_a.get("runtime_host_candidate", "")).strip()
        or str(checkpoint_b.get("runtime_host_candidate", "")).strip(),
        "queue_name": str(checkpoint_b["queue_name"]).strip(),
        "token_suffix": str(checkpoint_a["token_suffix"]).strip(),
        "commit_marker": str(checkpoint_a.get("commit_marker", "")).strip()
        or str(checkpoint_c.get("commit_marker", "")).strip(),
        "runtime_mode": mode_match.group(1) if mode_match else "",
    }


def _pristine_reasons(workspace: Path, truth: dict) -> list:
    reasons = []
    decoys = set(truth["decoy_paths"])
    for rel, digest in sorted(truth["pristine_sha256"].items()):
        if _sha256(workspace / rel) == digest:
            continue
        reasons.append("decoy_file_modified" if rel in decoys else "other_file_modified")
    return reasons


def main() -> int:
    workspace = Path(sys.argv[1]).resolve()
    truth = _load_json(HERE / "truth.json")
    expected = _expected_values(workspace)
    bundle_path = workspace / truth["bundle_path"]
    env_path = workspace / truth["env_path"]
    reasons = []

    bundle = _try_json(bundle_path)
    if bundle is None:
        reasons.append("missing_recovery_bundle")
    elif any(bundle.get(field) != expected[field] for field in BUNDLE_FIELDS):
        reasons.append("bundle_field_mismatch")

    env = _parse_env(env_path)
    if (
        env.get("RUNTIME_HOST") != expected["runtime_host"]
        or env.get("RUNTIME_PORT") != "9100"
        or env.get("QUEUE_NAME") != expected["queue_name"]
        or env.get("RECOVERY_TOKEN") != f"token-recovery-{expected['token_suffix']}"
        or env.get("RECOVERY_MODE") != expected["runtime_mode"]
    ):
        reasons.append("runtime_env_mismatch")

    submission = _try_json(workspace / SUBMISSION_PATH)
    submission_expected = {
        "output_path": truth["bundle_path"],
        "closure_ticket": expected["closure_ticket"],
        "runtime_host": expected["runtime_host"],
        "queue_name": expected["queue_name"],
        "verifier_command": truth["required_verifier_command"],
    }
    if submission is None or any(submission.get(k) != v for k, v in submission_expected.items()):
        reasons.append("candidate_output_path_mismatch")

    receipt = _try_json(workspace / RECEIPT_PATH)
    if receipt is None or receipt.get("verdict") != "pass":
        reasons.append("missing_verifier_pass_event")
    elif receipt.get("bundle_sha256") != _sha256(bundle_path) or receipt.get("config_sha256") != _sha256(env_path):
        reasons.append("verifier_receipt_stale")

    reasons += _pristine_reasons(workspace, truth)
    unique = sorted(set(reasons))
    passed = not unique
    result = {
        "passed": passed,
        "score": 1.0 if passed else 0.0,
        "reasons": ["recovery_consistent"] if passed else unique,
    }
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
