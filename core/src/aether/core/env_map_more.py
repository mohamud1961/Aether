"""More start facts for the environment map (same switch, AETHER_CORE_ENV_MAP=on): plan part 3, rows D4, D5, D7, D9.

Each is a measured fact the model would otherwise spend early calls finding, stated without interpretation:

- Submodules and hooks per repository (D4): declared submodules and how many are initialized, active hooks and a
  configured ``core.hooksPath``. A commit can run a hook; a submodule's files are not in the parent's history.
- Data files in the workspace (D5): kind and size; a CSV/TSV first line; for SQLite, the ``-wal``/``-shm`` files
  beside it and its tables. The tables are read from a copy in a temporary directory, so the original database is
  never opened: opening it read-write checkpoints and deletes the WAL (the db-wal study, 10 Nov), and read-only
  opening can still create ``-shm``.
- Absolute paths written in the task text (D7): exists or not, and kind. Only literal ``/...`` tokens; nothing is
  inferred from the wording.
- Display and Python browser drivers (D9): whether a display is set or an X socket exists, and whether ``playwright``
  or ``selenium`` is installed (found by module spec, not imported). Browser commands are already in the managed facts.

Bounded (12 data files, 64 MB copied in all, 12 task paths, one exec with a 30 s limit) and read-only outside the
temporary copy, which is removed.
"""

from __future__ import annotations

import re
import shlex

from .env import Environment, run

MAX_DATA, MAX_PATHS, COPY_LIMIT = 12, 12, 64 * 1024 * 1024
_TASK_PATH = re.compile(r"(?<![\w.:/~$-])/(?:[A-Za-z0-9_.+@-]+/)*[A-Za-z0-9_.+@-]*")
_SENSITIVE = r"secret|password|passwd|token|credential|private|id_rsa|id_ed25519"

_SCRIPT = r"""
wd=$(cd "$1" && pwd -P) || exit 1; shift
export LC_ALL=C GIT_CONFIG_NOSYSTEM=1
T=""; command -v timeout >/dev/null 2>&1 && T="timeout 10"
find -P "$wd" -xdev -mindepth 1 -maxdepth 3 \( -name .git -type d -print -prune -o -name '.*' -type d -prune \) 2>/dev/null | head -n 4 | sed 's#/\.git$##' | while IFS= read -r r; do
  [ -L "$r/.git" ] && continue
  sub=0; [ -f "$r/.gitmodules" ] && sub=$(grep -c '^[[:space:]]*path[[:space:]]*=' "$r/.gitmodules" 2>/dev/null)
  init=0; [ -d "$r/.git/modules" ] && init=$(find "$r/.git/modules" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l | tr -d ' ')
  hooks=$(find "$r/.git/hooks" -mindepth 1 -maxdepth 1 -type f -perm -u+x ! -name '*.sample' 2>/dev/null | sed 's#.*/##' | head -n 8 | tr '\n' ' ')
  hp=$(git config --file "$r/.git/config" --get core.hooksPath 2>/dev/null | head -c 160)
  printf 'G\t%s\t%s\t%s\t%s\t%s\n' "$r" "$sub" "$init" "$hooks" "$hp"
done
budget={copy_limit}
find -P "$wd" -xdev -mindepth 1 -maxdepth 3 \( -name '.*' -type d -prune -o -type f \( -iname '*.csv' -o -iname '*.tsv' -o -iname '*.parquet' -o -iname '*.db' -o -iname '*.sqlite' -o -iname '*.sqlite3' -o -iname '*.json' -o -iname '*.jsonl' -o -iname '*.xlsx' \) -print \) 2>/dev/null | grep -Eiv '{sensitive}' | sort | head -n {max_data} | while IFS= read -r f; do
  size=$(wc -c < "$f" 2>/dev/null | tr -d ' ')
  rel=${f#"$wd"/}
  if [ "$(head -c 15 "$f" 2>/dev/null)" = "SQLite format 3" ]; then
    side=""; for s in -wal -shm -journal; do [ -e "$f$s" ] && side="$side $s=$(wc -c < "$f$s" | tr -d ' ')"; done
    tables="(not read)"; need=$size; [ -e "$f-wal" ] && need=$((need + $(wc -c < "$f-wal")))
    if command -v python3 >/dev/null 2>&1 && [ "$need" -le "$budget" ]; then
      t=$(mktemp -d) && cp "$f" "$t/db" && { [ ! -e "$f-wal" ] || cp "$f-wal" "$t/db-wal"; } &&
        tables=$(cd / && $T python3 -c 'import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); r=[n for n, k in c.execute("select name, type from sqlite_master order by name") if k == "table"]; print((" ".join(r[:12]) + (" (+%d more)" % (len(r) - 12) if len(r) > 12 else "")) or "none")' "$t/db" 2>&1 | head -c 300 | tr '\n' ' ')
      rm -rf "$t"; budget=$((budget - need))
    fi
    printf 'D\t%s\tsqlite\t%s\t%s\t%s\n' "$rel" "$size" "$side" "$tables"
  else
    first=""; case "$f" in *.[cC][sS][vV]|*.[tT][sS][vV]) first=$(head -n 1 "$f" 2>/dev/null | head -c 160 | tr '\t\r' '  ');; esac
    printf 'D\t%s\tfile\t%s\t\t%s\n' "$rel" "$size" "$first"
  fi
done
for p in "$@"; do
  if [ -L "$p" ]; then k="symlink to $(readlink "$p" | head -c 120)"
  elif [ -d "$p" ]; then k="directory"
  elif [ -f "$p" ]; then k="file, $(wc -c < "$p" 2>/dev/null | tr -d ' ') bytes"
  elif [ -e "$p" ]; then k="exists (not a regular file or directory)"
  else k="does not exist"; fi
  printf 'P\t%s\t%s\n' "$p" "$k"
done
x=$(ls /tmp/.X11-unix 2>/dev/null | head -n 4 | tr '\n' ' ')
mods=""; command -v python3 >/dev/null 2>&1 && mods=$(cd / && $T python3 -c 'import importlib.util as u; print(" ".join(m for m in ("playwright", "selenium") if u.find_spec(m)))' 2>/dev/null)
printf 'X\t%s\t%s\t%s\t%s\n' "${DISPLAY:-}" "${WAYLAND_DISPLAY:-}" "$x" "$mods"
printf 'done\n'
"""


