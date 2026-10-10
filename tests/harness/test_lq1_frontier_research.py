from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from aether.model_profile import (
    API_KEY_CREDENTIAL_MODE,
    PRODUCTION_PROFILE,
    PROVIDER_CALLS_ALLOWED_ENV,
    PROVIDER_PROFILE_SHA256_ENV,
    SYSTEM_ASSIGNED_MANAGED_IDENTITY_CREDENTIAL_MODE,
)
from aether.providers.azure_model import AzureModelCallable
from aether.research_frontier_profile import (
    FRONTIER_RESEARCH_PROFILE,
    FRONTIER_RESEARCH_PROFILES,
    FRONTIER_RESEARCH_SELECTOR,
    build_frontier_research_models,
    frontier_research_profile,
)


_AZURE_IDENTITY_SELECTOR_ENV = (
    "IDENTITY_ENDPOINT",
    "IDENTITY_HEADER",
    "IDENTITY_SERVER_THUMBPRINT",
    "IMDS_ENDPOINT",
    "MSI_ENDPOINT",
    "MSI_SECRET",
    "AZURE_AUTHORITY_HOST",
    "AZURE_TENANT_ID",
    "AZURE_CLIENT_ID",
    "AZURE_FEDERATED_TOKEN_FILE",
    "AZURE_POD_IDENTITY_AUTHORITY_HOST",
    "AZURE_KUBERNETES_SNI_NAME",
    "AZURE_KUBERNETES_TOKEN_PROXY",
    "AZURE_KUBERNETES_CA_FILE",
    "AZURE_KUBERNETES_CA_DATA",
)


def _function_call(n: int) -> SimpleNamespace:
    return SimpleNamespace(
        id=f"fc-{n}",
        type="function_call",
        status="completed",
        call_id=f"call-{n}",
        name="read_file",
        arguments=json.dumps({"arguments": {"path": f"/app/input-{n}.txt"}}),
    )


def _response(n: int) -> SimpleNamespace:
    return SimpleNamespace(
        id=f"resp-{n}",
        status="completed",
        output=[_function_call(n)],
        usage=None,
        reasoning=None,
        error=None,
        incomplete_details=None,
    )


class _Responses:
    def __init__(self, rows: list[object]) -> None:
        self.rows = list(rows)
        self.requests: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> object:
        self.requests.append(dict(kwargs))
        if not self.rows:
            raise AssertionError("no fake response remains")
        return self.rows.pop(0)

    def retrieve(self, _response_id: str) -> object:
        raise AssertionError("foreground completed fake must not poll")

    def cancel(self, _response_id: str) -> object:
        raise AssertionError("completed fake must not cancel")


class _Client:
    def __init__(self, rows: list[object]) -> None:
        self.responses = _Responses(rows)


