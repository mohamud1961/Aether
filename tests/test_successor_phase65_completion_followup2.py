from __future__ import annotations

import json

from runner import successor_phase65_completion_followup2 as mod

REAL_RUN = mod._run


def _fake_docker(cmd, *, cwd, timeout):
    if cmd == ["docker", "info"]:
        return {"cmd": "docker info", "returncode": 1, "stdout": "", "stderr": "daemon down", "timed_out": False}
    return REAL_RUN(cmd, cwd=cwd, timeout=timeout)


def test_followup2_no_execute_writes_required_artifacts(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "_run", _fake_docker)
    monkeypatch.setattr(mod, "_record_ledger", lambda raw: None)
    monkeypatch.setattr(mod, "make_azure_gpt53_codex_route_from_env", lambda: {"model_client_id": "stub"})

    result = mod.launch_phase65_completion_followup2(output_dir=tmp_path, execute=False)

    assert result["blocked"] is True
    required = {
        "phase65_completion_followup2_plan.md",
        "phase65_completion_followup2_board_manifest.json",
        "phase65_completion_followup2_route_matrix.json",
        "phase65_completion_followup2_variant_doctrine_matrix.json",
        "phase65_completion_followup2_execution_plan.json",
        "phase65_completion_followup2_result_records.jsonl",
        "phase65_completion_followup2_score_envelope.json",
        "phase65_completion_followup2_report.json",
        "phase65_completion_followup2_trace_report.json",
        "phase65_completion_followup2_failure_source_report.json",
        "phase65_completion_followup2_cost_report.json",
        "phase65_completion_followup2_runtime_profile.json",
        "phase65_completion_followup2_handoff.md",
        "RAW_LEDGER_UPDATE",
    }
    assert required.issubset({path.name for path in tmp_path.iterdir()})


def test_followup2_manifest_covers_locked_comparison_set(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "_run", _fake_docker)
    monkeypatch.setattr(mod, "_record_ledger", lambda raw: None)
    monkeypatch.setattr(mod, "make_azure_gpt53_codex_route_from_env", lambda: {"model_client_id": "stub"})

    mod.launch_phase65_completion_followup2(output_dir=tmp_path, execute=False)
    manifest = json.loads((tmp_path / "phase65_completion_followup2_board_manifest.json").read_text(encoding="utf-8"))
    route = json.loads((tmp_path / "phase65_completion_followup2_route_matrix.json").read_text(encoding="utf-8"))
    doctrine = json.loads((tmp_path / "phase65_completion_followup2_variant_doctrine_matrix.json").read_text(encoding="utf-8"))
    execution = json.loads((tmp_path / "phase65_completion_followup2_execution_plan.json").read_text(encoding="utf-8"))

    assert set(manifest["comparison_set"]) == {
        "spb_01",
        "spb_tooling_seed_plus_receipt_and_completion_01",
        "candidate_plus_app_workspace_path_normalizer_01",
        "artifact_and_verifier_hard_gate_01",
        "checkpoint_verify_01",
        "candidate_plus_path_normalized_verifier_repair_projection_01",
    }
    assert manifest["optional_comparison_set"] == ["candidate_plus_closure_evidence_projection_01"]
    assert {"tb_style_partial_progress_false_completion_v1", "tb_style_verifier_fail_then_repair_v1", "extract_moves_from_video_repaired_closure", "terminalbench_public_financial-document-processor"} <= set(manifest["required_eval_ids"])
    assert "terminalbench_public_fix-git" in manifest["optional_eval_ids"]
    assert route["status"] == "pass"
    assert doctrine["status"] == "pass"
    assert execution["planned_model_backed_runs"] == 35


def test_followup2_score_requires_split_and_material_uplift():
    records = [
        {
            "variant_id": "spb_tooling_seed_plus_receipt_and_completion_01",
            "style": "model_led_ish",
            "eval_id": "tb_style_verifier_fail_then_repair_v1",
            "optional_eval": False,
            "closure_contract_status": "partial",
            "task_truth_status": "fail",
        },
        {
            "variant_id": "candidate_plus_app_workspace_path_normalizer_01",
            "style": "hybrid",
            "eval_id": "tb_style_verifier_fail_then_repair_v1",
            "optional_eval": False,
            "closure_contract_status": "partial",
            "task_truth_status": "fail",
        },
        {
            "variant_id": "candidate_plus_path_normalized_verifier_repair_projection_01",
            "style": "hybrid",
            "eval_id": "tb_style_verifier_fail_then_repair_v1",
            "optional_eval": False,
            "closure_contract_status": "pass",
            "task_truth_status": "pass",
        },
    ]

    score = mod._score(records)

    assert score["split_ready"] is True
    assert score["verifier_repair_improved"] is True
    assert score["selected_recommendation"] == "completion_followup2_sufficient_for_mixed_confirmation"
