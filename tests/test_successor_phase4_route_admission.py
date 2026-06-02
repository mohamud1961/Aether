from runner.packet04_route_manifest import (
    BASELINE_VARIANT_ID,
    PACKET06_PHASE2_ENV_TOOLING_SCOPE,
    build_packet04_route_manifest,
    get_allowed_packet04_variants,
    load_runtime_callables,
    validate_independent_candidate_routing,
)


def _changed_runtime_keys(manifest):
    return {row["runtime_key"] for row in manifest["routed_modules"] if row["claimed_changed_surface"]}


def test_phase4_required_challengers_are_narrowly_admitted():
    allowed = get_allowed_packet04_variants(scope=PACKET06_PHASE2_ENV_TOOLING_SCOPE)
    expected = {
        "spb_tooling_seed_plus_receipt_context_01",
        "spb_tooling_seed_plus_completion_gate_01",
        "spb_tooling_seed_plus_receipt_and_completion_01",
    }
    assert expected.issubset(allowed)


def test_phase4_required_challengers_have_bounded_changed_runtime_keys():
    baseline = build_packet04_route_manifest(BASELINE_VARIANT_ID, scope=PACKET06_PHASE2_ENV_TOOLING_SCOPE)
    expected = {
        "spb_tooling_seed_plus_receipt_context_01": {
            "orientation",
            "tools_getter",
            "tool_executor",
            "context",
        },
        "spb_tooling_seed_plus_completion_gate_01": {
            "orientation",
            "tools_getter",
            "tool_executor",
            "verification",
        },
        "spb_tooling_seed_plus_receipt_and_completion_01": {
            "orientation",
            "tools_getter",
            "tool_executor",
            "context",
            "verification",
        },
    }

    for variant_id, changed_keys in expected.items():
        manifest = build_packet04_route_manifest(variant_id, scope=PACKET06_PHASE2_ENV_TOOLING_SCOPE)
        validate_independent_candidate_routing(
            candidate_manifest=manifest,
            baseline_manifest=baseline,
        )
        assert _changed_runtime_keys(manifest) == changed_keys


def test_phase4_required_challengers_exclude_env_snapshot_rhv1_and_orchestration_surfaces():
    for variant_id in (
        "spb_tooling_seed_plus_receipt_context_01",
        "spb_tooling_seed_plus_completion_gate_01",
        "spb_tooling_seed_plus_receipt_and_completion_01",
    ):
        manifest = build_packet04_route_manifest(variant_id, scope=PACKET06_PHASE2_ENV_TOOLING_SCOPE)
        routed_text = "\n".join(
            f"{row['real_file_path']} {row['module_import_path']}" for row in manifest["routed_modules"]
        )

        assert "rhv1_prompt_plan_env" not in routed_text
        assert "evidence_report_scaffold" not in routed_text
        assert "blocks.verification.trust_model:check" not in routed_text
        assert "blocks.recovery.no_recovery:handle_error" not in routed_text
        assert "env_snapshot" not in routed_text
        assert "multi_agent" not in routed_text
        assert "dag" not in routed_text.lower()


def test_phase4_required_challengers_load_runtime_callables():
    for variant_id in (
        "spb_tooling_seed_plus_receipt_context_01",
        "spb_tooling_seed_plus_completion_gate_01",
        "spb_tooling_seed_plus_receipt_and_completion_01",
    ):
        manifest = build_packet04_route_manifest(variant_id, scope=PACKET06_PHASE2_ENV_TOOLING_SCOPE)
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
