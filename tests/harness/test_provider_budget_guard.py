from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from aether.provider_budget import (
    BUDGET_PATH_ENV,
    BUDGET_SHA256_ENV,
    ProviderBudgetError,
    ProviderBudgetGuard,
    clear_provider_budget_guard_cache_for_tests,
    parse_budget_contract,
    provider_budget_guard_from_env,
)
from aether.providers.azure_model import (
    AzureModelCallable,
    AzureModelError,
    AzureVisionCallable,
    make_azure_callable,
)


def _contract(*, solver_creates: int = 5, solver_input: int = 120000, solver_output: int = 16000) -> dict:
    role = {
        "max_input_tokens": 120000,
        "max_output_tokens": 16000,
        "input_gbp_per_million": "0.20",
        "output_gbp_per_million": "1.20",
    }
    return {
        "schema_version": "aether.provider_budget.v1",
        "model_id": "gpt-5.6-luna",
        "budget_id": "provider-budget-unit",
        "currency": "GBP",
        "budget_constrained": True,
        "total_cap_gbp": "1",
        "provider_max_retries": 0,
        "provider_sdk_max_retries": 0,
        "solver_turn_budget": 6,
        "agent_timeout_sec": 120.0,
        "vm_incremental_cap_gbp": "0",
        "roles": {
            "solver": {
                **role,
                "max_provider_creates": solver_creates,
                "max_input_tokens": solver_input,
                "max_output_tokens": solver_output,
            },
            "verifier": {**role, "max_provider_creates": 0},
            "vision": {**role, "max_provider_creates": 0, "max_output_tokens": 8000},
        },
    }


class _FakeResponses:
    def __init__(self, outer: "_FakeClient") -> None:
        self.outer = outer

    def create(self, **_kwargs):
        self.outer.create_calls += 1
        ordinal = self.outer.create_calls
        return SimpleNamespace(
            id=f"response-{ordinal}",
            status="completed",
            error=None,
            incomplete_details=None,
            output_text="",
            output=[SimpleNamespace(
                id=f"item-{ordinal}",
                type="function_call",
                status="completed",
                call_id=f"call-{ordinal}",
                name="read_file",
                arguments=json.dumps({"arguments": {"path": "out.txt"}}),
            )],
            usage=(
                SimpleNamespace(
                    input_tokens=100 + ordinal, output_tokens=10, total_tokens=110 + ordinal,
                    input_tokens_details=SimpleNamespace(cached_tokens=0),
                    output_tokens_details=SimpleNamespace(reasoning_tokens=0),
                )
                if self.outer.include_usage else None
            ),
        )


class _FakeClient:
    def __init__(self, *, include_usage: bool = True) -> None:
        self.create_calls = 0
        self.include_usage = include_usage
        self.responses = _FakeResponses(self)


class _FakeAsyncTransport:
    def __init__(self, client: _FakeClient) -> None:
        self.client = client

    def call(self, operation: str, *args, **kwargs):
        assert operation == "create"
        kwargs.pop("cancellation_event", None)
        return self.client.responses.create(**kwargs)

    def close(self) -> None:
        pass


def _guard(tmp_path: Path, **kwargs) -> ProviderBudgetGuard:
    contract = parse_budget_contract(_contract(**kwargs))
    return ProviderBudgetGuard(
        contract,
        contract_sha=contract.sha256(),
        journal_path=tmp_path / "reservations.jsonl",
    )


def _model(client: _FakeClient, guard: ProviderBudgetGuard) -> AzureModelCallable:
    return AzureModelCallable(
        client=client,  # type: ignore[arg-type]
        deployment="unit-test-deployment",
        effort="medium",
        role="solver",
        responses_background=False,
        prompt_cache_mode="off",
        poll_interval_s=1.0,
        poll_timeout_s=30.0,
        max_retries=0,
        budget_guard=guard,
    )


def _one_turn(model: AzureModelCallable, ordinal: int, *, max_output_tokens: int = 1000) -> str:
    run_id = "budget-run"
    task_id = "budget-task"
    result = model.call_with_telemetry_scope(
        [{"role": "user", "content": f"turn {ordinal}"}],
        max_output_tokens=max_output_tokens,
        run_id=run_id,
        task_id=task_id,
    )
    model.commit_pending_response(run_id=run_id, task_id=task_id)
    return result


