"""Grading: run a task's hidden grader on a final workspace state.

Grader contract: `python3.11 grader/grade.py <workspace_dir>` prints one JSON line
{"passed": bool, "score": number, "reasons": [str]} as its last stdout line and exits 0.
A grader that breaks the contract is reported as passed=False with GradeResult.error set.
Grading never returns a pass for a grader problem.

grade_audited runs the same grader through a launcher that records every file the grader
opens or lists, so validate-graders can detect reads outside the workspace. Python-level
file access is audited; subprocesses and C-level reads are not.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from harness_evals.task import Task

GRADER_INTERPRETER = "python3.11"
_STDERR_TAIL = 300

_AUDIT_LAUNCHER = r"""
import json
import os
import runpy
import sys

grader, workspace, audit_path = sys.argv[1], sys.argv[2], sys.argv[3]
opened = []


def _record(event, args):
    if event in ("open", "os.listdir", "os.scandir") and args and isinstance(args[0], str):
        opened.append(args[0])


sys.addaudithook(_record)
sys.argv = [grader, workspace]
sys.path.insert(0, os.path.dirname(grader))
try:
    runpy.run_path(grader, run_name="__main__")
finally:
    snapshot = list(opened)
    payload = json.dumps({"opened": snapshot, "prefixes": [sys.base_prefix, sys.prefix, sys.exec_prefix]})
    with open(audit_path, "w", encoding="utf-8") as handle:
        handle.write(payload)
"""


@dataclass(frozen=True)
class GradeResult:
    passed: bool
    score: float
    reasons: tuple[str, ...]
    grader_hash: str
    error: str | None


@dataclass(frozen=True)
class _RawRun:
    code: int | None
    stdout: str
    stderr: str
    error: str | None


def grade(task: Task, workspace: Path, timeout_s: float = 120) -> GradeResult:
    digest = _file_sha256(task.grader_path)
    argv = [GRADER_INTERPRETER, str(task.grader_path), str(Path(workspace).resolve())]
    with tempfile.TemporaryDirectory(prefix="harness-grade-") as scratch:
        raw = _run(argv, Path(scratch), timeout_s)
    return _parse(raw, digest)


def grade_audited(
    task: Task, workspace: Path, timeout_s: float = 120
) -> tuple[GradeResult, tuple[str, ...]]:
    """Grade and return the sorted paths the grader touched outside its allowed roots."""
    workspace_path = Path(workspace).resolve()
    digest = _file_sha256(task.grader_path)
    with tempfile.TemporaryDirectory(prefix="harness-grade-audit-") as scratch:
        scratch_path = Path(scratch)
        audit_file = scratch_path / "audit.json"
        argv = [
            GRADER_INTERPRETER,
            "-c",
            _AUDIT_LAUNCHER,
            str(task.grader_path),
            str(workspace_path),
            str(audit_file),
        ]
        raw = _run(argv, scratch_path, timeout_s)
        audit = _read_audit(audit_file)
    if audit is None:
        detail = (
            raw.error
            or f"grader exited with code {raw.code} without writing its audit log"
        )
        return _failed(digest, detail), ()
    allowed = [workspace_path, task.grader_path.parent, *audit["prefixes"]]
    outside = _outside_reads(audit["opened"], allowed)
    return _parse(raw, digest), outside


def _run(argv: list[str], cwd: Path, timeout_s: float) -> _RawRun:
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": str(cwd),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
    }
    try:
        proc = subprocess.run(
            argv,
            cwd=cwd,
            env=env,
            capture_output=True,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return _RawRun(None, "", "", f"grader timed out after {timeout_s} s")
    except FileNotFoundError:
        return _RawRun(None, "", "", f"grader interpreter not found: {argv[0]}")
    return _RawRun(
        code=proc.returncode,
        stdout=proc.stdout.decode("utf-8", errors="replace"),
        stderr=proc.stderr.decode("utf-8", errors="replace"),
        error=None,
    )


def _parse(raw: _RawRun, digest: str) -> GradeResult:
    if raw.error is not None:
        return _failed(digest, raw.error)
    if raw.code != 0:
        tail = raw.stderr.strip()[-_STDERR_TAIL:]
        return _failed(digest, f"grader exited with code {raw.code}: {tail}")
    lines = raw.stdout.strip().splitlines()
    if not lines:
        return _failed(digest, "grader printed no output")
    try:
        payload: Any = json.loads(lines[-1])
    except ValueError as exc:
        return _failed(digest, f"malformed grader output: {exc}")
    problem = _shape_problem(payload)
    if problem is not None:
        return _failed(digest, f"malformed grader output: {problem}")
    return GradeResult(
        passed=payload["passed"],
        score=float(payload["score"]),
        reasons=tuple(payload["reasons"]),
        grader_hash=digest,
        error=None,
    )


def _shape_problem(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return "last line is not a JSON object"
    if set(payload) != {"passed", "score", "reasons"}:
        return f"keys must be exactly passed, score, reasons; got {sorted(payload)}"
    if not isinstance(payload["passed"], bool):
        return "passed must be a boolean"
    score = payload["score"]
    if (
        isinstance(score, bool)
        or not isinstance(score, (int, float))
        or not math.isfinite(score)
    ):
        return "score must be a finite number"
    reasons = payload["reasons"]
    if not isinstance(reasons, list) or not all(
        isinstance(item, str) for item in reasons
    ):
        return "reasons must be a list of strings"
    return None


def _failed(digest: str, error: str) -> GradeResult:
    return GradeResult(
        passed=False, score=0.0, reasons=(), grader_hash=digest, error=error
    )


def _read_audit(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def _outside_reads(opened: list[str], allowed: list[Path]) -> tuple[str, ...]:
    roots = [os.path.realpath(root) for root in allowed]
    outside: set[str] = set()
    for raw_path in opened:
        real = os.path.realpath(raw_path)
        if not any(_is_within(real, root) for root in roots):
            outside.add(raw_path)
    return tuple(sorted(outside))


def _is_within(path: str, root: str) -> bool:
    return path == root or path.startswith(root.rstrip(os.sep) + os.sep)


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
