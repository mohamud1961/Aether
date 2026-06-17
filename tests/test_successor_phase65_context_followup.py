from __future__ import annotations

import json
from pathlib import Path

import pytest

EXPECTED_COMPARISON_SET = {
    "spb_01",
    "spb_tooling_seed_plus_receipt_and_completion_01",
    "candidate_plus_hybrid_receipt_handoff_01",
    "verified_work_pocket_handoff_hybrid_01",
    "candidate_plus_context_answer_extraction_01",
    "candidate_plus_context_followup_merged_01",
}
EXPECTED_CONTEXT_BOARD_COUNT = 11  # 4 ContextBench + 6 Letta + 1 work-pocket.


def _module():
    return pytest.importorskip("runner.successor_phase65_context_followup")


def _fake_docker_ok(real_run, cmd, *, cwd, timeout):
    if cmd == ["docker", "info"]:
        return {"cmd": "docker info", "returncode": 0, "stdout": "Client:\nServer:\n", "stderr": "", "timed_out": False}
    return real_run(cmd, cwd=cwd, timeout=timeout)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _comparison_set(manifest: dict, report: dict) -> set[str]:
    return set(manifest.get("comparison_set") or report.get("comparison_set") or [])


def _accepted_context_board_count(manifest: dict, report: dict) -> int | None:
    accepted_tracks = manifest.get("accepted_tracks")
    if isinstance(accepted_tracks, dict) and isinstance(accepted_tracks.get("context"), int):
        return accepted_tracks["context"]
    for key in ("accepted_context_board_count", "accepted_board_count", "context_board_count"):
        value = manifest.get(key, report.get(key))
        if isinstance(value, int):
            return value
    required_eval_ids = manifest.get("required_eval_ids")
    if isinstance(required_eval_ids, list):
        return len(required_eval_ids)
    return None


def _board_count_justification(manifest: dict, report: dict) -> str:
    for key in (
        "accepted_board_count_justification",
        "accepted_context_board_justification",
        "board_count_justification",
        "count_justification",
    ):
        value = manifest.get(key, report.get(key))
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _route_doctrine_statuses(output_dir: Path) -> tuple[str | None, str | None]:
    route_path = output_dir / "phase65_context_followup_route_matrix.json"
    doctrine_path = output_dir / "phase65_context_followup_variant_doctrine_matrix.json"
    if route_path.exists() and doctrine_path.exists():
        return _load_json(route_path).get("status"), _load_json(doctrine_path).get("status")
    score = _load_json(output_dir / "phase65_context_followup_score_envelope.json")
    route = score.get("route", {})
    doctrine = score.get("doctrine", {})
    return route.get("status"), doctrine.get("status")


def test_context_followup_no_execute_writes_required_artifacts(tmp_path, monkeypatch):
    mod = _module()
    real_run = mod._run
    monkeypatch.setattr(mod, "_run", lambda cmd, *, cwd, timeout: _fake_docker_ok(real_run, cmd, cwd=cwd, timeout=timeout))
    monkeypatch.setattr(mod, "_record_ledger", lambda raw: None)
    monkeypatch.setattr(mod, "make_azure_gpt53_codex_route_from_env", lambda: {"model_client_id": "stub"})

    result = mod.launch_phase65_context_followup(output_dir=tmp_path, execute=False)

    assert result["blocked"] is True
    required = {
        "phase65_context_followup_score_envelope.json",
        "phase65_context_followup_report.json",
        "phase65_context_followup_trace_report.json",
        "phase65_context_followup_failure_source_report.json",
        "phase65_context_followup_deep_trace_analysis.md",
        "phase65_context_followup_handoff.md",
        "RAW_LEDGER_UPDATE",
    }
    assert required.issubset({path.name for path in tmp_path.iterdir()})


def test_context_followup_narrow_board_invariants_and_status_pass(tmp_path, monkeypatch):
    mod = _module()
    real_run = mod._run
    monkeypatch.setattr(mod, "_run", lambda cmd, *, cwd, timeout: _fake_docker_ok(real_run, cmd, cwd=cwd, timeout=timeout))
    monkeypatch.setattr(mod, "_record_ledger", lambda raw: None)
    monkeypatch.setattr(mod, "make_azure_gpt53_codex_route_from_env", lambda: {"model_client_id": "stub"})

    mod.launch_phase65_context_followup(output_dir=tmp_path, execute=False)

    report = _load_json(tmp_path / "phase65_context_followup_report.json")
    manifest_path = tmp_path / "phase65_context_followup_board_manifest.json"
    manifest = _load_json(manifest_path) if manifest_path.exists() else {}

    assert EXPECTED_COMPARISON_SET <= _comparison_set(manifest, report)
    assert manifest.get("preserved_reference_branch") == "verified_work_pocket_handoff_hybrid_01"
    assert report.get("preserved_reference_branch") == "verified_work_pocket_handoff_hybrid_01"

    accepted_count = _accepted_context_board_count(manifest, report)
    assert accepted_count is not None
    if accepted_count != EXPECTED_CONTEXT_BOARD_COUNT:
        assert _board_count_justification(manifest, report)

    route_status, doctrine_status = _route_doctrine_statuses(tmp_path)
    assert route_status == "pass"
    assert doctrine_status == "pass"


