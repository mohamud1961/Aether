"""validate-graders: check each task's grader against its reference and known-bad states.

Exit status 0 only when every task is clean and at least one task was found.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from harness_evals.validity import ValidityReport, validate_tree


def register(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    parser = subparsers.add_parser(
        "validate-graders",
        help="check every task grader against its reference and known-bad states",
        description="Find every task directory (task.yaml) under ROOT and validate its grader.",
    )
    parser.add_argument(
        "root",
        type=Path,
        help="directory holding task directories, or one task directory",
    )
    parser.set_defaults(func=_run)


def render(report: ValidityReport) -> str:
    if not report.tasks:
        return f"no task directories (task.yaml) found under {report.root}"
    lines = [f"{'task':<40} {'known_bad':>9}  status"]
    for task in report.tasks:
        status = "ok" if task.ok else f"VIOLATIONS ({len(task.violations)})"
        lines.append(f"{task.task_id:<40} {task.known_bad_count:>9}  {status}")
    for task in report.tasks:
        for violation in task.violations:
            lines.append(f"  {task.task_id}: [{violation.check}] {violation.detail}")
    clean = sum(1 for task in report.tasks if task.ok)
    lines.append(f"{clean}/{len(report.tasks)} tasks clean")
    return "\n".join(lines)


def _run(args: argparse.Namespace) -> int:
    report = validate_tree(args.root)
    print(render(report))
    return 0 if report.ok else 1
