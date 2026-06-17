"""Generic native-tool discovery and dispatch for the active kernel."""

from __future__ import annotations

import copy
import importlib
import json
import sys
from pathlib import Path
from typing import Any, Callable

from blocks.tools.raw_bash import execute_tool_call as execute_raw_bash_tool_call, get_tools as get_raw_bash_tools


_TOOL_MANIFEST_NAMES = (
    "native_tools.json",
    "tool_definitions.json",
    "tool_schema.json",
    "tools.json",
    "tool_manifest.json",
    "visible_inputs.json",
)


def normalize_tool_schema(schema: Any) -> dict[str, Any]:
    if not isinstance(schema, dict):
        return {"type": "object", "properties": {}, "additionalProperties": True}
    normalized = copy.deepcopy(schema)
    return _normalize_schema_node(normalized)


def validate_tool_arguments(schema: Any, arguments: Any) -> dict[str, Any]:
    if not isinstance(schema, dict):
        return {
            "status": "schema_unavailable",
            "schema_present": False,
            "missing_required": [],
            "type_violations": [],
            "enum_violations": [],
            "unexpected_keys": [],
        }

    normalized_schema = normalize_tool_schema(schema)
    normalized_arguments = _normalize_tool_arguments_value(arguments)
    report = {
        "status": "pass",
        "schema_present": True,
        "missing_required": [],
        "type_violations": [],
        "enum_violations": [],
        "unexpected_keys": [],
    }
    _validate_schema_node(normalized_schema, normalized_arguments, path="", report=report)
    if report["missing_required"] or report["type_violations"] or report["enum_violations"] or report["unexpected_keys"]:
        report["status"] = "fail"
    return report


def get_tools(
    *,
    cwd: str | None = None,
    workspace_state: dict[str, Any] | None = None,
    task_prompt: str = "",
    route_manifest: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    tool_definitions = _discover_tool_definitions(
        cwd=cwd,
        workspace_state=workspace_state,
        route_manifest=route_manifest,
        task_prompt=task_prompt,
    )
    
    model_led_active = False
    if isinstance(workspace_state, dict):
        model_led_active = bool(workspace_state.get("active_kernel_state", {}).get("model_led_evidence_substrate_active"))
    if not model_led_active and route_manifest is not None:
        from runner.active_evidence_kernel import _is_control_plane_route
        model_led_active = _is_control_plane_route(route_manifest)
        
    if model_led_active:
        tools = list(tool_definitions)
        if not tools:
            tools = list(get_raw_bash_tools())
        service_tools = [
            {
                "name": "register_service",
                "description": "Register a running service or daemon process for harness service tracking.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "service_name": {"type": "string", "description": "The name of the service (e.g., 'nginx', 'uvicorn', 'service@8000')."},
                        "port": {"type": "integer", "description": "The TCP port the service is listening on (optional)."},
                        "pid": {"type": "integer", "description": "The process ID of the service (optional)."},
                        "command": {"type": "string", "description": "The command string that was run to start the service (optional)."}
                    },
                    "required": ["service_name"],
                }
            },
            {
                "name": "probe_service",
                "description": "Report the health/readiness probe status of a registered service.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "service_name": {"type": "string", "description": "The name of the service (e.g., 'nginx', 'uvicorn', 'service@8000')."},
                        "status": {"type": "string", "description": "The probe status to report (e.g., 'ready', 'not_ready')."}
                    },
                    "required": ["service_name", "status"],
                }
            }
        ]
        for s_tool in service_tools:
            if not any(t.get("name") == s_tool["name"] for t in tools):
                tools.append(s_tool)
        return tools
    else:
        if not tool_definitions:
            return get_raw_bash_tools()
        native_tools = [entry for entry in _dedupe_tools(tool_definitions) if entry.get("name") != "raw_bash"]
        return native_tools or get_raw_bash_tools()


