"""Grader for recovery/transport_fault_recovery (v2).

Standalone stdlib script: python3 grade.py <workspace_dir>. Prints one JSON line
{"passed", "score", "reasons"} as its last line. Reads only <workspace_dir> and
expected.json next to this file.

The candidate's run_batch is imported and driven in a child interpreter against a
scripted fault transport. The child reports the wire outcomes it actually served, which
the grader compares with the candidate's own results and attempt log.
"""

from __future__ import annotations

import hashlib
import json
import os
import select
import signal
import sys
import time
from pathlib import Path
from typing import Any

# subprocess is avoided on purpose: importing it lists site-packages, which the audit flags.

HERE = Path(__file__).resolve().parent
EXPECTED = json.loads((HERE / "expected.json").read_text(encoding="utf-8"))
MAX_ATTEMPTS = 4
IDEMPOTENT = {"GET", "PUT", "DELETE"}
CLASSES = {"ok", "rate_limited", "dropped", "truncated", "fatal"}
OK_REASONS = ["attempt_log_ok", "protected_inputs_unchanged", "results_ok", "retry_policy_ok"]

SCENARIO = [
    {"op_id": "op-a", "method": "GET", "payload": {"q": 1},
     "script": ["rate_limited", "ok"], "value": 11},
    {"op_id": "op-b", "method": "POST", "payload": {"name": "x"},
     "script": ["ok"], "value": "alpha"},
    {"op_id": "op-c", "method": "PUT", "payload": {"id": 3},
     "script": ["dropped", "truncated", "ok"], "value": [1, 2], "partial": '{"value": [1, 2]'},
    {"op_id": "op-d", "method": "POST", "payload": {"name": "y"},
     "script": ["truncated"], "value": 77, "partial": '{"value": 77'},
    {"op_id": "op-e", "method": "POST", "payload": {"name": "z"},
     "script": ["rate_limited", "rate_limited", "ok"], "value": 5},
    {"op_id": "op-f", "method": "GET", "payload": {"q": 2},
     "script": ["fatal"], "value": None},
    {"op_id": "op-g", "method": "DELETE", "payload": {"id": 9},
     "script": ["dropped", "dropped", "dropped", "dropped"], "value": None},
    {"op_id": "op-h", "method": "PATCH", "payload": {"id": 4},
     "script": ["dropped"], "value": None},
]

# Runs in a child interpreter. Serves each op's scripted outcome per attempt, then "ok".
RUNNER = r'''
import json, os, sys
ws = sys.argv[1]
scenario = json.loads(sys.argv[2])
os.chdir(ws)
sys.path.insert(0, ws)
from wirekit.errors import ConnectionDropped
specs = {s["op_id"]: s for s in scenario}
ledger = {}

def transport(op_id, method, payload):
    spec = specs[op_id]
    seen = ledger.setdefault(op_id, [])
    index = len(seen)
    outcome = spec["script"][index] if index < len(spec["script"]) else "ok"
    seen.append(outcome)
    if outcome == "dropped":
        raise ConnectionDropped("no reply")
    if outcome == "rate_limited":
        return {"status": 429, "body": ""}
    if outcome == "fatal":
        return {"status": 422, "body": '{"error": "invalid"}'}
    if outcome == "truncated":
        return {"status": 200, "body": spec["partial"]}
    return {"status": 200, "body": json.dumps({"value": spec["value"]})}

out = {"ledger": ledger, "return": None, "error": None}
try:
    from wirekit.batch import run_batch
    requests = [{"op_id": s["op_id"], "method": s["method"], "payload": s["payload"]} for s in scenario]
    out["return"] = run_batch(requests, transport)
except BaseException as exc:
    out["error"] = type(exc).__name__ + ": " + str(exc)[:200]
print(json.dumps(out, sort_keys=True, default=str))
'''


