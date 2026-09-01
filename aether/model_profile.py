"""Immutable model/runtime treatment profiles.

Production owns one explicit profile. Research may construct alternate profiles
outside the production package and inject them deliberately, but raw tasks and
environment facts cannot select or mutate a profile.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from hashlib import sha256
import json
import os
from typing import Any


API_KEY_CREDENTIAL_MODE = "api_key"
SYSTEM_ASSIGNED_MANAGED_IDENTITY_CREDENTIAL_MODE = "system_assigned_managed_identity"


@dataclass(frozen=True)
class ModelProfile:
    schema_version: str
    profile_id: str
    model_id: str
    deployment_env: str
    endpoint_env: str
    key_env: str
    solver_reasoning_effort: str
    verifier_reasoning_effort: str
    solver_reanchor_mode: str
    responses_background: bool
    prompt_cache_mode: str
    solver_max_output_tokens: int | None
    verifier_max_output_tokens: int | None
    provider_poll_interval_s: int
    provider_poll_timeout_s: int
    provider_max_retries: int
    provider_sdk_max_retries: int
    solver_turn_budget: int | None
    credential_mode: str = API_KEY_CREDENTIAL_MODE
    responses_websocket: bool = False
    responses_websocket_persistent: bool = False
    api_mode: str = "responses"
    chat_capacity_reanchor_recovery_mode: str = "off"
    chat_capacity_overflow_action: str = "reanchor"
    expected_returned_model: str | None = None

    def manifest(self) -> dict[str, Any]:
        """Public profile record: execution treatment plus descriptive identity."""
        payload = asdict(self)
        # Credential *values* never enter the profile. The key environment name
        # is deployment wiring rather than evidence and is excluded from the
        # public/sealed manifest to avoid encouraging credential propagation.
        payload.pop("key_env", None)
        # Keep the historical API-key production hash stable. Any explicit
        # non-default credential source is execution identity and remains
        # covered by the research profile hash.
        if payload.get("credential_mode") == API_KEY_CREDENTIAL_MODE:
            payload.pop("credential_mode", None)
        # Default-off research treatments do not perturb the qualified
        # production manifest/hash until explicitly enabled.
        if not payload.get("responses_websocket_persistent", False):
            payload.pop("responses_websocket_persistent", None)
        if payload.get("api_mode") == "responses":
            payload.pop("api_mode", None)
        if payload.get("chat_capacity_reanchor_recovery_mode") == "off":
            payload.pop("chat_capacity_reanchor_recovery_mode", None)
        # Keep the pre-existing control profile identity stable. Research modes
        # can select an explicit overflow action such as M-TREE's epoch failure.
        if payload.get("chat_capacity_overflow_action") == "reanchor":
            payload.pop("chat_capacity_overflow_action", None)
        if payload.get("expected_returned_model") is None:
            payload.pop("expected_returned_model", None)
        return payload

    def treatment_manifest(self) -> dict[str, Any]:
        """Return only positive executable treatment controls.

        S5 intentionally has one fixed implementation topology. Fixed transport,
        continuity, context-projection and tool-schema identity are derived from
        the installed implementation rather than duplicated here. This treatment
        manifest contains only values that positively configure execution.
        """
        payload = self.manifest()
        # Expected model identity belongs to the separately sealed route hash.
        for key in ("schema_version", "profile_id", "model_id", "expected_returned_model"):
            payload.pop(key, None)
        return {key: value for key, value in payload.items() if value is not None}

    def sha256(self) -> str:
        encoded = json.dumps(
            self.treatment_manifest(), sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("utf-8")
        return sha256(encoded).hexdigest()

    def route_identity_sha256(self, *, selector: str, endpoint: str, deployment: str) -> str:
        """Bind route evidence separately from the model-treatment hash."""
        route = {
            "schema": "aether.model_route_identity.v1",
            "selector": str(selector),
            "profile_id": self.profile_id,
            "model_id": self.model_id,
            "endpoint": str(endpoint),
            "deployment": str(deployment),
            "expected_returned_model": self.expected_returned_model or self.model_id,
        }
        encoded = json.dumps(route, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return sha256(encoded.encode("utf-8")).hexdigest()

PROVIDER_CALLS_ALLOWED_ENV = "AETHER_PROVIDER_CALLS_ALLOWED"
PROVIDER_PROFILE_SHA256_ENV = "AETHER_PROVIDER_PROFILE_SHA256"


def require_provider_authorization(profile: "ModelProfile") -> None:
    """Fail before credential reads unless the one-task launcher authorized calls."""
    allowed = str(os.environ.get(PROVIDER_CALLS_ALLOWED_ENV, "") or "").strip()
    if allowed != "1":
        raise RuntimeError("provider calls are not authorized by the Aether launch boundary")
    bound = str(os.environ.get(PROVIDER_PROFILE_SHA256_ENV, "") or "").strip().lower()
    expected = profile.sha256()
    if bound != expected:
        raise RuntimeError("provider authorization profile hash does not match production profile")


PRODUCTION_PROFILE = ModelProfile(
    schema_version="aether.model_profile.v1",
    profile_id="production-persistent-v1",
    model_id="gpt-5.6-luna",
    deployment_env="AZURE_OPENAI_GPT56_FRONTIER_DEPLOYMENT",
    endpoint_env="AZURE_OPENAI_GPT56_FRONTIER_ENDPOINT",
    key_env="AZURE_OPENAI_GPT56_FRONTIER_KEY",
    solver_reasoning_effort="max",
    verifier_reasoning_effort="max",
    solver_reanchor_mode="continuity_fresh_delta_v1",
    # Azure currently rejects local function_call_output continuation from
    # completed background Responses even with store=true. The selected S5
    # native previous_response tool loop therefore uses stored foreground
    # Responses until that provider defect is removed and independently
    # requalified.
    responses_background=False,
    prompt_cache_mode="off",
    solver_max_output_tokens=None,
    verifier_max_output_tokens=None,
    provider_poll_interval_s=10,
    provider_poll_timeout_s=1200,
    provider_max_retries=1,
    provider_sdk_max_retries=0,
    solver_turn_budget=None,
    responses_websocket=True,
    responses_websocket_persistent=True,
)

# Explicit research successor, never selected by task text or ambient provider
# flags. The frozen production profile and its historical hash are unchanged.
GLM_RESEARCH_PROFILE = ModelProfile(
    schema_version="aether.model_profile.v1", profile_id="glm-chat-judge-research-v1",
    model_id="FW-GLM-5.3-Flash",
    deployment_env="AETHER_FW_GLM_53_FLASH_DEPLOYMENT",
    endpoint_env="AETHER_FW_GLM_53_FLASH_ENDPOINT",
    key_env="AETHER_FW_GLM_53_FLASH_KEY",
    solver_reasoning_effort="max", verifier_reasoning_effort="max",
    solver_reanchor_mode="current_full", responses_background=False,
    # P3 trace-first default. This is a per-call failsafe ceiling, not an
    # expected turn length or an optimized reasoning target. Long turns are
    # investigated semantically; do not silently revert research rows to 24,576
    # or 16,384 (16,384 truncated a measured GLM turn that 32,768 completed).
    prompt_cache_mode="off", solver_max_output_tokens=32768,
    verifier_max_output_tokens=12000, provider_poll_interval_s=1,
    # Provider timeout is deliberately aligned with the task-owned 1800s
    # research wall budget. Shorter inner ceilings (first 450s, then 1200s)
    # manufactured infrastructure-invalid rows on legal 32k->65k synthesis
    # calls. Timeouts remain outcome-ambiguous and are NOT retried; bounded
    # retries apply only to known pre-response 429/5xx/connection failures.
    provider_poll_timeout_s=1800, provider_max_retries=2,
    provider_sdk_max_retries=0,
    # P1/P2 GLM mechanics are wall-clock governed. Historical held-out rows
    # retain their own explicit 32-turn runner/budget limits.
    solver_turn_budget=None,
    api_mode="chat_completions",
    # P1 initial rollover treatment: retain the exact trailing four complete
    # assistant/action/result exchanges at a throughput-capacity boundary.
    # If those four cannot fit, admission fails rather than silently shrinking.
    chat_capacity_reanchor_recovery_mode="recent_exchanges_v1",
)

# The PAR route is a selectable candidate for preparation. Its account,
# endpoint, deployment, and quota still require the separately gated A6.5
# qualification; defining this identity is not evidence that the route exists.
GLM_RESEARCH_PAR_PROFILE = replace(
    GLM_RESEARCH_PROFILE,
    profile_id="glm-chat-judge-research-par-v1",
    model_id="FW-GLM-5.3-Flash-par",
    expected_returned_model="FW-GLM-5.3-Flash",
)
GLM_RESEARCH_PAR2_PROFILE = replace(
    GLM_RESEARCH_PROFILE,
    profile_id="glm-chat-judge-research-par2-v1",
    model_id="FW-GLM-5.3-Flash-par-2",
    expected_returned_model="FW-GLM-5.3-Flash",
)
GLM_RESEARCH_PROFILES = {
    "glm-research-v1": GLM_RESEARCH_PROFILE,
    "glm-research-par-v1": GLM_RESEARCH_PAR_PROFILE,
    "glm-research-par2-v1": GLM_RESEARCH_PAR2_PROFILE,
}

# Local admission defaults only. Preserve the existing conservative batch caps
# until route-specific rates are observed and qualified; these are not claims
# about the provider's provisioned quotas.
GLM_RESEARCH_LOCAL_ADMISSION_DEFAULTS = {
    "glm-research-v1": (100_000, 100),
    "glm-research-par-v1": (100_000, 100),
    "glm-research-par2-v1": (100_000, 100),
}
