from __future__ import annotations

from decimal import Decimal

import pytest

from aether.provider_budget import (
    GPT6_FRONTIER_BUDGET_MODEL_ID,
    ProviderBudgetError,
    parse_budget_contract,
)


def _gpt6_frontier_canary_contract(*, model_id: str = GPT6_FRONTIER_BUDGET_MODEL_ID) -> dict[str, object]:
    role = {
        "max_input_tokens": 30_000,
        "max_output_tokens": 2_000,
        # These are conservative v1 reservation rates, not GPT-6-Luna list prices.
        "input_gbp_per_million": "0.20",
        "output_gbp_per_million": "1.20",
    }
    return {
        "schema_version": "aether.provider_budget.v1",
        "budget_id": "gpt6-frontier-canary-smoke-v1",
        "model_id": model_id,
        "currency": "GBP",
        "budget_constrained": True,
        "total_cap_gbp": "0.02",
        "provider_max_retries": 0,
        "provider_sdk_max_retries": 0,
        "solver_turn_budget": 2,
        "agent_timeout_sec": 360.0,
        "vm_incremental_cap_gbp": "0",
        "roles": {
            "solver": {**role, "max_provider_creates": 2},
            "verifier": {**role, "max_provider_creates": 0},
            "vision": {**role, "max_provider_creates": 0},
        },
    }


def test_explicit_gpt6_frontier_v1_contract_fits_two_bounded_solver_creates() -> None:
    contract = parse_budget_contract(_gpt6_frontier_canary_contract())

    assert contract.model_id == "gpt-6-luna"
    assert contract.max_total_provider_creates == 2
    assert contract.roles["solver"].max_provider_creates == 2
    assert contract.roles["verifier"].max_provider_creates == 0
    assert contract.roles["vision"].max_provider_creates == 0
    assert contract.roles["solver"].max_input_tokens == 30_000
    assert contract.roles["solver"].max_output_tokens == 2_000
    assert contract.provider_max_retries == contract.provider_sdk_max_retries == 0
    # 30K * 0.20/M * 1.25 cache-write reserve + 2K * 1.20/M,
    # multiplied by exactly two creates.
    assert contract.worst_case_total_gbp == Decimal("0.0198")
    assert contract.worst_case_total_gbp <= contract.total_cap_gbp


def test_gpt6_frontier_budget_model_id_is_canonical_and_v1_only() -> None:
    wrong_case = _gpt6_frontier_canary_contract(model_id="GPT-6-Luna")
    with pytest.raises(ProviderBudgetError, match="no admitted budget profile"):
        parse_budget_contract(wrong_case)

    v2 = _gpt6_frontier_canary_contract()
    v2["schema_version"] = "aether.provider_budget.v2"
    v2.pop("solver_turn_budget")
    v2["runtime_limits"] = {
        "solver_turn_budget": 2,
        "solver_max_output_tokens": 2_000,
        "verifier_max_output_tokens": None,
        "vision_max_output_tokens": None,
    }
    with pytest.raises(ProviderBudgetError, match="no admitted budget profile"):
        parse_budget_contract(v2)
