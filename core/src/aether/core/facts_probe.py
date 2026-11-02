"""Bounded measurements; file contents are read only for explicit watched paths."""

from __future__ import annotations

import json
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
SYSTEM_BASH_PATHS = ("/usr/bin/bash", "/bin/bash")
SYSTEM_PYTHON_PATHS = (
    "/usr/bin/python3.13", "/usr/bin/python3.12", "/usr/bin/python3.11",
    "/usr/bin/python3.10", "/usr/bin/python3.9", "/usr/bin/python3",
    "/usr/local/bin/python3.13", "/usr/local/bin/python3.12",
    "/usr/local/bin/python3.11", "/usr/local/bin/python3.10",
)
MAX_FILES = 20
MAX_WATCHED = 16
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


def safe_relative(path: str) -> bool:
    parts = path.split("/")
    return (len(path) <= 256 and len(parts) <= 8 and all(
        _NAME.fullmatch(part) and not _SENSITIVE.search(part) for part in parts
    ))


# This runs only in the task environment and only with a fixed system
# interpreter. Directory operations use no-follow descriptors; regular
# contents are opened solely for explicitly watched safe paths.
_WORKSPACE_SCRIPT = r"""
import hashlib, json, os, re, stat, sys
root, watched = sys.argv[1], json.loads(sys.argv[2])
safe = re.compile(r'^[A-Za-z0-9_][A-Za-z0-9_.+-]{0,127}$')
protect = re.compile(r'secret|password|passwd|token|credential|key|private|(?:^|[._-])(?:tests?|solutions?|verifiers?|graders?|grades?|id_rsa|id_ed25519)(?:$|[._-])|\.(?:pem|p12|pfx)$', re.I)
files = {}; omitted = 0; scanned = 0
def allowed(name):
    return bool(safe.fullmatch(name)) and not protect.search(name)
def open_root(path):
    parts = [part for part in path.split('/') if part]
    if not path.startswith('/') or not parts or any(part in ('.', '..') for part in parts):
        raise ValueError('workspace root is not a safe absolute directory')
    parent = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in parts:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
            os.close(parent); parent = child
        return parent
    except Exception:
        os.close(parent)
        raise
def walk(fd, prefix, depth, device):
    global omitted, scanned
    try:
        with os.scandir(fd) as iterator:
            for item in iterator:
                scanned += 1
                if scanned > 512:
                    omitted += 1
                    return
                name = item.name
                if not allowed(name) or len(prefix + name) > 256:
                    omitted += 1
                    continue
                try:
                    meta = os.stat(name, dir_fd=fd, follow_symlinks=False)
                    if meta.st_dev != device:
                        omitted += 1
                    elif stat.S_ISDIR(meta.st_mode):
                        if depth >= 4:
                            omitted += 1
                        else:
                            child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                            try:
                                if os.fstat(child).st_dev != device: omitted += 1
                                else: walk(child, prefix + name + '/', depth + 1, device)
                            finally: os.close(child)
                    elif stat.S_ISREG(meta.st_mode) and meta.st_nlink == 1 and len(files) < 200:
                        files[prefix + name] = [meta.st_dev, meta.st_ino, meta.st_size, meta.st_mtime_ns, meta.st_ctime_ns, meta.st_mode]
                    else:
                        omitted += 1
                except OSError:
                    omitted += 1
    except OSError:
        omitted += 1
def fingerprint(rootfd, path, device):
    parts = path.split('/')
    if not parts or len(parts) > 8 or any(not allowed(part) for part in parts):
        return {'status': 'unknown'}
    parent = os.dup(rootfd)
    try:
        for part in parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
            os.close(parent); parent = child
            if os.fstat(parent).st_dev != device:
                return {'status': 'unknown'}
        fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        try:
            before = os.fstat(fd)
            if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_dev != device
                    or before.st_size > 1048576):
                return {'status': 'unknown'}
            digest = hashlib.sha256()
            remaining = before.st_size
            while remaining:
                block = os.read(fd, min(65536, remaining))
                if not block: return {'status': 'unknown'}
                digest.update(block)
                remaining -= len(block)
            after = os.fstat(fd)
            identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_mode)
            return ({'status': 'observed', 'sha256': digest.hexdigest()}
                    if identity(before) == identity(after) else {'status': 'unknown'})
        finally:
            os.close(fd)
    except FileNotFoundError:
        return {'status': 'absent'}
    except (OSError, ValueError):
        return {'status': 'unknown'}
    finally:
        os.close(parent)
try:
    fd = open_root(root)
    try:
        st = os.fstat(fd)
        walk(fd, '', 1, st.st_dev)
        fingerprints = {name: fingerprint(fd, name, st.st_dev) for name in watched}
        # A task can move or replace the root while the descriptor remains
        # open.  Reopen without following links and publish only if the path
        # still names the directory that was scanned.
        check = open_root(root)
        try:
            latest = os.fstat(check)
            if (latest.st_dev, latest.st_ino) != (st.st_dev, st.st_ino):
                raise ValueError('workspace root changed during observation')
        finally:
            os.close(check)
    finally:
        os.close(fd)
    print('W\t' + json.dumps({'root': [st.st_dev, st.st_ino], 'files': files,
                              'complete': omitted == 0, 'fingerprints': fingerprints},
                             ensure_ascii=True, separators=(',', ':')))
except Exception:
    print('W\t-')
"""


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


