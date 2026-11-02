"""Conservative receipt facts for future replay; unobserved state stays unknown."""

from __future__ import annotations

import posixpath
import re
import shlex

_SENSITIVE = re.compile(r"secret|password|passwd|token|credential|id_rsa|id_ed25519|(?:^|[._-])keys?(?:$|[._-])", re.I)
_ENV_SENSITIVE = re.compile(r"secret|pass|token|credential|private|auth|key", re.I)
_ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
_ENV_BEGIN, _ENV_END, _ENV_UNKNOWN = "AETHER_ENV_NAMES_V1", "AETHER_ENV_NAMES_END", "AETHER_ENV_NAMES_UNKNOWN"

def reset_terminal_pre(session, enabled: bool) -> None:
    if enabled:
        session.pre_action_cwd = None
        session.pre_action_env_names = None


def before_terminal(session, mode: str, interrupt: bool, enabled: bool) -> None:
    if not enabled:
        return
    session.pre_action_cwd = (session.last_observed_cwd
                              if not session.pending and not session.cwd_uncertain and not interrupt else None)
    session.pre_action_env_names = session.env_names if session.pre_action_cwd is not None else None
    if mode == "keys" or interrupt:
        session.cwd_uncertain = True


def record_terminal_receipt(session, mark, enabled: bool) -> None:
    session.last_observed_cwd = None if session.cwd_receipt_ambiguous else mark.group(4)
    session.cwd_receipt_seq = None if session.cwd_receipt_ambiguous else int(mark.group(1))
    if enabled and session.last_observed_cwd is not None:
        session.cwd_uncertain = False
        session.env_names = session.pending_env_names


def terminal_receipt(names: tuple[str, ...], enabled: bool) -> tuple[str, str]:
    from . import facts_probe

    fmt, args = facts_probe.terminal_receipt(names)
    if not enabled:
        return fmt, args
    patterns = "|".join("*" + "".join(f"[{c.lower()}{c.upper()}]" for c in word) + "*"
                        for word in ("secret", "pass", "token", "credential", "private", "auth", "key"))
    script = (
        "if builtin compgen -e >/dev/null 2>&1; then "
        f"printf '{_ENV_BEGIN}\\n'; "
        "builtin compgen -e | while IFS= read -r __aether_env_name; do "
        'case "$__aether_env_name" in ""|AETHER_ENV_NAMES_*|[0-9]*|*[!A-Za-z0-9_]*|'
        + patterns + ') continue;; esac; '
        '[ "${#__aether_env_name}" -le 128 ] || continue; '
        '__aether_env_count=$((${__aether_env_count:-0}+1)); '
        'if [ "$__aether_env_count" -gt 128 ]; then printf "AETHER_ENV_NAMES_TRUNCATED\\n"; break; fi; '
        'printf "%s\\n" "$__aether_env_name"; done; '
        f"printf '{_ENV_END}\\n'; else printf '{_ENV_UNKNOWN}\\n'; fi"
    )
    return fmt + "%s\\n", args + f' "$(/bin/bash --noprofile --norc -p -c {shlex.quote(script)} 2>/dev/null || printf {_ENV_UNKNOWN})"'


def parse_terminal_receipt(names: tuple[str, ...], suffix: str, enabled: bool):
    from . import facts_probe

    if not enabled:
        return facts_probe.terminal_resolution(names, suffix), None
    lines = suffix.splitlines()
    captured = None
    if lines.count(_ENV_BEGIN) == 1 and lines.count(_ENV_END) == 1:
        start, end = lines.index(_ENV_BEGIN), lines.index(_ENV_END)
        if start < end:
            values = lines[start + 1:end]
            if len(values) <= 128 and len(set(values)) == len(values) and all(
                _ENV_NAME.fullmatch(value) and not _ENV_SENSITIVE.search(value) for value in values
            ):
                captured = sorted(values)
            lines = lines[:start] + lines[end + 1:]
    elif lines.count(_ENV_UNKNOWN) == 1 and _ENV_BEGIN not in lines and _ENV_END not in lines:
        lines.remove(_ENV_UNKNOWN)
    return facts_probe.terminal_resolution(names, "\n".join(lines) + "\n"), captured


def cwd_fact(value, workdir: str) -> dict:
    if not isinstance(value, str) or not value.startswith("/") or len(value) > 512:
        return {"status": "unknown"}
    if any(ord(char) < 32 for char in value):
        return {"status": "unknown"}
    root, path = posixpath.normpath(workdir), posixpath.normpath(value)
    relative = path[len(root):] if path == root or path.startswith(root.rstrip("/") + "/") else path
    if any(_SENSITIVE.search(part) for part in relative.split("/") if part):
        return {"status": "unknown", "reason": "path withheld"}
    return {"status": "observed", "value": value, "scope": "last shell or Python completion receipt"}
