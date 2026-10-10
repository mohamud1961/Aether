from __future__ import annotations

import json
import os
import socket as socket_module
import sys
from pathlib import Path
from typing import Callable

import pytest

from aether import provider_budget
from aether import provider_runtime_canary as canary
from aether.model_profile import PROVIDER_CALLS_ALLOWED_ENV, PROVIDER_PROFILE_SHA256_ENV
from aether.research_frontier_profile import FRONTIER_RESEARCH_PROFILE
from aether.providers import azure_model


OFFLINE_TOKEN = "offline-mi-token-must-not-be-persisted"
RETURNED_MODEL = "gpt-6-luna-2026-09-22"


def _contract(*, agent_timeout_sec: float = 360.0) -> dict[str, object]:
    role = {
        "max_input_tokens": 30_000,
        "max_output_tokens": 2_000,
        "input_gbp_per_million": "0.20",
        "output_gbp_per_million": "1.20",
    }
    return {
        "schema_version": "aether.provider_budget.v1",
        "budget_id": "gpt6-frontier-canary-smoke-test",
        "model_id": "gpt-6-luna",
        "currency": "GBP",
        "budget_constrained": True,
        "total_cap_gbp": "0.02",
        "provider_max_retries": 0,
        "provider_sdk_max_retries": 0,
        "solver_turn_budget": 2,
        "agent_timeout_sec": agent_timeout_sec,
        "vm_incremental_cap_gbp": "0",
        "roles": {
            "solver": {**role, "max_provider_creates": 2},
            "verifier": {**role, "max_provider_creates": 0},
            "vision": {**role, "max_provider_creates": 0},
        },
    }


class _OfflineSocket:
    def __init__(
        self,
        *,
        returned_model: str = RETURNED_MODEL,
        echo_kind: str | None = None,
        on_second_response: Callable[[], None] | None = None,
    ) -> None:
        self.returned_model = returned_model
        self.echo_kind = echo_kind
        self.on_second_response = on_second_response
        self.requests: list[dict[str, object]] = []
        self._events: list[str] = []
        self.closed = False
        self.timeout_values: list[float] = []

    def settimeout(self, timeout: float) -> None:
        self.timeout_values.append(float(timeout))
        return None

    def send(self, raw: str) -> None:
        request = json.loads(raw)
        self.requests.append(request)
        ordinal = len(self.requests)
        paths = [
            "/tmp/aether-provider-canary-unit.txt",
            "/tmp/aether-provider-canary-unit-continuation.txt",
        ]
        response_id = OFFLINE_TOKEN if self.echo_kind == "response_id" else f"offline-response-{ordinal}"
        call_id = OFFLINE_TOKEN if self.echo_kind == "call_id" else f"offline-call-{ordinal}"
        arguments: dict[str, object] = {"arguments": {"path": paths[ordinal - 1]}}
        if self.echo_kind == "arguments":
            arguments["arguments"]["extra"] = OFFLINE_TOKEN
        response = {
            "id": response_id,
            "status": "completed",
            "model": self.returned_model,
            "output": [{
                "id": f"offline-item-{ordinal}",
                "type": "function_call",
                "status": "completed",
                "call_id": call_id,
                "name": "read_file",
                "arguments": json.dumps(arguments),
            }],
            "usage": {
                "input_tokens": 1_000,
                "output_tokens": 100,
                "total_tokens": 1_100,
                "input_tokens_details": {"cached_tokens": 0},
                "output_tokens_details": {"reasoning_tokens": 20},
            },
        }
        if self.echo_kind == "terminal_metadata":
            response["incomplete_details"] = {"reason": OFFLINE_TOKEN}
        if self.echo_kind == "terminal_failure":
            self._events.append(json.dumps({
                "type": "response.failed",
                "response": {
                    "id": response_id,
                    "status": "failed",
                    "model": self.returned_model,
                    "error": {"code": "offline-terminal-failure", "message": OFFLINE_TOKEN},
                },
            }))
            return
        self._events.extend([
            json.dumps({"type": "response.created", "response": {"id": response_id}}),
            json.dumps({"type": "response.completed", "response": response}),
        ])

    def recv(self) -> str:
        if not self._events:
            raise AssertionError("offline response event queue exhausted")
        raw = self._events.pop(0)
        event = json.loads(raw)
        if (
            self.on_second_response is not None
            and len(self.requests) == 2
            and event.get("type") == "response.completed"
            and event.get("response", {}).get("id") == "offline-response-2"
        ):
            self.on_second_response()
        return raw

    def close(self) -> None:
        self.closed = True