def _system_binary(variable: str, paths: tuple[str, ...]) -> list[str]:
    if not re.fullmatch(r"__af_[a-z]+", variable) or any(
        not path.startswith("/") or ".." in path.split("/") or not path.strip("/")
        for path in paths
    ):
        raise ValueError("invalid system binary scope")
    return [
        f"{variable}=",
        "for __af_tool in " + " ".join(shlex.quote(x) for x in paths) + "; do",
        '  case "$__af_root" in /) continue;; esac',
        '  __af_root_prefix=${__af_root%/}',
        '  case "$__af_tool" in "$__af_root_prefix"/*) continue;; esac',
        '  __af_parent=$__af_tool; __af_links=0',
        '  while [ -n "$__af_parent" ] && [ "$__af_parent" != / ]; do',
        '    if [ -L "$__af_parent" ]; then __af_links=1; break; fi',
        '    __af_parent=${__af_parent%/*}',
        '  done',
        '  if [ "$__af_links" -ne 0 ]; then continue; fi',
        f'  if [ -x "$__af_tool" ] && [ -f "$__af_tool" ]; then {variable}=$__af_tool; break; fi',
        "done",
    ]


def _script(workdir: str, *, full: bool, hosts: tuple[tuple[str, int], ...],
            watched: tuple[str, ...]) -> str:
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
        'case "$__af_root" in /*) :;; *) __af_incomplete=1;; esac',
        'case "/$__af_root/" in */../*|*/./*) __af_incomplete=1;; esac',
        'case "$__af_root" in *[!/]*) :;; *) __af_incomplete=1;; esac',
        '__af_check=$__af_root; while [ "$__af_incomplete" -eq 0 ] && [ -n "$__af_check" ] && [ "$__af_check" != / ]; do',
        '  if [ -L "$__af_check" ]; then __af_incomplete=1; break; fi; __af_check=${__af_check%/*}',
        'done',
        'if [ "$__af_incomplete" -ne 0 ] || [ ! -d "$__af_root" ]; then __af_incomplete=1; else',
        '  ( command cd -P "$__af_root" 2>/dev/null || exit 1',
        '    __af_actual=$(command pwd -P 2>/dev/null) || exit 1',
        '    __af_expected=${__af_root%/}; [ -n "$__af_expected" ] || exit 1',
        '    [ "$__af_actual" = "$__af_expected" ] || exit 1',
        '    [ . -ef "$__af_root" ] 2>/dev/null || exit 1',
        '    __af_entries=',
        '  for __af_path in ./*; do',
        '    if [ -L "$__af_path" ]; then __af_incomplete=1; continue; fi',
        '    if [ ! -e "$__af_path" ]; then continue; fi',
        '    __af_seen=$((__af_seen+1)); [ "$__af_seen" -gt 1000 ] && { __af_incomplete=1; break; }',
        '    __af_base=${__af_path##*/}',
        f'    case "$__af_base" in {bad}) __af_incomplete=1; continue;; esac',
        '    case "$__af_base" in *[!A-Za-z0-9_.+-]*|"") __af_incomplete=1; continue;; esac',
        '    __af_count=$((__af_count+1)); [ "$__af_count" -gt 20 ] && { __af_incomplete=1; break; }',
        '    if [ -d "$__af_path" ]; then __af_kind=d; elif [ -f "$__af_path" ]; then __af_kind=f;',
        '    else __af_incomplete=1; continue; fi',
        '    __af_entries="${__af_entries}F\t${__af_kind}\t${__af_base}\n"',
        "  done",
        '    __af_final=$(command pwd -P 2>/dev/null) || exit 1',
        '    [ "$__af_final" = "$__af_expected" ] || exit 1',
        '    [ . -ef "$__af_root" ] 2>/dev/null || exit 1',
        '    __af_check=$__af_root; while [ -n "$__af_check" ] && [ "$__af_check" != / ]; do',
        '      [ -L "$__af_check" ] && exit 1; __af_check=${__af_check%/*}',
        '    done',
        '    printf "%s" "$__af_entries"',
        '    printf "FEND\\t%s\\n" "$__af_incomplete"',
        '  ) && __af_incomplete=2 || __af_incomplete=1',
        "fi",
        '[ "$__af_incomplete" -eq 2 ] || printf "FEND\\t1\\n"',
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
        ]
        lines += _system_binary("__af_timeout", SYSTEM_TIMEOUT_PATHS)
        lines += _system_binary("__af_bash", SYSTEM_BASH_PATHS)
        for host, port in hosts:
            if not re.fullmatch(r"[a-z0-9.-]+", host) or not 1 <= port <= 65535:
                raise ValueError("invalid fixed host")
            lines += [
                'if [ -n "$__af_timeout" ] && [ -n "$__af_bash" ]; then',
                f"  if \"$__af_timeout\" 1 \"$__af_bash\" --noprofile --norc -p -c 'echo > /dev/tcp/{host}/{port}' 2>/dev/null; "
                f"then printf 'N\\t{host}:{port}\\tconnected\\n'; "
                f"else printf 'N\\t{host}:{port}\\tunsuccessful\\n'; fi",
                f"else printf 'N\\t{host}:{port}\\tunknown\\n'; fi",
            ]
    if len(watched) > MAX_WATCHED or len(set(watched)) != len(watched) or not all(safe_relative(p) for p in watched):
        raise ValueError("invalid watched workspace paths")
    lines += _system_binary("__af_python", SYSTEM_PYTHON_PATHS)
    lines += [
        'if [ -n "$__af_python" ]; then',
        f'  "$__af_python" -I -S -B -c {shlex.quote(_WORKSPACE_SCRIPT)} "$__af_root" '
        f'{shlex.quote(json.dumps(watched))} 2>/dev/null || printf "W\\t-\\n"',
        'else printf "W\\t-\\n"; fi',
        "printf 'AETHER_FACTS_END\\n'",
    ]
    return "\n".join(lines)


