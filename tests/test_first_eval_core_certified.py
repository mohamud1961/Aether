from __future__ import annotations

import json
import subprocess
from pathlib import Path

from runner.eval_substrate_contracts import validate_result_row, validate_task_pack
from tools.run_first_eval_core_certified import run_first_eval_core_certified


def test_first_eval_core_certified_rows_and_scoreboard(tmp_path, monkeypatch):
    def fake_run(cmd, capture_output, text, check=False):
        if cmd[:3] == ["docker", "run", "-d"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="containerid", stderr="")
        if cmd[:3] == ["docker", "rm", "-f"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        if cmd[:4] == ["docker", "exec", "-w", "/app"]:
            return subprocess.CompletedProcess(cmd, 0, stdout='{"passed": true}\n', stderr="")
        if cmd[:4] == ["docker", "exec", "-w", "/app/reviewer_pack"]:
            case_id = cmd[-1].rsplit(" ", 1)[-1]
            if case_id == "ceiling":
                return subprocess.CompletedProcess(cmd, 0, stdout='{"passed": true}\n', stderr="")
            return subprocess.CompletedProcess(cmd, 9, stdout='{"passed": false}\n', stderr="")
        raise AssertionError(f"Unexpected command: {cmd}")

    monkeypatch.setattr("tools.run_first_eval_core_certified.subprocess.run", fake_run)
    summary = run_first_eval_core_certified(tmp_path)

    assert summary["backend_ref"] == "azure_vm_docker"
    assert summary["row_count"] == 15

    for path in summary["task_pack_paths"]:
        task_pack = json.loads(Path(path).read_text(encoding="utf-8"))
        validate_task_pack(task_pack)
        assert task_pack["admission_level"] == "certified"

    rows = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((tmp_path / "result_rows").glob("*.json"))
    ]
    assert len(rows) == 15
    assert all(validate_result_row(row) for row in rows)
    assert all(row["backend_ref"] == "azure_vm_docker" for row in rows)
    assert all(row["certification_claim"] == "certified_linux_docker" for row in rows)
    assert all("debug_local_no_sandbox" not in row["backend_ref"] for row in rows)
    assert all(not Path(row["environment_ref"]).is_absolute() for row in rows)
    assert all(not Path(row["verifier_ref"]).is_absolute() for row in rows)
    assert all(not Path(row["grader_ref"]).is_absolute() for row in rows)
    assert all(not Path(row["hidden_verifier_ref"]).is_absolute() for row in rows)
    assert all(not Path(ref).is_absolute() for row in rows for ref in row["artifact_refs"])
    assert all(not Path(ref).is_absolute() for row in rows for ref in row["trace_refs"])

    by_case = {case_id: [] for case_id in ("baseline", "known_bad", "ceiling")}
    for row in rows:
        assert Path(row["environment_ref_original"]).is_absolute()
        assert Path(row["verifier_ref_original"]).is_absolute()
        assert Path(row["grader_ref_original"]).is_absolute()
        assert Path(row["hidden_verifier_ref_original"]).is_absolute()
        assert all(Path(ref).is_absolute() for ref in row["artifact_refs_original"])
        assert all(Path(ref).is_absolute() for ref in row["trace_refs_original"])
        assert (tmp_path / row["environment_ref"]).exists()
        assert (tmp_path / row["verifier_ref"]).exists()
        assert (tmp_path / row["grader_ref"]).exists()
        assert (tmp_path / row["hidden_verifier_ref"]).exists()
        assert all((tmp_path / ref).exists() for ref in row["artifact_refs"])
        assert all((tmp_path / ref).exists() for ref in row["trace_refs"])
        bundle = json.loads((tmp_path / row["artifact_refs"][0]).read_text(encoding="utf-8"))
        assert not Path(bundle["manifest_ref"]).is_absolute()
        assert not Path(bundle["verifier_output_ref"]).is_absolute()
        assert not Path(bundle["hidden_verifier_ref"]).is_absolute()
        assert not Path(bundle["grader_ref"]).is_absolute()
        assert all(not Path(ref).is_absolute() for ref in bundle["trace_refs"])
        assert Path(bundle["manifest_ref_original"]).is_absolute()
        assert Path(bundle["verifier_output_ref_original"]).is_absolute()
        assert Path(bundle["hidden_verifier_ref_original"]).is_absolute()
        assert Path(bundle["grader_ref_original"]).is_absolute()
        assert all(Path(ref).is_absolute() for ref in bundle["trace_refs_original"])
        assert (tmp_path / bundle["manifest_ref"]).exists()
        assert (tmp_path / bundle["verifier_output_ref"]).exists()
        assert (tmp_path / bundle["hidden_verifier_ref"]).exists()
        assert (tmp_path / bundle["grader_ref"]).exists()
        assert all((tmp_path / ref).exists() for ref in bundle["trace_refs"])
        assert not Path(bundle["cheap_replay"]["environment_manifest_ref"]).is_absolute()
        assert Path(bundle["cheap_replay"]["environment_manifest_ref_original"]).is_absolute()
        by_case[row["run_id"].rsplit("-", 1)[1]].append(row)

    assert {row["task_truth_status"] for row in by_case["ceiling"]} == {"pass"}
    assert {row["task_truth_status"] for row in by_case["baseline"]} == {"fail"}
    assert {row["task_truth_status"] for row in by_case["known_bad"]} == {"fail"}

    scoreboard = json.loads((tmp_path / "scoreboard.json").read_text(encoding="utf-8"))
    assert scoreboard["row_count"] == 15
    assert scoreboard["by_admission_level"]["certified"]["total"] == 15
