"""Core-owned state, verified, shown in a few tokens (AETHER_CORE_MANAGED_FACTS=v2; needs the start copy).

Why (state v2, 2 Nov; research/core_mission_20261028/state_v2/): the user's design is state management in every
task, an environment view that is refreshed when the environment changes and kept in one place in the model's
input, light on tokens, and accurate by verification rather than assumption. Earlier channels either pushed long
prose (Codex's managed facts: 1.35x request text) or waited to be pulled. This service records everything in the
trace and shows Luna two things:

- the environment block, in the pinned slot the loop already replaces in place: the env brief at the start, measured
  again only after a command that can change the environment (or every REFRESH_EVERY steps), and replaced only when
  a measured line differs; listening TCP ports are part of it;
- one line after every action: files added, removed and changed against the start copy, and whether the start
  commit is still in HEAD's history. Details stay one command away (state_view).

Accuracy: metadata (size, mtime, ctime, inode) finds candidates. ctime cannot be set by user tools, so restored mtimes
(touch -r, cp -p, tar) are still seen, and a file whose ctime is within a second of the previous scan is re-checked
(git's "racy" rule). Every candidate is compared byte for byte with the start copy, so a file changed and changed back
counts as unchanged. Every VERIFY_EVERY steps and at finish all files are compared with the start copy; any disagreement with the
incremental result is traced as a miss (and counted in the run record) and the full result replaces it. A count is
never shown that was not measured: an unmeasured scan says so.
"""

from __future__ import annotations

import posixpath
import re
import shlex
import time
from typing import Any, Callable

from . import env_brief
from .env import Environment, run
from .facts import _FULL_REFRESH
from .facts_workspace import InitialWorkspace

PREFIX = "[core facts]\n"
REFRESH_EVERY, VERIFY_EVERY, MAX_FILES = 10, 10, 20_000

# Listening TCP ports with the owning command; sockets of Core's own processes (cmdline naming .aether or aether) are
# left out: the P5 smoke showed a port opened by the run's own machinery, which is not a fact about the task.
_PORTS = r"""
for f in /proc/net/tcp /proc/net/tcp6; do [ -r "$f" ] && awk 'NR>1 && $4=="0A" {n=split($2,a,":"); print a[n], $10}' "$f"; done 2>/dev/null |
  sort -u | while read -r h ino; do
    pid=$(for d in /proc/[0-9]*; do ls -l "$d/fd" 2>/dev/null | grep -q "socket:\[$ino\]" && { echo "${d#/proc/}"; break; }; done)
    cmd=$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null)
    case "$cmd" in *aether*) continue ;; esac
    name=$(cat "/proc/$pid/comm" 2>/dev/null)
    printf '%d%s\n' "0x$h" "${name:+ ($name)}"
  done | sort -n -u | tr '\n' ',' | sed 's/,$//; s/,/, /g'
"""

