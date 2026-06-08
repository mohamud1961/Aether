from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.clean_tool_contract_diagnostic_family import CASE_IDS, FAMILIES, SOURCE_LABEL, stage_solver_and_reviewer_packs, task_pack_for_family
from runner.eval_substrate_contracts import validate_task_pack


def test_clean_tool_contract_task_packs_validate_and_use_certified_contract():
    assert CASE_IDS == ("baseline", "known_bad", "ceiling")
    assert len(FAMILIES) == 3
    for family in FAMILIES:
        task_pack = task_pack_for_family(family)
        validate_task_pack(task_pack)
        assert task_pack["admission_level"] == "certified"
        assert task_pack["surface_type"] == "tool_call"
        assert task_pack["solver_reviewer_pack_contract"]["reviewer_pack_mount_ref"] == "/reviewer_pack"
        assert task_pack["solver_reviewer_pack_contract"]["hidden_truth_in_solver_pack"] is False
        assert task_pack["contamination_policy"]["benchmark_label"] == SOURCE_LABEL


def test_clean_tool_contract_fixture_staging_excludes_hidden_truth_from_solver(tmp_path):
    family = FAMILIES[0]
    refs = stage_solver_and_reviewer_packs(
        fixture_root=tmp_path / "fixture",
        family=family,
        case_id="baseline",
        case_state=family["baseline"],
    )
    solver_root = refs["solver_root"]
    reviewer_root = refs["reviewer_root"]

    assert (solver_root / "answer.json").exists()
    assert (solver_root / "verifier.py").exists()
    assert (solver_root / "tools_schema.json").exists()
    assert not (solver_root / "reviewer_pack").exists()
    assert not (solver_root / "hidden_expected_values.json").exists()
    assert not (solver_root / "hidden_policy.json").exists()
    assert not (solver_root / "hidden_case_manifest.json").exists()

    assert (reviewer_root / "hidden_expected_values.json").exists()
    assert (reviewer_root / "hidden_policy.json").exists()
    assert (reviewer_root / "hidden_case_manifest.json").exists()
    assert (reviewer_root / "hidden_verifier.py").exists()
    assert (reviewer_root / "hidden_tests" / "test_hidden_regressions.py").exists()

    policy = json.loads((reviewer_root / "hidden_policy.json").read_text(encoding="utf-8"))
    assert policy["grader_kind"] == "multi_required_order"


def test_hidden_verifier_ignores_auxiliary_prose_fields(tmp_path):
    family = FAMILIES[0]
    refs = stage_solver_and_reviewer_packs(
        fixture_root=tmp_path / "fixture",
        family=family,
        case_id="ceiling",
        case_state=family["expected"],
    )
    solver_root = refs["solver_root"]
    reviewer_root = refs["reviewer_root"]
    answer = json.loads((solver_root / "answer.json").read_text(encoding="utf-8"))
    answer["tool_calls"][0]["explanation"] = "completely different prose"
    answer["tool_calls"][1]["state_dependency"] = "another prose string"
    (solver_root / "answer.json").write_text(json.dumps(answer, indent=2, sort_keys=True), encoding="utf-8")

    proc = subprocess.run(
        ["python3", "hidden_verifier.py", "--solver-root", str(solver_root), "--case-id", "ceiling"],
        cwd=reviewer_root,
        capture_output=True,
        text=True,
        check=False,
    )
    payload = json.loads(proc.stdout)
    assert proc.returncode == 0
    assert payload["passed"] is True
    assert payload["semantic_only"] is True
