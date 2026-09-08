"""Persistent Azure Responses WebSocket transport.

This module is transport-only. It accepts the same finalized Responses request
mapping Aether would send over HTTP, strips the HTTP-only ``background`` flag,
sends one ``response.create`` event on one persistent socket, and returns the
terminal response as an attribute-shaped object for the existing provider
canonicalization path.
"""
from __future__ import annotations

import json
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
    ) -> None:
        self.terminal = bool(terminal)
        self.retry_safe = bool(retry_safe)
        self.provider_error_code = (
            None if provider_error_code is None else str(provider_error_code)
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
        api_key: str,
        connect_timeout_s: float = 30.0,
        receive_slice_s: float = 0.5,
        connection_factory: Callable[..., Any] | None = None,
    ) -> None:
        self._endpoint = websocket_responses_endpoint(endpoint)
        self._api_key = str(api_key)
        self._connect_timeout_s = max(1.0, float(connect_timeout_s))
        self._receive_slice_s = max(0.05, float(receive_slice_s))
        self._connection_factory = connection_factory
        self._ws: Any | None = None
        self._closed = False
        self._lock = threading.Lock()
        self._last_call_observability: dict[str, Any] = {}

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

    def _connect(self) -> Any:
        if self._closed:
            raise ResponsesWebSocketError("Responses WebSocket transport is closed")
        if self._ws is not None:
            return self._ws
        try:
            ws = self._factory()(
                self._endpoint,
                header=[f"Authorization: Bearer {self._api_key}"],
                timeout=self._connect_timeout_s,
            )
            settimeout = getattr(ws, "settimeout", None)
            if callable(settimeout):
                settimeout(self._receive_slice_s)
        except Exception as exc:
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

        No provider event content is retained here. The counters exist only to
        distinguish an active WebSocket event stream from a silent in-flight
        request during later forensic analysis.
        """
        return dict(self._last_call_observability)

    def call(
        self,
        request: dict[str, Any],
        *,
        cancellation_check: Callable[[], None] | None = None,
    ) -> Any:
        with self._lock:
            if cancellation_check is not None:
                cancellation_check()
            ws = self._connect()
            payload = dict(request)
            payload.pop("background", None)
            payload = {"type": "response.create", **payload}
            dispatched = False
            started = time.monotonic()
            event_count = 0
            event_type_counts: dict[str, int] = {}
            first_event_elapsed_s: float | None = None
            last_event_elapsed_s: float | None = None
            receive_timeout_slice_count = 0
            try:
                ws.send(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))
                dispatched = True
                while True:
                    if cancellation_check is not None:
                        cancellation_check()
                    try:
                        raw = ws.recv()
                    except Exception as exc:
                        if self._is_timeout(exc):
                            receive_timeout_slice_count += 1
                            continue
                        raise ResponsesWebSocketError(
                            f"Responses WebSocket receive failed: {exc}"
                        ) from exc
                    if raw is None:
                        raise ResponsesWebSocketError("Responses WebSocket closed before terminal event")
                    try:
                        event = json.loads(raw)
                    except Exception as exc:
                        raise ResponsesWebSocketError(
                            "Responses WebSocket emitted invalid JSON"
                        ) from exc
                    kind = str(event.get("type") or "")
                    event_count += 1
                    event_type_counts[kind or "unknown"] = event_type_counts.get(kind or "unknown", 0) + 1
                    event_elapsed_s = time.monotonic() - started
                    if first_event_elapsed_s is None:
                        first_event_elapsed_s = event_elapsed_s
                    last_event_elapsed_s = event_elapsed_s
                    if kind == "response.completed":
                        response = event.get("response")
                        if not isinstance(response, dict):
                            raise ResponsesWebSocketError(
                                "response.completed missing response object"
                            )
                        terminal = _namespace(response)
                        # Reconnection is only legal after the provider has
                        # explicitly completed this model decision. Closing
                        # here makes the next turn independent of provider
                        # idle/socket lifetime while preserving exact stored
                        # previous_response continuity.
                        self._close_socket()
                        return terminal
                    if kind in {"response.failed", "response.incomplete", "error"}:
                        error_obj = event.get("error")
                        if not isinstance(error_obj, dict):
                            response_obj = event.get("response")
                            error_obj = (
                                response_obj.get("error")
                                if isinstance(response_obj, dict) and isinstance(response_obj.get("error"), dict)
                                else {}
                            )
                        error_code = str(error_obj.get("code") or error_obj.get("type") or "")
                        retry_safe = kind in {"response.failed", "error"} and error_code == "server_error"
                        raise ResponsesWebSocketError(
                            "Responses WebSocket terminal failure: "
                            + json.dumps(event, sort_keys=True, default=str)[:4000],
                            terminal=True,
                            retry_safe=retry_safe,
                            provider_error_code=(error_code or None),
                        )
            except BaseException:
                # Once a request has been sent, a broken/cancelled socket cannot
                # be silently replayed because that would duplicate cognition.
                if dispatched:
                    self._close_socket()
                raise
            finally:
                self._last_call_observability = {
                    "provider_websocket_event_count": event_count,
                    "provider_websocket_event_type_counts": dict(sorted(event_type_counts.items())),
                    "provider_websocket_first_event_elapsed_s": (
                        None if first_event_elapsed_s is None else round(first_event_elapsed_s, 3)
                    ),
                    "provider_websocket_last_event_elapsed_s": (
                        None if last_event_elapsed_s is None else round(last_event_elapsed_s, 3)
                    ),
                    "provider_websocket_receive_timeout_slice_count": receive_timeout_slice_count,
                }

    def close(self) -> None:
        with self._lock:
            self._closed = True
            self._close_socket()
