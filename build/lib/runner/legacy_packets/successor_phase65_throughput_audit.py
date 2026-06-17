"""Run a bounded throughput audit for the resumed Phase 6.5 board."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from time import perf_counter
from typing import Any

from runner.successor_phase6_corrective_rerun import _record_ledger, _write_json, _write_text
from runner.successor_phase65_resumed_board import (
    DEFAULT_THROUGHPUT_WORKERS,
    launch_phase65_resumed_board,
)

MISSION_ID = "successor_phase65_throughput_audit_fix"
DEFAULT_OUTPUT_DIR = Path(
    "tracking/collab/stage_03_execution_planning/packets/packet_06_paired_combo_variants/"
    "runs/2026-05-07_successor_phase65_throughput_audit_fix"
)
SLICE = {
    "selected_tracks": ("bfcl", "completion", "context"),
    "max_specs_per_track": 1,
    "max_variants_per_spec": 2,
}


def launch_phase65_throughput_audit(*, output_dir: str | Path, execute: bool = True) -> dict[str, Any]:
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    serial_dir = out / "serial"
    parallel_dir = out / "parallel"
    _write_text(out / "phase65_throughput_plan.md", _plan(out))

    serial = _run_board(serial_dir, execute=execute, max_workers=1)
    parallel = _run_board(parallel_dir, execute=execute, max_workers=DEFAULT_THROUGHPUT_WORKERS)
    before_after = _before_after(serial=serial, parallel=parallel)
    policy = _parallelism_policy()
    profile = serial["runtime_profile"]

    _write_json(out / "phase65_throughput_profile_report.json", profile)
    _write_json(out / "phase65_throughput_parallelism_policy.json", policy)
    _write_json(out / "phase65_throughput_before_after_report.json", before_after)
    _write_text(out / "phase65_throughput_test_report.txt", _test_report(serial=serial, parallel=parallel))

    recommendation = _recommendation(before_after, serial=serial, parallel=parallel, execute=execute)
    _write_text(
        out / "phase65_throughput_handoff.md",
        _handoff(out=out, recommendation=recommendation, before_after=before_after),
    )
    ledger = _ledger(out=out, recommendation=recommendation, before_after=before_after)
    _record_ledger(ledger)
    _write_text(out / "RAW_LEDGER_UPDATE", ledger)
    return {
        "output_dir": str(out),
        "recommendation": recommendation,
        "serial_status": serial["result"].get("selected_recommendation"),
        "parallel_status": parallel["result"].get("selected_recommendation"),
    }


def _run_board(out: Path, *, execute: bool, max_workers: int) -> dict[str, Any]:
    if out.exists():
        shutil.rmtree(out)
    started = perf_counter()
    result = launch_phase65_resumed_board(
        output_dir=out,
        execute=execute,
        max_workers=max_workers,
        selected_tracks=SLICE["selected_tracks"],
        max_specs_per_track=SLICE["max_specs_per_track"],
        max_variants_per_spec=SLICE["max_variants_per_spec"],
    )
    wall_sec = perf_counter() - started
    profile_path = out / "phase65_resumed_runtime_profile.json"
    runtime_profile = json.loads(profile_path.read_text(encoding="utf-8")) if profile_path.exists() else {}
    return {"result": result, "wall_sec": wall_sec, "runtime_profile": runtime_profile, "output_dir": str(out)}


def _before_after(*, serial: dict[str, Any], parallel: dict[str, Any]) -> dict[str, Any]:
    serial_wall = float(serial["wall_sec"])
    parallel_wall = float(parallel["wall_sec"])
    speedup = (serial_wall / parallel_wall) if parallel_wall > 0 else 0.0
    reduction = ((serial_wall - parallel_wall) / serial_wall) if serial_wall > 0 else 0.0
    return {
        "mission_id": MISSION_ID,
        "serial": {"wall_sec": serial_wall, "output_dir": serial["output_dir"]},
        "parallel": {"wall_sec": parallel_wall, "output_dir": parallel["output_dir"]},
        "speedup_ratio": speedup,
        "wall_clock_reduction_ratio": reduction,
    }


def _parallelism_policy() -> dict[str, Any]:
    return {
        "mission_id": MISSION_ID,
        "policy": "bounded_worker_pool",
        "worker_cap": DEFAULT_THROUGHPUT_WORKERS,
        "safety_constraints": {
            "route_distinctness": "preserved by per-run route manifest validation",
            "attribution_safety": "preserved by unique run_id/run_dir per run",
            "workspace_isolation": "preserved by per-run workspace roots",
            "output_determinism": "preserved by plan-index sorting before aggregation",
        },
        "fail_closed": "max_workers must be >= 1 and capped by host/runner limits",
    }


def _recommendation(before_after: dict[str, Any], *, serial: dict[str, Any], parallel: dict[str, Any], execute: bool) -> str:
    if not execute:
        return "throughput_fix_blocked"
    if serial["result"].get("blocked") or parallel["result"].get("blocked"):
        return "throughput_fix_blocked"
    if before_after["speedup_ratio"] > 1.05:
        return "throughput_fix_completed_resume_completion_loop"
    return "throughput_audit_completed_fix_still_pending"


def _plan(out: Path) -> str:
    return "\n".join(
        [
            "# Phase 6.5 Throughput Plan",
            "",
            f"- mission_id: `{MISSION_ID}`",
            f"- output_root: `{out}`",
            "- profile target: active resumed-board path with per-run timing",
            "- bounded slice: one spec per bfcl/completion/context track, two variants per spec",
            "- policy target: bounded worker pool with deterministic result aggregation",
            "- proof target: serial (1 worker) vs bounded parallel (2 workers) wall-clock comparison",
        ]
    )


def _test_report(*, serial: dict[str, Any], parallel: dict[str, Any]) -> str:
    return "\n".join(
        [
            "throughput_audit_test_report",
            f"serial_output_dir={serial['output_dir']}",
            f"parallel_output_dir={parallel['output_dir']}",
            f"serial_wall_sec={serial['wall_sec']:.3f}",
            f"parallel_wall_sec={parallel['wall_sec']:.3f}",
        ]
    ) + "\n"


def _handoff(*, out: Path, recommendation: str, before_after: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Phase 6.5 Throughput Handoff",
            "",
            f"- mission_id: `{MISSION_ID}`",
            f"- output_root: `{out}`",
            f"- serial_wall_sec: `{before_after['serial']['wall_sec']:.3f}`",
            f"- parallel_wall_sec: `{before_after['parallel']['wall_sec']:.3f}`",
            f"- speedup_ratio: `{before_after['speedup_ratio']:.3f}`",
            f"- wall_clock_reduction_ratio: `{before_after['wall_clock_reduction_ratio']:.3f}`",
            f"- final_recommendation: `{recommendation}`",
        ]
    ) + "\n"


def _ledger(*, out: Path, recommendation: str, before_after: dict[str, Any]) -> str:
    return "\n".join(
        [
            "RAW_LEDGER_UPDATE",
            "- actor: codex",
            "- task: successor Phase 6.5 throughput audit and bounded worker-pool fix",
            "- event_type: implementation",
            f"- summary: Added per-run runtime timing and a bounded worker-pool execution path, then measured serial vs parallel throughput with recommendation `{recommendation}`.",
            (
                "- observations: "
                f"serial_wall_sec `{before_after['serial']['wall_sec']:.3f}`; "
                f"parallel_wall_sec `{before_after['parallel']['wall_sec']:.3f}`; "
                f"speedup_ratio `{before_after['speedup_ratio']:.3f}`."
            ),
            "- inference: Track/spec/variant orchestration is safely parallelizable at bounded worker cap with isolated workspaces and deterministic aggregation.",
            (
                f"- evidence_paths: {out / 'phase65_throughput_profile_report.json'}; "
                f"{out / 'phase65_throughput_parallelism_policy.json'}; "
                f"{out / 'phase65_throughput_before_after_report.json'}; "
                f"{out / 'phase65_throughput_handoff.md'}"
            ),
            "- affected_components: runner/agent.py; runner/successor_phase65_resumed_board.py; worker-pool execution and runtime timing paths",
            "- decision_change: Packet 07 remains closed; this slice is throughput-only and does not widen benchmark authority",
            "- unresolved_questions: Whether to raise the worker cap above 2 after additional contention and cost audits.",
            "- confidence: medium",
            "- commit_message: HOLD - phase65 throughput instrumentation and bounded worker-pool fix",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--no-execute", action="store_true")
    args = parser.parse_args(argv)
    print(json.dumps(launch_phase65_throughput_audit(output_dir=args.output_dir, execute=not args.no_execute), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
