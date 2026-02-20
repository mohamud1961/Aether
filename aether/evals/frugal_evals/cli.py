from __future__ import annotations

import argparse

from .certify import CertificationError, run_certification
from .chop_shop_patch import (
    build_t1_patch_tasks,
    run_patch_suite,
    score_patch_predictions,
)
from .chop_shop_search import (
    adapt_t2_external_run,
    build_t1_search_tasks,
    generate_baseline_search_predictions,
    score_search_predictions,
)
from .context_dump import dump_context_diagnostics
from .ingest import summarize_harness_run
from .scan_runs import run_scan_suite
from .task_000_gate import PASS, run_task_000_gate
from .tamper_fuzz import run_tamper_fuzz_suite
from .zombie import run_zombie_batch


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Frugal evals utilities")
    subparsers = parser.add_subparsers(dest="command", required=True)

    summary = subparsers.add_parser("summarize-run", help="Validate and summarize a harness run directory")
    summary.add_argument("--run-dir", required=True, help="Path to harness run directory")
    summary.add_argument(
        "--dump-context",
        action="store_true",
        help="Write context diagnostics for the first N steps",
    )
    summary.add_argument(
        "--steps",
        type=int,
        default=5,
        help="Number of initial run steps to include when --dump-context is set",
    )
    summary.add_argument(
        "--out-dir",
        default=None,
        help="Output directory for context diagnostic files (defaults to run dir)",
    )

    scan_runs = subparsers.add_parser(
        "scan-runs",
        help="Run strict parse, ingest compatibility, and episode extraction scans over run directories",
    )
    scan_runs.add_argument("--runs-root", required=True, help="Root containing run directories to scan")
    scan_runs.add_argument("--out-dir", required=True, help="Output directory for scan artifacts")
    scan_runs.add_argument("--top-buckets", type=int, default=10, help="Maximum error buckets to include per summary")

    zombie = subparsers.add_parser("run-zombie-batch", help="Run REPLAY_DECISION batch on episodes.jsonl")
    zombie.add_argument("--episodes", required=True, help="Path to episodes.jsonl")
    zombie.add_argument(
        "--out-root",
        default="runs/frugal/zombie",
        help="Directory where zombie run artifacts are written",
    )
    zombie.add_argument("--model-id", default="mock-zombie-v1", help="Model identifier for request/cost logging")
    zombie.add_argument("--adapter", default="mock", help="Adapter mode (currently only: mock)")
    zombie.add_argument("--limit", type=int, default=10, help="Max episodes to process")
    zombie.add_argument("--offset", type=int, default=0, help="Episode offset")
    zombie.add_argument(
        "--pricing-file",
        default=None,
        help="Optional path to model_pricing.json",
    )

    search_build = subparsers.add_parser(
        "build-search-tasks",
        help="Build Chop Shop Search-only tasks from aether runs (T1)",
    )
    search_build.add_argument("--runs-root", required=True, help="Path containing harness run directories")
    search_build.add_argument("--out", required=True, help="Output JSONL path for search tasks")
    search_build.add_argument(
        "--k-values",
        default="5,10,20",
        help="Comma-separated k values for scoring metadata",
    )
    search_build.add_argument(
        "--max-repo-files",
        type=int,
        default=2000,
        help="Maximum file entries to include in repo_map before truncation",
    )
    search_build.add_argument(
        "--intersect-patch-changes",
        action="store_true",
        help="Intersect T1 trace-derived gold files with git patch-changed files when available",
    )

    search_score = subparsers.add_parser(
        "score-search",
        help="Score Search-only predictions against task gold files",
    )
    search_score.add_argument("--predictions", required=True, help="Predictions JSONL")
    search_score.add_argument("--tasks", required=True, help="Search tasks JSONL")
    search_score.add_argument("--report", required=True, help="Output report JSON path")

    search_predict = subparsers.add_parser(
        "predict-search-baseline",
        help="Generate deterministic Search-only baseline predictions from tasks",
    )
    search_predict.add_argument("--tasks", required=True, help="Search tasks JSONL")
    search_predict.add_argument("--out", required=True, help="Output predictions JSONL")

    patch_build = subparsers.add_parser(
        "build-patch-tasks",
        help="Build Chop Shop Patch-only tasks from aether runs (T1)",
    )
    patch_build.add_argument("--runs-root", required=True, help="Path containing harness run directories")
    patch_build.add_argument("--out", required=True, help="Output JSONL path for patch tasks")
    patch_build.add_argument(
        "--min-tasks",
        type=int,
        default=5,
        help="Minimum number of tasks required (fail closed if unmet)",
    )
    patch_build.add_argument(
        "--max-tasks",
        type=int,
        default=20,
        help="Maximum tasks written",
    )
    patch_build.add_argument(
        "--max-repo-files",
        type=int,
        default=2000,
        help="Maximum file entries to include in repo_map before truncation",
    )

    patch_score = subparsers.add_parser(
        "score-patch",
        help="Score Patch-only predictions against task gold patches",
    )
    patch_score.add_argument("--predictions", required=True, help="Predictions JSONL")
    patch_score.add_argument("--tasks", required=True, help="Patch tasks JSONL")
    patch_score.add_argument("--report", required=True, help="Output report JSON path")
    patch_score.add_argument("--model-id", default=None, help="Optional model id label for report metadata")
    patch_score.add_argument(
        "--search-report",
        default=None,
        help="Optional Search-only report JSON to include in integrated Chop Shop component report",
    )

    patch_run = subparsers.add_parser(
        "chop-shop-patch",
        help="Run Patch-only mock adapter predictions and score them",
    )
    patch_run.add_argument("--tasks", required=True, help="Patch tasks JSONL")
    patch_run.add_argument("--model-id", required=True, help="Model identifier for report metadata")
    patch_run.add_argument("--out", required=True, help="Output report JSON path")
    patch_run.add_argument("--adapter", default="mock", help="Adapter mode (currently only: mock)")
    patch_run.add_argument(
        "--search-report",
        default=None,
        help="Optional Search-only report JSON to include in integrated Chop Shop component report",
    )
    patch_run.add_argument(
        "--predictions-out",
        default=None,
        help="Optional output JSONL path for generated patch predictions",
    )

    t2_adapter = subparsers.add_parser(
        "adapt-t2-search",
        help="Adapt one external run directory into a T2 Search-only task",
    )
    t2_adapter.add_argument("--external-run-dir", required=True, help="External run directory")
    t2_adapter.add_argument("--out", required=True, help="Output JSONL path")
    t2_adapter.add_argument("--task-id", default=None, help="Optional explicit task id override")
    t2_adapter.add_argument(
        "--k-values",
        default="5,10,20",
        help="Comma-separated k values for scoring metadata",
    )
    t2_adapter.add_argument(
        "--max-repo-files",
        type=int,
        default=2000,
        help="Maximum file entries to include in repo_map before truncation",
    )

    tamper = subparsers.add_parser(
        "run-tamper-fuzz",
        help="Run deterministic tamper fuzzing for hash-chain, CAS, and binding fail-closed checks",
    )
    tamper.add_argument("--run-dir", required=True, help="Path to source harness run directory")
    tamper.add_argument("--out-dir", required=True, help="Output directory for fuzz artifacts and report")
    tamper.add_argument(
        "--truncate-events",
        type=int,
        default=1,
        help="Number of trailing events to remove for truncation fuzz case",
    )

    task_000 = subparsers.add_parser(
        "task-000",
        help="Run Stage 2 spend gate canary task (Task 000)",
    )
    task_000.add_argument("--model-id", required=True, help="Model identifier for logging/cost tracking")
    task_000.add_argument(
        "--adapter",
        default="mock",
        help="Adapter mode: mock, mock_no_tool, mock_wrong_content, mock_no_file, mock_over_budget, mock_crash, claude, gemini",
    )
    task_000.add_argument("--max-steps", type=int, default=5, help="Max task steps (capped by task spec)")

    _add_certification_parser(
        subparsers=subparsers,
        command_name="certify",
        help_text="Run full frugal certification pipeline with deterministic evidence and cost ledger",
    )
    _add_certification_parser(
        subparsers=subparsers,
        command_name="run-certification",
        help_text="Alias for `certify`",
    )
    return parser


