from __future__ import annotations

from pathlib import Path

import pytest

import aether.harbor_runtime as harbor_runtime
from aether.judge_verifier_policy import TypedJudgeVerifierCallable


def test_judge_verifier_selector_defaults_to_control(monkeypatch) -> None:
    monkeypatch.delenv(harbor_runtime.JUDGE_VERIFIER_ARM_ENV, raising=False)
    assert (
        harbor_runtime.selected_judge_verifier_arm()
        == harbor_runtime.JUDGE_VERIFIER_CONTROL_ARM
    )


def test_judge_verifier_selector_rejects_unknown_arm(monkeypatch) -> None:
    monkeypatch.setenv(harbor_runtime.JUDGE_VERIFIER_ARM_ENV, "mystery")
    with pytest.raises(RuntimeError, match=harbor_runtime.JUDGE_VERIFIER_ARM_ENV):
        harbor_runtime.selected_judge_verifier_arm()


def test_v3_arm_does_not_construct_incumbent_verifier_provider(monkeypatch) -> None:
    calls: list[str] = []

    class Provider:
        def __init__(self, role: str) -> None:
            self.role = role

    sentinel = object()
    monkeypatch.setenv(
        harbor_runtime.JUDGE_VERIFIER_ARM_ENV,
        harbor_runtime.JUDGE_VERIFIER_V3_TYPED_ARM,
    )
    monkeypatch.setenv(
        harbor_runtime.H1_REVIEW_ARM_ENV,
        harbor_runtime.H1_SEMANTIC_ARM,
    )
    monkeypatch.setattr(
        harbor_runtime, "require_provider_authorization", lambda _profile: None,
    )
    monkeypatch.setattr(
        harbor_runtime, "budget_runtime_limits_from_env", lambda: None,
    )

    def fake_make_azure_callable(**kwargs):
        role = str(kwargs.get("role"))
        calls.append(role)
        return Provider(role)

    monkeypatch.setattr(
        harbor_runtime, "make_azure_callable", fake_make_azure_callable,
    )
    monkeypatch.setattr(
        harbor_runtime, "build_selected_judge_v3_verifier", lambda: sentinel,
    )

    solver, verifier = harbor_runtime.build_selected_frontier_models()
    assert isinstance(solver, Provider)
    assert solver.role == "solver"
    assert verifier is sentinel
    assert calls == ["solver"]


@pytest.mark.parametrize("h1_arm", [
    harbor_runtime.H1_MECHANICAL_ARM,
    harbor_runtime.H1_OFF_ARM,
])
def test_v3_arm_rejects_conflicting_h1_controls(monkeypatch, h1_arm: str) -> None:
    monkeypatch.setenv(
        harbor_runtime.JUDGE_VERIFIER_ARM_ENV,
        harbor_runtime.JUDGE_VERIFIER_V3_TYPED_ARM,
    )
    monkeypatch.setenv(harbor_runtime.H1_REVIEW_ARM_ENV, h1_arm)
    monkeypatch.setattr(
        harbor_runtime, "require_provider_authorization", lambda _profile: None,
    )
    monkeypatch.setattr(
        harbor_runtime, "budget_runtime_limits_from_env", lambda: None,
    )
    monkeypatch.setattr(
        harbor_runtime,
        "make_azure_callable",
        lambda **kwargs: object(),
    )
    with pytest.raises(RuntimeError, match="incompatible"):
        harbor_runtime.build_selected_frontier_models()


def test_v3_builder_requires_every_sealed_launch_field(monkeypatch) -> None:
    for name in (
        harbor_runtime.JUDGE_VERIFIER_MODEL_ENV,
        harbor_runtime.JUDGE_VERIFIER_JOURNAL_ENV,
        harbor_runtime.JUDGE_VERIFIER_MAX_CALLS_ENV,
        harbor_runtime.JUDGE_VERIFIER_CAP_GBP_ENV,
        harbor_runtime.JUDGE_VERIFIER_INPUT_PRICE_ENV,
    ):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(RuntimeError, match=harbor_runtime.JUDGE_VERIFIER_MODEL_ENV):
        harbor_runtime.build_selected_judge_v3_verifier()


