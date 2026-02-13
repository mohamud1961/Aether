from __future__ import annotations

from typing import Any, Dict

from .policy_config import PolicyConfig

_NETWORK_COMMANDS = {"curl", "wget"}
_INSTALL_PATTERNS = {
    ("pip", "install"),
    ("pip3", "install"),
    ("python", "-m", "pip", "install"),
    ("python3", "-m", "pip", "install"),
    ("npm", "install"),
    ("pnpm", "install"),
    ("yarn", "add"),
}


def check_network_allowed(tool_name: str, tool_args: Dict, policy: PolicyConfig) -> bool:
    if _network_enabled(policy):
        return True
    if tool_name == "network_call":
        return False

    command = _command_tokens(tool_args)
    if not command:
        return True
    lowered = tuple(token.lower() for token in command)
    if lowered[0] in _NETWORK_COMMANDS:
        return False
    for pattern in _INSTALL_PATTERNS:
        if lowered[: len(pattern)] == pattern:
            return False
    if any(token.startswith("http://") or token.startswith("https://") for token in lowered):
        return False
    return True


def _network_enabled(policy: PolicyConfig) -> bool:
    value = getattr(policy, "network_enabled", None)
    if isinstance(value, bool):
        return value
    # Default open to avoid accidental hard break on legacy profiles.
    return True


def _command_tokens(tool_args: Dict[str, Any]) -> list[str]:
    command = tool_args.get("command")
    if isinstance(command, list):
        return [str(item) for item in command if str(item)]
    cmd = tool_args.get("cmd")
    args = tool_args.get("args")
    if isinstance(cmd, str) and isinstance(args, list):
        return [cmd, *[str(item) for item in args]]
    return []
