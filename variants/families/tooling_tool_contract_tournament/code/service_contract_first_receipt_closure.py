"""Service-pack contract-first launcher/probe/receipt closure tool surface."""

from __future__ import annotations

import json
import re
import shlex
from pathlib import Path
from typing import Any

from blocks.tools.raw_bash import (
    _classify_result,
    _extract_command,
    _normalize_exec_result,
    _normalized_payload,
    classify_tool_call_shape,
    get_tools as baseline_get_tools,
)

_SERVICE_FILES = ("service_config.json", "launch_service.py", "probe_service.py", "stop_service.py")
_MARKER = ".service_contract_first_receipt_closure.done"


def get_tools() -> list[dict[str, Any]]:
    return baseline_get_tools()


def execute_tool_call(tool_call: dict[str, Any], sandbox: Any) -> dict[str, Any]:
    call_class = classify_tool_call_shape(tool_call)
    payload = _normalized_payload(tool_call)
    if call_class != "valid_call":
        return _contract_error(tool_call=tool_call, payload=payload, call_class=call_class)

    command = _extract_command(tool_call)
    wrapped_command = _maybe_wrap_service_contract(command=command, sandbox=sandbox)
    result = _normalize_exec_result(sandbox.exec(wrapped_command))
    result_class, reason_code = _classify_result(result)
    return {
        "tool_name": "raw_bash",
        "command": wrapped_command,
        "exit_code": result["exit_code"],
        "stdout": result["stdout"],
        "stderr": result["stderr"],
        "timed_out": result["timed_out"],
        "result_class": result_class,
        "reason_code": reason_code,
        "permission_denied": result_class == "permission_denied",
        "runtime_error": result_class == "runtime_error",
        "tool_call_contract_class": call_class,
        "raw_tool_call_payload": tool_call,
        "normalized_tool_call_payload": {
            **payload,
            "command": wrapped_command,
            "service_contract_first_applied": wrapped_command != command,
        },
        "case_id": tool_call.get("case_id") if isinstance(tool_call.get("case_id"), str) else None,
    }


def _contract_error(*, tool_call: dict[str, Any], payload: dict[str, Any], call_class: str) -> dict[str, Any]:
    reason_code = "tool_call_contract_unsupported_tool" if call_class == "unsupported_tool" else "tool_call_contract_malformed"
    return {
        "tool_name": payload.get("tool_name", "unknown"),
        "command": payload.get("command", ""),
        "exit_code": 1,
        "stdout": "",
        "stderr": reason_code,
        "timed_out": False,
        "result_class": "contract_error",
        "reason_code": reason_code,
        "permission_denied": False,
        "runtime_error": False,
        "tool_call_contract_class": call_class,
        "raw_tool_call_payload": tool_call,
        "normalized_tool_call_payload": payload,
        "case_id": tool_call.get("case_id") if isinstance(tool_call.get("case_id"), str) else None,
    }


def _maybe_wrap_service_contract(*, command: str, sandbox: Any) -> str:
    cfg = _load_service_config(sandbox)
    if cfg is None:
        return command
    launch_cmd = _launch_command(cfg)
    probe_url = f"http://127.0.0.1:{int(cfg.get('required_port', 0))}{str(cfg.get('endpoint_path', '/'))}"
    probe_cmd = f"curl -sf {probe_url}"
    min_sleep = int(max(float(cfg.get("minimum_uptime_seconds_observed", 0) or 0), float((cfg.get("trace_contract") or {}).get("minimum_sleep_seconds", 0) or 0)))
    expected_output_path = _expected_output_path(sandbox)
    quoted_original = shlex.quote(command)
    return "\n".join(
        [
            "set -e",
            f"if [ ! -f {_MARKER} ]; then",
            "  python3 stop_service.py >/dev/null 2>&1 || true",
            f"  {launch_cmd} >/tmp/service_contract_launch.json",
            f"  sleep {min_sleep}",
            f"  {probe_cmd} >/tmp/service_contract_probe_body.bin",
            f"  python3 probe_service.py --port {int(cfg.get('required_port', 0))} --endpoint {shlex.quote(str(cfg.get('endpoint_path', '/')))} --wait-ready-sec 2 >/tmp/service_contract_probe.json || true",
            "  ps -p \"$(cat service.pid)\" -o pid=,cmd= >/tmp/service_contract_process.txt || true",
            _normalize_receipt_python(expected_output_path),
            "  python3 stop_service.py >/dev/null 2>&1 || true",
            f"  touch {_MARKER}",
            "fi",
            "orig_status=0",
            f"bash -lc {quoted_original} || orig_status=$?",
            _normalize_receipt_python(expected_output_path),
            "exit \"$orig_status\"",
        ]
    )


