from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.run_clean_tool_contract_certified import run_clean_tool_contract_certified
from runner.eval_substrate_contracts import validate_result_row, validate_task_pack


def test_clean_tool_contract_certified_rows_use_hidden_reviewer_mount(tmp_path, monkeypatch):
    commands: list[list[str]] = []

    def fake_run(cmd, capture_output, text, check=False):
        commands.append(cmd)
        if cmd[:3] == ["docker", "run", "--rm"] and cmd[4] == "/app":
            return subprocess.CompletedProcess(cmd, 0, stdout='{"passed": true}\n', stderr="")
        if cmd[:3] == ["docker", "run", "--rm"] and cmd[4] == "/reviewer_pack":
            case_id = cmd[-1].rsplit(" ", 1)[-1]
            if case_id == "ceiling":
                return subprocess.CompletedProcess(cmd, 0, stdout='{"case_id":"ceiling","passed":true,"reason_codes":[]}\n', stderr="")
            return subprocess.CompletedProcess(cmd, 9, stdout='{"case_id":"x","passed":false,"reason_codes":["semantic_mismatch"]}\n', stderr="")
        raise AssertionError(f"Unexpected command: {cmd}")

    monkeypatch.setattr("tools.run_clean_tool_contract_certified.subprocess.run", fake_run)
    summary = run_clean_tool_contract_certified(tmp_path)

    assert summary["row_count"] == 9
    task_packs = [json.loads(Path(path).read_text(encoding="utf-8")) for path in summary["task_pack_paths"]]
    assert len(task_packs) == 3
    assert all(validate_task_pack(task_pack) for task_pack in task_packs)

    rows = [json.loads(path.read_text(encoding="utf-8")) for path in sorted((tmp_path / "result_rows").glob("*.json"))]
    assert len(rows) == 9
    assert all(validate_result_row(row) for row in rows)
    assert all(row["admission_level"] == "certified" for row in rows)
    assert all(row["benchmark_label"] == "BFCL-style private homolog" for row in rows)
    assert {row["run_id"].rsplit("-", 1)[1] for row in rows} == {"baseline", "known_bad", "ceiling"}

    hidden_runs = [cmd for cmd in commands if cmd[:3] == ["docker", "run", "--rm"] and cmd[4] == "/reviewer_pack"]
    assert hidden_runs
    assert all("/reviewer_pack" in " ".join(cmd) for cmd in hidden_runs)
    assert all(sum(1 for item in cmd if item == "-v") == 2 for cmd in hidden_runs)

    for row in rows:
        bundle = json.loads((tmp_path / row["artifact_refs"][0]).read_text(encoding="utf-8"))
        assert bundle["hidden_truth_in_solver_pack"] is False
        assert "reviewer_pack" not in bundle["solver_workspace_ref"]
        assert (tmp_path / row["environment_ref"]).exists()
