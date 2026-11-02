"""Bounded environment measurements. No task file contents are opened."""

from __future__ import annotations

import re
import shlex
from typing import Any

from .env import Environment, run

COMMANDS = (
    "python3", "python", "pip3", "pip", "node", "npm", "gcc", "g++", "make",
    "cmake", "git", "curl", "wget", "file", "xxd", "od", "strings", "nm",
    "objdump", "readelf", "gdb", "sqlite3", "jq", "rg", "ps", "ss", "netstat",
    "perl", "ruby", "go", "rustc", "cargo", "java", "R", "tesseract",
    "convert", "pdftotext", "chromium", "chromium-browser", "google-chrome",
    "firefox", "chromedriver", "apt-get", "apk", "dnf", "yum", "conda",
)
LANGUAGES = ("python3", "gcc", "g++", "node", "java", "rustc", "go")
MANAGERS = ("pip3", "pip", "apt-get", "apk", "dnf", "yum", "conda", "npm", "cargo")
HOSTS = (("pypi.org", 443), ("deb.debian.org", 80))
SYSTEM_TIMEOUT_PATHS = ("/usr/bin/timeout", "/bin/timeout")
MAX_FILES = 20
_COMMAND_NAME = re.compile(r"^[A-Za-z0-9_+.-]{1,64}$")
_RESOLUTION_MARKER = "AETHER_TERMINAL_RESOLUTION_V1"
_SENSITIVE = re.compile(
    r"secret|password|passwd|token|credential|key|private|"
    r"(?:^|[._-])(?:tests?|solutions?|verifiers?|graders?|grades?|id_rsa|id_ed25519)(?:$|[._-])|"
    r"\.(?:pem|p12|pfx)$", re.I,
)
_NAME = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.+-]{0,127}$")
_PATH = re.compile(r"^/[A-Za-z0-9_./+@ -]{1,240}$")
_VERSION = re.compile(r"^[A-Za-z0-9_ .+:/()\-]{1,120}$")
_VERSION_NUMBER = re.compile(r"(?<![A-Za-z0-9])(?:v|go)?[0-9]+(?:\.[0-9]+){1,3}(?:[-+._a-zA-Z0-9]{0,20})?")


def terminal_scope(names: tuple[str, ...]) -> None:
    if len(names) > 100 or len(set(names)) != len(names) or not all(_COMMAND_NAME.fullmatch(n) for n in names):
        raise ValueError("invalid terminal command-resolution scope")


def terminal_receipt(names: tuple[str, ...]) -> tuple[str, str]:
    """An isolated shell observes PATH without invoking task-defined functions."""
    if not names:
        return "", ""
    words = " ".join(shlex.quote(name) for name in names)
    script = (
        f"printf '%s\\n' {_RESOLUTION_MARKER}; for __aether_name in {words}; do "
        'if command -v "$__aether_name" >/dev/null 2>&1; then '
        'printf "1 %s\\n" "$__aether_name"; else '
        'printf "0 %s\\n" "$__aether_name"; fi; done'
    )
    return "%s\\n", f' "$(PATH="${{PATH-}}" /bin/sh -p -c {shlex.quote(script)} 2>/dev/null || :)"'


def terminal_resolution(names: tuple[str, ...], suffix: str) -> dict[str, bool] | None:
    lines = suffix.splitlines()
    if not names or len(lines) != len(names) + 2 or lines[0] != _RESOLUTION_MARKER:
        return None
    if lines[-1] not in ("__ALIVE__", "__DEAD__"):
        return None
    parsed = {}
    for line in lines[1:-1]:
        flag, separator, name = line.partition(" ")
        if not separator or flag not in ("0", "1") or name not in names or name in parsed:
            return None
        parsed[name] = flag == "1"
    return parsed if set(parsed) == set(names) else None


