from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.run_model_backed_baseline_certified_core import run_model_backed_baseline_certified_core


def test_model_backed_baseline_core_writes_hidden_verifier_artifact_with_hidden_record(tmp_path, monkeypatch):
    solver_root = tmp_path / "solver_seed"
    reviewer_root = tmp_path / "reviewer_seed"
    solver_root.mkdir()
    reviewer_root.mkdir()
    (solver_root / "answer.json").write_text("{}", encoding="utf-8")
    (solver_root / "verifier.py").write_text("print('ok')\n", encoding="utf-8")
    (reviewer_root / "hidden_verifier.py").write_text("print('ok')\n", encoding="utf-8")

    def fake_route(*args, **kwargs):
        run_dir = Path(kwargs["run_dir"])
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "run_events.jsonl").write_text("{}\n", encoding="utf-8")
        (run_dir / "route_manifest.json").write_text("{}", encoding="utf-8")
        return {"verified": True, "runtime_timing": {"model_call_count": 1, "tool_call_count": 1}}

    monkeypatch.setattr(
        "tools.run_model_backed_baseline_certified_core.draft._stage_solver_and_reviewer_packs",
        lambda **kwargs: {"solver_root": solver_root, "reviewer_root": reviewer_root},
    )
    monkeypatch.setattr(
        "tools.run_model_backed_baseline_certified_core.draft.FAMILIES",
        [
            {
                "task_id": "fec_tb_verifier_repair_001",
                "family": "tb_verifier_repair",
                "surface_type": "verifier_repair",
                "prompt": "repair the file",
                "failure_class": "verification",
                "baseline": {},
                "expected": {},
            }
        ],
    )
    monkeypatch.setattr("tools.run_model_backed_baseline_certified_core._backend_evidence", lambda **kwargs: {"backend_ref": "fake"})
    monkeypatch.setattr("tools.run_model_backed_baseline_certified_core.make_azure_gpt54_mini_route_from_env", lambda **_: {"provider": "fake"})
    monkeypatch.setattr("tools.run_model_backed_baseline_certified_core.run_reference_baseline", fake_route)

    def fake_docker_exec(workspace, image, command, *, cwd):
        payload = {"command": command, "cwd": cwd, "stdout": '{"passed": true}\n', "stderr": "", "exit_code": 0, "timeout": False}
        if "hidden_verifier.py" in command:
            payload["stdout"] = '{"case_id":"model_backed","passed":true}\n'
        return payload

    monkeypatch.setattr("tools.run_model_backed_baseline_certified_core._docker_exec", fake_docker_exec)

    summary = run_model_backed_baseline_certified_core(tmp_path, route_specs=(("spb_01", "packet06_phase2_env_tooling"),))

    assert summary["row_count"] == 1
    hidden_artifact = json.loads(
        (
            tmp_path
            / "runs"
            / "fec_tb_verifier_repair_001__spb_01__gpt54_mini"
            / "artifacts"
            / "hidden_verifier_output.json"
        ).read_text(encoding="utf-8")
    )
    assert "hidden_record" in hidden_artifact
    assert "visible_record" not in hidden_artifact
