from __future__ import annotations

import json

from runner.kernel_native_tools import execute_tool_call, get_tools, normalize_tool_schema, validate_tool_arguments


def test_normalize_tool_schema_and_tool_loading_alias_parameters_to_input_schema(tmp_path):
    manifest = [
        {
            "name": "sample_tool",
            "description": "generic tool",
            "parameters": {
                "properties": {
                    "config": {
                        "properties": {
                            "mode": {"type": "string"},
                        },
                        "required": ["mode"],
                    }
                },
                "required": ["config"],
            },
        }
    ]
    (tmp_path / "visible_inputs.json").write_text(json.dumps(manifest), encoding="utf-8")

    tools = get_tools(cwd=str(tmp_path))

    assert [tool["name"] for tool in tools] == ["sample_tool"]
    schema = tools[0]["input_schema"]
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is True
    assert schema["properties"]["config"]["type"] == "object"
    assert schema["properties"]["config"]["additionalProperties"] is True
    assert normalize_tool_schema({"properties": {"flag": {"type": "boolean"}}})["type"] == "object"


def test_validate_tool_arguments_reports_missing_required_args():
    schema = {
        "type": "object",
        "properties": {
            "value": {"type": "string"},
            "count": {"type": "integer"},
        },
        "required": ["value", "count"],
    }

    report = validate_tool_arguments(schema, {"value": "ok"})

    assert report["status"] == "fail"
    assert report["missing_required"] == ["count"]
    assert report["type_violations"] == []
    assert report["enum_violations"] == []


def test_validate_tool_arguments_checks_primitive_types():
    schema = {
        "type": "object",
        "properties": {
            "text": {"type": "string"},
            "count": {"type": "integer"},
            "ratio": {"type": "number"},
            "enabled": {"type": "boolean"},
        },
        "required": ["text", "count", "ratio", "enabled"],
    }

    passing = validate_tool_arguments(schema, {"text": "hello", "count": 3, "ratio": 2.5, "enabled": False})
    failing = validate_tool_arguments(schema, {"text": 7, "count": True, "ratio": "2.5", "enabled": "yes"})

    assert passing["status"] == "pass"
    assert failing["status"] == "fail"
    assert {violation["path"] for violation in failing["type_violations"]} == {"text", "count", "ratio", "enabled"}


def test_validate_tool_arguments_checks_enums():
    schema = {
        "type": "object",
        "properties": {
            "mode": {"type": "string", "enum": ["fast", "safe"]},
            "choice": {"type": "integer", "enum": [1, 2]},
        },
        "required": ["mode", "choice"],
    }

    report = validate_tool_arguments(schema, {"mode": "slow", "choice": 3})

    assert report["status"] == "fail"
    assert {violation["path"] for violation in report["enum_violations"]} == {"mode", "choice"}


def test_validate_tool_arguments_checks_one_level_nested_objects():
    schema = {
        "type": "object",
        "properties": {
            "config": {
                "type": "object",
                "properties": {
                    "mode": {"type": "string"},
                    "retries": {"type": "integer"},
                },
                "required": ["mode"],
            }
        },
        "required": ["config"],
    }

    passing = validate_tool_arguments(schema, {"config": {"mode": "safe", "retries": 2}})
    failing = validate_tool_arguments(schema, {"config": {"retries": "two"}})

    assert passing["status"] == "pass"
    assert failing["status"] == "fail"
    assert failing["missing_required"] == ["config.mode"]
    assert {violation["path"] for violation in failing["type_violations"]} == {"config.retries"}


def test_execute_tool_call_rejects_native_schema_violations_before_runtime_dispatch():
    observed = {"called": False}

    def _runtime(_tool_call):  # type: ignore[no-untyped-def]
        observed["called"] = True
        raise AssertionError("runtime should not be reached when schema validation fails")

    sandbox = type("_Sandbox", (), {})()
    sandbox.native_tool_definitions = [
        {
            "name": "sample_tool",
            "input_schema": {
                "type": "object",
                "properties": {"value": {"type": "string"}},
                "required": ["value"],
            },
        }
    ]
    sandbox.native_tool_registry = {"sample_tool": _runtime}

    result = execute_tool_call({"name": "sample_tool", "arguments": {}}, sandbox)

    assert result["result_class"] == "contract_error"
    assert result["reason_code"] == "native_tool_schema_violation"
    assert observed["called"] is False


