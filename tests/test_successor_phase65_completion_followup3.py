from __future__ import annotations

import json

from runner import successor_phase65_completion_followup3 as mod

REAL_RUN = mod._run


def _fake_docker(cmd, *, cwd, timeout):
    if cmd == ["docker", "info"]:
        return {"cmd": "docker info", "returncode": 1, "stdout": "", "stderr": "daemon down", "timed_out": False}
    return REAL_RUN(cmd, cwd=cwd, timeout=timeout)


def test_followup3_no_execute_writes_required_artifacts(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "_run", _fake_docker)
    monkeypatch.setattr(mod, "_record_ledger", lambda raw: None)
    monkeypatch.setattr(mod, "make_azure_gpt53_codex_route_from_env", lambda: {"model_client_id": "stub"})

    result = mod.launch_phase65_completion_followup3(output_dir=tmp_path, execute=False)

    assert result["blocked"] is True
    required = {
        "phase65_completion_followup3_plan.md",
        "phase65_completion_followup3_board_manifest.json",
        "phase65_completion_followup3_route_matrix.json",
        "phase65_completion_followup3_variant_doctrine_matrix.json",
        "phase65_completion_followup3_execution_plan.json",
        "phase65_completion_followup3_result_records.jsonl",
        "phase65_completion_followup3_score_envelope.json",
        "phase65_completion_followup3_report.json",
        "phase65_completion_followup3_trace_report.json",
        "phase65_completion_followup3_failure_source_report.json",
        "phase65_completion_followup3_cost_report.json",
        "phase65_completion_followup3_runtime_profile.json",
        "phase65_completion_followup3_deep_trace_analysis.md",
        "phase65_completion_followup3_handoff.md",
        "RAW_LEDGER_UPDATE",
    }
    assert required.issubset({path.name for path in tmp_path.iterdir()})


def test_followup3_manifest_covers_narrow_target_resolution_set(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "_run", _fake_docker)
    monkeypatch.setattr(mod, "_record_ledger", lambda raw: None)
    monkeypatch.setattr(mod, "make_azure_gpt53_codex_route_from_env", lambda: {"model_client_id": "stub"})

    mod.launch_phase65_completion_followup3(output_dir=tmp_path, execute=False)
    manifest = json.loads((tmp_path / "phase65_completion_followup3_board_manifest.json").read_text(encoding="utf-8"))
    execution = json.loads((tmp_path / "phase65_completion_followup3_execution_plan.json").read_text(encoding="utf-8"))

    assert manifest["comparison_set"] == [
        "candidate_plus_app_workspace_path_normalizer_01",
        "candidate_plus_path_normalized_verifier_repair_projection_01",
        "candidate_plus_path_normalized_target_resolution_guard_01",
    ]
    assert manifest["optional_comparison_set"] == []
    assert set(manifest["required_eval_ids"]) == {
        "tb_style_partial_progress_false_completion_v1",
        "tb_style_verifier_fail_then_repair_v1",
        "terminalbench_public_financial-document-processor",
        "terminalbench_public_fix-git",
    }
    assert manifest["optional_eval_ids"] == []
    assert execution["planned_model_backed_runs"] == 12


def test_followup3_run_one_passes_orientation_env_overrides(tmp_path, monkeypatch):
    captured: dict[str, object] = {}
    spec = mod._board_specs()[0]

    def _fake_seed(workspace, _spec):
        workspace.mkdir(parents=True, exist_ok=True)

    def _fake_run_reference_baseline(**kwargs):
        captured["orientation_env_overrides"] = kwargs.get("orientation_env_overrides")
        return {
            "execution": {"status": "completed"},
            "authoritative_closure_state": {
                "closure_contract_status": "pass",
                "required_deliverables": list(spec["closure_contract"]["required_deliverables"]),
                "required_artifact_paths": list(spec["closure_contract"]["required_artifact_paths"]),
                "actual_written_paths": list(spec["closure_contract"]["required_artifact_paths"]),
                "unresolved_blockers": [],
                "path_mismatches": [],
                "verifier_attempts": [],
                "latest_verifier_result": None,
                "verifier_repair_status": "not_required",
            },
            "score_envelope": {"model_usage": {"total_tokens": 0}},
        }

    monkeypatch.setattr(mod, "_seed_workspace", _fake_seed)
    monkeypatch.setattr(mod, "_workspace_fingerprints", lambda workspace: {})
    monkeypatch.setattr(mod, "run_reference_baseline", _fake_run_reference_baseline)
    monkeypatch.setattr(mod, "grade_phase65_spec", lambda spec, result, workspace: {"verdict": "pass", "reason_codes": []})
    monkeypatch.setattr(mod, "make_azure_gpt53_codex_route_from_env", lambda: {"model_client_id": "stub"})
    monkeypatch.setattr(mod, "build_packet04_route_manifest", lambda variant, scope: {"route_manifest_fingerprint": "fake", "routed_modules": []})

    record = mod._run_one(tmp_path, spec, mod.TARGET_RESOLUTION_GUARD)

    assert captured["orientation_env_overrides"] == {
        "required_artifact_paths": ["/app/final/report.json"],
        "required_deliverables": ["/app/final/report.json"],
        "requires_verifier": False,
    }
    assert record["task_truth_status"] == "pass"


def test_followup3_score_requires_target_resolution_alignment_for_top_recommendation():
    variants = [
        mod.PATH_NORMALIZER,
        mod.REPAIRED,
        mod.TARGET_RESOLUTION_GUARD,
    ]
    eval_ids = [
        "tb_style_partial_progress_false_completion_v1",
        "tb_style_verifier_fail_then_repair_v1",
        "terminalbench_public_financial-document-processor",
        "terminalbench_public_fix-git",
    ]
    records = []
    for eval_id in eval_ids:
        for variant in variants:
            status = "fail"
            if variant == mod.PATH_NORMALIZER and eval_id in {
                "tb_style_partial_progress_false_completion_v1",
                "tb_style_verifier_fail_then_repair_v1",
                "terminalbench_public_financial-document-processor",
            }:
                status = "pass"
            if variant == mod.REPAIRED and eval_id in {
                "tb_style_partial_progress_false_completion_v1",
                "tb_style_verifier_fail_then_repair_v1",
                "terminalbench_public_financial-document-processor",
            }:
                status = "pass"
            if variant == mod.TARGET_RESOLUTION_GUARD:
                status = "pass"
            records.append(
                {
                    "variant_id": variant,
                    "style": mod._style(variant),
                    "eval_id": eval_id,
                    "optional_eval": False,
                    "closure_contract_status": "pass",
                    "task_truth_status": status,
                }
            )

    score = mod._score(records)

    assert score["split_ready"] is True
    assert score["target_resolution_alignment_improved"] is True
    assert score["selected_recommendation"] == "completion_followup3_target_resolution_ready_for_mixed_confirmation"
