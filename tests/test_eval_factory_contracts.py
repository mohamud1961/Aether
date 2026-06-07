import json

import pytest

from runner.evaluator import (
    PACKET01_REQUIRED_CONTRACT_CHECKS,
    apply_packet01_guards,
    build_score_envelope,
    can_run_model_smoke,
)
from runner.logger import RunLogger
from runner.model_client import make_codex_subscription_route, make_no_model_route
from runner.schemas import (
    LAYER_IDS,
    SchemaValidationError,
    default_layers,
    validate_model_route,
    validate_score_envelope,
)


def _run_header(tmp_path):
    return {
        "run_id": "run-001",
        "started_at_utc": "2026-04-15T12:00:00Z",
        "task_id": "task-001",
        "benchmark_family": "contract",
        "seed_id": "sc_b_01",
        "block_selection": {
            "orientation": "raw_prompt",
            "tools": "raw_bash",
            "execution": "flat_loop",
            "context": "full_history",
            "verification": "trust_model",
            "recovery": "no_recovery",
        },
        "environment": {
            "sandbox_type": "none",
            "sandbox_image": None,
            "cwd": str(tmp_path),
            "timeout_sec": 60,
        },
        "model_route": make_no_model_route(),
        "scoring_contract": {"scoring_contract_version": "score_envelope.v0"},
    }


def test_run_logger_writes_immutable_header_and_append_only_events(tmp_path):
    logger = RunLogger(tmp_path / "run-001")
    logger.start_run(_run_header(tmp_path))

    first = logger.append_event(phase="orient", event_type="started")
    second = logger.append_event(phase="eval", event_type="contract_checked")

    assert first["seq"] == 0
    assert second["seq"] == 1
    assert [event["seq"] for event in logger.read_events()] == [0, 1]

    with pytest.raises(FileExistsError):
        logger.start_run(_run_header(tmp_path))


def test_run_logger_score_envelope_is_terminal_and_singular(tmp_path):
    logger = RunLogger(tmp_path / "run-001")
    logger.start_run(_run_header(tmp_path))
    logger.append_event(phase="orient", event_type="started")
    envelope = build_score_envelope(
        run_id="run-001",
        benchmark_id="contract",
        case_id="case-001",
    )

    logger.write_score_envelope(envelope)

    with pytest.raises(RuntimeError):
        logger.append_event(phase="eval", event_type="after_score")
    with pytest.raises(FileExistsError):
        logger.write_score_envelope(envelope)


def test_score_envelope_requires_all_layers_and_allowed_enums():
    envelope = build_score_envelope(
        run_id="run-001",
        benchmark_id="contract",
        case_id="case-001",
    )

    assert set(envelope["layers"]) == set(LAYER_IDS)
    assert envelope["aggregate"]["final_verdict"] == "unresolved"
    validate_score_envelope(envelope)

    broken = json.loads(json.dumps(envelope))
    broken["layers"]["L0_inline_assertion"]["status"] = "maybe"

    with pytest.raises(SchemaValidationError):
        validate_score_envelope(broken)


def test_l2_unavailable_cannot_be_substituted_by_l3_pass():
    layers = default_layers()
    layers["L2_replay_or_state_grader"]["status"] = "unavailable"
    layers["L3_judge_layer"]["status"] = "pass"
    layers["L3_judge_layer"]["judge_config"] = {
        "judge_type": "llm_as_judge",
        "model": "judge-model",
        "prompt_fingerprint": "prompt-sha",
        "schema_fingerprint": "schema-sha",
        "mode": "strict",
    }
    envelope = build_score_envelope(
        run_id="run-001",
        benchmark_id="contract",
        case_id="case-001",
        layers=layers,
        final_verdict="pass",
    )

    guarded = apply_packet01_guards(envelope)

    assert guarded["aggregate"]["final_verdict"] == "unresolved"
    assert "L2_replay_or_state_grader" in guarded["aggregate"]["unresolved_layers"]
    assert "replay_data_gap" in guarded["layers"]["L2_replay_or_state_grader"]["reason_codes"]
    assert (
        "l2_unavailable_cannot_be_substituted_by_l3_pass"
        in guarded["aggregate"]["substitution_guard_violations"]
    )


