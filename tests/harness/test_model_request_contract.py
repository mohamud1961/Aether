from __future__ import annotations

import pytest

from aether.model_request_contract import (
    ExpectedModelRequest,
    ModelRequestRealizationError,
    preflight_model_request,
)


class HonestCallable:
    def preflight_request(self, *, max_output_tokens: int, logical_role: str):
        return {
            "provider": "test-provider",
            "model": "test-model",
            "provider_role": logical_role,
            "effort": "low",
            "max_output_tokens": max_output_tokens,
            "background": True,
        }


class ClampingCallable:
    def __init__(self) -> None:
        self.called = False

    def preflight_request(self, *, max_output_tokens: int, logical_role: str):
        del max_output_tokens, logical_role
        return {
            "provider": "test-provider",
            "model": "test-model",
            "max_output_tokens": 1200,
        }

    def __call__(self, *args, **kwargs):
        self.called = True
        raise AssertionError("model call must not happen after failed preflight")


class OpaqueCallable:
    pass


class AzureCallableMissingJsonContract:
    def preflight_request(self, *, max_output_tokens: int, logical_role: str):
        return {
            "provider": "azure_openai_responses",
            "model": "test-model",
            "provider_role": logical_role,
            "max_output_tokens": max_output_tokens,
            "background": True,
            "structured_output_mode": "json_object",
            "explicit_json_instruction": False,
            "json_instruction_in_input": False,
        }


def test_explicit_preflight_contract_matches_declared_budget() -> None:
    row = preflight_model_request(
        HonestCallable(),
        ExpectedModelRequest("solver", 16000),
    )
    assert row["logical_role"] == "solver"
    assert row["actual_max_output_tokens"] == 16000
    assert row["status"] == "matched"


def test_clamping_callable_is_rejected_before_model_call() -> None:
    model = ClampingCallable()
    with pytest.raises(ModelRequestRealizationError) as exc_info:
        preflight_model_request(model, ExpectedModelRequest("solver", 16000))
    assert exc_info.value.code == "model_request_output_budget_mismatch"
    assert "16000" in exc_info.value.detail
    assert "1200" in exc_info.value.detail
    assert model.called is False


def test_opaque_callable_is_rejected_for_certified_run() -> None:
    with pytest.raises(ModelRequestRealizationError) as exc_info:
        preflight_model_request(OpaqueCallable(), ExpectedModelRequest("solver", 16000))
    assert exc_info.value.code == "model_request_preflight_unavailable"


def test_azure_preflight_rejects_missing_explicit_json_instruction() -> None:
    with pytest.raises(ModelRequestRealizationError) as exc_info:
        preflight_model_request(
            AzureCallableMissingJsonContract(),
            ExpectedModelRequest("solver", 16000),
        )
    assert exc_info.value.code == "model_request_json_contract_invalid"


def test_native_azure_callable_uses_audited_direct_forwarding_contract() -> None:
    from aether.providers.azure_model import AzureModelCallable

    model = object.__new__(AzureModelCallable)
    model._deployment = "gpt-test"
    model._role = "solver"
    model._effort = "low"
    row = preflight_model_request(model, ExpectedModelRequest("solver", 16000))
    assert row["provider"] == "azure_openai_responses"
    assert row["model"] == "gpt-test"
    assert row["actual_max_output_tokens"] == 16000
    assert row["certification"] == "native_json_object_request_contract"
    assert row["structured_output_mode"] == "json_object"
    assert row["explicit_json_instruction"] is True
    assert row["json_instruction_in_input"] is True


def test_native_verifier_callable_certifies_one_direct_turn() -> None:
    from aether.providers.azure_model import AzureModelCallable

    model = object.__new__(AzureModelCallable)
    model._deployment = "gpt-test"
    model._role = "verifier"
    model._effort = "low"
    row = preflight_model_request(model, ExpectedModelRequest("verifier", 12000))
    assert row["structured_output_mode"] == "verifier_direct_turn_json_schema"
    assert row["status"] == "matched"


def test_solver_chat_callable_certifies_one_strict_direct_turn() -> None:
    from aether.providers.azure_model import AzureModelCallable

    model = object.__new__(AzureModelCallable)
    model._deployment = "gpt-test"
    model._role = "solver"
    model._effort = "low"
    model._transport = "chat_completions"
    row = preflight_model_request(model, ExpectedModelRequest("solver", 16000))
    assert row["provider"] == "azure_openai_chat_completions"
    assert row["structured_output_mode"] == "solver_direct_turn_json_schema"
    assert row["certification"] == "chat_completions_single_solver_direct_turn_json_schema_contract"
    assert row["status"] == "matched"


def test_persistent_solver_responses_callable_certifies_one_strict_primary_turn() -> None:
    from aether.providers.azure_model import (
        AzureModelCallable,
        PERSISTENT_PRIMARY_STRUCTURED_OUTPUT_NAME,
        PERSISTENT_PRIMARY_TURN_SCHEMA,
    )

    model = object.__new__(AzureModelCallable)
    model._deployment = "gpt-test"
    model._role = "solver"
    model._effort = "low"
    model._transport = "responses"
    model._solver_protocol = "persistent_v0"
    model._structured_output_schema = PERSISTENT_PRIMARY_TURN_SCHEMA
    model._structured_output_name = PERSISTENT_PRIMARY_STRUCTURED_OUTPUT_NAME
    model._responses_background = True
    row = preflight_model_request(model, ExpectedModelRequest("solver", 16000))
    assert row["provider"] == "azure_openai_responses"
    assert row["structured_output_mode"] == "persistent_v0_primary_turn_json_schema"
    assert row["certification"] == "responses_single_persistent_v0_primary_turn_json_schema_contract"
    assert row["status"] == "matched"


def test_persistent_solver_chat_callable_certifies_one_strict_primary_turn() -> None:
    from aether.providers.azure_model import AzureModelCallable

    model = object.__new__(AzureModelCallable)
    model._deployment = "gpt-test"
    model._role = "solver"
    model._effort = "low"
    model._transport = "chat_completions"
    model._solver_protocol = "persistent_v0"
    row = preflight_model_request(model, ExpectedModelRequest("solver", 16000))
    assert row["provider"] == "azure_openai_chat_completions"
    assert row["structured_output_mode"] == "persistent_v0_primary_turn_json_schema"
    assert row["certification"] == "chat_completions_single_persistent_v0_primary_turn_json_schema_contract"
    assert row["status"] == "matched"
