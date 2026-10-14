"""prereg: seal a pre-registered plan, check that it has not changed, and analyse trials against it.

Exit status: seal and check return 0 when they succeed; a refusal or error returns 1. analyze returns
0 for SUPPORTED, 2 for FALSIFIED and 3 for INCONCLUSIVE, so a script can branch on the verdict.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from harness_evals import prereg, prereg_analysis
from harness_evals.prereg import PlanError

VERDICT_EXIT = {"SUPPORTED": 0, "FALSIFIED": 2, "INCONCLUSIVE": 3}


def register(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    parser = subparsers.add_parser(
        "prereg",
        help="seal a pre-registered plan, check it, and analyse trials against it",
        description="Pre-registration: seal a plan YAML, check for any later change, and analyse trial rows.",
    )
    actions = parser.add_subparsers(
        dest="prereg_action", metavar="ACTION", required=True
    )

    seal_parser = actions.add_parser("seal", help="write the seal file for a plan")
    seal_parser.add_argument("plan", type=Path, help="plan YAML file")
    seal_parser.add_argument(
        "--at",
        required=True,
        help="seal time as an ISO 8601 timestamp (recorded as given; no clock is read)",
    )
    seal_parser.add_argument(
        "--seal",
        type=Path,
        default=None,
        help="seal file (default: plan.sealed.json beside the plan)",
    )
    seal_parser.add_argument(
        "--replace", action="store_true", help="overwrite an existing seal file"
    )
    seal_parser.set_defaults(func=_seal)

    check_parser = actions.add_parser(
        "check", help="list every item that differs from the seal"
    )
    check_parser.add_argument("plan", type=Path, help="plan YAML file")
    check_parser.add_argument(
        "--seal",
        type=Path,
        default=None,
        help="seal file (default: plan.sealed.json beside the plan)",
    )
    check_parser.set_defaults(func=_check)

    analyze_parser = actions.add_parser(
        "analyze", help="evaluate the falsifier, sentinels and promotion bar"
    )
    analyze_parser.add_argument("plan", type=Path, help="plan YAML file")
    analyze_parser.add_argument(
        "--trials", required=True, type=Path, help="trial rows as JSON lines"
    )
    analyze_parser.add_argument(
        "--seal",
        type=Path,
        default=None,
        help="seal file (default: plan.sealed.json beside the plan)",
    )
    analyze_parser.set_defaults(func=_analyze)


def _seal_path(plan: Path, given: Path | None) -> Path:
    return given if given is not None else plan.parent / prereg.SEAL_FILE


def _seal(args: argparse.Namespace) -> int:
    seal_path = _seal_path(args.plan, args.seal)
    try:
        record = prereg.seal(
            args.plan, at=args.at, seal_path=seal_path, replace=args.replace
        )
    except PlanError as error:
        return _refuse(f"error: {error}")
    print(f"sealed {args.plan} -> {seal_path}")
    print(f"prereg_hash {record['prereg_hash']}")
    print(
        f"arms {len(record['arms'])}, tasks {len(record['tasks'])}, k {record['settings']['k']}"
    )
    return 0


def _check(args: argparse.Namespace) -> int:
    try:
        verification = prereg.verify(args.plan, _seal_path(args.plan, args.seal))
    except PlanError as error:
        return _refuse(f"error: {error}")
    if not verification.ok:
        return _refuse(_changed_report(verification.changes))
    print(f"OK: plan matches its seal (prereg_hash {verification.seal['prereg_hash']})")
    return 0


def _analyze(args: argparse.Namespace) -> int:
    seal_path = _seal_path(args.plan, args.seal)
    try:
        verification = prereg.verify(args.plan, seal_path)
    except PlanError as error:
        return _refuse(f"error: {error}")
    if not verification.ok:
        return _refuse(_changed_report(verification.changes))
    seal_record = verification.seal
    try:
        rows, problems = prereg_analysis.load_rows(args.trials)
    except PlanError as error:
        return _refuse(f"error: {error}")
    problems = problems + prereg_analysis.validate_rows(seal_record, rows)
    if problems:
        lines = [
            f"REFUSED: trial rows do not match the seal ({len(problems)} problem(s)):"
        ]
        lines.extend(f"  - {problem}" for problem in problems)
        return _refuse("\n".join(lines))
    analysis = prereg_analysis.analyze(seal_record, rows)
    print(prereg_analysis.render(analysis, seal_record))
    return VERDICT_EXIT[analysis.verdict]


def _changed_report(changes: tuple[str, ...]) -> str:
    lines = [f"CHANGED: plan no longer matches its seal ({len(changes)} item(s)):"]
    lines.extend(f"  - {change}" for change in changes)
    return "\n".join(lines)


def _refuse(message: str) -> int:
    print(message, file=sys.stderr)
    return 1