def test_sixth_provider_create_never_reaches_fake_provider(tmp_path: Path) -> None:
    client = _FakeClient()
    guard = _guard(tmp_path, solver_creates=5)
    model = _model(client, guard)

    for ordinal in range(5):
        assert _one_turn(model, ordinal)
    assert client.create_calls == 5
    with pytest.raises(AzureModelError, match="provider create ceiling exhausted"):
        _one_turn(model, 6)
    assert client.create_calls == 5
    snapshot = guard.snapshot()
    assert snapshot["aggregate_create_count"] == 5
    assert snapshot["role_create_counts"]["solver"] == 5
    rows = [json.loads(line) for line in (tmp_path / "reservations.jsonl").read_text().splitlines()]
    assert len(rows) == 5
    assert rows[-1]["aggregate_create_ordinal"] == 5
    assert rows[-1]["reservation_refundable"] is False


def test_budget_requires_explicit_output_cap_before_dispatch(tmp_path: Path) -> None:
    client = _FakeClient()
    model = _model(client, _guard(tmp_path))
    with pytest.raises(AzureModelError, match="requires explicit max_output_tokens"):
        model.call_with_telemetry_scope(
            [{"role": "user", "content": "hello"}],
            max_output_tokens=None,
            run_id="budget-run",
            task_id="budget-task",
        )
    assert client.create_calls == 0


def test_budget_rejects_output_cap_above_contract_before_dispatch(tmp_path: Path) -> None:
    client = _FakeClient()
    model = _model(client, _guard(tmp_path, solver_output=1000))
    with pytest.raises(AzureModelError, match="max_output_tokens exceeds contract"):
        _one_turn(model, 1, max_output_tokens=1001)
    assert client.create_calls == 0


def test_budget_rejects_serialized_request_above_conservative_input_ceiling(tmp_path: Path) -> None:
    client = _FakeClient()
    model = _model(client, _guard(tmp_path, solver_input=100))
    with pytest.raises(AzureModelError, match="input token upper bound exceeds contract"):
        _one_turn(model, 1, max_output_tokens=10)
    assert client.create_calls == 0


def test_contract_rejects_nonzero_provider_or_sdk_retries() -> None:
    for field in ("provider_max_retries", "provider_sdk_max_retries"):
        value = _contract()
        value[field] = 1
        with pytest.raises(ProviderBudgetError, match="retries must both be 0"):
            parse_budget_contract(value)


def test_contract_rejects_worst_case_ceiling_above_total_cap() -> None:
    value = _contract(solver_creates=100)
    value["total_cap_gbp"] = "0.01"
    with pytest.raises(ProviderBudgetError, match="exceed total_cap_gbp"):
        parse_budget_contract(value)


def test_env_hash_mismatch_fails_before_provider_credentials_are_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    value = _contract()
    contract = parse_budget_contract(value)
    path = tmp_path / "budget.json"
    path.write_text(json.dumps(contract.as_dict()))
    monkeypatch.setenv(BUDGET_PATH_ENV, str(path))
    monkeypatch.setenv(BUDGET_SHA256_ENV, "0" * 64)
    monkeypatch.delenv("MISSING_ENDPOINT", raising=False)
    monkeypatch.delenv("MISSING_DEPLOYMENT", raising=False)
    monkeypatch.delenv("MISSING_KEY", raising=False)
    clear_provider_budget_guard_cache_for_tests()
    with pytest.raises(ProviderBudgetError, match="SHA256"):
        make_azure_callable(
            endpoint_env="MISSING_ENDPOINT",
            deployment_env="MISSING_DEPLOYMENT",
            key_env="MISSING_KEY",
            role="solver",
            max_retries=0,
            sdk_max_retries=0,
        )


def test_budget_mode_rejects_nonzero_retry_before_credentials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    contract = parse_budget_contract(_contract())
    path = tmp_path / "budget.json"
    path.write_text(json.dumps(contract.as_dict()))
    monkeypatch.setenv(BUDGET_PATH_ENV, str(path))
    monkeypatch.setenv(BUDGET_SHA256_ENV, contract.sha256())
    clear_provider_budget_guard_cache_for_tests()
    with pytest.raises(AzureModelError, match="requires explicit provider and SDK retries = 0"):
        make_azure_callable(
            endpoint_env="MISSING_ENDPOINT",
            deployment_env="MISSING_DEPLOYMENT",
            key_env="MISSING_KEY",
            role="solver",
            max_retries=1,
            sdk_max_retries=0,
        )


def test_solver_verifier_factories_share_one_env_guard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    contract = parse_budget_contract(_contract())
    path = tmp_path / "budget.json"
    path.write_text(json.dumps(contract.as_dict()))
    monkeypatch.setenv(BUDGET_PATH_ENV, str(path))
    monkeypatch.setenv(BUDGET_SHA256_ENV, contract.sha256())
    clear_provider_budget_guard_cache_for_tests()
    first = provider_budget_guard_from_env()
    second = provider_budget_guard_from_env()
    assert first is second


