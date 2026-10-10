"""Static protocol-card sections of the solver's stable prompt prefix.

Extracted from compiler.py for the 500-LOC cap.  These are byte-stable across
every task and step; dynamic (task/world) sections stay in the compiler.
"""
from __future__ import annotations

from typing import Any, Mapping
from pathlib import PurePosixPath


PERSISTENT_STATIC_KERNEL_V1_TOOL_SEMANTICS = (
    "Only action kinds exposed by the provided native function schemas are callable. Use exactly the argument "
    "fields declared for the chosen action. One act turn contains one action frontier. "
    "Long tool outputs return handles that read_output can read; query_history searches earlier receipts."
)

PERSISTENT_STATIC_KERNEL_JOBS_V1_TOOL_SEMANTICS = (
    PERSISTENT_STATIC_KERNEL_V1_TOOL_SEMANTICS
    + " Use run_command for bounded commands that should return. For a command expected to stay live "
      "as a background job or service, use start_job so reasoning can continue; use probe_job to observe "
      "that exact job and stop_process only when cancellation is actually intended."
)

PERSISTENT_PROTOCOL_CARD_SECTIONS: tuple[tuple[str, str], ...] = (
    (
        "tool_semantics",
        (
            "Only action kinds exposed by the provided native function schemas are callable. Use exactly the argument "
            "fields declared for the chosen action. One act turn contains one action frontier. "
            "Use bootstrap_acquire for dependency installation. Use launch_process for a managed "
            "task-local process and start_job for a detached/persistent job or service; observe a "
            "started job with probe_job instead of emulating lifecycle with nohup or shell '&'. "
            "Treat a start_job as unfinished until its exact generation-bound probe establishes a "
            "successful terminal result, unless the task contract declares that named process as a "
            "persistent live service. Stopping, canceling, losing, or observing failure of a finite "
            "job is not evidence that the work succeeded; establish later current execution or "
            "verification evidence before completion."
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


PERSISTENT_STATIC_KERNEL_EDIT_V1_COMPLETION_CONTROLS = (
    "Use finish when you decide the task is complete; it actually finishes. It cites "
    "current evidence references. Do not use it to report known incompleteness."
)


def protocol_card_sections(
    tool_surface_mode: str = "control",
) -> tuple[tuple[str, str], ...]:
    """Return Aether's sole PERSISTENT protocol-card sections.

    Control is the byte-stable incumbent; static_kernel_v1 names only exposed tools.
    """
    if tool_surface_mode == "static_kernel_v1":
        return tuple(
            (name, PERSISTENT_STATIC_KERNEL_V1_TOOL_SEMANTICS if name == "tool_semantics" else text)
            for name, text in PERSISTENT_PROTOCOL_CARD_SECTIONS
        )
    if tool_surface_mode == "static_kernel_jobs_v1":
        return tuple(
            (name, PERSISTENT_STATIC_KERNEL_JOBS_V1_TOOL_SEMANTICS if name == "tool_semantics" else text)
            for name, text in PERSISTENT_PROTOCOL_CARD_SECTIONS
        )
    if tool_surface_mode in {"static_kernel_edit_v1", "static_kernel_edit_flat_v1"}:
        return tuple(
            (name, PERSISTENT_STATIC_KERNEL_V1_TOOL_SEMANTICS if name == "tool_semantics"
             else PERSISTENT_STATIC_KERNEL_EDIT_V1_COMPLETION_CONTROLS if name == "completion_controls"
             else text)
            for name, text in PERSISTENT_PROTOCOL_CARD_SECTIONS
        )
    return PERSISTENT_PROTOCOL_CARD_SECTIONS

def persistent_model_environment_probe(probe: Mapping[str, Any]) -> dict[str, Any]:
    """Return a factual PERSISTENT model view of the bounded environment probe.

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


def persistent_model_environment_probe_compact(probe: Mapping[str, Any]) -> dict[str, Any]:
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
            "environment_inventory": (
                "When the task gives a literal tool/module marker but not its name, use query_history with "
                "that literal marker to search Aether's bounded preflight environment inventory. Treat returned "
                "inventory facts as preflight/historical and revalidate mutable availability with a live tool action."
            ),
            "commands": "Prefer exact preflight inventory lookup when a literal marker is known; otherwise use run_command with portable command -v/--version or bounded shell discovery.",
            "python_modules": "Prefer exact preflight inventory lookup when a literal marker is known; otherwise use the selected Python interpreter to import/probe modules.",
            "files": "Use read_file/run_command filesystem inspection when needed.",
            "paths": "Prefer returned exact paths or task-workspace-relative paths instead of reconstructing long absolute paths manually.",
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


def persistent_model_environment_probe_compact_scoped(probe: Mapping[str, Any]) -> dict[str, Any]:
    """Compact factual context plus task-local live-discovery scope.

    This treatment intentionally does *not* select a task-relevant executable,
    module, file, or strategy. It projects only mechanically observed topology
    that can bound Frontier's own live discovery: workspace-local executable roots,
    interpreter identity, counts, and feasibility facts. Exhaustive inventories
    remain out of the hot prefix.
    """
    source = dict(probe)
    scoped = dict(persistent_model_environment_probe_compact(source))
    workspace_root = str(source.get("workspace_root") or "").rstrip("/")
    roots: set[str] = set()
    command_names = source.get("command_names", {})
    if workspace_root and isinstance(command_names, Mapping):
        for row in command_names.values():
            if not isinstance(row, Mapping) or row.get("available") is not True:
                continue
            raw_path = str(row.get("path") or "").strip()
            if not raw_path.startswith("/"):
                continue
            parent = str(PurePosixPath(raw_path).parent)
            if parent == workspace_root or parent.startswith(workspace_root + "/"):
                roots.add(parent)
    commands = dict(scoped.get("commands", {}) or {})
    if roots:
        commands["workspace_search_roots"] = sorted(roots)[:16]
    if commands:
        scoped["commands"] = commands

    discovery = dict(scoped.get("discovery", {}) or {})
    # Replace compact-v1's inventory-first wording. The scoped treatment's
    # causal variable is precisely that unknown behavioral identities are
    # discovered live inside a small factual scope rather than assumed to be
    # present in an exact preflight/history index.
    discovery.update({
        "environment_inventory": (
            "Exhaustive command/module inventories remain in Aether custody rather than the hot prefix. "
            "Use recorded-history retrieval only for facts actually observed already; unknown behavioral "
            "identity is established through live discovery."
        ),
        "commands": (
            "For an exact known command name, use ordinary live command lookup. For an unknown name, prefer "
            "one bounded live scan of workspace_search_roots when present; otherwise inspect PATH and test "
            "candidate behavior in the same bounded action when practical."
        ),
        "python_modules": (
            "Use the selected interpreter for live module discovery. When the module name is unknown, inspect "
            "sys.path/pkgutil and test the task's ROLE/behavior in one bounded live action when practical."
        ),
        "behavioral_descriptor": (
            "When a command or module name is unknown but the task gives a behavioral/version/ROLE "
            "descriptor, own the discovery live. Prefer one bounded discriminating action: enumerate the "
            "relevant task-local search root when one is supplied (otherwise inspect PATH/sys.path) and test "
            "candidate identities in the same bounded action when practical."
        ),
        "history_boundary": (
            "query_history is literal retrieval over facts already recorded by Aether; do not assume an "
            "unobserved behavioral descriptor is indexed there."
        ),
        "scope_priority": (
            "Prefer workspace-local/task-local roots before broad system-wide enumeration. The model chooses "
            "the probe and interprets its result; these roots are topology only."
        ),
    })
    scoped["schema_version"] = "environment_probe.compact_scoped.v1"
    scoped["discovery"] = discovery
    scoped["guidance_version"] = "bounded_live_discovery.v1"
    return {key: value for key, value in scoped.items() if value not in (None, "", [], {}, ())}


def persistent_model_environment_probe_compact_guided(probe: Mapping[str, Any]) -> dict[str, Any]:
    """Return compact environment truth with an explicit discovery protocol.

    ``compact`` already removes exhaustive inventories.  This treatment keeps
    the same information boundary but makes the first recovery move explicit:
    demand-load an exact preflight identity when the task supplies a literal
    descriptor, then revalidate it against the live workspace.  The guidance is
    generic and never contains a task-specific command, module, path, or token.
    """
    view = persistent_model_environment_probe_compact(probe)
    guided = dict(view)
    discovery = dict(guided.get("discovery", {}) or {})
    discovery.update({
        "first_choice": (
            "If the task describes an unknown command or Python module with a literal descriptor, "
            "first call query_history with that exact descriptor. Use the returned identity only as "
            "a historical lead, then revalidate it with one live command or import before writing output."
        ),
        "bounded_fallback": (
            "If no literal descriptor is available, use a bounded portable probe such as command -v, "
            "a directory listing, or one selected-interpreter import check. Do not execute every PATH "
            "entry, assume GNU-only flags, or reconstruct long absolute paths by hand."
        ),
        "evidence_boundary": (
            "query_history is a retrieval aid, not completion evidence; completion must cite current "
            "live tool output and the resulting workspace state."
        ),
    })
    guided["schema_version"] = "environment_probe.compact_guided.v1"
    guided["discovery"] = discovery
    guided["guidance_version"] = "demand_loaded_inventory.v1"
    return {key: value for key, value in guided.items() if value not in (None, "", [], {}, ())}
