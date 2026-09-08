"""Tiny MCP client executed inside the Harbor task environment.

This module intentionally depends only on the Python standard library.  It is
uploaded into the task workspace by ``HarborEnvironmentExecutor`` so network
names declared by a task's Compose environment are resolved from the task
world, not from the Aether host.  It implements only the generic MCP handshake
plus tools/list and tools/call; no server- or benchmark-specific semantics live
here.
"""
from __future__ import annotations

import argparse
import json
import queue
import subprocess
import sys
import threading
import time
from typing import Any, BinaryIO
from urllib.parse import urljoin
from urllib.request import Request, urlopen


class MCPClientError(RuntimeError):
    pass


def _json_line(value: Any) -> bytes:
    return (json.dumps(value, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def _read_sse_events(stream: BinaryIO):
    event = "message"
    data_lines: list[str] = []
    while True:
        raw = stream.readline()
        if not raw:
            if data_lines:
                yield event, "\n".join(data_lines)
            return
        line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
        if not line:
            if data_lines:
                yield event, "\n".join(data_lines)
            event = "message"
            data_lines = []
            continue
        if line.startswith(":"):
            continue
        if line.startswith("event:"):
            event = line[6:].strip() or "message"
        elif line.startswith("data:"):
            data_lines.append(line[5:].lstrip())


def _json_rpc_from_http(response: Any, *, wanted_id: int) -> dict[str, Any]:
    content_type = str(response.headers.get("Content-Type", "")).lower()
    if "text/event-stream" in content_type:
        for _event, data in _read_sse_events(response):
            try:
                payload = json.loads(data)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict) and payload.get("id") == wanted_id:
                return payload
        raise MCPClientError(f"stream ended before JSON-RPC response id={wanted_id}")
    body = response.read().decode("utf-8", errors="replace").strip()
    if not body:
        raise MCPClientError(f"empty HTTP response for JSON-RPC id={wanted_id}")
    payload = json.loads(body)
    if not isinstance(payload, dict) or payload.get("id") != wanted_id:
        raise MCPClientError(f"unexpected JSON-RPC response for id={wanted_id}")
    return payload


def _rpc_result(payload: dict[str, Any]) -> Any:
    if "error" in payload:
        raise MCPClientError("MCP JSON-RPC error: " + json.dumps(payload["error"], sort_keys=True))
    if "result" not in payload:
        raise MCPClientError("MCP JSON-RPC response has no result")
    return payload["result"]


def _streamable_post(
    url: str,
    payload: dict[str, Any],
    *,
    timeout_s: float,
    session_id: str = "",
    protocol_version: str = "2025-06-18",
) -> tuple[dict[str, Any] | None, str]:
    method = str(payload.get("method") or "")
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": protocol_version,
        "Mcp-Method": method,
    }
    name = str(params.get("name") or params.get("uri") or "")
    if name:
        headers["Mcp-Name"] = name
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    request = Request(url, data=json.dumps(payload, separators=(",", ":")).encode("utf-8"), headers=headers, method="POST")
    response = urlopen(request, timeout=timeout_s)
    new_session = str(response.headers.get("Mcp-Session-Id", "") or session_id)
    if "id" not in payload:
        response.read()
        return None, new_session
    return _json_rpc_from_http(response, wanted_id=int(payload["id"])), new_session


