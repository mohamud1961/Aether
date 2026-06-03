from __future__ import annotations

import json
from runner.kernel_layer2_audit import (
    _clean_hidden_refs,
    build_layer2_audit_prompt,
    deterministic_layer2_fallback,
    parse_layer2_audit_response,
    normalize_layer2_audit_state,
    should_run_layer2,
)


def test_clean_hidden_refs():
    data = {
        "visible_field": 123,
        "hidden_expected_answer": "secret",
        "nested": {"good": "ok", "grader_value": 456, "secret_key": "xyz"},
        "list_field": [{"ok": 1, "hidden_val": 2}],
    }
    cleaned = _clean_hidden_refs(data)
    assert cleaned == {"visible_field": 123, "nested": {"good": "ok"}, "list_field": [{"ok": 1}]}


def test_build_layer2_audit_prompt_removes_hidden_keys():
    success_contract = {"criteria": ["check file exists"], "expected_answer": "hidden info"}
    context_pack = {
        "files_written": ["out.txt"],
        "hidden_grader_check": True,
    }
    finalization_gate = {"governed_status": "governed_pass", "secret_details": "leak"}
    messages = build_layer2_audit_prompt(
        task_prompt="extract files",
        success_contract=success_contract,
        context_pack=context_pack,
        finalization_gate=finalization_gate,
    )

    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"

    user_payload = json.loads(messages[1]["content"])
    assert user_payload["task_prompt"] == "extract files"
    assert "expected_answer" not in user_payload["success_contract"]
    assert "hidden_grader_check" not in user_payload["context_pack"]
    assert "secret_details" not in user_payload["finalization_gate"]
    assert user_payload["success_contract"]["criteria"] == ["check file exists"]


def test_parse_layer2_audit_response_valid():
    raw_response = """
    ```json
    {
      "verdict": "PASS",
      "confidence": "high",
      "mismatches": [],
      "missing_evidence": [],
      "reason_codes": ["all_passed"],
      "repair_instruction": ""
    }
    ```
    """
    parsed = parse_layer2_audit_response(raw_response)
    assert parsed["verdict"] == "PASS"
    assert parsed["confidence"] == "high"
    assert parsed["reason_codes"] == ["all_passed"]


def test_parse_layer2_audit_response_invalid_json():
    parsed = parse_layer2_audit_response("not a json")
    assert parsed["verdict"] == "UNCLEAR"
    assert parsed["confidence"] == "low"
    assert "layer2_parse_failed" in parsed["reason_codes"]


def test_normalize_layer2_audit_state_adds_missing_alias_and_blocks_conflicts():
    model_state = {
        "verdict": "FAIL",
        "confidence": "medium",
        "reason_codes": ["missing_required_artifacts"],
        "mismatches": ["required_artifacts"],
    }
    static_state = {
        "status": "unclear",
        "reason_codes": ["missing_artifact_evidence"],
        "missing_evidence": ["artifact_refs"],
    }
    conflicting_state = {
        "status": "pass",
        "verdict": "FAIL",
        "reason_codes": ["layer2_audit_failed"],
    }

    normalized_model = normalize_layer2_audit_state(model_state)
    normalized_static = normalize_layer2_audit_state(static_state)
    normalized_conflict = normalize_layer2_audit_state(conflicting_state)

    assert normalized_model["status"] == "fail"
    assert normalized_model["verdict"] == "FAIL"
    assert normalized_static["status"] == "unclear"
    assert normalized_static["verdict"] == "UNCLEAR"
    assert normalized_conflict["status"] == "fail"
    assert normalized_conflict["verdict"] == "FAIL"


def test_deterministic_layer2_fallback_pass():
    final_gate = {"governed_status": "governed_pass", "reason_codes": []}
    res = deterministic_layer2_fallback(finalization_gate=final_gate, success_contract={})
    assert res["verdict"] == "PASS"
    assert res["confidence"] == "high"


def test_deterministic_layer2_fallback_fail():
    final_gate = {
        "governed_status": "verifier_failed",
        "reason_codes": ["verifier_failed"],
        "open_obligations": {"fix_something": {}},
    }
    res = deterministic_layer2_fallback(finalization_gate=final_gate, success_contract={})
    assert res["verdict"] == "FAIL"
    assert "verifier_failed" in res["reason_codes"]
    assert len(res["mismatches"]) > 0


def test_should_run_layer2_checks():
    manifest_no_flag = {"variant_id": "v1"}
    manifest_with_flag = {"variant_id": "v1", "feature_flags": {"layer2_success_audit": True}}

    gate_pass = {"governed_status": "governed_pass"}
    gate_fail = {"governed_status": "verifier_failed"}

    # 1. No feature flag
    assert not should_run_layer2(route_manifest=manifest_no_flag, finalization_gate=gate_pass)
    # 2. Feature flag but gate fails
    assert not should_run_layer2(route_manifest=manifest_with_flag, finalization_gate=gate_fail)
    # 3. Both match
    assert should_run_layer2(route_manifest=manifest_with_flag, finalization_gate=gate_pass)
