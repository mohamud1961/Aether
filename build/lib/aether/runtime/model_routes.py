"""Model-client boundary and provider-route metadata."""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request

from harness.aether2.runtime.route_schemas import validate_model_route

CODEX_INFERENCE_ENDPOINT = "https://chatgpt.com/backend-api/codex/responses"
CODEX_REFRESH_ENDPOINT = "https://auth.openai.com/oauth/token"
CODEX_REFRESH_CLIENT_ID = "app_codex"
DEFAULT_CODEX_AUTH_PATH = Path("~/.codex/auth.json").expanduser()
TRANSIENT_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
AZURE_OPENAI_DEFAULT_API_VERSION = "2024-12-01-preview"
AZURE_ROUTE_MODEL_TIERS = frozenset({"gpt-5.4-mini", "gpt-5.3-codex"})

AZURE_ENV_ENDPOINT = "AZURE_OPENAI_ENDPOINT"
AZURE_ENV_API_VERSION = "AZURE_OPENAI_API_VERSION"
AZURE_ENV_GPT54_MINI_KEY = "AZURE_OPENAI_GPT54_MINI_KEY"
AZURE_ENV_GPT54_MINI_DEPLOYMENT = "AZURE_OPENAI_GPT54_MINI_DEPLOYMENT"
AZURE_ENV_GPT53_CODEX_KEY = "AZURE_OPENAI_GPT53_CODEX_KEY"
AZURE_ENV_GPT53_CODEX_DEPLOYMENT = "AZURE_OPENAI_GPT53_CODEX_DEPLOYMENT"
OPENAI_ENV_API_KEY = "OPENAI_API_KEY"


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


