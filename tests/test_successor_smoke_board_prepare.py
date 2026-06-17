import json

import runner.successor_smoke_board_prepare as smoke_prepare


def test_prepare_successor_smoke_board_emits_artifacts(tmp_path):
    out_dir = tmp_path / "smoke_prepare"
    report = smoke_prepare.prepare_successor_smoke_board(output_dir=out_dir)

    assert report["status"] == "pass"
    assert (out_dir / "smoke_route_set.json").exists()
    assert (out_dir / "smoke_eval_board.json").exists()
    assert (out_dir / "smoke_trace_markers.json").exists()
    assert (out_dir / "smoke_grader_comparator_readiness.json").exists()
    assert (out_dir / "smoke_live_gate_artifact_boundary.json").exists()
    assert (out_dir / "smoke_prepare_report.json").exists()

    route_payload = json.loads((out_dir / "smoke_route_set.json").read_text(encoding="utf-8"))
    routes = {row["variant_id"]: row for row in route_payload["routes"]}
    assert "spb_01" in routes
    assert "rhv1_ref_01" in routes
    assert routes["spb_01"]["enabled_for_initial_smoke"] is True
    assert routes["rhv1_ref_01"]["enabled_for_initial_smoke"] is True

    board_payload = json.loads((out_dir / "smoke_eval_board.json").read_text(encoding="utf-8"))
    homes = board_payload["homes"]
    assert 2 <= len(homes) <= 4
    assert all(row["primary_comparator_variant_id"] == "spb_01" for row in homes)
    assert all(row["legacy_visibility_comparator_variant_id"] == "sc_b_01" for row in homes)

    marker_payload = json.loads((out_dir / "smoke_trace_markers.json").read_text(encoding="utf-8"))
    mechanism_contract = marker_payload["declared_vs_observed_mechanism_contract"]
    assert mechanism_contract["declared_field"] == "trace_summary.declared_mechanisms"
    assert mechanism_contract["observed_field"] == "trace_summary.observed_mechanisms"
    assert mechanism_contract["rhv1_reference_variant_id"] == "rhv1_ref_01"
    assert mechanism_contract["primary_comparator_variant_id"] == "spb_01"
    assert mechanism_contract["forbid_rhv1_marker_family_on_primary_comparator"] is True
    assert set(mechanism_contract["required_rhv1_observed_marker_ids"]) == {
        "environment_aware_orientation",
        "target_state_updates",
        "evidence_state_ledger_entries",
        "structured_state_context_summaries",
        "evidence_backed_completion_gate",
        "verification_before_completion_decision",
        "failure_source_typing",
    }


def test_prepare_successor_smoke_board_fails_without_primary_route(monkeypatch, tmp_path):
    route_set_without_spb = tuple(row for row in smoke_prepare.SMOKE_ROUTE_SET if row["variant_id"] != "spb_01")
    monkeypatch.setattr(smoke_prepare, "SMOKE_ROUTE_SET", route_set_without_spb)

    out_dir = tmp_path / "smoke_prepare"
    report = smoke_prepare.prepare_successor_smoke_board(output_dir=out_dir)

    assert report["status"] == "fail"
    assert any("missing one or more required compiled routes" in error for error in report["errors"])


def test_prepare_successor_smoke_board_fails_when_eval_home_count_exceeds_bound(monkeypatch, tmp_path):
    too_many_homes = tuple(smoke_prepare.SMOKE_EVAL_BOARD) + (
        {
            "home_id": "smoke_extra_home_out_of_bounds",
            "eval_id": "ae_sync_interrupt_cleanup_probe",
            "evaluation_lane": "bounded_diagnostic",
            "required": False,
            "focus": "out_of_bounds_guard",
        },
        {
            "home_id": "smoke_extra_home_out_of_bounds_2",
            "eval_id": "ae_sync_interrupt_cleanup_probe",
            "evaluation_lane": "bounded_diagnostic",
            "required": False,
            "focus": "out_of_bounds_guard",
        },
    )
    monkeypatch.setattr(smoke_prepare, "SMOKE_EVAL_BOARD", too_many_homes)

    out_dir = tmp_path / "smoke_prepare"
    report = smoke_prepare.prepare_successor_smoke_board(output_dir=out_dir)

    assert report["status"] == "fail"
    assert any("must contain 2-4 homes" in error for error in report["errors"])