def test_v3_builder_rejects_model_identity_drift(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv(harbor_runtime.JUDGE_VERIFIER_MODEL_ENV, "judge-other")
    monkeypatch.setenv(
        harbor_runtime.JUDGE_VERIFIER_JOURNAL_ENV,
        str(tmp_path / "judge.jsonl"),
    )
    monkeypatch.setenv(harbor_runtime.JUDGE_VERIFIER_MAX_CALLS_ENV, "4")
    monkeypatch.setenv(harbor_runtime.JUDGE_VERIFIER_CAP_GBP_ENV, "0.05")
    monkeypatch.setenv(
        harbor_runtime.JUDGE_VERIFIER_INPUT_PRICE_ENV,
        "0.10",
    )
    with pytest.raises(RuntimeError, match="frozen model"):
        harbor_runtime.build_selected_judge_v3_verifier()


def test_v3_builder_binds_explicit_budget_and_transport(monkeypatch, tmp_path: Path) -> None:
    captured: dict = {}

    class FakeTransport:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)

        def __call__(self, request):
            raise AssertionError("provider call is not part of builder qualification")

    import aether.providers.judge as judge_provider

    monkeypatch.setenv("AETHER_JUDGE_CALLS_ALLOWED", "1")
    monkeypatch.setenv("AETHER_JUDGE_API_KEY", "test-key-never-used")
    monkeypatch.setenv(
        harbor_runtime.JUDGE_VERIFIER_MODEL_ENV,
        harbor_runtime.JUDGE_VERIFIER_FROZEN_MODEL,
    )
    journal = tmp_path / "judge-v3-budget.jsonl"
    monkeypatch.setenv(harbor_runtime.JUDGE_VERIFIER_JOURNAL_ENV, str(journal))
    monkeypatch.setenv(harbor_runtime.JUDGE_VERIFIER_MAX_CALLS_ENV, "7")
    monkeypatch.setenv(harbor_runtime.JUDGE_VERIFIER_CAP_GBP_ENV, "0.06")
    monkeypatch.setenv(
        harbor_runtime.JUDGE_VERIFIER_INPUT_PRICE_ENV,
        "0.10",
    )
    monkeypatch.setattr(judge_provider, "HttpJudgeTransport", FakeTransport)

    verifier = harbor_runtime.build_selected_judge_v3_verifier()
    assert isinstance(verifier, TypedJudgeVerifierCallable)
    assert captured == {
        "model": harbor_runtime.JUDGE_VERIFIER_FROZEN_MODEL,
        "journal": journal,
        "max_calls": 7,
        "cap_gbp": "0.06",
        "input_gbp_per_million": "0.10",
    }

def test_v3_builder_can_use_credential_free_file_broker(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("AETHER_JUDGE_CALLS_ALLOWED", raising=False)
    monkeypatch.delenv("AETHER_JUDGE_API_KEY", raising=False)
    monkeypatch.setenv(
        harbor_runtime.JUDGE_VERIFIER_MODEL_ENV,
        harbor_runtime.JUDGE_VERIFIER_FROZEN_MODEL,
    )
    journal = tmp_path / "judge-v3-broker.jsonl"
    broker_dir = tmp_path / "broker"
    monkeypatch.setenv(harbor_runtime.JUDGE_VERIFIER_JOURNAL_ENV, str(journal))
    monkeypatch.setenv(harbor_runtime.JUDGE_VERIFIER_MAX_CALLS_ENV, "12")
    monkeypatch.setenv(harbor_runtime.JUDGE_VERIFIER_CAP_GBP_ENV, "0.05")
    monkeypatch.setenv(harbor_runtime.JUDGE_VERIFIER_INPUT_PRICE_ENV, "0.10")
    monkeypatch.setenv(
        harbor_runtime.JUDGE_VERIFIER_TRANSPORT_ENV,
        harbor_runtime.JUDGE_VERIFIER_TRANSPORT_FILE_BROKER,
    )
    monkeypatch.setenv(harbor_runtime.JUDGE_VERIFIER_BROKER_DIR_ENV, str(broker_dir))

    verifier = harbor_runtime.build_selected_judge_v3_verifier()
    assert isinstance(verifier, TypedJudgeVerifierCallable)
    transport = verifier._evaluator._transport
    from aether.providers.judge_broker import FileBrokerEvaluator
    assert isinstance(transport, FileBrokerEvaluator)
    assert transport.max_calls == 12
    assert transport.broker_dir == broker_dir
    assert journal.is_file()


def test_v3_builder_rejects_unknown_transport(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv(
        harbor_runtime.JUDGE_VERIFIER_MODEL_ENV,
        harbor_runtime.JUDGE_VERIFIER_FROZEN_MODEL,
    )
    monkeypatch.setenv(
        harbor_runtime.JUDGE_VERIFIER_JOURNAL_ENV,
        str(tmp_path / "judge.jsonl"),
    )
    monkeypatch.setenv(harbor_runtime.JUDGE_VERIFIER_MAX_CALLS_ENV, "4")
    monkeypatch.setenv(harbor_runtime.JUDGE_VERIFIER_CAP_GBP_ENV, "0.05")
    monkeypatch.setenv(harbor_runtime.JUDGE_VERIFIER_INPUT_PRICE_ENV, "0.10")
    monkeypatch.setenv(harbor_runtime.JUDGE_VERIFIER_TRANSPORT_ENV, "mystery")
    with pytest.raises(RuntimeError, match=harbor_runtime.JUDGE_VERIFIER_TRANSPORT_ENV):
        harbor_runtime.build_selected_judge_v3_verifier()

