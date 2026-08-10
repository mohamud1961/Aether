from __future__ import annotations

import json

import pytest

from aether.architect_output_schema import HARNESS_CONFIG_V1_PROVIDER_SCHEMA
from aether.compiler import CapabilityRegistry, ConfigCompiler
from aether.runtime_ir import CapabilityDescriptor, EnvMap
from aether.runtime_manual import SUPPORTED_SYNTAX_CHECK_LANGUAGES, build_runtime_manual
from aether.smoke_compile import compile_visible_smoke_tests
from aether.workbench_compile import harness_config_to_runtime_ir
from aether.workbench_config import parse_harness_config_ir
from aether.workbench_prompt import WORKBENCH_ARCHITECT_SYSTEM_PROMPT
from tests.harness.test_architect_structured_output import _canonical_config


def _env() -> EnvMap:
    return EnvMap(
        task_prompt="Create /app/server.py.",
        workspace_root="/app",
        capabilities={
            "filesystem": CapabilityDescriptor("filesystem", "files", tool_names=("read_file", "write_file")),
            "shell": CapabilityDescriptor("shell", "shell", tool_names=("run_command",)),
        },
        task_metadata={
            "environment_probe": {
                "validation_guidance": {"preferred_python": "python3"},
            }
        },
    )


def test_prompt_requires_separate_owner_and_requirement_bindings() -> None:
    prompt = WORKBENCH_ARCHITECT_SYSTEM_PROMPT
    assert "state literal, owner, and requirement" in prompt
    assert "Owner and requirement are independent" in prompt
    assert "use owner=null for standalone facts" in prompt
    assert "requirement=null unless the task states an exact constraint" in prompt
    assert "Put categories in meaning" in prompt
    assert "Row kind is derived" in prompt
    assert '"owner":null,"requirement":null' in prompt
    assert '"owner":"Service","requirement":null' in prompt
    assert '"owner":"Message","requirement":"task type"' in prompt
    rule_at = prompt.index("state literal, owner, and requirement")
    shape_at = prompt.index('"visible_contract": [')
    assert 0 < shape_at - rule_at < 600
    assert len(prompt) <= 15_000


def test_provider_schema_exposes_uniform_binding_contract_at_generation_boundary() -> None:
    visible = HARNESS_CONFIG_V1_PROVIDER_SCHEMA["properties"]["visible_contract"]
    assert "optional immediate ownership" in visible["description"]
    assert "optional exact type/version/format/cardinality requirements" in visible["description"]
    assert "does not choose an internal row kind" in visible["description"]
    item = visible["items"]
    assert item["type"] == "object"
    assert item["additionalProperties"] is False
    assert set(item["required"]) == set(item["properties"])
    assert set(item["properties"]) == {
        "literal", "owner", "requirement", "meaning", "contrast", "contrast_owner"
    }
    props = item["properties"]
    assert "unqualified" in props["literal"]["description"]
    assert "Never include an owner prefix" in props["literal"]["description"]
    assert "immediate semantic owner" in props["owner"]["description"]
    assert "Ownership does not imply a data type" in props["owner"]["description"]
    assert "Exact task-stated type, version, format, or cardinality" in props["requirement"]["description"]
    assert "independent of owner" in props["requirement"]["description"]
    assert "Entity categories" in props["requirement"]["description"]
    assert "meanings, not requirements" in props["requirement"]["description"]
    assert "false/lookalike" in props["contrast"]["description"]
    evidence_description = HARNESS_CONFIG_V1_PROVIDER_SCHEMA["properties"]["verifier_strategy"]["properties"]["clause_checks"]["items"]["properties"]["required_evidence_class"]["description"]
    assert "behavioral for a fresh public-interface operation with observed response" in evidence_description
    assert "Shape or liveness proxies cannot prove behavior" in evidence_description
    for field in ("owner", "requirement", "contrast_owner"):
        assert props[field]["anyOf"][0]["type"] == "string"
        assert props[field]["anyOf"][0]["minLength"] == 1
        assert props[field]["anyOf"][1] == {"type": "null"}


def test_runtime_manual_and_provider_schema_share_syntax_language_inventory() -> None:
    manual = build_runtime_manual()
    assert manual["verification"]["supported_syntax_check_languages"] == list(SUPPORTED_SYNTAX_CHECK_LANGUAGES)
    syntax_schema = HARNESS_CONFIG_V1_PROVIDER_SCHEMA["properties"]["verification_policy"]["properties"]["visible_smoke_tests"]["items"]["anyOf"][2]
    language = syntax_schema["properties"]["language"]["anyOf"][0]
    assert language["enum"] == list(SUPPORTED_SYNTAX_CHECK_LANGUAGES)


