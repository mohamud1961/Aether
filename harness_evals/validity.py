"""Grader validity: prove a task's grader accepts the right state and rejects the wrong ones.

For each task directory, validate_task_dir checks:

1. The task loads (task format and known-bad headers are well formed).
2. The task has at least one known-bad state.
3. reference state: running reference/solve.sh in a fresh workspace copy produces a state the grader passes.
4. untouched state: the initial workspace fails.
5. each known-bad state: running known_bad/<name> produces a state the grader fails, and the
   script's '# expect:' reason code appears in the grader's reasons.
6. determinism: grading each state twice gives identical results.
7. containment: the grader opens or lists nothing outside the workspace, its own directory and
   the Python installation (audited at the Python level; see grading.grade_audited).

Each state is produced in a fresh LocalSandbox. Every failed check becomes a Violation; a report
with no violations and at least one task is the only clean result.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from harness_evals.grading import GradeResult, grade_audited
from harness_evals.sandbox import ExecResult, LocalSandbox
from harness_evals.task import KnownBad, Task, find_task_dirs, load_task

REFERENCE_COMMAND = 'bash "$TASK_ROOT/reference/solve.sh"'


@dataclass(frozen=True)
class Violation:
    check: str
    detail: str


@dataclass(frozen=True)
class TaskValidity:
    task_id: str
    path: Path
    known_bad_count: int
    violations: tuple[Violation, ...]

    @property
    def ok(self) -> bool:
        return not self.violations


@dataclass(frozen=True)
class ValidityReport:
    root: Path
    tasks: tuple[TaskValidity, ...] = field(default=())

    @property
    def ok(self) -> bool:
        return bool(self.tasks) and all(task.ok for task in self.tasks)


@dataclass(frozen=True)
class _Graded:
    result: GradeResult
    outside_reads: tuple[str, ...]


def validate_tree(root: Path) -> ValidityReport:
    """Validate every task directory under root (root itself included if it is a task)."""
    results = tuple(validate_task_dir(path) for path in find_task_dirs(root))
    return ValidityReport(root=Path(root), tasks=results)


def validate_task_dir(path: Path) -> TaskValidity:
    try:
        task = load_task(path)
    except (ValueError, OSError) as exc:
        return TaskValidity(
            task_id=Path(path).name,
            path=Path(path),
            known_bad_count=0,
            violations=(Violation("task_load", str(exc)),),
        )
    violations: list[Violation] = []
    known_bad = task.known_bad
    if not known_bad:
        violations.append(
            Violation("no_known_bads", "task has no known_bad/*.sh states")
        )
    _check_reference(task, violations)
    _check_untouched(task, violations)
    for bad in known_bad:
        _check_known_bad(task, bad, violations)
    return TaskValidity(
        task_id=task.id,
        path=task.root,
        known_bad_count=len(known_bad),
        violations=tuple(violations),
    )


def _check_reference(task: Task, violations: list[Violation]) -> None:
    graded = _produce_and_grade(task, REFERENCE_COMMAND, "reference", violations)
    if graded is None:
        return
    if not graded.result.passed:
        violations.append(Violation("reference_not_passing", _describe(graded.result)))


def _check_untouched(task: Task, violations: list[Violation]) -> None:
    graded = _produce_and_grade(task, None, "untouched", violations)
    if graded is not None and graded.result.passed:
        violations.append(
            Violation("untouched_passes", "grader passes the initial workspace")
        )


def _check_known_bad(task: Task, bad: KnownBad, violations: list[Violation]) -> None:
    label = f"known_bad {bad.path.name}"
    command = f'bash "$TASK_ROOT/known_bad/{bad.path.name}"'
    graded = _produce_and_grade(task, command, label, violations)
    if graded is None:
        return
    if graded.result.passed:
        violations.append(
            Violation("known_bad_passes", f"{label}: grader passes a wrong state")
        )
    elif bad.expect not in graded.result.reasons:
        violations.append(
            Violation(
                "known_bad_expect_missing",
                f"{label}: expected reason {bad.expect!r}, grader reasons {list(graded.result.reasons)}"
                + (f", error {graded.result.error}" if graded.result.error else ""),
            )
        )


def _produce_and_grade(
    task: Task, command: str | None, label: str, violations: list[Violation]
) -> _Graded | None:
    """Build one state in a fresh sandbox, grade it twice, and record any violation found."""
    sandbox = LocalSandbox(task, trusted=True)
    try:
        if command is not None:
            script = sandbox.exec(command, timeout_s=task.timeout_s)
            if script.timed_out or script.code != 0:
                violations.append(
                    Violation(_script_check(label), _script_problem(label, script))
                )
                return None
        first = _grade_once(task, sandbox)
        second = _grade_once(task, sandbox)
    finally:
        sandbox.close()
    if first.result != second.result:
        violations.append(
            Violation("grading_not_deterministic", f"{label}: two grading runs differ")
        )
    outside = tuple(sorted(set(first.outside_reads) | set(second.outside_reads)))
    if outside:
        violations.append(
            Violation(
                "grader_reads_outside_workspace", f"{label}: {', '.join(outside)}"
            )
        )
    return first


def _grade_once(task: Task, sandbox: LocalSandbox) -> _Graded:
    result, outside = grade_audited(task, sandbox.root, timeout_s=task.timeout_s)
    return _Graded(result=result, outside_reads=outside)


def _script_check(label: str) -> str:
    return (
        "reference_script_failed" if label == "reference" else "known_bad_script_failed"
    )


def _script_problem(label: str, script: ExecResult) -> str:
    status = "timed out" if script.timed_out else f"exited with code {script.code}"
    tail = script.stderr.strip()[-300:]
    return f"{label} script {status}: {tail}"


def _describe(result: GradeResult) -> str:
    if result.error is not None:
        return f"grader error: {result.error}"
    return f"passed={result.passed} score={result.score} reasons={list(result.reasons)}"