def _add_certification_parser(
    *,
    subparsers: argparse._SubParsersAction,
    command_name: str,
    help_text: str,
) -> None:
    cert = subparsers.add_parser(command_name, help=help_text)
    source_group = cert.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--runs-root", default=None, help="Root directory containing run subdirectories")
    source_group.add_argument(
        "--run-dirs",
        nargs="+",
        default=None,
        help="Explicit run directories to certify",
    )
    cert.add_argument("--out-dir", required=True, help="Output directory for certification artifacts")
    cert.add_argument(
        "--selection-prefix",
        default="frugal-cert-fixture_",
        help="If matching runs exist under --runs-root, select only this deterministic prefix",
    )
    cert.add_argument("--max-runs", type=int, default=None, help="Optional cap on selected runs")
    cert.add_argument("--zombie-model-id", default="mock-zombie-v1", help="Model identifier for zombie stage")
    cert.add_argument("--zombie-adapter", default="mock", help="Zombie adapter mode")
    cert.add_argument("--zombie-limit", type=int, default=None, help="Optional zombie episode cap")
    cert.add_argument("--zombie-offset", type=int, default=0, help="Zombie episode offset")
    cert.add_argument("--pricing-file", default=None, help="Optional pricing file for zombie stage")
    cert.add_argument("--k-values", default="5,10,20", help="Comma-separated k-values for Chop Shop scoring")
    cert.add_argument("--max-repo-files", type=int, default=2000, help="Repo map file cap for Chop Shop tasks")
    cert.add_argument("--truncate-events", type=int, default=1, help="Tamper fuzz truncation depth")


