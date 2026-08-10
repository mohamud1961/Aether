from __future__ import annotations

import json

import pytest

from aether.architect_output_schema import HARNESS_CONFIG_V1_PROVIDER_SCHEMA
from aether.compiler import CapabilityRegistry, ConfigCompiler
from aether.runtime_ir import CapabilityDescriptor, EnvMap
from aether.workbench_compile import harness_config_to_runtime_ir
from aether.workbench_config import parse_harness_config_ir
from tests.harness.test_architect_structured_output import _canonical_config


def _env() -> EnvMap:
    return EnvMap(
        task_prompt="Implement the visible interface.",
        workspace_root="/app",
        capabilities={
            "filesystem": CapabilityDescriptor(
                "filesystem", "files", tool_names=("read_file", "write_file")
            )
        },
    )


def test_provider_binding_row_is_one_uniform_closed_object() -> None:
    item = HARNESS_CONFIG_V1_PROVIDER_SCHEMA["properties"]["visible_contract"]["items"]
    assert item["type"] == "object"
    assert item["additionalProperties"] is False
    assert list(item["properties"]) == [
        "literal", "owner", "requirement", "meaning", "contrast", "contrast_owner"
    ]
    assert set(item["required"]) == set(item["properties"])
    assert "kind" not in item["properties"]
    assert "exact_type" not in item["properties"]


def test_uniform_rows_project_standalone_scoped_and_typed_bindings() -> None:
    raw = _canonical_config()
    raw["visible_contract"] = [
        {
            "literal": "/app/service.proto", "owner": None, "requirement": None,
            "meaning": "source path", "contrast": "", "contrast_owner": None,
        },
        {
            "literal": "GetVal", "owner": "KVStore", "requirement": None,
            "meaning": "read RPC", "contrast": "SetVal", "contrast_owner": "KVStore",
        },
        {
            "literal": "value", "owner": "SetValRequest", "requirement": "int",
            "meaning": "stored value field", "contrast": "val", "contrast_owner": "SetValRequest",
        },
    ]
    parsed = parse_harness_config_ir(json.dumps(raw), require_semantic_contract=True)
    assert [row.kind for row in parsed.visible_contract] == [
        "literal", "scoped_symbol", "owned_symbol"
    ]
    assert [row.required_binding for row in parsed.visible_contract] == [
        "/app/service.proto", "KVStore.GetVal", "SetValRequest.value"
    ]
    assert parsed.visible_contract[1].exact_type == ""
    assert parsed.visible_contract[2].exact_type == "int"
    ir = harness_config_to_runtime_ir(parsed, _env())
    assert ir.visible_contract[1] == {
        "kind": "scoped_symbol", "owner": "KVStore", "literal": "GetVal",
        "meaning": "read RPC", "contrast_owner": "KVStore", "contrast": "SetVal",
    }
    compiled = ConfigCompiler(CapabilityRegistry.from_envmap(_env())).compile(ir, _env())
    ledger = json.loads(dict(compiled.stable_prefix_sections)["architect_visible_contract"])
    assert ledger == list(ir.visible_contract)


def test_uniform_row_supports_independent_requirement_and_rejects_contrast_owner_without_owner() -> None:
    raw = _canonical_config()
    raw["visible_contract"] = [{
        "literal": "grpcio", "owner": None, "requirement": "1.73.0",
        "meaning": "python package", "contrast": "", "contrast_owner": None,
    }]
    parsed = parse_harness_config_ir(json.dumps(raw), require_semantic_contract=True)
    assert parsed.visible_contract[0].kind == "constrained_literal"
    assert parsed.visible_contract[0].exact_type == "1.73.0"
    assert parsed.visible_contract[0].as_dict() == {
        "kind": "constrained_literal", "literal": "grpcio", "exact_type": "1.73.0",
        "meaning": "python package", "contrast": "",
    }

    raw["visible_contract"] = [{
        "literal": "thing", "owner": None, "requirement": None,
        "meaning": "standalone thing", "contrast": "other", "contrast_owner": "Owner",
    }]
    with pytest.raises(Exception, match="contrast_owner requires an immediate owner"):
        parse_harness_config_ir(json.dumps(raw), require_semantic_contract=True)


def test_uniform_rows_cover_all_owner_requirement_combinations() -> None:
    raw = _canonical_config()
    raw["visible_contract"] = [
        {"literal": "path", "owner": None, "requirement": None, "meaning": "path", "contrast": "", "contrast_owner": None},
        {"literal": "pkg", "owner": None, "requirement": "1.2.3", "meaning": "package", "contrast": "", "contrast_owner": None},
        {"literal": "Method", "owner": "Service", "requirement": None, "meaning": "operation", "contrast": "", "contrast_owner": None},
        {"literal": "field", "owner": "Message", "requirement": "string", "meaning": "field", "contrast": "", "contrast_owner": None},
    ]
    parsed = parse_harness_config_ir(json.dumps(raw), require_semantic_contract=True)
    assert [row.kind for row in parsed.visible_contract] == [
        "literal", "constrained_literal", "scoped_symbol", "owned_symbol"
    ]


def test_historical_kind_rows_remain_readable() -> None:
    raw = _canonical_config()
    raw["visible_contract"] = [
        {"kind": "literal", "literal": "legacy.txt", "meaning": "legacy path", "contrast": ""},
        {
            "kind": "owned_symbol", "owner": "Message", "literal": "field",
            "exact_type": "string", "meaning": "typed field",
            "contrast_owner": "", "contrast": "",
        },
        {
            "kind": "scoped_symbol", "owner": "Service", "literal": "Method",
            "meaning": "untyped operation", "contrast_owner": "", "contrast": "",
        },
    ]
    parsed = parse_harness_config_ir(json.dumps(raw), require_semantic_contract=True)
    assert [row.kind for row in parsed.visible_contract] == [
        "literal", "owned_symbol", "scoped_symbol"
    ]


def test_uniform_scoped_required_and_contrast_bindings_must_differ() -> None:
    raw = _canonical_config()
    raw["visible_contract"] = [{
        "literal": "Method", "owner": "Service", "requirement": None,
        "meaning": "service operation", "contrast": "Method", "contrast_owner": "Service",
    }]
    with pytest.raises(Exception, match="required and contrast bindings must differ"):
        parse_harness_config_ir(json.dumps(raw), require_semantic_contract=True)


def test_scoped_uniform_row_allows_standalone_contrast() -> None:
    raw = _canonical_config()
    raw["visible_contract"] = [{
        "literal": "KV store", "owner": "Server", "requirement": "Python dict",
        "meaning": "storage", "contrast": "database", "contrast_owner": None,
    }]
    parsed = parse_harness_config_ir(json.dumps(raw), require_semantic_contract=True)
    row = parsed.visible_contract[0]
    assert row.kind == "owned_symbol"
    assert row.owner == "Server"
    assert row.exact_type == "Python dict"
    assert row.contrast == "database"
    assert row.contrast_owner == ""


def test_uniform_row_rejects_contrast_owner_without_contrast() -> None:
    raw = _canonical_config()
    raw["visible_contract"] = [{
        "literal": "Method", "owner": "Service", "requirement": None,
        "meaning": "operation", "contrast": "", "contrast_owner": "Service",
    }]
    with pytest.raises(Exception, match="contrast_owner requires a non-empty contrast"):
        parse_harness_config_ir(json.dumps(raw), require_semantic_contract=True)
