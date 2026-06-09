import importlib

import pytest

PACKET03_ALLOWED_EXECUTION_MODES = {
    "deterministic_no_model",
    "one_shot_batchable",
    "multistep_batchable",
    "sync_interactive",
    "offline_judge_batchable",
}

PACKET03_DEFAULT_MODEL_TIER_POLICY = {
    "screening_default": "oauth:gpt-5.4-nano",
    "screening_fallback": "oauth:gpt-5.4-mini",
    "promotion_tier": "gpt-5.3-codex",
}


def _load_router_module():
    try:
        return importlib.import_module("runner.eval_runner_router")
    except ModuleNotFoundError as exc:
        pytest.fail(
            "Packet 03 router module is missing: expected runner.eval_runner_router "
            f"to exist for router contract tests ({exc})."
        )


def _resolve_route_eval_card(router_module):
    for name in ("route_eval_card", "route_eval", "resolve_eval_route"):
        candidate = getattr(router_module, name, None)
        if callable(candidate):
            return candidate
    pytest.fail(
        "Packet 03 router does not expose a callable route resolver "
        "(expected one of: route_eval_card, route_eval, resolve_eval_route)."
    )


def _canonical_eval_card(
    *,
    execution_mode="one_shot_batchable",
    batch_eligibility=True,
    model_tier_policy=None,
):
    return {
        "eval_id": "ae_tool_call_shape_argument_contract",
        "block_family": "af_tool_gateway_argument_result_contract",
        "execution_mode": execution_mode,
        "batch_eligibility": batch_eligibility,
        "model_tier_policy": model_tier_policy or dict(PACKET03_DEFAULT_MODEL_TIER_POLICY),
        "task_fixture_set": "packet03_smoke_fixture_set_v1",
        "rerun_policy": {"count": 3},
        "fixed_invariants": {"grader_version": "grader.v1"},
        "stability_metric_tuple": {
            "pass_rate_spread": 0.0,
            "contradiction_rate_spread": 0.0,
            "token_cost_spread": 0.0,
        },
        "stability_pass_rule": "max_spread_le_0.05",
        "batch_result_schema_ref": "packet03.result_record.v1",
    }


def _extract_mode_registry(router_module):
    for attr in ("ALLOWED_EXECUTION_MODES", "EXECUTION_MODES", "SUPPORTED_EXECUTION_MODES"):
        value = getattr(router_module, attr, None)
        if isinstance(value, (set, tuple, list)):
            return set(value)

    route_registry = getattr(router_module, "ROUTE_REGISTRY", None)
    if isinstance(route_registry, dict):
        key_set = set(route_registry.keys())
        if PACKET03_ALLOWED_EXECUTION_MODES.issubset(key_set):
            return key_set
    return None


def test_execution_mode_taxonomy_is_exact_four_mode_set():
    router_module = _load_router_module()
    modes = _extract_mode_registry(router_module)
    assert modes is not None, "Router must expose an explicit execution-mode registry."
    assert modes == PACKET03_ALLOWED_EXECUTION_MODES


def test_router_rejects_unknown_execution_mode():
    router_module = _load_router_module()
    route_eval_card = _resolve_route_eval_card(router_module)
    invalid = _canonical_eval_card(execution_mode="interactive_plus_judge")

    with pytest.raises(Exception):
        route_eval_card(invalid)


def test_packet03_default_screening_ladder_is_accepted():
    router_module = _load_router_module()
    route_eval_card = _resolve_route_eval_card(router_module)
    routed = route_eval_card(_canonical_eval_card())

    assert routed is not None


def test_router_rejects_free_form_model_tier_policy_strings():
    router_module = _load_router_module()
    route_eval_card = _resolve_route_eval_card(router_module)
    invalid = _canonical_eval_card(model_tier_policy="cheap_then_best_effort")

    with pytest.raises(Exception):
        route_eval_card(invalid)


def test_router_rejects_non_boolean_batch_eligibility():
    router_module = _load_router_module()
    route_eval_card = _resolve_route_eval_card(router_module)
    invalid = _canonical_eval_card(batch_eligibility="true")

    with pytest.raises(Exception):
        route_eval_card(invalid)