def test_lq1_frontier_research_identity_is_explicit_and_production_default_unchanged() -> None:
    assert FRONTIER_RESEARCH_SELECTOR == "frontier-research-v1"
    assert FRONTIER_RESEARCH_PROFILES == {FRONTIER_RESEARCH_SELECTOR: FRONTIER_RESEARCH_PROFILE}
    assert frontier_research_profile() is FRONTIER_RESEARCH_PROFILE
    assert FRONTIER_RESEARCH_PROFILE is not PRODUCTION_PROFILE
    assert PRODUCTION_PROFILE.profile_id == "production-persistent-v1"
    assert PRODUCTION_PROFILE.model_id == "gpt-5.6-luna"
    assert PRODUCTION_PROFILE.solver_reasoning_effort == "max"
    assert PRODUCTION_PROFILE.verifier_reasoning_effort == "max"
    assert PRODUCTION_PROFILE.prompt_cache_mode == "off"
    assert FRONTIER_RESEARCH_PROFILE.profile_id == FRONTIER_RESEARCH_SELECTOR
    assert FRONTIER_RESEARCH_PROFILE.model_id == "GPT-6-Luna"
    assert FRONTIER_RESEARCH_PROFILE.expected_returned_model == "GPT-6-Luna"
    assert FRONTIER_RESEARCH_PROFILE.solver_reasoning_effort == "high"
    assert FRONTIER_RESEARCH_PROFILE.verifier_reasoning_effort == "high"
    assert FRONTIER_RESEARCH_PROFILE.prompt_cache_mode == "stable_prefix"
    assert FRONTIER_RESEARCH_PROFILE.deployment_env == "AZURE_OPENAI_GPT56_FRONTIER_DEPLOYMENT"
    assert FRONTIER_RESEARCH_PROFILE.endpoint_env == "AZURE_OPENAI_GPT56_FRONTIER_ENDPOINT"
    assert FRONTIER_RESEARCH_PROFILE.key_env == ""
    assert FRONTIER_RESEARCH_PROFILE.credential_mode == SYSTEM_ASSIGNED_MANAGED_IDENTITY_CREDENTIAL_MODE
    assert FRONTIER_RESEARCH_PROFILE.api_mode == "responses"
    assert FRONTIER_RESEARCH_PROFILE.responses_background is False
    assert FRONTIER_RESEARCH_PROFILE.responses_websocket is True
    assert FRONTIER_RESEARCH_PROFILE.responses_websocket_persistent is True
    assert FRONTIER_RESEARCH_PROFILE.provider_poll_timeout_s == 1200
    assert FRONTIER_RESEARCH_PROFILE.manifest()["credential_mode"] == (
        SYSTEM_ASSIGNED_MANAGED_IDENTITY_CREDENTIAL_MODE
    )
    assert FRONTIER_RESEARCH_PROFILE.sha256() != PRODUCTION_PROFILE.sha256()
    assert PRODUCTION_PROFILE.credential_mode == API_KEY_CREDENTIAL_MODE
    assert "credential_mode" not in PRODUCTION_PROFILE.manifest()


def test_lq1_route_identity_binds_selector_endpoint_deployment_and_returned_model() -> None:
    first = FRONTIER_RESEARCH_PROFILE.route_identity_sha256(
        selector=FRONTIER_RESEARCH_SELECTOR,
        endpoint="https://example.openai.azure.com/",
        deployment="test-deployment",
    )
    repeat = FRONTIER_RESEARCH_PROFILE.route_identity_sha256(
        selector=FRONTIER_RESEARCH_SELECTOR,
        endpoint="https://example.openai.azure.com/",
        deployment="test-deployment",
    )
    different_deployment = FRONTIER_RESEARCH_PROFILE.route_identity_sha256(
        selector=FRONTIER_RESEARCH_SELECTOR,
        endpoint="https://example.openai.azure.com/",
        deployment="other-test-deployment",
    )
    assert first == repeat
    assert len(first) == 64
    assert different_deployment != first


def test_lq1_unknown_selector_fails_closed() -> None:
    with pytest.raises(ValueError, match="unsupported Frontier research profile selector"):
        frontier_research_profile("mystery")


def test_lq1_builder_reuses_canonical_frontier_factory_without_provider_call(monkeypatch) -> None:
    captured: list[object] = []

    def fake_builder(profile):
        captured.append(profile)
        return "solver", "verifier"

    monkeypatch.setattr("aether.research_frontier_profile.build_selected_frontier_models", fake_builder)
    assert build_frontier_research_models() == ("solver", "verifier")
    assert captured == [FRONTIER_RESEARCH_PROFILE]


def test_lq1_canonical_builder_binds_budget_guard_to_profile_model_id(monkeypatch) -> None:
    import aether.harbor_runtime as harbor_runtime

    captured: list[dict[str, object]] = []
    monkeypatch.setattr(harbor_runtime, "require_provider_authorization", lambda _profile: None)
    monkeypatch.setattr(harbor_runtime, "budget_runtime_limits_from_env", lambda: None)
    monkeypatch.setattr(harbor_runtime, "selected_h1_review_arm", lambda: "semantic")
    monkeypatch.setattr(harbor_runtime, "selected_judge_verifier_arm", lambda: "control")
    monkeypatch.setattr(
        harbor_runtime,
        "make_azure_callable",
        lambda **kwargs: captured.append(kwargs) or object(),
    )

    solver, verifier = harbor_runtime.build_selected_frontier_models(FRONTIER_RESEARCH_PROFILE)

    assert solver is not verifier
    assert [call["expected_model_id"] for call in captured] == [
        "gpt-6-luna",
        "gpt-6-luna",
    ]