def test_execute_tool_call_includes_validation_report_in_all_outcomes():
    # 1. Validation Fail
    sandbox = type("_Sandbox", (), {})()
    sandbox.native_tool_definitions = [
        {
            "name": "math_tool",
            "input_schema": {
                "type": "object",
                "properties": {"value": {"type": "integer"}},
                "required": ["value"],
            },
        }
    ]
    sandbox.native_tool_registry = {"math_tool": lambda tc: {"result_class": "success"}}

    result_fail = execute_tool_call({"name": "math_tool", "arguments": {"value": "not-an-int"}}, sandbox)
    assert result_fail["result_class"] == "contract_error"
    assert "tool_contract_status" in result_fail
    assert result_fail["tool_contract_status"]["status"] == "fail"

    # 2. Validation Pass
    result_pass = execute_tool_call({"name": "math_tool", "arguments": {"value": 42}}, sandbox)
    assert result_pass["exit_code"] == 0
    assert "tool_contract_status" in result_pass
    assert result_pass["tool_contract_status"]["status"] == "pass"

    # 3. Runtime Unavailable
    sandbox_no_runtime = type("_Sandbox", (), {})()
    sandbox_no_runtime.native_tool_definitions = sandbox.native_tool_definitions
    sandbox_no_runtime.native_tool_registry = {}

    result_unavail = execute_tool_call({"name": "math_tool", "arguments": {"value": 42}}, sandbox_no_runtime)
    assert result_unavail["result_class"] == "runtime_error"
    assert result_unavail["reason_code"] == "native_tool_runtime_unavailable"
    assert "tool_contract_status" in result_unavail
    assert result_unavail["tool_contract_status"]["status"] == "pass"


def test_build_receipt_includes_tool_contract_status():
    from runner.kernel_receipts import build_receipt

    validation = {
        "status": "fail",
        "schema_present": True,
        "missing_required": ["value"],
        "type_violations": [],
        "enum_violations": [],
        "unexpected_keys": [],
    }

    receipt = build_receipt(
        receipt_id="r0001",
        action_id="run-a0001",
        action_type="native_tool_call",
        tool_name="math_tool",
        command="math_tool(value)",
        cwd="/workspace",
        exit_code=1,
        reason_code="native_tool_schema_violation",
        tool_contract_status=validation,
    )

    assert receipt["tool_contract_status"] == validation
    assert "tool_contract_status:fail" in receipt["provenance_refs"]


def test_finalization_gate_classifies_runtime_unavailable_as_invalid_environment():
    from runner.kernel_gates import _evaluate_finalization_gate

    # 1. Via native_tool_status/native_tool_state dict
    state_with_unavail_status = {
        "native_tool_state": {
            "status": "unavailable",
            "runtime_status": "native_tool_runtime_unavailable",
            "reason_codes": ["native_tool_runtime_unavailable"],
        }
    }
    eval1 = _evaluate_finalization_gate(workspace_state=state_with_unavail_status)
    assert eval1["governed_status"] == "invalid_environment"
    assert eval1["final_verdict"] == "blocked_non_promotable"
    assert "native_tool_runtime_unavailable" in eval1["reason_codes"]

    # 2. Via open obligations
    state_with_obligation = {
        "open_obligations": {
            "native_tool_runtime_unavailable": True
        }
    }
    eval2 = _evaluate_finalization_gate(workspace_state=state_with_obligation)
    assert eval2["governed_status"] == "invalid_environment"
    assert eval2["final_verdict"] == "blocked_non_promotable"
    assert "native_tool_runtime_unavailable" in eval2["reason_codes"]


def test_model_led_evidence_substrate_route():
    from runner.packet04_route_manifest import build_packet04_route_manifest
    from runner.packet04_route_manifest import get_allowed_packet04_variants

    allowed = get_allowed_packet04_variants(scope="packet06_phase6_context_completion_repair")
    assert "model_led_evidence_substrate_v1" in allowed

    manifest = build_packet04_route_manifest(
        "model_led_evidence_substrate_v1",
        scope="packet06_phase6_context_completion_repair"
    )

    assert manifest["variant_id"] == "model_led_evidence_substrate_v1"
    assert manifest["feature_flags"]["model_led_success_contract"] is True
    assert manifest["feature_flags"]["tool_contract_substrate"] is True
    assert manifest["feature_flags"]["artifact_evidence_substrate"] is True
    assert manifest["feature_flags"]["layer2_success_audit"] is True
    assert manifest["feature_flags"]["anti_benchfying_mode"] is True

    routes = {entry["runtime_key"]: entry["module_import_path"] for entry in manifest["routed_modules"]}
    assert routes["orientation"] == "runner.active_evidence_kernel:orient"
    assert routes["tools_getter"] == "runner.kernel_native_tools:get_tools"
    assert routes["tool_executor"] == "runner.kernel_native_tools:execute_tool_call"
    assert routes["execution"] == "runner.active_evidence_kernel:run_loop"
    assert routes["context"] == "runner.kernel_working_window:manage"
    assert routes["verification"] == "runner.kernel_gates:check"
    assert routes["recovery"] == "runner.kernel_recovery:handle_error"
    assert routes["terminal_guard"] == "runner.active_evidence_kernel:finalize"