def execute_tool_call(tool_call: dict[str, Any], sandbox: Any) -> dict[str, Any]:
    tool_name = _tool_name(tool_call)
    if tool_name == "raw_bash":
        return execute_raw_bash_tool_call(tool_call, sandbox)
    if tool_name == "register_service":
        args = _tool_arguments(tool_call) or {}
        service_name = str(args.get("service_name") or "service@unknown")
        port = args.get("port")
        if port is None and "@" in service_name:
            try:
                port = int(service_name.split("@")[-1])
            except ValueError:
                pass
        return {
            "tool_name": "register_service",
            "command": f"register_service {service_name}",
            "exit_code": 0,
            "stdout": f"Service '{service_name}' successfully registered.",
            "stderr": "",
            "timed_out": False,
            "result_class": "success",
            "reason_code": "tool_success",
            "service_name": service_name,
            "service_status": "running",
            "service_port": port,
            "pid": args.get("pid"),
        }
    if tool_name == "probe_service":
        args = _tool_arguments(tool_call) or {}
        service_name = str(args.get("service_name") or "service@unknown")
        status = str(args.get("status") or "ready")
        port = args.get("port")
        if port is None and "@" in service_name:
            try:
                port = int(service_name.split("@")[-1])
            except ValueError:
                pass
        return {
            "tool_name": "probe_service",
            "command": f"probe_service {service_name}",
            "exit_code": 0,
            "stdout": f"Service '{service_name}' probe status reported as '{status}'.",
            "stderr": "",
            "timed_out": False,
            "result_class": "success",
            "reason_code": "tool_success",
            "service_name": service_name,
            "service_status": "ready" if status == "ready" else "not_ready",
            "service_port": port,
        }
    if not tool_name:
        return _contract_error(tool_call=tool_call, reason_code="tool_call_contract_malformed")
    schema = _resolve_native_tool_schema(tool_name=tool_name, sandbox=sandbox)
    validation = validate_tool_arguments(schema, _tool_arguments(tool_call))
    if validation["status"] == "fail":
        return {
            "tool_name": tool_name,
            "command": _tool_command(tool_call),
            "exit_code": 1,
            "stdout": "",
            "stderr": "native_tool_schema_violation",
            "timed_out": False,
            "result_class": "contract_error",
            "reason_code": "native_tool_schema_violation",
            "native_tool_runtime_active": False,
            "native_tool_name": tool_name,
            "tool_contract_status": validation,
        }
    runtime_callable = _resolve_native_runtime_callable(tool_name=tool_name, sandbox=sandbox)
    if runtime_callable is None:
        return {
            "tool_name": tool_name,
            "command": _tool_command(tool_call),
            "exit_code": 1,
            "stdout": "",
            "stderr": f"native_tool_runtime_unavailable:{tool_name}",
            "timed_out": False,
            "result_class": "runtime_error",
            "reason_code": "native_tool_runtime_unavailable",
            "native_tool_runtime_active": False,
            "native_tool_name": tool_name,
            "tool_contract_status": validation,
        }
    result = runtime_callable(tool_call)
    if not isinstance(result, dict):
        return {
            "tool_name": tool_name,
            "command": _tool_command(tool_call),
            "exit_code": 1,
            "stdout": "",
            "stderr": "native_tool_runtime_invalid_result",
            "timed_out": False,
            "result_class": "runtime_error",
            "reason_code": "native_tool_runtime_invalid_result",
            "native_tool_runtime_active": True,
            "native_tool_name": tool_name,
            "tool_contract_status": validation,
        }
    normalized = dict(result)
    normalized.setdefault("tool_name", tool_name)
    normalized.setdefault("command", _tool_command(tool_call))
    normalized.setdefault("stdout", "")
    normalized.setdefault("stderr", "")
    normalized.setdefault("timed_out", False)
    normalized.setdefault("exit_code", 0 if normalized.get("result_class") == "success" else 1)
    normalized.setdefault("reason_code", "native_tool_runtime_success" if normalized["exit_code"] == 0 else "native_tool_runtime_error")
    normalized.setdefault("native_tool_runtime_active", True)
    normalized.setdefault("native_tool_name", tool_name)
    normalized.setdefault("tool_contract_status", validation)
    return normalized