def terminal_observation(session: Any, generation: int | None) -> dict | None:
    if session is None:
        return None
    known = not session.pending and session.command_resolution is not None
    return {
        "generation": generation,
        "foreground": "completion_not_observed" if session.pending else "idle_at_last_observation",
        "last_observed_cwd": session.last_observed_cwd,
        "cwd_receipt_seq": session.cwd_receipt_seq,
        "last_command_seq": session.seq,
        "command_resolution": {
            "status": "observed" if known else "unknown",
            "resolved": dict(session.command_resolution) if known else None,
            "source": "terminal receipt",
            "receipt_seq": session.resolution_receipt_seq,
            "freshness": "last_observation" if known else "unknown",
        },
        "background_processes": "unknown",
    }


def _case_insensitive(word: str) -> str:
    return "".join(f"[{c.lower()}{c.upper()}]" if c.isalpha() else c for c in word)


def _script(workdir: str, *, full: bool, hosts: tuple[tuple[str, int], ...]) -> str:
    """Generate a fixed shell program; only a quoted workdir is variable input."""
    bad = "|".join("*" + _case_insensitive(x) + "*" for x in
                   ("secret", "password", "passwd", "token", "credential", "key", "private",
                    "test", "solution", "verifier", "grader", "grade"))
    bad += "|*." + _case_insensitive("pem") + "|*." + _case_insensitive("p12") + "|*." + _case_insensitive("pfx")
    commands = " ".join(shlex.quote(x) for x in COMMANDS)
    lines = [
        "LC_ALL=C; export LC_ALL",
        "printf 'AETHER_FACTS_V1\\n'",
        f"for __af_name in {commands}; do",
        '  __af_value=$(command -v "$__af_name" 2>/dev/null) && '
        'printf "C\\t%s\\t%s\\n" "$__af_name" "$__af_value" || '
        'printf "C\\t%s\\t-\\n" "$__af_name"',
        "done",
        f"__af_root={shlex.quote(workdir)}",
        "__af_count=0; __af_seen=0; __af_incomplete=0",
        'if [ ! -d "$__af_root" ] || [ -L "$__af_root" ]; then __af_incomplete=1; else',
        '  for __af_path in "$__af_root"/*; do',
        '    if [ ! -e "$__af_path" ] && [ ! -L "$__af_path" ]; then continue; fi',
        '    __af_seen=$((__af_seen+1)); [ "$__af_seen" -gt 1000 ] && { __af_incomplete=1; break; }',
        '    __af_base=${__af_path##*/}',
        f'    case "$__af_base" in {bad}) __af_incomplete=1; continue;; esac',
        '    case "$__af_base" in *[!A-Za-z0-9_.+-]*|"") __af_incomplete=1; continue;; esac',
        '    if [ -L "$__af_path" ]; then __af_incomplete=1; continue; fi',
        '    __af_count=$((__af_count+1)); [ "$__af_count" -gt 20 ] && { __af_incomplete=1; break; }',
        '    if [ -d "$__af_path" ]; then __af_kind=d; elif [ -f "$__af_path" ]; then __af_kind=f;',
        '    else __af_incomplete=1; continue; fi',
        '    printf "F\\t%s\\t%s\\n" "$__af_kind" "$__af_base"',
        "  done",
        "fi",
        'printf "FEND\\t%s\\n" "$__af_incomplete"',
    ]
    if full:
        languages = " ".join(shlex.quote(x) for x in LANGUAGES)
        lines += [
            f"for __af_name in {languages}; do",
            # A binary on PATH can be task-supplied; even --version can
            # modify the task environment or read private data.
            '  printf "V\\t%s\\t-\\n" "$__af_name"',
            "done",
            "__af_mem=",
            "if [ -r /proc/meminfo ]; then",
            '  while read -r __af_key __af_value __af_rest; do',
            '    if [ "$__af_key" = "MemAvailable:" ]; then __af_mem=$__af_value; break; fi',
            '  done < /proc/meminfo',
            "fi",
            'printf "M\\t%s\\n" "${__af_mem:--}"',
            "__af_timeout=",
            "for __af_tool in " + " ".join(shlex.quote(x) for x in SYSTEM_TIMEOUT_PATHS) + "; do",
            '  if [ -x "$__af_tool" ]; then __af_timeout=$__af_tool; break; fi',
            "done",
        ]
        for host, port in hosts:
            if not re.fullmatch(r"[a-z0-9.-]+", host) or not 1 <= port <= 65535:
                raise ValueError("invalid fixed host")
            lines += [
                'if [ -n "$__af_timeout" ] && [ -x /bin/bash ]; then',
                f"  if \"$__af_timeout\" 1 /bin/bash --noprofile --norc -p -c 'echo > /dev/tcp/{host}/{port}' 2>/dev/null; "
                f"then printf 'N\\t{host}:{port}\\tconnected\\n'; "
                f"else printf 'N\\t{host}:{port}\\tunsuccessful\\n'; fi",
                f"else printf 'N\\t{host}:{port}\\tunknown\\n'; fi",
            ]
    lines.append("printf 'AETHER_FACTS_END\\n'")
    return "\n".join(lines)