def make_codex_subscription_route(
    *,
    model_name: str,
    request_settings: dict[str, Any] | None = None,
    provider_scope: str = "local_dev",
) -> dict[str, Any]:
    return make_model_route(
        model_client_id="codex_subscription",
        provider_route="codex_subscription",
        model_name=model_name,
        adapter_id="codex_subscription_oauth",
        auth_mode="oauth",
        provider_scope=provider_scope,
        api_base=CODEX_INFERENCE_ENDPOINT,
        request_settings=request_settings,
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


def make_openai_chat_completions_route(
    *,
    model_name: str,
    api_key_env_var: str = OPENAI_ENV_API_KEY,
    request_settings: dict[str, Any] | None = None,
    provider_scope: str = "local_dev",
) -> dict[str, Any]:
    settings = dict(request_settings or {})
    settings["api_key_env_var"] = api_key_env_var
    return make_model_route(
        model_client_id="openai_api_key",
        provider_route="openai_api",
        model_name=model_name,
        adapter_id="openai_chat_completions_api_key",
        auth_mode="api_key",
        provider_scope=provider_scope,
        api_base="https://api.openai.com/v1/chat/completions",
        request_settings=settings,
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
class CodexSubscriptionModelClient:
    route: dict[str, Any]
    auth_path: Path = DEFAULT_CODEX_AUTH_PATH
    timeout_sec: float = 30.0
    max_retries: int = 2
    retry_backoff_sec: float = 0.2
    refresh_cooldown_sec: float = 5.0
    _last_refresh_attempt: float = field(default=-1.0, init=False, repr=False)

    def __post_init__(self) -> None:
        self.route = validate_model_route(dict(self.route))
        self.auth_path = Path(self.auth_path).expanduser()
        if self.route["provider_route"] != "codex_subscription":
            raise ValueError("CodexSubscriptionModelClient requires provider_route=codex_subscription")

    def complete(self, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        payload = self._build_payload(messages=messages, kwargs=kwargs)
        timeout_sec = float(kwargs.get("timeout_sec", self.timeout_sec))
        max_retries = max(0, int(kwargs.get("max_retries", self.max_retries)))
        max_attempts = max_retries + 1

        access_token, refresh_token, auth_payload = _load_auth_tokens(self.auth_path)
        refreshed = False
        attempts = 0
        while attempts < max_attempts:
            attempts += 1
            try:
                events = self._post_inference(payload=payload, access_token=access_token, timeout_sec=timeout_sec)
                return _normalize_codex_result(events=events, model_route=self.route)
            except urllib_error.HTTPError as err:
                status_code = int(getattr(err, "code", 0) or 0)
                if status_code == 401 and not refreshed:
                    access_token, refresh_token, auth_payload = self._refresh_access_token(
                        refresh_token=refresh_token,
                        auth_payload=auth_payload,
                        timeout_sec=timeout_sec,
                    )
                    refreshed = True
                    attempts -= 1
                    continue
                if status_code in TRANSIENT_STATUS_CODES and attempts < max_attempts:
                    self._sleep_for_retry(attempts)
                    continue
                raise ModelClientError(
                    f"codex_subscription request failed with status {status_code}",
	                    status_code=status_code,
	                    response_body=_http_error_body(err),
	                    response_headers=_http_error_headers(err),
	                    error_kind="http_error",
                    metadata={"url": getattr(err, "url", None)},
                ) from err
            except (urllib_error.URLError, OSError, TimeoutError, ConnectionError) as err:
                if attempts < max_attempts:
                    self._sleep_for_retry(attempts)
                    continue
                raise ModelClientError(
                    "codex_subscription request failed due to network error",
                    error_kind="network_error",
                    metadata={"reason": _network_error_reason(err)},
                ) from err

        raise ModelClientError("codex_subscription request exhausted retries")

    def _build_payload(self, *, messages: list[dict[str, Any]], kwargs: dict[str, Any]) -> dict[str, Any]:
        route_settings = self.route.get("request_settings") or {}
        route_settings = dict(route_settings) if isinstance(route_settings, dict) else {}
        tools = _normalize_request_tools(kwargs.get("tools", route_settings.get("tools", [])))

        payload: dict[str, Any] = {
            "model": self.route["model_name"],
            "store": False,
            "stream": True,
            "instructions": _extract_instructions(messages, route_settings, kwargs),
            "input": _normalize_input_messages(messages),
            "tools": tools,
        }
        route_settings.pop("tools", None)
        route_settings.pop("instructions", None)
        if isinstance(route_settings, dict):
            payload.update(route_settings)
        for key, value in kwargs.items():
            if key in {"timeout_sec", "max_retries", "tools"}:
                continue
            payload[key] = value
        return payload

    def _post_inference(
        self,
        *,
        payload: dict[str, Any],
        access_token: str,
        timeout_sec: float,
    ) -> list[dict[str, Any]]:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        request = urllib_request.Request(
            url=self.route.get("api_base") or CODEX_INFERENCE_ENDPOINT,
            data=body,
            method="POST",
            headers=headers,
        )
        with urllib_request.urlopen(request, timeout=timeout_sec) as response:
            return _parse_sse_events(response.read())

    def _refresh_access_token(
        self,
        *,
        refresh_token: str | None,
        auth_payload: dict[str, Any],
        timeout_sec: float,
    ) -> tuple[str, str | None, dict[str, Any]]:
        if not refresh_token:
            raise ModelClientError("codex_subscription refresh token is missing")
        now = time.monotonic()
        if self._last_refresh_attempt >= 0 and now - self._last_refresh_attempt < self.refresh_cooldown_sec:
            raise ModelClientError("codex_subscription refresh cooldown active")
        self._last_refresh_attempt = now

        refresh_payload = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": CODEX_REFRESH_CLIENT_ID,
        }
        request = urllib_request.Request(
            url=CODEX_REFRESH_ENDPOINT,
            data=json.dumps(refresh_payload, separators=(",", ":")).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        try:
            with urllib_request.urlopen(request, timeout=timeout_sec) as response:
                refresh_data = json.loads(response.read().decode("utf-8"))
        except urllib_error.HTTPError as err:
            status_code = int(getattr(err, "code", 0) or 0)
            raise ModelClientError(
                f"codex_subscription token refresh failed with status {status_code}",
	                status_code=status_code,
	                response_body=_http_error_body(err),
	                response_headers=_http_error_headers(err),
	                error_kind="refresh_http_error",
                metadata={"url": getattr(err, "url", None)},
            ) from err
        except (urllib_error.URLError, OSError, TimeoutError, ConnectionError) as err:
            raise ModelClientError(
                "codex_subscription token refresh failed due to network error",
                error_kind="refresh_network_error",
                metadata={"reason": _network_error_reason(err)},
            ) from err

        new_access_token = _first_string(refresh_data.get("access_token"))
        if not new_access_token:
            raise ModelClientError("codex_subscription token refresh returned no access token")
        new_refresh_token = _first_string(refresh_data.get("refresh_token")) or refresh_token
        updated_payload = _with_updated_tokens(
            auth_payload=auth_payload,
            access_token=new_access_token,
            refresh_token=new_refresh_token,
        )
        self.auth_path.parent.mkdir(parents=True, exist_ok=True)
        self.auth_path.write_text(
            json.dumps(updated_payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return new_access_token, new_refresh_token, updated_payload

    def _sleep_for_retry(self, attempts: int) -> None:
        delay = self.retry_backoff_sec * attempts
        if delay > 0:
            time.sleep(delay)


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
        payload = self._build_payload(messages=messages, kwargs=kwargs)
        route_settings = self.route.get("request_settings") or {}
        route_settings = dict(route_settings) if isinstance(route_settings, dict) else {}
        api_surface = _first_string(route_settings.get("azure_api_surface")) or "deployment_chat_completions"
        timeout_sec = float(kwargs.get("timeout_sec", self.timeout_sec))
        max_retries = max(0, int(kwargs.get("max_retries", self.max_retries)))
        max_attempts = max_retries + 1
        attempts = 0
        while attempts < max_attempts:
            attempts += 1
            try:
                response = self._post_chat_completion(payload=payload, timeout_sec=timeout_sec)
                if api_surface == "v1_responses":
                    return _normalize_azure_responses_result(response=response, model_route=self.route)
                return _normalize_azure_chat_result(response=response, model_route=self.route)
            except urllib_error.HTTPError as err:
                status_code = int(getattr(err, "code", 0) or 0)
                if status_code in TRANSIENT_STATUS_CODES and attempts < max_attempts:
                    self._sleep_for_retry(attempts)
                    continue
                raise ModelClientError(
                    f"azure openai request failed with status {status_code}",
	                    status_code=status_code,
	                    response_body=_http_error_body(err),
	                    response_headers=_http_error_headers(err),
	                    error_kind="http_error",
                    metadata={
                        "url": getattr(err, "url", None),
                        "deployment": self.route.get("model_name"),
                        "api_base": self.route.get("api_base"),
                    },
                ) from err
            except (urllib_error.URLError, OSError, TimeoutError, ConnectionError) as err:
                if attempts < max_attempts:
                    self._sleep_for_retry(attempts)
                    continue
                raise ModelClientError(
                    "azure openai request failed due to network error",
                    error_kind="network_error",
                    metadata={
                        "reason": _network_error_reason(err),
                        "deployment": self.route.get("model_name"),
                        "api_base": self.route.get("api_base"),
                    },
                ) from err

        raise ModelClientError("azure openai request exhausted retries")

    def _build_payload(self, *, messages: list[dict[str, Any]], kwargs: dict[str, Any]) -> dict[str, Any]:
        route_settings = self.route.get("request_settings") or {}
        route_settings = dict(route_settings) if isinstance(route_settings, dict) else {}
        api_surface = _first_string(route_settings.get("azure_api_surface")) or "deployment_chat_completions"
        tools_input = kwargs.get("tools", route_settings.pop("tools", []))
        if api_surface == "v1_responses":
            tools = _normalize_request_tools(tools_input)
            payload: dict[str, Any] = {
                "model": self.route["model_name"],
                "input": _normalize_input_messages(messages),
                "instructions": _extract_instructions(messages, route_settings, kwargs),
                "store": False,
            }
        else:
            tools = _normalize_chat_completions_tools(tools_input)
            payload = {"messages": _normalize_chat_messages(messages)}
        if api_surface == "v1_chat_completions":
            payload["model"] = self.route["model_name"]
        if tools:
            payload["tools"] = tools

        for internal_key in (
            "azure_endpoint",
            "azure_api_version",
            "azure_deployment",
            "api_key_env_var",
            "pricing_model_id",
            "azure_api_surface",
        ):
            route_settings.pop(internal_key, None)
        if isinstance(route_settings, dict):
            payload.update(route_settings)
        for key, value in kwargs.items():
            if key in {"timeout_sec", "max_retries", "tools"}:
                continue
            payload[key] = value
        return payload

    def _post_chat_completion(self, *, payload: dict[str, Any], timeout_sec: float) -> dict[str, Any]:
        route_settings = self.route.get("request_settings") or {}
        settings = dict(route_settings) if isinstance(route_settings, dict) else {}
        api_key_env_var = _first_string(settings.get("api_key_env_var"))
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
        api_surface = _first_string(settings.get("azure_api_surface")) or "deployment_chat_completions"
        request_url = _first_string(self.route.get("api_base"))
        if api_surface != "v1_responses":
            api_version = _first_string(settings.get("azure_api_version")) or AZURE_OPENAI_DEFAULT_API_VERSION
            request_url = _with_api_version(url=request_url, api_version=api_version)
        if not request_url:
            raise ModelClientError("azure openai route is missing api_base", error_kind="route_error")
        headers = {
            "api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        request = urllib_request.Request(
            url=request_url,
            data=body,
            method="POST",
            headers=headers,
        )
        with urllib_request.urlopen(request, timeout=timeout_sec) as response:
            decoded = response.read().decode("utf-8")
        parsed = json.loads(decoded)
        if not isinstance(parsed, dict):
            raise ModelClientError("azure openai response payload must be an object")
        return parsed

    def _sleep_for_retry(self, attempts: int) -> None:
        delay = self.retry_backoff_sec * attempts
        if delay > 0:
            time.sleep(delay)


@dataclass
class OpenAIAPIKeyModelClient:
    route: dict[str, Any]
    timeout_sec: float = 30.0
    max_retries: int = 2
    retry_backoff_sec: float = 0.2

    def __post_init__(self) -> None:
        self.route = validate_model_route(dict(self.route))
        if self.route["provider_route"] != "openai_api":
            raise ValueError("OpenAIAPIKeyModelClient requires provider_route=openai_api")
        if self.route.get("auth_mode") != "api_key":
            raise ValueError("OpenAIAPIKeyModelClient requires auth_mode=api_key")
        if self.route.get("model_client_id") != "openai_api_key":
            raise ValueError("OpenAIAPIKeyModelClient requires model_client_id=openai_api_key")

    def complete(self, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
        payload = self._build_payload(messages=messages, kwargs=kwargs)
        timeout_sec = float(kwargs.get("timeout_sec", self.timeout_sec))
        max_retries = max(0, int(kwargs.get("max_retries", self.max_retries)))
        max_attempts = max_retries + 1
        attempts = 0
        while attempts < max_attempts:
            attempts += 1
            try:
                response = self._post_chat_completion(payload=payload, timeout_sec=timeout_sec)
                return _normalize_azure_chat_result(response=response, model_route=self.route)
            except urllib_error.HTTPError as err:
                status_code = int(getattr(err, "code", 0) or 0)
                if status_code in TRANSIENT_STATUS_CODES and attempts < max_attempts:
                    self._sleep_for_retry(attempts)
                    continue
                raise ModelClientError(
                    f"openai api request failed with status {status_code}",
	                    status_code=status_code,
	                    response_body=_http_error_body(err),
	                    response_headers=_http_error_headers(err),
	                    error_kind="http_error",
                    metadata={"url": getattr(err, "url", None), "model": self.route.get("model_name")},
                ) from err
            except (urllib_error.URLError, OSError, TimeoutError, ConnectionError) as err:
                if attempts < max_attempts:
                    self._sleep_for_retry(attempts)
                    continue
                raise ModelClientError(
                    "openai api request failed due to network error",
                    error_kind="network_error",
                    metadata={"reason": _network_error_reason(err), "model": self.route.get("model_name")},
                ) from err

        raise ModelClientError("openai api request exhausted retries")

    def _build_payload(self, *, messages: list[dict[str, Any]], kwargs: dict[str, Any]) -> dict[str, Any]:
        route_settings = self.route.get("request_settings") or {}
        route_settings = dict(route_settings) if isinstance(route_settings, dict) else {}
        tools = _normalize_chat_completions_tools(kwargs.get("tools", route_settings.pop("tools", [])))
        payload: dict[str, Any] = {
            "model": self.route["model_name"],
            "messages": _normalize_chat_messages(messages),
        }
        if tools:
            payload["tools"] = tools
        route_settings.pop("api_key_env_var", None)
        if isinstance(route_settings, dict):
            payload.update(route_settings)
        for key, value in kwargs.items():
            if key in {"timeout_sec", "max_retries", "tools"}:
                continue
            payload[key] = value
        return payload

    def _post_chat_completion(self, *, payload: dict[str, Any], timeout_sec: float) -> dict[str, Any]:
        route_settings = self.route.get("request_settings") or {}
        settings = dict(route_settings) if isinstance(route_settings, dict) else {}
        api_key_env_var = _first_string(settings.get("api_key_env_var")) or OPENAI_ENV_API_KEY
        api_key = _first_string(os.environ.get(api_key_env_var))
        if not api_key:
            raise ModelClientError(
                f"missing OpenAI API key in environment variable {api_key_env_var}",
                error_kind="auth_error",
                metadata={"api_key_env_var": api_key_env_var},
            )
        request_url = _first_string(self.route.get("api_base"))
        if not request_url:
            raise ModelClientError("openai api route is missing api_base", error_kind="route_error")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        request = urllib_request.Request(
            url=request_url,
            data=body,
            method="POST",
            headers=headers,
        )
        with urllib_request.urlopen(request, timeout=timeout_sec) as response:
            decoded = response.read().decode("utf-8")
        parsed = json.loads(decoded)
        if not isinstance(parsed, dict):
            raise ModelClientError("openai api response payload must be an object")
        return parsed

    def _sleep_for_retry(self, attempts: int) -> None:
        delay = self.retry_backoff_sec * attempts
        if delay > 0:
            time.sleep(delay)


def make_model_client_from_route(model_route: dict[str, Any], **kwargs: Any) -> ModelClient:
    route = validate_model_route(dict(model_route))
    client_kwargs = dict(kwargs)
    pacer_options = _extract_tpm_pacer_options(route, client_kwargs)
    client_route = _route_without_tpm_pacer_settings(route)
    provider_route = route["provider_route"]
    if provider_route == "codex_subscription":
        return _maybe_wrap_tpm_pacer(CodexSubscriptionModelClient(route=client_route, **client_kwargs), pacer_options)
    if provider_route == "openai_api":
        if route.get("model_client_id") == "azure_openai_api_key":
            return _maybe_wrap_tpm_pacer(AzureOpenAIAPIKeyModelClient(route=client_route, **client_kwargs), pacer_options)
        if route.get("model_client_id") == "openai_api_key":
            return _maybe_wrap_tpm_pacer(OpenAIAPIKeyModelClient(route=client_route, **client_kwargs), pacer_options)
        raise ValueError(
            "unsupported openai_api model client route; expected model_client_id=azure_openai_api_key or openai_api_key"
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


_TPM_PACER_SETTING_KEYS = frozenset(
    {
        "tpm_pacer_enabled",
        "tpm_limit",
        "tpm_window_sec",
        "tpm_throttle_fraction",
        "tpm_pause_sec",
        "tpm_count_mode",
        "rpm_limit",
        "rpm_window_sec",
        "model_max_concurrency",
    }
)


def _route_without_tpm_pacer_settings(route: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(route)
    settings = cleaned.get("request_settings")
    if isinstance(settings, dict):
        cleaned["request_settings"] = {
            key: value for key, value in settings.items() if key not in _TPM_PACER_SETTING_KEYS
        }
    return cleaned


def _extract_tpm_pacer_options(route: dict[str, Any], kwargs: dict[str, Any]) -> dict[str, Any]:
    settings = route.get("request_settings")
    settings = dict(settings) if isinstance(settings, dict) else {}

    def _pop_or_setting(key: str, default: Any = None) -> Any:
        if key in kwargs:
            return kwargs.pop(key)
        return settings.get(key, default)

    enabled = _bool_env("HARNESS_TPM_PACER_ENABLED", default=False)
    enabled = _as_bool(_pop_or_setting("tpm_pacer_enabled", enabled), default=enabled)
    return {
        "enabled": enabled,
        "tpm_limit": _as_positive_int(
            _pop_or_setting("tpm_limit", os.environ.get("HARNESS_TPM_LIMIT", "100000")),
            default=100000,
        ),
        "window_sec": _as_positive_float(
            _pop_or_setting("tpm_window_sec", os.environ.get("HARNESS_TPM_WINDOW_SEC", "60")),
            default=60.0,
        ),
        "throttle_fraction": _as_positive_float(
            _pop_or_setting("tpm_throttle_fraction", os.environ.get("HARNESS_TPM_THROTTLE_FRACTION", "0.85")),
            default=0.85,
        ),
        "pause_sec": _as_non_negative_float(
            _pop_or_setting("tpm_pause_sec", os.environ.get("HARNESS_TPM_PAUSE_SEC", "4")),
            default=4.0,
        ),
        "token_count_mode": str(
            _pop_or_setting("tpm_count_mode", os.environ.get("HARNESS_TPM_COUNT_MODE", "total"))
            or "total"
        ),
        "rpm_limit": _as_optional_positive_int(
            _pop_or_setting("rpm_limit", os.environ.get("HARNESS_RPM_LIMIT")),
        ),
        "rpm_window_sec": _as_positive_float(
            _pop_or_setting("rpm_window_sec", os.environ.get("HARNESS_RPM_WINDOW_SEC", "60")),
            default=60.0,
        ),
        "max_concurrency": _as_positive_int(
            _pop_or_setting("model_max_concurrency", os.environ.get("HARNESS_MODEL_MAX_CONCURRENCY", "1")),
            default=1,
        ),
        "shared_scope": _model_route_pacer_scope(route),
    }


def _maybe_wrap_tpm_pacer(client: ModelClient, options: dict[str, Any]) -> ModelClient:
    if not options.get("enabled"):
        return client
    from harness.aether2.runtime.tpm_pacer import make_paced_client

    return make_paced_client(
        client,
        tpm_limit=int(options["tpm_limit"]),
        window_sec=float(options["window_sec"]),
        throttle_fraction=float(options["throttle_fraction"]),
        pause_sec=float(options["pause_sec"]),
        token_count_mode=str(options["token_count_mode"]),
        rpm_limit=options.get("rpm_limit"),
        rpm_window_sec=float(options["rpm_window_sec"]),
        max_concurrency=int(options["max_concurrency"]),
        shared_scope=str(options["shared_scope"]),
        enabled=True,
    )


def _bool_env(name: str, *, default: bool) -> bool:
    return _as_bool(os.environ.get(name), default=default)


def _as_bool(value: Any, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    if value is None:
        return default
    return bool(value)


def _as_positive_int(value: Any, *, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _as_optional_positive_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _as_positive_float(value: Any, *, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _as_non_negative_float(value: Any, *, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= 0 else default


def _model_route_pacer_scope(route: dict[str, Any]) -> str:
    settings = route.get("request_settings")
    settings = settings if isinstance(settings, dict) else {}
    return "|".join(
        [
            str(route.get("provider_route") or "provider"),
            str(route.get("model_client_id") or "client"),
            str(route.get("model_name") or "model"),
            str(settings.get("azure_deployment") or ""),
            str(route.get("api_base") or ""),
        ]
    )


def _first_string(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _load_auth_tokens(auth_path: Path) -> tuple[str, str | None, dict[str, Any]]:
    if not auth_path.exists():
        raise ModelClientError(f"codex auth file not found: {auth_path}")
    auth_payload = json.loads(auth_path.read_text(encoding="utf-8"))
    nested_tokens = auth_payload.get("tokens")
    nested_tokens = nested_tokens if isinstance(nested_tokens, dict) else {}
    access_token = _first_string(auth_payload.get("access_token")) or _first_string(
        nested_tokens.get("access_token")
    )
    refresh_token = _first_string(auth_payload.get("refresh_token")) or _first_string(
        nested_tokens.get("refresh_token")
    )
    if not access_token:
        raise ModelClientError("codex auth file is missing access_token")
    return access_token, refresh_token, auth_payload


def _with_updated_tokens(
    *,
    auth_payload: dict[str, Any],
    access_token: str,
    refresh_token: str | None,
) -> dict[str, Any]:
    updated_payload = dict(auth_payload)
    if "access_token" in updated_payload or not isinstance(updated_payload.get("tokens"), dict):
        updated_payload["access_token"] = access_token
    if "refresh_token" in updated_payload and refresh_token is not None:
        updated_payload["refresh_token"] = refresh_token

    nested_tokens = updated_payload.get("tokens")
    if isinstance(nested_tokens, dict):
        nested = dict(nested_tokens)
        nested["access_token"] = access_token
        if refresh_token is not None:
            nested["refresh_token"] = refresh_token
        updated_payload["tokens"] = nested
    return updated_payload


def _parse_sse_events(raw_body: bytes) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    data_lines: list[str] = []

    def flush() -> None:
        if not data_lines:
            return
        chunk = "\n".join(data_lines).strip()
        data_lines.clear()
        if not chunk or chunk == "[DONE]":
            return
        parsed = json.loads(chunk)
        if isinstance(parsed, dict):
            events.append(parsed)

    for line in raw_body.decode("utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if stripped.startswith("data:"):
            data_lines.append(stripped[5:].lstrip())
        elif not stripped:
            flush()
    flush()
    return events


def _normalize_codex_result(
    *,
    events: list[dict[str, Any]],
    model_route: dict[str, Any],
) -> dict[str, Any]:
    response_payload: dict[str, Any] = {}
    text_deltas: list[str] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        if event.get("type") == "response.output_text.delta":
            delta = event.get("delta")
            if isinstance(delta, str):
                text_deltas.append(delta)
        if isinstance(event.get("output"), list):
            response_payload = event
        response = event.get("response")
        if isinstance(response, dict):
            response_payload = response

    text, tool_calls = _extract_text_and_tool_calls(response_payload)
    usage = response_payload.get("usage") if isinstance(response_payload.get("usage"), dict) else {}
    status = response_payload.get("status") if isinstance(response_payload.get("status"), str) else "completed"
    reasoning_telemetry = _extract_responses_reasoning_telemetry(response_payload)
    reasoning_token_count = _extract_reasoning_token_count(usage)
    if not text:
        text = "".join(text_deltas)

    normalized = {
        "text": text,
        "tool_calls": tool_calls,
        "usage": usage,
        "status": status,
        "model_route": model_route,
    }
    if reasoning_token_count is not None:
        normalized["reasoning_token_count"] = reasoning_token_count
    normalized.update(reasoning_telemetry)
    return normalized


def _extract_text_and_tool_calls(response_payload: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    text_parts: list[str] = []
    tool_calls: list[dict[str, Any]] = []
    output = response_payload.get("output")
    if not isinstance(output, list):
        return "", []

    for item in output:
        if not isinstance(item, dict):
            continue
        item_type = item.get("type")
        if item_type in {"function_call", "tool_call"}:
            tool_calls.append(_normalize_tool_call(item, fallback_type=item_type))

        content = item.get("content")
        if not isinstance(content, list):
            continue
        for content_item in content:
            if not isinstance(content_item, dict):
                continue
            content_type = content_item.get("type")
            if content_type in {"output_text", "text"}:
                text_value = content_item.get("text")
                if isinstance(text_value, str):
                    text_parts.append(text_value)
            if content_type in {"function_call", "tool_call"}:
                tool_calls.append(_normalize_tool_call(content_item, fallback_type=content_type))

    return "".join(text_parts), tool_calls


def _normalize_request_tools(tools: Any) -> list[dict[str, Any]]:
    if not isinstance(tools, list):
        return []
    normalized: list[dict[str, Any]] = []
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        if isinstance(tool.get("type"), str):
            normalized.append(dict(tool))
            continue
        name = tool.get("name")
        if not isinstance(name, str) or not name:
            continue
        normalized_tool = {
            "type": "function",
            "name": name,
        }
        description = tool.get("description")
        if isinstance(description, str) and description:
            normalized_tool["description"] = description
        parameters = tool.get("parameters")
        if isinstance(parameters, dict):
            normalized_tool["parameters"] = parameters
        else:
            input_schema = tool.get("input_schema")
            if isinstance(input_schema, dict):
                normalized_tool["parameters"] = input_schema
        normalized.append(normalized_tool)
    return normalized


def _normalize_chat_completions_tools(tools: Any) -> list[dict[str, Any]]:
    normalized_tools = _normalize_request_tools(tools)
    converted: list[dict[str, Any]] = []
    for tool in normalized_tools:
        if tool.get("type") != "function":
            continue
        name = _first_string(tool.get("name"))
        if not name:
            continue
        function_payload: dict[str, Any] = {"name": name}
        description = _first_string(tool.get("description"))
        if description:
            function_payload["description"] = description
        parameters = tool.get("parameters")
        if isinstance(parameters, dict):
            function_payload["parameters"] = parameters
        converted.append({"type": "function", "function": function_payload})
    return converted


def _normalize_chat_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for message in messages:
        role = message.get("role")
        if not isinstance(role, str) or not role:
            continue
        if role == "assistant":
            tool_calls = _normalize_history_tool_calls(message.get("tool_calls"))
            if tool_calls:
                content = message.get("content")
                if not isinstance(content, str):
                    content = None
                normalized.append({"role": role, "content": content, "tool_calls": tool_calls})
                continue
        if role == "tool":
            content = message.get("content")
            if not isinstance(content, str):
                continue
            tool_call_id = _first_string(message.get("tool_call_id"))
            row = {"role": role, "content": content}
            if tool_call_id:
                row["tool_call_id"] = tool_call_id
            name = _first_string(message.get("name"))
            if name:
                row["name"] = name
            normalized.append(row)
            continue
        content = message.get("content")
        if isinstance(content, str):
            normalized.append({"role": role, "content": content})
            continue
        if isinstance(content, list):
            normalized.append({"role": role, "content": content})
            continue
    return normalized


def _normalize_history_tool_calls(tool_calls_payload: Any) -> list[dict[str, Any]]:
    if not isinstance(tool_calls_payload, list):
        return []
    normalized: list[dict[str, Any]] = []
    for tool_call in tool_calls_payload:
        if not isinstance(tool_call, dict):
            continue
        tool_call_id = _first_string(tool_call.get("id"))
        tool_type = _first_string(tool_call.get("type")) or "function"
        tool_name = _first_string(tool_call.get("name"))
        arguments = tool_call.get("arguments")
        if not tool_name:
            function_payload = tool_call.get("function")
            if isinstance(function_payload, dict):
                tool_name = _first_string(function_payload.get("name"))
                if arguments is None:
                    arguments = function_payload.get("arguments")
        if not tool_name:
            continue
        function_row: dict[str, Any] = {"name": tool_name}
        if isinstance(arguments, str):
            function_row["arguments"] = arguments
        elif arguments is not None:
            function_row["arguments"] = json.dumps(arguments, sort_keys=True, separators=(",", ":"))
        row: dict[str, Any] = {"type": tool_type, "function": function_row}
        if tool_call_id:
            row["id"] = tool_call_id
        normalized.append(row)
    return normalized


def _normalize_azure_chat_result(*, response: dict[str, Any], model_route: dict[str, Any]) -> dict[str, Any]:
    message_payload: dict[str, Any] = {}
    finish_reason = "stop"
    choices = response.get("choices")
    if isinstance(choices, list) and choices:
        first_choice = choices[0]
        if isinstance(first_choice, dict):
            finish_reason_value = first_choice.get("finish_reason")
            if isinstance(finish_reason_value, str) and finish_reason_value:
                finish_reason = finish_reason_value
            candidate_message = first_choice.get("message")
            if isinstance(candidate_message, dict):
                message_payload = candidate_message

    text = _extract_chat_message_text(message_payload)
    reasoning_summary = message_payload.get("reasoning_content")
    if not isinstance(reasoning_summary, str) or not reasoning_summary.strip():
        reasoning_summary = None

    tool_calls = _normalize_azure_tool_calls(message_payload.get("tool_calls"))
    usage_raw = response.get("usage")
    usage_dict = usage_raw if isinstance(usage_raw, dict) else {}
    usage = _normalize_azure_usage(usage_dict)
    usage["provider_usage_raw"] = usage_dict
    reasoning_token_count = _extract_reasoning_token_count(usage_dict)

    status = "completed"
    if finish_reason == "length":
        status = "max_tokens_exhausted"
    elif finish_reason == "content_filter":
        status = "blocked"

    normalized = {
        "text": text,
        "tool_calls": tool_calls,
        "usage": usage,
        "status": status,
        "model_route": model_route,
    }
    if reasoning_summary is not None:
        normalized["reasoning_summary"] = reasoning_summary
        normalized["provider_reasoning"] = {
            "source": "message.reasoning_content",
            "summary_count": 1,
        }
    if reasoning_token_count is not None:
        normalized["reasoning_token_count"] = reasoning_token_count
    return normalized


def _normalize_azure_responses_result(*, response: dict[str, Any], model_route: dict[str, Any]) -> dict[str, Any]:
    text, tool_calls = _extract_text_and_tool_calls(response)
    usage_raw = response.get("usage")
    usage_dict = usage_raw if isinstance(usage_raw, dict) else {}
    usage = _normalize_azure_usage(usage_dict)
    usage["provider_usage_raw"] = usage_dict
    status = _first_string(response.get("status")) or "completed"
    reasoning_token_count = _extract_reasoning_token_count(usage_dict)
    reasoning_telemetry = _extract_responses_reasoning_telemetry(response)
    normalized = {
        "text": text,
        "tool_calls": tool_calls,
        "usage": usage,
        "status": status,
        "model_route": model_route,
    }
    if reasoning_token_count is not None:
        normalized["reasoning_token_count"] = reasoning_token_count
    normalized.update(reasoning_telemetry)
    return normalized


def _extract_chat_message_text(message_payload: dict[str, Any]) -> str:
    content = message_payload.get("content")
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    text_parts: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        item_type = item.get("type")
        if item_type in {"text", "output_text"}:
            text_value = item.get("text")
            if isinstance(text_value, str):
                text_parts.append(text_value)
    return "".join(text_parts)


def _normalize_azure_tool_calls(tool_calls_payload: Any) -> list[dict[str, Any]]:
    if not isinstance(tool_calls_payload, list):
        return []
    normalized: list[dict[str, Any]] = []
    for tool_call in tool_calls_payload:
        if not isinstance(tool_call, dict):
            continue
        function_payload = tool_call.get("function")
        function_payload = function_payload if isinstance(function_payload, dict) else {}
        item = {
            "type": _first_string(tool_call.get("type")) or "function",
            "id": _first_string(tool_call.get("id")),
            "name": _first_string(function_payload.get("name")),
            "arguments": function_payload.get("arguments"),
        }
        normalized.append({key: value for key, value in item.items() if value is not None})
    return normalized


def _normalize_azure_usage(usage: dict[str, Any]) -> dict[str, int]:
    input_tokens = _coerce_int(usage.get("input_tokens"))
    if input_tokens <= 0:
        input_tokens = _coerce_int(usage.get("prompt_tokens"))
    output_tokens = _coerce_int(usage.get("output_tokens"))
    if output_tokens <= 0:
        output_tokens = _coerce_int(usage.get("completion_tokens"))
    total_tokens = _coerce_int(usage.get("total_tokens"))
    cached_input_tokens = _coerce_int(usage.get("cached_input_tokens"))
    if cached_input_tokens <= 0:
        details = usage.get("prompt_tokens_details")
        details = details if isinstance(details, dict) else usage.get("input_tokens_details")
        if isinstance(details, dict):
            cached_input_tokens = _coerce_int(details.get("cached_tokens"))

    if total_tokens <= 0:
        total_tokens = input_tokens + output_tokens
    if cached_input_tokens < 0:
        cached_input_tokens = 0

    return {
        "input_tokens": max(0, input_tokens),
        "cached_input_tokens": cached_input_tokens,
        "output_tokens": max(0, output_tokens),
        "total_tokens": max(0, total_tokens),
    }


def _extract_reasoning_token_count(usage: dict[str, Any]) -> int | None:
    completion_details = usage.get("completion_tokens_details")
    if isinstance(completion_details, dict) and "reasoning_tokens" in completion_details:
        return max(0, _coerce_int(completion_details.get("reasoning_tokens")))
    output_details = usage.get("output_tokens_details")
    if isinstance(output_details, dict) and "reasoning_tokens" in output_details:
        return max(0, _coerce_int(output_details.get("reasoning_tokens")))
    if "reasoning_tokens" in usage:
        return max(0, _coerce_int(usage.get("reasoning_tokens")))
    return None


def _extract_responses_reasoning_telemetry(response_payload: dict[str, Any]) -> dict[str, Any]:
    # Provider-visible reasoning telemetry only: summaries and encrypted continuity metadata.
    # Never persist raw encrypted blobs or imply access to hidden chain-of-thought.
    output = response_payload.get("output")
    if not isinstance(output, list):
        return {}

    summary_parts: list[str] = []
    encrypted_hashes: list[str] = []
    encrypted_chars_total = 0
    reasoning_item_count = 0

    for item in output:
        if not isinstance(item, dict) or item.get("type") != "reasoning":
            continue
        reasoning_item_count += 1
        summary = item.get("summary")
        if isinstance(summary, list):
            for summary_item in summary:
                if isinstance(summary_item, dict):
                    text = summary_item.get("text")
                    if isinstance(text, str) and text:
                        summary_parts.append(text)
                elif isinstance(summary_item, str) and summary_item:
                    summary_parts.append(summary_item)
        elif isinstance(summary, str) and summary:
            summary_parts.append(summary)

        encrypted_content = item.get("encrypted_content")
        if isinstance(encrypted_content, str) and encrypted_content:
            encrypted_chars_total += len(encrypted_content)
            encrypted_hashes.append(hashlib.sha256(encrypted_content.encode("utf-8")).hexdigest())

    if not summary_parts and not encrypted_hashes and reasoning_item_count == 0:
        return {}

    telemetry: dict[str, Any] = {
        "provider_reasoning": {
            "source": "responses.output.reasoning",
            "reasoning_item_count": reasoning_item_count,
            "summary_count": len(summary_parts),
            "encrypted_item_count": len(encrypted_hashes),
        }
    }
    if summary_parts:
        telemetry["reasoning_summary"] = "\n".join(summary_parts)
    if encrypted_hashes:
        telemetry["reasoning_artifact"] = {
            "type": "encrypted_reasoning_continuity",
            "encoding": "provider_encrypted",
            "encrypted_content_char_count": encrypted_chars_total,
            "encrypted_content_hashes": encrypted_hashes,
        }
    return telemetry


def _http_error_body(err: urllib_error.HTTPError) -> str | None:
    body_stream = getattr(err, "fp", None)
    if body_stream is None:
        return None
    try:
        raw = err.read()
    except Exception:
        return None
    if not raw:
        return None
    return raw.decode("utf-8", errors="replace")[:1000]


def _http_error_headers(err: urllib_error.HTTPError) -> dict[str, str]:
    headers_obj = getattr(err, "headers", None) or getattr(err, "hdrs", None)
    if headers_obj is None:
        return {}
    try:
        items = headers_obj.items()
    except Exception:
        return {}
    headers: dict[str, str] = {}
    for key, value in items:
        key_str = str(key).strip().lower()
        if not key_str:
            continue
        if (
            key_str == "retry-after"
            or key_str == "apim-request-id"
            or key_str == "x-request-id"
            or key_str.startswith("x-ratelimit-")
        ):
            headers[key_str] = str(value)[:500]
    return headers


def _network_error_reason(err: Exception) -> str:
    reason = getattr(err, "reason", None)
    if reason is None:
        return str(err)
    return str(reason)


def _coerce_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return 0
    return 0


def _required_env_var(name: str) -> str:
    value = os.environ.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"missing required environment variable: {name}")
    return value.strip()


def _with_api_version(*, url: Any, api_version: str) -> str:
    base_url = _first_string(url) or ""
    if not base_url:
        raise ModelClientError("azure openai route is missing api_base", error_kind="route_error")
    separator = "&" if "?" in base_url else "?"
    encoded_api_version = urllib_parse.quote(api_version, safe="")
    return f"{base_url}{separator}api-version={encoded_api_version}"


def _normalize_tool_call(tool_payload: dict[str, Any], *, fallback_type: str) -> dict[str, Any]:
    normalized: dict[str, Any] = {
        "type": _first_string(tool_payload.get("type")) or fallback_type,
        "id": _first_string(tool_payload.get("call_id")) or _first_string(tool_payload.get("id")),
        "name": _first_string(tool_payload.get("name")),
        "arguments": tool_payload.get("arguments"),
    }
    return {key: value for key, value in normalized.items() if value is not None}


def _extract_instructions(
    messages: list[dict[str, Any]],
    route_settings: dict[str, Any],
    kwargs: dict[str, Any],
) -> str:
    explicit = kwargs.get("instructions")
    if isinstance(explicit, str) and explicit.strip():
        return explicit

    route_instruction = route_settings.get("instructions")
    if isinstance(route_instruction, str) and route_instruction.strip():
        return route_instruction

    system_parts: list[str] = []
    for message in messages:
        if message.get("role") != "system":
            continue
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            system_parts.append(content.strip())
    if system_parts:
        return "\n\n".join(system_parts)

    return "You are a concise assistant. Follow the user and available tools exactly."


def _normalize_input_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for message in messages:
        role = message.get("role")
        if role == "system":
            continue
        if role == "assistant":
            content = message.get("content")
            if content is not None:
                normalized.append({"role": role, "content": content})
            tool_calls = _normalize_history_tool_calls(message.get("tool_calls"))
            for tool_call in tool_calls:
                function_payload = tool_call.get("function")
                if not isinstance(function_payload, dict):
                    continue
                name = _first_string(function_payload.get("name"))
                if not name:
                    continue
                row: dict[str, Any] = {
                    "type": "function_call",
                    "name": name,
                    "arguments": function_payload.get("arguments", ""),
                }
                call_id = _first_string(tool_call.get("id"))
                if call_id:
                    row["call_id"] = call_id
                normalized.append(row)
            continue
        if role == "tool":
            tool_call_id = _first_string(message.get("tool_call_id"))
            content = message.get("content")
            if not tool_call_id or content is None:
                continue
            normalized.append(
                {
                    "type": "function_call_output",
                    "call_id": tool_call_id,
                    "output": content,
                }
            )
            continue
        content = message.get("content")
        if isinstance(role, str) and content is not None:
            normalized.append({"role": role, "content": content})
    return normalized
