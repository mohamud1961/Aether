from __future__ import annotations

import json

from blocks.verification.closure_truth_state import build_closure_state
from blocks.tools.app_path_normalizer import execute_tool_call
from runner import successor_phase65_completion_closure as mod

REAL_RUN = mod._run


def _fake_docker(cmd, *, cwd, timeout):
    if cmd == ["docker", "info"]:
        return {"cmd": "docker info", "returncode": 1, "stdout": "", "stderr": "daemon down", "timed_out": False}
    return REAL_RUN(cmd, cwd=cwd, timeout=timeout)


def test_completion_closure_no_execute_writes_required_artifacts(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "_run", _fake_docker)
    monkeypatch.setattr(mod, "_record_ledger", lambda raw: None)
    monkeypatch.setattr(mod, "make_azure_gpt53_codex_route_from_env", lambda: {"model_client_id": "stub"})

    result = mod.launch_phase65_completion_closure(output_dir=tmp_path, execute=False)

    assert result["blocked"] is True
    required = {
        "phase65_completion_closure_plan.md",
        "phase65_completion_closure_board_manifest.json",
        "phase65_completion_closure_route_matrix.json",
        "phase65_completion_closure_variant_doctrine_matrix.json",
        "phase65_completion_closure_execution_plan.json",
        "phase65_completion_closure_result_records.jsonl",
        "phase65_completion_closure_score_envelope.json",
        "phase65_completion_closure_report.json",
        "phase65_completion_closure_trace_report.json",
        "phase65_completion_closure_failure_source_report.json",
        "phase65_completion_closure_cost_report.json",
        "phase65_completion_closure_runtime_profile.json",
        "phase65_completion_closure_handoff.md",
        "RAW_LEDGER_UPDATE",
    }
    assert required.issubset({path.name for path in tmp_path.iterdir()})


def test_completion_closure_manifest_and_route_cover_required_comparison_set(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "_run", _fake_docker)
    monkeypatch.setattr(mod, "_record_ledger", lambda raw: None)
    monkeypatch.setattr(mod, "make_azure_gpt53_codex_route_from_env", lambda: {"model_client_id": "stub"})

    mod.launch_phase65_completion_closure(output_dir=tmp_path, execute=False)
    manifest = json.loads((tmp_path / "phase65_completion_closure_board_manifest.json").read_text(encoding="utf-8"))
    route = json.loads((tmp_path / "phase65_completion_closure_route_matrix.json").read_text(encoding="utf-8"))
    doctrine = json.loads((tmp_path / "phase65_completion_closure_variant_doctrine_matrix.json").read_text(encoding="utf-8"))
    execution = json.loads((tmp_path / "phase65_completion_closure_execution_plan.json").read_text(encoding="utf-8"))

    assert {
        "spb_01",
        "spb_tooling_seed_plus_receipt_and_completion_01",
        "artifact_and_verifier_hard_gate_01",
        "checkpoint_verify_01",
        "candidate_plus_closure_truth_ledger_01",
    } <= set(manifest["comparison_set"])
    assert {"tb_style_partial_progress_false_completion_v1", "tb_style_verifier_fail_then_repair_v1", "extract_moves_from_video_repaired_closure", "terminalbench_public_financial-document-processor"} <= set(manifest["required_eval_ids"])
    assert "terminalbench_public_fix-git" in manifest["optional_eval_ids"]
    assert route["status"] == "pass"
    assert doctrine["status"] == "pass"
    assert execution["planned_model_backed_runs"] == 35


def test_closure_truth_state_records_written_paths_and_verifier_attempts(tmp_path):
    (tmp_path / "output.txt").write_text("status=complete\n", encoding="utf-8")
    (tmp_path / "verify.sh").write_text("#!/bin/bash\necho PASS\n", encoding="utf-8")
    state = build_closure_state(
        "Run /app/verify.sh and repair /app/output.txt before closing.",
        {
            "cwd": str(tmp_path),
            "model_claimed_done": True,
            "closure_contract": {
                "required_deliverables": ["/app/output.txt"],
                "required_artifact_paths": ["/app/output.txt"],
                "requires_verifier": True,
                "initial_workspace_fingerprints": {"verify.sh": "seed", "output.txt": "seed"},
            },
            "execution_result": {
                "last_completion": {"text": "Updated /app/output.txt and reran verify.sh with PASS."},
                "steps": [
                    {
                        "step": 1,
                        "results": [
                            {
                                "command": "bash /Users/test/workspace/verify.sh",
                                "exit_code": 0,
                                "stdout": "PASS\n",
                                "stderr": "",
                            }
                        ],
                    }
                ],
            },
        },
    )

    assert state["status"] == "solved"
    assert "/app/output.txt" in state["actual_written_paths"]
    assert state["latest_verifier_result"]["status"] == "pass"


def test_app_path_normalizer_rewrites_app_paths_and_local_scripts(tmp_path):
    class _Sandbox:
        sandbox_type = "none"

        def __init__(self, cwd):
            self.cwd = cwd

        def exec(self, command):  # type: ignore[no-untyped-def]
            self.command = command
            return {"exit_code": 0, "stdout": command, "stderr": "", "timed_out": False}

    sandbox = _Sandbox(tmp_path)
    result = execute_tool_call(
        {"name": "raw_bash", "arguments": json.dumps({"command": "cd /app && ./verify.sh && cat /app/output.txt"})},
        sandbox,
    )

    assert result["result_class"] == "success"
    assert str(tmp_path) in result["command"]
    assert "bash ./verify.sh" in result["command"]
