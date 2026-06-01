from __future__ import annotations

import json

from runner import successor_phase6_corrective_rerun as mod


def _fake_docker_ok(cmd, *, cwd, timeout):
    if cmd == ["docker", "info"]:
        return {"cmd": "docker info", "returncode": 0, "stdout": "Client:\nServer:\n", "stderr": "", "timed_out": False}
    return mod._run(cmd, cwd=cwd, timeout=timeout)


def test_corrective_no_execute_writes_required_artifacts(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "_run", _fake_docker_ok)

    result = mod.launch_corrective_phase6(output_dir=tmp_path, execute=False)

    assert result["blocked"] is True
    assert result["selected_recommendation"] == "benchmark_adapter_still_invalid"
    required = {
        "phase6_corrective_plan.md",
        "phase6_corrective_scope_gap_report.md",
        "phase6_corrective_board_manifest.json",
        "phase6_corrective_route_matrix.json",
        "phase6_corrective_variant_mechanism_matrix.json",
        "phase6_corrective_eval_design_report.md",
        "phase6_corrective_execution_plan.json",
        "phase6_corrective_result_records.jsonl",
        "phase6_corrective_score_envelope.json",
        "phase6_corrective_context_report.json",
        "phase6_corrective_completion_report.json",
        "phase6_corrective_bfcl_report.json",
        "phase6_corrective_terminalbench_report.json",
        "phase6_corrective_trace_report.json",
        "phase6_corrective_failure_source_report.json",
        "phase6_corrective_cost_report.json",
        "phase6_corrective_handoff.md",
        "RAW_LEDGER_UPDATE",
    }
    assert required.issubset({path.name for path in tmp_path.iterdir()})


def test_corrective_board_manifest_matches_accepted_lane_shape(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "_run", _fake_docker_ok)

    mod.launch_corrective_phase6(output_dir=tmp_path, execute=False)
    manifest = json.loads((tmp_path / "phase6_corrective_board_manifest.json").read_text(encoding="utf-8"))
    execution = json.loads((tmp_path / "phase6_corrective_execution_plan.json").read_text(encoding="utf-8"))
    eval_ids = set(manifest["eval_ids"])

    assert len([eid for eid in eval_ids if eid.startswith("contextbench_verified_")]) == 8
    letta_ids = [eid for eid in eval_ids if eid.startswith("letta_filesystem_")]
    assert len(letta_ids) == 6
    assert sum("_easy" in eid for eid in letta_ids) == 2
    assert sum("_medium" in eid for eid in letta_ids) == 2
    assert sum("_hard" in eid for eid in letta_ids) == 2
    bfcl_ids = [eid for eid in eval_ids if eid.startswith("bfcl_v3_strict_")]
    assert 5 <= len(bfcl_ids) <= 10
    assert "bfcl_v3_strict_multi_turn_composite_97" in eval_ids
    assert {"terminalbench_public_fix-git", "terminalbench_public_regex-log", "terminalbench_public_financial-document-processor"} <= eval_ids
    assert "terminalbench_extract_moves_repaired_closure" in eval_ids
    assert len([eid for eid in eval_ids if eid.startswith("internal_")]) == 4
    assert 150 <= execution["planned_model_backed_runs"] <= 250


def test_corrective_contextbench_prompt_requires_json_shape():
    specs = mod._contextbench_specs()
    assert specs
    assert all("json object" in spec["task_prompt"].lower() for spec in specs)


def test_corrective_mechanism_matrix_fails_closed_on_doctrine_only(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "_run", _fake_docker_ok)

    real_build = mod.build_packet04_route_manifest

    def fake_build(variant_id: str, *, scope: str):
        manifest = real_build(variant_id, scope=scope)
        if variant_id in mod.COMPLETION_VARIANTS:
            for row in manifest["routed_modules"]:
                if row["runtime_key"] == "verification":
                    row["claimed_changed_surface"] = False
        return manifest

    monkeypatch.setattr(mod, "build_packet04_route_manifest", fake_build)

    mod.launch_corrective_phase6(output_dir=tmp_path, execute=True)

    matrix = json.loads((tmp_path / "phase6_corrective_variant_mechanism_matrix.json").read_text(encoding="utf-8"))
    assert matrix["status"] == "blocked"
    assert any(row["classification"] in {"doctrine-only", "mixed"} for row in matrix["rows"])
    score = json.loads((tmp_path / "phase6_corrective_score_envelope.json").read_text(encoding="utf-8"))
    assert score["score"]["selected_recommendation"] == "benchmark_adapter_still_invalid"


def test_corrective_mechanism_matrix_passes_for_mechanism_bearing_routes(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "_run", _fake_docker_ok)

    mod.launch_corrective_phase6(output_dir=tmp_path, execute=False)

    matrix = json.loads((tmp_path / "phase6_corrective_variant_mechanism_matrix.json").read_text(encoding="utf-8"))
    assert matrix["status"] == "pass"
    candidate_rows = [row for row in matrix["rows"] if row["variant_id"].startswith("candidate_plus_")]
    assert candidate_rows
    assert all(row["classification"] == "mechanism-bearing" for row in candidate_rows)