def test_context_followup_local_merged_route_uses_owned_context_file():
    mod = _module()
    manifest = mod._build_route_manifest("candidate_plus_context_followup_merged_01")

    assert manifest["variant_id"] == "candidate_plus_context_followup_merged_01"
    context_rows = [row for row in manifest["routed_modules"] if row["runtime_key"] == "context"]
    assert len(context_rows) == 1
    context_row = context_rows[0]
    assert context_row["module_import_path"] == "blocks.context.phase65_context_followup_merged:manage"
    assert context_row["real_file_path"].endswith("blocks/context/phase65_context_followup_merged.py")


def test_structured_observation_register_projects_source_backed_record():
    mod = pytest.importorskip("blocks.context.structured_observation_register")
    history = [
        {
            "role": "assistant",
            "content": "Working on a structured extraction task.",
            "tool_calls": [
                {
                    "name": "raw_bash",
                    "arguments": json.dumps(
                        {
                            "command": "python3 - <<'PY'\n# inspect contextbench/Verified.csv\ntarget='SWE-Bench-Verified__python__maintenance__bugfix__27320d49'\nPY"
                        }
                    ),
                }
            ],
        }
    ]
    tool_observation = {
        "role": "tool",
        "name": "raw_bash",
        "content": (
            "raw_bash exit=0\nstdout:\n"
            "{'instance_id': 'SWE-Bench-Verified__python__maintenance__bugfix__27320d49', "
            "'original_inst_id': 'scikit-learn__scikit-learn-25232', 'language': 'python'}\n"
            "stderr:\n"
        ),
    }

    updated = mod.apply_structured_observation_register(history, tool_observation)

    register = updated.get("structured_observation_register")
    assert isinstance(register, dict)
    created = register.get("created_observations")
    assert isinstance(created, list) and len(created) == 1
    created_obs = created[0]
    assert created_obs["type"] in {"json_record", "python_record", "csv_row", "kv_record"}
    assert created_obs["matched_token"] == "SWE-Bench-Verified__python__maintenance__bugfix__27320d49"
    assert created_obs["record"]["original_inst_id"] == "scikit-learn__scikit-learn-25232"
    assert "[structured_observation_register]" in updated["content"]
    assert "[structured_observation_register_projection]" in updated["content"]
    assert "observation_created=1" in updated["content"]
    assert "observation_projected=1" in updated["content"]
    assert "provenance=source=" in updated["content"]
    assert "Verified.csv" in updated["content"]
    assert '"original_inst_id":"scikit-learn__scikit-learn-25232"' in updated["content"]


def test_structured_observation_register_projection_stays_compact():
    mod = pytest.importorskip("blocks.context.structured_observation_register")
    history = [{"role": "assistant", "tool_calls": [{"name": "raw_bash", "arguments": json.dumps({"command": "cat /tmp/metrics.json"})}]}]
    tool_observation = {"role": "tool", "content": 'stdout:\n{"run_id":"abc","status":"ok","duration_sec":3}\nstderr:\n'}

    updated = mod.apply_structured_observation_register(history, tool_observation)

    projection_lines = [line for line in updated["content"].splitlines() if line.startswith("obs[") or line == "[structured_observation_register_projection]"]
    assert projection_lines[0] == "[structured_observation_register_projection]"
    assert len(projection_lines) == 3
    assert len(updated["content"]) < 560
    assert '"duration_sec":3' in updated["content"]


@pytest.mark.parametrize(
    ("command", "stdout_blob", "record_fragment"),
    [
        ("cat /tmp/out.csv", "name,score\nalex,10\n", '"name":"alex"'),
        ("cat /tmp/system_status.yaml", "service: scheduler\nstatus: healthy\nattempt: 3\n", '"service":"scheduler"'),
        ("cat /tmp/events.log", "event=sync component=queue attempt=4 success=true\n", '"component":"queue"'),
    ],
)
def test_structured_observation_register_projects_generic_structured_formats(command, stdout_blob, record_fragment):
    mod = pytest.importorskip("blocks.context.structured_observation_register")
    history = [{"role": "assistant", "tool_calls": [{"name": "raw_bash", "arguments": json.dumps({"command": command})}]}]
    tool_observation = {"role": "tool", "content": f"stdout:\n{stdout_blob}stderr:\n"}

    updated = mod.apply_structured_observation_register(history, tool_observation)

    register = updated.get("structured_observation_register")
    assert isinstance(register, dict)
    created = register.get("created_observations")
    assert isinstance(created, list) and created
    assert "observation_projected=1" in updated["content"]
    assert "[structured_observation_register_projection]" in updated["content"]
    assert record_fragment in updated["content"]