def test_python3_syntax_check_parses_and_compiles_without_quarantine() -> None:
    payload = _canonical_config()
    payload["verification_policy"]["visible_smoke_tests"] = [
        {"type": "syntax_check", "path": "/app/server.py", "language": "python3"}
    ]
    config = parse_harness_config_ir(json.dumps(payload), require_semantic_contract=True)
    result = compile_visible_smoke_tests(config, _env())
    assert not result.rejected
    assert len(result.checks) == 1
    assert result.checks[0].command.startswith("python3 -m py_compile")
    ir = harness_config_to_runtime_ir(config, _env())
    compiled = ConfigCompiler(CapabilityRegistry.from_envmap(_env())).compile(ir, _env())
    assert compiled.config_realization["checks_compiled"]


def test_unsupported_syntax_language_fails_before_compilation() -> None:
    payload = _canonical_config()
    payload["verification_policy"]["visible_smoke_tests"] = [
        {"type": "syntax_check", "path": "/app/server.rb", "language": "ruby"}
    ]
    with pytest.raises(Exception, match="unsupported syntax_check language"):
        parse_harness_config_ir(json.dumps(payload), require_semantic_contract=True)


def test_provider_schema_rejects_empty_uniform_values_and_parser_rejects_half_bindings() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    visible = HARNESS_CONFIG_V1_PROVIDER_SCHEMA["properties"]["visible_contract"]
    validator = jsonschema.Draft202012Validator(visible)

    valid_typed_no_contrast = [{
        "literal": "timeout_ms",
        "owner": "Config",
        "requirement": "int",
        "meaning": "Timeout field.",
        "contrast": "",
        "contrast_owner": None,
    }]
    valid_typed_contrast = [{
        "literal": "timeout_ms",
        "owner": "Config",
        "requirement": "int",
        "meaning": "Timeout field.",
        "contrast": "timeout",
        "contrast_owner": "Config",
    }]
    validator.validate(valid_typed_no_contrast)
    validator.validate(valid_typed_contrast)

    for field in ("literal", "owner", "requirement", "meaning"):
        invalid = [dict(valid_typed_no_contrast[0])]
        invalid[0][field] = ""
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(invalid)

    payload = _canonical_config()
    payload["visible_contract"] = [{
        **valid_typed_no_contrast[0],
        "contrast_owner": "Config",
        "contrast": "",
    }]
    with pytest.raises(Exception, match="contrast_owner requires a non-empty contrast"):
        parse_harness_config_ir(json.dumps(payload), require_semantic_contract=True)

    payload["visible_contract"] = [{
        **valid_typed_no_contrast[0],
        "contrast_owner": None,
        "contrast": "timeout",
    }]
    parsed = parse_harness_config_ir(json.dumps(payload), require_semantic_contract=True)
    assert parsed.visible_contract[0].contrast == "timeout"
    assert parsed.visible_contract[0].contrast_owner == ""

    payload["visible_contract"] = [{
        "literal": "python", "owner": None, "requirement": "3.12",
        "meaning": "runtime version", "contrast": "", "contrast_owner": None,
    }]
    constrained = parse_harness_config_ir(json.dumps(payload), require_semantic_contract=True)
    assert constrained.visible_contract[0].kind == "constrained_literal"
    assert constrained.visible_contract[0].exact_type == "3.12"


def test_provider_schema_rejects_empty_required_standalone_fields() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    visible = HARNESS_CONFIG_V1_PROVIDER_SCHEMA["properties"]["visible_contract"]
    validator = jsonschema.Draft202012Validator(visible)
    row = {
        "literal": "/app/config.yaml",
        "owner": None,
        "requirement": None,
        "meaning": "Required configuration path.",
        "contrast": "",
        "contrast_owner": None,
    }
    validator.validate([row])
    for field in ("literal", "meaning"):
        invalid = [dict(row)]
        invalid[0][field] = ""
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(invalid)



def test_provider_schema_route_prefixes_match_parser_inventory() -> None:
    import re
    import jsonschema
    from aether.proof_contract import ROUTE_EVIDENCE_CEILINGS

    item = HARNESS_CONFIG_V1_PROVIDER_SCHEMA["properties"]["verifier_strategy"]["properties"]["clause_checks"]["items"]
    route = item["properties"]["inspection_route"]
    pattern = re.compile(route["pattern"])
    for kind in ROUTE_EVIDENCE_CEILINGS:
        assert pattern.fullmatch(f"{kind}:target")
    assert not pattern.fullmatch("probe_service:5328")
    validator = jsonschema.Draft202012Validator(item)
    valid = {
        "clause_id": "live",
        "inspection_route": "overlay_run_command:python3",
        "fallback_route": "probe_port:5328",
        "falsification_check": "The behavior fails.",
        "proof_obligation": "public_behavior",
        "required_evidence_class": "behavioral",
    }
    validator.validate(valid)
    invalid = dict(valid, inspection_route="probe_service:5328")
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(invalid)
    invalid_fallback = dict(valid, fallback_route="probe_service:5328")
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(invalid_fallback)
