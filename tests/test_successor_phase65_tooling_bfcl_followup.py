from __future__ import annotations

import inspect
import json

from runner import successor_phase65_tooling_bfcl_followup as mod


CONTROL = "spb_01"
INCUMBENT = "spb_tooling_seed_plus_receipt_and_completion_01"
RECOMMENDATIONS = {
    "tooling_bfcl_followup_ready_for_family_reducer",
    "tooling_bfcl_followup_partial_uplift_tooling_still_open",
    "tooling_bfcl_followup_blocked",
}


def _launch(tmp_path):
    params = inspect.signature(mod.launch_phase65_tooling_bfcl_followup).parameters
    if "execute" in params:
        return mod.launch_phase65_tooling_bfcl_followup(output_dir=tmp_path, execute=False)
    return mod.launch_phase65_tooling_bfcl_followup(output_dir=tmp_path)


def _load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _comparison_set(*, manifest, report):
    return set(manifest.get("comparison_set") or report.get("comparison_set") or [])


def _planned_runs(execution):
    for key in ("planned_model_backed_runs", "planned_probe_runs", "planned_runs"):
        value = execution.get(key)
        if isinstance(value, int):
            return value
    return None


def _root_cause(row):
    for key in ("root_cause", "root_cause_summary", "failure_root_cause"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def test_tooling_bfcl_followup_writes_required_board_artifacts(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "_record_ledger", lambda raw: None)

    result = _launch(tmp_path)

    if "selected_recommendation" in result:
        assert result["selected_recommendation"] in RECOMMENDATIONS
    required = {
        "phase65_tooling_bfcl_followup_board_manifest.json",
        "phase65_tooling_bfcl_followup_route_matrix.json",
        "phase65_tooling_bfcl_followup_variant_doctrine_matrix.json",
        "phase65_tooling_bfcl_followup_execution_plan.json",
        "phase65_tooling_bfcl_followup_result_records.jsonl",
        "phase65_tooling_bfcl_followup_score_envelope.json",
        "phase65_tooling_bfcl_followup_report.json",
        "phase65_tooling_bfcl_followup_trace_report.json",
        "phase65_tooling_bfcl_followup_failure_source_report.json",
        "phase65_tooling_bfcl_followup_deep_trace_analysis.md",
        "phase65_tooling_bfcl_followup_handoff.md",
        "RAW_LEDGER_UPDATE",
    }
    assert required.issubset({path.name for path in tmp_path.iterdir()})


def test_tooling_bfcl_followup_narrow_board_policy_keeps_control_incumbent_and_caps_challengers(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "_record_ledger", lambda raw: None)

    _launch(tmp_path)

    manifest = _load_json(tmp_path / "phase65_tooling_bfcl_followup_board_manifest.json")
    report = _load_json(tmp_path / "phase65_tooling_bfcl_followup_report.json")
    route = _load_json(tmp_path / "phase65_tooling_bfcl_followup_route_matrix.json")
    doctrine = _load_json(tmp_path / "phase65_tooling_bfcl_followup_variant_doctrine_matrix.json")
    execution = _load_json(tmp_path / "phase65_tooling_bfcl_followup_execution_plan.json")

    comparison = _comparison_set(manifest=manifest, report=report)
    assert {CONTROL, INCUMBENT} <= comparison
    assert len(comparison - {CONTROL, INCUMBENT}) <= 1

    if "slice_type" in manifest:
        slice_type = str(manifest["slice_type"]).lower()
        assert "tool" in slice_type or "bfcl" in slice_type
        assert "context" not in slice_type
        assert "completion" not in slice_type
        assert "verification" not in slice_type
        assert "recovery" not in slice_type

    assert route["status"] == "pass"
    assert doctrine["status"] == "pass"

    planned_runs = _planned_runs(execution)
    assert planned_runs is not None
    assert planned_runs > 0


def test_tooling_bfcl_followup_trace_report_has_per_run_root_causes_and_deep_trace_ledger(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "_record_ledger", lambda raw: None)

    _launch(tmp_path)

    score = _load_json(tmp_path / "phase65_tooling_bfcl_followup_score_envelope.json")
    trace = _load_json(tmp_path / "phase65_tooling_bfcl_followup_trace_report.json")
    failure = _load_json(tmp_path / "phase65_tooling_bfcl_followup_failure_source_report.json")
    deep_trace = (tmp_path / "phase65_tooling_bfcl_followup_deep_trace_analysis.md").read_text(encoding="utf-8")
    rows = trace["traces"]

    assert score["selected_recommendation"] in RECOMMENDATIONS
    assert rows
    assert all(row.get("run_id") for row in rows)
    assert all(row.get("variant_id") for row in rows)
    assert all(row.get("eval_id") for row in rows)
    assert all(_root_cause(row) for row in rows)

    sources = {str(row.get("source", "")) for row in rows}
    assert any("tool" in source for source in sources)
    assert any("bfcl" in source for source in sources)

    assert failure.get("mission_id") == "successor_phase65_tooling_bfcl_followup"
    assert isinstance(failure.get("behavioral_tooling_failure_variant_count"), int)
    assert isinstance(failure.get("bfcl_invalid_infrastructure_failure_count"), int)

    assert "Full Run Ledger" in deep_trace
