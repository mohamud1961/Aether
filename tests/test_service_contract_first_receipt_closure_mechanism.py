from __future__ import annotations

import json

from blocks.tools.service_contract_first_receipt_closure import execute_tool_call
from runner.packet04_route_manifest import (
    PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE,
    build_packet04_route_manifest,
    load_runtime_callables,
)


class _Sandbox:
    def __init__(self, cwd: str) -> None:
        self.cwd = cwd
        self.sandbox_type = "docker"
        self.commands: list[str] = []

    def exec(self, command: str) -> dict[str, object]:
        self.commands.append(command)
        return {"exit_code": 0, "stdout": "ok", "stderr": "", "timed_out": False}


def test_route_manifest_wires_service_contract_first_receipt_closure_variant() -> None:
    manifest = build_packet04_route_manifest(
        "service_contract_first_receipt_closure_01",
        scope=PACKET06_PHASE6_CONTEXT_COMPLETION_SCOPE,
    )
    load_runtime_callables(manifest)
    routed = {row["runtime_key"]: row for row in manifest["routed_modules"]}
    assert (
        routed["orientation"]["module_import_path"]
        == "blocks.orientation.phase6_doctrine:orient_service_contract_first_receipt_closure"
    )
    assert (
        routed["tool_executor"]["module_import_path"]
        == "blocks.tools.service_contract_first_receipt_closure:execute_tool_call"
    )


def test_service_contract_wrapper_is_noop_without_service_pack(tmp_path) -> None:
    sandbox = _Sandbox(str(tmp_path))
    result = execute_tool_call({"name": "raw_bash", "arguments": {"command": "echo hello"}}, sandbox)
    assert len(sandbox.commands) == 1
    assert sandbox.commands[0] == "echo hello"
    assert result["normalized_tool_call_payload"]["service_contract_first_applied"] is False


def test_service_contract_wrapper_injects_contract_launch_probe_and_teardown(tmp_path) -> None:
    for filename in ("launch_service.py", "probe_service.py", "stop_service.py"):
        (tmp_path / filename).write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    (tmp_path / "visible_inputs.json").write_text(
        json.dumps({"expected_output_path": "/app/readiness_receipt.json"}),
        encoding="utf-8",
    )
    (tmp_path / "service_config.json").write_text(
        json.dumps(
            {
                "required_port": 8411,
                "endpoint_path": "/healthz/ready",
                "expected_persistence_mode": "supervised_foreground",
                "trace_contract": {
                    "required_launch_command_regex": "python3\\s+launch_service\\.py\\s+--mode\\s+supervised_foreground",
                    "minimum_sleep_seconds": 0,
                },
            }
        ),
        encoding="utf-8",
    )
    sandbox = _Sandbox(str(tmp_path))
    result = execute_tool_call({"name": "raw_bash", "arguments": {"command": "echo done"}}, sandbox)
    wrapped = sandbox.commands[0]
    assert "python3 launch_service.py --mode supervised_foreground" in wrapped
    assert "curl -sf http://127.0.0.1:8411/healthz/ready" in wrapped
    assert "python3 stop_service.py" in wrapped
    assert result["normalized_tool_call_payload"]["service_contract_first_applied"] is True