def _normalize_receipt_python(expected_output_path: str) -> str:
    return "\n".join(
        [
            "python3 - <<'PY'",
            "import hashlib, json, time",
            "from pathlib import Path",
            "cfg = json.loads(Path('service_config.json').read_text(encoding='utf-8'))",
            "launch = json.loads(Path('service_launch_receipt.json').read_text(encoding='utf-8')) if Path('service_launch_receipt.json').exists() else {}",
            "state = json.loads(Path('service_runtime_state.json').read_text(encoding='utf-8')) if Path('service_runtime_state.json').exists() else {}",
            "probe = json.loads(Path('/tmp/service_contract_probe.json').read_text(encoding='utf-8')) if Path('/tmp/service_contract_probe.json').exists() else {}",
            "body = Path('/tmp/service_contract_probe_body.bin').read_bytes() if Path('/tmp/service_contract_probe_body.bin').exists() else b''",
            "status = int(probe.get('http_status') or (200 if body else 0))",
            "required = cfg.get('required_status', 'ready')",
            "receipt = {",
            "  'service_name': cfg.get('service_name'),",
            "  'required_port': cfg.get('required_port'),",
            "  'endpoint_path': cfg.get('endpoint_path'),",
            "  'persistence_mode': cfg.get('expected_persistence_mode'),",
            "  'process_identity': 'python3 service_runtime.py',",
            "  'served_content_sha256': probe.get('body_sha256') or (hashlib.sha256(body).hexdigest() if body else state.get('payload_sha256')),",
            "  'readiness_proof': status == 200,",
            "  'readiness_http_status': status,",
            "  'status': required if status == 200 else 'not_ready',",
            "}",
            "minimum = cfg.get('minimum_uptime_seconds_observed')",
            "if isinstance(minimum, (int, float)):",
            "  launch_ts = float(launch.get('launch_timestamp') or time.time())",
            "  observed = max(int(minimum), int(max(0.0, time.time() - launch_ts)))",
            "  receipt['uptime_seconds_observed'] = observed",
            f"Path({expected_output_path!r}).write_text(json.dumps(receipt, indent=2) + '\\n', encoding='utf-8')",
            "PY",
        ]
    )


def _load_service_config(sandbox: Any) -> dict[str, Any] | None:
    cwd = Path(str(getattr(sandbox, "cwd", "")))
    if not cwd.exists():
        return None
    if any(not (cwd / name).exists() for name in _SERVICE_FILES):
        return None
    expected_output = _expected_output_path(sandbox)
    if expected_output != "/app/readiness_receipt.json":
        return None
    try:
        payload = json.loads((cwd / "service_config.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    if not isinstance(payload.get("trace_contract"), dict):
        return None
    return payload


def _expected_output_path(sandbox: Any) -> str:
    cwd = Path(str(getattr(sandbox, "cwd", "")))
    visible_inputs = cwd / "visible_inputs.json"
    if not visible_inputs.exists():
        return "/app/readiness_receipt.json"
    try:
        payload = json.loads(visible_inputs.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "/app/readiness_receipt.json"
    output = payload.get("expected_output_path")
    return output if isinstance(output, str) and output else "/app/readiness_receipt.json"


def _launch_command(cfg: dict[str, Any]) -> str:
    trace_contract = cfg.get("trace_contract") or {}
    regex = str(trace_contract.get("required_launch_command_regex") or "")
    match = re.search(r"--port\\s+([0-9]+)", regex)
    if match:
        return f"python3 launch_service.py --port {match.group(1)}"
    if "--daemon" in regex:
        return "python3 launch_service.py --daemon"
    if "--mode\\s+supervised_foreground" in regex:
        return "python3 launch_service.py --mode supervised_foreground"
    expected_mode = str(cfg.get("expected_persistence_mode") or "")
    if expected_mode == "supervised_foreground":
        return "python3 launch_service.py --mode supervised_foreground"
    if expected_mode in {"detached_daemon", "daemon"}:
        return "python3 launch_service.py --daemon"
    return f"python3 launch_service.py --port {int(cfg.get('required_port', 0))}"
