from runner.packet04_route_manifest import (
    PACKET06_PHASE2_ENV_TOOLING_SCOPE,
    build_packet04_route_manifest,
    get_allowed_packet04_variants,
    load_runtime_callables,
    validate_independent_candidate_routing,
)


def test_autonomy_continuation_variants_are_narrowly_admitted():
    allowed = get_allowed_packet04_variants(scope=PACKET06_PHASE2_ENV_TOOLING_SCOPE)
    expected = {
        "spb_env_snapshot_seed_01",
        "spb_receipt_context_seed_01",
        "spb_completion_gate_seed_01",
        "spb_trace_learning_seed_01",
    }
    assert expected.issubset(allowed)


def test_autonomy_continuation_variants_load_and_route_independently():
    baseline = build_packet04_route_manifest("sc_b_01", scope=PACKET06_PHASE2_ENV_TOOLING_SCOPE)
    for variant_id in (
        "spb_env_snapshot_seed_01",
        "spb_receipt_context_seed_01",
        "spb_completion_gate_seed_01",
        "spb_trace_learning_seed_01",
    ):
        manifest = build_packet04_route_manifest(variant_id, scope=PACKET06_PHASE2_ENV_TOOLING_SCOPE)
        validate_independent_candidate_routing(
            candidate_manifest=manifest,
            baseline_manifest=baseline,
        )
        callables = load_runtime_callables(manifest)
        assert set(callables) == {
            "orientation",
            "tools_getter",
            "tool_executor",
            "execution",
            "context",
            "verification",
            "recovery",
            "terminal_guard",
        }
