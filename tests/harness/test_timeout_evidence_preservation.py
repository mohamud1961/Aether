from aether.kernel import AetherNextKernel
from aether.ledger import ExecutionLedger, Receipt
from aether.result_metrics import run_metrics_for_row
from aether.runners.docker_runner import _provider_protocol_validity


def test_interrupted_result_preserves_protocol_error_receipts_and_blocks_protocol_admission() -> None:
    kernel = AetherNextKernel(max_steps=3)
    ledger = ExecutionLedger()
    ledger.record(Receipt(
        receipt_id="step-0:solver_parse_error",
        step=0,
        kind="solver_parse_error",
        success=False,
        summary="multiple distinct assistant outputs",
        failure_class="solver_protocol_error",
        payload={"retry_attempted": True},
    ))
    kernel._active_ledger = ledger
    kernel._active_env_digest = "env-digest"
    kernel._active_step = 1

    result = kernel.interrupted_result(
        status="timeout", blockers=("kernel_timeout_after_60s",),
    )
    metrics = run_metrics_for_row(result)
    provider_valid, protocol_valid = _provider_protocol_validity(
        record_error="",
        classifier_label="timeout_resource_failure",
        model_parse_errors=list(metrics["model_parse_errors"]),
    )

    assert result.status == "timeout"
    assert result.step == 1
    assert result.env_digest == "env-digest"
    assert len(result.receipts) == 1
    assert metrics["solver_parse_error_count"] == 1
    assert metrics["parse_repair_attempts"] == 1
    assert metrics["solver_parse_error_examples"][0]["failure_class"] == "solver_protocol_error"
    assert provider_valid is True
    assert protocol_valid is False


def test_interrupted_result_preserves_accounting_and_architect_defect() -> None:
    kernel = AetherNextKernel(max_steps=3)
    ledger = ExecutionLedger()
    ledger.record_accounting(
        receipt_id="step-0:solver_provider_turn:1",
        step=0,
        counter="solver_provider_turns",
        event="primary_solver_call",
    )
    kernel._active_ledger = ledger
    kernel._active_step = 2
    kernel._active_reconfigurations = 1
    kernel._active_architect_defect_reasons = ["initial_config_repaired:x"]

    result = kernel.interrupted_result(status="timeout")

    assert result.accounting is not None
    assert result.accounting["solver_provider_turns"] == 1
    assert result.reconfigurations == 1
    assert result.architect_defect is True
    assert result.architect_defect_reasons == ("initial_config_repaired:x",)


def test_provider_item_ambiguity_is_provider_invalid_but_single_message_atomicity_is_not() -> None:
    provider_error = [{
        "error": "solver call failed: provider_persistent_v0_multiple_distinct_semantic_payloads: candidates",
    }]
    provider_valid, protocol_valid = _provider_protocol_validity(
        record_error="", classifier_label="timeout_resource_failure",
        model_parse_errors=provider_error,
    )
    assert provider_valid is False
    assert protocol_valid is False

    atomicity_error = [{
        "error": "solver call failed: provider_persistent_v0_multiple_objects_in_message: candidates",
    }]
    provider_valid, protocol_valid = _provider_protocol_validity(
        record_error="", classifier_label="timeout_resource_failure",
        model_parse_errors=atomicity_error,
    )
    assert provider_valid is True
    assert protocol_valid is False


def test_terminal_provider_failure_is_not_protocol_or_provider_valid() -> None:
    provider_valid, protocol_valid = _provider_protocol_validity(
        record_error="",
        classifier_label="provider_failure",
        model_parse_errors=[],
    )
    assert provider_valid is False
    assert protocol_valid is False