def discover_native_tool_definitions(
    *,
    cwd: str | None = None,
    workspace_state: dict[str, Any] | None = None,
    route_manifest: dict[str, Any] | None = None,
    task_prompt: str = "",
) -> list[dict[str, Any]]:
    return _discover_tool_definitions(
        cwd=cwd,
        workspace_state=workspace_state,
        route_manifest=route_manifest,
        task_prompt=task_prompt,
    )


def project_native_tool_state(
    *,
    declared_tool_names: list[str],
    declared_tool_schemas: dict[str, dict[str, Any]],
    receipts: list[dict[str, Any]],
    runtime_status: str,
    attempted_native_tool_call: bool,
    contract_status: str,
) -> dict[str, Any]:
    violations: list[str] = []
    for receipt in receipts:
        if not isinstance(receipt, dict):
            continue
        tool_contract = receipt.get("tool_contract_status")
        if not isinstance(tool_contract, dict):
            continue
        if tool_contract.get("status") == "fail":
            receipt_id = receipt.get("receipt_id")
            if isinstance(receipt_id, str) and receipt_id:
                violations.append(receipt_id)
    return {
        "mode": "native" if any(name != "raw_bash" for name in declared_tool_names) else "shell_only",
        "runtime_status": runtime_status,
        "declared_tool_names": list(dict.fromkeys(declared_tool_names)),
        "declared_tool_schemas": dict(declared_tool_schemas),
        "attempted_native_tool_call": attempted_native_tool_call,
        "contract_status": contract_status,
        "violation_receipt_ids": [receipt_id for receipt_id in violations if receipt_id],
    }


def _discover_tool_definitions(
    *,
    cwd: str | None,
    workspace_state: dict[str, Any] | None,
    route_manifest: dict[str, Any] | None,
    task_prompt: str,
) -> list[dict[str, Any]]:
    discovered: list[dict[str, Any]] = []
    seen: set[str] = set()
    if isinstance(workspace_state, dict):
        for key in ("native_tool_definitions", "tool_definitions", "declared_tool_definitions"):
            value = workspace_state.get(key)
            discovered.extend(_normalize_tool_collection(value, seen))
    if cwd:
        root = Path(cwd)
        for name in _TOOL_MANIFEST_NAMES:
            candidate = root / name
            if not candidate.exists():
                continue
            discovered.extend(_normalize_tool_collection(_load_json(candidate), seen))
    if isinstance(route_manifest, dict):
        route_tools = route_manifest.get("native_tool_definitions")
        discovered.extend(_normalize_tool_collection(route_tools, seen))
    return _dedupe_tools(discovered)


