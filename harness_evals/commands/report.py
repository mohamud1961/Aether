"""report: scoreboard markdown from a trial rows JSONL file (written by `run`)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from harness_evals.trial_report import render_report
from harness_evals.trials import TRACE_SUFFIX, read_rows, read_traces, trace_path_for


def register(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    parser = subparsers.add_parser(
        "report",
        help="scoreboard markdown from a trial rows file",
        description=(
            "Per-task and overall pass rates with Wilson 95% intervals, pass@k and pass^k, invalid trials "
            "by reason, and a trajectory summary. Reads the trace sidecar (<stem>"
            + TRACE_SUFFIX
            + ") when present."
        ),
    )
    parser.add_argument("rows", type=Path, help="trial rows JSONL file")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="write the markdown here instead of stdout",
    )
    parser.set_defaults(func=_run)


def _run(args: argparse.Namespace) -> int:
    if not args.rows.is_file():
        print(f"error: {args.rows} is not a file", file=sys.stderr)
        return 2
    try:
        rows = read_rows(args.rows)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    traces_path = trace_path_for(args.rows)
    traces = read_traces(traces_path) if traces_path.is_file() else {}
    text = render_report(rows, traces, source=args.rows.name)
    if args.out is None:
        print(text, end="")
        return 0
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8")
    print(f"wrote {args.out}")
    return 0
