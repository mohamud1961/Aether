"""Grader for retrieval/structured_evidence_join (v2).

Standalone stdlib script: python3 grade.py <workspace_dir>. Prints one JSON line
{"passed", "score", "reasons"} as its last stdout line. Reads only files under <workspace_dir>
and expected.json next to this script.

The expected late-order list is sealed in expected.json, derived from the workspace event logs
and the current export. It is checked as a state: the set of late orders, each order's promised
and shipped times and whole-minute delay, and the declared source of shipped times. Every input
file must keep its pristine bytes; the September export, the data dictionary, the changelog and the
README are decoys.

Reason codes (stable):
  missing_submission, submission_shape_invalid, shipped_source_mismatch,
  late_set_mismatch, delay_value_mismatch, decoy_file_modified, other_file_modified
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

SUBMISSION_PATH = "out/late_shipments.json"
ITEM_FIELDS = ("order_id", "promised_at_utc", "shipped_at_utc", "delay_minutes")


def _sha256(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _load(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _pristine_reasons(workspace: Path, expected: dict[str, Any]) -> list[str]:
    decoys = set(expected["decoy_paths"])
    reasons = []
    for rel, digest in sorted(expected["pristine_sha256"].items()):
        if _sha256(workspace / rel) != digest:
            reasons.append("decoy_file_modified" if rel in decoys else "other_file_modified")
    return reasons


def _grade(expected: dict[str, Any], workspace: Path) -> list[str]:
    reasons = _pristine_reasons(workspace, expected)
    submission_path = workspace / SUBMISSION_PATH
    if not submission_path.is_file():
        return sorted(set(reasons + ["missing_submission"]))
    submission = _load(submission_path)
    if not isinstance(submission, dict) or "late_orders" not in submission or "shipped_time_source" not in submission:
        return sorted(set(reasons + ["submission_shape_invalid"]))
    late = submission["late_orders"]
    if not isinstance(late, list) or not all(isinstance(item, dict) and all(f in item for f in ITEM_FIELDS) for item in late):
        return sorted(set(reasons + ["submission_shape_invalid"]))

    if submission["shipped_time_source"] != expected["shipped_time_source"]:
        reasons.append("shipped_source_mismatch")

    want = {item["order_id"]: item for item in expected["late_orders"]}
    got = {str(item["order_id"]): item for item in late}
    if set(got) != set(want) or len(got) != len(late):
        reasons.append("late_set_mismatch")
    elif any(got[oid] != want[oid] for oid in want):
        reasons.append("delay_value_mismatch")
    elif [item["order_id"] for item in late] != sorted(want):
        reasons.append("submission_shape_invalid")
    return sorted(set(reasons))


def main() -> int:
    workspace = Path(sys.argv[1]).resolve()
    expected = _load(Path(__file__).resolve().parent / "expected.json")
    if not isinstance(expected, dict):
        raise SystemExit("grader expected.json is unreadable")
    reasons = _grade(expected, workspace)
    passed = not reasons
    result = {
        "passed": passed,
        "score": 1.0 if passed else 0.0,
        "reasons": ["late_shipments_verified_against_event_log"] if passed else reasons,
    }
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