def _normalize_tool_collection(value: Any, seen: set[str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if isinstance(value, dict):
        if _looks_like_tool_definition(value):
            name = str(value.get("name") or "")
            if name and name not in seen:
                out.append(_normalize_tool_definition(value))
                seen.add(name)
        for key in ("tool_definitions", "tools", "native_tools"):
            nested = value.get(key)
            out.extend(_normalize_tool_collection(nested, seen))
        return out
    if isinstance(value, list):
        for item in value:
            out.extend(_normalize_tool_collection(item, seen))
    return out


def _looks_like_tool_definition(value: dict[str, Any]) -> bool:
    name = value.get("name")
    return isinstance(name, str) and bool(name)


def _normalize_tool_definition(value: dict[str, Any]) -> dict[str, Any]:
    normalized = {
        "name": value["name"],
        "description": value.get("description", ""),
    }
    if isinstance(value.get("input_schema"), dict):
        normalized["input_schema"] = normalize_tool_schema(value["input_schema"])
    elif isinstance(value.get("parameters"), dict):
        normalized["input_schema"] = normalize_tool_schema(value["parameters"])
    else:
        normalized["input_schema"] = normalize_tool_schema({})
    if isinstance(value.get("runtime_spec"), dict):
        normalized["runtime_spec"] = dict(value["runtime_spec"])
    for key in ("runtime_callable", "native_callable", "handler", "implementation", "tool_kind"):
        if key in value:
            normalized[key] = value[key]
    return normalized


def _dedupe_tools(tool_definitions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in tool_definitions:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        if not isinstance(name, str) or not name or name in seen:
            continue
        seen.add(name)
        out.append(dict(entry))
    return out


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _resolve_native_tool_schema(*, tool_name: str, sandbox: Any) -> dict[str, Any] | None:
    definitions = getattr(sandbox, "native_tool_definitions", None)
    if not isinstance(definitions, list):
        return None
    for definition in definitions:
        if not isinstance(definition, dict) or definition.get("name") != tool_name:
            continue
        schema = definition.get("input_schema")
        if isinstance(schema, dict):
            return schema
        parameters = definition.get("parameters")
        if isinstance(parameters, dict):
            return parameters
    return None


def _tool_name(tool_call: dict[str, Any]) -> str:
    if not isinstance(tool_call, dict):
        return ""
    name = tool_call.get("name")
    if isinstance(name, str):
        return name
    function = tool_call.get("function")
    if isinstance(function, dict):
        maybe_name = function.get("name")
        if isinstance(maybe_name, str):
            return maybe_name
    return ""


def _tool_command(tool_call: dict[str, Any]) -> str:
    if not isinstance(tool_call, dict):
        return ""
    arguments = tool_call.get("arguments")
    if isinstance(arguments, dict):
        command = arguments.get("command")
        if isinstance(command, str):
            return command
    if isinstance(arguments, str):
        return arguments
    function = tool_call.get("function")
    if isinstance(function, dict):
        arguments = function.get("arguments")
        if isinstance(arguments, str):
            return arguments
    return ""


def _tool_arguments(tool_call: dict[str, Any]) -> Any:
    if not isinstance(tool_call, dict):
        return {}
    if "arguments" in tool_call:
        return _normalize_tool_arguments_value(tool_call.get("arguments"))
    function = tool_call.get("function")
    if isinstance(function, dict) and "arguments" in function:
        return _normalize_tool_arguments_value(function.get("arguments"))
    return {}


def _normalize_tool_arguments_value(arguments: Any) -> Any:
    if arguments is None:
        return {}
    if isinstance(arguments, dict):
        return dict(arguments)
    if isinstance(arguments, str):
        stripped = arguments.strip()
        if not stripped:
            return {}
        try:
            return json.loads(stripped)
        except Exception:
            return arguments
    return arguments


def _normalize_schema_node(schema: dict[str, Any]) -> dict[str, Any]:
    schema_type = schema.get("type")
    object_like = any(key in schema for key in ("properties", "required", "additionalProperties"))
    array_like = "items" in schema

    if schema_type is None:
        if object_like:
            schema["type"] = "object"
        elif array_like:
            schema["type"] = "array"
    elif isinstance(schema_type, (list, tuple, set)):
        normalized_types = [item for item in schema_type if isinstance(item, str) and item]
        if normalized_types:
            schema["type"] = normalized_types
        else:
            schema.pop("type", None)
    elif not isinstance(schema_type, str) or not schema_type:
        schema.pop("type", None)

    if "enum" in schema:
        enum_value = schema.get("enum")
        if isinstance(enum_value, (list, tuple, set)):
            schema["enum"] = list(enum_value)
        else:
            schema.pop("enum", None)

    properties = schema.get("properties")
    if isinstance(properties, dict):
        normalized_properties: dict[str, Any] = {}
        for key, value in properties.items():
            if isinstance(key, str) and key:
                if isinstance(value, dict):
                    normalized_properties[key] = _normalize_schema_node(copy.deepcopy(value))
                else:
                    normalized_properties[key] = value
        schema["properties"] = normalized_properties
    elif schema.get("type") == "object" or object_like:
        schema["properties"] = {}

    required = schema.get("required")
    if isinstance(required, list):
        schema["required"] = [item for item in required if isinstance(item, str) and item]
    elif "required" in schema and (schema.get("type") == "object" or object_like):
        schema.pop("required", None)

    items = schema.get("items")
    if isinstance(items, dict):
        schema["items"] = _normalize_schema_node(copy.deepcopy(items))
    elif isinstance(items, list):
        normalized_items: list[Any] = []
        for item in items:
            if isinstance(item, dict):
                normalized_items.append(_normalize_schema_node(copy.deepcopy(item)))
            else:
                normalized_items.append(item)
        schema["items"] = normalized_items

    additional = schema.get("additionalProperties")
    if isinstance(additional, dict):
        schema["additionalProperties"] = _normalize_schema_node(copy.deepcopy(additional))
    elif isinstance(additional, bool):
        pass
    elif schema.get("type") == "object" or object_like:
        schema["additionalProperties"] = True

    return schema


def _validate_schema_node(
    schema: dict[str, Any],
    value: Any,
    *,
    path: str,
    report: dict[str, Any],
) -> None:
    expected_types = _schema_types(schema.get("type"))
    if expected_types and not _value_matches_schema_types(value, expected_types):
        report["type_violations"].append(
            {
                "path": path or "$",
                "expected_type": expected_types[0] if len(expected_types) == 1 else list(expected_types),
                "observed_type": type(value).__name__,
            }
        )
        return

    enum_values = schema.get("enum")
    if isinstance(enum_values, list) and enum_values and value not in enum_values:
        report["enum_violations"].append(
            {
                "path": path or "$",
                "allowed_values": list(enum_values),
                "observed_value": value,
            }
        )

    schema_type = _matched_schema_type(schema.get("type"), value)
    if schema_type == "object" or (schema_type is None and isinstance(schema.get("properties"), dict)):
        if not isinstance(value, dict):
            return
        properties = schema.get("properties")
        if not isinstance(properties, dict):
            properties = {}
        required = schema.get("required")
        required_keys = [item for item in required if isinstance(item, str)] if isinstance(required, list) else []
        for key in required_keys:
            if key not in value:
                report["missing_required"].append(_join_schema_path(path, key))
        for key, observed in value.items():
            prop_schema = properties.get(key)
            if isinstance(prop_schema, dict):
                _validate_schema_node(prop_schema, observed, path=_join_schema_path(path, key), report=report)
                continue
            additional = schema.get("additionalProperties", True)
            if isinstance(additional, dict):
                _validate_schema_node(additional, observed, path=_join_schema_path(path, key), report=report)
            elif additional is False:
                report["unexpected_keys"].append(_join_schema_path(path, key))
        return

    if schema_type == "array":
        if not isinstance(value, list):
            return
        items = schema.get("items")
        if isinstance(items, dict):
            for index, item in enumerate(value):
                _validate_schema_node(items, item, path=_join_schema_path(path, f"[{index}]"), report=report)
        elif isinstance(items, list):
            for index, item_schema in enumerate(items):
                if index >= len(value):
                    break
                if isinstance(item_schema, dict):
                    _validate_schema_node(item_schema, value[index], path=_join_schema_path(path, f"[{index}]"), report=report)


def _schema_types(value: Any) -> tuple[str, ...]:
    if isinstance(value, str) and value:
        return (value,)
    if isinstance(value, (list, tuple, set)):
        return tuple(item for item in value if isinstance(item, str) and item)
    return ()


def _matched_schema_type(value: Any, expected_types: Any) -> str | None:
    types = _schema_types(expected_types)
    for schema_type in types:
        if _value_matches_schema_type(value, schema_type):
            return schema_type
    if isinstance(expected_types, str) and expected_types in {"object", "array"}:
        return expected_types
    return None


def _value_matches_schema_types(value: Any, expected_types: tuple[str, ...]) -> bool:
    return any(_value_matches_schema_type(value, expected_type) for expected_type in expected_types)


def _value_matches_schema_type(value: Any, expected_type: str) -> bool:
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "number":
        return (isinstance(value, int) or isinstance(value, float)) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "null":
        return value is None
    return False


def _join_schema_path(base: str, key: str) -> str:
    if not base:
        return key
    if key.startswith("["):
        return f"{base}{key}"
    return f"{base}.{key}"


def _contract_error(*, tool_call: dict[str, Any], reason_code: str) -> dict[str, Any]:
    return {
        "tool_name": _tool_name(tool_call) or "unknown",
        "command": _tool_command(tool_call),
        "exit_code": 1,
        "stdout": "",
        "stderr": reason_code,
        "timed_out": False,
        "result_class": "contract_error",
        "reason_code": reason_code,
        "native_tool_runtime_active": False,
        "tool_contract_status": {
            "status": "fail",
            "schema_present": False,
            "missing_required": [],
            "type_violations": [],
            "enum_violations": [],
            "unexpected_keys": [],
        },
    }


def _resolve_native_runtime_callable(*, tool_name: str, sandbox: Any) -> Callable[[dict[str, Any]], dict[str, Any]] | None:
    registry = getattr(sandbox, "native_tool_registry", None)
    if isinstance(registry, dict):
        candidate = registry.get(tool_name)
        if callable(candidate):
            return candidate
    definitions = getattr(sandbox, "native_tool_definitions", None)
    if isinstance(definitions, list):
        for definition in definitions:
            if not isinstance(definition, dict) or definition.get("name") != tool_name:
                continue
            runtime_spec = definition.get("runtime_spec")
            if isinstance(runtime_spec, dict):
                candidate = _resolve_runtime_spec_callable(runtime_spec=runtime_spec, sandbox=sandbox)
                if callable(candidate):
                    return candidate
            for key in ("runtime_callable", "native_callable", "handler", "implementation"):
                candidate = definition.get(key)
                if callable(candidate):
                    return candidate
    maybe_method = getattr(sandbox, "execute_native_tool", None)
    if callable(maybe_method):
        return lambda tool_call: maybe_method(tool_call)
    return None


def _resolve_runtime_spec_callable(*, runtime_spec: dict[str, Any], sandbox: Any) -> Callable[[dict[str, Any]], dict[str, Any]] | None:
    runtime_kind = runtime_spec.get("runtime_kind")
    if runtime_kind != "bfcl_api_method":
        return None
    module_name = runtime_spec.get("module_name")
    class_name = runtime_spec.get("class_name")
    method_name = runtime_spec.get("method_name")
    if not all(isinstance(value, str) and value for value in (module_name, class_name, method_name)):
        return None

    import_root = runtime_spec.get("import_root")
    if isinstance(import_root, str) and import_root and import_root not in sys.path:
        sys.path.insert(0, import_root)

    try:
        module = importlib.import_module(module_name)
        cls = getattr(module, class_name)
    except Exception:
        return None

    runtime_cache = getattr(sandbox, "native_tool_runtime_cache", None)
    if not isinstance(runtime_cache, dict):
        runtime_cache = {}
        setattr(sandbox, "native_tool_runtime_cache", runtime_cache)

    cache_key = f"{module_name}:{class_name}"
    instance = runtime_cache.get(cache_key)
    if instance is None:
        try:
            instance = cls()
            initial_config = runtime_spec.get("initial_config")
            long_context = bool(runtime_spec.get("long_context", False))
            if hasattr(instance, "_load_scenario") and callable(getattr(instance, "_load_scenario")):
                instance._load_scenario(initial_config if isinstance(initial_config, dict) else {}, long_context=long_context)
        except Exception:
            return None
        runtime_cache[cache_key] = instance

    method = getattr(instance, method_name, None)
    if callable(method):
        return lambda tool_call, _method=method: _invoke_runtime_method(_method, tool_call)
    return None


def _invoke_runtime_method(method: Callable[..., Any], tool_call: dict[str, Any]) -> dict[str, Any]:
    arguments = tool_call.get("arguments") if isinstance(tool_call, dict) else None
    if isinstance(arguments, dict):
        return method(**arguments)
    if isinstance(arguments, str):
        stripped = arguments.strip()
        if not stripped:
            return method()
        try:
            parsed = json.loads(stripped)
        except Exception:
            parsed = None
        if isinstance(parsed, dict):
            return method(**parsed)
        if isinstance(parsed, list):
            return method(*parsed)
        if parsed is not None:
            return method(parsed)
        return method(arguments)
    return method()
