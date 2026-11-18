"""Rehydration after the context is shortened (switch AETHER_CORE_REHYDRATE=on; E18 candidate K2, row E5).

After a checkpoint (or a provider compaction item) the model keeps a summary of its own earlier work. The files it
changed are shown again as they are now, read from the sandbox at that moment. A summary's memory of a file is
replaced by its current bytes, as Claude Code re-reads recently modified files after compaction.

Only facts: each file's path, size and current contents (bounded), read now. Nothing is inferred about the task.
Files the run wrote last come first; binary files and files that no longer exist are named, not shown.
"""

from __future__ import annotations

import shlex

from .env import Environment, run

MAX_FILES, MAX_CHARS = 5, 6_000
HEADER = "[after the context was shortened: files this run changed, read again now]"


async def note(env: Environment, written: list[str], max_files: int = MAX_FILES,
               max_chars: int = MAX_CHARS) -> tuple[str, dict]:
    """The note (empty when there is nothing to show) and trace fields."""
    paths = list(dict.fromkeys(reversed(written)))[:max_files]
    if not paths:
        return "", {"files": 0}
    parts, shown, missing = [HEADER], 0, 0
    for path in paths:
        q = shlex.quote(path)
        script = (f"if [ -f {q} ]; then printf 'size=%s\\n' \"$(wc -c < {q} | tr -d ' ')\"; "
                  f"a=$(head -c 65536 {q} | wc -c); b=$(head -c 65536 {q} | tr -d '\\000' | wc -c); "
                  f"if [ \"$a\" = \"$b\" ]; then head -c {max_chars + 1} {q}; else printf '\\001binary'; fi; "
                  f"else printf 'missing\\n'; fi")
        try:
            result = await run(env, f"sh -c {shlex.quote(script)}", timeout_s=10)
        except Exception as exc:  # an instrument: say it could not be read, never guess
            parts.append(f"--- {path}: could not be read ({type(exc).__name__})")
            continue
        out = result.stdout
        if out.startswith("missing"):
            parts.append(f"--- {path}: no longer exists")
            missing += 1
            continue
        first, _, body = out.partition("\n")
        size = first.removeprefix("size=")
        if body.startswith("\x01binary"):
            parts.append(f"--- {path} ({size} bytes, binary; not shown)")
            continue
        cut = len(body) > max_chars
        body = body[:max_chars]
        parts.append(f"--- {path} ({size} bytes{'; first ' + str(max_chars) + ' characters' if cut else ''})\n{body}")
        shown += 1
    return "\n".join(parts), {"files": len(paths), "shown": shown, "missing": missing}