def _install_offline_io(
    monkeypatch: pytest.MonkeyPatch,
    *,
    returned_model: str = RETURNED_MODEL,
    fail_socket_with_token: bool = False,
    echo_kind: str | None = None,
    on_second_response: Callable[[], None] | None = None,
) -> tuple[_OfflineSocket, list[object]]:
    socket = _OfflineSocket(
        returned_model=returned_model,
        echo_kind=echo_kind,
        on_second_response=on_second_response,
    )
    # Use the real async Azure Identity credential and Azure Core pipeline.
    # Its HTTP transport and the provider WebSocket are the only I/O seams.
    azure_identity_aio = pytest.importorskip("azure.identity.aio")
    azure_core_transport = pytest.importorskip("azure.core.pipeline.transport")
    websocket_module = pytest.importorskip("websocket")
    real_credential_type = azure_identity_aio.ManagedIdentityCredential
    AsyncHttpResponse = azure_core_transport.AsyncHttpResponse
    AioHttpTransport = azure_core_transport.AioHttpTransport
    credentials: list[object] = []
    closed_credentials: list[object] = []
    credential_constructor_kwargs: list[dict[str, object]] = []
    token_transport_requests: list[dict[str, object]] = []
    closed_async_transports: list[object] = []
    network_denials: list[str] = []
    credential_implementation_types: list[str] = []
    real_transport_close = AioHttpTransport.close

    class _OfflineAsyncHttpResponse(AsyncHttpResponse):
        def __init__(self, request: object) -> None:
            body = json.dumps({
                "access_token": OFFLINE_TOKEN,
                "expires_in": 3600,
                "resource": "https://cognitiveservices.azure.com/",
            }).encode("utf-8")
            super().__init__(request, internal_response=None)
            self.status_code = 200
            self.headers = {"Content-Type": "application/json"}
            self.content_type = "application/json"
            self.reason = "OK"
            self._body = body

        def body(self) -> bytes:
            return self._body

        async def load_body(self) -> None:
            return None

        async def read(self) -> bytes:
            return self._body

        async def close(self) -> None:
            return None

    async def offline_transport_send(
        self: object,
        request: object,
        **_kwargs: object,
    ) -> _OfflineAsyncHttpResponse:
        connection_config = getattr(self, "connection_config", None)
        token_transport_requests.append({
            "method": getattr(request, "method", None),
            "url": getattr(request, "url", None),
            "metadata_header": dict(getattr(request, "headers", {}) or {}).get("Metadata"),
            "connection_timeout": getattr(connection_config, "timeout", None),
            "read_timeout": getattr(connection_config, "read_timeout", None),
        })
        return _OfflineAsyncHttpResponse(request)

    async def observed_transport_close(self: object) -> None:
        closed_async_transports.append(self)
        await real_transport_close(self)

    class _RealManagedIdentityWithOfflineTransport:
        def __init__(self, **kwargs: object) -> None:
            self.constructor_kwargs = dict(kwargs)
            credential_constructor_kwargs.append(dict(kwargs))
            # Keep the real SDK constructor and its default Azure Core transport;
            # only AioHttpTransport's network-send method is patched offline.
            self.inner = real_credential_type(**kwargs)
            credential_implementation_types.append(
                type(getattr(self.inner, "_credential", None)).__name__
            )
            credentials.append(self)

        async def get_token(self, *scopes: str) -> object:
            return await self.inner.get_token(*scopes)

        async def close(self) -> None:
            await self.inner.close()
            closed_credentials.append(self)

    monkeypatch.setattr(AioHttpTransport, "send", offline_transport_send)
    monkeypatch.setattr(AioHttpTransport, "close", observed_transport_close)

    monkeypatch.setattr(
        azure_identity_aio,
        "ManagedIdentityCredential",
        _RealManagedIdentityWithOfflineTransport,
    )

    def deny_network(self: object, address: object) -> None:
        network_denials.append(str(address))
        raise AssertionError("outbound sockets are disabled in this offline test")

    monkeypatch.setattr(socket_module.socket, "connect", deny_network)
    monkeypatch.setattr(socket_module.socket, "connect_ex", deny_network)

    def create_connection(_url: str, *, header: list[str], timeout: float) -> _OfflineSocket:
        assert header == [f"Authorization: Bearer {OFFLINE_TOKEN}"]
        assert timeout <= canary.FRONTIER_REQUEST_DEADLINE_S
        if fail_socket_with_token:
            raise RuntimeError(f"synthetic websocket failure: Authorization: Bearer {OFFLINE_TOKEN}")
        return socket

    monkeypatch.setattr(websocket_module, "create_connection", create_connection)
    socket.token_transport_requests = token_transport_requests  # type: ignore[attr-defined]
    socket.credential_constructor_kwargs = credential_constructor_kwargs  # type: ignore[attr-defined]
    socket.credentials = credentials  # type: ignore[attr-defined]
    socket.closed_credentials = closed_credentials  # type: ignore[attr-defined]
    socket.closed_async_transports = closed_async_transports  # type: ignore[attr-defined]
    socket.network_denials = network_denials  # type: ignore[attr-defined]
    socket.credential_implementation_types = credential_implementation_types  # type: ignore[attr-defined]
    return socket, credentials


