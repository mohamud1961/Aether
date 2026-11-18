"""A small, measured orientation note for a task's initial working directory."""

import json
import posixpath
import shlex

from .env import run


async def observe(env, workdir, trace):
    if workdir == "/" or not workdir.startswith("/") or posixpath.normpath(workdir) != workdir:
        return ""
    command = r"""
set -eu
[ "$(pwd -P)" = "$1" ]
identity=$(stat -Lc '%d:%i' -- .)
count=0
for entry in ./*; do
    [ -e "$entry" ] || [ -L "$entry" ] || continue
    [ "$count" -lt 16 ] || break
    if [ -L "$entry" ]; then kind=link
    elif [ -d "$entry" ]; then kind=dir
    elif [ -f "$entry" ]; then kind=file
    else kind=other
    fi
    printf '%s\000%s\000' "${entry#./}" "$kind"
    count=$((count+1))
done
[ "$(stat -Lc '%d:%i' -- "$1")" = "$identity" ]
printf 'observed\000'
"""
    try:
        result = await run(env, f"sh -c {shlex.quote(command)} core-workspace {shlex.quote(workdir)}",
                           cwd=workdir, timeout_s=3)
    except (OSError, RuntimeError, TimeoutError):
        return ""
    fields = result.stdout.split("\0")
    if result.code != 0 or fields[-2:] != ["observed", ""] or (len(fields)-2) % 2:
        return ""
    suffix = {"dir": "/", "link": "@"}
    entries = [name + suffix.get(kind, "") for name, kind in zip(fields[:-2:2], fields[1:-2:2])]
    if not entries:
        return ""
    selected = []
    for entry in entries:
        if len(json.dumps([*selected, entry], ensure_ascii=True)) > 600:
            break
        selected.append(entry)
    if not selected:
        return ""
    trace("workspace_brief", root=workdir, shown=len(selected), bound=16,
          partial=len(selected) < len(entries) or len(entries) == 16)
    return "[Core observation: initial top-level workspace sample] " + json.dumps(selected, ensure_ascii=True)
