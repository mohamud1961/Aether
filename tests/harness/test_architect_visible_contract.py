from __future__ import annotations

import json

import pytest

from aether.compiler import CapabilityRegistry, ConfigCompiler
from aether.runtime_ir import CapabilityDescriptor, EnvMap
from aether.workbench_compile import harness_config_to_runtime_ir
from aether.workbench_config import parse_harness_config_ir


def _payload() -> dict:
    return {
        "schema_version": "harness_config.v1",
        "task_understanding": "Implement the visible interface.",
        "visible_contract": [
            {"kind": "owned_symbol", "owner": "GetValResponse", "literal": "val", "exact_type": "int32", "meaning": "response field", "contrast_owner": "SetValRequest", "contrast": "value"},
            {"kind": "owned_symbol", "owner": "SetValRequest", "literal": "value", "exact_type": "int32", "meaning": "request field", "contrast_owner": "GetValResponse", "contrast": "val"},
        ],
        "success_definition": "The visible interface is implemented exactly.",
        "solver_system_prompt": {"role": "interface solver", "workflow": ["inspect", "implement", "verify"], "self_verification": ["compare exact public signatures"], "memory_use": ["reuse fresh evidence"], "stop_conditions": ["submit after exact comparison"], "avoid": []},
        "verifier_system_prompt": {"role": "interface verifier", "success_criteria": ["exact interface"], "required_evidence": ["direct signature inspection"], "false_positive_traps": ["self-consistent wrong field"], "verdict_guidance": ["complete when exact", "repair when mismatched", "uncertain when uninspected"], "feedback_guidance": ["name the exact mismatch"]},
        "clause_coverage": [{"clause_id": "interface", "solver_handling": "preserve exact fields", "verifier_check": "compare exact fields"}],
        "verifier_strategy": {"clause_checks": [{"clause_id": "interface", "inspection_route": "read_file:contract.proto", "fallback_route": None, "falsification_check": "field names differ", "required_evidence_class": "exact_contract"}], "false_positive_traps": ["same-method round trip"], "return_all_findings": True},
        "evidence_requirements": ["exact public interface"],
        "false_positive_risks": ["val/value substitution"],
        "minimum_completion_evidence": ["direct contract comparison"],
        "re_derivable_claims": ["public field names"],
        "context_policy": {"mode": "default_bounded", "always_include": [], "include_on_failure": [], "model_context_window_tokens": 50000, "recipe": {"always_include": [], "include_recent": [], "include_last_failure": 1, "preserve_exact": [], "make_queryable_not_inline": []}},
        "memory_policy": {"automatic_repeat_mode": "advisory"},
        "verification_policy": {"visible_smoke_tests": []},
        "model_verifier_policy": {"enabled": True, "runs_on": ["solver_submit"]},
        "helper_script_policy": {"enabled": True, "directory": "/app/.aether_tools"},
        "local_verification_limits": ["local checks are not official truth"],
        "expected_steps": 6,
    }


def _env() -> EnvMap:
    return EnvMap(task_prompt="Implement the visible interface.", workspace_root="/app", capabilities={"filesystem": CapabilityDescriptor("filesystem", "files", tool_names=("read_file", "write_file"))})


def test_visible_contract_parses_and_compiles_to_prominent_solver_section() -> None:
    config = parse_harness_config_ir(json.dumps(_payload()), require_semantic_contract=True)
    assert [row.required_binding for row in config.visible_contract] == ["GetValResponse.val", "SetValRequest.value"]
    assert all(row.kind == "owned_symbol" for row in config.visible_contract)
    assert [row.exact_type for row in config.visible_contract] == ["int32", "int32"]
    ir = harness_config_to_runtime_ir(config, _env())
    assert ir.visible_contract[0]["owner"] == "GetValResponse"
    assert ir.visible_contract[0]["literal"] == "val"
    compiled = ConfigCompiler(CapabilityRegistry.from_envmap(_env())).compile(ir, _env())
    sections = dict(compiled.stable_prefix_sections)
    ledger = json.loads(sections["architect_visible_contract"])
    assert ledger[0]["owner"] == "GetValResponse"
    assert ledger[0]["literal"] == "val"
    assert ledger[0]["exact_type"] == "int32"
    assert ledger[0]["contrast_owner"] == "SetValRequest"
    assert ledger[0]["contrast"] == "value"
    assert compiled.config_realization["visible_contract"] == ledger
    assert "architect_visible_contract" in compiled.config_realization["rendered_sections"]


