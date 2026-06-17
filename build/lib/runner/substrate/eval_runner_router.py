"""Packet 03 eval-card routing and execution-mode normalization."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from runner.model_client import (
    make_azure_gpt53_codex_route_from_env,
    make_azure_gpt54_mini_route_from_env,
    make_codex_subscription_route,
    make_no_model_route,
)
from runner.packet03_eval_fixtures import get_packet03_eval_lane_policy
from runner.schemas import (
    SchemaValidationError,
    normalize_batch_eligibility,
    normalize_model_tier_policy,
    validate_evaluation_lane,
    validate_execution_mode,
    validate_model_route,
)

ROUTE_REGISTRY: dict[str, dict[str, str]] = {
    "deterministic_no_model": {
        "guardrail_debug": "route.deterministic_no_model.guardrail_debug.v2",
        "bounded_diagnostic": "route.deterministic_no_model.bounded_diagnostic.v2",
        "promotion": "route.deterministic_no_model.promotion.v2",
    },
    "one_shot_batchable": {
        "guardrail_debug": "route.one_shot_batchable.guardrail_debug.v2",
        "bounded_diagnostic": "route.one_shot_batchable.bounded_diagnostic.v2",
        "promotion": "route.one_shot_batchable.promotion.v2",
    },
    "multistep_batchable": {
        "guardrail_debug": "route.multistep_batchable.guardrail_debug.v2",
        "bounded_diagnostic": "route.multistep_batchable.bounded_diagnostic.v2",
        "promotion": "route.multistep_batchable.promotion.v2",
    },
    "sync_interactive": {
        "guardrail_debug": "route.sync_interactive.guardrail_debug.v2",
        "bounded_diagnostic": "route.sync_interactive.bounded_diagnostic.v2",
        "promotion": "route.sync_interactive.promotion.v2",
    },
    "offline_judge_batchable": {
        "guardrail_debug": "route.offline_judge_batchable.guardrail_debug.v2",
        "bounded_diagnostic": "route.offline_judge_batchable.bounded_diagnostic.v2",
        "promotion": "route.offline_judge_batchable.promotion.v2",
    },
}
MODEL_TIER_SELECTORS = frozenset({"screening_default", "screening_fallback", "promotion_tier"})


def _require_mapping(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SchemaValidationError(f"{path} must be an object")
    return value


def _require_string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value:
        raise SchemaValidationError(f"{path} must be a non-empty string")
    return value


def get_route_registry() -> dict[str, dict[str, str]]:
    return deepcopy(ROUTE_REGISTRY)


def normalize_eval_card(eval_card: dict[str, Any]) -> dict[str, Any]:
    card = _require_mapping(eval_card, "eval_card")
    eval_id = _require_string(card.get("eval_id"), "eval_card.eval_id")
    execution_mode = validate_execution_mode(card.get("execution_mode"), "eval_card.execution_mode")
    batch_eligibility = normalize_batch_eligibility(card.get("batch_eligibility"), "eval_card.batch_eligibility")
    try:
        lane_policy = get_packet03_eval_lane_policy(eval_id)
    except ValueError as err:
        raise SchemaValidationError(str(err)) from err
    evaluation_lane = _resolve_eval_card_lane(
        card=card,
        eval_id=eval_id,
        lane_policy=lane_policy,
    )
    lane_blocker_codes = _normalize_lane_blockers(
        card_blockers=card.get("lane_blocker_codes"),
        policy_blockers=lane_policy["promotion_blocker_codes"],
    )
    promotion_authority = evaluation_lane == "promotion"
    if promotion_authority and lane_blocker_codes:
        raise SchemaValidationError(
            f"eval_card.{eval_id} cannot run in promotion lane with blockers: {lane_blocker_codes}"
        )
    model_tier_policy = normalize_model_tier_policy(
        card.get("model_tier_policy"),
        execution_mode=execution_mode,
    )
    normalized = dict(card)
    normalized["eval_id"] = eval_id
    normalized["execution_mode"] = execution_mode
    normalized["batch_eligibility"] = batch_eligibility
    normalized["evaluation_lane"] = evaluation_lane
    normalized["promotion_authority"] = promotion_authority
    normalized["lane_blocker_codes"] = lane_blocker_codes
    normalized["model_tier_policy"] = model_tier_policy
    return normalized


def route_eval_card(eval_card: dict[str, Any], *, batch_lane: str | None = None) -> dict[str, Any]:
    card = normalize_eval_card(eval_card)
    lane = card["evaluation_lane"]
    if batch_lane is not None:
        normalized_batch_lane = validate_evaluation_lane(batch_lane, "batch_lane")
        if lane != normalized_batch_lane:
            raise SchemaValidationError(
                f"eval_card.{card['eval_id']} lane mismatch: card={lane} batch={normalized_batch_lane}"
            )
    route_id = ROUTE_REGISTRY[card["execution_mode"]][lane]
    return {
        "eval_id": card["eval_id"],
        "execution_mode": card["execution_mode"],
        "batch_eligibility": card["batch_eligibility"],
        "evaluation_lane": lane,
        "promotion_authority": card["promotion_authority"],
        "lane_blocker_codes": list(card["lane_blocker_codes"]),
        "route_id": route_id,
        "model_tier_policy": card["model_tier_policy"],
        "eval_card": card,
    }


def _resolve_eval_card_lane(
    *,
    card: dict[str, Any],
    eval_id: str,
    lane_policy: dict[str, Any],
) -> str:
    explicit_lane = card.get("evaluation_lane")
    if explicit_lane is None:
        explicit_lane = lane_policy["default_evaluation_lane"]
    return validate_evaluation_lane(explicit_lane, "eval_card.evaluation_lane")


def _normalize_lane_blockers(*, card_blockers: Any, policy_blockers: list[str]) -> list[str]:
    blockers = set(policy_blockers)
    if card_blockers is None:
        return sorted(blockers)
    if not isinstance(card_blockers, list):
        raise SchemaValidationError("eval_card.lane_blocker_codes must be a list when provided")
    for index, blocker in enumerate(card_blockers):
        if not isinstance(blocker, str) or not blocker:
            raise SchemaValidationError(f"eval_card.lane_blocker_codes[{index}] must be a non-empty string")
        blockers.add(blocker)
    return sorted(blockers)


def resolve_model_route_for_route(
    resolved_route: dict[str, Any],
    *,
    override_model_route: dict[str, Any] | None = None,
    model_policy_override: dict[str, Any] | None = None,
    model_tier_selector: str = "screening_default",
) -> dict[str, Any]:
    route_data = _require_mapping(resolved_route, "resolved_route")
    execution_mode = validate_execution_mode(route_data.get("execution_mode"), "resolved_route.execution_mode")
    if override_model_route is not None:
        return validate_model_route(dict(override_model_route))
    if execution_mode == "deterministic_no_model":
        return make_no_model_route()
    if model_tier_selector not in MODEL_TIER_SELECTORS:
        raise SchemaValidationError(
            f"resolved_route.model_tier_selector must be one of {sorted(MODEL_TIER_SELECTORS)}"
        )
    policy_source = model_policy_override if model_policy_override is not None else route_data.get("model_tier_policy")
    policy = _require_mapping(policy_source, "resolved_route.model_tier_policy")
    model_tier_value = _require_string(
        policy.get(model_tier_selector), f"resolved_route.model_tier_policy.{model_tier_selector}"
    )
    if model_tier_value == "no_model":
        return make_no_model_route()
    if model_tier_value.startswith("oauth:"):
        model_name = model_tier_value.split("oauth:", 1)[1]
        return make_codex_subscription_route(model_name=model_name)
    if model_tier_value.startswith("azure:"):
        azure_model_tier = model_tier_value.split("azure:", 1)[1]
        if azure_model_tier == "gpt-5.4-mini":
            return make_azure_gpt54_mini_route_from_env()
        if azure_model_tier == "gpt-5.3-codex":
            return make_azure_gpt53_codex_route_from_env()
        raise SchemaValidationError(
            "resolved_route.model_tier_policy contains unsupported azure model tier; "
            "expected azure:gpt-5.4-mini or azure:gpt-5.3-codex"
        )
    model_name = model_tier_value
    if not model_name:
        raise SchemaValidationError(f"resolved_route.model_tier_policy.{model_tier_selector} must contain a model name")
    return make_codex_subscription_route(model_name=model_name)
