from __future__ import annotations

import json

from runner.benchmark_adapter_acebench import (
    EQUIVALENT_AUTHORITY_DETAIL,
    EQUIVALENT_AUTHORITY_LABEL,
    NATIVE_AUTHORITY_LABEL,
    build_native_tool_definitions,
    build_result_row_for_grade,
    build_task_pack,
    grade_case_equivalent,
    native_grader_preflight,
    selected_case_spec,
)
from runner.eval_substrate_contracts import validate_result_row
from tools.run_benchmark_adapter_acebench_smoke import run_benchmark_adapter_acebench_smoke


def _expected_call_text() -> str:
    spec = selected_case_spec()
    function_name, kwargs = next(iter(spec["expected_call"].items()))
    rendered = ", ".join(f"{key}={repr(value) if isinstance(value, str) else value}" for key, value in kwargs.items())
    return f"[{function_name}({rendered})]"


def test_acebench_equivalent_grader_pass_and_known_bad_behavior():
    spec = selected_case_spec()
    function_name = next(iter(spec["expected_call"].keys()))
    pass_grade = grade_case_equivalent(_expected_call_text())
    known_bad_grade = grade_case_equivalent(
        f"[{function_name}(meal_type='dinner', include_vegetarian_options=False, cuisine_preference='Asian')]"
    )

    assert pass_grade["verdict"] == "pass"
    assert pass_grade["authority_label"] == EQUIVALENT_AUTHORITY_LABEL
    assert pass_grade["authority_detail"] == EQUIVALENT_AUTHORITY_DETAIL

    assert known_bad_grade["verdict"] == "fail"
    assert "acebench_parameter_mismatch" in known_bad_grade["reason_codes"]
    assert known_bad_grade["expected_call_hash"] != known_bad_grade["observed_call_hash"]


def test_acebench_result_row_matches_eval_substrate_contract():
    grade = grade_case_equivalent(_expected_call_text())
    row = build_result_row_for_grade(
        run_id="acebench-row-pass",
        eval_id="acebench-adapter-smoke",
        task_pack_id="acebench-normal-atom-bool-smoke",
        control_label="pass",
        environment_ref="debug://local_no_sandbox",
        artifact_refs=["artifacts/bundle.json"],
        trace_refs=["traces/trace.json"],
        verifier_ref="artifacts/verifier.json",
        grader_ref="artifacts/grader.json",
        grade=grade,
        authority_label=EQUIVALENT_AUTHORITY_LABEL,
        authority_detail=EQUIVALENT_AUTHORITY_DETAIL,
    )

    assert validate_result_row(row)["surface_type"] == "tool_call"
    assert row["task_truth_status"] == "pass"
    assert row["authority_label"] == EQUIVALENT_AUTHORITY_LABEL
    assert row["authority_detail"] == EQUIVALENT_AUTHORITY_DETAIL


def test_acebench_smoke_runner_equivalent_emits_rows_scoreboard_and_blocker_report(tmp_path):
    summary = run_benchmark_adapter_acebench_smoke(tmp_path, authority_mode="equivalent")
    scoreboard = json.loads((tmp_path / "scoreboard.json").read_text(encoding="utf-8"))

    assert summary["output_authority_label"] == EQUIVALENT_AUTHORITY_LABEL
    assert summary["output_authority_detail"] == EQUIVALENT_AUTHORITY_DETAIL
    assert summary["native_blocker_report_path"]
    assert scoreboard["row_count"] == 3
    assert scoreboard["totals"] == {"pass": 2, "fail": 1, "invalid": 0, "total": 3}
    assert scoreboard["by_family"]["acebench_adapter"] == {
        "pass": 2,
        "fail": 1,
        "invalid": 0,
        "total": 3,
    }
    assert scoreboard["by_surface_type"]["tool_call"]["total"] == 3


def test_acebench_native_preflight_reports_blocked_when_upstream_assets_missing(tmp_path):
    preflight = native_grader_preflight(upstream_root=tmp_path / "missing")
    assert preflight["native_runtime_available"] is False
    assert "missing_upstream_assets" in preflight["blocker_codes"]


def test_acebench_task_pack_contract_has_explicit_authority_label():
    task_pack = build_task_pack(
        task_pack_id="acebench-smoke",
        authority_label=NATIVE_AUTHORITY_LABEL,
        authority_detail="detail",
        adapter_label="label",
        admission_level="certified",
    )
    assert task_pack["hidden_verifier"]["leak_hidden_checks_to_prompt"] is False
    assert task_pack["surface_type"] == "tool_call"
    assert task_pack["benchmark_adapter_contract"]["authority_label"] == NATIVE_AUTHORITY_LABEL
    assert task_pack["admission_level"] == "certified"


def test_acebench_supports_multiple_selected_official_cases():
    deep_spec = selected_case_spec("normal_atom_object_deep_0")
    grade = grade_case_equivalent(
        "[partner_assessment_evaluate_operational_efficiency(partner_id='TP-12345', evaluation_criteria={'metrics': ['time savings', 'cost reduction'], 'time_frame': 'Last Quarter'})]",
        case_id="normal_atom_object_deep_0",
    )

    assert deep_spec["category"] == "normal_atom_object_deep"
    assert grade["verdict"] == "pass"


def test_acebench_native_certified_row_is_promotion_eligible():
    grade = {
        "verdict": "pass",
        "reason_codes": [],
        "score": 1.0,
    }
    row = build_result_row_for_grade(
        run_id="acebench-native-certified-pass",
        eval_id="acebench-native-certified",
        task_pack_id="acebench-native-certified-pack",
        control_label="ceiling",
        environment_ref="certified://acebench-native-vm",
        artifact_refs=["artifacts/bundle.json"],
        trace_refs=["traces/trace.json"],
        verifier_ref="artifacts/verifier.json",
        grader_ref="artifacts/grader.json",
        grade=grade,
        authority_label=NATIVE_AUTHORITY_LABEL,
        authority_detail="acebench_native_official_eval_main_runtime_and_checker",
        backend_ref="linux_container",
        admission_level="certified",
    )

    assert row["native_certification_status"] == "native_certified_pass"
    assert row["native_promotion_eligible"] is True


def test_acebench_native_tool_definitions_are_loaded_from_upstream_prompt_schema(tmp_path, monkeypatch):
    upstream_root = tmp_path / "acebench_upstream"
    prompt_dir = upstream_root / "data_all" / "data_en"
    prompt_dir.mkdir(parents=True)
    prompt_path = prompt_dir / "data_normal_atom_bool.json"
    prompt_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "id": "normal_atom_bool_0",
                        "question": "choose a function",
                        "function": [
                            {
                                "name": "alpha_tool",
                                "description": "Alpha tool",
                                "arguments": {
                                    "type": "object",
                                    "properties": {"value": {"type": "string"}},
                                    "required": ["value"],
                                },
                            },
                            {
                                "name": "beta_tool",
                                "description": "Beta tool",
                                "parameters": {
                                    "type": "object",
                                    "properties": {"count": {"type": "integer"}},
                                    "required": ["count"],
                                },
                            },
                        ],
                        "time": 0,
                    }
                )
            ]
        ),
        encoding="utf-8",
    )

    definitions = build_native_tool_definitions(case_id="normal_atom_bool_0", upstream_root=upstream_root)
    names = {entry["name"] for entry in definitions}

    assert names == {"alpha_tool", "beta_tool"}
    assert definitions[0]["input_schema"] == definitions[0]["parameters"]
    assert definitions[1]["input_schema"] == definitions[1]["parameters"]
    assert definitions[0]["input_schema"]["type"] == "object"
