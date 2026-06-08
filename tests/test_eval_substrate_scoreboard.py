from __future__ import annotations

import json

import pytest

from runner.eval_substrate_scoreboard import build_scoreboard_from_result_files


def _row(**overrides):
    row = {
        "run_id": "run-1",
        "eval_id": "eval-1",
        "task_pack_id": "task-1",
        "family": "terminalbench",
        "surface_type": "filesystem",
        "admission_level": "certified",
        "backend_ref": "backend/ref",
        "environment_ref": "env/ref",
        "artifact_refs": ["artifact/ref"],
        "trace_refs": ["trace/ref"],
        "closure_status": "closed",
        "task_truth_status": "pass",
        "contamination_status": "clean",
        "failure_class": "none",
        "reason_codes": [],
        "verifier_ref": "verifier/ref",
        "grader_ref": "grader/ref",
        "score": 1.0,
    }
    row.update(overrides)
    return row


def test_scoreboard_aggregates_requested_dimensions(tmp_path):
    jsonl_path = tmp_path / "rows_a.jsonl"
    json_path = tmp_path / "rows_b.json"

    jsonl_path.write_text(
        "\n".join(
            [
                json.dumps(_row(run_id="run-1")),
                json.dumps(
                    _row(
                        run_id="run-2",
                        task_truth_status="fail",
                        failure_class="path_cwd",
                        reason_codes=["cwd_mismatch"],
                        score=0.0,
                    )
                ),
                json.dumps(
                    _row(
                        run_id="run-3",
                        family="bfcl",
                        surface_type="tool_call",
                        admission_level="draft",
                        contamination_status="suspect",
                        closure_status="invalid",
                        task_truth_status="invalid",
                        failure_class="tool_contract",
                        reason_codes=["invalid_tool_schema"],
                        score=0.0,
                    )
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    json_path.write_text(
        json.dumps(
            {
                "rows": [
                    _row(
                        run_id="run-4",
                        family="bfcl",
                        surface_type="tool_call",
                        admission_level="draft",
                        failure_class="none",
                    ),
                    _row(
                        run_id="run-5",
                        family="custom",
                        surface_type="retrieval",
                        admission_level="diagnostic",
                        closure_status="invalid",
                        task_truth_status="invalid",
                        failure_class="unclear",
                        reason_codes=["incomplete_row_debug"],
                        score=0.0,
                    ),
                ]
            }
        ),
        encoding="utf-8",
    )

    scoreboard = build_scoreboard_from_result_files([jsonl_path, json_path])

    assert scoreboard["row_count"] == 5
    assert scoreboard["totals"] == {"pass": 2, "fail": 1, "invalid": 2, "total": 5}

    assert scoreboard["by_family"]["terminalbench"] == {
        "pass": 1,
        "fail": 1,
        "invalid": 0,
        "total": 2,
    }
    assert scoreboard["by_family"]["bfcl"] == {"pass": 1, "fail": 0, "invalid": 1, "total": 2}
    assert scoreboard["by_family"]["custom"] == {
        "pass": 0,
        "fail": 0,
        "invalid": 1,
        "total": 1,
    }

    assert scoreboard["by_surface_type"]["filesystem"] == {
        "pass": 1,
        "fail": 1,
        "invalid": 0,
        "total": 2,
    }
    assert scoreboard["by_admission_level"]["certified"]["total"] == 2
    assert scoreboard["by_contamination_status"]["clean"] == {
        "pass": 2,
        "fail": 1,
        "invalid": 1,
        "total": 4,
    }
    assert scoreboard["by_failure_class"]["tool_contract"] == {
        "pass": 0,
        "fail": 0,
        "invalid": 1,
        "total": 1,
    }


def test_scoreboard_aggregates_cost_summary_from_row_payloads(tmp_path):
    path = tmp_path / "rows.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps(
                    _row(
                        run_id="run-cost-1",
                        token_and_cost_summary={
                            "total_input_messages": 1,
                            "input_tokens": 100,
                            "cached_input_tokens": 25,
                            "billable_input_tokens": 75,
                            "total_output_tokens": 40,
                            "output_tokens": 40,
                            "total_tokens": 140,
                            "usd": 0.01,
                            "usd_estimate": 0.01,
                            "cost_breakdown_usd": {
                                "input_cost": 0.003,
                                "cached_input_cost": 0.001,
                                "output_cost": 0.006,
                                "total_cost": 0.01,
                            },
                            "pricing_model_ids": ["gpt-5.4-mini"],
                        },
                    )
                ),
                json.dumps(
                    _row(
                        run_id="run-cost-2",
                        cost_summary={
                            "total_input_messages": 2,
                            "input_tokens": 50,
                            "cached_input_tokens": 5,
                            "billable_input_tokens": 45,
                            "total_output_tokens": 10,
                            "output_tokens": 10,
                            "total_tokens": 60,
                            "usd": 0.02,
                            "usd_estimate": 0.02,
                            "cost_breakdown_usd": {
                                "input_cost": 0.01,
                                "cached_input_cost": 0.002,
                                "output_cost": 0.008,
                                "total_cost": 0.02,
                            },
                            "pricing_model_ids": ["gpt-5.3-codex"],
                        },
                    )
                ),
                json.dumps(_row(run_id="run-cost-3")),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    scoreboard = build_scoreboard_from_result_files([path])

    assert scoreboard["cost_summary"]["run_count"] == 3
    assert scoreboard["cost_summary"]["model_backed_run_count"] == 2
    assert scoreboard["cost_summary"]["total_input_messages"] == 3
    assert scoreboard["cost_summary"]["input_tokens"] == 150
    assert scoreboard["cost_summary"]["cached_input_tokens"] == 30
    assert scoreboard["cost_summary"]["billable_input_tokens"] == 120
    assert scoreboard["cost_summary"]["output_tokens"] == 50
    assert scoreboard["cost_summary"]["total_tokens"] == 200
    assert scoreboard["cost_summary"]["usd"] == pytest.approx(0.03, rel=0.0, abs=1e-12)
    assert scoreboard["cost_summary"]["usd_estimate"] == pytest.approx(0.03, rel=0.0, abs=1e-12)
    assert scoreboard["cost_summary"]["pricing_model_ids"] == ["gpt-5.3-codex", "gpt-5.4-mini"]


def test_scoreboard_accepts_list_json_payload(tmp_path):
    path = tmp_path / "rows.json"
    path.write_text(
        json.dumps(
            [
                    _row(
                        run_id="run-list",
                        family="custom",
                        surface_type="verifier_repair",
                        admission_level="certified",
                    )
            ]
        ),
        encoding="utf-8",
    )

    scoreboard = build_scoreboard_from_result_files([path])

    assert scoreboard["row_count"] == 1
    assert scoreboard["totals"] == {"pass": 1, "fail": 0, "invalid": 0, "total": 1}
    assert scoreboard["by_family"]["custom"]["pass"] == 1


def test_scoreboard_rejects_non_contract_rows(tmp_path):
    path = tmp_path / "not_a_result_row.json"
    path.write_text(json.dumps({"status": "ok", "family": "prose_claim"}), encoding="utf-8")

    with pytest.raises(Exception, match="missing required fields"):
        build_scoreboard_from_result_files([path])