def _parse(text: str, *, full: bool, hosts: tuple[tuple[str, int], ...]) -> dict[str, Any]:
    lines = text.splitlines()
    if not lines or lines[0] != "AETHER_FACTS_V1" or lines[-1] != "AETHER_FACTS_END":
        raise ValueError("incomplete probe")
    commands: dict[str, str | None] = {}
    files: list[str] = []
    versions: dict[str, str | None] = {}
    network: dict[str, str] = {}
    complete: bool | None = None
    memory: int | None = None
    memory_seen = False
    for line in lines[1:-1]:
        parts = line.split("\t")
        if len(parts) == 3 and parts[0] == "C" and parts[1] in COMMANDS and parts[1] not in commands:
            value = parts[2]
            if value == "-":
                commands[parts[1]] = None
            elif not _PATH.fullmatch(value) or _SENSITIVE.search(value):
                commands[parts[1]] = "resolved; path withheld"
            else:
                commands[parts[1]] = value
        elif len(parts) == 3 and parts[0] == "F" and parts[1] in ("d", "f"):
            name = parts[2]
            if not _NAME.fullmatch(name) or _SENSITIVE.search(name):
                raise ValueError("unsafe directory entry")
            files.append(name + ("/" if parts[1] == "d" else ""))
        elif len(parts) == 2 and parts[0] == "FEND" and parts[1] in ("0", "1") and complete is None:
            complete = parts[1] == "0"
        elif len(parts) == 3 and parts[0] == "V" and parts[1] in LANGUAGES and parts[1] not in versions:
            value = parts[2]
            match = _VERSION_NUMBER.search(value) if value != "-" and _VERSION.fullmatch(value) else None
            versions[parts[1]] = match.group() if match else None
        elif len(parts) == 2 and parts[0] == "M" and not memory_seen:
            memory_seen = True
            memory = int(parts[1]) if parts[1].isdigit() else None
        elif len(parts) == 3 and parts[0] == "N" and parts[2] in ("connected", "unsuccessful", "unknown"):
            if parts[1] in network:
                raise ValueError("duplicate host")
            network[parts[1]] = parts[2]
        else:
            raise ValueError("unrecognized probe record")
    if set(commands) != set(COMMANDS) or complete is None or len(files) > MAX_FILES or len(set(files)) != len(files):
        raise ValueError("incomplete or duplicate probe fields")
    if full and (set(versions) != set(LANGUAGES) or not memory_seen or
                 set(network) != {f"{host}:{port}" for host, port in hosts}):
        raise ValueError("incomplete full probe")
    return {"commands": commands, "files": sorted(files), "files_complete": complete,
            "versions": versions if full else None, "network": network if full else None,
            "host_available_memory_kib": memory if full else None}


async def probe(env: Environment, workdir: str, *, full: bool, remaining_s: float,
                hosts: tuple[tuple[str, int], ...] = HOSTS) -> dict[str, Any]:
    if remaining_s < 2:
        return {"ok": False, "reason": "insufficient time"}
    try:
        result = await run(env, _script(workdir, full=full, hosts=hosts),
                           timeout_s=max(1, int(min(15, remaining_s - 1))))
        if result.code != 0:
            return {"ok": False, "reason": "probe command failed"}
        return {"ok": True, "facts": _parse(result.stdout, full=full, hosts=hosts)}
    except Exception as exc:  # timeouts and malformed output do not establish an environment fact
        return {"ok": False, "reason": type(exc).__name__}