def _parse(text: str, *, full: bool, hosts: tuple[tuple[str, int], ...],
           watched: tuple[str, ...]) -> dict[str, Any]:
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
    workspace: dict | None = None
    workspace_seen = False
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
        elif len(parts) == 2 and parts[0] == "W" and not workspace_seen:
            workspace_seen = True
            if parts[1] != "-":
                value = json.loads(parts[1])
                if not isinstance(value, dict) or type(value.get("complete")) is not bool:
                    raise ValueError("malformed workspace observation")
                root, entries, fingerprints = value.get("root"), value.get("files"), value.get("fingerprints")
                if (not isinstance(root, list) or len(root) != 2 or any(type(n) is not int for n in root) or
                        not isinstance(entries, dict) or len(entries) > 200 or
                        any(not safe_relative(k) or not isinstance(v, list) or len(v) != 6 or
                            any(type(n) is not int for n in v) for k, v in entries.items()) or
                        not isinstance(fingerprints, dict) or set(fingerprints) != set(watched)):
                    raise ValueError("malformed workspace entries")
                for item in fingerprints.values():
                    if not isinstance(item, dict) or item.get("status") not in ("observed", "unknown", "absent"):
                        raise ValueError("malformed fingerprint")
                    if item["status"] == "observed" and not re.fullmatch(r"[0-9a-f]{64}", str(item.get("sha256", ""))):
                        raise ValueError("malformed fingerprint digest")
                workspace = value
        else:
            raise ValueError("unrecognized probe record")
    if (set(commands) != set(COMMANDS) or complete is None or not workspace_seen or
            len(files) > MAX_FILES or len(set(files)) != len(files)):
        raise ValueError("incomplete or duplicate probe fields")
    if full and (set(versions) != set(LANGUAGES) or not memory_seen or
                 set(network) != {f"{host}:{port}" for host, port in hosts}):
        raise ValueError("incomplete full probe")
    return {"commands": commands, "files": sorted(files), "files_complete": complete,
            "versions": versions if full else None, "network": network if full else None,
            "host_available_memory_kib": memory if full else None, "workspace": workspace}


async def probe(env: Environment, workdir: str, *, full: bool, remaining_s: float,
                hosts: tuple[tuple[str, int], ...] = HOSTS,
                watched: tuple[str, ...] = ()) -> dict[str, Any]:
    if remaining_s < 2:
        return {"ok": False, "reason": "insufficient time"}
    try:
        result = await run(env, _script(workdir, full=full, hosts=hosts, watched=watched),
                           timeout_s=max(1, int(min(15, remaining_s - 1))))
        if result.code != 0:
            return {"ok": False, "reason": "probe command failed"}
        return {"ok": True, "facts": _parse(result.stdout, full=full, hosts=hosts, watched=watched)}
    except Exception as exc:  # timeouts and malformed output do not establish an environment fact
        return {"ok": False, "reason": type(exc).__name__}
