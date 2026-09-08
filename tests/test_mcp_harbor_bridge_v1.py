from __future__ import annotations

import asyncio
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
from types import SimpleNamespace
from typing import Any, Mapping

from aether.execution import MemoryExecutor
from aether.harbor_executor import HarborEnvironmentExecutor
from aether.kernel_dispatch import dispatch_action
from aether.ledger import ExecutionLedger
from aether.pcr_provider_protocol import PCR_ACTION_ARGUMENT_VARIANTS
from aether.runtime_ir import ActionRequest, EnvMap, FIXED_KERNEL_TOOL_SURFACE


@dataclass
class _Completed:
    return_code: int
    stdout: str = ""
    stderr: str = ""


class _LocalAsyncEnvironment:
    async def exec(
        self,
        *,
        command: str,
        cwd: str | None,
        env: dict[str, str] | None,
        timeout_sec: int,
    ) -> _Completed:
        def _run() -> _Completed:
            completed = subprocess.run(
                ["/bin/sh", "-lc", command],
                cwd=cwd,
                env=None if env is None else {**dict(__import__("os").environ), **env},
                text=True,
                capture_output=True,
                timeout=timeout_sec,
            )
            return _Completed(completed.returncode, completed.stdout, completed.stderr)
        return await asyncio.to_thread(_run)

    async def upload_file(self, source: Path, destination: str) -> None:
        def _copy() -> None:
            target = Path(destination)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        await asyncio.to_thread(_copy)

    async def download_file(self, source: str, destination: Path) -> None:
        await asyncio.to_thread(shutil.copyfile, source, destination)


class _MCPHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, _format: str, *args: Any) -> None:
        del args

    def do_POST(self) -> None:  # noqa: N802
        size = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(size).decode("utf-8"))
        method = payload.get("method")
        if method == "notifications/initialized":
            self.send_response(202)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if method == "initialize":
            result = {
                "protocolVersion": "2025-06-18",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "bridge-test", "version": "1"},
            }
        elif method == "tools/list":
            result = {"tools": [{
                "name": "set_value",
                "description": "test tool",
                "inputSchema": {"type": "object"},
            }]}
        elif method == "tools/call":
            result = {
                "content": [{
                    "type": "text",
                    "text": "called:" + json.dumps(payload["params"]["arguments"], sort_keys=True),
                }],
                "isError": False,
            }
        else:
            self.send_error(400)
            return
        body = json.dumps({
            "jsonrpc": "2.0", "id": payload["id"], "result": result,
        }, separators=(",", ":")).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Mcp-Session-Id", "bridge-session")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class _Server:
    def __init__(self) -> None:
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), _MCPHandler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    @property
    def url(self) -> str:
        host, port = self.httpd.server_address
        return f"http://{host}:{port}/mcp"

    def close(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=2)


def _run_harbor(callback):
    async def _main():
        with tempfile.TemporaryDirectory(prefix="aether-mcp-harbor-") as tmp:
            root = Path(tmp) / "workspace"
            state = Path(tmp) / "state"
            root.mkdir()
            loop = asyncio.get_running_loop()
            return await asyncio.to_thread(callback, loop, root, state)
    return asyncio.run(_main())


def test_harbor_executor_uploads_and_invokes_task_world_mcp_bridge() -> None:
    server = _Server()
    try:
        def scenario(loop, root: Path, state: Path) -> None:
            executor = HarborEnvironmentExecutor(
                _LocalAsyncEnvironment(),
                event_loop=loop,
                workspace_root=str(root),
                local_state_dir=state,
                mcp_servers=({
                    "name": "declared",
                    "transport": "streamable-http",
                    "url": server.url,
                },),
            )
            listed = executor.call_environment_extension(
                server_name="declared",
                operation="tools_list",
                timeout_s=5,
            )
            assert listed["success"] is True
            assert listed["result"]["tools"][0]["name"] == "set_value"
            called = executor.call_environment_extension(
                server_name="declared",
                operation="tools_call",
                tool_name="set_value",
                arguments={"value": 42},
                timeout_s=5,
            )
            assert called["success"] is True
            assert called["result"]["isError"] is False
            assert "42" in called["result"]["content"][0]["text"]
            assert not (root / ".aether" / "tools" / "mcp_environment_client_v1.py").exists()
            helper = Path(executor._mcp_client_remote_path)
            assert helper.is_file()
            assert called["bridge_provenance"] == "harbor_task_environment:mcp_environment_client_v1"
            executor.close()
            assert not helper.exists()
        _run_harbor(scenario)
    finally:
        server.close()


