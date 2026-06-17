import json

from blocks.orientation.rhv1_prompt_plan_env import orient as rhv1_orient
from blocks.orientation.prompt_plan_env import orient as prompt_plan_env_orient
import runner.successor_slice_compile as successor_slice_compile
from runner.packet04_route_manifest import BASELINE_VARIANT_ID, SUCCESSOR_SLICE1_ROUTE_SCOPE, build_packet04_route_manifest


def test_compile_successor_slice_one_emits_amended_reports(tmp_path):
    out_dir = tmp_path / "compile_artifacts"
    report = successor_slice_compile.compile_successor_slice_one(output_dir=out_dir)

    assert report["status"] == "pass"
    assert (out_dir / "reference_harness_composition.json").exists()
    assert (out_dir / "ablation_manifests.json").exists()
    assert (out_dir / "eval_board_lane_bindings.json").exists()
    assert (out_dir / "fixture_grader_comparator_contracts.json").exists()
    assert (out_dir / "compile_report.json").exists()

    board_payload = json.loads((out_dir / "ablation_manifests.json").read_text(encoding="utf-8"))
    board = {row["variant_id"]: row for row in board_payload["controls"]}
    assert successor_slice_compile.PRIMARY_COMPARATOR_VARIANT_ID in board
    assert BASELINE_VARIANT_ID in board
    assert "rh1_no_completion_01" in board

    lane_payload = json.loads((out_dir / "eval_board_lane_bindings.json").read_text(encoding="utf-8"))
    lanes = {row["evaluation_lane"] for row in lane_payload["bindings"]}
    assert lanes == {"promotion", "bounded_diagnostic"}
    assert all(row["status"] == "pass" for row in lane_payload["bindings"])
    assert all(row["primary_comparator_variant_id"] == "spb_01" for row in lane_payload["bindings"])
    assert all(row["legacy_visibility_comparator_variant_id"] == BASELINE_VARIANT_ID for row in lane_payload["bindings"])


def test_successor_slice_one_scope_resolves_amended_route_manifests():
    baseline = build_packet04_route_manifest(BASELINE_VARIANT_ID, scope=SUCCESSOR_SLICE1_ROUTE_SCOPE)
    primary = build_packet04_route_manifest("spb_01", scope=SUCCESSOR_SLICE1_ROUTE_SCOPE)
    reference = build_packet04_route_manifest("rhv1_ref_01", scope=SUCCESSOR_SLICE1_ROUTE_SCOPE)
    completion_control = build_packet04_route_manifest("rh1_no_completion_01", scope=SUCCESSOR_SLICE1_ROUTE_SCOPE)
    assert baseline["route_scope"] == SUCCESSOR_SLICE1_ROUTE_SCOPE
    assert primary["route_scope"] == SUCCESSOR_SLICE1_ROUTE_SCOPE
    assert reference["route_scope"] == SUCCESSOR_SLICE1_ROUTE_SCOPE
    assert completion_control["route_scope"] == SUCCESSOR_SLICE1_ROUTE_SCOPE


def test_rhv1_reference_orientation_is_a_real_routed_delta():
    primary = build_packet04_route_manifest("spb_01", scope=SUCCESSOR_SLICE1_ROUTE_SCOPE)
    reference = build_packet04_route_manifest("rhv1_ref_01", scope=SUCCESSOR_SLICE1_ROUTE_SCOPE)

    def orientation_row(manifest):
        return next(row for row in manifest["routed_modules"] if row["runtime_key"] == "orientation")

    primary_orientation = orientation_row(primary)
    reference_orientation = orientation_row(reference)

    assert primary_orientation["surface_id"] == reference_orientation["surface_id"]
    assert primary_orientation["real_file_path"] != reference_orientation["real_file_path"]
    assert primary_orientation["module_import_path"] != reference_orientation["module_import_path"]


def test_rhv1_orientation_reserves_final_turn_and_requires_python3_for_multifile_tasks():
    context = rhv1_orient(
        "Read patch_plan.json, update files, and run verify_changes.py before completion.",
        {"cwd": "/tmp/workspace", "task_id": "smoke_multifile"},
    )
    system_text = context["messages"][0]["content"]
    assert "at most 2 tool turns" in system_text
    assert "python3, not python" in system_text
    assert "final model turn for a no-tool completion report" in system_text


def test_prompt_plan_env_verify_task_requires_exact_patch_plan_and_final_no_tool_turn():
    context = prompt_plan_env_orient(
        "Inspect the patch plan, update workspace/internal_multifile/src/service.py and workspace/internal_multifile/config/settings.env, and run verify_changes.py before completion.",
        {"cwd": "/tmp/workspace", "task_id": "smoke_multifile"},
    )
    system_text = context["messages"][0]["content"]
    assert "exact patch_plan.json file" in system_text
    assert "do not invent alternate patch-plan paths" in system_text
    assert "within 2 tool turns" in system_text
    assert "no-tool completion report" in system_text
    assert "consolidated inspection command" in system_text
    assert "workspace/internal_multifile/src/service.py" in system_text
    assert "workspace/internal_multifile/config/settings.env" in system_text


def test_compile_successor_slice_one_fails_closed_when_spb_missing(monkeypatch, tmp_path):
    board_without_spb = tuple(
        row for row in successor_slice_compile.SLICE_ONE_CONTROL_BOARD if row["variant_id"] != "spb_01"
    )
    monkeypatch.setattr(successor_slice_compile, "SLICE_ONE_CONTROL_BOARD", board_without_spb)
    out_dir = tmp_path / "compile_artifacts"
    report = successor_slice_compile.compile_successor_slice_one(output_dir=out_dir)

    assert report["status"] == "fail"
    assert any("missing mandatory primary comparator variant spb_01" in error for error in report["errors"])


def test_compile_successor_slice_one_fails_closed_without_mixed_lane_structure(monkeypatch, tmp_path):
    promotion_only_bindings = tuple(
        row for row in successor_slice_compile.SLICE_ONE_EVAL_BINDINGS if row["evaluation_lane"] == "promotion"
    )
    monkeypatch.setattr(successor_slice_compile, "SLICE_ONE_EVAL_BINDINGS", promotion_only_bindings)
    out_dir = tmp_path / "compile_artifacts"
    report = successor_slice_compile.compile_successor_slice_one(output_dir=out_dir)

    assert report["status"] == "fail"
    assert any("missing mixed promotion/bounded_diagnostic structure" in error for error in report["errors"])