def test_success_contract_extraction_and_lifecycle():
    from runner.kernel_success_contract import (
        extract_success_contract,
        validate_success_contract,
        freeze_success_contract,
        propose_success_contract_revision,
    )
    from runner.kernel_state import KernelState
    from pathlib import Path

    # 1. Extraction from text JSON
    completion_text = """
    ```json
    {
      "success_contract": {
        "status": "proposed",
        "criteria": ["Deliverable A is produced", "Task completed"],
        "required_artifacts": ["output.txt"],
        "required_checks": ["verify_output"]
      }
    }
    ```
    """
    contract = extract_success_contract(completion_text)
    assert contract is not None
    assert contract["criteria"] == ["Deliverable A is produced", "Task completed"]

    # 2. Validation
    validation = validate_success_contract(contract)
    assert validation["status"] == "accepted"

    # 3. Freeze & Revision Proposed
    state = KernelState(
        run_id="run-01",
        task_id="task-01",
        workspace_root=Path("/workspace"),
        cwd="/workspace",
        task_prompt="Produce deliverable A.",
    )

    frozen = freeze_success_contract(
        state=state,
        contract=contract,
        receipt_id="r0001",
        evidence_refs=["r0001"]
    )
    assert state.success_contract["status"] == "frozen"
    assert state.success_contract["revision"] == 0
    assert state.success_contract["criteria"] == ["Deliverable A is produced", "Task completed"]

    # Propose revision
    revised_contract = {
        "status": "proposed",
        "criteria": ["Deliverable A is produced", "Task completed", "Deliverable B is produced"],
        "required_artifacts": ["output.txt", "output_b.txt"],
        "required_checks": ["verify_output"]
    }
    proposal = propose_success_contract_revision(
        state=state,
        proposed=revised_contract,
        receipt_id="r0002",
        evidence_refs=["r0002"]
    )
    assert proposal["status"] == "accepted"
    assert state.success_contract["status"] == "revised"
    assert state.success_contract["revision"] == 1
    assert len(state.success_contract_history) == 1
    assert state.success_contract_history[0]["revision"] == 0


def test_layer2_success_audit_consistency():
    from runner.kernel_success_contract import audit_success_contract_consistency

    # 1. Matching
    success_contract = {
        "status": "frozen",
        "criteria": ["Deliverable A is produced"],
        "required_artifacts": ["output.txt"],
        "required_checks": ["verify_output"]
    }
    final_state = {
        "task_prompt": "Produce deliverable A.",
        "success_contract": success_contract,
        "artifact_refs": ["output.txt"],
        "verifier_checks": ["verify_output"]
    }
    audit = audit_success_contract_consistency(
        task_prompt="Produce deliverable A.",
        success_contract=success_contract,
        final_state=final_state,
    )
    assert audit["status"] == "pass"

    # 2. Mismatching artifact
    final_state_bad = {
        "task_prompt": "Produce deliverable A.",
        "success_contract": success_contract,
        "artifact_refs": ["wrong.txt"],
        "verifier_checks": ["verify_output"]
    }
    audit_bad = audit_success_contract_consistency(
        task_prompt="Produce deliverable A.",
        success_contract=success_contract,
        final_state=final_state_bad,
    )
    assert audit_bad["status"] == "fail"
    assert "required_artifacts" in audit_bad["mismatches"]


def test_anti_benchfying_and_layer2_audit_in_finalize(tmp_path):
    from runner.kernel_state import KernelState
    from runner.active_evidence_kernel import ActiveEvidenceKernel

    state = KernelState(
        run_id="run-01",
        task_id="task-01",
        workspace_root=tmp_path,
        cwd=str(tmp_path),
        task_prompt="Task description",
    )
    state.success_contract = {
        "status": "frozen",
        "criteria": ["Deliverable"],
        "required_artifacts": ["out.txt"],
        "required_checks": []
    }

    # Write artifact file
    out_file = tmp_path / "out.txt"
    out_file.write_text("This contains clean output.")

    state.artifact_registry = {
        "out.txt": {
            "path": str(out_file),
            "exists": True,
            "sha256": "9b1c7b8d43d1a5c6d328b9d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4",
            "freshness": "generated",
        }
    }

    # Enable flags via route_manifest
    route_manifest = {
        "feature_flags": {
            "layer2_success_audit": True,
            "anti_benchfying_mode": True,
        }
    }
    kernel = ActiveEvidenceKernel(state=state, route_manifest=route_manifest)
    
    # 1. Test Passing Case
    workspace_state = {
        "verified": True,
        "verifier_status": {"status": "pass", "reason_codes": []},
        "artifact_status": {"status": "pass", "reason_codes": []},
        "provenance_status": {"status": "pass", "reason_codes": []},
    }
    execution_result = {"status": "completed", "workspace_state": workspace_state}

    res = kernel.finalize(execution_result=execution_result, workspace_state=workspace_state, verified=True)
    assert res["status"] == "governed_pass"
    assert "layer2_audit_state" in res
    assert res["layer2_audit_state"]["status"] == "pass"

    # 2. Test Anti-benchfying failure (leakage in artifact)
    out_file.write_text("This contains a hidden:// link or other forbidden benchmark data.")
    res_leak = kernel.finalize(execution_result=execution_result, workspace_state=workspace_state, verified=True)
    assert res_leak["governed_status"] == "artifact_gate_failed"
    assert "forbidden_marker_detected" in res_leak["reason_codes"]


