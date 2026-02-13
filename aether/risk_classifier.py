from __future__ import annotations

from typing import Any, Dict

from .enum_registry import load_enum_registry
from .policy_config import PolicyConfig

_READ_ONLY_TOOLS = {"read_file", "list_paths", "list_dir", "search_files", "stat_paths", "diff_files"}
_INTERPRETERS = {
    "python",
    "python3",
    "node",
    "ruby",
    "perl",
    "bash",
    "sh",
    "zsh",
}
_NETWORK_COMMANDS = {"curl", "wget", "http", "https"}
_INSTALL_COMMANDS = {"pip", "pip3", "npm", "pnpm", "yarn"}


def classify_risk(tool_name: str, tool_args: Dict[str, Any], policy: PolicyConfig) -> str:
    """Returns 'LOW', 'MED', or 'HIGH' from closed enum."""
    _ = policy  # Explicit for deterministic signature and future policy extensions.
    command = _command_tokens(tool_args)
    first = command[0].lower() if command else ""

    if tool_name in _READ_ONLY_TOOLS:
        risk = "LOW"
    elif tool_name == "verifier":
        if _looks_high_risk(command):
            risk = "HIGH"
        elif _looks_workspace_write(tool_name, tool_args, command):
            risk = "MED"
        else:
            risk = "LOW"
    elif tool_name in {"network_call"}:
        risk = "HIGH"
    elif _looks_high_risk(command):
        risk = "HIGH"
    elif _looks_workspace_write(tool_name, tool_args, command):
        risk = "MED"
    else:
        risk = "LOW"

    registry = load_enum_registry()
    if not registry.validate_enum("risk_class", risk):
        raise ValueError(f"invalid_risk_class:{risk}")
    return risk


def risk_classification_reason(tool_name: str, tool_args: Dict[str, Any]) -> str:
    command = _command_tokens(tool_args)
    first = command[0].lower() if command else ""
    joined = " ".join(command).lower()

    if tool_name in _READ_ONLY_TOOLS:
        return "read_only_tool"
    if tool_name == "verifier":
        if _looks_high_risk(command):
            return "verifier_high_risk_command"
        if _looks_workspace_write(tool_name, tool_args, command):
            return "verifier_workspace_mutation"
        return "verifier_read_only"
    if tool_name == "network_call":
        return "explicit_network_tool"
    if first in _NETWORK_COMMANDS or "http://" in joined or "https://" in joined:
        return "network_command_detected"
    if first in _INSTALL_COMMANDS and "install" in command:
        return "dependency_install_detected"
    if first in _INTERPRETERS:
        return "interpreter_execution_detected"
    if any(token in {"rm", "del", "unlink"} for token in command):
        return "deletion_operation_detected"
    if _looks_workspace_write(tool_name, tool_args, command):
        return "workspace_mutation_detected"
    return "default_read_only"


def emit_risk_eval_event(
    *,
    event_log,
    timestamp: str,
    cwd: str,
    tool_name: str,
    risk_class: str,
    classification_reason: str,
) -> Dict[str, Any]:
    return event_log.append_event(
        {
            "event_type": "RISK_EVAL",
            "timestamp": timestamp,
            "cwd": cwd,
            "tool_name": tool_name,
            "risk_class": risk_class,
            "classification_reason": classification_reason,
        }
    )


def _looks_high_risk(command: list[str]) -> bool:
    if not command:
        return False
    lowered = [token.lower() for token in command]
    first = lowered[0]
    if first in _NETWORK_COMMANDS:
        return True
    if first in _INTERPRETERS:
        return True
    if first in _INSTALL_COMMANDS and "install" in lowered:
        return True
    if first in {"rm", "del", "unlink", "chmod", "chown"}:
        return True
    if any(token.startswith("http://") or token.startswith("https://") for token in lowered):
        return True
    return False


def _looks_workspace_write(tool_name: str, tool_args: Dict[str, Any], command: list[str]) -> bool:
    if tool_name in {"write_file", "apply_patch"}:
        return True
    if tool_name == "pipeline_run" and any(
        isinstance(tool_args.get(field), str) and str(tool_args.get(field)).strip()
        for field in ("stdout_path", "stderr_path")
    ):
        return True
    if isinstance(tool_args.get("write_paths"), list) and bool(tool_args["write_paths"]):
        return True
    lowered = [token.lower() for token in command]
    if any(token in {"touch", "mkdir", "mv", "cp"} for token in lowered):
        return True
    if any(token in {"build", "compile"} for token in lowered):
        return True
    return False


def _command_tokens(tool_args: Dict[str, Any]) -> list[str]:
    command = tool_args.get("command")
    if isinstance(command, list):
        return [str(item) for item in command if str(item)]
    pipeline = tool_args.get("pipeline")
    if isinstance(pipeline, list) and pipeline:
        first = pipeline[0]
        if isinstance(first, dict):
            first_command = first.get("command")
            if isinstance(first_command, list):
                return [str(item) for item in first_command if str(item)]
    cmd = tool_args.get("cmd")
    args = tool_args.get("args")
    if isinstance(cmd, str) and isinstance(args, list):
        return [cmd, *[str(item) for item in args]]
    return []
