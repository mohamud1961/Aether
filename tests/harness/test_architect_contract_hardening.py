from __future__ import annotations

import json

import pytest

from aether.architect_input import build_architect_runtime_contract
from aether.model_hooks import ModelOutputError
from aether.workbench_config import parse_harness_config_ir
from aether.workbench_hooks import WorkbenchArchitect


def _base_config() -> dict[str, object]:
    return {
        "schema_version": "harness_config.v1",
        "task_understanding": "Create the requested output artifact.",
        "success_definition": "The artifact satisfies every visible requirement.",
        "solver_system_prompt": {
            "role": "Task-specific solver",
            "workflow": ["inspect", "build", "verify", "submit"],
            "self_verification": ["inspect current state and run an independent check"],
            "memory_use": ["use prior receipts before repeating actions"],
            "stop_conditions": ["submit only after fresh evidence supports every clause"],
            "avoid": ["do not treat existence alone as semantic correctness"],
        },
        "verifier_system_prompt": {
            "role": "Read-only task-state verifier",
            "success_criteria": ["the requested artifact is correct"],
            "required_evidence": ["current direct artifact evidence"],
            "false_positive_traps": ["shape-only success"],
            "verdict_guidance": ["completed requires current evidence"],
            "feedback_guidance": ["name the concrete missing evidence or repair"],
        },
        "evidence_requirements": ["current artifact state"],
        "false_positive_risks": ["an artifact may exist but be semantically wrong"],
        "minimum_completion_evidence": ["direct current-state inspection"],
        "context_policy": {"mode": "retrieval_augmented"},
        "model_verifier_policy": {"enabled": True, "runs_on": ["solver_submit"]},
    }


def _with_semantic_contract(raw: dict[str, object]) -> dict[str, object]:
    result = json.loads(json.dumps(raw))
    result["clause_coverage"] = [
        {
            "clause_id": "artifact-correct",
            "solver_handling": "Build the artifact and validate its requested semantics.",
            "verifier_check": "Inspect the current artifact and establish semantic correctness.",
        }
    ]
    result["verifier_strategy"] = {
        "clause_checks": [
            {
                "clause_id": "artifact-correct",
                "inspection_route": "read_file:/app/out.txt",
                "fallback_route": "overlay_run_command:independent-check",
                "falsification_check": "A direct mismatch or independent countercheck disproves completion.",
                "required_evidence_class": "exact_contract",
            }
        ],
        "false_positive_traps": ["file existence alone is not semantic proof"],
        "return_all_findings": True,
    }
    return result


def _encoded(raw: dict[str, object]) -> str:
    return json.dumps(raw)


def test_legacy_capture_remains_parseable_without_semantic_contract() -> None:
    config = parse_harness_config_ir(_encoded(_base_config()))
    assert config.clause_coverage == ()
    assert config.verifier_strategy == ()


def test_production_parse_requires_complete_semantic_contract() -> None:
    with pytest.raises(ModelOutputError, match="requires non-empty clause_coverage"):
        parse_harness_config_ir(
            _encoded(_base_config()), require_semantic_contract=True
        )


def test_partial_semantic_contract_fails_closed() -> None:
    raw = _base_config()
    raw["clause_coverage"] = [
        {
            "clause_id": "artifact-correct",
            "solver_handling": "build it",
            "verifier_check": "inspect it",
        }
    ]
    with pytest.raises(ModelOutputError, match="verifier_strategy is required"):
        parse_harness_config_ir(_encoded(raw))


def test_semantic_clause_ids_must_match_exactly() -> None:
    raw = _with_semantic_contract(_base_config())
    raw["verifier_strategy"]["clause_checks"][0]["clause_id"] = "different"  # type: ignore[index]
    with pytest.raises(ModelOutputError, match="must match exactly"):
        parse_harness_config_ir(_encoded(raw), require_semantic_contract=True)


def test_semantic_clause_ids_must_be_unique() -> None:
    raw = _with_semantic_contract(_base_config())
    raw["clause_coverage"].append(dict(raw["clause_coverage"][0]))  # type: ignore[union-attr,index]
    with pytest.raises(ModelOutputError, match="clause_id values must be unique"):
        parse_harness_config_ir(_encoded(raw), require_semantic_contract=True)


