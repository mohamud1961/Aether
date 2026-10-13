"""File tools: line-numbered reads, whole-file writes and exact-match edits.

Writes keep an existing file's permission bits. Relative paths resolve against
the task working directory.
"""
from __future__ import annotations

import posixpath
import shlex

from .env import Environment, get_bytes, put_bytes, run

MAX_READ_CHARS = 40_000
DEFAULT_LINES = 400


class Files:
    def __init__(self, env: Environment, workdir: str) -> None:
        self._env = env
        self._workdir = workdir
        self.written: dict[str, int] = {}  # path -> bytes, for the record and the reviewer

    def resolve(self, path: str) -> str:
        path = str(path).strip()
        if not path:
            raise ValueError("path is empty")
        return posixpath.normpath(path if path.startswith("/") else posixpath.join(self._workdir, path))

    async def _mode(self, path: str) -> str | None:
        q = shlex.quote(path)
        res = await run(self._env, f"stat -c %a {q} 2>/dev/null || stat -f %Lp {q} 2>/dev/null")
        mode = res.stdout.strip()
        return mode if res.code == 0 and mode.isdigit() else None

    async def read(self, path: str, start_line: int = 1, num_lines: int = DEFAULT_LINES) -> str:
        path = self.resolve(path)
        start = max(1, int(start_line))
        end = start + max(1, min(int(num_lines), 4000)) - 1
        q = shlex.quote(path)
        res = await run(self._env,
            f"if [ ! -f {q} ]; then echo 'not a regular file (or missing)' >&2; exit 2; fi; "
            f"if [ -s {q} ] && ! head -c 8192 {q} | grep -qI .; then echo BINARY; wc -c < {q}; exit 0; fi; "
            f"awk 'END {{print NR}}' {q}; awk 'NR>={start} && NR<={end} {{printf \"%6d  %s\\n\", NR, $0}}' {q}")
        if res.code != 0:
            raise FileNotFoundError(f"{path}: {(res.stderr or res.stdout).strip()[:200]}")
        if res.stdout.startswith("BINARY\n"):
            size = res.stdout.split()[1] if len(res.stdout.split()) > 1 else "?"
            return (f"[{path}: binary file, {size} bytes; not shown as text. Inspect it in the terminal "
                    f"(xxd, od, file, strings) or with the python tool]")
        total_s, _, body = res.stdout.partition("\n")
        total = int(total_s.strip() or 0)
        if len(body) > MAX_READ_CHARS:
            body = body[:MAX_READ_CHARS] + f"\n…[truncated at {MAX_READ_CHARS} chars; read fewer lines]"
        shown_end = min(end, total)
        more = f"; next: start_line={shown_end + 1}" if shown_end < total else ""
        return f"{body.rstrip()}\n[{path}: lines {start}-{shown_end} of {total}{more}]"

    async def write(self, path: str, content: str) -> str:
        path = self.resolve(path)
        mode = await self._mode(path)
        data = content.encode()
        await put_bytes(self._env, data, path)
        if mode:
            await run(self._env, f"chmod {mode} {shlex.quote(path)}")
        self.written[path] = len(data)
        lines = content.count("\n") + (0 if content.endswith("\n") or not content else 1)
        return f"wrote {len(data)} bytes ({lines} lines) to {path}" + ("" if mode else " (new file)")

    async def edit(self, path: str, old_str: str, new_str: str, replace_all: bool = False) -> str:
        path = self.resolve(path)
        if not old_str:
            raise ValueError("old_str is empty; use write_file to create or replace a whole file")
        try:
            text = (await get_bytes(self._env, path)).decode()
        except UnicodeDecodeError as exc:
            raise ValueError(f"{path} is not UTF-8 text") from exc
        count = text.count(old_str)
        if count == 0:
            raise ValueError(f"old_str not found in {path}; re-read the file and copy the exact text")
        if count > 1 and not replace_all:
            raise ValueError(f"old_str occurs {count} times in {path}; add context to make it unique "
                             f"or set replace_all=true")
        updated = text.replace(old_str, new_str) if replace_all else text.replace(old_str, new_str, 1)
        mode = await self._mode(path)
        await put_bytes(self._env, updated.encode(), path)
        if mode:
            await run(self._env, f"chmod {mode} {shlex.quote(path)}")
        self.written[path] = len(updated.encode())
        at = updated.find(new_str) if new_str else text.find(old_str)
        line = updated.count("\n", 0, max(0, at)) + 1
        lines = updated.split("\n")
        lo, hi = max(0, line - 4), min(len(lines), line + new_str.count("\n") + 3)
        snippet = "\n".join(f"{i + 1:6d}  {lines[i]}" for i in range(lo, hi))
        return f"edited {path} ({count if replace_all else 1} replacement{'s' if replace_all and count > 1 else ''})\n{snippet}"
