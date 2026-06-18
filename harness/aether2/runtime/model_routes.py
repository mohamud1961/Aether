"""Model-client boundary and provider-route metadata."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Protocol
from urllib import parse as urllib_parse

from harness.aether2.runtime.route_schemas import validate_model_route
from harness.aether2.runtime.model_response_normalizers import (
    _extract_instructions,
    _extract_text_and_tool_calls,
    _first_string,
    _normalize_azure_chat_result,
    _normalize_azure_responses_result,
    _normalize_chat_completions_tools,
    _normalize_chat_messages,
    _normalize_history_tool_calls,
    _normalize_input_messages,
    _normalize_request_tools,
    _normalize_tool_call,
)
from harness.aether2.runtime.model_route_helpers import (
    _TPM_PACER_SETTING_KEYS,
    _as_bool,
    _as_non_negative_float,
    _as_optional_positive_int,
    _as_positive_float,
    _as_positive_int,
    _bool_env,
    _extract_tpm_pacer_options,
    _maybe_wrap_tpm_pacer,
    _model_route_pacer_scope,
    _required_env_var,
    _route_without_tpm_pacer_settings,
)

TRANSIENT_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
AZURE_OPENAI_DEFAULT_API_VERSION = "2024-12-01-preview"
AZURE_ROUTE_MODEL_TIERS = frozenset({"gpt-5.4-mini", "gpt-5.3-codex"})

AZURE_ENV_ENDPOINT = "AZURE_OPENAI_ENDPOINT"
AZURE_ENV_API_VERSION = "AZURE_OPENAI_API_VERSION"
AZURE_ENV_GPT54_MINI_KEY = "AZURE_OPENAI_GPT54_MINI_KEY"
AZURE_ENV_GPT54_MINI_DEPLOYMENT = "AZURE_OPENAI_GPT54_MINI_DEPLOYMENT"
AZURE_ENV_GPT53_CODEX_KEY = "AZURE_OPENAI_GPT53_CODEX_KEY"
AZURE_ENV_GPT53_CODEX_DEPLOYMENT = "AZURE_OPENAI_GPT53_CODEX_DEPLOYMENT"


class ModelClientError(RuntimeError):
    """Raised when a model client cannot return a normalized completion."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        response_body: str | None = None,
        response_headers: dict[str, str] | None = None,
        error_kind: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body
        self.response_headers = dict(response_headers or {})
        self.error_kind = error_kind
        self.metadata = dict(metadata or {})

    @property
    def details(self) -> dict[str, Any]:
        details: dict[str, Any] = {"message": str(self)}
        if self.error_kind:
            details["error_kind"] = self.error_kind
        if isinstance(self.status_code, int):
            details["status_code"] = self.status_code
        if isinstance(self.response_body, str) and self.response_body:
            details["response_body"] = self.response_body
        if self.response_headers:
            details["response_headers"] = dict(self.response_headers)
        if self.metadata:
            details["metadata"] = dict(self.metadata)
        return details


