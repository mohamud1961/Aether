from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from aether.provider_budget import (
    FRONTIER_CONTEXT_WINDOW_TOKENS,
    FRONTIER_MAX_OUTPUT_TOKENS,
    ProviderBudgetError,
    ProviderBudgetGuard,
    budget_journal_state,
    parse_budget_contract,
)


def _role(*, creates: int = 100) -> dict[str, object]:
    return {
        "max_provider_creates": creates,
        "max_input_tokens": FRONTIER_CONTEXT_WINDOW_TOKENS,
        "max_output_tokens": FRONTIER_MAX_OUTPUT_TOKENS,
        "input_gbp_per_million": "0.20",
        "output_gbp_per_million": "1.20",
    }


def _v2(*, cap: str = "0.30") -> dict[str, object]:
    return {
        "schema_version": "aether.provider_budget.v2",
        "budget_id": "unit-v2-settlement",
        "model_id": "gpt-5.6-luna",
        "currency": "GBP",
        "budget_constrained": True,
        "total_cap_gbp": cap,
        "provider_max_retries": 1,
        "provider_sdk_max_retries": 0,
        "agent_timeout_sec": 900,
        "vm_incremental_cap_gbp": "0",
        "runtime_limits": {
            "solver_turn_budget": None,
            "solver_max_output_tokens": None,
            "verifier_max_output_tokens": None,
            "vision_max_output_tokens": None,
        },
        "roles": {
            "solver": _role(),
            "verifier": _role(),
            "vision": {
                **_role(creates=0),
            },
        },
    }


def _v1(*, cap: str = "1.00") -> dict[str, object]:
    return {
        "schema_version": "aether.provider_budget.v1",
        "budget_id": "unit-v1-no-settlement",
        "model_id": "gpt-5.6-luna",
        "currency": "GBP",
        "budget_constrained": True,
        "total_cap_gbp": cap,
        "provider_max_retries": 0,
        "provider_sdk_max_retries": 0,
        "solver_turn_budget": 4,
        "agent_timeout_sec": 900,
        "vm_incremental_cap_gbp": "0",
        "roles": {
            "solver": {
                "max_provider_creates": 4,
                "max_input_tokens": 200000,
                "max_output_tokens": 8000,
                "input_gbp_per_million": "0.20",
                "output_gbp_per_million": "1.20",
            },
            "verifier": {
                "max_provider_creates": 0,
                "max_input_tokens": 200000,
                "max_output_tokens": 8000,
                "input_gbp_per_million": "0.20",
                "output_gbp_per_million": "1.20",
            },
            "vision": {
                "max_provider_creates": 0,
                "max_input_tokens": 200000,
                "max_output_tokens": 8000,
                "input_gbp_per_million": "0.20",
                "output_gbp_per_million": "1.20",
            },
        },
    }


def test_v2_success_settlement_releases_only_provisional_headroom(tmp_path: Path) -> None:
    contract = parse_budget_contract(_v2(cap="0.30"))
    journal = tmp_path / "budget.jsonl"
    guard = ProviderBudgetGuard(contract, contract_sha=contract.sha256(), journal_path=journal)
    request = {"model": "gpt-5.6-luna", "input": "hello"}
    first = guard.reserve("solver", request, input_token_upper_bound=100)
    assert Decimal(first["reserved_gbp"]) > Decimal("0.15")
    with pytest.raises(ProviderBudgetError, match="exceed GBP cap"):
        guard.reserve("solver", request, input_token_upper_bound=100)

    settlement = guard.settle_success(first, input_tokens=80, output_tokens=1000)
    assert Decimal(settlement["settled_gbp"]) < Decimal(first["reserved_gbp"])
    assert Decimal(settlement["released_provisional_gbp"]) > 0

    second = guard.reserve("solver", request, input_token_upper_bound=100)
    assert second["aggregate_create_ordinal"] == 2
    snapshot = guard.snapshot()
    assert snapshot["settlement_count"] == 1
    assert snapshot["unsettled_reservation_count"] == 1
    assert Decimal(snapshot["reserved_gbp"]) <= contract.total_cap_gbp