def test_verifier_routes_must_be_supported() -> None:
    raw = _with_semantic_contract(_base_config())
    raw["verifier_strategy"]["clause_checks"][0]["inspection_route"] = "magic_oracle:/app/out.txt"  # type: ignore[index]
    with pytest.raises(ModelOutputError, match="unsupported verifier inspection route"):
        parse_harness_config_ir(_encoded(raw), require_semantic_contract=True)


def test_valid_semantic_contract_compiles_at_parse_boundary() -> None:
    config = parse_harness_config_ir(
        _encoded(_with_semantic_contract(_base_config())),
        require_semantic_contract=True,
    )
    assert [item.clause_id for item in config.clause_coverage] == ["artifact-correct"]
    assert [item.clause_id for item in config.verifier_strategy] == ["artifact-correct"]


def test_unsupported_top_level_context_selector_fails_closed() -> None:
    raw = _with_semantic_contract(_base_config())
    raw["context_policy"] = {
        "mode": "retrieval_augmented",
        "always_include": ["/app/out.txt"],
    }
    with pytest.raises(ModelOutputError, match="unsupported context_policy.always_include selectors"):
        parse_harness_config_ir(_encoded(raw), require_semantic_contract=True)


def test_unsupported_exact_recipe_selector_fails_closed() -> None:
    raw = _with_semantic_contract(_base_config())
    raw["context_policy"] = {
        "mode": "retrieval_augmented",
        "recipe": {"preserve_exact": ["latest client round-trip"]},
    }
    with pytest.raises(ModelOutputError, match="unsupported context_policy.recipe.preserve_exact selectors"):
        parse_harness_config_ir(_encoded(raw), require_semantic_contract=True)


def test_unsupported_recent_recipe_selector_fails_closed() -> None:
    raw = _with_semantic_contract(_base_config())
    raw["context_policy"] = {
        "mode": "retrieval_augmented",
        "recipe": {"include_recent": {"server.py": 2}},
    }
    with pytest.raises(ModelOutputError, match="unsupported context_policy.recipe.include_recent selectors"):
        parse_harness_config_ir(_encoded(raw), require_semantic_contract=True)


def test_valid_context_selector_values_are_preserved() -> None:
    raw = _with_semantic_contract(_base_config())
    raw["context_policy"] = {
        "mode": "retrieval_augmented",
        "always_include": ["pending_checks", "command_results"],
        "include_on_failure": ["recent_progress"],
        "recipe": {
            "always_include": ["active_completion_findings"],
            "include_recent": {"command_results": 2},
            "preserve_exact": ["pending_checks"],
            "make_queryable_not_inline": ["artifact_history"],
            "include_last_failure": 1,
        },
    }
    config = parse_harness_config_ir(_encoded(raw), require_semantic_contract=True)
    assert config.context_policy.always_include == ("pending_checks", "command_results")
    assert config.context_policy.recipe is not None
    assert config.context_policy.recipe.include_recent[0].selector == "command_results"


def test_runtime_contract_separates_top_level_and_recipe_selectors() -> None:
    supported = build_architect_runtime_contract()["supported_values"]
    assert "pending_checks" in supported["context_top_level_sections"]
    assert "active_completion_findings" in supported["context_exact_selectors"]
    assert "/app/out.txt" not in supported["context_top_level_sections"]


def test_live_architect_gets_one_repair_for_missing_semantic_contract() -> None:
    missing = _encoded(_base_config())
    valid = _encoded(_with_semantic_contract(_base_config()))

    class Model:
        def __init__(self) -> None:
            self.calls = 0

        def __call__(self, messages, *, max_output_tokens=24000):
            self.calls += 1
            return missing if self.calls == 1 else valid

    model = Model()
    config, errors = WorkbenchArchitect(model).configure({"schema_version": "architect_request.v2"})
    assert model.calls == 2
    assert config is not None
    assert config.clause_coverage
    assert errors == []


def test_live_architect_never_accepts_prose_only_contract() -> None:
    missing = _encoded(_base_config())

    class Model:
        def __init__(self) -> None:
            self.calls = 0

        def __call__(self, messages, *, max_output_tokens=24000):
            self.calls += 1
            return missing

    model = Model()
    config, errors = WorkbenchArchitect(model).configure({"schema_version": "architect_request.v2"})
    assert model.calls == 2
    assert config is None
    assert any("requires non-empty clause_coverage" in item for item in errors)
