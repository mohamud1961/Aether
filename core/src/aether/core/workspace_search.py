"""Bounded search of the current task workspace, on demand (AETHER_CORE_WORKSPACE_SEARCH=on).

Returns what a ripgrep-backed agent tool returns: each matching line with its path, line and column, the totals in
the scanned scope, and whether the scan covered all of it. The walk is the replay lab's descriptor-scoped navigator:
it never follows a symbolic link, never leaves the workspace's mount, never opens a FIFO or device, and records each
matched file's sha256 so a later read can be tied to the version searched. It skips version-control and dependency
caches only (``.git``, ``node_modules``, virtualenvs, bytecode caches) and hidden directories unless asked for one.
An earlier version also skipped ``tests``, ``solution``, ``grader`` and ``verifier``: that hid ordinary project code and
was benchmark framing, so it is gone.
"""

import json
import posixpath
import re
import shlex

from .env import run
from .facts_probe import SYSTEM_PYTHON_PATHS


TOOL = {"type": "function", "function": {
    "name": "search_workspace",
    "description": "Search file names or file contents under the workspace or a relative subdirectory. mode filename: "
                   "names containing query; text: lines containing query literally; regex: lines matching a Python "
                   "regular expression. Returns matching lines with path, line and column, totals, and whether the "
                   "whole scope was scanned. Skips .git, node_modules, virtualenvs and hidden directories.",
    "parameters": {"type": "object", "properties": {
        "mode": {"type": "string", "enum": ["filename", "text", "regex"]},
        "query": {"type": "string"},
        "subdir": {"type": "string", "description": "Relative directory, default is the task workspace."},
    }, "required": ["mode", "query"]},
}}


# Adapted from the replay lab's descriptor-scoped navigator. Open a pinned
# regular file only after checking its type, link count and mount identity.
_PROBE = r"""
import hashlib, json, os, re, stat, sys, time
from contextlib import contextmanager

root, subdir, mode, query, exclude = sys.argv[1:]
skip = {'.git', '.hg', '.svn', 'node_modules', '__pycache__', '.venv', 'venv', '.tox', '.mypy_cache', '.pytest_cache'}
MAX_ENTRIES, MAX_SHOWN, MAX_FILE, MAX_BYTES, LINE = 50000, 40, 2_000_000, 32_000_000, 240
pattern = re.compile(query) if mode == 'regex' else None
matches, examined, bytes_read, omitted, total, files_matched = [], 0, 0, 0, 0, 0
deadline = time.monotonic() + 3

def mount(fd):
    with open(f'/proc/self/fdinfo/{fd}', encoding='ascii') as f:
        return next(line.split()[1] for line in f if line.startswith('mnt_id:'))

def version(s):
    return s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_nlink

@contextmanager
def directory(path):
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    fd = os.open('/', flags)
    try:
        for part in path.split('/')[1:]:
            child = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = child
        yield fd
    finally:
        os.close(fd)

def visible(name, is_dir):
    return name not in skip and not (is_dir and name.startswith('.'))

def find(line):
    if pattern is not None:
        m = pattern.search(line)
        return m.start() if m else -1
    return line.find(query)

def walk(fd, prefix, depth, root_mount):
    global examined, bytes_read, omitted, total, files_matched
    with os.scandir(fd) as entries:
        for entry in sorted(entries, key=lambda e: e.name):
            if examined >= MAX_ENTRIES or time.monotonic() >= deadline:
                omitted += 1
                return
            examined += 1
            path = os.path.join(prefix, entry.name)
            try:
                is_dir_hint = entry.is_dir(follow_symlinks=False)
            except OSError:
                is_dir_hint = False
            if not visible(entry.name, is_dir_hint) or os.path.join(root, path) == exclude:
                continue
            child = None
            try:
                child = os.open(entry.name, os.O_PATH | os.O_NOFOLLOW, dir_fd=fd)
                info = os.fstat(child)
                is_dir = stat.S_ISDIR(info.st_mode)
                is_file = stat.S_ISREG(info.st_mode)
                if mount(child) != root_mount or len(path) > 256 or not (is_dir or is_file):
                    omitted += 1
                    continue
                if mode == 'filename' and query in entry.name:
                    total += 1
                    if len(matches) < MAX_SHOWN:
                        matches.append({'path': path, 'kind': 'directory' if is_dir else 'file'})
                if is_dir:
                    if depth == 24:
                        omitted += 1
                        continue
                    directory_fd = os.open(f'/proc/self/fd/{child}', os.O_RDONLY | os.O_DIRECTORY)
                    try:
                        walk(directory_fd, path, depth + 1, root_mount)
                    finally:
                        os.close(directory_fd)
                    continue
                if mode == 'filename':
                    continue
                if info.st_nlink != 1 or info.st_size > MAX_FILE or bytes_read + info.st_size > MAX_BYTES:
                    omitted += 1
                    continue
                with open(f'/proc/self/fd/{child}', 'rb') as stream:
                    raw = stream.read(info.st_size + 1)
                    bytes_read += len(raw)
                    if len(raw) != info.st_size or version(os.fstat(stream.fileno())) != version(info) or b'\0' in raw:
                        omitted += 1
                        continue
                digest = None
                for line_no, line in enumerate(raw.decode('utf-8').split('\n'), 1):
                    offset = find(line)
                    if offset < 0:
                        continue
                    total += 1
                    if digest is None:
                        files_matched += 1
                        digest = hashlib.sha256(raw).hexdigest()
                    if len(matches) < MAX_SHOWN:
                        start = max(0, min(offset - LINE // 3, len(line) - LINE))
                        matches.append({'path': path, 'line': line_no, 'column': offset + 1, 'sha256': digest,
                                        'text': line[start:start + LINE]})
            except (OSError, UnicodeDecodeError, StopIteration):
                omitted += 1
            finally:
                if child is not None:
                    os.close(child)

def identity(fd):
    s = os.fstat(fd)
    return s.st_dev, s.st_ino, mount(fd)

try:
    target = os.path.join(root, subdir) if subdir else root
    with directory(root) as base, directory(target) as fd:
        owner, start = identity(base), identity(fd)
        if owner[2] != start[2]:
            raise ValueError('subdirectory is on a different mount')
        walk(fd, subdir, 0, owner[2])
        with directory(root) as current, directory(target) as check:
            if identity(current) != owner or identity(check) != start:
                raise ValueError('directory was replaced during search')
    result = {'status': 'partial' if omitted else 'searched', 'subdir': subdir, 'matches': matches,
              'matches_total': total, 'files_matched': files_matched, 'shown': len(matches),
              'examined': examined, 'skipped_or_limited': omitted, 'bytes_read': bytes_read}
except (ValueError, OSError, StopIteration, AttributeError):
    result = {'status': 'scope_unavailable'}
print(json.dumps(result, ensure_ascii=True, separators=(',', ':')))
"""