def test_lq1_existing_responses_continuation_uses_previous_response_id_provider_free() -> None:
    client = _Client([_response(1), _response(2)])
    model = AzureModelCallable(
        client=client,  # type: ignore[arg-type]
        deployment="test-deployment",
        effort=FRONTIER_RESEARCH_PROFILE.solver_reasoning_effort,
        role="solver",
        responses_background=False,
        poll_interval_s=1.0,
        poll_timeout_s=30.0,
        max_retries=0,
        prompt_cache_mode=FRONTIER_RESEARCH_PROFILE.prompt_cache_mode,
    )

    for content in ("first-boundary", "second-boundary"):
        model.call_with_telemetry_scope(
            [{"role": "user", "content": content}],
            max_output_tokens=16000,
            run_id="lq1-run",
            task_id="lq1-task",
        )
        model.commit_pending_response(run_id="lq1-run", task_id="lq1-task")

    first, second = client.responses.requests
    assert first["store"] is True
    assert "previous_response_id" not in first
    assert first["prompt_cache_key"]
    assert second["store"] is True
    assert second["prompt_cache_key"]
    assert second["previous_response_id"] == "resp-1"
    assert second["input"] == [{
        "type": "function_call_output",
        "call_id": "call-1",
        "output": json.dumps(
            [{"role": "user", "content": "second-boundary"}],
            sort_keys=True,
            separators=(",", ":"),
        ),
    }]
    events = model.drain_telemetry()
    assert events[-1]["persistent_continuity_request_previous_response_id"] == "resp-1"
    assert events[-1]["persistent_continuity_prior_call_id_match_count"] == 1
    assert events[-1]["prompt_cache_key_mode"] == "stable_prefix"


def test_lq1_managed_identity_build_uses_system_identity_and_cannot_fall_back_to_key(monkeypatch) -> None:
    import sys
    from types import ModuleType

    from openai._models import FinalRequestOptions

    from aether.providers.azure_model import AZURE_COGNITIVE_SERVICES_SCOPE

    credentials = []
    credential_scopes = []
    credential_options = []

    class _FakeManagedIdentityCredential:
        def __init__(self, *args, **kwargs):
            credentials.append({"args": args, "kwargs": kwargs, "closed": False})
            self.instance = credentials[-1]

        async def get_token(self, *scopes, **kwargs):
            credential_scopes.append(tuple(scopes))
            credential_options.append(dict(kwargs))
            identity_index = credentials.index(self.instance) + 1
            return SimpleNamespace(token=f"system-mi-token-{identity_index}")

        async def close(self):
            self.instance["closed"] = True

    azure_module = ModuleType("azure")
    azure_module.__path__ = []  # type: ignore[attr-defined]
    identity_module = ModuleType("azure.identity")
    identity_aio_module = ModuleType("azure.identity.aio")
    identity_aio_module.ManagedIdentityCredential = _FakeManagedIdentityCredential
    identity_module.aio = identity_aio_module
    azure_module.identity = identity_module
    monkeypatch.setitem(sys.modules, "azure", azure_module)
    monkeypatch.setitem(sys.modules, "azure.identity", identity_module)
    monkeypatch.setitem(sys.modules, "azure.identity.aio", identity_aio_module)

    monkeypatch.setenv(FRONTIER_RESEARCH_PROFILE.endpoint_env, "https://unit.openai.azure.com/")
    monkeypatch.setenv(FRONTIER_RESEARCH_PROFILE.deployment_env, "GPT-6-Luna")
    monkeypatch.delenv("AZURE_OPENAI_GPT56_FRONTIER_KEY", raising=False)
    for name in _AZURE_IDENTITY_SELECTOR_ENV:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "decoy-key-must-not-be-used")
    monkeypatch.setenv(PROVIDER_CALLS_ALLOWED_ENV, "1")
    monkeypatch.setenv(PROVIDER_PROFILE_SHA256_ENV, FRONTIER_RESEARCH_PROFILE.sha256())

    solver, verifier = build_frontier_research_models()

    assert credentials == []
    expected_constructor_options = {
        "connection_timeout": 5.0,
        "read_timeout": 5.0,
        "timeout": 5.0,
        "retry_total": 0,
        "retry_connect": 0,
        "retry_read": 0,
        "retry_status": 0,
    }
    for identity_index, (model, expected_timeout_s) in enumerate(
        zip((solver, verifier), (1200, 170)), start=1,
    ):
        assert model._deployment == "GPT-6-Luna"
        assert model._effort == "high"
        assert model._prompt_cache_mode == "stable_prefix"
        assert model._responses_websocket is True
        assert model._responses_background is False
        assert model._poll_timeout_s == expected_timeout_s
        assert model._websocket_transport._request_timeout_s == expected_timeout_s
        assert model._websocket_transport._persist_completed_connection is True
        assert model._websocket_transport._bearer_token_provider is None
        assert callable(model._websocket_transport._deadline_bearer_token_provider)

        model._client._prepare_options(
            FinalRequestOptions(method="GET", url="/models")
        )
        assert model._client.auth_headers == {
            "Authorization": f"Bearer system-mi-token-{identity_index}"
        }
        assert credentials[-1]["args"] == ()
        assert credentials[-1]["kwargs"] == expected_constructor_options
        model.close_run_transport()

    assert credential_scopes == [
        (AZURE_COGNITIVE_SERVICES_SCOPE,),
        (AZURE_COGNITIVE_SERVICES_SCOPE,),
    ]
    assert credential_options == [
        {},
        {},
    ]
    assert all(row["closed"] for row in credentials)


