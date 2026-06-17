from blocks.tools import spb_tooling_seed
from runner.packet04_route_manifest import (
    BASELINE_VARIANT_ID,
    PACKET06_PHASE2_ENV_TOOLING_SCOPE,
    build_packet04_route_manifest,
    get_allowed_packet04_variants,
    load_runtime_callables,
    validate_independent_candidate_routing,
)


class _Sandbox:
    def __init__(self, payload):
        self._payload = dict(payload)

    def exec(self, command):  # type: ignore[no-untyped-def]
        _ = command
        return dict(self._payload)


def _changed_runtime_keys(manifest):
    return {row["runtime_key"] for row in manifest["routed_modules"] if row["claimed_changed_surface"]}


def test_spb_tooling_seed_is_admitted_only_as_bounded_phase3_tooling_seed():
    assert "spb_tooling_seed_01" in get_allowed_packet04_variants(scope=PACKET06_PHASE2_ENV_TOOLING_SCOPE)

    baseline = build_packet04_route_manifest(BASELINE_VARIANT_ID, scope=PACKET06_PHASE2_ENV_TOOLING_SCOPE)
    seed = build_packet04_route_manifest("spb_tooling_seed_01", scope=PACKET06_PHASE2_ENV_TOOLING_SCOPE)

    validate_independent_candidate_routing(candidate_manifest=seed, baseline_manifest=baseline)
    assert _changed_runtime_keys(seed) == {"orientation", "tools_getter", "tool_executor"}


def test_spb_tooling_seed_route_excludes_rhv1_env_snapshot_and_orchestration_surfaces():
    seed = build_packet04_route_manifest("spb_tooling_seed_01", scope=PACKET06_PHASE2_ENV_TOOLING_SCOPE)
    routed_text = "\n".join(
        f"{row['real_file_path']} {row['module_import_path']}" for row in seed["routed_modules"]
    )

    assert "rhv1_prompt_plan_env" not in routed_text
    assert "evidence_report_scaffold" not in routed_text
    assert "blocks.verification.trust_model:check" not in routed_text
    assert "blocks.recovery.no_recovery:handle_error" not in routed_text
    assert "env_snapshot" not in routed_text
    assert "multi_agent" not in routed_text
    assert "dag" not in routed_text.lower()


def test_spb_tooling_seed_runtime_callables_load_for_contract_validation():
    seed = build_packet04_route_manifest("spb_tooling_seed_01", scope=PACKET06_PHASE2_ENV_TOOLING_SCOPE)
    callables = load_runtime_callables(seed)

    assert callable(callables["orientation"])
    assert callable(callables["tools_getter"])
    assert callable(callables["tool_executor"])


def test_spb_tooling_seed_emits_contract_class_and_structured_receipt_fields():
    malformed = spb_tooling_seed.execute_tool_call(
        {"name": "raw_bash", "arguments": "not-json", "case_id": "malformed"},
        _Sandbox({"exit_code": 0, "stdout": "", "stderr": "", "timed_out": False}),
    )
    permission = spb_tooling_seed.execute_tool_call(
        {"name": "raw_bash", "arguments": {"command": "cat /root/secret"}, "case_id": "permission"},
        _Sandbox({"exit_code": 126, "stdout": "", "stderr": "Permission denied", "timed_out": False}),
    )

    assert malformed["tool_call_contract_class"] == "malformed_call"
    assert malformed["result_class"] == "contract_error"
    assert malformed["tool_result_receipt"]["reason_code"] == "tool_call_contract_malformed"

    assert permission["tool_call_contract_class"] == "valid_call"
    assert permission["result_class"] == "permission_denied"
    assert permission["reason_code"] == "tool_permission_denied"
    assert permission["attribution_trace"]["permission_signal_detected"] is True
    assert permission["tool_result_receipt"]["attribution_trace"]["permission_signal_detected"] is True