def test_layer2_success_audit_failure_blocks_finalize_and_preserves_reason_codes(tmp_path):
    from runner.kernel_state import KernelState
    from runner.active_evidence_kernel import ActiveEvidenceKernel

    state = KernelState(
        run_id="run-02",
        task_id="task-02",
        workspace_root=tmp_path,
        cwd=str(tmp_path),
        task_prompt="Task description",
    )
    state.success_contract = {
        "status": "frozen",
        "criteria": ["Deliverable"],
        "required_artifacts": ["out.txt"],
        "required_checks": [],
    }

    wrong_file = tmp_path / "wrong.txt"
    wrong_file.write_text("This file is not the required deliverable.")
    state.artifact_registry = {
        "wrong.txt": {
            "path": str(wrong_file),
            "exists": True,
            "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
            "freshness": "generated",
        }
    }

    route_manifest = {
        "feature_flags": {
            "layer2_success_audit": True,
        }
    }
    kernel = ActiveEvidenceKernel(state=state, route_manifest=route_manifest)
    workspace_state = {
        "verified": True,
        "verifier_status": {"status": "pass", "reason_codes": [], "output_summary": "ok"},
        "artifact_status": {"status": "pass", "reason_codes": [], "output_summary": ""},
        "provenance_status": {"status": "pass", "reason_codes": [], "output_summary": ""},
        "verifier_artifact_present": True,
        "open_obligations": {},
    }
    execution_result = {"status": "completed", "workspace_state": workspace_state}

    res = kernel.finalize(execution_result=execution_result, workspace_state=workspace_state, verified=True)

    assert res["governed_status"] == "ungoverned_model_claim"
    assert res["final_verdict"] == "unresolved"
    assert "layer2_audit_failed" in res["reason_codes"]
    assert "missing_required_artifacts" in res["reason_codes"]
    assert res["layer2_audit_state"]["status"] == "fail"
    assert res["layer2_audit_state"]["verdict"] == "FAIL"


def test_model_led_additional_repairs(tmp_path):
    from runner.kernel_state import KernelState
    from runner.kernel_context_pack import build_context_pack, render_context_pack
    from runner.kernel_gates import _evaluate_finalization_gate

    # 1. Test slicing skip
    state = KernelState(
        run_id="run-01",
        task_id="task-01",
        workspace_root=tmp_path,
        cwd=str(tmp_path),
        task_prompt="A" * 7000,
    )
    state.model_led_evidence_substrate_active = True
    
    pack = build_context_pack(state)
    rendered = render_context_pack(pack)
    assert len(rendered) > 6000
    assert not rendered.endswith("…")

    # 2. Test success_contract_missing obligation
    state.model_led_success_contract_active = True
    state.success_contract = {"status": "not_declared"}
    obligations = state.refresh_open_obligations()
    assert "success_contract_missing" in obligations

    # 3. Test blocking governed_pass when success_contract_missing in open_obligations
    eval_res = _evaluate_finalization_gate(
        workspace_state={
            "active_kernel_state": state.to_dict(),
            "open_obligations": {"success_contract_missing": True},
            "verified": True,
            "model_claimed_done": True,
            "artifact_status": {"status": "pass"},
            "verifier_status": {"status": "pass"},
            "provenance_status": {"status": "pass"},
        }
    )
    assert eval_res["governed_status"] == "ungoverned_model_claim"
    assert "success_contract_missing" in eval_res["reason_codes"]

    # 4. Test blocking governed_pass when layer2 audit failed
    eval_res_layer2 = _evaluate_finalization_gate(
        workspace_state={
            "route_manifest": {"feature_flags": {"layer2_success_audit": True}},
            "active_kernel_state": {
                "layer2_audit_state": {"verdict": "FAIL"}
            },
            "verified": True,
            "model_claimed_done": True,
            "artifact_status": {"status": "pass"},
            "verifier_status": {"status": "pass"},
            "provenance_status": {"status": "pass"},
        }
    )
    assert eval_res_layer2["governed_status"] == "ungoverned_model_claim"
    assert "layer2_audit_failed" in eval_res_layer2["reason_codes"]