def _sha(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _protected_reasons(workspace: Path) -> set[str]:
    for rel, digest in EXPECTED["protected_sha256"].items():
        if _sha(workspace / rel) != digest:
            return {"protected_file_modified"}
    return set()


def _run_candidate(workspace: Path) -> dict[str, Any] | None:
    read_fd, write_fd = os.pipe()
    actions = [(os.POSIX_SPAWN_DUP2, write_fd, 1), (os.POSIX_SPAWN_CLOSE, read_fd)]
    argv = [sys.executable, "-I", "-B", "-c", RUNNER, str(workspace), json.dumps(SCENARIO)]
    try:
        pid = os.posix_spawn(sys.executable, argv, {"PATH": os.environ.get("PATH", "")},
                             file_actions=actions)
    except OSError:
        os.close(read_fd)
        os.close(write_fd)
        return None
    os.close(write_fd)
    chunks: list[bytes] = []
    deadline = time.monotonic() + 30.0
    timed_out = False
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            timed_out = True
            break
        ready, _, _ = select.select([read_fd], [], [], remaining)
        if not ready:
            timed_out = True
            break
        data = os.read(read_fd, 65536)
        if not data:
            break
        chunks.append(data)
    os.close(read_fd)
    if timed_out:
        os.kill(pid, signal.SIGKILL)
    os.waitpid(pid, 0)
    if timed_out:
        return None
    try:
        return json.loads(b"".join(chunks).decode("utf-8", "replace").strip().splitlines()[-1])
    except (IndexError, ValueError):
        return None


def _policy_reasons(ledger: dict[str, list[str]]) -> set[str]:
    reasons: set[str] = set()
    for spec in SCENARIO:
        got = ledger.get(spec["op_id"], [])
        exp = spec["script"]
        if len(got) < len(exp):
            reasons.add("premature_stop")
        elif len(got) > len(exp):
            if exp[-1] == "fatal":
                reasons.add("fatal_retried")
            elif spec["method"] not in IDEMPOTENT and any(x in ("dropped", "truncated") for x in exp):
                reasons.add("unsafe_retry")
            elif len(got) > MAX_ATTEMPTS:
                reasons.add("retry_budget_exceeded")
            else:
                reasons.add("unexpected_retry")
    return reasons


def _result_reasons(ret: Any) -> set[str]:
    if not isinstance(ret, dict) or not all(k in ret for k in ("results", "failed", "attempts")):
        return {"candidate_shape_invalid"}
    reasons: set[str] = set()
    expected_results = {s["op_id"]: s["value"] for s in SCENARIO if s["script"][-1] == "ok"}
    expected_failed = sorted(s["op_id"] for s in SCENARIO if s["script"][-1] != "ok")
    if not isinstance(ret["results"], dict) or ret["results"] != expected_results:
        reasons.add("result_value_mismatch")
    if not isinstance(ret["failed"], list) or sorted(ret["failed"], key=str) != expected_failed:
        reasons.add("failed_list_mismatch")
    return reasons


def _attempt_reasons(attempts: Any, ledger: dict[str, list[str]]) -> set[str]:
    if not isinstance(attempts, list):
        return {"attempt_record_invalid"}
    ops = {s["op_id"] for s in SCENARIO}
    reasons: set[str] = set()
    for row in attempts:
        if not isinstance(row, dict) or row.get("classification") not in CLASSES:
            reasons.add("attempt_record_invalid")
        elif row.get("op_id") not in ops:
            reasons.add("phantom_attempt_record")
    for op in ops:
        reported = [r.get("classification") for r in attempts
                    if isinstance(r, dict) and r.get("op_id") == op]
        served = ledger.get(op, [])
        if reported == served:
            continue
        if len(reported) < len(served):
            reasons.add("attempt_record_missing")
        elif len(reported) > len(served):
            reasons.add("phantom_attempt_record")
        else:
            reasons.add("attempt_label_mismatch")
    return reasons


def main() -> int:
    workspace = Path(sys.argv[1]).resolve()
    reasons = _protected_reasons(workspace)
    report = _run_candidate(workspace)
    if report is None or report.get("error"):
        reasons.add("candidate_crashed")
    else:
        ledger = report.get("ledger") or {}
        ret = report.get("return")
        reasons |= _policy_reasons(ledger)
        reasons |= _result_reasons(ret)
        if isinstance(ret, dict):
            reasons |= _attempt_reasons(ret.get("attempts"), ledger)
    passed = not reasons
    result = {
        "passed": passed,
        "score": 1.0 if passed else 0.0,
        "reasons": OK_REASONS if passed else sorted(reasons),
    }
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