def test_v2_settlement_reconstruction_is_append_only_and_stable(tmp_path: Path) -> None:
    contract = parse_budget_contract(_v2(cap="1.00"))
    journal = tmp_path / "budget.jsonl"
    guard = ProviderBudgetGuard(contract, contract_sha=contract.sha256(), journal_path=journal)
    reservation = guard.reserve("solver", {"model": "x", "input": "hello"}, input_token_upper_bound=1000)
    settlement = guard.settle_success(reservation, input_tokens=900, output_tokens=1200)
    lines = journal.read_text().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["schema_version"] == "aether.provider_budget_reservation.v1"
    assert json.loads(lines[1])["schema_version"] == "aether.provider_budget_settlement.v1"

    restored = budget_journal_state(contract, contract_sha=contract.sha256(), journal_path=journal)
    assert restored["aggregate_create_count"] == 1
    assert restored["settlement_count"] == 1
    assert restored["reservation_records"][1]["settled"] is True
    assert Decimal(restored["reserved_gbp"]) == Decimal(settlement["settled_gbp"])

    reconstructed = ProviderBudgetGuard(contract, contract_sha=contract.sha256(), journal_path=journal)
    with pytest.raises(ProviderBudgetError, match="settled more than once"):
        reconstructed.settle_success(1, input_tokens=900, output_tokens=1200)


def test_v2_settlement_rejects_usage_outside_original_bounds_without_release(tmp_path: Path) -> None:
    contract = parse_budget_contract(_v2(cap="1.00"))
    journal = tmp_path / "budget.jsonl"
    guard = ProviderBudgetGuard(contract, contract_sha=contract.sha256(), journal_path=journal)
    reservation = guard.reserve("solver", {"model": "x", "input": "hello"}, input_token_upper_bound=1000)
    before = journal.read_text()
    reserved_before = guard.snapshot()["reserved_gbp"]
    with pytest.raises(ProviderBudgetError, match="input usage exceeds reservation bound"):
        guard.settle_success(reservation, input_tokens=1001, output_tokens=100)
    assert journal.read_text() == before
    assert guard.snapshot()["reserved_gbp"] == reserved_before


def test_v2_missing_or_malformed_usage_cannot_release_reservation(tmp_path: Path) -> None:
    contract = parse_budget_contract(_v2(cap="1.00"))
    guard = ProviderBudgetGuard(contract, contract_sha=contract.sha256(), journal_path=tmp_path / "j.jsonl")
    reservation = guard.reserve("solver", {"model": "x", "input": "hello"}, input_token_upper_bound=1000)
    with pytest.raises(ProviderBudgetError, match="must be integer"):
        guard.settle_success(reservation, input_tokens=None, output_tokens=10)  # type: ignore[arg-type]
    assert guard.snapshot()["settlement_count"] == 0
    assert guard.snapshot()["unsettled_reservation_count"] == 1


def test_v1_reservations_remain_non_settleable_and_hash_semantics_unchanged(tmp_path: Path) -> None:
    contract = parse_budget_contract(_v1())
    journal = tmp_path / "v1.jsonl"
    guard = ProviderBudgetGuard(contract, contract_sha=contract.sha256(), journal_path=journal)
    reservation = guard.reserve(
        "solver", {"model": "x", "input": "hello", "max_output_tokens": 1000}, input_token_upper_bound=1000,
    )
    before = journal.read_text()
    with pytest.raises(ProviderBudgetError, match="only valid for v2"):
        guard.settle_success(reservation, input_tokens=900, output_tokens=900)
    assert journal.read_text() == before
    restored = budget_journal_state(contract, contract_sha=contract.sha256(), journal_path=journal)
    assert restored["settlement_count"] == 0
    assert restored["aggregate_create_count"] == 1


