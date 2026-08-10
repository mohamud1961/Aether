from __future__ import annotations

import copy
import json

import pytest

from aether.architect_output_schema import HARNESS_CONFIG_V1_PROVIDER_SCHEMA
from aether.workbench_config import parse_harness_config_ir
from aether.workbench_prompt import WORKBENCH_ARCHITECT_SYSTEM_PROMPT
from tests.harness.test_architect_structured_output import _canonical_config


_REMOVED_MIRRORS = {
    "task_understanding",
    "success_definition",
    "evidence_requirements",
    "false_positive_risks",
    "minimum_completion_evidence",
    "local_verification_limits",
}


def test_provider_contract_is_reduced_and_contract_first() -> None:
    properties = list(HARNESS_CONFIG_V1_PROVIDER_SCHEMA["properties"])
    assert properties == [
        "schema_version", "visible_contract", "clause_coverage", "verifier_strategy",
        "solver_system_prompt", "verifier_system_prompt", "re_derivable_claims",
        "context_policy", "memory_policy", "verification_policy",
        "model_verifier_policy", "helper_script_policy", "expected_steps",
    ]
    assert set(HARNESS_CONFIG_V1_PROVIDER_SCHEMA["required"]) == set(properties)
    assert _REMOVED_MIRRORS.isdisjoint(properties)
    assert properties.index("visible_contract") < properties.index("solver_system_prompt")
    assert properties.index("clause_coverage") < properties.index("solver_system_prompt")
    assert properties.index("verifier_strategy") < properties.index("verifier_system_prompt")


def test_reduced_payload_mechanically_projects_legacy_runtime_views() -> None:
    raw = _canonical_config()
    parsed = parse_harness_config_ir(json.dumps(raw), require_semantic_contract=True)
    assert parsed.task_understanding == raw["solver_system_prompt"]["role"]
    assert parsed.success_definition == raw["clause_coverage"][0]["verifier_check"]
    assert parsed.evidence_requirements == tuple(raw["verifier_system_prompt"]["required_evidence"])
    assert parsed.minimum_completion_evidence == tuple(raw["verifier_system_prompt"]["required_evidence"])
    assert parsed.false_positive_risks == (
        *raw["verifier_system_prompt"]["false_positive_traps"],
        *raw["verifier_strategy"]["false_positive_traps"],
    )
    assert parsed.local_verification_limits == ()


def test_historical_explicit_mirrors_remain_authoritative_and_byte_stable() -> None:
    reduced = _canonical_config()
    historical = copy.deepcopy(reduced)
    historical.update({
        "task_understanding": "Historical exact understanding.",
        "success_definition": "Historical exact completion definition.",
        "evidence_requirements": ["Historical evidence requirement."],
        "false_positive_risks": ["Historical false-positive risk."],
        "minimum_completion_evidence": ["Historical minimum evidence."],
        "local_verification_limits": ["Historical local limit."],
    })
    parsed = parse_harness_config_ir(json.dumps(historical), require_semantic_contract=True)
    assert parsed.task_understanding == historical["task_understanding"]
    assert parsed.success_definition == historical["success_definition"]
    assert parsed.evidence_requirements == tuple(historical["evidence_requirements"])
    assert parsed.false_positive_risks == tuple(historical["false_positive_risks"])
    assert parsed.minimum_completion_evidence == tuple(historical["minimum_completion_evidence"])
    assert parsed.local_verification_limits == tuple(historical["local_verification_limits"])


def test_reduced_payload_matches_strict_provider_schema() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    jsonschema.Draft202012Validator(HARNESS_CONFIG_V1_PROVIDER_SCHEMA).validate(_canonical_config())


def test_prompt_declares_one_authority_and_removed_mirrors_are_not_shape_fields() -> None:
    prompt = WORKBENCH_ARCHITECT_SYSTEM_PROMPT
    assert "visible_contract is the sole exact identity/owner/requirement/contrast authority" in prompt
    assert "clause_coverage plus verifier_strategy are the sole completion/proof authority" in prompt
    assert "Do not emit compatibility mirrors" in prompt
    for field in _REMOVED_MIRRORS:
        assert f'"{field}":' not in prompt
    assert prompt.index('"visible_contract": [') < prompt.index('"solver_system_prompt": {')
    assert prompt.index('"clause_coverage": [') < prompt.index('"solver_system_prompt": {')
    assert len(prompt) <= 15_000
