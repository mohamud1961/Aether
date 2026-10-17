"""Field-aware view of delimited files a call changed (``AETHER_CORE_VIEW=on``; off is the baseline).

After each ``terminal``, ``python``, ``write_file`` or ``edit_file`` call, the ``*.csv`` / ``*.tsv`` files under the
working directory (depth <= 2) whose content changed since the previous listing are shown under the call's result,
each row as its literal named fields::

    [view] /app/out.csv: CSV with header fields (to, from), 2 rows
    row 1: to=B, from=A
    row 2: to=C, from=B

No instruction, no verdict and no interpretation: only what the header says each value is. A listing or read that
fails is traced and shows nothing (the call's own result is never changed by a view failure). The first listing is
taken just before the first such call, so files present before the run are never shown unless they change.
"""

from __future__ import annotations

import csv
import io
import shlex
from typing import Any, Callable

from .env import Environment, run

VIEW_TOOLS = frozenset({"terminal", "python", "write_file", "edit_file"})
MAX_FILES, MAX_ROWS, MAX_VALUE, MAX_DEPTH = 3, 20, 40, 2


def _short(value: str) -> str:
    return value if len(value) <= MAX_VALUE else value[: MAX_VALUE - 3] + "..."


def render(path: str, text: str, total_rows: int) -> str:
    """The view of one file: ``text`` holds its first lines; ``total_rows`` counts its data rows (header excluded)."""
    kind = "TSV" if path.endswith(".tsv") else "CSV"
    lines = list(csv.reader(io.StringIO(text), delimiter="\t" if kind == "TSV" else ","))
    if not lines:
        return f"[view] {path}: empty"
    header = [_short(h) for h in lines[0]]
    out = [f"[view] {path}: {kind} with header fields ({', '.join(header)}), {total_rows} rows"]
    for i, row in enumerate(lines[1 : MAX_ROWS + 1], 1):
        names = header + [f"field{k}" for k in range(len(header) + 1, len(row) + 1)]
        out.append(f"row {i}: " + ", ".join(f"{n}={_short(v)}" for n, v in zip(names, row)))
    if total_rows > MAX_ROWS:
        out.append(f"... {total_rows - MAX_ROWS} more rows")
    return "\n".join(out)


class View:
    def __init__(self, env: Environment, workdir: str, trace: Callable[..., Any]) -> None:
        self._env, self._workdir, self._trace = env, workdir, trace
        self._seen: dict[str, str] | None = None
        self.shown = 0  # files rendered over the run, for the run record

    async def _list(self) -> dict[str, str]:
        res = await run(
            self._env,
            f"find {shlex.quote(self._workdir)} -maxdepth {MAX_DEPTH} -type f "
            r"\( -name '*.csv' -o -name '*.tsv' \) -exec cksum {} + 2>/dev/null; true",
            timeout_s=20,
        )
        if res.code != 0:
            raise OSError(f"listing failed: {res.stderr.strip()[:200]}")
        listing = {}
        for line in res.stdout.splitlines():
            crc, size, path = line.split(" ", 2)
            listing[path] = f"{crc} {size}"
        return listing

    async def before(self) -> None:
        if self._seen is None:
            try:
                self._seen = await self._list()
            except Exception as exc:  # substrate failure: traced; the next call retries the first listing
                self._trace("view_error", stage="before", error=f"{type(exc).__name__}: {exc}")

    async def after(self) -> str:
        """The views of the files changed since the last listing, as text to append to the result ('' if none)."""
        if self._seen is None:
            return ""
        try:
            now = await self._list()
            changed = sorted(p for p, sig in now.items() if self._seen.get(p) != sig)
            self._seen = now
            views = []
            for path in changed[:MAX_FILES]:
                q = shlex.quote(path)
                res = await run(
                    self._env, f"head -n {MAX_ROWS + 1} {q}; printf '\\0'; awk 'END{{print NR}}' {q}", timeout_s=20
                )
                text, _, count = res.stdout.partition("\0")
                if res.code != 0 or not count.strip().isdigit():
                    raise OSError(f"reading {path} failed: {res.stderr.strip()[:200]}")
                views.append(render(path, text, max(0, int(count) - 1)))
            if len(changed) > MAX_FILES:
                views.append(f"[view] {len(changed) - MAX_FILES} more changed delimited files not shown")
        except Exception as exc:  # substrate failure: traced, nothing shown
            self._trace("view_error", stage="after", error=f"{type(exc).__name__}: {exc}")
            return ""
        self.shown += min(len(changed), MAX_FILES)
        return "\n\n" + "\n\n".join(views) if views else ""