# One step of the file and git account. Writes only under $S. Paths are relative to the workdir, one per line.
# Two-file awk joins test FILENAME==ARGV[1], not NR==FNR: an empty first file would make NR==FNR read the second as
# the first (found by the trace replay: a read-only step dropped three known changes).
_STEP = r"""
W={wd}; C={copy}; S={state}; MODE={mode}; MAX={max_files}
mkdir -p "$S" 2>/dev/null || {{ echo "F unmeasured"; exit 0; }}
for t in find stat awk; do command -v $t >/dev/null 2>&1 || {{ echo "F unmeasured (no $t)"; exit 0; }}; done
if [ ! -f "$S/fmt" ]; then
  if stat -c '%s' / >/dev/null 2>&1; then echo gnu > "$S/fmt"; else echo bsd > "$S/fmt"; fi
fi
scan() {{
  ( cd "$1" 2>/dev/null || exit 3
    if [ "$(cat "$S/fmt")" = gnu ]; then find . -path ./.git -prune -o ! -type d -exec stat -c '%n|%s|%Y|%Z|%i' {{}} +
    else find . -path ./.git -prune -o ! -type d -exec stat -f '%N|%z|%m|%c|%i' {{}} +; fi ) 2>/dev/null |
    awk '{{ sub(/^\.\//, ""); print }}' | sort
}}
now=$(date +%s)
scan "$W" > "$S/cur.tsv"; [ -d "$W" ] || {{ echo "F unmeasured (workdir missing)"; exit 0; }}
n=$(wc -l < "$S/cur.tsv" | tr -d ' ')
if [ "$n" -gt "$MAX" ]; then echo "F unmeasured (over $MAX files)"; rm -f "$S/prev.tsv"; exit 0; fi
cut -d'|' -f1 "$S/cur.tsv" > "$S/cur.paths"
if [ "$MODE" = start ]; then
  if [ -d "$C" ]; then scan "$C" | cut -d'|' -f1 > "$S/start.paths"; else : > "$S/start.paths"; echo nocopy > "$S/nocopy"; fi
  : > "$S/differs"; cp "$S/cur.tsv" "$S/prev.tsv"; echo "$now" > "$S/t_prev"
fi
[ -f "$S/nocopy" ] && {{ echo "F nocopy"; exit 0; }}
same() {{ if command -v cmp >/dev/null 2>&1; then cmp -s "$C/$1" "$W/$1"; else [ "$(cksum < "$C/$1")" = "$(cksum < "$W/$1")" ]; fi; }}
tp=$(cat "$S/t_prev" 2>/dev/null || echo 0)
if [ -f "$S/prev.tsv" ]; then
  awk -F'|' -v tp="$tp" 'FILENAME==ARGV[1] {{ p[$1]=$0; next }} !($1 in p) || p[$1]!=$0 || $4>=tp-1 {{ print $1 }}' "$S/prev.tsv" "$S/cur.tsv"
else cat "$S/cur.paths"; fi > "$S/cand"
: > "$S/upd"
awk 'FILENAME==ARGV[1] {{ s[$0]=1; next }} ($0 in s)' "$S/start.paths" "$S/cand" | while IFS= read -r p; do
  if same "$p"; then printf '%s\t0\n' "$p"; else printf '%s\t1\n' "$p"; fi; done > "$S/upd"
awk -F'\t' 'FILENAME==ARGV[1] {{ u[$1]=$2; next }} {{ if (!($0 in u)) print }} END {{ for (k in u) if (u[k]==1) print k }}' \
  "$S/upd" "$S/differs" | sort -u > "$S/differs.new"
awk 'FILENAME==ARGV[1] {{ c[$0]=1; next }} ($0 in c)' "$S/cur.paths" "$S/differs.new" > "$S/differs"
if [ "$MODE" = verify ]; then
  awk 'FILENAME==ARGV[1] {{ s[$0]=1; next }} ($0 in s)' "$S/start.paths" "$S/cur.paths" | while IFS= read -r p; do
    same "$p" || echo "$p"; done | sort > "$S/full"
  if [ "$(cat "$S/full")" != "$(cat "$S/differs")" ]; then
    echo "M $( (comm -3 "$S/full" "$S/differs" 2>/dev/null || true) | tr -d '\t' | head -5 | tr '\n' ' ')"
  fi
  cp "$S/full" "$S/differs"
fi
cp "$S/cur.tsv" "$S/prev.tsv"; echo "$now" > "$S/t_prev"
added=$(awk 'FILENAME==ARGV[1] {{ s[$0]=1; next }} !($0 in s)' "$S/start.paths" "$S/cur.paths" | wc -l | tr -d ' ')
removed=$(awk 'FILENAME==ARGV[1] {{ c[$0]=1; next }} !($0 in c)' "$S/cur.paths" "$S/start.paths" | wc -l | tr -d ' ')
echo "F +$added -$removed ~$(wc -l < "$S/differs" | tr -d ' ')"
if [ -d "$C/.git" ] && command -v git >/dev/null 2>&1; then
  g() {{ GIT_OPTIONAL_LOCKS=0 git -c safe.directory='*' -c core.fsmonitor=false "$@" 2>/dev/null; }}
  [ -f "$S/git_start" ] || g -C "$C" rev-parse HEAD > "$S/git_start"
  s0=$(cat "$S/git_start"); h=$(g -C "$W" rev-parse HEAD)
  if [ -z "$s0" ]; then echo "G nostart"
  elif [ -z "$h" ]; then echo "G nohead"
  elif [ "$s0" = "$h" ]; then echo "G same"
  elif g -C "$W" merge-base --is-ancestor "$s0" "$h"; then echo "G ahead $(g -C "$W" rev-list --count "$s0..$h")"
  else echo "G gone"; fi
fi
"""


def _copy_path(workdir: str, control_dir: str) -> str:
    return posixpath.join(control_dir, "start", posixpath.basename(workdir.rstrip("/")) or "root")  # as start_copy


def render_line(lines: list[str]) -> str:
    """The one line shown after an action, from the step script's output."""
    files = next((x[2:] for x in lines if x.startswith("F ")), "unmeasured")
    if files == "nocopy":
        text = "files: no start copy to compare with"
    elif files.startswith("unmeasured"):
        text = f"files vs start: {files}"
    else:
        a, r, c = files.split()
        text = f"files vs start: {a.lstrip('+')} added, {r.lstrip('-')} removed, {c.lstrip('~')} changed"
    git = next((x[2:].split() for x in lines if x.startswith("G ")), None)
    if git:
        text += {"same": " · git: HEAD is the start commit",
                 "ahead": f" · git: {git[-1]} new commit(s) on the start commit",
                 "gone": " · git: the start commit is not in HEAD's history",
                 "nohead": " · git: no readable HEAD",
                 "nostart": " · git: start commit unknown"}[git[0]]
    return "[state] " + text


def _env_lines(text: str) -> dict[str, str]:
    return {re.sub(r"\s*\(.*", "", line.split(":", 1)[0]): line for line in text.splitlines()
            if ":" in line and not line.startswith("  ")}