def test_visible_contract_rejects_empty_literal_or_meaning() -> None:
    payload = _payload()
    payload["visible_contract"] = [{"kind": "literal", "literal": "", "meaning": "field", "contrast": ""}]
    with pytest.raises(Exception, match="literal is required"):
        parse_harness_config_ir(json.dumps(payload), require_semantic_contract=True)
    payload["visible_contract"] = [{"kind": "literal", "literal": "field", "meaning": "", "contrast": ""}]
    with pytest.raises(Exception, match="meaning is required"):
        parse_harness_config_ir(json.dumps(payload), require_semantic_contract=True)


def test_historical_config_without_ledger_remains_byte_shape_compatible() -> None:
    payload = _payload()
    payload.pop("visible_contract")
    config = parse_harness_config_ir(json.dumps(payload), require_semantic_contract=True)
    assert config.visible_contract == ()
    assert "visible_contract" not in config.as_dict()


def test_legacy_visible_contract_rows_remain_readable_but_normalize_to_literal_kind() -> None:
    payload = _payload()
    payload["visible_contract"] = [{"literal": "legacy.txt", "meaning": "legacy path", "contrast": ""}]
    config = parse_harness_config_ir(json.dumps(payload), require_semantic_contract=True)
    assert config.visible_contract[0].kind == "literal"
    assert config.visible_contract[0].as_dict() == {
        "kind": "literal", "literal": "legacy.txt", "meaning": "legacy path", "contrast": "",
    }


def test_owned_symbol_contract_rejects_missing_type_and_conflicting_duplicate() -> None:
    payload = _payload()
    row = dict(payload["visible_contract"][0])
    row["exact_type"] = ""
    payload["visible_contract"] = [row]
    with pytest.raises(Exception, match="exact_type is required"):
        parse_harness_config_ir(json.dumps(payload), require_semantic_contract=True)

    payload = _payload()
    conflicting = dict(payload["visible_contract"][0])
    conflicting["exact_type"] = "string"
    payload["visible_contract"].append(conflicting)
    with pytest.raises(Exception, match="conflicts with an earlier binding"):
        parse_harness_config_ir(json.dumps(payload), require_semantic_contract=True)


def test_repeated_legacy_literal_with_distinct_meanings_remains_compatible() -> None:
    payload = _payload()
    payload["visible_contract"] = [
        {"literal": "key", "meaning": "Get request string field", "contrast": ""},
        {"literal": "key", "meaning": "Set request string field", "contrast": ""},
        {"literal": "key", "meaning": "Get request string field", "contrast": ""},
    ]
    config = parse_harness_config_ir(json.dumps(payload), require_semantic_contract=True)
    assert len(config.visible_contract) == 2
    assert [row.meaning for row in config.visible_contract] == [
        "Get request string field", "Set request string field",
    ]
    assert all(row.kind == "literal" for row in config.visible_contract)
    assert all(row.as_dict()["kind"] == "literal" for row in config.visible_contract)


def test_explicit_literal_rows_may_repeat_token_but_owned_symbol_conflicts_fail() -> None:
    payload = _payload()
    payload["visible_contract"] = [
        {"kind": "literal", "literal": "key", "meaning": "first unowned role", "contrast": ""},
        {"kind": "literal", "literal": "key", "meaning": "second unowned role", "contrast": ""},
    ]
    config = parse_harness_config_ir(json.dumps(payload), require_semantic_contract=True)
    assert len(config.visible_contract) == 2

    payload = _payload()
    conflicting = dict(payload["visible_contract"][0])
    conflicting["exact_type"] = "string"
    payload["visible_contract"].append(conflicting)
    with pytest.raises(Exception, match="conflicts with an earlier binding"):
        parse_harness_config_ir(json.dumps(payload), require_semantic_contract=True)