class ModelClient(Protocol):
    @property
    def route(self) -> dict[str, Any]:
        ...

    def complete(self, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        ...


def settings_fingerprint(settings: dict[str, Any]) -> str:
    payload = json.dumps(settings, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def make_model_route(
    *,
    model_client_id: str,
    provider_route: str,
    model_name: str,
    adapter_id: str,
    auth_mode: str = "none",
    provider_scope: str = "local_dev",
    api_base: str | None = None,
    request_settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    settings = request_settings or {}
    route = {
        "model_client_id": model_client_id,
        "provider_route": provider_route,
        "provider_scope": provider_scope,
        "adapter_id": adapter_id,
        "model_name": model_name,
        "api_base": api_base,
        "auth_mode": auth_mode,
        "request_settings": settings,
        "request_settings_fingerprint": settings_fingerprint(settings),
    }
    return validate_model_route(route)


def make_no_model_route() -> dict[str, Any]:
    return make_model_route(
        model_client_id="none",
        provider_route="none",
        model_name="none",
        adapter_id="no_model",
        auth_mode="none",
    )


def make_azure_openai_route(
    *,
    endpoint: str,
    deployment: str,
    api_key_env_var: str,
    pricing_model_id: str,
    api_version: str = AZURE_OPENAI_DEFAULT_API_VERSION,
    request_settings: dict[str, Any] | None = None,
    provider_scope: str = "local_dev",
) -> dict[str, Any]:
    endpoint_value = endpoint.strip().rstrip("/")
    deployment_value = deployment.strip()
    key_env_value = api_key_env_var.strip()
    api_version_value = api_version.strip() or AZURE_OPENAI_DEFAULT_API_VERSION
    pricing_model_value = pricing_model_id.strip()
    if not endpoint_value:
        raise ValueError("Azure route requires a non-empty endpoint")
    if not deployment_value:
        raise ValueError("Azure route requires a non-empty deployment")
    if not key_env_value:
        raise ValueError("Azure route requires a non-empty api_key_env_var")
    if pricing_model_value not in AZURE_ROUTE_MODEL_TIERS:
        raise ValueError(f"unsupported Azure pricing_model_id: {pricing_model_value}")

    settings = dict(request_settings or {})
    settings["azure_endpoint"] = endpoint_value
    settings["azure_deployment"] = deployment_value
    settings["api_key_env_var"] = key_env_value
    settings["pricing_model_id"] = pricing_model_value

    api_surface = "deployment_chat_completions"
    api_base = (
        f"{endpoint_value}/openai/deployments/"
        f"{urllib_parse.quote(deployment_value, safe='')}/chat/completions"
    )
    if pricing_model_value == "gpt-5.3-codex":
        api_surface = "v1_responses"
        api_base = f"{endpoint_value}/openai/v1/responses"
    else:
        settings["azure_api_version"] = api_version_value
    settings["azure_api_surface"] = api_surface

    return make_model_route(
        model_client_id="azure_openai_api_key",
        provider_route="openai_api",
        model_name=deployment_value,
        adapter_id="azure_openai_chat_completions_api_key",
        auth_mode="api_key",
        provider_scope=provider_scope,
        api_base=api_base,
        request_settings=settings,
    )


def make_azure_gpt54_mini_route_from_env(
    *,
    request_settings: dict[str, Any] | None = None,
    provider_scope: str = "local_dev",
) -> dict[str, Any]:
    endpoint = _required_env_var(AZURE_ENV_ENDPOINT)
    deployment = _required_env_var(AZURE_ENV_GPT54_MINI_DEPLOYMENT)
    _required_env_var(AZURE_ENV_GPT54_MINI_KEY)
    api_version = os.environ.get(AZURE_ENV_API_VERSION, AZURE_OPENAI_DEFAULT_API_VERSION)
    return make_azure_openai_route(
        endpoint=endpoint,
        deployment=deployment,
        api_key_env_var=AZURE_ENV_GPT54_MINI_KEY,
        pricing_model_id="gpt-5.4-mini",
        api_version=api_version,
        request_settings=request_settings,
        provider_scope=provider_scope,
    )


def make_azure_gpt53_codex_route_from_env(
    *,
    request_settings: dict[str, Any] | None = None,
    provider_scope: str = "local_dev",
) -> dict[str, Any]:
    endpoint = _required_env_var(AZURE_ENV_ENDPOINT)
    deployment = _required_env_var(AZURE_ENV_GPT53_CODEX_DEPLOYMENT)
    _required_env_var(AZURE_ENV_GPT53_CODEX_KEY)
    api_version = os.environ.get(AZURE_ENV_API_VERSION, AZURE_OPENAI_DEFAULT_API_VERSION)
    return make_azure_openai_route(
        endpoint=endpoint,
        deployment=deployment,
        api_key_env_var=AZURE_ENV_GPT53_CODEX_KEY,
        pricing_model_id="gpt-5.3-codex",
        api_version=api_version,
        request_settings=request_settings,
        provider_scope=provider_scope,
    )


@dataclass(frozen=True)
class LocalStubModelClient:
    route: dict[str, Any]
    response_text: str = "stub response"
    planned_completions: tuple[dict[str, Any], ...] = ()

    @classmethod
    def create(cls, response_text: str = "stub response") -> "LocalStubModelClient":
        return cls(
            route=make_model_route(
                model_client_id="local_stub",
                provider_route="local_stub",
                model_name="local_stub",
                adapter_id="local_stub",
                auth_mode="none",
            ),
            response_text=response_text,
        )

    def complete(self, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        if self.planned_completions:
            completion = self.planned_completions[0]
            normalized = dict(completion)
            normalized.setdefault("text", "")
            normalized.setdefault("tool_calls", [])
            normalized.setdefault("usage", {"input_messages": len(messages), "output_tokens": 0})
            normalized.setdefault("status", "completed")
            normalized["model_route"] = self.route
            return normalized
        return {
            "text": self.response_text,
            "tool_calls": [],
            "usage": {"input_messages": len(messages), "output_tokens": 0},
            "status": "completed",
            "model_route": self.route,
        }


@dataclass
class AzureOpenAIAPIKeyModelClient:
    route: dict[str, Any]
    timeout_sec: float = 30.0
    max_retries: int = 2
    retry_backoff_sec: float = 0.2

    def __post_init__(self) -> None:
        self.route = validate_model_route(dict(self.route))
        if self.route["provider_route"] != "openai_api":
            raise ValueError("AzureOpenAIAPIKeyModelClient requires provider_route=openai_api")
        if self.route.get("auth_mode") != "api_key":
            raise ValueError("AzureOpenAIAPIKeyModelClient requires auth_mode=api_key")
        if self.route.get("model_client_id") != "azure_openai_api_key":
            raise ValueError("AzureOpenAIAPIKeyModelClient requires model_client_id=azure_openai_api_key")

    def complete(self, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        # litellm is imported lazily so the module loads cleanly when litellm is absent.
        import litellm  # type: ignore[import-not-found]

        route_settings = self.route.get("request_settings") or {}
        route_settings = dict(route_settings) if isinstance(route_settings, dict) else {}

        api_surface = _first_string(route_settings.get("azure_api_surface")) or "deployment_chat_completions"
        deployment = _first_string(route_settings.get("azure_deployment")) or self.route.get("model_name") or ""
        endpoint = _first_string(route_settings.get("azure_endpoint"))
        api_version = (
            _first_string(route_settings.get("azure_api_version")) or AZURE_OPENAI_DEFAULT_API_VERSION
        )
        api_key_env_var = _first_string(route_settings.get("api_key_env_var"))
        if not api_key_env_var:
            raise ModelClientError(
                "azure openai route is missing request_settings.api_key_env_var",
                error_kind="route_error",
            )
        api_key = _first_string(os.environ.get(api_key_env_var))
        if not api_key:
            raise ModelClientError(
                f"missing Azure API key in environment variable {api_key_env_var}",
                error_kind="auth_error",
                metadata={"api_key_env_var": api_key_env_var},
            )
        if not endpoint:
            raise ModelClientError(
                "azure openai route is missing request_settings.azure_endpoint",
                error_kind="route_error",
            )

        tools_input = kwargs.get("tools", route_settings.get("tools", []))
        if api_surface == "v1_responses":
            # Azure Responses API: use normalized flat tools for litellm's chat completions call.
            tools = _normalize_request_tools(tools_input) or None
            normalized_messages = _normalize_input_messages(messages)
        else:
            tools = _normalize_chat_completions_tools(tools_input) or None
            normalized_messages = _normalize_chat_messages(messages)

        # Build extra kwargs from route settings, excluding internal keys.
        _INTERNAL_KEYS = frozenset({
            "azure_endpoint", "azure_api_version", "azure_deployment",
            "api_key_env_var", "pricing_model_id", "azure_api_surface", "tools",
        })
        extra: dict[str, Any] = {
            k: v for k, v in route_settings.items() if k not in _INTERNAL_KEYS
        }
        for key, value in kwargs.items():
            if key not in {"timeout_sec", "max_retries", "tools"}:
                extra[key] = value

        timeout_sec = float(kwargs.get("timeout_sec", self.timeout_sec))
        max_retries = max(0, int(kwargs.get("max_retries", self.max_retries)))

        litellm_kwargs: dict[str, Any] = {
            "model": f"azure/{deployment}",
            "messages": normalized_messages,
            "api_key": api_key,
            "api_base": endpoint,
            "api_version": api_version,
            "timeout": timeout_sec,
            "num_retries": max_retries,
            **extra,
        }
        if tools:
            litellm_kwargs["tools"] = tools

        try:
            response_obj = litellm.completion(**litellm_kwargs)
        except litellm.exceptions.AuthenticationError as exc:
            raise ModelClientError(
                f"azure openai authentication error: {exc}",
                status_code=getattr(exc, "status_code", 401),
                error_kind="auth_error",
                metadata={"deployment": deployment, "api_base": endpoint},
            ) from exc
        except litellm.exceptions.RateLimitError as exc:
            raise ModelClientError(
                f"azure openai rate limit: {exc}",
                status_code=getattr(exc, "status_code", 429),
                error_kind="rate_limit_error",
                metadata={"deployment": deployment, "api_base": endpoint},
            ) from exc
        except litellm.exceptions.ServiceUnavailableError as exc:
            raise ModelClientError(
                f"azure openai service unavailable: {exc}",
                status_code=getattr(exc, "status_code", 503),
                error_kind="service_unavailable_error",
                metadata={"deployment": deployment, "api_base": endpoint},
            ) from exc
        except litellm.exceptions.BadRequestError as exc:
            raise ModelClientError(
                f"azure openai bad request: {exc}",
                status_code=getattr(exc, "status_code", 400),
                error_kind="bad_request_error",
                metadata={"deployment": deployment, "api_base": endpoint},
            ) from exc
        except litellm.exceptions.APIConnectionError as exc:
            raise ModelClientError(
                f"azure openai connection error: {exc}",
                error_kind="network_error",
                metadata={"deployment": deployment, "api_base": endpoint},
            ) from exc
        except litellm.exceptions.Timeout as exc:
            raise ModelClientError(
                f"azure openai request timed out: {exc}",
                error_kind="timeout_error",
                metadata={"deployment": deployment, "api_base": endpoint},
            ) from exc
        except Exception as exc:
            status_code = getattr(exc, "status_code", None)
            if isinstance(status_code, int):
                raise ModelClientError(
                    f"azure openai request failed with status {status_code}: {exc}",
                    status_code=status_code,
                    error_kind="http_error",
                    metadata={"deployment": deployment, "api_base": endpoint},
                ) from exc
            raise ModelClientError(
                f"azure openai request failed: {exc}",
                error_kind="unknown_error",
                metadata={"deployment": deployment, "api_base": endpoint},
            ) from exc

        try:
            response_dict = response_obj.model_dump()
        except AttributeError:
            try:
                response_dict = dict(response_obj)
            except TypeError:
                response_dict = json.loads(response_obj.json())

        if api_surface == "v1_responses":
            return _normalize_azure_responses_result(response=response_dict, model_route=self.route)
        return _normalize_azure_chat_result(response=response_dict, model_route=self.route)


def make_model_client_from_route(model_route: dict[str, Any], **kwargs: Any) -> ModelClient:
    route = validate_model_route(dict(model_route))
    client_kwargs = dict(kwargs)
    pacer_options = _extract_tpm_pacer_options(route, client_kwargs)
    client_route = _route_without_tpm_pacer_settings(route)
    provider_route = route["provider_route"]
    if provider_route == "openai_api":
        if route.get("model_client_id") == "azure_openai_api_key":
            return _maybe_wrap_tpm_pacer(AzureOpenAIAPIKeyModelClient(route=client_route, **client_kwargs), pacer_options)
        raise ValueError(
            "unsupported openai_api model client route; expected model_client_id=azure_openai_api_key"
        )
    if provider_route == "local_stub":
        planned_completions = client_kwargs.get("planned_completions")
        if isinstance(planned_completions, list):
            planned_completions = tuple(
                item for item in planned_completions if isinstance(item, dict)
            )
        else:
            planned_completions = ()
        return LocalStubModelClient(
            route=client_route,
            response_text=client_kwargs.get("response_text", "stub response"),
            planned_completions=planned_completions,
        )
    if provider_route == "none":
        planned_completions = client_kwargs.get("planned_completions")
        if isinstance(planned_completions, list):
            planned_completions = tuple(
                item for item in planned_completions if isinstance(item, dict)
            )
        else:
            planned_completions = ()
        return LocalStubModelClient(
            route=client_route,
            response_text="",
            planned_completions=planned_completions,
        )
    raise ValueError(f"unsupported provider_route: {provider_route}")


