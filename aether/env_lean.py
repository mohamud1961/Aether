"""Opt-in arm that stops pushing the unrequested bulk of the preflight environment inventory.

Under ``AETHER_G4_ENV_MODE=lean_v1`` three model-visible prefix sections are rendered smaller.
``lean_v2`` keeps those reductions, names network reachability directly, and adds actionable
installation hints to missing-command/module results; nothing obtainable on request is removed:

* ``[environment_probe]`` keeps interpreter details, network and resources, but the command
  inventory becomes ``{available_count, present, unavailable_from_that_list}`` over a fixed generic
  toolchain list, and the Python module inventory becomes ``{available_count}``.
* ``[envmap_file_map_summary]`` keeps extension counts, file and directory counts and the top-level
  entries (at most ``TOP_LEVEL_LIMIT``).
* ``[envmap_file_tree]`` (a capped listing of visible paths) is not rendered.

The complete probe stays in ``config_realization`` receipt custody, so ``query_history`` with a
literal substring still returns any command or module identity; ``run_command`` (``ls``,
``which``, ``pip list``) remains available. Only the model-facing rendering changes.
"""
from __future__ import annotations

import argparse
from typing import Any, Mapping

from .compiler_prefix import persistent_model_environment_probe

CONTROL = "control"
LEAN_V1 = "lean_v1"
LEAN_V2 = "lean_v2"
SUPPORTED_ENV_MODES = frozenset({CONTROL, LEAN_V1, LEAN_V2})
ENV_MODE_ENV = "AETHER_G4_ENV_MODE"
TOP_LEVEL_LIMIT = 40
EXTENSION_LIMIT = 40
# Generic toolchain commands whose presence is stated by name; ``qemu-*`` is a prefix family.
TOOLCHAIN_COMMANDS: tuple[str, ...] = (
    "gcc", "g++", "clang", "make", "cmake", "python3", "pip", "node", "npm", "java", "javac",
    "rustc", "cargo", "go", "git", "curl", "wget", "docker", "sqlite3", "perl", "ruby", "gdb",
    "valgrind", "apt-get", "dpkg", "pip3", "conda", "gem", "cpan",
)
PACKAGE_MANAGER_COMMANDS: tuple[str, ...] = ("apt-get", "pip", "pip3", "conda", "cpan", "gem")
QEMU_PREFIX = "qemu-"
INVENTORY_ACCESS = (
    "Full command and Python-module inventories are not listed here: search them with query_history "
    "using a literal substring, or run_command (ls, which, pip list)."
)
FILE_LISTING_VIA = "run_command (for example: ls, find)"


class EnvModeError(ValueError):
    """An unknown mode or an unexpected probe shape was supplied."""


def resolve_env_mode(value: str | None = None, *, environ: Mapping[str, str] | None = None) -> str:
    env = environ or {}
    selected = str(value if value is not None else env.get(ENV_MODE_ENV, CONTROL)).strip()
    if selected not in SUPPORTED_ENV_MODES:
        raise EnvModeError(f"unknown env mode: {selected!r}")
    return selected


def add_env_mode_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--env-mode", choices=sorted(SUPPORTED_ENV_MODES), default=CONTROL,
        help="render counts and a fixed toolchain list instead of the full command/module/file inventories (opt-in)",
    )


def build_env_launch_binding(mode: str | None) -> dict[str, Any]:
    selected = resolve_env_mode(mode)
    return {"env_mode": selected, "env": {ENV_MODE_ENV: selected}, "manifest": {"env_mode": selected}}


def _is_available(row: Any) -> bool:
    return isinstance(row, Mapping) and row.get("available") is True


def lean_commands(command_names: Mapping[str, Any]) -> dict[str, Any]:
    available = sorted(str(name) for name, row in command_names.items() if _is_available(row))
    available_set = set(available)
    present = [name for name in TOOLCHAIN_COMMANDS if name in available_set]
    absent = [name for name in TOOLCHAIN_COMMANDS if name not in available_set]
    qemu = [name for name in available if name.startswith(QEMU_PREFIX)]
    present.extend(qemu)
    if not qemu:
        absent.append(QEMU_PREFIX + "*")
    return {
        "available_count": len(available),
        "present": present,
        "unavailable_from_that_list": absent,
    }