def test_lq1_managed_identity_late_token_cannot_dispatch_websocket_request(monkeypatch) -> None:
    import sys
    from types import ModuleType

    import aether.providers.azure_model as azure_model
    from aether.providers.responses_websocket import ResponsesWebSocketError

    clock = {"now": 0.0}
    constructor_options = []
    token_requests = []
    factory_calls = []

    class _FakeManagedIdentityCredential:
        def __init__(self, *args, **kwargs):
            constructor_options.append({"args": args, "kwargs": dict(kwargs)})

        async def get_token(self, *scopes, **kwargs):
            token_requests.append({"scopes": tuple(scopes), "kwargs": dict(kwargs)})
            # Simulate auth returning after the absolute WebSocket deadline.
            clock["now"] += 1.0
            return SimpleNamespace(token="synthetic-system-mi-token")

        async def close(self):
            pass

    azure_module = ModuleType("azure")
    azure_module.__path__ = []  # type: ignore[attr-defined]
    identity_module = ModuleType("azure.identity")
    identity_aio_module = ModuleType("azure.identity.aio")
    identity_aio_module.ManagedIdentityCredential = _FakeManagedIdentityCredential
    identity_module.aio = identity_aio_module
    azure_module.identity = identity_module
    monkeypatch.setitem(sys.modules, "azure", azure_module)
    monkeypatch.setitem(sys.modules, "azure.identity", identity_module)
    monkeypatch.setitem(sys.modules, "azure.identity.aio", identity_aio_module)
    monkeypatch.setattr(azure_model, "provider_budget_guard_from_env", lambda **_kwargs: None)
    monkeypatch.setenv(FRONTIER_RESEARCH_PROFILE.endpoint_env, "https://unit.openai.azure.com/")
    monkeypatch.setenv(FRONTIER_RESEARCH_PROFILE.deployment_env, "GPT-6-Luna")
    monkeypatch.delenv("AZURE_OPENAI_GPT56_FRONTIER_KEY", raising=False)
    for name in _AZURE_IDENTITY_SELECTOR_ENV:
        monkeypatch.delenv(name, raising=False)

    model = azure_model.make_azure_callable(
        deployment_env=FRONTIER_RESEARCH_PROFILE.deployment_env,
        key_env=FRONTIER_RESEARCH_PROFILE.key_env,
        endpoint_env=FRONTIER_RESEARCH_PROFILE.endpoint_env,
        credential_mode=SYSTEM_ASSIGNED_MANAGED_IDENTITY_CREDENTIAL_MODE,
        expected_model_id="gpt-6-luna",
        effort="high",
        role="solver",
        poll_timeout_s=1200,
        responses_background=False,
        responses_websocket=True,
        responses_websocket_persistent=True,
        max_retries=0,
        sdk_max_retries=0,
    )

    def forbidden_socket_factory(*args, **kwargs):
        factory_calls.append((args, kwargs))
        raise AssertionError("late token must not open a provider socket")

    transport = model._websocket_transport
    transport._monotonic = lambda: clock["now"]
    transport._connection_factory = forbidden_socket_factory
    try:
        with pytest.raises(ResponsesWebSocketError) as excinfo:
            transport.call({"model": "GPT-6-Luna"}, timeout_s=0.25)
    finally:
        model.close_run_transport()

    assert excinfo.value.replay_safety_reason == "request_deadline_exceeded_before_dispatch"
    assert excinfo.value.provider_acceptance_unknown_after_dispatch is False
    assert factory_calls == []
    assert len(constructor_options) == 1
    assert constructor_options[0] == {
        "args": (),
        "kwargs": {
            "connection_timeout": 0.25,
            "read_timeout": 0.25,
            "timeout": 0.25,
            "retry_total": 0,
            "retry_connect": 0,
            "retry_read": 0,
            "retry_status": 0,
        },
    }
    assert token_requests == [
        {
            "scopes": ("https://cognitiveservices.azure.com/.default",),
            "kwargs": {},
        },
    ]


