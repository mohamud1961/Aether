from __future__ import annotations

from types import SimpleNamespace

from aether.classifier import HarnessLimiterClassifier
from aether.kernel import _provider_failure_result
from aether.ledger import ExecutionLedger
from aether.model_hooks import ModelProviderError
from aether.provider_budget import ProviderBudgetError


def _nested_budget_error() -> RuntimeError:
    try:
        raise ProviderBudgetError("budgeted solver input token upper bound exceeds contract")
    except ProviderBudgetError as exc:
        try:
            raise RuntimeError("responses native-tool call failed") from exc
        except RuntimeError as wrapped:
            return wrapped


def test_model_provider_error_recognizes_nested_pre_dispatch_budget_refusal() -> None:
    exc = ModelProviderError(_nested_budget_error(), role="solver")
    assert exc.pre_dispatch_budget_admission_refused is True


def test_kernel_reports_budget_admission_as_resource_boundary_not_provider_failure() -> None:
    ledger = ExecutionLedger()
    result = _provider_failure_result(
        exc=ModelProviderError(_nested_budget_error(), role="solver"),
        step=4,
        reconfigurations=0,
        compiled=SimpleNamespace(env_digest="env"),
        ledger=ledger,
        parse_correction_attempted=False,
    )
    assert result.status == "provider_budget_blocked"
    assert result.blockers == ("solver_provider_budget_admission",)
    receipt = result.receipts[-1]
    assert receipt.kind == "provider_budget_admission"
    assert receipt.failure_class == "provider_budget_admission"
    assert receipt.payload["provider_dispatch_attempted"] is False
    assert receipt.payload["budget_admission_refused"] is True
    classified = HarnessLimiterClassifier().classify(result)
    assert classified.label == "budget_resource_limit"
    assert "not a provider/network failure" in classified.detail


def test_real_provider_failure_keeps_existing_status_and_classification() -> None:
    result = _provider_failure_result(
        exc=ModelProviderError(ConnectionError("network down"), role="solver"),
        step=1,
        reconfigurations=0,
        compiled=SimpleNamespace(env_digest="env"),
        ledger=ExecutionLedger(),
        parse_correction_attempted=False,
    )
    assert result.status == "provider_failure"
    assert result.receipts[-1].kind == "provider_failure"
    assert HarnessLimiterClassifier().classify(result).label == "provider_failure"
