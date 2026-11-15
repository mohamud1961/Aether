"""State witness outside the workspace (A21; AETHER_CORE_OUTSIDE_WITNESS, default off).

The start copy keeps the working directory as it was before the first action. Changes outside it (a service's
config under /etc, a file the model writes by absolute path) had no record of their original. This adds two:

- at the start, a copy of each configured root (default /etc) under the control directory, bounded in size;
- at the first write by Core's own file tools to a path outside the workdir and those roots, a copy of that file's
  original (or the fact that it did not exist).

Facts only: the task message names where the root copy is, and the first file-tool write names where the original
is kept. Core never uses the copies.

Research gate (a21_outside_writes.py, 15 Nov, 793 graded Core traces, 81 tasks): literal writes outside the
workspace appear in 8 tasks, almost all the task's own required system config (sshd_config, mailman.cfg, nginx,
/git, /var/www), and do not separate passing from failing runs of the same task. No trace showed a lost outside
original. The model writes through the shell about 8 to 1 (F7), which the per-file capture cannot see before the
write; the root copy covers /etc for that path. Built small and off, as the plan requires; not promoted.
"""

from __future__ import annotations

import posixpath
import shlex

from .env import Environment, run

OUTSIDE_WITNESS_ENV = "AETHER_CORE_OUTSIDE_WITNESS"
ROOTS = ("/etc",)
ROOT_LIMIT_BYTES = 64 * 1024 * 1024
FILE_LIMIT_BYTES = 16 * 1024 * 1024
SCRATCH = ("/tmp", "/dev", "/proc", "/sys", "/run", "/var/tmp")
ROOT_NOTE = "(A copy of {roots} as it was before your first action is at {copy}. The harness made it and does not use it.)"
KEPT = "[the original of {path}, before this run first changed it, is kept at {copy}]"
ABSENT = "[{path} did not exist before this run first wrote it]"


def _under(path: str, root: str) -> bool:
    return path == root or path.startswith(root.rstrip("/") + "/")


async def take(env: Environment, workdir: str, control_dir: str, roots: tuple[str, ...] = ROOTS) -> tuple[str, dict]:
    """Copy each root under ``control_dir/outside``; the note for the task message ('' when nothing was copied)."""
    base, q = posixpath.join(control_dir, "outside"), shlex.quote
    copied, rows = [], []
    for root in roots:
        if _under(workdir, root) or _under(root, workdir):
            rows.append({"root": root, "copied": False, "reason": "overlaps the workdir"})
            continue
        dest = base + root
        script = (f"[ -d {q(root)} ] || {{ echo missing; exit 3; }}; k=$(du -sk {q(root)} 2>/dev/null | cut -f1); "
                  f"[ -n \"$k\" ] || {{ echo unmeasured; exit 3; }}; [ $((k*1024)) -le {ROOT_LIMIT_BYTES} ] || "
                  f"{{ echo too_large $k; exit 4; }}; mkdir -p {q(posixpath.dirname(dest))} && "
                  f"cp -a {q(root)} {q(dest)} 2>/dev/null; [ -d {q(dest)} ] && echo ok $k")
        try:
            result = await run(env, script, timeout_s=120)
        except Exception as exc:  # an instrument: no copy, no note
            rows.append({"root": root, "copied": False, "reason": f"{type(exc).__name__}: {exc}"[:200]})
            continue
        words = result.stdout.split()
        if words[:1] == ["ok"]:
            copied.append(root)
            rows.append({"root": root, "copied": True, "kib": int(words[1])})
        else:
            rows.append({"root": root, "copied": False, "reason": result.stdout.strip()[:200], "exit": result.code})
    if not copied:
        return "", {"roots": rows}
    return ROOT_NOTE.format(roots=" and ".join(copied), copy=base + (copied[0] if len(copied) == 1 else "")), {
        "roots": rows, "path": base}


class Witness:
    """First-write capture for Core's file tools outside the workdir, the copied roots and scratch paths."""

    def __init__(self, env: Environment, workdir: str, control_dir: str, roots: tuple[str, ...] = ROOTS) -> None:
        self.env, self.workdir, self.control_dir, self.roots = env, workdir.rstrip("/") or "/", control_dir, roots
        self.base = posixpath.join(control_dir, "witness")
        self.seen: dict[str, str] = {}  # path -> kept | absent | skipped | unreadable

    def applies(self, path: str) -> bool:
        if not path.startswith("/"):
            return False  # file tools resolve relative paths inside the workdir
        path = posixpath.normpath(path)
        excluded = (self.workdir, self.control_dir, *self.roots, *SCRATCH)
        return path not in self.seen and not any(_under(path, root) for root in excluded)

    async def before_write(self, path: str) -> str:
        """Keep the original of ``path`` at its first write; the line to add to the tool result ('' if none)."""
        if not self.applies(path):
            return ""
        path, q = posixpath.normpath(path), shlex.quote
        dest = self.base + path
        script = (f"if [ -f {q(path)} ] && [ ! -L {q(path)} ]; then "
                  f"[ $(wc -c < {q(path)}) -le {FILE_LIMIT_BYTES} ] || {{ echo skipped; exit 0; }}; "
                  f"mkdir -p {q(posixpath.dirname(dest))} && cp -p {q(path)} {q(dest)} && echo kept; "
                  f"elif [ -e {q(path)} ] || [ -L {q(path)} ]; then echo skipped; else echo absent; fi")
        try:
            result = await run(self.env, script, timeout_s=30)
            state = result.stdout.strip() if result.code == 0 else "unreadable"
        except Exception:  # an instrument: the write goes ahead without a witness
            state = "unreadable"
        self.seen[path] = state if state in ("kept", "absent", "skipped") else "unreadable"
        if self.seen[path] == "kept":
            return KEPT.format(path=path, copy=dest)
        if self.seen[path] == "absent":
            return ABSENT.format(path=path)
        return ""