def _run_streamable(config: dict[str, Any], operation: str, tool_name: str, arguments: dict[str, Any], timeout_s: float) -> Any:
    url = str(config["url"])
    initialize = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "aether-next", "version": "mcp-bridge-v1"},
        },
    }
    response, session = _streamable_post(url, initialize, timeout_s=timeout_s)
    assert response is not None
    _rpc_result(response)
    _streamable_post(
        url,
        {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
        timeout_s=timeout_s,
        session_id=session,
    )
    request = _operation_request(operation, tool_name, arguments, request_id=2)
    response, _session = _streamable_post(url, request, timeout_s=timeout_s, session_id=session)
    assert response is not None
    return _rpc_result(response)


class _LegacySSESession:
    def __init__(self, url: str, timeout_s: float) -> None:
        self.url = url
        self.timeout_s = timeout_s
        self.endpoint_queue: queue.Queue[str] = queue.Queue()
        self.message_queue: queue.Queue[dict[str, Any]] = queue.Queue()
        self.error_queue: queue.Queue[BaseException] = queue.Queue()
        self.response: Any | None = None
        self.thread = threading.Thread(target=self._listen, daemon=True)
        self.thread.start()
        self.post_url = self._wait_endpoint()

    def _listen(self) -> None:
        try:
            request = Request(self.url, headers={"Accept": "text/event-stream"}, method="GET")
            with urlopen(request, timeout=self.timeout_s) as response:
                self.response = response
                for event, data in _read_sse_events(response):
                    if event == "endpoint":
                        self.endpoint_queue.put(urljoin(self.url, data.strip()))
                        continue
                    try:
                        payload = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(payload, dict):
                        self.message_queue.put(payload)
        except BaseException as exc:  # transport thread must surface failure to caller
            self.error_queue.put(exc)

    def _wait_endpoint(self) -> str:
        deadline = time.monotonic() + self.timeout_s
        while time.monotonic() < deadline:
            try:
                return self.endpoint_queue.get(timeout=min(0.1, max(0.01, deadline - time.monotonic())))
            except queue.Empty:
                if not self.error_queue.empty():
                    raise MCPClientError(f"legacy SSE listener failed: {self.error_queue.get()}")
        raise MCPClientError("legacy SSE endpoint event timed out")

    def close(self) -> None:
        response = self.response
        if response is not None:
            try:
                response.close()
            except Exception:
                pass
        self.thread.join(timeout=1.0)

    def post(self, payload: dict[str, Any]) -> None:
        request = Request(
            self.post_url,
            data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=self.timeout_s) as response:
            response.read()

    def wait_response(self, request_id: int) -> dict[str, Any]:
        deadline = time.monotonic() + self.timeout_s
        deferred: list[dict[str, Any]] = []
        try:
            while time.monotonic() < deadline:
                if not self.error_queue.empty():
                    raise MCPClientError(f"legacy SSE listener failed: {self.error_queue.get()}")
                try:
                    payload = self.message_queue.get(timeout=min(0.1, max(0.01, deadline - time.monotonic())))
                except queue.Empty:
                    continue
                if payload.get("id") == request_id:
                    return payload
                deferred.append(payload)
        finally:
            for payload in deferred:
                self.message_queue.put(payload)
        raise MCPClientError(f"legacy SSE response id={request_id} timed out")


def _run_legacy_sse(config: dict[str, Any], operation: str, tool_name: str, arguments: dict[str, Any], timeout_s: float) -> Any:
    session = _LegacySSESession(str(config["url"]), timeout_s)
    initialize = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "aether-next", "version": "mcp-bridge-v1"},
        },
    }
    try:
        session.post(initialize)
        _rpc_result(session.wait_response(1))
        session.post({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
        request = _operation_request(operation, tool_name, arguments, request_id=2)
        session.post(request)
        return _rpc_result(session.wait_response(2))
    finally:
        session.close()


def _stdio_reader(stream: Any, output: queue.Queue[dict[str, Any]], errors: queue.Queue[BaseException]) -> None:
    try:
        for line in stream:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                output.put(payload)
    except BaseException as exc:
        errors.put(exc)


def _stdio_wait(output: queue.Queue[dict[str, Any]], errors: queue.Queue[BaseException], request_id: int, timeout_s: float) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_s
    deferred: list[dict[str, Any]] = []
    try:
        while time.monotonic() < deadline:
            if not errors.empty():
                raise MCPClientError(f"stdio reader failed: {errors.get()}")
            try:
                payload = output.get(timeout=min(0.1, max(0.01, deadline - time.monotonic())))
            except queue.Empty:
                continue
            if payload.get("id") == request_id:
                return payload
            deferred.append(payload)
    finally:
        for payload in deferred:
            output.put(payload)
    raise MCPClientError(f"stdio response id={request_id} timed out")


def _run_stdio(config: dict[str, Any], operation: str, tool_name: str, arguments: dict[str, Any], timeout_s: float) -> Any:
    process = subprocess.Popen(
        [str(config["command"]), *[str(item) for item in config.get("args", [])]],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    assert process.stdin is not None and process.stdout is not None
    output: queue.Queue[dict[str, Any]] = queue.Queue()
    errors: queue.Queue[BaseException] = queue.Queue()
    threading.Thread(target=_stdio_reader, args=(process.stdout, output, errors), daemon=True).start()
    try:
        initialize = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "aether-next", "version": "mcp-bridge-v1"},
            },
        }
        process.stdin.write(_json_line(initialize).decode("utf-8")); process.stdin.flush()
        _rpc_result(_stdio_wait(output, errors, 1, timeout_s))
        process.stdin.write(_json_line({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}).decode("utf-8")); process.stdin.flush()
        request = _operation_request(operation, tool_name, arguments, request_id=2)
        process.stdin.write(_json_line(request).decode("utf-8")); process.stdin.flush()
        return _rpc_result(_stdio_wait(output, errors, 2, timeout_s))
    finally:
        try:
            process.terminate()
            process.wait(timeout=2)
        except Exception:
            process.kill()


def _operation_request(operation: str, tool_name: str, arguments: dict[str, Any], *, request_id: int) -> dict[str, Any]:
    if operation == "tools_list":
        return {"jsonrpc": "2.0", "id": request_id, "method": "tools/list", "params": {}}
    if operation == "tools_call":
        if not tool_name:
            raise MCPClientError("tools_call requires tool_name")
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }
    raise MCPClientError(f"unsupported operation: {operation}")


def run(config: dict[str, Any], operation: str, tool_name: str, arguments: dict[str, Any], timeout_s: float) -> dict[str, Any]:
    transport = str(config.get("transport") or "")
    if transport == "sse":
        result = _run_legacy_sse(config, operation, tool_name, arguments, timeout_s)
    elif transport == "streamable-http":
        result = _run_streamable(config, operation, tool_name, arguments, timeout_s)
    elif transport == "stdio":
        result = _run_stdio(config, operation, tool_name, arguments, timeout_s)
    else:
        raise MCPClientError(f"unsupported transport: {transport}")
    return {
        "ok": True,
        "server": str(config.get("name") or ""),
        "transport": transport,
        "operation": operation,
        "tool_name": tool_name,
        "result": result,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config-json", required=True)
    parser.add_argument("--operation", choices=("tools_list", "tools_call"), required=True)
    parser.add_argument("--tool-name", default="")
    parser.add_argument("--arguments-json", default="{}")
    parser.add_argument("--timeout-s", type=float, default=30.0)
    args = parser.parse_args(argv)
    try:
        config = json.loads(args.config_json)
        arguments = json.loads(args.arguments_json)
        if not isinstance(config, dict) or not isinstance(arguments, dict):
            raise MCPClientError("config and arguments must be JSON objects")
        payload = run(config, args.operation, args.tool_name, arguments, max(1.0, args.timeout_s))
        print(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({
            "ok": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
