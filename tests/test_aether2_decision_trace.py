from __future__ import annotations

import importlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path


def _load_module():
    module_path = Path(__file__).resolve().parents[1] / "tools" / "aether2_decision_trace.py"
    spec = importlib.util.spec_from_file_location("aether2_decision_trace_test_module", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.collect_decision_trace_bundle is HARNESS_TRACE.collect_decision_trace_bundle
    assert module.render_summary is HARNESS_TRACE.render_summary
    assert module.build_parser is HARNESS_TRACE.build_parser
    assert module.main is HARNESS_TRACE.main
    assert module.NON_COT_NOTE == HARNESS_TRACE.NON_COT_NOTE
    assert str(module.__file__).endswith("tools/aether2_decision_trace.py")
    return module


HARNESS_TRACE = importlib.import_module("harness.aether2.traces.decision_trace")


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _write_reasoning_trace_fixture(run_root: Path) -> tuple[Path, Path]:
    receipts_dir = run_root / ".aether2" / "host_receipts" / "receipts"
    trace_path = run_root / ".aether2" / "host_receipts" / "traces" / "reasoning_trace.json"
    model_exchange = _write_json(
        receipts_dir / "model_exchange_1.json",
        {
            "call_idx": 1,
            "call_role": "normal",
            "request_context": {
                "env_contract": {"version": "aether2_env_contract_v1", "digest": "digest-a"},
                "tail_state": {"plan": ""},
                "tool_schema_digest": "tool-digest",
            },
            "request_messages": [],
            "response": {"text": "inspect", "tool_calls": []},
        },
    )
    _write_json(
        trace_path,
        {
            "schema_version": 1,
            "step_count": 1,
            "model_call_count": 1,
            "finalize_reason": "task_done",
            "verifier_clean": True,
            "steps": [
                {
                    "schema_version": 1,
                    "step": 1,
                    "model_call_idx": 1,
                    "call_role": "normal",
                    "decision_kind": "task_done",
                    "assistant_text": "inspect then finish",
                    "assistant_plan_after_turn": "inspect",
                    "model_input_digests": {
                        "immutable_prefix_digest": "prefix-a",
                        "task_instruction_digest": "task-a",
                        "orientation_digest": "orientation-a",
                        "tool_schema_digest": "tool-a",
                        "tail_digest": "tail-a",
                        "completion_contract_digest": "contract-a",
                        "compaction_generation": 0,
                    },
                    "tool_call_count": 1,
                    "tool_calls": [
                        {
                            "step": 1,
                            "tool_name": "run_command",
                            "arguments": {"cmd": "cat input.txt"},
                            "observation": {
                                "tool": "run_command",
                                "exit_code": 0,
                                "raw_log_path": str(run_root / "workspace" / ".aether2" / "raw_logs" / "cmd1.json"),
                                "stdout_head": "hello",
                                "stdout_tail": "",
                                "stderr_head": "",
                                "stderr_tail": "",
                                "files_changed": [],
                                "process_delta": {},
                                "blind_retry_blocked": False,
                                "error": None,
                                "duration_sec": 0.1,
                                "cwd": str(run_root / "workspace"),
                                "truncated": False,
                            },
                        }
                    ],
                    "visible_context": {
                        "model_exchange_ref": str(model_exchange),
                        "tail_state": {"plan": ""},
                        "completion_contract": {
                            "unresolved_requirements": ["recover the structural value"],
                            "next_required_evidence": ["independent parse"],
                            "weak_evidence": [],
                            "verifier_blockers": [],
                        },
                        "model_visible_requirements": {
                            "unresolved_requirements": ["recover the structural value"],
                            "next_required_evidence": ["independent parse"],
                            "weak_evidence": [],
                            "verifier_blockers": [],
                            "persistent_blockers": [],
                        },
                    },
                    "pre_step_evidence_ledger": {"requirements": []},
                    "post_step_evidence_ledger": {"requirements": []},
                    "progress": {
                        "requirement_advanced": False,
                        "stronger_evidence_added": False,
                        "no_progress": True,
                    },
                    "task_done": {"called": True, "summary": "done", "checks": ["cat out.txt"]},
                    "finalize_reason": "task_done",
                }
            ],
            "non_step_model_calls": [],
        },
    )
    return trace_path, model_exchange


def _route_event(*, seq: int, event_type: str, phase: str, details: dict) -> dict:
    return {
        "artifact_refs": [],
        "correlation_id": None,
        "event_type": event_type,
        "payload": {"details": details},
        "phase": phase,
        "seq": seq,
        "ts_utc": f"2026-06-13T00:00:{seq:02d}Z",
    }


def _write_route_trace_fixture(run_root: Path) -> tuple[Path, Path, Path, Path]:
    row_dir = run_root / "rows" / "task_route"
    route_trace = row_dir / "route_trace" / "run_events.jsonl"
    trace_json = row_dir / "traces" / "trace.json"
    artifact_bundle = row_dir / "artifacts" / "artifact_bundle.json"
    verifier_output = row_dir / "artifacts" / "verifier_output.json"
    grader_output = row_dir / "artifacts" / "grader_output.json"

    route_events = [
        _route_event(seq=0, event_type="oriented", phase="orient", details={"initial_messages": 2, "timing_sec": 0.01}),
        _route_event(seq=1, event_type="sandbox_started", phase="tool", details={"sandbox_type": "docker", "timing_sec": 0.1, "tool_count": 1}),
        _route_event(
            seq=2,
            event_type="model_completion",
            phase="execute",
            details={
                "assistant_text": "",
                "assistant_text_char_count": 0,
                "reasoning_summary": None,
                "reasoning_summary_char_count": 0,
                "reasoning_token_count": 0,
                "status": None,
                "step": 0,
                "tool_call_count": 1,
                "tool_calls": [
                    {
                        "arguments": {"command": "printf hello"},
                        "id": "call-1",
                        "name": "raw_bash",
                    }
                ],
            },
        ),
        _route_event(
            seq=3,
            event_type="raw_bash_result",
            phase="execute",
            details={
                "command": "printf hello",
                "decision_source": "tool_executor",
                "exit_code": 0,
                "normalized_payload": {"command": "printf hello", "tool_name": "raw_bash"},
                "permission_signal_detected": False,
                "proxy_permission_signal_detected": False,
                "proxy_runtime_signal_detected": False,
                "raw_payload": {"arguments": {"command": "printf hello"}, "id": "call-1", "name": "raw_bash"},
                "reason_code": "tool_runtime_success",
                "result_class": "success",
                "runtime_signal_detected": False,
                "signal_attribution_scope": "visible",
                "step": 0,
                "timed_out": False,
                "tool_call_contract_class": "ok",
                "tool_name": "raw_bash",
            },
        ),
        _route_event(
            seq=4,
            event_type="verification_completed",
            phase="verify",
            details={
                "layer_statuses": {
                    "L0_inline_assertion": "fail",
                    "L1_verifier_artifact": "pass",
                    "L4_final_acceptance": "fail",
                },
                "reason_codes": ["verification_completion_not_claimed", "layered_acceptance_rejected"],
                "substitution_violations": [],
                "verified": False,
            },
        ),
        _route_event(
            seq=5,
            event_type="loop_completed",
            phase="execute",
            details={"status": "max_steps_exhausted", "step_count": 1},
        ),
    ]
    route_trace.parent.mkdir(parents=True, exist_ok=True)
    trace_json.parent.mkdir(parents=True, exist_ok=True)
    route_trace.write_text("\n".join(json.dumps(event, sort_keys=True) for event in route_events) + "\n", encoding="utf-8")

    trace_json.write_text(
        json.dumps({"events": [{"command": "printf hello", "event_type": "tool_call", "exit_code": 0, "tool_name": "raw_bash"}], "meta": {"task_id": "task_route"}}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_json(
        artifact_bundle,
        {
            "authority_label": "official_task_verifier_execution",
            "environment_manifest_ref": str(row_dir / "artifacts" / "environment_manifest.json"),
            "grader_ref": str(grader_output),
            "route_trace_ref": str(route_trace),
            "trace_refs": [str(trace_json)],
            "verifier_ref": str(verifier_output),
        },
    )
    _write_json(
        verifier_output,
        {
            "benchmark_case_id": "demo-case",
            "returncode": 0,
            "reward": "0",
            "status": "fail",
            "stderr_tail": "missing verifier evidence",
            "stdout_tail": "verifier ran",
        },
    )
    _write_json(
        grader_output,
        {
            "benchmark_case_id": "demo-case",
            "failure_class": "verification_grading",
            "reason_codes": ["terminalbench_verifier_failed"],
            "score": 0.0,
            "verdict": "fail",
        },
    )
    return route_trace, trace_json, artifact_bundle, row_dir


def _write_embedded_combined_fixture(root: Path) -> Path:
    combined = root / "rows" / "attempt1_rows_combined.jsonl"
    marker = root / "attempt_1" / "20260613T010101Z" / "task_alpha" / "row.json"
    row = {
        "task_id": "task_alpha",
        "run_id": "alpha-run",
        "row_status": "fail",
        "verifier_exit_code": 1,
        "run_result": {
            "tool_invocations": [
                {
                    "step": 1,
                    "tool_name": "run_command",
                    "arguments": {"command": "cat input.txt"},
                    "envelope": {
                        "blind_retry_blocked": False,
                        "cwd": str(marker.parent),
                        "duration_sec": 0.01,
                        "exit_code": 0,
                        "files_changed": [],
                        "process_delta": {},
                        "raw_log_path": str(marker.parent / "raw_1.json"),
                        "stderr_head": "",
                        "stderr_tail": "",
                        "stdout_head": "alpha",
                        "stdout_tail": "",
                    },
                }
            ],
            "discrepancy_reports": [
                {
                    "requirements": [
                        {
                            "requirement": "must verify the output",
                            "verdict": "unverifiable",
                            "evidence": "no verifier evidence was recorded",
                        }
                    ]
                }
            ],
        },
    }
    combined.parent.mkdir(parents=True, exist_ok=True)
    combined.write_text(
        "### FILE: {marker}\n{body}\n".format(marker=marker, body=json.dumps(row, indent=2, sort_keys=True)),
        encoding="utf-8",
    )
    return combined


def test_combined_row_parsing_and_provenance_tagging(tmp_path) -> None:
    mod = _load_module()
    combined = _write_embedded_combined_fixture(tmp_path)

    bundle = mod.collect_decision_trace_bundle([combined])

    assert bundle["summary"]["row_count"] == 1
    row = bundle["rows"][0]
    assert row["source_kind"] == "combined_row_file"
    assert row["attempt_ref"] == "1"
    assert row["attempt_provenance"] == "source_path"
    assert row["source_run_ref"]["run_path"].endswith("attempt_1/20260613T010101Z")
    assert row["primary_receipt_mode"] == "embedded_tool_invocations"
    assert row["events"][0]["source_provenance"]["attempt_provenance"] == "source_path"
    assert row["events"][0]["preceding_observation"]["status"] == "start_of_run"
    assert row["events"][0]["resulting_observation"]["stdout_head"] == "alpha"
    assert row["events"][0]["evidence_classification"]["action_kind"] == "inspect"
    assert row["unresolved_verifier_gaps"][0]["gap_type"] == "discrepancy_report"


def test_missing_row_tolerance_and_external_receipt_bundling(tmp_path) -> None:
    mod = _load_module()
    run_root = tmp_path / "run_root"
    route_trace, trace_json, artifact_bundle, row_dir = _write_route_trace_fixture(run_root)
    result_rows = run_root / "result_rows.jsonl"
    result_rows.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "task_id": "task_route",
                        "run_id": "route-run",
                        "row_status": "fail",
                        "verifier_exit_code": 1,
                        "artifact_refs": [str(artifact_bundle)],
                        "trace_refs": [str(trace_json), str(route_trace)],
                        "verifier_ref": str(row_dir / "artifacts" / "verifier_output.json"),
                        "grader_ref": str(row_dir / "artifacts" / "grader_output.json"),
                    },
                    sort_keys=True,
                ),
                "{\"task_id\": \"broken\"",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    bundle = mod.collect_decision_trace_bundle([run_root])

    assert bundle["summary"]["row_count"] == 2
    assert bundle["summary"]["parse_issue_count"] >= 1


def test_reasoning_trace_steps_become_primary_events(tmp_path) -> None:
    mod = _load_module()
    run_root = tmp_path / "reasoning_run"
    trace_path, model_exchange = _write_reasoning_trace_fixture(run_root)
    result_rows = run_root / "result_rows.jsonl"
    result_rows.write_text(
        json.dumps(
            {
                "task_id": "reasoning-task",
                "run_id": "reasoning-run",
                "row_status": "pass",
                "verifier_exit_code": 0,
                "reasoning_trace_ref": str(trace_path),
                "run_dir": str(run_root),
                "artifacts": str(run_root / "artifacts"),
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    bundle = mod.collect_decision_trace_bundle([run_root])

    assert bundle["summary"]["event_count"] == 1
    row = bundle["rows"][0]
    assert row["primary_receipt_mode"] == "reasoning_trace_steps"
    assert row["events"][0]["tool_name"] == "run_command"
    assert row["events"][0]["receipt_refs"][1] == str(model_exchange)
    assert row["parse_issues"] == []


def test_summary_mentions_non_cot_and_unresolved_gaps(tmp_path) -> None:
    mod = _load_module()
    run_root = tmp_path / "run_root"
    route_trace, trace_json, artifact_bundle, row_dir = _write_route_trace_fixture(run_root)
    result_rows = run_root / "result_rows.jsonl"
    result_rows.write_text(
        json.dumps(
            {
                "task_id": "task_route",
                "run_id": "route-run",
                "row_status": "fail",
                "verifier_exit_code": 1,
                "artifact_refs": [str(artifact_bundle)],
                "trace_refs": [str(trace_json), str(route_trace)],
                "verifier_ref": str(row_dir / "artifacts" / "verifier_output.json"),
                "grader_ref": str(row_dir / "artifacts" / "grader_output.json"),
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    bundle = mod.collect_decision_trace_bundle([run_root])
    summary = mod.render_summary(bundle)

    assert "This is not private chain-of-thought" in summary
    assert "# Observable Decision Trace Summary" in summary
    assert "Unresolved verifier gaps" in summary
    assert "task_route" in summary


def test_cli_smoke_writes_bundle(tmp_path) -> None:
    mod = _load_module()
    run_root = tmp_path / "run_root"
    route_trace, trace_json, artifact_bundle, row_dir = _write_route_trace_fixture(run_root)
    result_rows = run_root / "result_rows.jsonl"
    result_rows.write_text(
        json.dumps(
            {
                "task_id": "task_route",
                "run_id": "route-run",
                "row_status": "fail",
                "verifier_exit_code": 1,
                "artifact_refs": [str(artifact_bundle)],
                "trace_refs": [str(trace_json), str(route_trace)],
                "verifier_ref": str(row_dir / "artifacts" / "verifier_output.json"),
                "grader_ref": str(row_dir / "artifacts" / "grader_output.json"),
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    out_root = tmp_path / "bundle_out"

    proc = subprocess.run(
        [sys.executable, str(Path(mod.__file__)), "--root", str(run_root), "--out", str(out_root)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert proc.returncode == 0, proc.stderr
    assert (out_root / "decision_trace.jsonl").exists()
    assert (out_root / "decision_trace_summary.md").exists()
    payload = json.loads(proc.stdout.strip())
    assert payload["row_count"] == 1
    assert payload["parse_issue_count"] == 0
    assert payload["output_dir"] == str(out_root.resolve())


def test_verifier_context_payload_becomes_visible_events_and_preserves_blockers(tmp_path: Path) -> None:
    mod = _load_module()
    root = tmp_path / "run"
    root.mkdir()
    (root / "result_rows.jsonl").write_text(
        json.dumps(
            {
                "task_id": "alpha",
                "attempt": 5,
                "row_status": "fail",
                "verifier_exit_code": 1,
                "phase_rows_path": str(root / "phase_rows.jsonl"),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    verifier_context = root / "verifier_context"
    verifier_context.mkdir()
    (verifier_context / "alpha.json").write_text(
        json.dumps(
            {
                "task_id": "alpha",
                "tool_invocations": [
                    {
                        "step": 3,
                        "tool_name": "run_command",
                        "arguments": {"cmd": "pytest tests/test_alpha.py"},
                        "envelope": {
                            "exit_code": 0,
                            "stdout_head": "ok",
                            "stderr_tail": "",
                            "raw_log_path": str(root / "logs" / "alpha.log"),
                        },
                    }
                ],
                "persistent_blockers": [
                    {
                        "blocker_id": "blocker-1",
                        "status": "active",
                        "age_steps": 3,
                        "reason_codes": ["unchanged_blocker"],
                    }
                ],
                "verifier_suppression_metrics": {"suppressed_verifier_calls": 1},
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    result = mod.collect_decision_trace_bundle([root])
    assert result["summary"]["row_count"] == 1
    trace = result["rows"][0]
    assert trace["primary_receipt_mode"] == "verifier_context_tool_invocations"
    assert trace["events"][0]["visible_action"] == "pytest tests/test_alpha.py"
    assert trace["persistent_blockers"][0]["blocker_id"] == "blocker-1"
    assert trace["persistent_blockers"][0]["status"] == "active"
    assert trace["persistent_blockers"][0]["age_steps"] == 3
    assert trace["verifier_suppression_metrics"]["suppressed_verifier_calls"] == 1


def test_reasoning_trace_ref_is_discoverable_and_summarized(tmp_path: Path) -> None:
    mod = _load_module()
    root = tmp_path / "run"
    row_dir = root / "rows" / "task_route"
    row_dir.mkdir(parents=True, exist_ok=True)
    reasoning_trace = row_dir / "traces" / "reasoning_trace.json"
    reasoning_trace.parent.mkdir(parents=True, exist_ok=True)
    reasoning_trace.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "task_id": "task_route",
                "step_count": 1,
                "model_call_count": 1,
                "finalize_reason": "task_done",
                "verifier_clean": False,
                "steps": [
                    {
                        "step": 1,
                        "call_role": "normal",
                        "decision_kind": "task_done",
                        "assistant_text": "done",
                        "progress": {"no_progress": False},
                    }
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "result_rows.jsonl").write_text(
        json.dumps(
            {
                "task_id": "task_route",
                "run_id": "route-run",
                "row_status": "fail",
                "reasoning_trace_ref": str(reasoning_trace),
                "verifier_exit_code": 1,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = mod.collect_decision_trace_bundle([root])
    trace = result["rows"][0]
    assert trace["reasoning_trace_ref"] == str(reasoning_trace)
    assert any(
        item.get("receipt_name") == "reasoning_trace.json"
        for item in trace["receipt_bundle"]
        if isinstance(item, dict)
    )
    assert trace["receipt_bundle"][0]["step_count"] == 1