def test_projection_fallback_requires_explicit_reason():
    layers = default_layers()
    layers["L4_final_acceptance"]["status"] = "pass"
    layers["L4_final_acceptance"]["final_gate"] = {
        "gate_type": "projection",
        "gate_value": 1.0,
    }
    envelope = build_score_envelope(
        run_id="run-001",
        benchmark_id="contract",
        case_id="case-001",
        layers=layers,
        final_verdict="pass",
    )

    guarded = apply_packet01_guards(envelope)

    assert guarded["aggregate"]["final_verdict"] == "unresolved"
    assert "final_projection_fallback" in guarded["layers"]["L4_final_acceptance"]["reason_codes"]
    assert (
        "projection_fallback_requires_explicit_reason"
        in guarded["aggregate"]["substitution_guard_violations"]
    )


def test_projection_fallback_with_reason_still_cannot_stay_clean_pass():
    layers = default_layers()
    layers["L4_final_acceptance"]["status"] = "pass"
    layers["L4_final_acceptance"]["final_gate"] = {
        "gate_type": "projection",
        "gate_value": 1.0,
    }
    layers["L4_final_acceptance"]["projection_fallback_reason"] = "verifier temporarily unavailable"
    envelope = build_score_envelope(
        run_id="run-001",
        benchmark_id="contract",
        case_id="case-001",
        layers=layers,
        final_verdict="pass",
    )

    guarded = apply_packet01_guards(envelope)

    assert guarded["aggregate"]["final_verdict"] == "unresolved"
    assert "final_projection_fallback" in guarded["layers"]["L4_final_acceptance"]["reason_codes"]
    assert (
        "projection_fallback_non_promotable_for_packet02"
        in guarded["aggregate"]["substitution_guard_violations"]
    )


def test_missing_verifier_artifact_emits_reason_code():
    layers = default_layers()
    layers["L1_verifier_artifact"]["status"] = "unavailable"
    layers["L4_final_acceptance"]["status"] = "pass"
    envelope = build_score_envelope(
        run_id="run-001",
        benchmark_id="contract",
        case_id="case-001",
        layers=layers,
        final_verdict="pass",
    )

    guarded = apply_packet01_guards(envelope)

    assert guarded["aggregate"]["final_verdict"] == "unresolved"
    assert "verifier_artifact_missing" in guarded["layers"]["L1_verifier_artifact"]["reason_codes"]
    assert (
        "verifier_artifact_missing_cannot_be_hidden_by_l4_pass"
        in guarded["aggregate"]["substitution_guard_violations"]
    )


def test_capture_only_claim_is_blocked_non_promotable():
    envelope = build_score_envelope(
        run_id="run-001",
        benchmark_id="capture",
        case_id="case-001",
        adapter={
            "adapter_id": "capture_reader",
            "adapter_contract_version": "adapter.v0",
            "benchmark_family": "capture_only_terminalbench_notes",
            "case_id": "case-001",
        },
        final_verdict="pass",
    )

    guarded = apply_packet01_guards(envelope)

    assert guarded["aggregate"]["final_verdict"] == "blocked_non_promotable"


def test_active_l3_requires_pinned_judge_config():
    layers = default_layers()
    layers["L3_judge_layer"]["status"] = "pass"
    layers["L3_judge_layer"]["judge_config"] = {
        "judge_type": "llm_as_judge",
        "model": "judge-model",
        "prompt_fingerprint": None,
        "schema_fingerprint": "schema-sha",
        "mode": "strict",
    }
    envelope = build_score_envelope(
        run_id="run-001",
        benchmark_id="contract",
        case_id="case-001",
        layers=layers,
        final_verdict="pass",
    )

    guarded = apply_packet01_guards(envelope)

    assert guarded["aggregate"]["final_verdict"] == "unresolved"
    assert "judge_config_unpinned" in guarded["layers"]["L3_judge_layer"]["reason_codes"]


def test_codex_subscription_route_is_metadata_without_tokens():
    route = make_codex_subscription_route(
        model_name="gpt-5.4-mini",
        request_settings={"temperature": 0, "max_tokens": 256},
    )

    assert route["provider_route"] == "codex_subscription"
    assert route["auth_mode"] == "oauth"
    assert "access_token" not in route
    assert "refresh_token" not in route
    validate_model_route(route)


def test_model_smoke_is_blocked_until_all_contract_checks_pass():
    required = {name: True for name in PACKET01_REQUIRED_CONTRACT_CHECKS}
    assert can_run_model_smoke(required)

    missing_one = dict(required)
    missing_one.pop("l3_pinning_guard")
    assert not can_run_model_smoke(missing_one)

    with_extra = dict(required)
    with_extra["extra_check"] = True
    assert not can_run_model_smoke(with_extra)

    with_failure = dict(required)
    with_failure["non_substitution_guard"] = False
    assert not can_run_model_smoke(with_failure)

    assert not can_run_model_smoke({})
