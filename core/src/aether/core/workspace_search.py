"""Bounded literal search of the current task workspace, on demand."""

import json
import posixpath
import shlex

from .env import run
from .facts_probe import SYSTEM_PYTHON_PATHS


TOOL = {"type": "function", "function": {
    "name": "search_workspace",
    "description": "Find a literal filename or UTF-8 text under the workspace or a chosen relative subdirectory. "
                   "Returns exact paths and lines with scan coverage. Narrow the scope when the result is partial.",
    "parameters": {"type": "object", "properties": {
        "mode": {"type": "string", "enum": ["filename", "text"]},
        "query": {"type": "string"},
        "subdir": {"type": "string", "description": "Relative directory, default is the task workspace."},
    }, "required": ["mode", "query"]},
}}


# Adapted from the replay lab's descriptor-scoped navigator. Open a pinned
# regular file only after checking its type, link count and mount identity.
_PROBE = r"""
import hashlib, json, os, stat, sys, time
from contextlib import contextmanager

root, subdir, mode, query, exclude = sys.argv[1:]
skip = {'.git', 'tests', 'test', 'solution', 'solutions', 'grader', 'verifier', 'node_modules', '__pycache__'}
matches, examined, bytes_read, omitted = [], 0, 0, 0
deadline = time.monotonic() + 1

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

def visible(name):
    return not name.startswith('.') and name.casefold() not in skip

def walk(fd, prefix, depth, root_mount):
    global examined, bytes_read, omitted
    with os.scandir(fd) as entries:
        for entry in entries:
            if examined >= 256 or len(matches) >= 12 or time.monotonic() >= deadline:
                omitted += 1
                return
            examined += 1
            path = os.path.join(prefix, entry.name)
            if not visible(entry.name) or os.path.join(root, path) == exclude:
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
                    matches.append({'path': path, 'kind': 'directory' if is_dir else 'file'})
                if is_dir:
                    if depth == 5:
                        omitted += 1
                        continue
                    directory_fd = os.open(f'/proc/self/fd/{child}', os.O_RDONLY | os.O_DIRECTORY)
                    try:
                        walk(directory_fd, path, depth + 1, root_mount)
                    finally:
                        os.close(directory_fd)
                    continue
                if mode != 'text':
                    continue
                if info.st_nlink != 1 or info.st_size > 32768 or bytes_read + info.st_size > 196608:
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
                    offset = line.find(query)
                    if offset < 0:
                        continue
                    if len(matches) >= 12:
                        omitted += 1
                        break
                    digest = digest or hashlib.sha256(raw).hexdigest()
                    matches.append({'path': path, 'line': line_no, 'column': offset + 1, 'sha256': digest})
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
              'examined': examined, 'skipped_or_limited': omitted, 'bytes_read': bytes_read}
except (ValueError, OSError, StopIteration, AttributeError):
    result = {'status': 'scope_unavailable'}
print(json.dumps(result, ensure_ascii=True, separators=(',', ':')))
"""


async def search(env, workdir, control_dir, args):
    mode, query, subdir = args["mode"], args["query"], args.get("subdir", "")
    if (mode not in ("filename", "text") or not 1 <= len(query) <= 160 or "\0" in query
            or "\n" in query or "\0" in subdir or len(subdir) > 256 or (subdir and any(
                not part or part.startswith(".") or part.casefold() in
                ("test", "tests", "solution", "solutions", "grader", "verifier", "node_modules", "__pycache__")
                for part in subdir.split("/")
            ))):
        raise ValueError("search requires a literal query and a visible workspace-relative directory")
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
    result = await run(env, f'for p in {choices}; do [ -x "$p" ] && exec "$p" {launch}; done; exit 127', timeout_s=4)
    if result.code != 0 or len(result.stdout) > 26000:
        return '{"status":"search_unavailable","fallback":"Use terminal or read_file in the task workspace."}'
    return json.dumps(json.loads(result.stdout), ensure_ascii=True, separators=(",", ":"))
