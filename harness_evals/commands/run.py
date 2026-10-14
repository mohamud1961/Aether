"""run: run one agent over every task under a directory, k attempts each, and write trial rows.

Each finished trial is appended to --out as it completes, so an interrupted run keeps its rows.
Re-running with --resume continues the same file and skips every (arm, task, attempt) it holds.
Invalid trials are written with their reason and are not re-run.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from harness_evals.agents.base import UnknownAgent, get_agent
from harness_evals.task import discover
from harness_evals.trials import (
    SANDBOX_KINDS,
    Arm,
    TrialRow,
    existing_run_id,
    new_run_id,
    run_trials,
)


def register(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    parser = subparsers.add_parser(
        "run",
        help="run an agent over a task directory and write trial rows",
        description=(
            "Run arms x tasks x attempts. Each attempt runs in a fresh sandbox, is graded by the task's "
            "hidden grader, and is written as one JSON line to --out."
        ),
    )
    parser.add_argument(
        "--tasks",
        required=True,
        type=Path,
        help="directory of task directories, or one task",
    )
    parser.add_argument(
        "--agent", required=True, help="agent name, e.g. reference, noop or minimal"
    )
    parser.add_argument(
        "--include-smoke",
        action="store_true",
        help="diagnostic override; no capability claim",
    )
    parser.add_argument("--endpoint", default=None, help="OpenAI-compatible base URL")
    parser.add_argument("--command", default=None, help="CLI command; no secrets")
    parser.add_argument("--input-per-million", type=float, default=None)
    parser.add_argument("--output-per-million", type=float, default=None)
    parser.add_argument(
        "--model", default=None, help="model name, passed to agents that take one"
    )
    parser.add_argument(
        "--arm",
        default=None,
        help="arm name written to the rows (default: the agent name)",
    )
    parser.add_argument(
        "--k", type=_positive_int, default=1, help="attempts per task (default 1)"
    )
    parser.add_argument(
        "--sandbox",
        choices=SANDBOX_KINDS,
        default=None,
        help="candidate default docker; reference/floor default local",
    )
    parser.add_argument(
        "--out", required=True, type=Path, help="trial rows JSONL to write"
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="run id stored in every row (default: the id already in --out when resuming, else generated)",
    )
    parser.add_argument(
        "--resume", action="store_true", help="continue an existing --out file"
    )
    parser.set_defaults(func=_run)


def _positive_int(text: str) -> int:
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return value


def _run(args: argparse.Namespace) -> int:
    try:
        tasks = discover(args.tasks, include_smoke=args.include_smoke)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if not tasks:
        print(
            f"error: no task directories (task.yaml) under {args.tasks}",
            file=sys.stderr,
        )
        return 2
    try:
        options = {
            key: value
            for key, value in {
                "model": args.model,
                "endpoint": args.endpoint,
                "command": args.command,
                "input_per_million": args.input_per_million,
                "output_per_million": args.output_per_million,
            }.items()
            if value is not None
        }
        agent = get_agent(args.agent, **options)
    except (UnknownAgent, TypeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    version = (
        args.agent
        if not options
        else args.agent + ":" + json.dumps(options, sort_keys=True)
    )
    arm = Arm(name=args.arm or args.agent, agent=agent, version=version)
    try:
        run_id = (
            args.run_id
            or (existing_run_id(args.out) if args.resume else None)
            or new_run_id()
        )
        rows = run_trials(
            tasks,
            [arm],
            k=args.k,
            sandbox_kind=args.sandbox
            or ("local" if args.agent in {"reference", "noop"} else "docker"),
            out_path=args.out,
            run_id=run_id,
            resume=args.resume,
            on_row=_print_progress,
        )
    except (FileExistsError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    valid = sum(1 for row in rows if row.valid)
    print(
        f"run {run_id}: {len(rows)} rows in {args.out} ({valid} valid, {len(rows) - valid} invalid)"
    )
    return 0


def _print_progress(row: TrialRow) -> None:
    if row.valid:
        status = "passed" if row.passed else "failed"
    else:
        status = f"invalid: {row.invalid_reason}"
    print(
        f"{row.arm} {row.task_id} attempt {row.attempt}: {status} ({row.wall_s:.1f} s)",
        flush=True,
    )
