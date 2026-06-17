from __future__ import annotations

import json
from pathlib import Path

from runner.final_harness_eval_suite_adapter import FinalSuiteRowSpec
from tools import run_final_harness_eval_suite_baseline as mod


def _row_spec(row_id: str) -> FinalSuiteRowSpec:
    return FinalSuiteRowSpec(
        row_id=row_id,
        row_type="sentinel",
        is_flagship=False,
        provenance_type="private_homolog",
        critical_clusters=("filesystem/path",),
        task_pack_ref="tracking/collab/final_harness_eval_suite/task_packs/sentinel/fsent_03_filesystem_verifier_repair/task_pack.yaml",
        task_pack_id=row_id,
        canonical_workspace_root="/workspace/fsverify",
        runtime_python_command="python3",
        max_solver_seconds=180,
        surface_type="filesystem",
        legacy_layout=False,
        expected_candidate_output="/workspace/fsverify/out/final_submission.json",
        execution_source="task_pack",
    )


def test_resolve_candidate_path_strips_canonical_root_prefix(tmp_path):
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)
    spec = _row_spec("fsent_03_filesystem_verifier_repair")

    resolved = mod._resolve_candidate_path(
        workspace_root,
        spec.expected_candidate_output,
        spec,
    )

    assert resolved == (workspace_root / "out" / "final_submission.json").resolve()


def test_invalid_rows_include_execution_truth_payload(tmp_path, monkeypatch):
    spec = _row_spec("fhard_01_toolchain_runner_repair")
    monkeypatch.setattr(mod, "load_final_suite_row_specs", lambda _repo_root: [spec])
    monkeypatch.setattr(mod, "_resolve_model_route", lambda _mode: ({"provider": "stub", "model": "stub"}, "local_stub"))
    monkeypatch.setattr(
        mod,
        "_docker_runtime_status",
        lambda: {
            "available": False,
            "reason_code": "invalid_environment_docker_unavailable",
            "reason": "docker daemon unavailable",
            "probe": {"command": ["docker", "version"], "returncode": 1},
        },
    )

    result = mod.run_final_harness_eval_suite_baseline(output_root=tmp_path, model_mode="stub")
    run_root = Path(result["run_root"])
    rows = [
        json.loads(line)
        for line in (run_root / "result_rows.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    assert rows[0]["verdict"] == "invalid"

    artifact_ref = Path(rows[0]["artifact_refs"][0])
    artifact_bundle = json.loads(artifact_ref.read_text(encoding="utf-8"))
    execution_truth_ref = Path(artifact_bundle["execution_truth_ref"])
    execution_truth = json.loads(execution_truth_ref.read_text(encoding="utf-8"))

    assert execution_truth["invalid_execution"]["reason_code"] == "invalid_environment_docker_unavailable"
