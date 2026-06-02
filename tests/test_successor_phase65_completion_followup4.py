from __future__ import annotations

import json
from pathlib import Path

from runner import successor_phase65_completion_followup4 as mod

REAL_RUN = mod._run


def _fake_docker(cmd, *, cwd, timeout):
    if cmd == ["docker", "info"]:
        return {"cmd": "docker info", "returncode": 1, "stdout": "", "stderr": "daemon down", "timed_out": False}
    return REAL_RUN(cmd, cwd=cwd, timeout=timeout)


def test_followup4_no_execute_writes_required_artifacts(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "_run", _fake_docker)
    monkeypatch.setattr(mod, "_record_ledger", lambda raw: None)
    monkeypatch.setattr(mod, "make_azure_gpt53_codex_route_from_env", lambda: {"model_client_id": "stub"})
    result = mod.launch_phase65_completion_followup4(output_dir=tmp_path, execute=False)
    assert result["blocked"] is True
    required = {
        "phase65_completion_followup4_score_envelope.json",
        "phase65_completion_followup4_report.json",
        "phase65_completion_followup4_trace_report.json",
        "phase65_completion_followup4_failure_source_report.json",
        "phase65_completion_followup4_result_records.jsonl",
        "phase65_completion_followup4_deep_trace_analysis.md",
        "phase65_completion_followup4_handoff.md",
        "RAW_LEDGER_UPDATE",
    }
    assert required.issubset({path.name for path in tmp_path.iterdir()})


def test_followup4_manifest_includes_merged_route(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "_run", _fake_docker)
    monkeypatch.setattr(mod, "_record_ledger", lambda raw: None)
    monkeypatch.setattr(mod, "make_azure_gpt53_codex_route_from_env", lambda: {"model_client_id": "stub"})
    mod.launch_phase65_completion_followup4(output_dir=tmp_path, execute=False)
    report = json.loads((tmp_path / "phase65_completion_followup4_report.json").read_text(encoding="utf-8"))
    manifest = json.loads((tmp_path / "phase65_completion_followup4_board_manifest.json").read_text(encoding="utf-8"))
    assert "candidate_plus_path_normalized_exact_target_projection_01" in report["comparison_set"]
    assert set(manifest["required_eval_ids"]) == {
        "tb_style_partial_progress_false_completion_v1",
        "tb_style_verifier_fail_then_repair_v1",
        "terminalbench_public_financial-document-processor",
        "terminalbench_public_fix-git",
    }


def test_followup4_trace_report_labels_multi_verifier_episode():
    records = [
        {
            "run_id": "r1",
            "eval_id": "tb_style_verifier_fail_then_repair_v1",
            "variant_id": mod.MERGED_EXACT_TARGET,
            "closure_contract_status": "partial",
            "task_truth_status": "fail",
            "failure_source": "verifier_failure",
            "closure_state": {
                "required_deliverables": ["/app/output.txt"],
                "required_artifact_paths": ["/app/output.txt"],
                "actual_written_paths": ["/app/output.txt"],
                "verifier_attempts": [
                    {"step": 1, "result_index": 0, "status": "fail"},
                    {"step": 1, "result_index": 0, "status": "pass"},
                ],
                "latest_verifier_result": {"status": "pass"},
                "verifier_repair_status": "repaired_and_reran_to_pass",
                "unresolved_blockers": [],
            },
        }
    ]
    trace = mod._trace_report(records)
    row = trace["traces"][0]
    assert row["verifier_attempt_count"] == 2
    assert row["multi_verifier_shell_results"] == 1
    assert row["verifier_episode_label"] == "fail_repair_rerun_to_pass"


def test_followup4_detects_invalid_infrastructure_from_model_client_network_error(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    event = {
        "event_type": "model_client_error",
        "payload": {
            "details": {
                "error_kind": "network_error",
                "message": "azure openai request failed due to network error",
                "metadata": {
                    "api_base": "https://example.openai.azure.com/openai/v1/responses",
                    "reason": "[Errno 8] nodename nor servname provided, or not known",
                },
            }
        },
    }
    (run_dir / "run_events.jsonl").write_text(json.dumps(event) + "\n", encoding="utf-8")
    assert mod._is_invalid_infrastructure_failure(run_dir) is True


def test_followup4_failure_report_excludes_invalid_infrastructure_from_behavioral_failures():
    records = [
        {
            "run_id": "invalid",
            "task_truth_status": "fail",
            "invalid_infrastructure_failure": True,
            "failure_source": "invalid_infrastructure",
        },
        {
            "run_id": "behavioral",
            "task_truth_status": "fail",
            "invalid_infrastructure_failure": False,
            "failure_source": "closure_evidence_omission",
        },
        {
            "run_id": "pass",
            "task_truth_status": "pass",
            "invalid_infrastructure_failure": False,
            "failure_source": "none",
        },
    ]
    failure = mod._failure_report(records)
    assert failure["invalid_infrastructure_failure_count"] == 1
    assert failure["failure_count"] == 1
    assert failure["failure_counts_by_source"] == {"closure_evidence_omission": 1}