def _install_budget(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    agent_timeout_sec: float = 360.0,
) -> None:
    contract = provider_budget.parse_budget_contract(
        _contract(agent_timeout_sec=agent_timeout_sec),
    )
    path = tmp_path / "canary-budget.json"
    path.write_text(json.dumps(contract.as_dict(), sort_keys=True) + "\n", encoding="utf-8")
    monkeypatch.setenv(provider_budget.BUDGET_PATH_ENV, str(path))
    monkeypatch.setenv(provider_budget.BUDGET_SHA256_ENV, contract.sha256())
    monkeypatch.setenv(
        provider_budget.BUDGET_JOURNAL_ENV,
        str(tmp_path / "provider-budget-reservations.jsonl"),
    )
    provider_budget.clear_provider_budget_guard_cache_for_tests()


def _run_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, output_name: str = "receipt.json") -> tuple[int, dict[str, object], str]:
    output = tmp_path / output_name
    monkeypatch.setattr(sys, "argv", [
        "aether.provider_runtime_canary",
        "--label", "unit",
        "--output", str(output),
        "--profile", "frontier-research-v1",
        "--mode", "bounded-canary-smoke",
    ])
    result = canary.main()
    return result, json.loads(output.read_text(encoding="utf-8")), output.read_text(encoding="utf-8")


def _prepare_cli(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    returned_model: str = RETURNED_MODEL,
    fail_socket_with_token: bool = False,
    echo_kind: str | None = None,
    on_second_response: Callable[[], None] | None = None,
    agent_timeout_sec: float = 360.0,
):
    socket, credentials = _install_offline_io(
        monkeypatch,
        returned_model=returned_model,
        fail_socket_with_token=fail_socket_with_token,
        echo_kind=echo_kind,
        on_second_response=on_second_response,
    )
    _install_budget(
        tmp_path, monkeypatch, agent_timeout_sec=agent_timeout_sec,
    )
    monkeypatch.setenv(PROVIDER_CALLS_ALLOWED_ENV, "1")
    monkeypatch.setenv(PROVIDER_PROFILE_SHA256_ENV, FRONTIER_RESEARCH_PROFILE.sha256())
    monkeypatch.setenv(FRONTIER_RESEARCH_PROFILE.endpoint_env, "https://unit.openai.azure.com/")
    monkeypatch.setenv(FRONTIER_RESEARCH_PROFILE.deployment_env, "GPT-6-Luna")
    monkeypatch.setenv("AETHER_SOURCE_COMMIT", "1" * 40)
    monkeypatch.setenv("AETHER_RUNTIME_MANIFEST_SHA256", "2" * 64)
    monkeypatch.delenv("AETHER_CAPTURE_RAW_PROVIDER_REQUEST", raising=False)
    monkeypatch.delenv("AETHER_CAPTURE_RAW_PROVIDER_OUTPUT", raising=False)
    monkeypatch.delenv("AETHER_PROVIDER_LIFECYCLE_JOURNAL", raising=False)
    return socket, credentials


