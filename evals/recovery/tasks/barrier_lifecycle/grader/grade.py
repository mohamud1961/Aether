"""Grader for recovery/barrier_lifecycle (v2).

Standalone stdlib script: python3 grade.py <workspace_dir>. Prints one JSON line
{"passed", "score", "reasons"} as its last line. Reads only <workspace_dir>, this
directory (fixture/worker.py, expected.json).

The candidate's JobRunner is driven in a child interpreter through a fixed plan of real
local processes. The grader then checks overlap, result association, delivery, cancel
scope and orphaned processes from the child's report and from the process table.
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

HERE = Path(__file__).resolve().parent
WORKER = str(HERE / "fixture" / "worker.py")
EXPECTED = json.loads((HERE / "expected.json").read_text(encoding="utf-8"))
OK_REASONS = ["cancel_scope_ok", "delivery_ok", "overlap_ok", "protected_inputs_unchanged", "result_association_ok"]
PLAN = {
    "jobs": [["job-a", 0.6], ["job-b", 0.4], ["job-c", 6.0], ["job-d", 1.0]],
    "cancel": "job-c",
    "cancel_after_s": 0.4,
    "join_timeout_s": 3.0,
}
NAMES = [name for name, _ in PLAN["jobs"]]

# Runs in a child interpreter. Drives the candidate runner and reports what it observed.
RUNNER = r'''
import json, os, sys, tempfile, time
ws, worker, plan = sys.argv[1], sys.argv[2], json.loads(sys.argv[3])
os.chdir(ws)
sys.path.insert(0, ws)
piddir = tempfile.mkdtemp()
report = {"joins": {}, "joins_again": {}, "deliveries": [], "pids": {}, "error": None}

def take(runner, job, timeout):
    try:
        return runner.join(job, timeout=timeout)
    except BaseException as exc:
        return {"error": type(exc).__name__}

try:
    from jobctl.runner import JobRunner
    runner = JobRunner()
    jobs = {}
    for name, seconds in plan["jobs"]:
        jobs[name] = runner.start(name, [sys.executable, worker, name, str(seconds), piddir])
    time.sleep(plan["cancel_after_s"])
    # Cancel only once the target job has started its own child, so an orphan is observable under load.
    target = os.path.join(piddir, plan["cancel"] + ".pids")
    ready_by = time.monotonic() + 10.0
    while time.monotonic() < ready_by:
        try:
            with open(target, encoding="utf-8") as handle:
                if len(handle.read().split()) == 2:
                    break
        except OSError:
            pass
        time.sleep(0.02)
    runner.cancel(jobs[plan["cancel"]])
    for name, _ in plan["jobs"]:
        report["joins"][name] = take(runner, jobs[name], plan["join_timeout_s"])
    for name, _ in plan["jobs"]:
        report["joins_again"][name] = take(runner, jobs[name], plan["join_timeout_s"])
    report["deliveries"] = list(runner.deliveries)
except BaseException as exc:
    report["error"] = type(exc).__name__ + ": " + str(exc)[:200]

for name, _ in plan["jobs"]:
    try:
        with open(os.path.join(piddir, name + ".pids"), encoding="utf-8") as handle:
            report["pids"][name] = [int(x) for x in handle.read().split()]
    except OSError:
        report["pids"][name] = []
print(json.dumps(report, sort_keys=True, default=str))
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
    # subprocess is avoided on purpose: importing it lists site-packages, which the audit flags.
    read_fd, write_fd = os.pipe()
    actions = [(os.POSIX_SPAWN_DUP2, write_fd, 1), (os.POSIX_SPAWN_CLOSE, read_fd)]
    argv = [sys.executable, "-I", "-B", "-c", RUNNER, str(workspace), WORKER, json.dumps(PLAN)]
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
        ready = select.select([read_fd], [], [], max(remaining, 0))[0] if remaining > 0 else []
        if not ready:
            timed_out = remaining <= 0 or not ready
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


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _token(output: Any) -> str | None:
    try:
        return json.loads(output)["token"]
    except (TypeError, ValueError, KeyError):
        return None


def _check(report: dict[str, Any]) -> set[str]:
    reasons: set[str] = set()
    joins = report.get("joins") or {}
    again = report.get("joins_again") or {}
    for name in ("job-a", "job-b", "job-d"):
        result = joins.get(name)
        if not isinstance(result, dict) or "error" in result:
            reasons.add("result_missing")
            continue
        if result.get("cancelled") or result.get("exit_code") != 0:
            reasons.add("sibling_killed")
        token = _token(result.get("output"))
        if token is None:
            reasons.add("result_missing")
        elif token != name:
            reasons.add("result_swapped")
    cancelled = joins.get("job-c")
    if not isinstance(cancelled, dict) or "error" in cancelled or cancelled.get("cancelled") is not True \
            or cancelled.get("exit_code") is not None:
        reasons.add("cancel_not_effective")
    if again != joins:
        reasons.add("join_not_stable")
    try:
        first = json.loads(joins["job-a"]["output"])
        second = json.loads(joins["job-b"]["output"])
        if not (first["start"] < second["end"] and second["start"] < first["end"]):
            reasons.add("jobs_not_overlapped")
    except (KeyError, TypeError, ValueError):
        reasons.add("result_missing")
    names = [d.get("name") for d in report.get("deliveries") or [] if isinstance(d, dict)]
    if len(names) != len(set(names)) or len(names) > len(NAMES):
        reasons.add("duplicate_delivery")
    elif len(names) < len(NAMES):
        reasons.add("result_missing")
    return reasons


def main() -> int:
    workspace = Path(sys.argv[1]).resolve()
    reasons = _protected_reasons(workspace)
    report = _run_candidate(workspace)
    if report is None or report.get("error"):
        reasons.add("candidate_crashed")
    else:
        reasons |= _check(report)
    time.sleep(0.3)
    job_pids = (report or {}).get("pids", {}).get("job-c", [])
    # A killed job can linger briefly as an unreaped zombie; give it time to disappear.
    settle_by = time.monotonic() + 3.0
    while job_pids and _alive(job_pids[0]) and time.monotonic() < settle_by:
        time.sleep(0.05)
    leftovers = [pid for pid in job_pids if _alive(pid)]
    if leftovers:
        # An orphan outlives its killed job; if the job itself still runs, the cancel was ignored instead.
        if job_pids and not _alive(job_pids[0]):
            reasons.add("orphaned_process")
        for pid in leftovers:
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
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