def _run_summarize(run_dir: str, *, dump_context: bool = False, steps: int = 5, out_dir: str | None = None) -> int:
    summary = summarize_harness_run(run_dir)
    print(
        "run_id={run_id} event_count={event_count} first_step_id={first_step_id} "
        "last_step_id={last_step_id} hash_chain_ok={hash_chain_ok}".format(**summary)
    )
    if not summary["hash_chain_ok"]:
        print(f"first_bad_event_id={summary['first_bad_event_id']}")
        return 2
    if dump_context:
        files = dump_context_diagnostics(run_dir, max_steps=steps, out_dir=out_dir)
        print(f"debug_context={files['debug_context_path']}")
        print(f"context_diagnostic={files['context_diagnostic_path']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "summarize-run":
        return _run_summarize(
            args.run_dir,
            dump_context=bool(args.dump_context),
            steps=int(args.steps),
            out_dir=args.out_dir,
        )

    if args.command == "scan-runs":
        summary = run_scan_suite(
            runs_root=args.runs_root,
            out_dir=args.out_dir,
            top_buckets=int(args.top_buckets),
        )
        print(
            "run_count={run_count} strict_ok={strict_ok_count} ingest_ok={ingest_ok_count} "
            "episode_ok={episode_ok_count} internal_exceptions={internal_exception_count} report={scan_runs_report_path}".format(
                **summary
            )
        )
        return 0

    if args.command == "run-zombie-batch":
        result = run_zombie_batch(
            episodes_path=args.episodes,
            out_root=args.out_root,
            model_id=args.model_id,
            adapter_mode=args.adapter,
            limit=args.limit,
            offset=args.offset,
            pricing_path=args.pricing_file,
        )
        print(
            "batch_id={batch_id} episode_count={episode_count} batch_dir={batch_dir} batch_summary={batch_summary_path}".format(
                **result
            )
        )
        return 0

    if args.command == "build-search-tasks":
        summary = build_t1_search_tasks(
            runs_root=args.runs_root,
            out_path=args.out,
            k_values=_parse_k_values(args.k_values),
            max_repo_files=int(args.max_repo_files),
            intersect_patch_changed=bool(args.intersect_patch_changes),
        )
        print(
            "runs_processed={runs_processed} tasks_written={tasks_written} out={out_path}".format(
                **summary
            )
        )
        return 0

    if args.command == "score-search":
        summary = score_search_predictions(
            predictions_path=args.predictions,
            tasks_path=args.tasks,
            report_path=args.report,
        )
        print(
            "tasks_scored={tasks_scored} report={report_path}".format(
                **summary
            )
        )
        return 0

    if args.command == "predict-search-baseline":
        summary = generate_baseline_search_predictions(
            tasks_path=args.tasks,
            out_path=args.out,
        )
        print(
            "tasks_scored={tasks_scored} predictor={predictor} out={out_path}".format(
                **summary
            )
        )
        return 0

    if args.command == "build-patch-tasks":
        summary = build_t1_patch_tasks(
            runs_root=args.runs_root,
            out_path=args.out,
            min_tasks=int(args.min_tasks),
            max_tasks=int(args.max_tasks),
            max_repo_files=int(args.max_repo_files),
        )
        print(
            "runs_processed={runs_processed} tasks_written={tasks_written} out={out_path}".format(
                **summary
            )
        )
        return 0

    if args.command == "score-patch":
        summary = score_patch_predictions(
            predictions_path=args.predictions,
            tasks_path=args.tasks,
            report_path=args.report,
            model_id=args.model_id,
            search_report_path=args.search_report,
        )
        print(
            "tasks_scored={tasks_scored} report={report_path}".format(
                **summary
            )
        )
        return 0

    if args.command == "chop-shop-patch":
        summary = run_patch_suite(
            tasks_path=args.tasks,
            model_id=args.model_id,
            report_path=args.out,
            adapter_mode=args.adapter,
            search_report_path=args.search_report,
            predictions_path=args.predictions_out,
        )
        print(
            "tasks_scored={tasks_scored} report={report_path} predictions={predictions_path}".format(
                **summary
            )
        )
        return 0

    if args.command == "adapt-t2-search":
        summary = adapt_t2_external_run(
            external_run_dir=args.external_run_dir,
            out_path=args.out,
            task_id=args.task_id,
            k_values=_parse_k_values(args.k_values),
            max_repo_files=int(args.max_repo_files),
        )
        print(
            "tasks_written={tasks_written} out={out_path} task_id={task_id}".format(
                **summary
            )
        )
        return 0

    if args.command == "run-tamper-fuzz":
        summary = run_tamper_fuzz_suite(
            run_dir=args.run_dir,
            out_dir=args.out_dir,
            truncation_events=int(args.truncate_events),
        )
        print(
            "case_count={case_count} passed_cases={passed_cases} report={report_path} report_hash={report_hash}".format(
                **summary
            )
        )
        return 0

    if args.command == "task-000":
        result = run_task_000_gate(
            model_id=args.model_id,
            adapter_mode=args.adapter,
            max_steps=int(args.max_steps),
        )
        if result.outcome == PASS:
            print(
                "PASS steps={steps}/{max_steps} cost=${cost:.3f}".format(
                    steps=result.steps_used,
                    max_steps=result.max_steps,
                    cost=result.cost_usd_est,
                )
            )
            return 0

        print(
            "{outcome} reason={reason} steps={steps}/{max_steps}".format(
                outcome=result.outcome,
                reason=result.reason_code,
                steps=result.steps_used,
                max_steps=result.max_steps,
            )
        )
        return 2

    if args.command in {"certify", "run-certification"}:
        try:
            summary = run_certification(
                out_dir=args.out_dir,
                runs_root=args.runs_root,
                run_dirs=args.run_dirs,
                selection_prefix=args.selection_prefix,
                max_runs=args.max_runs,
                zombie_model_id=args.zombie_model_id,
                zombie_adapter=args.zombie_adapter,
                zombie_limit=args.zombie_limit,
                zombie_offset=args.zombie_offset,
                pricing_path=args.pricing_file,
                k_values=_parse_k_values(args.k_values),
                max_repo_files=int(args.max_repo_files),
                truncate_events=int(args.truncate_events),
            )
        except CertificationError as exc:
            print(f"certification_error={exc}")
            return 2
        print(
            "pipeline_run_id={pipeline_run_id} evidence_bearing_hash={evidence_bearing_hash} report={certification_report_path}".format(
                **summary
            )
        )
        return 0

    raise RuntimeError(f"Unknown command: {args.command}")


def _parse_k_values(value: str) -> list[int]:
    parts = [item.strip() for item in value.split(",")]
    parsed: list[int] = []
    for part in parts:
        if not part:
            continue
        parsed.append(int(part))
    return parsed


if __name__ == "__main__":
    raise SystemExit(main())