def test_lq1_real_async_managed_identity_cancels_slow_sdk_io_before_provider_dispatch(
    monkeypatch,
) -> None:
    import asyncio
    import json
    import socket
    import time

    import aether.providers.azure_model as azure_model
    from aether.providers.responses_websocket import ResponsesWebSocketError

    identity_aio = pytest.importorskip("azure.identity.aio")
    transport_types = pytest.importorskip("azure.core.pipeline.transport")
    azure_exceptions = pytest.importorskip("azure.core.exceptions")

    real_managed_identity_credential = identity_aio.ManagedIdentityCredential
    real_transport_close = transport_types.AioHttpTransport.close
    modes = iter(("slow", "retryable_error", "success"))
    transport_records = {}
    constructor_options = []
    provider_socket_calls = []

    class _FakeAsyncResponse(transport_types.AsyncHttpResponse):
        def __init__(self, request):
            super().__init__(request, None)
            self.status_code = 200
            self.headers = {"Content-Type": "application/json"}
            self.reason = "OK"

        def body(self):
            return json.dumps({
                "access_token": "synthetic-managed-identity-token",
                "expires_in": 3600,
                "resource": "https://cognitiveservices.azure.com/",
                "token_type": "Bearer",
            }).encode("utf-8")

        async def stream_download(self, pipeline, **kwargs):
            yield self.body()

    async def test_owned_transport_send(transport, request, **kwargs):
        record = transport_records[id(transport)]
        record["send_calls"] += 1
        record["send_options"].append(dict(kwargs))
        record["request_urls"].append(request.url)
        if record["mode"] == "slow":
            try:
                await asyncio.sleep(1.0)
            except asyncio.CancelledError:
                record["cancelled"] = True
                raise
            return _FakeAsyncResponse(request)
        if record["mode"] == "retryable_error":
            raise azure_exceptions.ServiceRequestError("synthetic retryable transport failure")
        return _FakeAsyncResponse(request)

    async def counted_transport_close(transport):
        record = transport_records.get(id(transport))
        if record is not None:
            record["close_calls"] += 1
        await real_transport_close(transport)

    class _InjectedRealManagedIdentityCredential:
        def __init__(self, *args, **kwargs):
            constructor_options.append({"args": args, "kwargs": dict(kwargs)})
            self._credential = real_managed_identity_credential(*args, **kwargs)
            pipeline = self._credential._credential._client._pipeline
            transport = pipeline._transport
            retry_policy = next(
                policy for policy in pipeline._impl_policies
                if hasattr(policy, "total_retries")
            )
            transport_records[id(transport)] = {
                "mode": next(modes),
                "send_calls": 0,
                "send_options": [],
                "request_urls": [],
                "cancelled": False,
                "close_calls": 0,
                "transport": transport,
                "retry_policy": retry_policy,
            }

        async def get_token(self, *scopes, **kwargs):
            return await self._credential.get_token(*scopes, **kwargs)

        async def close(self):
            await self._credential.close()

    monkeypatch.setattr(identity_aio, "ManagedIdentityCredential", _InjectedRealManagedIdentityCredential)
    monkeypatch.setattr(transport_types.AioHttpTransport, "send", test_owned_transport_send)
    monkeypatch.setattr(transport_types.AioHttpTransport, "close", counted_transport_close)
    monkeypatch.setattr(azure_model, "provider_budget_guard_from_env", lambda **_kwargs: None)

    def forbid_unowned_network(*args, **kwargs):
        raise AssertionError("test unexpectedly attempted an unowned network connection")

    monkeypatch.setattr(socket, "create_connection", forbid_unowned_network)
    monkeypatch.setenv(FRONTIER_RESEARCH_PROFILE.endpoint_env, "https://unit.openai.azure.com/")
    monkeypatch.setenv(FRONTIER_RESEARCH_PROFILE.deployment_env, "GPT-6-Luna")
    monkeypatch.setenv("OPENAI_API_KEY", "decoy-key-must-not-be-used")
    for name in _AZURE_IDENTITY_SELECTOR_ENV:
        monkeypatch.delenv(name, raising=False)

    def forbidden_provider_socket(*args, **kwargs):
        provider_socket_calls.append((args, kwargs))
        raise AssertionError("managed identity timeout must happen before provider socket creation")

    def make_model():
        return azure_model.make_azure_callable(
            deployment_env=FRONTIER_RESEARCH_PROFILE.deployment_env,
            key_env=FRONTIER_RESEARCH_PROFILE.key_env,
            endpoint_env=FRONTIER_RESEARCH_PROFILE.endpoint_env,
            credential_mode=SYSTEM_ASSIGNED_MANAGED_IDENTITY_CREDENTIAL_MODE,
            expected_model_id="gpt-6-luna",
            effort="high",
            role="solver",
            poll_timeout_s=2.0,
            responses_background=False,
            responses_websocket=True,
            responses_websocket_persistent=False,
            max_retries=0,
            sdk_max_retries=0,
        )

    slow_model = make_model()
    slow_model._websocket_transport._connection_factory = forbidden_provider_socket
    started = time.monotonic()
    try:
        with pytest.raises(ResponsesWebSocketError) as timeout_exc:
            slow_model._websocket_transport.call({"model": "GPT-6-Luna"}, timeout_s=0.15)
    finally:
        slow_model.close_run_transport()
    elapsed_s = time.monotonic() - started

    assert timeout_exc.value.replay_safety_reason == "request_deadline_exceeded_before_dispatch"
    assert timeout_exc.value.provider_acceptance_unknown_after_dispatch is False
    assert elapsed_s < 0.75
    assert len(transport_records) == 1
    slow_transport = next(iter(transport_records.values()))
    assert slow_transport["send_calls"] == 1
    assert slow_transport["cancelled"] is True
    assert slow_transport["close_calls"] >= 1
    assert len(slow_transport["request_urls"]) == 1
    assert slow_transport["request_urls"][0].startswith(
        "http://169.254.169.254/metadata/identity/oauth2/token?"
    )
    connection_config = slow_transport["transport"].connection_config
    assert 0 < connection_config.timeout <= 0.15
    assert 0 < connection_config.read_timeout <= 0.15
    slow_retry_policy = slow_transport["retry_policy"]
    assert 0 < slow_retry_policy.timeout <= 0.15
    assert slow_retry_policy.total_retries == 0
    assert slow_retry_policy.connect_retries == 0
    assert slow_retry_policy.read_retries == 0
    assert slow_retry_policy.status_retries == 0
    assert constructor_options[0]["args"] == ()
    slow_options = constructor_options[0]["kwargs"]
    assert 0 < slow_options["connection_timeout"] <= 0.15
    assert 0 < slow_options["read_timeout"] <= 0.15
    assert 0 < slow_options["timeout"] <= 0.15
    assert slow_options["retry_total"] == 0
    assert slow_options["retry_connect"] == 0
    assert slow_options["retry_read"] == 0
    assert slow_options["retry_status"] == 0

    retry_model = make_model()
    retry_model._websocket_transport._connection_factory = forbidden_provider_socket
    try:
        with pytest.raises(ResponsesWebSocketError, match="connect failed"):
            retry_model._websocket_transport.call({"model": "GPT-6-Luna"}, timeout_s=1.0)
    finally:
        retry_model.close_run_transport()

    retry_transport = next(
        row for row in transport_records.values() if row["mode"] == "retryable_error"
    )
    assert retry_transport["send_calls"] == 1
    assert retry_transport["close_calls"] >= 1
    assert retry_transport["retry_policy"].total_retries == 0
    assert constructor_options[1]["kwargs"]["retry_total"] == 0
    assert constructor_options[1]["kwargs"]["retry_connect"] == 0
    assert constructor_options[1]["kwargs"]["retry_read"] == 0
    assert constructor_options[1]["kwargs"]["retry_status"] == 0
    assert provider_socket_calls == []

    class _ProviderSocketFake:
        def __init__(self):
            self.events = [json.dumps({
                "type": "response.completed",
                "response": {"id": "resp-real-sdk-token", "status": "completed", "output": []},
            })]
            self.sent = []
            self.closed = False

        def settimeout(self, _timeout_s):
            return None

        def send(self, payload):
            self.sent.append(payload)

        def recv(self):
            return self.events.pop(0)

        def close(self):
            self.closed = True

    provider_socket = _ProviderSocketFake()
    provider_headers = []
    success_model = make_model()

    def provider_socket_factory(_endpoint, **kwargs):
        provider_headers.extend(kwargs.get("header", []))
        return provider_socket

    success_model._websocket_transport._connection_factory = provider_socket_factory
    try:
        success_response = success_model._websocket_transport.call(
            {"model": "GPT-6-Luna"},
            timeout_s=1.0,
        )
    finally:
        success_model.close_run_transport()

    assert success_response.id == "resp-real-sdk-token"
    assert provider_headers == ["Authorization: Bearer synthetic-managed-identity-token"]
    assert len(provider_socket.sent) == 1
    assert provider_socket.closed is True
    success_transport = next(
        row for row in transport_records.values() if row["mode"] == "success"
    )
    assert success_transport["send_calls"] == 1
    assert success_transport["close_calls"] >= 1


