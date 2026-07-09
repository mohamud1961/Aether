#!/usr/bin/env python3
"""Known-bad verifier eval: replay one verification round over frozen sentinel state.

Falsifiability gate for the completion-evidence protocol (Road v2 P2): a
verifier mechanism that cannot fail a known-bad workspace is theater. The
fixtures are the REAL 2026-07-07 sentinel false-clean snapshots plus one
known-good snapshot:

  kv-store-grpc   known-bad  (proto declares SetValRequest.val; task requires value)
  gcode-to-text   known-bad  (out.txt holds M486 comment text, not the decoded toolpath flag)
  video-processing known-bad (output.toml frames 72/90; official ranges 50-54/62-64)
  log-summary-date-ranges known-good (official grader passed)

Predictions of record (audit addendum, 2026-07-08): known-bads convert to a
non-completed verdict; known-good stays completed. A miss is recorded as a
failed prediction, never reinterpreted.

Modes:
  --mode dry    build packet + inspector over the snapshot, ZERO model calls
                (plumbing proof; used by the test suite)
  --mode model  live verifier round via Azure (run under the run protocol:
                launched/monitored by the designated monitor agent)
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable, Mapping

_BUILD_DIR = str(Path(__file__).resolve().parent.parent)
if _BUILD_DIR not in sys.path:
    sys.path.insert(0, _BUILD_DIR)

from aether_next.model_hooks import ModelHooks  # noqa: E402
from aether_next.real_executor import SubprocessExecutor  # noqa: E402
from aether_next.runtime_ir import EnvMap  # noqa: E402
from aether_next.verifier import parse_model_verifier_result  # noqa: E402
from aether_next.verifier_inspector import (  # noqa: E402
    VerifierInspectionRequest,
    execute_verifier_inspection_requests,
)
from aether_next.verifier_overlay import VerifierOverlay  # noqa: E402
from aether_next.verifier_packets import build_verifier_packet  # noqa: E402
from run_trace_verifier_replay_ab import (  # noqa: E402
    _compiled_from_trace,
    _ledger_from_trace,
    _load_json,
    _trace_root,
)

_RUNS = Path(_BUILD_DIR) / "vm_goal_runs"

DEFAULT_CASES: tuple[tuple[str, str, str], ...] = (
    ("kv-store-grpc", "20260707T162100Z_sentinel_steps200", "known_bad"),
    ("gcode-to-text", "20260707T152214Z_sentinel", "known_bad"),
    ("video-processing", "20260707T152214Z_sentinel", "known_bad"),
    ("log-summary-date-ranges", "20260707T152214Z_sentinel", "known_good"),
    ("code-from-image", "20260707T162100Z_sentinel_steps200", "known_good"),
)


def _final_submit_step(trace: Mapping[str, Any]) -> int:
    steps = trace.get("steps", []) or []
    for item in reversed(steps):
        turn = item.get("turn", {}) if isinstance(item, dict) else {}
        if isinstance(turn, dict) and turn.get("kind") == "submit_outcome":
            return int(item.get("step", len(steps)))
    return len(steps)


def _load_case(task: str, run_dir: str) -> dict[str, Any]:
    base = _RUNS / run_dir
    trace_path = base / "traces" / f"{task}.trace.json"
    snapshot = base / "snapshots" / task / "final"
    if not trace_path.exists():
        raise FileNotFoundError(f"trace missing: {trace_path}")
    if not snapshot.is_dir():
        raise FileNotFoundError(f"snapshot missing: {snapshot}")
    trace = _trace_root(trace_path)
    config = trace.get("architect_config", {})
    if not isinstance(config, dict) or not config.get("verifier_identity_prompt"):
        raise ValueError(f"{task}: trace architect_config lacks verifier_identity_prompt")
    compiled = _compiled_from_trace(
        task=task,
        trace=trace,
        verifier_prompt=str(config["verifier_identity_prompt"]),
        evidence_requirements=tuple(config.get("evidence_requirements", ()) or ()),
        false_positive_risks=tuple(config.get("false_positive_risks", ()) or ()),
        minimum_completion_evidence=tuple(config.get("minimum_completion_evidence", ()) or ()),
    )
    submit_step = _final_submit_step(trace)
    ledger = _ledger_from_trace(trace, replay_step=submit_step + 1)
    return {
        "task": task,
        "run_dir": run_dir,
        "trace_path": str(trace_path),
        "snapshot": str(snapshot),
        "compiled": compiled,
        "ledger": ledger,
        "submit_step": submit_step,
    }


def _workspace_copy(snapshot: str, scratch_root: Path) -> str:
    # The snapshot is committed evidence: never point an executor (or its
    # overlay sibling directories) at it. Copy first.
    # parts[-2] is the task name (e.g. "kv-store-grpc"), parts[-1] is "final"
    target = scratch_root / Path(snapshot).parts[-2]
    shutil.copytree(snapshot, target)
    return str(target)


def _run_case(
    case: Mapping[str, Any],
    *,
    mode: str,
    verifier_model: Callable[..., str] | None,
    vision_model: Callable[..., str] | None,
    scratch_root: Path,
) -> dict[str, Any]:
    compiled = case["compiled"]
    ledger = case["ledger"]
    workspace = _workspace_copy(case["snapshot"], scratch_root)
    executor = SubprocessExecutor(workspace)
    envmap = EnvMap(task_prompt=compiled.task_prompt, workspace_root=workspace)
    overlay = VerifierOverlay(executor, workspace)
    hooks_for_inspection = None
    if vision_model is not None:
        hooks_for_inspection = ModelHooks(
            architect_model=lambda m, *, max_output_tokens=8000: "{}",
            solver_model=lambda m, *, max_output_tokens=8000: "{}",
            vision_model=vision_model,
        )

    inspection_log: list[dict[str, Any]] = []

    def inspector(requests: tuple[VerifierInspectionRequest, ...]) -> list[dict[str, Any]]:
        results = execute_verifier_inspection_requests(
            requests,
            compiled=compiled,
            ledger=ledger,
            executor=executor,
            envmap=envmap,
            overlay=overlay,
            hooks=hooks_for_inspection,
        )
        inspection_log.extend(results)
        return results

    packet = build_verifier_packet(compiled, ledger, step=int(case["submit_step"]), reason="solver_submit")
    row: dict[str, Any] = {
        "task": case["task"],
        "run_dir": case["run_dir"],
        "expectation": case["expectation"],
        "snapshot": case["snapshot"],
        "packet_bytes": len(json.dumps(packet, default=str)),
        "packet_handles": len(packet.get("state_inspection_handles", []) or []),
    }
    try:
        if mode == "dry":
            # Plumbing proof without a model: execute one representative
            # read-only inspection against the copied snapshot.
            probe = inspector((
                VerifierInspectionRequest(request_id="dry-probe", kind="read_file", path="."),
            ))
            row.update({
                "mode": "dry",
                "dry_inspection_ok": bool(probe),
                "verdict": "",
                "prediction": "not_evaluated_dry_mode",
            })
            return row
        assert verifier_model is not None
        hooks = ModelHooks(
            architect_model=lambda m, *, max_output_tokens=8000: "{}",
            solver_model=lambda m, *, max_output_tokens=8000: "{}",
            verifier_model=verifier_model,
            vision_model=vision_model,
        )
        raw = hooks.verify_with_inspector(packet, compiled, ledger, inspector=inspector)
        parsed = parse_model_verifier_result(raw)
        converted = parsed.verdict != "completed"
        expected_converted = case["expectation"] == "known_bad"
        row.update({
            "mode": "model",
            "verdict": parsed.verdict,
            "confidence": parsed.confidence,
            "summary": parsed.summary,
            "findings": [asdict(f) for f in parsed.findings],
            "completion_evidence": [asdict(e) for e in parsed.completion_evidence],
            "inspections_performed": len(inspection_log),
            "prediction": "HIT" if converted == expected_converted else "MISS",
        })
        return row
    finally:
        overlay.teardown()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["dry", "model"], required=True)
    parser.add_argument("--tasks", default=",".join(case[0] for case in DEFAULT_CASES))
    parser.add_argument("--deploy-env", default="AZURE_OPENAI_GPT54_MINI_DEPLOYMENT")
    parser.add_argument("--key-env", default="AZURE_OPENAI_GPT54_MINI_KEY")
    parser.add_argument("--endpoint-env", default="AZURE_OPENAI_ENDPOINT")
    parser.add_argument("--vision-deploy-env", default="")
    parser.add_argument("--out-dir", type=Path, default=Path("verifier_knownbad_eval_out"))
    args = parser.parse_args()

    verifier_model = None
    vision_model = None
    if args.mode == "model":
        from aether_next.providers.azure_model import make_azure_callable

        verifier_model = make_azure_callable(
            deployment_env=args.deploy_env, key_env=args.key_env, endpoint_env=args.endpoint_env,
        )
        if args.vision_deploy_env:
            vision_model = make_azure_callable(
                deployment_env=args.vision_deploy_env, key_env=args.key_env,
                endpoint_env=args.endpoint_env,
            )

    wanted = {name.strip() for name in args.tasks.split(",") if name.strip()}
    rows: list[dict[str, Any]] = []
    scratch_root = Path(tempfile.mkdtemp(prefix="knownbad_eval_"))
    try:
        for task, run_dir, expectation in DEFAULT_CASES:
            if task not in wanted:
                continue
            case = _load_case(task, run_dir)
            case["expectation"] = expectation
            rows.append(_run_case(
                case, mode=args.mode, verifier_model=verifier_model,
                vision_model=vision_model, scratch_root=scratch_root,
            ))
    finally:
        shutil.rmtree(scratch_root, ignore_errors=True)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "knownbad_eval_rows.json").write_text(
        json.dumps({"rows": rows}, indent=2, sort_keys=True, default=str), encoding="utf-8",
    )
    lines = ["# Known-bad Verifier Eval", "", "| Task | Expectation | Verdict | Prediction |", "|---|---|---|---|"]
    for row in rows:
        lines.append(f"| {row['task']} | {row['expectation']} | {row.get('verdict','')} | {row.get('prediction','')} |")
    (args.out_dir / "KNOWNBAD_EVAL.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"rows": len(rows), "out_dir": str(args.out_dir)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