def env_change(old: str, new: str) -> str:
    """A short account of what differs between two environment blocks ('' when nothing does)."""
    before, after = _env_lines(old), _env_lines(new)
    if before == after:
        return ""
    have = lambda d: set(d.get("available", "").split(":", 1)[-1].split())  # noqa: E731
    gained, lost = sorted(have(after) - have(before)), sorted(have(before) - have(after))
    parts = ([f"now on PATH: {' '.join(gained)}"] if gained else []) + ([f"gone: {' '.join(lost)}"] if lost else [])
    other = sorted(k for k in set(before) | set(after) if k != "available" and before.get(k) != after.get(k))
    if other:
        parts.append("updated: " + ", ".join(other))
    return " · env changed (" + "; ".join(parts) + ")"


class StateService:
    """The loop's managed-facts interface: start() -> pinned block, after_action() -> one line."""

    def __init__(self, env: Environment, workdir: str, remaining: Callable[[], float], trace: Callable[..., None],
                 *, control_dir: str, **_: Any) -> None:
        self.env, self.workdir, self.remaining, self.trace = env, workdir, remaining, trace
        self.copy, self.state_dir = _copy_path(workdir, control_dir), posixpath.join(control_dir, "state2")
        self.initial_workspace = InitialWorkspace()  # the loop's continuation checkpoint; this service keeps none
        self.context_changed = False
        self.block = ""
        self.files_at_start = ""
        self.env_text = ""
        self.rows: list[dict[str, Any]] = []
        self.misses: list[dict[str, Any]] = []
        self.last_refresh = 0

    async def _env(self) -> str:
        text, row = await env_brief.take(self.env, self.workdir)
        ports = ""
        try:
            result = await run(self.env, _PORTS, timeout_s=5)
            ports = result.stdout.strip() if result.code == 0 else ""
        except Exception:
            ports = ""
        body = text.removeprefix("(Environment, measured by the harness before your first action:\n").removesuffix(")")
        head, sep, files = body.partition("\nfiles under ")
        if not self.files_at_start and sep:
            self.files_at_start = "files at start under " + files
        if not head:
            return "environment: unmeasured"
        return head + f"\nlistening TCP ports: {ports or 'none'}"

    def _render(self, step: int) -> str:
        # The start file list stays in the trace only: it was most of the block (P5 smoke: ~3.5K of ~4K characters)
        # and the per-action line plus the state view already account for files.
        return (f"{PREFIX}Environment, measured by Core (last measured at step {step}; measured again after commands "
                f"that can change it):\n{self.env_text}")

    async def _step(self, mode: str) -> tuple[list[str], float]:
        script = _STEP.format(wd=shlex.quote(self.workdir.rstrip("/") or "/"), copy=shlex.quote(self.copy),
                              state=shlex.quote(self.state_dir), mode=mode, max_files=MAX_FILES)
        started = time.monotonic()
        try:
            result = await run(self.env, script, timeout_s=max(1, min(30, int(self.remaining() - 1))))
            lines = result.stdout.splitlines()
        except Exception as exc:
            lines = [f"F unmeasured ({type(exc).__name__})"]
        return lines, time.monotonic() - started

    async def start(self) -> str:
        self.env_text = await self._env()
        self.block = self._render(0)
        lines, seconds = await self._step("start")
        self.trace("core_state_v2", step=0, mode="start", out=lines, seconds=round(seconds, 3),
                   files_at_start=self.files_at_start, block_chars=len(self.block))
        return self.block

    def context_summary(self) -> str:
        return self.block

    async def after_action(self, step: int, tool: str, args: dict, result: str, *, call_id: str | None = None) -> str:
        self.context_changed = False
        if tool == "finish":
            lines, seconds = await self._step("verify")
            self._note(step, tool, "verify", lines, seconds, "")
            return ""
        command = str(args.get("input") or args.get("code") or "")
        changed = ""
        if (tool in ("terminal", "python") and _FULL_REFRESH.search(command)) or step - self.last_refresh >= REFRESH_EVERY:
            self.last_refresh = step
            new = await self._env()
            changed = env_change(self.env_text, new)
            if changed:
                self.env_text = new
                self.block, self.context_changed = self._render(step), True
        mode = "verify" if step % VERIFY_EVERY == 0 else "step"
        lines, seconds = await self._step(mode)
        self._note(step, tool, mode, lines, seconds, changed)
        return render_line(lines) + changed

    def _note(self, step: int, tool: str, mode: str, lines: list[str], seconds: float, changed: str) -> None:
        miss = next((x[2:] for x in lines if x.startswith("M ")), None)
        if miss is not None:  # the incremental account disagreed with the full comparison, which replaced it
            self.misses.append({"step": step, "paths": miss})
        row = {"step": step, "tool": tool, "mode": mode, "out": lines, "seconds": round(seconds, 3),
               "env_changed": bool(changed), "miss": miss}
        self.rows.append(row)
        self.trace("core_state_v2", **row)

    def safe_record(self) -> dict[str, Any]:
        seconds = [r["seconds"] for r in self.rows]
        return {"service": "state_v2", "steps": len(self.rows), "misses": self.misses,
                "env_refreshes": sum(r["env_changed"] for r in self.rows),
                "median_seconds": sorted(seconds)[len(seconds) // 2] if seconds else None}