def task_paths(task: str) -> list[str]:
    """Literal absolute paths written in the task, in order, without trailing punctuation."""
    found: list[str] = []
    for match in _TASK_PATH.finditer(task or ""):
        path = match.group(0).rstrip(".")
        if len(path) > 1 and len(path) <= 200 and path not in found:
            found.append(path)
    return found[:MAX_PATHS]


def parse(stdout: str) -> tuple[list[str], dict]:
    lines: list[str] = []
    data, paths, row = [], [], {"repos_with_extras": 0, "data_files": 0, "task_paths": 0, "display": False}
    for line in stdout.splitlines():
        f = line.split("\t")
        if f[0] == "G" and len(f) == 6:
            sub, init, hooks, hooks_path = f[2] or "0", f[3] or "0", f[4].split(), f[5].strip()
            parts = []
            if sub != "0":
                parts.append(f"submodules declared {sub} (initialized {init})")
            if hooks:
                parts.append("active hooks: " + " ".join(hooks))
            if hooks_path:
                parts.append(f"core.hooksPath {hooks_path}")
            if parts:
                row["repos_with_extras"] += 1
                lines.append(f"- git repository {f[1]}: " + "; ".join(parts))
        elif f[0] == "D" and len(f) == 6:
            name, kind, size, side, extra = f[1], f[2], f[3], f[4].split(), f[5].strip()
            if kind == "sqlite":
                beside = f"; beside it: {', '.join(s.replace('=', ' ') + ' bytes' for s in side)}" if side else ""
                tables = ("tables not read: no python3, or over the copy limit" if extra == "(not read)"
                          else f"tables, read from a copy: {extra or 'none'}")
                data.append(f"{name} (SQLite, {size} bytes{beside}; {tables})")
            else:
                data.append(f"{name} ({size} bytes" + (f"; first line: {extra}" if extra else "") + ")")
        elif f[0] == "P" and len(f) == 3:
            paths.append(f"{f[1]} {f[2]}")
        elif f[0] == "X" and len(f) == 5:
            display = ", ".join(x for x in (f[1] and f"DISPLAY={f[1]}", f[2] and f"WAYLAND_DISPLAY={f[2]}",
                                           f[3].strip() and f"X sockets {f[3].strip()}") if x) or "none set"
            row["display"] = display != "none set"
            lines.append(f"- display: {display}; Python browser drivers: {f[4].strip() or 'none found'}")
    if data:
        lines.append("- data files: " + "; ".join(data))
    if paths:
        lines.append("- absolute paths written in the task: " + "; ".join(paths))
    row["data_files"], row["task_paths"] = len(data), len(paths)
    return lines, row


async def take(env: Environment, workdir: str, task: str) -> tuple[list[str], dict]:
    """Note lines (none when the probe fails) and trace fields."""
    script = (_SCRIPT.replace("{copy_limit}", str(COPY_LIMIT)).replace("{max_data}", str(MAX_DATA))
              .replace("{sensitive}", _SENSITIVE))
    args = " ".join(shlex.quote(p) for p in task_paths(task))
    try:
        result = await run(env, f"sh -c {shlex.quote(script)} core-env-more {shlex.quote(workdir)} {args}",
                           timeout_s=30)
    except Exception as exc:  # an instrument: no note, no claim
        return [], {"more_ok": False, "more_reason": f"{type(exc).__name__}: {exc}"[:300]}
    if result.code != 0 or not result.stdout.rstrip().endswith("done"):
        return [], {"more_ok": False, "more_reason": (result.stderr or f"exit {result.code}")[:300]}
    lines, row = parse(result.stdout)
    return lines, {"more_ok": True, **row}
