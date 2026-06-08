from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.run_clean_tool_contract_model_backed import run_clean_tool_contract_model_backed
from runner.eval_substrate_contracts import validate_result_row


def test_clean_tool_contract_model_backed_rows_keep_hidden_truth_out_of_solver(tmp_path, monkeypatch):
    commands: list[list[str]] = []

    def fake_route(*args, **kwargs):
        run_dir = Path(kwargs["run_dir"])
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "run_events.jsonl").write_text("{}\n", encoding="utf-8")
        (run_dir / "route_manifest.json").write_text("{}", encoding="utf-8")
        return {"verified": False, "runtime_timing": {"model_call_count": 2, "tool_call_count": 2}}

    def fake_visible(**kwargs):
        commands.append(["visible", kwargs["cwd"]])
        return {"command": kwargs["command"], "cwd": kwargs["cwd"], "stdout": '{"passed": true}\n', "stderr": "", "exit_code": 0, "timeout": False}

    def fake_hidden(**kwargs):
        commands.append(["hidden", kwargs["cwd"]])
        return {"command": kwargs["command"], "cwd": kwargs["cwd"], "stdout": '{"case_id":"model_backed","passed":false,"reason_codes":["tool_call_count_mismatch"]}\n', "stderr": "", "exit_code": 9, "timeout": False}

    monkeypatch.setattr("tools.run_clean_tool_contract_model_backed.run_reference_baseline", fake_route)
    monkeypatch.setattr("tools.run_clean_tool_contract_model_backed.make_azure_gpt54_mini_route_from_env", lambda **_: {"provider": "fake"})
    monkeypatch.setattr("tools.run_clean_tool_contract_model_backed._docker_exec_single_mount", fake_visible)
    monkeypatch.setattr("tools.run_clean_tool_contract_model_backed._docker_exec_dual_mount", fake_hidden)

    summary = run_clean_tool_contract_model_backed(tmp_path)

    assert summary["row_count"] == 6
    rows = [json.loads(path.read_text(encoding="utf-8")) for path in sorted((tmp_path / "result_rows").glob("*.json"))]
    assert len(rows) == 6
    assert all(validate_result_row(row) for row in rows)
    assert {row["route_id"] for row in rows} == {"sc_b_01", "candidate_plus_path_normalized_verifier_repair_projection_01"}
    assert all(row["failure_class"] == "tool_contract" for row in rows)
    assert all(row["reason_codes"] == ["tool_call_count_mismatch"] for row in rows)
    hidden_artifact = json.loads(
        (
            tmp_path
            / "runs"
            / "ctc_semantics_001_multi_required_order__sc_b_01__gpt54_mini"
            / "artifacts"
            / "hidden_verifier_output.json"
        ).read_text(encoding="utf-8")
    )
    assert "hidden_record" in hidden_artifact
    assert "visible_record" not in hidden_artifact

    hidden_runs = [cmd for cmd in commands if cmd[0] == "hidden"]
    assert hidden_runs
    assert all(cmd[1] == "/reviewer_pack" for cmd in hidden_runs)


def test_clean_tool_contract_model_backed_can_filter_routes_and_tasks(tmp_path, monkeypatch):
    def fake_route(*args, **kwargs):
        run_dir = Path(kwargs["run_dir"])
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "run_events.jsonl").write_text("{}\n", encoding="utf-8")
        (run_dir / "route_manifest.json").write_text("{}", encoding="utf-8")
        return {"verified": False, "runtime_timing": {"model_call_count": 1, "tool_call_count": 1}}

    monkeypatch.setattr("tools.run_clean_tool_contract_model_backed.run_reference_baseline", fake_route)
    monkeypatch.setattr("tools.run_clean_tool_contract_model_backed.make_azure_gpt54_mini_route_from_env", lambda **_: {"provider": "fake"})
    monkeypatch.setattr(
        "tools.run_clean_tool_contract_model_backed._docker_exec_single_mount",
        lambda **kwargs: {"command": kwargs["command"], "cwd": kwargs["cwd"], "stdout": '{"passed": true}\n', "stderr": "", "exit_code": 0, "timeout": False},
    )
    monkeypatch.setattr(
        "tools.run_clean_tool_contract_model_backed._docker_exec_dual_mount",
        lambda **kwargs: {"command": kwargs["command"], "cwd": kwargs["cwd"], "stdout": '{"passed": true}\n', "stderr": "", "exit_code": 0, "timeout": False},
    )

    summary = run_clean_tool_contract_model_backed(
        tmp_path,
        route_specs=(("sc_b_01", "packet06_phase6_context_completion_repair"),),
        task_ids=("ctc_semantics_001_multi_required_order",),
    )

    assert summary["row_count"] == 1
    assert summary["route_specs"] == [{"route_id": "sc_b_01", "route_scope": "packet06_phase6_context_completion_repair"}]
    assert summary["task_ids"] == ["ctc_semantics_001_multi_required_order"]
    rows = [json.loads(path.read_text(encoding="utf-8")) for path in sorted((tmp_path / "result_rows").glob("*.json"))]
    assert len(rows) == 1
    assert rows[0]["route_id"] == "sc_b_01"
    assert rows[0]["task_pack_id"] == "ctc_semantics_001_multi_required_order"