def test_harbor_executor_rejects_undeclared_mcp_server_without_network_call() -> None:
    def scenario(loop, root: Path, state: Path) -> None:
        executor = HarborEnvironmentExecutor(
            _LocalAsyncEnvironment(), event_loop=loop,
            workspace_root=str(root), local_state_dir=state,
        )
        result = executor.call_environment_extension(
            server_name="not-declared", operation="tools_list", timeout_s=2,
        )
        assert result["success"] is False
        assert result["failure_class"] == "environment_extension_unknown"
        assert not (root / ".aether" / "tools" / "mcp_environment_client_v1.py").exists()
        assert not Path(executor._mcp_client_remote_path).exists()
    _run_harbor(scenario)


class _ExtensionMemoryExecutor(MemoryExecutor):
    def __init__(self) -> None:
        super().__init__(workspace_root="/app")
        self.calls: list[dict[str, Any]] = []

    def call_environment_extension(
        self,
        *,
        server_name: str,
        operation: str,
        tool_name: str = "",
        arguments: Mapping[str, Any] | None = None,
        timeout_s: int = 30,
    ) -> dict[str, Any]:
        row = {
            "server_name": server_name,
            "operation": operation,
            "tool_name": tool_name,
            "arguments": dict(arguments or {}),
            "timeout_s": timeout_s,
        }
        self.calls.append(row)
        return {
            "success": True,
            "server": server_name,
            "transport": "streamable-http",
            "operation": operation,
            "tool_name": tool_name,
            "result": {"content": [{"type": "text", "text": "ok"}], "isError": False},
            "exit_code": 0,
            "bridge_provenance": "memory:test",
        }


class _FailureParser:
    @staticmethod
    def classify(_text: str, *, exit_code: int) -> str:
        return "command_failure" if exit_code else ""


class _Integrity:
    @staticmethod
    def validate_modified_paths(_objective, _paths) -> str:
        return ""


def _action(arguments: Mapping[str, Any]) -> ActionRequest:
    return ActionRequest(
        action_id="ext",
        kind="run_command",
        capability_id="shell",
        arguments=dict(arguments),
        intent="invoke declared environment extension",
        expected_observation="structured MCP result",
        if_fail_next="inspect failure",
    )


def test_kernel_routes_exact_run_command_extension_mode_into_ordinary_receipt() -> None:
    executor = _ExtensionMemoryExecutor()
    kernel = SimpleNamespace(failure_parser=_FailureParser(), integrity_guards=_Integrity())
    compiled = SimpleNamespace(objective_graph=SimpleNamespace())
    envmap = EnvMap(task_prompt="extension", workspace_root="/app")
    rows = dispatch_action(
        kernel,
        _action({
            "command": "environment_extension",
            "extension_server": "declared",
            "extension_operation": "tools_call",
            "extension_tool": "set_value",
            "extension_arguments_json": '{"value":42}',
            "timeout_s": 9,
        }),
        4,
        compiled,
        executor,
        envmap,
        ExecutionLedger(),
    )
    assert len(rows) == 1
    receipt = rows[0]
    assert receipt.kind == "environment_extension"
    assert receipt.success is True
    assert receipt.payload["server"] == "declared"
    assert receipt.payload["operation"] == "tools_call"
    assert receipt.payload["tool_name"] == "set_value"
    assert receipt.payload["result"]["isError"] is False
    assert executor.calls == [{
        "server_name": "declared",
        "operation": "tools_call",
        "tool_name": "set_value",
        "arguments": {"value": 42},
        "timeout_s": 9,
    }]


def test_extension_mode_does_not_add_kernel_tool_and_is_closed_in_pcr_schema() -> None:
    assert "environment_extension" not in FIXED_KERNEL_TOOL_SURFACE
    assert "mcp_call" not in FIXED_KERNEL_TOOL_SURFACE
    variants = PCR_ACTION_ARGUMENT_VARIANTS["run_command"]
    rows = [row["properties"] for row in variants]
    assert any(
        props.get("command", {}).get("enum") == ["environment_extension"]
        and props.get("extension_operation", {}).get("enum") == ["tools_list"]
        for props in rows
    )
    assert any(
        props.get("command", {}).get("enum") == ["environment_extension"]
        and props.get("extension_operation", {}).get("enum") == ["tools_call"]
        and "extension_tool" in props
        and "extension_arguments_json" in props
        for props in rows
    )


def test_mcp_execution_modules_contain_no_server_or_benchmark_strategy() -> None:
    root = Path(__file__).parents[1] / "aether"
    text = "\n".join(
        (root / name).read_text(encoding="utf-8").lower()
        for name in (
            "environment_extension_execution.py",
            "mcp_environment_client.py",
            "environment_extensions.py",
        )
    )
    for forbidden in (
        "playwright",
        "medical-claims-processing",
        "frontier-bench",
        "browser_navigate",
    ):
        assert forbidden not in text


