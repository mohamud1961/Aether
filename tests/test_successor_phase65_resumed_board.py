from __future__ import annotations

import json

from runner import successor_phase65_resumed_board as mod

REAL_RUN = mod._run


def _fake_docker_ok(cmd, *, cwd, timeout):
    if cmd == ["docker", "info"]:
        return {"cmd": "docker info", "returncode": 0, "stdout": "Client:\nServer:\n", "stderr": "", "timed_out": False}
    return REAL_RUN(cmd, cwd=cwd, timeout=timeout)


def test_resumed_board_no_execute_writes_required_artifacts(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "_run", _fake_docker_ok)
    monkeypatch.setattr(mod, "_record_ledger", lambda raw: None)
    monkeypatch.setattr(mod, "make_azure_gpt53_codex_route_from_env", lambda: {"model_client_id": "stub"})

    result = mod.launch_phase65_resumed_board(output_dir=tmp_path, execute=False)

    assert result["blocked"] is True
    required = {
        "phase65_resumed_plan.md",
        "phase65_resumed_board_manifest.json",
        "phase65_resumed_route_matrix.json",
        "phase65_resumed_variant_doctrine_matrix.json",
        "phase65_resumed_execution_plan.json",
        "phase65_resumed_result_records.jsonl",
        "phase65_resumed_score_envelope.json",
        "phase65_resumed_bfcl_report.json",
        "phase65_resumed_completion_report.json",
        "phase65_resumed_context_report.json",
        "phase65_resumed_terminalbench_report.json",
        "phase65_resumed_trace_report.json",
        "phase65_resumed_failure_source_report.json",
        "phase65_resumed_cost_report.json",
        "phase65_resumed_handoff.md",
        "RAW_LEDGER_UPDATE",
    }
    assert required.issubset({path.name for path in tmp_path.iterdir()})


def test_resumed_board_manifest_and_route_contract(monkeypatch, tmp_path):
    monkeypatch.setattr(mod, "_run", _fake_docker_ok)
    monkeypatch.setattr(mod, "_record_ledger", lambda raw: None)
    monkeypatch.setattr(mod, "make_azure_gpt53_codex_route_from_env", lambda: {"model_client_id": "stub"})

    mod.launch_phase65_resumed_board(output_dir=tmp_path, execute=False)

    manifest = json.loads((tmp_path / "phase65_resumed_board_manifest.json").read_text(encoding="utf-8"))
    route = json.loads((tmp_path / "phase65_resumed_route_matrix.json").read_text(encoding="utf-8"))
    doctrine = json.loads((tmp_path / "phase65_resumed_variant_doctrine_matrix.json").read_text(encoding="utf-8"))
    execution = json.loads((tmp_path / "phase65_resumed_execution_plan.json").read_text(encoding="utf-8"))

    assert manifest["accepted_tracks"] == {"bfcl": 5, "completion": 3, "context": 11, "terminalbench": 3}
    assert execution["planned_model_backed_runs"] == 91
    assert route["status"] == "pass"
    assert doctrine["status"] == "pass"
    admitted = {row["variant_id"] for row in route["routes"]}
    assert {
        "candidate_plus_bfcl_strict_argument_guard_01",
        "checkpoint_verify_01",
        "artifact_and_verifier_hard_gate_01",
        "verified_work_pocket_handoff_hybrid_01",
    } <= admitted


def test_resumed_board_bfcl_only_disables_terminalbench_regression(monkeypatch, tmp_path):
    monkeypatch.setattr(mod, "_run", _fake_docker_ok)
    monkeypatch.setattr(mod, "_record_ledger", lambda raw: None)
    monkeypatch.setattr(mod, "make_azure_gpt53_codex_route_from_env", lambda: {"model_client_id": "stub"})

    mod.launch_phase65_resumed_board(output_dir=tmp_path, execute=False, selected_tracks=("bfcl",))

    manifest = json.loads((tmp_path / "phase65_resumed_board_manifest.json").read_text(encoding="utf-8"))
    execution = json.loads((tmp_path / "phase65_resumed_execution_plan.json").read_text(encoding="utf-8"))
    score_envelope = json.loads((tmp_path / "phase65_resumed_score_envelope.json").read_text(encoding="utf-8"))

    assert manifest["accepted_tracks"] == {"bfcl": 5, "completion": 0, "context": 0, "terminalbench": 0}
    assert execution["terminalbench_regression_enabled"] is False
    assert execution["planned_model_backed_runs"] == 15
    assert score_envelope["score"]["preflight"]["planned_model_backed_runs"] == 15
