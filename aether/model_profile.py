"""Immutable model/runtime treatment profiles.

Production owns one explicit profile. Research may construct alternate profiles
outside the production package and inject them deliberately, but raw tasks and
environment facts cannot select or mutate a profile.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import os
from typing import Any


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
    responses_websocket: bool = False

    def manifest(self) -> dict[str, Any]:
        """Public profile record: execution treatment plus descriptive identity."""
        payload = asdict(self)
        # Credential *values* never enter the profile. The key environment name
        # is deployment wiring rather than evidence and is excluded from the
        # public/sealed manifest to avoid encouraging credential propagation.
        payload.pop("key_env", None)
        return payload

    def treatment_manifest(self) -> dict[str, Any]:
        """Return only positive executable treatment controls.

        S5 intentionally has one fixed implementation topology. Fixed transport,
        continuity, context-projection and tool-schema identity are derived from
        the installed implementation rather than duplicated here. This treatment
        manifest contains only values that positively configure execution.
        """
        payload = self.manifest()
        for key in ("schema_version", "profile_id", "model_id"):
            payload.pop(key, None)
        return {key: value for key, value in payload.items() if value is not None}

    def sha256(self) -> str:
        encoded = json.dumps(
            self.treatment_manifest(), sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("utf-8")
        return sha256(encoded).hexdigest()

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
    profile_id="production-pcr-v1",
    model_id="gpt-5.6-luna",
    deployment_env="AZURE_OPENAI_GPT56_LUNA_DEPLOYMENT",
    endpoint_env="AZURE_OPENAI_GPT56_LUNA_ENDPOINT",
    key_env="AZURE_OPENAI_GPT56_LUNA_KEY",
    solver_reasoning_effort="high",
    verifier_reasoning_effort="low",
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
)