def test_successful_tools_call_advances_freshness_without_inventing_concrete_delta() -> None:
    executor = _ExtensionMemoryExecutor()
    kernel = SimpleNamespace(failure_parser=_FailureParser(), integrity_guards=_Integrity())
    compiled = SimpleNamespace(objective_graph=SimpleNamespace())
    envmap = EnvMap(task_prompt="extension", workspace_root="/app")
    ledger = ExecutionLedger()
    receipt = dispatch_action(
        kernel,
        _action({
            "command": "environment_extension",
            "extension_server": "declared",
            "extension_operation": "tools_call",
            "extension_tool": "set_value",
            "extension_arguments_json": '{"value":42}',
        }),
        1, compiled, executor, envmap, ledger,
    )[0]
    assert receipt.state_change is True
    assert receipt.payload["mutation_semantics"] == "unknown_possible_external_state_change"
    assert "modified_paths" not in receipt.payload
    assert "created_paths" not in receipt.payload
    ledger.record(receipt)
    assert ledger.task_state_generation() == 1


def test_successful_tools_list_is_observational_and_does_not_advance_freshness() -> None:
    executor = _ExtensionMemoryExecutor()
    kernel = SimpleNamespace(failure_parser=_FailureParser(), integrity_guards=_Integrity())
    compiled = SimpleNamespace(objective_graph=SimpleNamespace())
    envmap = EnvMap(task_prompt="extension", workspace_root="/app")
    ledger = ExecutionLedger()
    receipt = dispatch_action(
        kernel,
        _action({
            "command": "environment_extension",
            "extension_server": "declared",
            "extension_operation": "tools_list",
        }),
        1, compiled, executor, envmap, ledger,
    )[0]
    assert receipt.state_change is False
    assert receipt.payload["mutation_semantics"] == "read_only_discovery"
    ledger.record(receipt)
    assert ledger.task_state_generation() == 0


def test_harbor_refresh_preserves_extension_facts() -> None:
    def scenario(loop, root: Path, state: Path) -> None:
        executor = HarborEnvironmentExecutor(
            _LocalAsyncEnvironment(), event_loop=loop,
            workspace_root=str(root), local_state_dir=state,
            mcp_servers=({
                "name": "declared",
                "transport": "streamable-http",
                "url": "http://mcp.internal:8080/mcp",
            },),
        )
        env = EnvMap(
            task_prompt="x", workspace_root=str(root),
            task_metadata={"environment_probe": {"schema_version": "environment_probe.v1"}},
        )
        refreshed = executor.refresh_envmap(env)
        ext = refreshed.task_metadata["environment_probe"]["environment_extensions"]
        assert ext["mcp_server_count"] == 1
        assert ext["mcp_servers"][0]["name"] == "declared"
        assert refreshed.task_metadata["environment_extensions"] == ext
    _run_harbor(scenario)


def test_mcp_result_is_immediately_visible_but_large_payload_is_retrievable_not_inlined() -> None:
    from aether.context_views import receipt_inline_view, recent_receipts
    from aether.ledger import Receipt

    small = Receipt(
        receipt_id="step-1:ext:extension", step=1, kind="environment_extension",
        success=True, summary="extension ok", state_change=False,
        payload={
            "server": "declared", "operation": "tools_list",
            "transport": "streamable-http",
            "result": {"tools": [{"name": "set_value"}]},
            "mutation_semantics": "read_only_discovery",
        },
    )
    row = receipt_inline_view(small)
    assert row["result"] == {"tools": [{"name": "set_value"}]}
    assert row["result_receipt_handle"] == "receipt:step-1:ext:extension"

    large = Receipt(
        receipt_id="step-2:ext:extension", step=2, kind="environment_extension",
        success=True, summary="extension large", state_change=True,
        payload={
            "server": "declared", "operation": "tools_call",
            "result": {"content": [{"type": "text", "text": "x" * 12000}]},
            "mutation_semantics": "unknown_possible_external_state_change",
        },
    )
    large_row = receipt_inline_view(large)
    assert "result" not in large_row
    assert len(large_row["result_excerpt"]) <= 6080
    assert large_row["full_result_available_by_receipt_handle"] is True
    assert large_row["result_receipt_handle"] == "receipt:step-2:ext:extension"

    ledger = ExecutionLedger()
    ledger.record(small)
    ledger.record(large)
    assert recent_receipts("tool_results", ledger, 2) == [small, large]