def test_vision_zero_create_cap_blocks_before_provider(tmp_path: Path) -> None:
    client = _FakeClient()
    guard = _guard(tmp_path)
    vision = AzureVisionCallable(
        client, "unit-test-deployment", async_transport=_FakeAsyncTransport(client),
        budget_guard=guard,
    )
    with pytest.raises(ProviderBudgetError, match="ceiling exhausted for role vision"):
        vision("describe", "AAAA", "image/png")
    assert client.create_calls == 0


def test_contract_rejects_optimistic_frontier_pricing_floor() -> None:
    for field, value in (("input_gbp_per_million", "0.19"), ("output_gbp_per_million", "1.19")):
        contract = _contract()
        contract["roles"]["solver"][field] = value
        with pytest.raises(ProviderBudgetError, match="pricing floor"):
            parse_budget_contract(contract)


def test_long_context_surcharge_is_reserved_before_dispatch(tmp_path: Path) -> None:
    guard = _guard(tmp_path, solver_input=300000, solver_output=16000)
    event = guard.reserve(
        "solver",
        {"model": "unit-test", "input": "x", "max_output_tokens": 1000},
        input_token_upper_bound=272001,
    )
    assert event["long_context_surcharge_applied"] is True
    # Conservative input reserves the documented cache-write premium too: 272001 * ($0.20 * 1.25 * 2) + 1000 * ($1.20 * 1.5), treating $1 as £1.
    assert event["reserved_gbp"] == "0.1378005"


def test_second_solver_turn_reserves_prior_provider_tokens_plus_request_bytes(tmp_path: Path) -> None:
    client = _FakeClient()
    guard = _guard(tmp_path, solver_creates=2)
    model = _model(client, guard)
    assert _one_turn(model, 1)
    assert _one_turn(model, 2)
    rows = [json.loads(line) for line in (tmp_path / "reservations.jsonl").read_text().splitlines()]
    assert len(rows) == 2
    assert rows[0]["input_bound_source"] == "provider_continuity_plus_serialized_request_bytes" or rows[0]["input_bound_source"] == "serialized_request_bytes"
    assert rows[1]["input_bound_source"] == "provider_continuity_plus_serialized_request_bytes"
    assert rows[1]["input_token_upper_bound"] == rows[1]["request_bytes"] + 111


def test_missing_provider_usage_blocks_only_next_continuation_before_dispatch(tmp_path: Path) -> None:
    client = _FakeClient(include_usage=False)
    model = _model(client, _guard(tmp_path, solver_creates=2))
    # The already-paid first action remains usable and can be admitted.
    assert _one_turn(model, 1)
    assert client.create_calls == 1
    with pytest.raises(AzureModelError, match="lacks prior provider token usage"):
        _one_turn(model, 2)
    assert client.create_calls == 1


def test_budget_guard_reconstruction_inherits_spent_envelope(tmp_path: Path) -> None:
    first = _guard(tmp_path, solver_creates=2)
    request = {"model": "unit-test", "input": "hello", "max_output_tokens": 1000}
    event1 = first.reserve("solver", request)
    second = ProviderBudgetGuard(
        first.contract, contract_sha=first.contract_sha,
        journal_path=tmp_path / "reservations.jsonl",
    )
    snap = second.snapshot()
    assert snap["aggregate_create_count"] == 1
    assert snap["role_create_counts"]["solver"] == 1
    assert snap["reserved_gbp"] == event1["running_reserved_gbp"]
    event2 = second.reserve("solver", request)
    assert event2["aggregate_create_ordinal"] == 2
    assert event2["role_create_ordinal"] == 2
    with pytest.raises(ProviderBudgetError, match="ceiling exhausted"):
        second.reserve("solver", request)


def test_budget_guard_reconstruction_rejects_tampered_running_total(tmp_path: Path) -> None:
    first = _guard(tmp_path, solver_creates=2)
    request = {"model": "unit-test", "input": "hello", "max_output_tokens": 1000}
    first.reserve("solver", request)
    path = tmp_path / "reservations.jsonl"
    row = json.loads(path.read_text())
    row["running_reserved_gbp"] = "0"
    path.write_text(json.dumps(row) + "\n")
    with pytest.raises(ProviderBudgetError, match="running total mismatch"):
        ProviderBudgetGuard(first.contract, contract_sha=first.contract_sha, journal_path=path)


def test_budget_guard_reconstruction_rejects_malformed_journal(tmp_path: Path) -> None:
    first = _guard(tmp_path)
    path = tmp_path / "reservations.jsonl"
    path.write_text("{not-json}\n")
    with pytest.raises(ProviderBudgetError, match="invalid JSON"):
        ProviderBudgetGuard(first.contract, contract_sha=first.contract_sha, journal_path=path)