@pytest.mark.parametrize("identity_env", _AZURE_IDENTITY_SELECTOR_ENV)
def test_lq1_managed_identity_fails_closed_on_non_vm_identity_environment(
    monkeypatch, identity_env: str,
) -> None:
    import aether.providers.azure_model as azure_model

    from aether.model_profile import SYSTEM_ASSIGNED_MANAGED_IDENTITY_CREDENTIAL_MODE
    from aether.providers.azure_model import AzureModelError, make_azure_callable

    monkeypatch.setattr(azure_model, "provider_budget_guard_from_env", lambda **_kwargs: None)
    monkeypatch.setenv(FRONTIER_RESEARCH_PROFILE.endpoint_env, "https://unit.openai.azure.com/")
    monkeypatch.setenv(FRONTIER_RESEARCH_PROFILE.deployment_env, "GPT-6-Luna")
    monkeypatch.delenv("AZURE_OPENAI_GPT56_FRONTIER_KEY", raising=False)
    for name in _AZURE_IDENTITY_SELECTOR_ENV:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv(identity_env, "selector-must-not-be-used")

    with pytest.raises(AzureModelError, match="environment detected"):
        make_azure_callable(
            deployment_env=FRONTIER_RESEARCH_PROFILE.deployment_env,
            key_env=FRONTIER_RESEARCH_PROFILE.key_env,
            endpoint_env=FRONTIER_RESEARCH_PROFILE.endpoint_env,
            credential_mode=SYSTEM_ASSIGNED_MANAGED_IDENTITY_CREDENTIAL_MODE,
            effort="high",
            role="solver",
            responses_background=False,
            responses_websocket=True,
            responses_websocket_persistent=False,
        )
