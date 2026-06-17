from __future__ import annotations

import json
from pathlib import Path

from tools import aether2_fake_progress_homologs as mod


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = (
    REPO_ROOT
    / "tracking"
    / "collab"
    / "aether2_fake_progress_homologs"
    / "homolog_manifest.example.json"
)


def test_manifest_example_matches_builder_and_validates() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    assert manifest == mod.build_manifest()
    report = mod.validate_manifest(manifest)
    assert report["status"] == "pass"
    assert len(report["manifest"]["evals"]) == 9


def test_each_eval_ceiling_passes_and_known_bad_fails(tmp_path: Path) -> None:
    manifest = mod.build_manifest()

    for spec in manifest["evals"]:
        eval_id = spec["eval_id"]

        ceiling_root = tmp_path / eval_id / "ceiling"
        mod.materialize_fixture(eval_id, ceiling_root)
        mod.write_control_output(eval_id, "ceiling", ceiling_root)
        ceiling_grade = mod.grade_eval(eval_id, ceiling_root)
        assert ceiling_grade["verdict"] == "pass", (eval_id, ceiling_grade)

        known_bad_root = tmp_path / eval_id / "known_bad"
        mod.materialize_fixture(eval_id, known_bad_root)
        mod.write_control_output(eval_id, "known_bad", known_bad_root)
        known_bad_grade = mod.grade_eval(eval_id, known_bad_root)
        assert known_bad_grade["verdict"] == "fail", (eval_id, known_bad_grade)


def test_reserved_baseline_row_is_not_run(tmp_path: Path) -> None:
    eval_id = "fp_01_candidate_label_structure"
    root = tmp_path / "baseline_reserved"

    mod.materialize_fixture(eval_id, root)
    mod.write_control_output(eval_id, "baseline_reserved", root)
    row = mod.build_control_row(eval_id, "baseline_reserved", root)

    assert row["row_status"] == "not_run_reserved"
    assert row["scoreable"] is False
    assert row["reason_codes"] == ["reserved_for_runner_phase"]