async def search(env, workdir, control_dir, args):
    mode, query, subdir = args["mode"], args["query"], args.get("subdir", "")
    if (mode not in ("filename", "text", "regex") or not 1 <= len(query) <= 160 or "\0" in query
            or "\n" in query or "\0" in subdir or len(subdir) > 256 or subdir.startswith("/")
            or (subdir and any(part in ("", ".", "..") for part in subdir.rstrip("/").split("/")))):
        raise ValueError("search requires a query and a workspace-relative directory")
    if mode == "regex":
        try:
            re.compile(query)
        except re.error as exc:
            raise ValueError(f"invalid regular expression: {exc}") from None
    if workdir == "/" or workdir.startswith("//") or not workdir.startswith("/") or posixpath.normpath(workdir) != workdir:
        return '{"status":"scope_unavailable"}'
    excluded = posixpath.normpath(posixpath.join(workdir, control_dir))
    target = posixpath.join(workdir, subdir).rstrip("/")
    if target == excluded or target.startswith(excluded + "/"):
        return '{"status":"scope_unavailable"}'
    choices = " ".join(p for p in SYSTEM_PYTHON_PATHS if not p.startswith(workdir + "/"))
    if not choices:
        return '{"status":"search_unavailable"}'
    launch = shlex.join(["-I", "-S", "-c", _PROBE, workdir, subdir, mode, query, excluded])
    result = await run(env, f'for p in {choices}; do [ -x "$p" ] && exec "$p" {launch}; done; exit 127', timeout_s=8)
    if result.code != 0 or len(result.stdout) > 60000:
        return '{"status":"search_unavailable","fallback":"Use terminal or read_file in the task workspace."}'
    return json.dumps(json.loads(result.stdout), ensure_ascii=True, separators=(",", ":"))
