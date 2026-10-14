"""Grader for orchestration/delegation_fidelity (v2).

Standalone stdlib script: python3 grade.py <workspace_dir>. Prints one JSON line
{"passed", "score", "reasons"} as its last line. Reads only <workspace_dir> and
expected.json next to this file.

Packets are checked against the sealed schema and the sealed constraint sets: every live
constraint for a worker must be present, no retracted or superseded id may appear, and no
other id may be assigned. The merge is checked against the sealed result: the stale reconcile
result (built on packet version 1) must be rejected, and its finding must not appear.
Every initial file must stay byte-identical, except that out/ is the only place to write.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
OK_REASONS = (
    "packets_match_thread",
    "merge_matches_rules",
    "inputs_unchanged",
)


def _sha256(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _load_object(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _types_ok(data: dict[str, Any]) -> bool:
    if type(data.get("packet_version")) is not int:
        return False
    if not isinstance(data.get("worker"), str):
        return False
    for key in ("goal", "done_when"):
        if not isinstance(data.get(key), str) or not data[key].strip():
            return False
    for key in ("constraint_ids", "inputs", "outputs"):
        value = data.get(key)
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            return False
    return True


def _packet_reasons(data: dict[str, Any], expected: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if set(data) != set(expected["packet_keys"]) or not _types_ok(data):
        return ["packet_schema_mismatch"]
    if data["packet_version"] != expected["packet_version_current"]:
        reasons.append("packet_version_mismatch")
    ids = set(data["constraint_ids"])
    want = set(expected["constraints_by_worker"][data["worker"]])
    banned = set(expected["banned_ids"])
    if ids & banned:
        reasons.append("retracted_constraint_present")
    if want - ids:
        reasons.append("live_constraint_missing")
    if (ids - banned) - want:
        reasons.append("constraint_misassigned")
    return reasons


def _packets_reasons(workspace: Path, expected: dict[str, Any]) -> list[str]:
    folder = workspace / "out/packets"
    if not folder.is_dir():
        return ["missing_packets"]
    by_worker: dict[str, dict[str, Any]] = {}
    reasons: list[str] = []
    for path in sorted(folder.glob("*.json")):
        data = _load_object(path)
        if data is None:
            return ["packet_unparseable"]
        worker = data.get("worker")
        if worker not in expected["workers"]:
            reasons.append("unexpected_packet")
            continue
        if worker in by_worker:
            reasons.append("duplicate_packet")
            continue
        by_worker[worker] = data
    for worker in expected["workers"]:
        if worker not in by_worker:
            reasons.append("missing_packets")
    for data in by_worker.values():
        reasons += _packet_reasons(data, expected)
    return reasons


def _merged_reasons(workspace: Path, expected: dict[str, Any]) -> list[str]:
    path = workspace / "out/merged.json"
    if not path.is_file():
        return ["missing_merged"]
    data = _load_object(path)
    if data is None:
        return ["merged_unparseable"]
    reasons: list[str] = []
    accepted = data.get("accepted_workers")
    findings = data.get("findings")
    if isinstance(accepted, list) and "reconcile" in accepted:
        reasons.append("stale_result_accepted")
    if isinstance(findings, list) and set(findings) & set(expected["stale_finding_ids"]):
        reasons.append("stale_result_accepted")
    if (
        data.get("schema_version") != expected["merged_schema"]
        or accepted != expected["accepted_workers"]
        or data.get("rejected") != expected["rejected"]
        or findings != expected["findings"]
        or data.get("packet_versions") != expected["packet_versions"]
    ):
        reasons.append("merge_mismatch")
    return reasons


def _input_reasons(workspace: Path, expected: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    for rel, digest in sorted(expected["pristine_sha256"].items()):
        if rel.startswith("out/"):
            continue
        if _sha256(workspace / rel) != digest:
            reasons.append("vendor_modified" if rel.startswith("vendor/") else "input_modified")
    for path in workspace.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(workspace).as_posix()
        if rel.startswith("out/") or rel in expected["pristine_sha256"]:
            continue
        reasons.append("input_modified")
    return reasons


def grade(workspace: Path, expected: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons = (
        _packets_reasons(workspace, expected)
        + _merged_reasons(workspace, expected)
        + _input_reasons(workspace, expected)
    )
    unique = sorted(set(reasons))
    return (not unique, unique)


def main() -> int:
    workspace = Path(sys.argv[1]).resolve()
    expected = json.loads((HERE / "expected.json").read_text(encoding="utf-8"))
    passed, reasons = grade(workspace, expected)
    result = {
        "passed": passed,
        "score": 1.0 if passed else 0.0,
        "reasons": list(OK_REASONS) if passed else reasons,
    }
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