def lean_environment_probe(probe: Mapping[str, Any]) -> dict[str, Any]:
    """Return the lean model view of ``probe``; a probe of unknown schema is rendered as the control view."""
    view = persistent_model_environment_probe(probe)
    if probe.get("schema_version") != "environment_probe.v1":
        return view
    command_names = probe.get("command_names")
    if not isinstance(command_names, Mapping):
        raise EnvModeError("environment probe has no command_names mapping; refusing to guess a lean view")
    view.pop("discovered_command_names", None)
    view["commands"] = lean_commands(command_names)
    python = view.get("python")
    source_python = probe.get("python")
    if isinstance(python, dict) and isinstance(source_python, Mapping):
        modules = source_python.get("modules")
        if isinstance(modules, Mapping):
            python["modules"] = {"available_count": sum(1 for row in modules.values() if _is_available(row))}
    view["inventory_access"] = INVENTORY_ACCESS
    return view


def _network_reachability(probe: Mapping[str, Any]) -> str:
    network = probe.get("network")
    if not isinstance(network, Mapping):
        return "unknown"
    status = str(network.get("status", "")).strip().lower()
    value = str(network.get("value", "")).strip().lower()
    if status in {"probed_true", "available", "reachable"} or value in {
        "available", "open_external_network", "reachable",
    }:
        return "reachable"
    if status in {"probed_false", "policy_disabled", "unavailable", "unreachable"} or value in {
        "probed_no_external_network", "no_external_network_by_task_policy", "unreachable",
    }:
        return "unreachable"
    return "unknown"


def lean_v2_environment_probe(probe: Mapping[str, Any]) -> dict[str, Any]:
    """Render lean_v1 inventory plus a concise, explicit network reachability value."""
    view = lean_environment_probe(probe)
    if probe.get("schema_version") == "environment_probe.v1":
        view["network"] = _network_reachability(probe)
    return view


def available_package_managers(probe: Mapping[str, Any]) -> list[str]:
    """Return only package managers present in the immutable command probe."""
    commands = probe.get("command_names")
    if not isinstance(commands, Mapping):
        return []
    return [
        name for name in PACKAGE_MANAGER_COMMANDS
        if _is_available(commands.get(name))
    ]


def actionable_error_hint(
    *, exit_code: int | None, output: str, probe: Mapping[str, Any], success: bool,
) -> str | None:
    """Return one concise install hint for a failed command/module result."""
    if success:
        return None
    text = str(output or "")
    is_python_module = "ModuleNotFoundError" in text or "No module named" in text
    is_perl_module = "Can't locate " in text and ".pm" in text
    is_missing_command = exit_code == 127 or "command not found" in text.lower()
    if not (is_python_module or is_perl_module or is_missing_command):
        return None
    managers = available_package_managers(probe)
    manager_list = ", ".join(managers) if managers else "none detected"
    hint = f"not installed; package managers available here: {manager_list}"
    relevant: list[str] = []
    if is_python_module:
        pip = next((name for name in ("pip", "pip3") if name in managers), "")
        if pip:
            relevant.append(pip)
        elif "apt-get" in managers:
            relevant.append("apt-get (python3-<module>)")
    elif is_perl_module:
        if "apt-get" in managers:
            relevant.append("apt-get (Debian packages named lib<module>-perl)")
        if "cpan" in managers:
            relevant.append("cpan")
    if relevant:
        hint += f"; relevant manager: {', '.join(relevant)}"
    return hint


def lean_file_map(summary: Mapping[str, Any]) -> dict[str, Any]:
    """Counts and top-level entries only; the input mapping is not mutated."""
    counts = summary.get("extension_counts")
    if not isinstance(counts, Mapping):
        raise EnvModeError("file map summary has no extension_counts mapping; refusing to guess a lean view")
    ranked = sorted(((str(ext), int(n)) for ext, n in counts.items()), key=lambda item: (-item[1], item[0]))
    kept = dict(sorted(ranked[:EXTENSION_LIMIT]))
    top_level = [str(item) for item in (summary.get("top_level") or ())][:TOP_LEVEL_LIMIT]
    view: dict[str, Any] = {
        "extension_counts": kept,
        "file_count": summary.get("visible_file_count", 0),
        "dir_count": summary.get("visible_dir_count", 0),
        "top_level": top_level,
        "full_listing_via": FILE_LISTING_VIA,
    }
    if len(ranked) > EXTENSION_LIMIT:
        view["extension_types_omitted"] = len(ranked) - EXTENSION_LIMIT
    return view
