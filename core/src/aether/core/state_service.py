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

import asyncio
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

def settings(choice: Callable[[str, tuple, str], str], on_off: tuple, facts_modes: tuple) -> dict:
    """CoreConfig fields for env + state. Default on since 2 Nov (user decision after P5 and the reach count):
    state v2 plus the `changes` view, both needing the start copy. AETHER_CORE_ENV_BRIEF=on selects the old one-shot
    brief instead; AETHER_CORE_MANAGED_FACTS=off turns the service off."""
    copy = choice("AETHER_CORE_START_COPY", on_off, "on") == "on"
    brief = choice(env_brief.ENV_BRIEF_ENV, on_off, "off") == "on"
    facts = choice("AETHER_CORE_MANAGED_FACTS", facts_modes, "v2" if copy and not brief else "off")
    return {"state_view": choice("AETHER_CORE_STATE_VIEW", on_off, "on" if copy else "off") == "on",
            "env_brief": brief, "managed_facts": facts != "off", "facts_pull": facts == "pull", "facts_v2": facts == "v2"}
REFRESH_EVERY, VERIFY_EVERY, MAX_FILES = 10, 10, 20_000
PORTS_LABEL = "listening TCP ports"

# Listening TCP ports with the owning command; sockets of Core's own processes (cmdline naming .aether or aether) are
# left out, and so are sockets with no owning process in the container (Docker's embedded DNS on 127.0.0.11 is owned
# by dockerd outside it): the P5 smokes showed such a port, which is not a fact about the task.
_PORTS = r"""
[ -r /proc/net/tcp ] || [ -r /proc/net/tcp6 ] || { echo "/proc/net/tcp unreadable" >&2; exit 3; }
for f in /proc/net/tcp /proc/net/tcp6; do [ -r "$f" ] && awk 'NR>1 && $4=="0A" {n=split($2,a,":"); print a[n], $10}' "$f"; done 2>/dev/null |
  sort -u | while read -r h ino; do
    pid=$(for d in /proc/[0-9]*; do ls -l "$d/fd" 2>/dev/null | grep -q "socket:\[$ino\]" && { echo "${d#/proc/}"; break; }; done)
    [ -n "$pid" ] || continue
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
{versions}added=$(awk 'FILENAME==ARGV[1] {{ s[$0]=1; next }} !($0 in s)' "$S/start.paths" "$S/cur.paths" | wc -l | tr -d ' ')
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


# E15 (switch AETHER_CORE_CHECK_VERSIONS, trace only): a workspace version per action. GNU find gives nanosecond
# mtime/ctime, so a same-size rewrite in the same second still moves it; without -printf (BSD, some busybox) the
# version falls back to the step's one-second stat listing ("V s"), which can miss such a rewrite. Inserted into the
# step script only when the switch is on, so the stock script is byte-identical.
_VERSION = r"""if ( cd "$W" && find . -maxdepth 0 -printf '' ) >/dev/null 2>&1; then
  v=$( (cd "$W" && find . -path ./.git -prune -o ! -type d -printf '%P|%s|%T@|%C@|%i\n') 2>/dev/null | sort | cksum )
  echo "V ns ${v%% *}"
else echo "V s $(cksum < "$S/cur.tsv" | cut -d' ' -f1)"; fi
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


# Free memory and free disk drift by a few MiB between measurements (other processes on the host, logs, caches).
# Counting that drift as a change rewrote the pinned block near the top of the request, so the provider's prompt
# cache missed the whole request after it (16 Nov: chess L-1 calls 3-7 cached 0 tokens, each rewrite only moved
# "30370 -> 30456 MiB available"). A move counts when it exceeds both bounds below.
_VOLATILE = re.compile(r"(\d+) MiB (available|at )")
DRIFT_MIB, DRIFT_SHARE = 512, 0.10


def _machine_same(a: str, b: str) -> bool:
    """Same machine line apart from free-memory/free-disk drift within DRIFT_MIB or DRIFT_SHARE."""
    if _VOLATILE.sub(r"N MiB \2", a) != _VOLATILE.sub(r"N MiB \2", b):
        return False
    for x, y in zip((int(m.group(1)) for m in _VOLATILE.finditer(a)), (int(m.group(1)) for m in _VOLATILE.finditer(b))):
        if abs(x - y) > DRIFT_MIB and abs(x - y) > DRIFT_SHARE * max(x, y):
            return False
    return True