# ---- Provider-boundary integration -------------------------------------------------
from types import SimpleNamespace

from aether.providers.azure_model import AzureModelCallable


def _provider_response(n: int, *, usage: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        id=f"resp-{n}",
        status="completed",
        output=[SimpleNamespace(
            id=f"fc-{n}", type="function_call", status="completed",
            call_id=f"call-{n}", name="read_file",
            arguments=json.dumps({"arguments": {"path": "/app/input.txt"}}),
        )],
        usage=(
            SimpleNamespace(
                input_tokens=1000 + n,
                output_tokens=100 + n,
                total_tokens=1100 + 2 * n,
                input_tokens_details=SimpleNamespace(cached_tokens=0),
                output_tokens_details=SimpleNamespace(reasoning_tokens=0),
            ) if usage else None
        ),
        reasoning=None,
        error=None,
        incomplete_details=None,
    )


class _SequenceResponses:
    def __init__(self, rows: list[object]) -> None:
        self.rows = list(rows)
        self.requests: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> object:
        self.requests.append(dict(kwargs))
        if not self.rows:
            raise AssertionError("no fake provider response remains")
        row = self.rows.pop(0)
        if isinstance(row, BaseException):
            raise row
        return row

    def retrieve(self, _response_id: str) -> object:
        raise AssertionError("completed foreground fake must not poll")

    def cancel(self, _response_id: str) -> object:
        raise AssertionError("completed foreground fake must not cancel")


class _SequenceClient:
    def __init__(self, rows: list[object]) -> None:
        self.responses = _SequenceResponses(rows)


class _PreviousResponseNotFound(Exception):
    def __init__(self) -> None:
        super().__init__("previous_response_not_found")
        self.status_code = 400
        self.body = {"error": {"code": "previous_response_not_found"}}


def _v2_guard_and_model(
    tmp_path: Path, rows: list[object], *, cap: str = "1.00",
) -> tuple[ProviderBudgetGuard, AzureModelCallable, _SequenceClient, Path]:
    raw = _v2(cap=cap)
    raw["provider_max_retries"] = 0
    contract = parse_budget_contract(raw)
    journal = tmp_path / "provider.jsonl"
    guard = ProviderBudgetGuard(contract, contract_sha=contract.sha256(), journal_path=journal)
    client = _SequenceClient(rows)
    model = AzureModelCallable(
        client=client,  # type: ignore[arg-type]
        deployment="unit-v2-settlement",
        effort="low",
        role="solver",
        responses_background=False,
        poll_interval_s=1.0,
        poll_timeout_s=30.0,
        max_retries=0,
        prompt_cache_mode="off",
        budget_guard=guard,
    )
    return guard, model, client, journal


def _uncapped_scoped_call(model: AzureModelCallable, content: str) -> str:
    raw = model.call_with_telemetry_scope(
        [{"role": "user", "content": content}],
        max_output_tokens=None,
        run_id="settlement-run",
        task_id="settlement-task",
    )
    model.commit_pending_response(run_id="settlement-run", task_id="settlement-task")
    return raw


def test_v2_provider_success_settles_uncapped_create_from_reported_usage(tmp_path: Path) -> None:
    guard, model, client, journal = _v2_guard_and_model(
        tmp_path, [_provider_response(1)], cap="0.30",
    )
    assert _uncapped_scoped_call(model, "first")
    assert len(client.responses.requests) == 1
    assert "max_output_tokens" not in client.responses.requests[0]
    rows = [json.loads(line) for line in journal.read_text().splitlines()]
    assert [r["schema_version"] for r in rows] == [
        "aether.provider_budget_reservation.v1",
        "aether.provider_budget_settlement.v1",
    ]
    snapshot = guard.snapshot()
    assert snapshot["aggregate_create_count"] == 1
    assert snapshot["settlement_count"] == 1
    assert snapshot["unsettled_reservation_count"] == 0
    assert Decimal(snapshot["reserved_gbp"]) < Decimal("0.30")
    event = model.drain_telemetry()[0]
    assert event["provider_budget_settlement_status"] == "settled_terminal_success_usage"
    assert event["provider_budget_settlement_aggregate_create_ordinal"] == 1


