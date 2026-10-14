"""Grader for environment_bootstrap_runner_repair (v2).

Standalone stdlib script: python3 grade.py <workspace_dir>. Prints one JSON line
{"passed", "score", "reasons"} as its last stdout line.

Reads only <workspace_dir> and expected.json next to this file. The expected runner command,
package manager and pristine file hashes are sealed in expected.json, so editing the contract
or the stale notes cannot move the target. Judgement is on end state: the report must name the
sealed command, the repaired runner script must contain it, the patch list must equal the set of
files actually changed, and the runner must really pass when it is run in place.
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
REPORT = Path("out") / "toolchain_repair_report.json"
PATCHES = Path("out") / "patches_applied.txt"
RUNNER = "scripts/run_tests.sh"
RUN_TIMEOUT_S = 90


def _sha(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _changed_files(ws: Path, expected: dict[str, Any]) -> set[str]:
    return {rel for rel, digest in expected["pristine_sha256"].items() if _sha(ws / rel) != digest}


def _check_report(ws: Path, expected: dict[str, Any], reasons: list[str]) -> None:
    path = ws / REPORT
    if not path.is_file():
        reasons.append("missing_toolchain_repair_report")
        return
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        reasons.append("toolchain_repair_report_invalid")
        return
    if not isinstance(report, dict):
        reasons.append("toolchain_repair_report_invalid")
        return
    if report.get("runner_command") != expected["runner_command"]:
        reasons.append("runner_command_mismatch")
    if report.get("package_manager") != expected["package_manager"]:
        reasons.append("package_manager_mismatch")
    if report.get("preflight_success") is not True:
        reasons.append("preflight_not_successful")


def _check_patches(ws: Path, expected: dict[str, Any], reasons: list[str]) -> None:
    path = ws / PATCHES
    if not path.is_file():
        reasons.append("missing_patches_applied")
        return
    listed = {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}
    if listed != _changed_files(ws, expected):
        reasons.append("patches_list_mismatch")


def _check_runner_text(ws: Path, expected: dict[str, Any], reasons: list[str]) -> None:
    path = ws / RUNNER
    if not path.is_file():
        reasons.append("runner_script_missing")
        return
    command = " ".join(expected["runner_command"].split())
    lines = [" ".join(raw.split()) for raw in path.read_text(encoding="utf-8").splitlines()]
    if command not in [line for line in lines if line and not line.startswith("#")]:
        reasons.append("runner_script_not_patched")


def _run_runner(ws: Path) -> tuple[int | None, str]:
    """Run the runner in place in a forked child; return (exit code or None on timeout, output)."""
    read_fd, write_fd = os.pipe()
    pid = os.fork()
    if pid == 0:
        os.close(read_fd)
        try:
            os.chdir(ws)
            os.dup2(write_fd, 1)
            os.dup2(write_fd, 2)
            os.execv("/bin/bash", ["bash", RUNNER])
        finally:
            os._exit(127)
    os.close(write_fd)
    chunks: list[bytes] = []
    deadline = time.monotonic() + RUN_TIMEOUT_S
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            os.kill(pid, signal.SIGKILL)
            os.waitpid(pid, 0)
            os.close(read_fd)
            return None, b"".join(chunks).decode("utf-8", errors="replace")
        ready, _, _ = select.select([read_fd], [], [], remaining)
        if not ready:
            continue
        data = os.read(read_fd, 65536)
        if not data:
            break
        chunks.append(data)
    os.close(read_fd)
    _, status = os.waitpid(pid, 0)
    code = os.WEXITSTATUS(status) if os.WIFEXITED(status) else -os.WTERMSIG(status)
    return code, b"".join(chunks).decode("utf-8", errors="replace")


def _check_runner_run(ws: Path, expected: dict[str, Any], reasons: list[str]) -> None:
    code, output = _run_runner(ws)
    if code != 0 or "OK" not in output:
        reasons.append("runner_run_failed")
    elif f"Ran {expected['expected_test_count']} tests" not in output:
        reasons.append("runner_test_count_mismatch")


def _check_pristine(ws: Path, expected: dict[str, Any], reasons: list[str]) -> None:
    decoys = set(expected["decoy_paths"])
    contract = set(expected["contract_paths"])
    for rel in sorted(_changed_files(ws, expected)):
        if rel == RUNNER:
            continue
        if rel in contract:
            reasons.append("contract_modified")
        elif rel in decoys:
            reasons.append("decoy_file_modified")
        else:
            reasons.append("other_file_modified")


def grade(ws: Path) -> list[str]:
    expected = json.loads((HERE / "expected.json").read_text(encoding="utf-8"))
    reasons: list[str] = []
    _check_report(ws, expected, reasons)
    _check_patches(ws, expected, reasons)
    _check_runner_text(ws, expected, reasons)
    _check_runner_run(ws, expected, reasons)
    _check_pristine(ws, expected, reasons)
    return sorted(set(reasons))


def main() -> int:
    reasons = grade(Path(sys.argv[1]).resolve())
    passed = not reasons
    result = {"passed": passed, "score": 1.0 if passed else 0.0,
              "reasons": ["runner_contract_ok"] if passed else reasons}
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
