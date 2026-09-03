"""Persistent Azure Responses WebSocket transport.

This module is transport-only. It accepts the same finalized Responses request
mapping Aether would send over HTTP, strips the HTTP-only ``background`` flag,
sends one ``response.create`` event on one persistent socket, and returns the
terminal response as an attribute-shaped object for the existing provider
canonicalization path.
"""
from __future__ import annotations

import json
import math
import threading
import time
from types import SimpleNamespace
from typing import Any, Callable
from urllib.parse import urlparse


class ResponsesWebSocketError(RuntimeError):
    """A WebSocket request failed, with explicit replay-safety facts when known."""

    def __init__(
        self,
        message: str,
        *,
        terminal: bool = False,
        retry_safe: bool = False,
        provider_error_code: str | None = None,
        event_type: str | None = None,
        response_id: str | None = None,
        request_accepted: bool = False,
        partial_output_observed: bool = False,
        native_tool_call_observed: bool = False,
        native_tool_execution_observed: bool | None = None,
        incomplete_reason: str | None = None,
        replay_safety_reason: str | None = None,
        acceptance_known: bool = False,
        provider_acceptance_unknown_after_dispatch: bool = False,
    ) -> None:
        self.terminal = bool(terminal)
        self.retry_safe = bool(retry_safe)
        self.provider_error_code = (
            None if provider_error_code is None else str(provider_error_code)
        )
        self.event_type = None if event_type is None else str(event_type)
        self.response_id = None if response_id is None else str(response_id)
        # ``request_accepted`` is retained as a compatibility alias for the
        # observed acceptance bit. It must not be read as evidence that the
        # provider rejected a dispatched request when the bit is false.
        self.request_accepted = bool(request_accepted)
        self.acceptance_observed = self.request_accepted
        # An observed response lifecycle event makes acceptance known. A
        # dispatched request with no such event remains unknown, even when the
        # next event is a terminal server_error.
        self.acceptance_known = bool(acceptance_known or self.acceptance_observed)
        self.partial_output_observed = bool(partial_output_observed)
        self.native_tool_call_observed = bool(native_tool_call_observed)
        # The transport only observes provider output. Host-side native tool
        # execution occurs after canonicalization in the kernel and therefore
        # cannot be inferred from a WebSocket event. ``None`` means that the
        # provider stream supplied no observation either way.
        self.native_tool_execution_observed = (
            None
            if native_tool_execution_observed is None
            else bool(native_tool_execution_observed)
        )
        self.incomplete_reason = (
            None if incomplete_reason is None else str(incomplete_reason)
        )
        self.replay_safety_reason = (
            None if replay_safety_reason is None else str(replay_safety_reason)
        )
        # ``request_accepted=False`` means that no acceptance event was
        # observed. It is not evidence that the provider rejected or never
        # accepted the request after the client sent it.
        self.provider_acceptance_unknown_after_dispatch = bool(
            provider_acceptance_unknown_after_dispatch
        )
        super().__init__(message)


def _namespace(value: Any) -> Any:
    if isinstance(value, dict):
        return SimpleNamespace(**{str(k): _namespace(v) for k, v in value.items()})
    if isinstance(value, list):
        return [_namespace(v) for v in value]
    return value


def websocket_responses_endpoint(raw_endpoint: str) -> str:
    parsed = urlparse(str(raw_endpoint).strip())
    if not parsed.scheme or not parsed.netloc:
        raise ResponsesWebSocketError("invalid Azure endpoint for Responses WebSocket")
    return f"wss://{parsed.netloc}/openai/v1/responses"


_PARTIAL_OUTPUT_EVENT_TYPES = frozenset({
    "response.output_item.added",
    "response.output_item.done",
    "response.output_text.delta",
    "response.output_text.done",
    "response.content_part.added",
    "response.content_part.done",
    "response.function_call_arguments.delta",
    "response.function_call_arguments.done",
})
_NATIVE_TOOL_TYPES = frozenset({
    "function_call", "computer_call", "custom_tool_call",
})


