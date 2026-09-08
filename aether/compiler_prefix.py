"""Static protocol-card sections of the solver's stable prompt prefix.

Extracted from compiler.py for the 500-LOC cap.  These are byte-stable across
every task and step; dynamic (task/world) sections stay in the compiler.
"""
from __future__ import annotations

from typing import Any, Mapping


PCR_PROTOCOL_CARD_SECTIONS: tuple[tuple[str, str], ...] = (
    (
        "tool_semantics",
        (
            "Only action kinds exposed by the provided native function schemas are callable. Use exactly the argument "
            "fields declared for the chosen action. One act turn contains one action frontier. "
            "Use bootstrap_acquire for dependency installation. Use launch_process for a managed "
            "task-local process and start_job for a detached/persistent job or service; observe a "
            "started job with probe_job instead of emulating lifecycle with nohup or shell '&'."
        ),
    ),
    (
        "completion_controls",
        (
            "Use finish_intent when you believe the current candidate is complete and want the one "
            "advisory independent review for this candidate generation. Review supplies evidence but "
            "does not own the final semantic decision. Use finish when you decide the task is complete; "
            "finish actually finishes and never implicitly starts review. Both completion calls cite "
            "current evidence references. Do not use them to report known incompleteness."
        ),
    ),
)


def protocol_card_sections() -> tuple[tuple[str, str], ...]:
    """Return Aether's sole PCR protocol-card sections."""
    return PCR_PROTOCOL_CARD_SECTIONS

def pcr_model_environment_probe(probe: Mapping[str, Any]) -> dict[str, Any]:
    """Return a factual PCR model view of the bounded environment probe.

    The complete probe remains in EnvMap/task metadata and config_realization
    custody. This view removes repeated false/empty rows and derived guidance
    while preserving decision-relevant positive and negative availability.
    Unknown probe schema versions fail open to the exact original mapping.
    """
    source = dict(probe)
    if source.get("schema_version") != "environment_probe.v1":
        return source

    view: dict[str, Any] = {}
    for key in ("schema_version", "workspace_root", "network", "task_hints"):
        if key in source:
            view[key] = source[key]

    command_names = source.get("command_names", {})
    if isinstance(command_names, Mapping):
        available: dict[str, Any] = {}
        unavailable_names: list[str] = []
        unavailable_details: dict[str, Any] = {}
        for raw_name, raw_row in sorted(command_names.items(), key=lambda item: str(item[0])):
            name = str(raw_name)
            if isinstance(raw_row, Mapping) and raw_row.get("available") is True:
                available[name] = {
                    str(key): value
                    for key, value in raw_row.items()
                    if key != "available" and value not in (None, "", [], {}, ())
                }
            else:
                unavailable_names.append(name)
                if isinstance(raw_row, Mapping):
                    extra = {
                        str(key): value
                        for key, value in raw_row.items()
                        if key not in {"available", "path"} and value not in (None, "", [], {}, ())
                    }
                    if extra:
                        unavailable_details[name] = extra
        view["commands"] = {
            "available": available,
            "unavailable_names": unavailable_names,
        }
        if unavailable_details:
            view["commands"]["unavailable_details"] = unavailable_details
    elif "command_names" in source:
        view["command_names"] = source["command_names"]

    python = source.get("python")
    if isinstance(python, Mapping):
        py_view: dict[str, Any] = {}
        for key in ("preferred", "interpreters", "interpreter_details", "package_contract"):
            if key in python:
                py_view[key] = python[key]

        interpreters = python.get("interpreters", ())
        if isinstance(interpreters, (list, tuple)):
            for raw_name in interpreters:
                name = str(raw_name)
                row = python.get(name)
                if isinstance(row, Mapping):
                    py_view[name] = {
                        str(key): value
                        for key, value in row.items()
                        if key != "modules" and value not in (None, "", [], {}, ())
                    }

        modules = python.get("modules")
        if isinstance(modules, Mapping):
            available_modules: dict[str, Any] = {}
            unavailable_module_names: list[str] = []
            unavailable_module_details: dict[str, Any] = {}
            for raw_name, raw_row in sorted(modules.items(), key=lambda item: str(item[0])):
                name = str(raw_name)
                if isinstance(raw_row, Mapping) and raw_row.get("available") is True:
                    available_modules[name] = {
                        str(key): value
                        for key, value in raw_row.items()
                        if key != "available" and value not in (None, "", [], {}, ())
                    }
                else:
                    unavailable_module_names.append(name)
                    if isinstance(raw_row, Mapping):
                        extra = {
                            str(key): value
                            for key, value in raw_row.items()
                            if key not in {"available", "available_in"} and value not in (None, "", [], {}, ())
                        }
                        if extra:
                            unavailable_module_details[name] = extra
            py_view["modules"] = {
                "available": available_modules,
                "unavailable_names": unavailable_module_names,
            }
            if unavailable_module_details:
                py_view["modules"]["unavailable_details"] = unavailable_module_details
        elif "modules" in python:
            py_view["modules"] = python["modules"]

        known_python = {
            "preferred", "interpreters", "interpreter_details", "package_contract", "modules",
            *(str(name) for name in interpreters if isinstance(interpreters, (list, tuple))),
        }
        for key, value in python.items():
            if str(key) not in known_python:
                py_view[str(key)] = value
        view["python"] = py_view
    elif "python" in source:
        view["python"] = source["python"]

    guidance = source.get("validation_guidance")
    if isinstance(guidance, Mapping):
        extra_guidance = {
            str(key): value
            for key, value in guidance.items()
            if key not in {"preferred_python", "missing_commands", "notes"}
            and value not in (None, "", [], {}, ())
        }
        if extra_guidance:
            view["validation_guidance_extra"] = extra_guidance
    elif "validation_guidance" in source and guidance not in (None, "", [], {}, ()):
        view["validation_guidance"] = guidance

    known_top = {
        "schema_version", "workspace_root", "command_names", "python", "network",
        "task_hints", "validation_guidance",
    }
    for key, value in source.items():
        if str(key) not in known_top:
            view[str(key)] = value
    return view


