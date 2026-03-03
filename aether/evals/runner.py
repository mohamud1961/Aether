from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import List

from .fixtures import list_fixtures, materialize_fixture
from .models import TestExecutionContext, TestResult
from .registry import list_packs, list_tests, resolve
from .reporting import write_reports
from .spec_index import write_spec_index
from .utils.artifacts import open_artifact_store
from .utils.enums import EnumRegistry
from .utils.events import load_events


class harnessAdapterunavailable(RuntimeError):
    """Raised when execution was requested without artifact source wiring."""


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="V1.1 evaluation runner")

    parser.add_argument(
        "--pack",
        default="all",
        choices=[
            "contract",
            "intent",
            "plan",
            "tool",
            "context",
            "loop",
            "audit",
            "security",
            "candidate",
            "capability",
            "userstory",
            "interface",
            "ingest",
            "phaseworkflow",
            "contextvnext",
            "toolhardening",
            "verification",
            "loopvnext",
            "determinism",
            "chopshop",
            "userstoryvnext",
            "integrity",
            "all",
        ],
        help="Pack to execute or inspect.",
    )
    parser.add_argument("--test", default=None, help="Optional test id filter, e.g. CT-01")
    parser.add_argument("--profile", default="eval", choices=["eval", "prod"])
    parser.add_argument("--mode", default="deterministic", choices=["deterministic", "stochastic", "replay"])
    parser.add_argument("--out", default="./eval_output", help="Output directory for reports and generated fixtures")
    parser.add_argument("--run-dir", default=None, help="Real harness run directory to evaluate")
    parser.add_argument("--artifact_dir", default=None, help="Existing artifact directory to evaluate")
    parser.add_argument(
        "--fixture",
        default=None,
        help=f"Named fixture to generate and evaluate. Available: {', '.join(list_fixtures())}",
    )

    parser.add_argument("--list-packs", action="store_true", help="List available packs")
    parser.add_argument("--list-tests", action="store_true", help="List available tests")
    parser.add_argument(
        "--build-spec-index",
        action="store_true",
        help="Build markdown test-id index file and exit",
    )
    parser.add_argument(
        "--spec-dir",
        default="phase_plans/spec/evals/v1_1",
        help="Spec directory used for markdown test-id index generation",
    )
    parser.add_argument(
        "--spec-index-out",
        default="aether/evals/generated/spec_test_id_index.json",
        help="Output path for generated markdown test-id index",
    )

    return parser


def _resolve_artifact_source(args: argparse.Namespace) -> tuple[Path, str | None]:
    if args.run_dir:
        run_dir = Path(args.run_dir)
        if not run_dir.exists():
            raise FileNotFoundError(f"Run directory does not exist: {run_dir}")
        return run_dir, None

    if args.artifact_dir:
        artifact_dir = Path(args.artifact_dir)
        if not artifact_dir.exists():
            raise FileNotFoundError(f"Artifact directory does not exist: {artifact_dir}")
        return artifact_dir, None

    if args.fixture:
        fixture_root = Path(args.out) / "fixtures"
        artifact_dir = materialize_fixture(args.fixture, fixture_root)
        return artifact_dir, args.fixture

    raise harnessAdapterunavailable(
        "harness adapter integration is not available in V1.1 eval runner. "
        "Provide --run-dir, --artifact_dir, or --fixture."
    )


def _print_pack_listing() -> None:
    for pack in list_packs():
        print(pack)


def _print_test_listing(pack: str, test_id: str | None) -> None:
    if test_id is not None:
        selected = resolve(pack=pack, test_id=test_id)
    else:
        selected = list_tests(None if pack == "all" else pack)

    for case in selected:
        print(f"{case.id}\t{case.pack}\t{case.name}")


def _run_selected_tests(args: argparse.Namespace) -> int:
    selected_tests = resolve(pack=args.pack, test_id=args.test)
    if not selected_tests:
        raise RuntimeError("No tests selected")

    artifact_dir, fixture_name = _resolve_artifact_source(args)
    events = load_events(artifact_dir)
    artifact_store = open_artifact_store(artifact_dir)
    enum_registry = EnumRegistry.load(artifact_dir / "enum_registry.json")

    context = TestExecutionContext(
        artifact_dir=artifact_dir,
        events=events,
        artifact_store=artifact_store,
        enum_registry=enum_registry,
        profile=args.profile,
        mode=args.mode,
        fixture_name=fixture_name,
        metadata={"selected_pack": args.pack},
    )

    results: List[TestResult] = []
    for case in selected_tests:
        started = perf_counter()
        result = case.run(context)
        elapsed_ms = round((perf_counter() - started) * 1000.0, 3)
        results.append(replace(result, timings={"elapsed_ms": elapsed_ms}))

    metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pack": args.pack,
        "profile": args.profile,
        "mode": args.mode,
        "artifact_dir": artifact_dir.as_posix(),
        "fixture_name": fixture_name,
        "selected_test": args.test,
        "total_tests": len(results),
    }

    report_paths = write_reports(args.out, results, metadata)

    passed = sum(1 for result in results if result.passed)
    failed = len(results) - passed
    print(f"Executed {len(results)} tests | passed={passed} failed={failed}")
    for label, path in report_paths.items():
        print(f"{label}: {path}")

    return 0 if failed == 0 else 2


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.build_spec_index:
        output_path = write_spec_index(args.spec_dir, args.spec_index_out)
        print(output_path)
        return 0

    if args.list_packs:
        _print_pack_listing()
        return 0

    if args.list_tests:
        _print_test_listing(args.pack, args.test)
        return 0

    return _run_selected_tests(args)


if __name__ == "__main__":
    raise SystemExit(main())