def test_v2_completed_response_without_usage_retains_full_reservation(tmp_path: Path) -> None:
    guard, model, _client, journal = _v2_guard_and_model(
        tmp_path, [_provider_response(1, usage=False)], cap="1.00",
    )
    assert _uncapped_scoped_call(model, "first")
    rows = [json.loads(line) for line in journal.read_text().splitlines()]
    assert len(rows) == 1
    assert rows[0]["schema_version"] == "aether.provider_budget_reservation.v1"
    snapshot = guard.snapshot()
    assert snapshot["settlement_count"] == 0
    assert snapshot["unsettled_reservation_count"] == 1
    event = model.drain_telemetry()[0]
    assert event["provider_budget_settlement_status"] == "retained_missing_usage"


def test_v2_reanchor_retains_failed_create_and_settles_only_successful_create(tmp_path: Path) -> None:
    guard, model, client, journal = _v2_guard_and_model(
        tmp_path,
        [_provider_response(1), _PreviousResponseNotFound(), _provider_response(2)],
        cap="1.00",
    )
    assert _uncapped_scoped_call(model, "one")
    assert _uncapped_scoped_call(model, "two")
    assert len(client.responses.requests) == 3
    assert client.responses.requests[1]["previous_response_id"] == "resp-1"
    assert "previous_response_id" not in client.responses.requests[2]

    snapshot = guard.snapshot()
    assert snapshot["aggregate_create_count"] == 3
    assert snapshot["settlement_count"] == 2
    assert snapshot["unsettled_reservation_count"] == 1
    rows = [json.loads(line) for line in journal.read_text().splitlines()]
    reservation_ordinals = [
        r["aggregate_create_ordinal"] for r in rows
        if r["schema_version"] == "aether.provider_budget_reservation.v1"
    ]
    settlement_ordinals = [
        r["aggregate_create_ordinal"] for r in rows
        if r["schema_version"] == "aether.provider_budget_settlement.v1"
    ]
    assert reservation_ordinals == [1, 2, 3]
    assert settlement_ordinals == [1, 3]
    event = model.drain_telemetry()[-1]
    assert event["persistent_continuity_reanchor_attempted"] is True
    assert event["persistent_continuity_reanchor_succeeded"] is True
    assert event["provider_budget_settlement_aggregate_create_ordinal"] == 3


from aether.providers.azure_model import AzureVisionCallable


class _VisionResponses:
    def __init__(self, *, include_usage: bool = True) -> None:
        self.requests: list[dict[str, object]] = []
        self.include_usage = include_usage

    def create(self, **kwargs: object) -> object:
        self.requests.append(dict(kwargs))
        return SimpleNamespace(
            id="vision-1",
            status="completed",
            output=[SimpleNamespace(
                id="vision-message", type="message", role="assistant",
                content=[SimpleNamespace(type="output_text", text="vision description")],
            )],
            usage=(
                SimpleNamespace(
                    input_tokens=50,
                    output_tokens=20,
                    total_tokens=70,
                    input_tokens_details=SimpleNamespace(cached_tokens=0),
                    output_tokens_details=SimpleNamespace(reasoning_tokens=0),
                ) if self.include_usage else None
            ),
            error=None,
            incomplete_details=None,
        )


class _VisionClient:
    def __init__(self, *, include_usage: bool = True) -> None:
        self.responses = _VisionResponses(include_usage=include_usage)