def pcr_model_environment_probe_compact(probe: Mapping[str, Any]) -> dict[str, Any]:
    """Return the compact experimental Solver view of environment truth.

    Keep facts that affect immediate feasibility while making exhaustive PATH and
    package inventories discoverable through the unchanged shell/file tools.  The
    complete probe remains in runtime custody and the FULL treatment remains the
    production baseline until a controlled comparison earns this treatment.
    """
    source = dict(probe)
    if source.get("schema_version") != "environment_probe.v1":
        return source
    view: dict[str, Any] = {
        "schema_version": "environment_probe.compact.v1",
        "source_schema_version": source.get("schema_version"),
        "workspace_root": source.get("workspace_root"),
        "network": source.get("network"),
        "resources": source.get("resources"),
        "discovery": {
            "commands": "Use run_command with command -v/--version or shell discovery when needed.",
            "python_modules": "Use the selected Python interpreter to import/probe modules when needed.",
            "files": "Use read_file/run_command filesystem inspection when needed.",
        },
    }
    command_names = source.get("command_names", {})
    task_hints = source.get("task_hints", {})
    requested = (
        list(task_hints.get("requested_command_names", ()) or ())
        if isinstance(task_hints, Mapping) else []
    )
    requested_rows: dict[str, Any] = {}
    if isinstance(command_names, Mapping):
        for raw_name in requested:
            name = str(raw_name)
            row = command_names.get(name)
            if isinstance(row, Mapping):
                requested_rows[name] = {
                    str(key): value for key, value in row.items()
                    if key in {"available", "path", "version", "detail"}
                    and value not in (None, "", [], {}, ())
                }
            else:
                requested_rows[name] = {"available": False}
        view["commands"] = {
            "probed_count": len(command_names),
            "available_count": sum(
                1 for row in command_names.values()
                if isinstance(row, Mapping) and row.get("available") is True
            ),
            "requested": requested_rows,
        }
    if isinstance(task_hints, Mapping):
        missing = [str(item) for item in task_hints.get("missing_requested_commands", ()) or ()]
        if missing:
            view["missing_requested_commands"] = missing
    python = source.get("python")
    if isinstance(python, Mapping):
        py_view: dict[str, Any] = {}
        for key in ("preferred", "interpreters"):
            value = python.get(key)
            if value not in (None, "", [], {}, ()):
                py_view[key] = value
        modules = python.get("modules")
        if isinstance(modules, Mapping):
            py_view["module_probe_count"] = len(modules)
            py_view["available_module_count"] = sum(
                1 for row in modules.values()
                if isinstance(row, Mapping) and row.get("available") is True
            )
        package_contract = python.get("package_contract")
        if isinstance(package_contract, Mapping):
            py_view["package_install"] = {
                str(key): value for key, value in package_contract.items()
                if key in {"pip_available", "uv_available", "network_status", "install_available"}
                and value not in (None, "", [], {}, ())
            }
        if py_view:
            view["python"] = py_view
    # Remove explicit nulls so the treatment spends no tokens saying nothing.
    return {key: value for key, value in view.items() if value not in (None, "", [], {}, ())}
