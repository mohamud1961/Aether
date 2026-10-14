"""run-one: run one agent on one task in a local sandbox, grade the result and print JSON."""

from __future__ import annotations

import argparse
import dataclasses
import json
from pathlib import Path

from harness_evals.agents.base import get_agent
from harness_evals.grading import grade
from harness_evals.sandbox import LocalSandbox
from harness_evals.task import load_task


def register(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    parser = subparsers.add_parser(
        "run-one",
        help="run one agent on one task and grade the result",
        description="Run an agent in a fresh local sandbox, grade the final state, print JSON.",
    )
    parser.add_argument("--task", required=True, type=Path, help="task directory")
    parser.add_argument(
        "--agent", required=True, help="agent name, e.g. reference or noop"
    )
    parser.add_argument(
        "--budget-s",
        type=_positive_float,
        default=None,
        help="agent time budget in seconds (default: the task's timeout_s)",
    )
    parser.set_defaults(func=_run)


def _positive_float(text: str) -> float:
    value = float(text)
    if value <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return value


def _run(args: argparse.Namespace) -> int:
    task = load_task(args.task)
    if task.admission == "debug" and args.agent not in {"reference", "noop"}:
        raise ValueError("isolated candidate-execution grader unavailable")
    agent = get_agent(args.agent)
    budget_s = args.budget_s if args.budget_s is not None else float(task.timeout_s)
    sandbox = LocalSandbox(task, trusted=args.agent == "reference")
    try:
        agent_result = agent.run(task, sandbox, budget_s)
        grade_result = grade(task, sandbox.root, timeout_s=task.timeout_s)
    finally:
        sandbox.close()
    output = {
        "task_id": task.id,
        "agent": args.agent,
        "budget_s": budget_s,
        "agent_result": dataclasses.asdict(agent_result),
        "grade": dataclasses.asdict(grade_result),
    }
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0