def test_v2_vision_omits_harness_output_cap_and_settles_success(tmp_path: Path) -> None:
    raw = _v2(cap="1.00")
    raw["provider_max_retries"] = 0
    raw["roles"]["vision"]["max_provider_creates"] = 2
    contract = parse_budget_contract(raw)
    journal = tmp_path / "vision.jsonl"
    guard = ProviderBudgetGuard(contract, contract_sha=contract.sha256(), journal_path=journal)
    client = _VisionClient()
    vision = AzureVisionCallable(client, "unit-vision", budget_guard=guard)  # type: ignore[arg-type]
    assert vision("describe", "AAAA", "image/png") == "vision description"
    assert len(client.responses.requests) == 1
    assert "max_output_tokens" not in client.responses.requests[0]
    snapshot = guard.snapshot()
    assert snapshot["aggregate_create_count"] == 1
    assert snapshot["settlement_count"] == 1
    assert snapshot["unsettled_reservation_count"] == 0
    event = vision.drain_telemetry()[0]
    assert event["max_output_tokens"] is None
    assert event["provider_budget_settlement_status"] == "settled_terminal_success_usage"


def test_v2_vision_missing_usage_retains_full_hold(tmp_path: Path) -> None:
    raw = _v2(cap="1.00")
    raw["provider_max_retries"] = 0
    raw["roles"]["vision"]["max_provider_creates"] = 1
    contract = parse_budget_contract(raw)
    guard = ProviderBudgetGuard(contract, contract_sha=contract.sha256(), journal_path=tmp_path / "vision.jsonl")
    client = _VisionClient(include_usage=False)
    vision = AzureVisionCallable(client, "unit-vision", budget_guard=guard)  # type: ignore[arg-type]
    assert vision("describe", "AAAA", "image/png") == "vision description"
    snapshot = guard.snapshot()
    assert snapshot["settlement_count"] == 0
    assert snapshot["unsettled_reservation_count"] == 1
    event = vision.drain_telemetry()[0]
    assert event["provider_budget_settlement_status"] == "retained_missing_usage"


from aether.providers.azure_model import AzureProviderOutputError


def test_v2_verifier_settles_billable_success_even_when_local_output_validation_rejects(tmp_path: Path) -> None:
    raw = _v2(cap="1.00")
    raw["provider_max_retries"] = 0
    contract = parse_budget_contract(raw)
    journal = tmp_path / "verifier.jsonl"
    guard = ProviderBudgetGuard(contract, contract_sha=contract.sha256(), journal_path=journal)
    # A Solver-shaped native call is deliberately wrong for the Verifier tool.
    # The provider request nevertheless completed and reported usage, so fiscal
    # settlement should occur before local semantic/schema validation rejects it.
    client = _SequenceClient([_provider_response(1)])
    verifier = AzureModelCallable(
        client=client,  # type: ignore[arg-type]
        deployment="unit-v2-verifier",
        effort="low",
        role="verifier",
        responses_background=False,
        poll_interval_s=1.0,
        poll_timeout_s=30.0,
        max_retries=0,
        prompt_cache_mode="off",
        budget_guard=guard,
    )
    with pytest.raises(AzureProviderOutputError):
        verifier.call_with_telemetry_scope(
            [{"role": "user", "content": "verify the current completion packet"}],
            max_output_tokens=None,
            run_id="verify-run",
            task_id="verify-task",
        )
    assert len(client.responses.requests) == 1
    assert "max_output_tokens" not in client.responses.requests[0]
    snapshot = guard.snapshot()
    assert snapshot["aggregate_create_count"] == 1
    assert snapshot["settlement_count"] == 1
    assert snapshot["unsettled_reservation_count"] == 0
    event = verifier.drain_telemetry()[0]
    assert event["status"] == "failed"
    assert event["provider_budget_settlement_status"] == "settled_terminal_success_usage"
    rows = [json.loads(line) for line in journal.read_text().splitlines()]
    assert [row["schema_version"] for row in rows] == [
        "aether.provider_budget_reservation.v1",
        "aether.provider_budget_settlement.v1",
    ]