def env_change(old: str, new: str) -> str:
    """A short account of what differs between two environment blocks ('' when nothing does)."""
    before, after = _env_lines(old), _env_lines(new)
    if "machine" in before and "machine" in after and _machine_same(before["machine"], after["machine"]):
        after = {**after, "machine": before["machine"]}
    if before == after:
        return ""
    have = lambda d: set(d.get("available", "").split(":", 1)[-1].split())  # noqa: E731
    gained, lost = sorted(have(after) - have(before)), sorted(have(before) - have(after))
    parts = ([f"now on PATH: {' '.join(gained)}"] if gained else []) + ([f"gone: {' '.join(lost)}"] if lost else [])
    if before.get(PORTS_LABEL) != after.get(PORTS_LABEL):
        parts.append(f"{PORTS_LABEL} now: {after.get(PORTS_LABEL, ': unmeasured').split(':', 1)[1].strip()}")
    other = sorted(k for k in set(before) | set(after)
                   if k not in ("available", PORTS_LABEL) and before.get(k) != after.get(k))
    if other:
        parts.append("updated: " + ", ".join(other))
    return " · env changed (" + "; ".join(parts) + ")"


class StateService:
    """The loop's managed-facts interface: start() -> pinned block, after_action() -> one line."""

    def __init__(self, env: Environment, workdir: str, remaining: Callable[[], float], trace: Callable[..., None],
                 *, control_dir: str, versions: bool = False, **_: Any) -> None:
        self.env, self.workdir, self.remaining, self.trace = env, workdir, remaining, trace
        self.versions = versions  # E15: trace a workspace version (stat fingerprint) per action; never shown
        self.copy, self.state_dir = _copy_path(workdir, control_dir), posixpath.join(control_dir, "state2")
        self.initial_workspace = InitialWorkspace()  # the loop's continuation checkpoint; this service keeps none
        self.context_changed = False
        self.block = ""
        self.files_at_start = ""
        self.env_text = ""
        self.rows: list[dict[str, Any]] = []
        self.misses: list[dict[str, Any]] = []
        self.last_refresh = 0

    async def _ports(self) -> str:
        """The ports line. 'none' only after a probe that ran and found nothing; a failed probe is not an absence
        (Codex review, 3 Nov: a timed-out probe was shown as 'none')."""
        try:
            result = await run(self.env, _PORTS, timeout_s=5)
        except Exception as exc:
            return f"{PORTS_LABEL}: unknown (probe failed: {type(exc).__name__})"
        if result.code != 0:
            return f"{PORTS_LABEL}: unknown (probe failed: exit {result.code})"
        return f"{PORTS_LABEL}: {result.stdout.strip() or 'none'}"

    async def _env(self) -> str:
        text, row = await env_brief.take(self.env, self.workdir)
        body = text.removeprefix("(Environment, measured by the harness before your first action:\n").removesuffix(")")
        head, sep, files = body.partition("\nfiles under ")
        if not self.files_at_start and sep:
            self.files_at_start = "files at start under " + files
        if not head:
            return "environment: unmeasured"
        return head + "\n" + await self._ports()

    async def _ports_only(self) -> str:
        """The current block with only the ports line measured again: a server started by a command the full-refresh
        pattern does not match (`python3 -m http.server 8080 &`) left the block stale until the next full refresh."""
        if PORTS_LABEL + ":" not in self.env_text:
            return self.env_text
        line = await self._ports()
        return "\n".join(line if x.startswith(PORTS_LABEL + ":") else x for x in self.env_text.splitlines())

    def _render(self, step: int) -> str:
        # The start file list stays in the trace only: it was most of the block (P5 smoke: ~3.5K of ~4K characters)
        # and the per-action line plus the state view already account for files.
        return (f"{PREFIX}Environment, measured by Core (last measured at step {step}; measured again after commands "
                f"that can change it):\n{self.env_text}")

    async def _step(self, mode: str) -> tuple[list[str], float]:
        script = _STEP.format(wd=shlex.quote(self.workdir.rstrip("/") or "/"), copy=shlex.quote(self.copy),
                              state=shlex.quote(self.state_dir), mode=mode, max_files=MAX_FILES,
                              versions=_VERSION if self.versions else "")
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
            # Recorded, not shown: showing it would mean holding finish (a completion veto), and post-finish facts were
            # inert (LC-2: 87/87 continuations re-finished in one step). Background changes before finish already
            # reach Luna in the next action's line; only changes after the last action go unseen, with no decision left.
            lines, seconds = await self._step("verify")
            self._note(step, tool, "verify", lines, seconds, "")
            return ""
        command = str(args.get("input") or args.get("code") or "")
        mode = "verify" if step % VERIFY_EVERY == 0 else "step"
        new = None
        if (tool in ("terminal", "python") and _FULL_REFRESH.search(command)) or step - self.last_refresh >= REFRESH_EVERY:
            self.last_refresh = step
            new = await self._env()
            lines, seconds = await self._step(mode)
        elif tool in ("terminal", "terminal_wait", "python"):
            # Neither probe depends on the other's result. Await both before
            # publishing the state for the next model decision.
            new, (lines, seconds) = await asyncio.gather(self._ports_only(), self._step(mode))
        else:
            lines, seconds = await self._step(mode)
        changed = ""
        if new is not None:
            changed = env_change(self.env_text, new)
            if changed:
                self.env_text = new
                self.block, self.context_changed = self._render(step), True
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
