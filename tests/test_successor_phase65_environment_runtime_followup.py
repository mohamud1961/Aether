from __future__ import annotations

import json

from runner import successor_phase65_environment_runtime_followup as mod

REAL_RUN = mod._run


def _fake_docker(cmd, *, cwd, timeout):
    if cmd == ["docker", "info"]:
        return {"cmd": "docker info", "returncode": 1, "stdout": "", "stderr": "daemon down", "timed_out": False}
    return REAL_RUN(cmd, cwd=cwd, timeout=timeout)


def test_environment_runtime_followup_no_execute_writes_required_artifacts(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "_run", _fake_docker)
    monkeypatch.setattr(mod, "_record_ledger", lambda raw: None)
    monkeypatch.setattr(mod, "make_azure_gpt53_codex_route_from_env", lambda: {"model_client_id": "stub"})

    result = mod.launch_phase65_environment_runtime_followup(output_dir=tmp_path, execute=False)

    assert result["blocked"] is True
    required = {
        "phase65_environment_runtime_followup_board_manifest.json",
        "phase65_environment_runtime_followup_route_matrix.json",
        "phase65_environment_runtime_followup_variant_doctrine_matrix.json",
        "phase65_environment_runtime_followup_execution_plan.json",
        "phase65_environment_runtime_followup_result_records.jsonl",
        "phase65_environment_runtime_followup_score_envelope.json",
        "phase65_environment_runtime_followup_report.json",
        "phase65_environment_runtime_followup_trace_report.json",
        "phase65_environment_runtime_followup_failure_source_report.json",
        "phase65_environment_runtime_followup_deep_trace_analysis.md",
        "phase65_environment_runtime_followup_handoff.md",
        "RAW_LEDGER_UPDATE",
    }
    assert required.issubset({path.name for path in tmp_path.iterdir()})


def test_environment_runtime_followup_board_and_report_shape_in_blocked_mode(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "_run", _fake_docker)
    monkeypatch.setattr(mod, "_record_ledger", lambda raw: None)
    monkeypatch.setattr(mod, "make_azure_gpt53_codex_route_from_env", lambda: {"model_client_id": "stub"})

    mod.launch_phase65_environment_runtime_followup(output_dir=tmp_path, execute=False)

    manifest = json.loads((tmp_path / "phase65_environment_runtime_followup_board_manifest.json").read_text(encoding="utf-8"))
    report = json.loads((tmp_path / "phase65_environment_runtime_followup_report.json").read_text(encoding="utf-8"))
    execution = json.loads((tmp_path / "phase65_environment_runtime_followup_execution_plan.json").read_text(encoding="utf-8"))

    assert manifest["slice_type"] == "environment_runtime_only"
    assert manifest["comparison_set"] == [
        "spb_01",
        "candidate_plus_app_workspace_path_normalizer_01",
        "candidate_plus_path_normalized_verifier_repair_projection_01",
        "candidate_plus_path_normalized_target_resolution_guard_01",
        "candidate_plus_path_normalized_exact_target_projection_01",
    ]
    assert set(manifest["required_eval_ids"]) == {
        "tb_style_partial_progress_false_completion_v1",
        "tb_style_verifier_fail_then_repair_v1",
        "terminalbench_public_financial-document-processor",
        "terminalbench_public_fix-git",
    }
    assert report["blocked"] is True
    assert report["execute"] is False
    assert report["comparison_set"] == manifest["comparison_set"]
    assert execution["planned_probe_runs"] == 20


def test_environment_runtime_followup_failure_report_reducer_counts_sources():
    records = [
        {"task_truth_status": "fail", "failure_source": "route_invalid"},
        {"task_truth_status": "fail", "failure_source": "doctrine_runtime_key_gap"},
        {"task_truth_status": "pass", "failure_source": "none"},
        {"task_truth_status": "fail", "failure_source": "doctrine_runtime_key_gap"},
    ]
    failure = mod._failure_report(records)
    assert failure["failure_count"] == 3
    assert failure["failure_counts_by_source"] == {"route_invalid": 1, "doctrine_runtime_key_gap": 2}


def test_environment_runtime_followup_local_path_probes_cover_quoted_script_variant():
    probes = mod._local_path_probes()

    assert {probe["probe_id"] for probe in probes} == {
        "alias_command_root_resolution",
        "local_script_body_workspace_projection",
        "quoted_local_script_body_workspace_projection",
        "external_script_rewrite_guard",
    }
    assert all(probe["verdict"] == "pass" for probe in probes)


def test_environment_runtime_followup_blocked_report_uses_selected_eval_slice(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "_run", _fake_docker)
    monkeypatch.setattr(mod, "_record_ledger", lambda raw: None)
    monkeypatch.setattr(mod, "make_azure_gpt53_codex_route_from_env", lambda: {"model_client_id": "stub"})

    mod.launch_phase65_environment_runtime_followup(
        output_dir=tmp_path,
        execute=False,
        selected_eval_ids=("terminalbench_public_fix-git",),
    )

    manifest = json.loads((tmp_path / "phase65_environment_runtime_followup_board_manifest.json").read_text(encoding="utf-8"))
    report = json.loads((tmp_path / "phase65_environment_runtime_followup_report.json").read_text(encoding="utf-8"))

    assert manifest["required_eval_ids"] == ["terminalbench_public_fix-git"]
    assert report["runtime_required_eval_ids"] == ["terminalbench_public_fix-git"]