def _install_artifact_write_guard(monkeypatch: pytest.MonkeyPatch) -> tuple[list[str], list[str]]:
    writes: list[str] = []
    unsafe_attempts: list[str] = []
    original_write_text = Path.write_text
    secret_spellings = {
        OFFLINE_TOKEN,
        repr(OFFLINE_TOKEN),
        repr(OFFLINE_TOKEN.encode("utf-8")),
        str(OFFLINE_TOKEN.encode("utf-8")),
        json.dumps(OFFLINE_TOKEN, ensure_ascii=True),
        json.dumps(OFFLINE_TOKEN, ensure_ascii=False),
        json.dumps(OFFLINE_TOKEN, ensure_ascii=True)[1:-1],
        json.dumps(OFFLINE_TOKEN, ensure_ascii=False)[1:-1],
    }

    def guarded_write_text(self: Path, data: str, *args: object, **kwargs: object) -> int:
        rendered = str(data)
        writes.append(rendered)
        if any(spelling and spelling in rendered for spelling in secret_spellings):
            unsafe_attempts.append("access token reached Path.write_text")
            raise AssertionError("access token crossed the artifact write boundary")
        return original_write_text(self, data, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", guarded_write_text)
    return writes, unsafe_attempts


def _install_os_persistence_guard(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[list[bytes], list[int], list[str]]:
    writes: list[bytes] = []
    fsyncs: list[int] = []
    unsafe_attempts: list[str] = []
    buffers_by_fd: dict[int, bytearray] = {}
    original_write = os.write
    original_fsync = os.fsync
    token_bytes = {
        OFFLINE_TOKEN.encode("utf-8"),
        repr(OFFLINE_TOKEN).encode("utf-8"),
        repr(OFFLINE_TOKEN.encode("utf-8")).encode("utf-8"),
        str(OFFLINE_TOKEN.encode("utf-8")).encode("utf-8"),
        json.dumps(OFFLINE_TOKEN, ensure_ascii=True).encode("utf-8"),
        json.dumps(OFFLINE_TOKEN, ensure_ascii=False).encode("utf-8"),
        json.dumps(OFFLINE_TOKEN, ensure_ascii=True)[1:-1].encode("utf-8"),
        json.dumps(OFFLINE_TOKEN, ensure_ascii=False)[1:-1].encode("utf-8"),
    }

    def has_token(payload: bytes) -> bool:
        return any(spelling and spelling in payload for spelling in token_bytes)

    def guarded_write(fd: int, data: bytes | bytearray | memoryview) -> int:
        payload = bytes(data)
        writes.append(payload)
        if has_token(payload):
            unsafe_attempts.append("access token reached os.write")
            raise AssertionError("access token crossed the os.write boundary")
        buffers_by_fd.setdefault(fd, bytearray()).extend(payload)
        return original_write(fd, payload)

    def guarded_fsync(fd: int) -> None:
        if has_token(bytes(buffers_by_fd.get(fd, b""))):
            unsafe_attempts.append("access token reached os.fsync")
            raise AssertionError("access token crossed the os.fsync boundary")
        fsyncs.append(fd)
        original_fsync(fd)
        buffers_by_fd.pop(fd, None)

    monkeypatch.setattr(os, "write", guarded_write)
    monkeypatch.setattr(os, "fsync", guarded_fsync)
    return writes, fsyncs, unsafe_attempts


def test_exact_frontier_cli_executes_two_bounded_native_responses_offline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    socket, credentials = _prepare_cli(tmp_path, monkeypatch)
    writes, unsafe_attempts = _install_artifact_write_guard(monkeypatch)
    journal_path = tmp_path / "provider-lifecycle-safe.jsonl"
    monkeypatch.setenv("AETHER_PROVIDER_LIFECYCLE_JOURNAL", str(journal_path))
    os_writes, fsyncs, unsafe_os_attempts = _install_os_persistence_guard(monkeypatch)

    code, receipt, raw_artifact = _run_cli(tmp_path, monkeypatch)

    assert code == 0, receipt["worker"]["error"]
    assert receipt["passed"] is True
    assert receipt["profile_selector"] == "frontier-research-v1"
    assert receipt["mode"] == "bounded-canary-smoke"
    assert receipt["completed_provider_calls"] == 2
    assert receipt["provider_budget"]["snapshot"]["aggregate_create_count"] == 2
    assert receipt["provider_budget"]["snapshot"]["role_create_counts"] == {
        "solver": 2, "verifier": 0, "vision": 0,
    }
    assert receipt["provider_policy"]["request_deadline_s"] == 180
    assert receipt["provider_policy"]["max_input_tokens"] == 30_000
    assert receipt["provider_policy"]["max_output_tokens"] == 2_000
    assert receipt["provider_policy"]["cache_hit_claimed"] is False
    assert receipt["pricing"]["official_usd_per_million"]["short_input"] == 0.10
    assert receipt["pricing"]["reservation_rates_are_conservative_ceilings_not_gpt6_list_prices"] is True

    assert len(socket.requests) == 2
    first, second = socket.requests
    assert first["model"] == second["model"] == "GPT-6-Luna"
    assert first["reasoning"]["effort"] == second["reasoning"]["effort"] == "high"
    assert first["prompt_cache_key"] == second["prompt_cache_key"]
    assert "previous_response_id" not in first
    assert second["previous_response_id"] == "offline-response-1"
    assert second["input"] == [{
        "type": "function_call_output",
        "call_id": "offline-call-1",
        "output": json.dumps(
            [{
                "role": "user",
                "content": (
                    "Synthetic tool result for your previous read_file call: "
                    "the file contained 'AETHER_CANARY_SYNTHETIC_OK'. Now call "
                    "read_file for /tmp/aether-provider-canary-unit-continuation.txt."
                ),
            }],
            sort_keys=True,
            separators=(",", ":"),
        ),
    }]
    assert [row["provider_native_action"]["call_id"] for row in receipt["model_visible_turns"]] == [
        "offline-call-1", "offline-call-2",
    ]
    assert [row["returned_model"] for row in receipt["provider_attempt_telemetry"]] == [
        RETURNED_MODEL, RETURNED_MODEL,
    ]
    assert receipt["candidate"]["package_closure_sha256"]
    assert receipt["candidate"]["source_commit"] == "1" * 40
    assert receipt["provider_runtime"]["websocket_client_required"] is True
    assert receipt["provider_runtime"]["create_connection_available"] is True
    assert receipt["provider_runtime"]["network_calls_performed"] == 0
    assert OFFLINE_TOKEN not in raw_artifact
    assert "Authorization" not in raw_artifact
    assert "Bearer" not in raw_artifact
    assert credentials
    assert socket.closed_credentials == credentials
    assert socket.closed_async_transports
    assert socket.token_transport_requests
    assert all(name == "ImdsCredential" for name in socket.credential_implementation_types)
    assert all(call["connection_timeout"] <= 5 for call in socket.credential_constructor_kwargs)
    assert all(
        call["retry_total"] == call["retry_connect"] == call["retry_read"] == call["retry_status"] == 0
        for call in socket.credential_constructor_kwargs
    )
    assert all(call["metadata_header"] == "true" for call in socket.token_transport_requests)
    assert all(call["connection_timeout"] <= 5 for call in socket.token_transport_requests)
    assert all(call["read_timeout"] <= 5 for call in socket.token_transport_requests)
    assert socket.network_denials == []
    assert socket.closed is True
    assert len(writes) == 1
    assert unsafe_attempts == []
    lifecycle_events = [
        json.loads(line) for line in journal_path.read_text(encoding="utf-8").splitlines()
    ]
    assert any(row["stage"] == "provider_call_returned" for row in lifecycle_events)
    assert any(row.get("response_id") == "offline-response-1" for row in lifecycle_events)
    assert len(os_writes) >= len(lifecycle_events)
    assert fsyncs
    assert unsafe_os_attempts == []
    assert "AETHER_CAPTURE_RAW_PROVIDER_REQUEST" not in __import__("os").environ
    assert "AETHER_CAPTURE_RAW_PROVIDER_OUTPUT" not in __import__("os").environ


@pytest.mark.parametrize(
    "echo_kind",
    ["arguments", "response_id", "call_id", "terminal_metadata", "terminal_failure"],
)
def test_frontier_cli_rejects_provider_token_echoes_before_continuity_or_artifact_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    echo_kind: str,
) -> None:
    socket, credentials = _prepare_cli(
        tmp_path, monkeypatch, echo_kind=echo_kind,
    )
    lifecycle_path: Path | None = None
    os_boundary: tuple[list[bytes], list[int], list[str]] | None = None
    commit_calls: list[tuple[str, str]] = []
    if echo_kind == "response_id":
        lifecycle_path = tmp_path / "provider-lifecycle-echo.jsonl"
        monkeypatch.setenv("AETHER_PROVIDER_LIFECYCLE_JOURNAL", str(lifecycle_path))
        os_boundary = _install_os_persistence_guard(monkeypatch)
        original_commit = azure_model.AzureModelCallable.commit_pending_response

        def observe_commit(self: object, *, run_id: str, task_id: str) -> None:
            commit_calls.append((run_id, task_id))
            original_commit(self, run_id=run_id, task_id=task_id)

        monkeypatch.setattr(
            azure_model.AzureModelCallable,
            "commit_pending_response",
            observe_commit,
        )
    writes, unsafe_attempts = _install_artifact_write_guard(monkeypatch)

    code, receipt, raw_artifact = _run_cli(
        tmp_path, monkeypatch, output_name=f"echo-{echo_kind}.json",
    )
    captured = capsys.readouterr()
    token_spellings = {
        OFFLINE_TOKEN,
        repr(OFFLINE_TOKEN),
        repr(OFFLINE_TOKEN.encode("utf-8")),
        str(OFFLINE_TOKEN.encode("utf-8")),
        json.dumps(OFFLINE_TOKEN, ensure_ascii=True),
        json.dumps(OFFLINE_TOKEN, ensure_ascii=False),
        json.dumps(OFFLINE_TOKEN, ensure_ascii=True)[1:-1],
        json.dumps(OFFLINE_TOKEN, ensure_ascii=False)[1:-1],
    }

    assert code == 2
    assert receipt["passed"] is False
    assert receipt["provider_create_count"] == 1
    assert receipt["completed_provider_calls"] in {0, 1}
    assert receipt["provider_budget"]["snapshot"]["aggregate_create_count"] == 1
    assert receipt["provider_attempt_raw_evidence"]
    assert receipt["provider_attempt_raw_evidence"][0]["provider_websocket_request_dispatched"] is True
    assert receipt["provider_value_containment"]["token_bearing_provider_values_rejected"] is True
    assert receipt["provider_value_containment"]["rejected_fields"]
    assert len(socket.requests) == 1, "the contaminated first response must not be committed or continued"
    assert len(writes) == 1
    assert unsafe_attempts == []
    assert all(spelling not in raw_artifact for spelling in token_spellings if spelling)
    assert all(spelling not in captured.out for spelling in token_spellings if spelling)
    assert all(spelling not in captured.err for spelling in token_spellings if spelling)
    assert credentials
    assert socket.closed_credentials == credentials
    assert socket.network_denials == []
    if echo_kind == "response_id":
        assert receipt["provider_terminal_response_count"] == 1
        assert commit_calls == []
        assert any(
            "provider_returned_lifecycle_fields.response_id" in finding["path"]
            for finding in receipt["provider_value_containment"]["rejected_fields"]
        )
        assert lifecycle_path is not None
        lifecycle_events = [
            json.loads(line)
            for line in lifecycle_path.read_text(encoding="utf-8").splitlines()
        ]
        assert lifecycle_events
        assert not any(row.get("response_id") == OFFLINE_TOKEN for row in lifecycle_events)
        assert not any(row["stage"] == "provider_call_returned" for row in lifecycle_events)
        assert os_boundary is not None
        os_writes, fsyncs, unsafe_os_attempts = os_boundary
        assert os_writes
        assert fsyncs
        assert unsafe_os_attempts == []


def test_frontier_artifact_secret_guard_has_a_safe_false_control() -> None:
    with pytest.raises(canary._CanaryCheckFailure):
        canary._assert_serialized_artifact_secret_free(
            json.dumps({"provider_value": OFFLINE_TOKEN}), [OFFLINE_TOKEN],
        )
    canary._assert_serialized_artifact_secret_free(
        json.dumps({"provider_value": "safe synthetic value"}), [OFFLINE_TOKEN],
    )


def test_frontier_short_contract_deadline_rejects_late_second_response_without_third_create(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    clock_origin = __import__("time").monotonic()
    clock_offset = [0.0]
    monkeypatch.setattr(
        canary,
        "_monotonic",
        lambda: clock_origin + clock_offset[0],
    )

    def slow_second_response() -> None:
        clock_offset[0] += 11.0

    socket, credentials = _prepare_cli(
        tmp_path,
        monkeypatch,
        agent_timeout_sec=10.0,
        on_second_response=slow_second_response,
    )
    writes, unsafe_attempts = _install_artifact_write_guard(monkeypatch)

    code, receipt, raw_artifact = _run_cli(
        tmp_path, monkeypatch, output_name="late-second-response.json",
    )
    captured = capsys.readouterr()

    assert code == 2
    assert receipt["passed"] is False
    assert receipt["provider_policy"]["overall_deadline_s"] == 10.0
    assert receipt["worker"]["error"]["code"] == "overall_canary_deadline_exceeded"
    assert receipt["provider_budget"]["agent_timeout_sec"] == 10.0
    assert receipt["provider_budget"]["snapshot"]["aggregate_create_count"] == 2
    assert len(socket.requests) == 2, "late second response must not cause a third create"
    assert socket.timeout_values
    assert max(socket.timeout_values) <= 10.0
    assert len(writes) == 1
    assert unsafe_attempts == []
    assert OFFLINE_TOKEN not in raw_artifact
    assert OFFLINE_TOKEN not in captured.out
    assert OFFLINE_TOKEN not in captured.err
    assert credentials
    assert socket.closed_credentials == credentials
    assert socket.network_denials == []


def test_frontier_cli_fails_closed_on_wrong_returned_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    socket, _credentials = _prepare_cli(
        tmp_path, monkeypatch, returned_model="gpt-6-luna-wrong",
    )

    code, receipt, raw_artifact = _run_cli(tmp_path, monkeypatch)

    assert code == 2
    assert receipt["passed"] is False
    assert receipt["worker"]["error"]["code"] == "returned_model_identity_mismatch", receipt["worker"]["error"]
    assert len(socket.requests) == 1
    assert OFFLINE_TOKEN not in raw_artifact
    assert "Authorization" not in raw_artifact


def test_frontier_cli_fails_closed_when_previous_call_id_is_corrupted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    socket, _credentials = _prepare_cli(tmp_path, monkeypatch)
    original_commit = azure_model.AzureModelCallable.commit_pending_response

    def corrupt_after_commit(self, *, run_id: str, task_id: str) -> None:
        original_commit(self, run_id=run_id, task_id=task_id)
        if run_id == "provider-canary-unit" and task_id == "synthetic-provider-canary-unit":
            key = (run_id, task_id)
            self._persistent_continuity_states[key]["call_id"] = "wrong-prior-call-id"

    monkeypatch.setattr(
        azure_model.AzureModelCallable,
        "commit_pending_response",
        corrupt_after_commit,
    )

    code, receipt, raw_artifact = _run_cli(tmp_path, monkeypatch)

    assert code == 2
    assert receipt["passed"] is False
    assert receipt["worker"]["error"]["code"] == "native_previous_response_continuity_mismatch", receipt["worker"]["error"]
    assert len(socket.requests) == 2
    assert socket.requests[1]["previous_response_id"] == "offline-response-1"
    assert socket.requests[1]["input"][0]["call_id"] == "wrong-prior-call-id"
    assert OFFLINE_TOKEN not in raw_artifact
    assert "Authorization" not in raw_artifact


def test_frontier_cli_provider_error_artifact_redacts_token_bearing_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    socket, credentials = _prepare_cli(
        tmp_path, monkeypatch, fail_socket_with_token=True,
    )
    code, receipt, raw_artifact = _run_cli(tmp_path, monkeypatch, output_name="redacted-receipt.json")
    stdout = capsys.readouterr().out

    assert code == 2
    assert receipt["passed"] is False
    assert receipt["worker"]["error"]["message"] == "raw error detail omitted"
    assert receipt["worker"]["error"]["detail_sha256"]
    assert OFFLINE_TOKEN not in raw_artifact
    assert "Authorization" not in raw_artifact
    assert "Bearer" not in raw_artifact
    assert OFFLINE_TOKEN not in stdout
    assert "Authorization" not in stdout
    assert credentials
    assert socket.closed_credentials == credentials
    assert socket.requests == []
    assert socket.network_denials == []