def _event_response_id(event: dict[str, Any]) -> str | None:
    direct = event.get("response_id")
    if direct:
        return str(direct)
    response = event.get("response")
    if isinstance(response, dict) and response.get("id"):
        return str(response["id"])
    return None


def _event_native_tool_call(event: dict[str, Any], kind: str) -> bool:
    if kind in {
        "response.function_call_arguments.delta",
        "response.function_call_arguments.done",
    }:
        return True
    for key in ("item", "output_item"):
        item = event.get(key)
        if isinstance(item, dict) and str(item.get("type") or "") in _NATIVE_TOOL_TYPES:
            return True
    response = event.get("response")
    if isinstance(response, dict):
        output = response.get("output")
        if isinstance(output, list):
            return any(
                isinstance(item, dict) and str(item.get("type") or "") in _NATIVE_TOOL_TYPES
                for item in output
            )
    return False


def _event_incomplete_reason(event: dict[str, Any]) -> str | None:
    response = event.get("response")
    for value in (event, response):
        if not isinstance(value, dict):
            continue
        details = value.get("incomplete_details")
        if isinstance(details, dict) and details.get("reason"):
            return str(details["reason"])
    return None


class ResponsesWebSocketTransport:
    """One persistent Responses socket with cancellation-aware receive polling.

    Each provider turn owns one socket. After a terminal completed response the
    socket is closed deliberately; the next turn opens a fresh socket and
    continues from Aether's exact stored previous_response_id/call_id. A socket
    is never reconnected or replayed while a request is in flight.
    """

    def __init__(
        self,
        *,
        endpoint: str,
        api_key: str | None = None,
        bearer_token_provider: Callable[[], str] | None = None,
        deadline_bearer_token_provider: Callable[[float], str] | None = None,
        request_timeout_s: float = 1200.0,
        connect_timeout_s: float = 30.0,
        receive_slice_s: float = 0.5,
        connection_factory: Callable[..., Any] | None = None,
        persist_completed_connection: bool = False,
        monotonic_clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if sum(value is not None for value in (
            api_key, bearer_token_provider, deadline_bearer_token_provider,
        )) != 1:
            raise ValueError(
                "provide exactly one of api_key, bearer_token_provider, "
                "or deadline_bearer_token_provider"
            )
        self._endpoint = websocket_responses_endpoint(endpoint)
        self._api_key = None if api_key is None else str(api_key)
        self._bearer_token_provider = bearer_token_provider
        self._deadline_bearer_token_provider = deadline_bearer_token_provider
        self._request_timeout_s = self._finite_timeout_s(
            request_timeout_s, field_name="request_timeout_s"
        )
        self._connect_timeout_s = max(1.0, float(connect_timeout_s))
        self._receive_slice_s = max(0.05, float(receive_slice_s))
        self._connection_factory = connection_factory
        self._persist_completed_connection = bool(persist_completed_connection)
        self._monotonic = monotonic_clock
        self._ws: Any | None = None
        self._closed = False
        self._lock = threading.Lock()
        self._last_call_observability: dict[str, Any] = {}

    @staticmethod
    def _finite_timeout_s(value: float, *, field_name: str) -> float:
        timeout_s = float(value)
        if not math.isfinite(timeout_s) or timeout_s <= 0:
            raise ValueError(f"{field_name} must be finite and positive")
        return timeout_s

    def _remaining_s(self, deadline_at: float) -> float:
        return deadline_at - self._monotonic()

    @staticmethod
    def _deadline_error(
        *,
        dispatched: bool,
        request_accepted: bool = False,
        acceptance_known: bool = False,
        partial_output_observed: bool = False,
        native_tool_call_observed: bool = False,
        event_type: str | None = None,
        response_id: str | None = None,
    ) -> ResponsesWebSocketError:
        return ResponsesWebSocketError(
            "Responses WebSocket request deadline exceeded",
            event_type=event_type,
            response_id=response_id,
            request_accepted=request_accepted,
            partial_output_observed=partial_output_observed,
            native_tool_call_observed=native_tool_call_observed,
            replay_safety_reason=(
                "request_deadline_exceeded_after_dispatch"
                if dispatched else "request_deadline_exceeded_before_dispatch"
            ),
            acceptance_known=acceptance_known,
            provider_acceptance_unknown_after_dispatch=(
                dispatched and not acceptance_known
            ),
        )

    def _factory(self) -> Callable[..., Any]:
        if self._connection_factory is not None:
            return self._connection_factory
        try:
            import websocket  # type: ignore
        except ModuleNotFoundError as exc:  # pragma: no cover - packaging gate
            raise ResponsesWebSocketError(
                "websocket-client package is required for Responses WebSocket mode"
            ) from exc
        return websocket.create_connection

    def _connect(self, *, deadline_at: float) -> Any:
        if self._closed:
            raise ResponsesWebSocketError("Responses WebSocket transport is closed")
        if self._ws is not None:
            return self._ws
        remaining_s = self._remaining_s(deadline_at)
        if remaining_s <= 0:
            raise self._deadline_error(dispatched=False)
        ws: Any | None = None
        try:
            if self._deadline_bearer_token_provider is not None:
                token = self._deadline_bearer_token_provider(remaining_s)
            elif self._bearer_token_provider is not None:
                token = self._bearer_token_provider()
            else:
                token = self._api_key
            if not isinstance(token, str) or not token.strip():
                raise ResponsesWebSocketError("Responses WebSocket bearer token is empty")
            remaining_s = self._remaining_s(deadline_at)
            if remaining_s <= 0:
                raise self._deadline_error(dispatched=False)
            ws = self._factory()(
                self._endpoint,
                header=[f"Authorization: Bearer {token}"],
                timeout=min(self._connect_timeout_s, remaining_s),
            )
            remaining_s = self._remaining_s(deadline_at)
            if remaining_s <= 0:
                raise self._deadline_error(dispatched=False)
            settimeout = getattr(ws, "settimeout", None)
            if not callable(settimeout):
                raise ResponsesWebSocketError(
                    "Responses WebSocket cannot enforce the request deadline"
                )
            settimeout(min(self._receive_slice_s, remaining_s))
        except Exception as exc:
            if ws is not None:
                try:
                    ws.close()
                except Exception:
                    pass
            if isinstance(exc, ResponsesWebSocketError):
                raise
            if self._remaining_s(deadline_at) <= 0:
                raise self._deadline_error(dispatched=False) from exc
            raise ResponsesWebSocketError(f"Responses WebSocket connect failed: {exc}") from exc
        self._ws = ws
        return ws

    @staticmethod
    def _is_timeout(exc: BaseException) -> bool:
        # websocket-client's timeout class is optional at import time; compare
        # both its conventional class name and the stdlib TimeoutError.
        return isinstance(exc, TimeoutError) or exc.__class__.__name__ in {
            "WebSocketTimeoutException",
            "TimeoutError",
        }

    def _close_socket(self) -> None:
        ws, self._ws = self._ws, None
        if ws is None:
            return
        try:
            ws.close()
        except Exception:
            pass

    def last_call_observability(self) -> dict[str, Any]:
        """Return mechanical event-timing facts from the most recent call.

        Provider event bodies are not retained. The exact returned model ID
        and bounded counters distinguish the provider route and an active
        WebSocket event stream from a silent in-flight request.
        """
        return dict(self._last_call_observability)

    def call(
        self,
        request: dict[str, Any],
        *,
        timeout_s: float | None = None,
        cancellation_check: Callable[[], None] | None = None,
        lifecycle_observer: Callable[[str, dict[str, Any]], None] | None = None,
        inflight_guard: Callable[[dict[str, Any]], None] | None = None,
    ) -> Any:
        with self._lock:
            # A connect failure occurs before the main request's finally block.
            # Clear the prior receipt now so callers can never mistake stale
            # response/model facts for this call's outcome.
            self._last_call_observability = {}
            call_started = self._monotonic()
            request_timeout_s = (
                self._request_timeout_s
                if timeout_s is None
                else self._finite_timeout_s(timeout_s, field_name="timeout_s")
            )
            request_timeout_s = min(self._request_timeout_s, request_timeout_s)
            deadline_at = call_started + request_timeout_s
            if cancellation_check is not None:
                cancellation_check()
            connection_reused = self._ws is not None
            connect_started = self._monotonic()
            ws = self._connect(deadline_at=deadline_at)
            connect_elapsed_s = self._monotonic() - connect_started
            payload = dict(request)
            payload.pop("background", None)
            payload = {"type": "response.create", **payload}
            dispatched = False
            started = self._monotonic()
            event_count = 0
            event_type_counts: dict[str, int] = {}
            first_event_elapsed_s: float | None = None
            first_partial_output_elapsed_s: float | None = None
            first_native_tool_call_elapsed_s: float | None = None
            last_event_elapsed_s: float | None = None
            last_event_type: str | None = None
            output_item_added_type_counts: dict[str, int] = {}
            response_id: str | None = None
            returned_model: str | None = None
            returned_model_known = False
            request_accepted = False
            acceptance_known = False
            partial_output_observed = False
            native_tool_call_observed = False
            incomplete_reason: str | None = None
            replay_safety_reason: str | None = None
            receive_timeout_slice_count = 0
            receive_elapsed_s = 0.0
            json_decode_elapsed_s = 0.0
            serialization_started = self._monotonic()
            serialized_payload = json.dumps(
                payload, separators=(",", ":"), ensure_ascii=False
            )
            serialization_elapsed_s = self._monotonic() - serialization_started
            send_elapsed_s = 0.0
            completed = False

            def apply_inflight_guard() -> None:
                if inflight_guard is None:
                    return
                inflight_guard({
                    "request_dispatched": bool(dispatched),
                    "request_accepted": bool(request_accepted),
                    "acceptance_known": bool(acceptance_known),
                    "partial_output_observed": bool(partial_output_observed),
                    "native_tool_call_observed": bool(native_tool_call_observed),
                    "response_id": response_id,
                    "event_count": int(event_count),
                    "last_event_type": last_event_type,
                    "elapsed_s": max(0.0, self._monotonic() - started),
                })

            try:
                remaining_s = self._remaining_s(deadline_at)
                if remaining_s <= 0:
                    raise self._deadline_error(dispatched=False)
                settimeout = getattr(ws, "settimeout", None)
                if not callable(settimeout):
                    raise ResponsesWebSocketError(
                        "Responses WebSocket cannot enforce the request deadline"
                    )
                settimeout(remaining_s)
                send_started = self._monotonic()
                # A send-side timeout may happen after bytes reached the
                # provider. Record the attempt as dispatched before entering
                # the socket call so failures remain fail-closed.
                dispatched = True
                replay_safety_reason = "ambiguous_transport_failure_after_dispatch"
                try:
                    ws.send(serialized_payload)
                except Exception as exc:
                    if self._is_timeout(exc):
                        raise self._deadline_error(dispatched=True) from exc
                    replay_safety_reason = "ambiguous_transport_failure_after_dispatch"
                    raise ResponsesWebSocketError(
                        f"Responses WebSocket send failed: {exc}",
                        retry_safe=False,
                        event_type=last_event_type,
                        response_id=response_id,
                        request_accepted=request_accepted,
                        partial_output_observed=partial_output_observed,
                        native_tool_call_observed=native_tool_call_observed,
                        replay_safety_reason=replay_safety_reason,
                        acceptance_known=acceptance_known,
                        provider_acceptance_unknown_after_dispatch=(
                            dispatched and not acceptance_known
                        ),
                    ) from exc
                replay_safety_reason = None
                send_elapsed_s = self._monotonic() - send_started
                if lifecycle_observer is not None:
                    lifecycle_observer("request_dispatched", {})
                if self._remaining_s(deadline_at) <= 0:
                    raise self._deadline_error(dispatched=True)
                while True:
                    if cancellation_check is not None:
                        cancellation_check()
                    remaining_s = self._remaining_s(deadline_at)
                    if remaining_s <= 0:
                        raise self._deadline_error(
                            dispatched=dispatched,
                            request_accepted=request_accepted,
                            acceptance_known=acceptance_known,
                            partial_output_observed=partial_output_observed,
                            native_tool_call_observed=native_tool_call_observed,
                            event_type=last_event_type,
                            response_id=response_id,
                        )
                    settimeout = getattr(ws, "settimeout", None)
                    if not callable(settimeout):
                        replay_safety_reason = "ambiguous_transport_failure_after_dispatch"
                        raise ResponsesWebSocketError(
                            "Responses WebSocket cannot enforce the receive deadline",
                            retry_safe=False,
                            event_type=last_event_type,
                            response_id=response_id,
                            request_accepted=request_accepted,
                            partial_output_observed=partial_output_observed,
                            native_tool_call_observed=native_tool_call_observed,
                            replay_safety_reason=replay_safety_reason,
                            acceptance_known=acceptance_known,
                            provider_acceptance_unknown_after_dispatch=(
                                dispatched and not acceptance_known
                            ),
                        )
                    try:
                        settimeout(min(self._receive_slice_s, remaining_s))
                    except Exception as exc:
                        replay_safety_reason = "ambiguous_transport_failure_after_dispatch"
                        raise ResponsesWebSocketError(
                            f"Responses WebSocket receive timeout setup failed: {exc}",
                            retry_safe=False,
                            event_type=last_event_type,
                            response_id=response_id,
                            request_accepted=request_accepted,
                            partial_output_observed=partial_output_observed,
                            native_tool_call_observed=native_tool_call_observed,
                            replay_safety_reason=replay_safety_reason,
                            acceptance_known=acceptance_known,
                            provider_acceptance_unknown_after_dispatch=(
                                dispatched and not acceptance_known
                            ),
                        ) from exc
                    recv_started = self._monotonic()
                    try:
                        raw = ws.recv()
                    except Exception as exc:
                        receive_elapsed_s += self._monotonic() - recv_started
                        if self._is_timeout(exc):
                            receive_timeout_slice_count += 1
                            apply_inflight_guard()
                            if self._remaining_s(deadline_at) <= 0:
                                raise self._deadline_error(
                                    dispatched=dispatched,
                                    request_accepted=request_accepted,
                                    acceptance_known=acceptance_known,
                                    partial_output_observed=partial_output_observed,
                                    native_tool_call_observed=native_tool_call_observed,
                                    event_type=last_event_type,
                                    response_id=response_id,
                                ) from exc
                            continue
                        replay_safety_reason = (
                            "ambiguous_transport_failure_after_dispatch"
                            if dispatched else "transport_failure_before_dispatch"
                        )
                        raise ResponsesWebSocketError(
                            f"Responses WebSocket receive failed: {exc}",
                            event_type=last_event_type,
                            response_id=response_id,
                            request_accepted=request_accepted,
                            partial_output_observed=partial_output_observed,
                            native_tool_call_observed=native_tool_call_observed,
                            replay_safety_reason=replay_safety_reason,
                            acceptance_known=acceptance_known,
                            provider_acceptance_unknown_after_dispatch=(
                                dispatched and not acceptance_known
                            ),
                        ) from exc
                    receive_elapsed_s += self._monotonic() - recv_started
                    if raw is None:
                        replay_safety_reason = (
                            "ambiguous_transport_failure_after_dispatch"
                            if dispatched else "transport_failure_before_dispatch"
                        )
                        raise ResponsesWebSocketError(
                            "Responses WebSocket closed before terminal event",
                            event_type=last_event_type,
                            response_id=response_id,
                            request_accepted=request_accepted,
                            partial_output_observed=partial_output_observed,
                            native_tool_call_observed=native_tool_call_observed,
                            replay_safety_reason=replay_safety_reason,
                            acceptance_known=acceptance_known,
                            provider_acceptance_unknown_after_dispatch=(
                                dispatched and not acceptance_known
                            ),
                        )
                    decode_started = self._monotonic()
                    try:
                        event = json.loads(raw)
                    except Exception as exc:
                        json_decode_elapsed_s += self._monotonic() - decode_started
                        replay_safety_reason = "malformed_provider_event"
                        raise ResponsesWebSocketError(
                            "Responses WebSocket emitted invalid JSON",
                            event_type=last_event_type,
                            response_id=response_id,
                            request_accepted=request_accepted,
                            partial_output_observed=partial_output_observed,
                            native_tool_call_observed=native_tool_call_observed,
                            replay_safety_reason="malformed_provider_event",
                            acceptance_known=acceptance_known,
                            provider_acceptance_unknown_after_dispatch=(
                                dispatched and not acceptance_known
                            ),
                        ) from exc
                    json_decode_elapsed_s += self._monotonic() - decode_started
                    if not isinstance(event, dict):
                        replay_safety_reason = "malformed_provider_event"
                        raise ResponsesWebSocketError(
                            "Responses WebSocket emitted non-object JSON",
                            event_type=last_event_type,
                            response_id=response_id,
                            request_accepted=request_accepted,
                            partial_output_observed=partial_output_observed,
                            native_tool_call_observed=native_tool_call_observed,
                            replay_safety_reason="malformed_provider_event",
                            acceptance_known=acceptance_known,
                            provider_acceptance_unknown_after_dispatch=(
                                dispatched and not acceptance_known
                            ),
                        )
                    kind = str(event.get("type") or "")
                    last_event_type = kind or "unknown"
                    event_count += 1
                    event_type_counts[kind or "unknown"] = event_type_counts.get(kind or "unknown", 0) + 1
                    observed_response_id = _event_response_id(event)
                    if observed_response_id is not None:
                        response_id = observed_response_id
                    if kind.startswith("response.") or response_id is not None:
                        request_accepted = True
                        acceptance_known = True
                    event_has_partial_output = (
                        kind in _PARTIAL_OUTPUT_EVENT_TYPES
                        or (
                            isinstance(event.get("response"), dict)
                            and bool(event["response"].get("output"))
                        )
                    )
                    event_has_native_tool_call = _event_native_tool_call(event, kind)
                    if kind == "response.output_item.added":
                        item = event.get("item")
                        if not isinstance(item, dict):
                            item = event.get("output_item")
                        item_type = (
                            str(item.get("type") or "unknown")
                            if isinstance(item, dict) else "unknown"
                        )
                        output_item_added_type_counts[item_type] = (
                            output_item_added_type_counts.get(item_type, 0) + 1
                        )
                    partial_output_observed = partial_output_observed or event_has_partial_output
                    native_tool_call_observed = (
                        native_tool_call_observed or event_has_native_tool_call
                    )
                    event_reason = _event_incomplete_reason(event)
                    if event_reason is not None:
                        incomplete_reason = event_reason
                    if kind in {
                        "response.completed", "response.failed", "response.incomplete", "error",
                    }:
                        terminal_response = event.get("response")
                        if isinstance(terminal_response, dict):
                            raw_model = terminal_response.get("model")
                            if isinstance(raw_model, str):
                                returned_model = raw_model
                                returned_model_known = True
                    event_elapsed_s = self._monotonic() - started
                    if first_event_elapsed_s is None:
                        first_event_elapsed_s = event_elapsed_s
                        if lifecycle_observer is not None:
                            lifecycle_observer("first_provider_event", {"event_type": kind or "unknown"})
                    if event_has_partial_output and first_partial_output_elapsed_s is None:
                        first_partial_output_elapsed_s = event_elapsed_s
                    if event_has_native_tool_call and first_native_tool_call_elapsed_s is None:
                        first_native_tool_call_elapsed_s = event_elapsed_s
                    last_event_elapsed_s = event_elapsed_s
                    apply_inflight_guard()
                    if self._remaining_s(deadline_at) <= 0:
                        raise self._deadline_error(
                            dispatched=dispatched,
                            request_accepted=request_accepted,
                            acceptance_known=acceptance_known,
                            partial_output_observed=partial_output_observed,
                            native_tool_call_observed=native_tool_call_observed,
                            event_type=last_event_type,
                            response_id=response_id,
                        )
                    if kind == "response.completed":
                        if lifecycle_observer is not None:
                            lifecycle_observer("provider_terminal_event", {"event_type": kind})
                        response = event.get("response")
                        if not isinstance(response, dict):
                            replay_safety_reason = "malformed_terminal_provider_event"
                            raise ResponsesWebSocketError(
                                "response.completed missing response object",
                                event_type=kind,
                                response_id=response_id,
                                request_accepted=request_accepted,
                                partial_output_observed=partial_output_observed,
                                native_tool_call_observed=native_tool_call_observed,
                                replay_safety_reason=replay_safety_reason,
                                acceptance_known=acceptance_known,
                                provider_acceptance_unknown_after_dispatch=(
                                    dispatched and not acceptance_known
                                ),
                            )
                        terminal = _namespace(response)
                        completed = True
                        # Persistence is an explicit treatment. The default remains
                        # one socket per provider turn. When enabled, a completed
                        # request leaves the healthy task-scoped socket available
                        # for the next sequential response.create. Any failure or
                        # cancellation below still closes it without replay.
                        if not self._persist_completed_connection:
                            self._close_socket()
                        return terminal
                    if kind in {"response.failed", "response.incomplete", "error"}:
                        if lifecycle_observer is not None:
                            lifecycle_observer("provider_terminal_event", {"event_type": kind})
                        error_obj = event.get("error")
                        if not isinstance(error_obj, dict):
                            response_obj = event.get("response")
                            error_obj = (
                                response_obj.get("error")
                                if isinstance(response_obj, dict) and isinstance(response_obj.get("error"), dict)
                                else {}
                            )
                        error_code = str(error_obj.get("code") or error_obj.get("type") or "")
                        # A WebSocket terminal server_error occurs after the
                        # request was sent. Absence of response.created or
                        # output is not evidence that the provider rejected or
                        # did not accept that request, so no replay is marked
                        # safe from event ordering alone. A future provider
                        # protocol guarantee may supply an explicit safe
                        # signal; none is accepted by this transport today.
                        retry_safe = False
                        if error_code == "server_error" and (
                            request_accepted or partial_output_observed or native_tool_call_observed
                        ):
                            replay_safety_reason = (
                                "server_error_after_response_acceptance_or_partial_output"
                            )
                        elif error_code == "server_error":
                            replay_safety_reason = "server_error_replay_safety_unknown_after_dispatch"
                        elif kind == "response.incomplete":
                            replay_safety_reason = "provider_incomplete_response_not_replay_safe"
                        else:
                            replay_safety_reason = "terminal_provider_error_not_explicitly_replay_safe"
                        raise ResponsesWebSocketError(
                            "Responses WebSocket terminal failure: "
                            + json.dumps(event, sort_keys=True, default=str)[:4000],
                            terminal=True,
                            retry_safe=retry_safe,
                            provider_error_code=(error_code or None),
                            event_type=kind,
                            response_id=response_id,
                            request_accepted=request_accepted,
                            partial_output_observed=partial_output_observed,
                            native_tool_call_observed=native_tool_call_observed,
                            incomplete_reason=incomplete_reason,
                            replay_safety_reason=replay_safety_reason,
                            acceptance_known=acceptance_known,
                            provider_acceptance_unknown_after_dispatch=(
                                dispatched and not acceptance_known
                            ),
                        )
            except BaseException as exc:
                # A broken/cancelled persistent socket is never retained. Even a
                # send-side failure can be ambiguous after partial transmission,
                # so close and propagate rather than reconnect/replay silently.
                if (
                    isinstance(exc, ResponsesWebSocketError)
                    and exc.replay_safety_reason is not None
                ):
                    replay_safety_reason = exc.replay_safety_reason
                elif dispatched and not acceptance_known and replay_safety_reason is None:
                    replay_safety_reason = "ambiguous_transport_failure_after_dispatch"
                self._close_socket()
                raise
            finally:
                self._last_call_observability = {
                    "provider_websocket_event_count": event_count,
                    "provider_websocket_event_type_counts": dict(sorted(event_type_counts.items())),
                    "provider_websocket_last_event_type": last_event_type,
                    "provider_websocket_response_id": response_id,
                    "provider_websocket_request_timeout_s": request_timeout_s,
                    "returned_model": returned_model,
                    "returned_model_known": returned_model_known,
                    "provider_websocket_request_dispatched": dispatched,
                    "provider_websocket_request_accepted": request_accepted,
                    "provider_websocket_acceptance_observed": request_accepted,
                    "provider_websocket_acceptance_known": acceptance_known,
                    "provider_websocket_acceptance_unknown_after_dispatch": (
                        dispatched and not acceptance_known
                    ),
                    "provider_websocket_partial_output_observed": partial_output_observed,
                    "provider_websocket_native_tool_call_observed": native_tool_call_observed,
                    "provider_websocket_output_item_added_type_counts": dict(
                        sorted(output_item_added_type_counts.items())
                    ),
                    # Host-side execution is outside this transport. Keep it
                    # unknown rather than treating provider output as evidence
                    # that a host-side side effect did or did not occur.
                    "provider_websocket_native_tool_execution_observed": None,
                    "provider_websocket_incomplete_reason": incomplete_reason,
                    "provider_websocket_replay_safety_reason": replay_safety_reason,
                    "provider_websocket_first_event_elapsed_s": (
                        None if first_event_elapsed_s is None else round(first_event_elapsed_s, 3)
                    ),
                    "provider_websocket_first_partial_output_elapsed_s": (
                        None if first_partial_output_elapsed_s is None
                        else round(first_partial_output_elapsed_s, 3)
                    ),
                    "provider_websocket_first_native_tool_call_elapsed_s": (
                        None if first_native_tool_call_elapsed_s is None
                        else round(first_native_tool_call_elapsed_s, 3)
                    ),
                    "provider_websocket_last_event_elapsed_s": (
                        None if last_event_elapsed_s is None else round(last_event_elapsed_s, 3)
                    ),
                    "provider_websocket_receive_timeout_slice_count": receive_timeout_slice_count,
                    "provider_websocket_connect_elapsed_s": round(connect_elapsed_s, 6),
                    "provider_websocket_serialize_elapsed_s": round(serialization_elapsed_s, 6),
                    "provider_websocket_send_elapsed_s": round(send_elapsed_s, 6),
                    "provider_websocket_receive_elapsed_s": round(receive_elapsed_s, 6),
                    "provider_websocket_json_decode_elapsed_s": round(json_decode_elapsed_s, 6),
                    "provider_websocket_total_call_elapsed_s": round(
                        self._monotonic() - call_started, 6
                    ),
                    "provider_websocket_connection_reused": bool(connection_reused),
                    "provider_websocket_connection_persisted_after_completed": bool(
                        completed and self._persist_completed_connection and self._ws is not None
                    ),
                }

    def close(self) -> None:
        with self._lock:
            self._closed = True
            self._close_socket()
