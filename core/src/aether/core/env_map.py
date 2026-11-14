"""Environment map: repository state and listening services, measured once at start (AETHER_CORE_ENV_MAP=on).

Off by default (``CoreConfig.env_map``). The stock start (managed facts, start copy) reports tools, files and
processes, but not version-control state or which services already listen. Both decide where evidence lives: the
commit-timing study (12 Nov) found failing runs that never visited the git history the passes used (4/16 vs 18/18),
and service tasks start with a server the model has to locate. Leading coding agents put this in the first request:
Claude Code's start context carries the branch, working-tree status and recent commits; Codex carries the
environment and repository instructions. This module adapts that to fresh sandboxes of any kind.

Measured, bounded, read-only, never interpreted:

- Repositories: the one containing the working directory, and ``.git`` directories or files (not links) up to depth 3
  below it, at most 4. Per repository: branch or detached HEAD, the HEAD commit (short hash, date, subject), commit
  count over all refs, local branches (8), tag, stash and HEAD reflog counts, and the number of changed or untracked
  paths. Git runs with optional locks off, the fsmonitor and untracked cache disabled, no pager or prompt, each
  command under a timeout; read commands do not run hooks. A refusal (for example dubious ownership) is reported as
  git's own first error line. Git reads tracked regular files to compare them; it does not open FIFOs or devices.
- Listening TCP sockets from ``/proc/net/tcp{,6}``, with the owning process name when its descriptors are visible
  (link targets are read with ``find -printf %l``, never followed). As root every in-sandbox owner is visible, so
  an ownerless listener belongs to the runtime outside the sandbox (e.g. a container DNS resolver) and is omitted;
  as another user it is shown as "owner not visible".

The note is placed in the task message after the start copy is taken, so nothing here runs before originals are
preserved. A failed probe adds nothing and is recorded in the trace.
"""

from __future__ import annotations

import shlex

from .env import Environment, run

MAX_REPOS, MAX_LISTEN, MAX_CHARS = 4, 12, 2000

_SCRIPT = r"""
wd=$1
export GIT_OPTIONAL_LOCKS=0 GIT_TERMINAL_PROMPT=0 GIT_PAGER=cat PAGER=cat LC_ALL=C
T=""; command -v timeout >/dev/null 2>&1 && T="timeout 5"
g() { $T git -c core.fsmonitor=false -c core.untrackedCache=false -C "$r" "$@" 2>/dev/null; }
if command -v git >/dev/null 2>&1; then
  {
    top=$($T git -C "$wd" rev-parse --show-toplevel 2>&1) && printf '%s\n' "$top"
    case "$top" in *fatal*|*error*|*warning*) case "$top" in *"not a git repository"*) ;; *) printf 'E\t%s\t%s\n' "$wd" "$(printf '%s' "$top" | head -n 1 | head -c 200)" >&2;; esac;; esac
    find -P "$wd" -mindepth 1 -maxdepth 3 -name .git \( -type d -o -type f \) -prune -print 2>/dev/null | head -n 12 | sed 's#/\.git$##'
  } | awk '!seen[$0]++' | grep -v '^fatal' | head -n {max_repos} > "${TMPDIR:-/tmp}/.aether_env_map_repos.$$"
  while IFS= read -r r; do
    [ -n "$r" ] || continue
    if ! out=$($T git -C "$r" rev-parse --git-dir 2>&1); then
      printf 'R\t%s\terror\t%s\n' "$r" "$(printf '%s' "$out" | head -n 1 | head -c 200)"; continue
    fi
    printf 'R\t%s\tbranch\t%s\n' "$r" "$(g symbolic-ref --short -q HEAD || echo '(detached HEAD)')"
    printf 'R\t%s\thead\t%s\n' "$r" "$(g log -1 --format='%h %cs %s' | head -c 160)"
    printf 'R\t%s\tcommits\t%s\n' "$r" "$(g rev-list --count --all)"
    printf 'R\t%s\tbranches\t%s\n' "$r" "$(g for-each-ref --format='%(refname:short)' refs/heads | head -n 8 | tr '\n' ' ')"
    printf 'R\t%s\tbranch_count\t%s\n' "$r" "$(g for-each-ref --format=x refs/heads | wc -l | tr -d ' ')"
    printf 'R\t%s\ttags\t%s\n' "$r" "$(g for-each-ref --format=x refs/tags | wc -l | tr -d ' ')"
    printf 'R\t%s\tstashes\t%s\n' "$r" "$(g stash list | wc -l | tr -d ' ')"
    printf 'R\t%s\treflog\t%s\n' "$r" "$(g reflog show --format=%h HEAD | wc -l | tr -d ' ')"
    printf 'R\t%s\tremotes\t%s\n' "$r" "$(g remote | head -n 4 | tr '\n' ' ')"
    printf 'R\t%s\tchanged\t%s\n' "$r" "$(g status --porcelain=v1 --untracked-files=normal | head -n 1000 | wc -l | tr -d ' ')"
  done < "${TMPDIR:-/tmp}/.aether_env_map_repos.$$"
  rm -f "${TMPDIR:-/tmp}/.aether_env_map_repos.$$"
fi
for f in /proc/net/tcp /proc/net/tcp6; do
  [ -r "$f" ] && awk -v f="${f##*/}" 'NR>1 && $4=="0A" {print "L\t" f "\t" $2 "\t" $10}' "$f"
done | head -n {max_listen}
if [ -r /proc/net/tcp ]; then
  find -P /proc/[0-9]*/fd -maxdepth 1 -lname 'socket:\[*' -printf 'S\t%h\t%l\n' 2>/dev/null | head -n 4000
fi
printf 'U\t%s\n' "$(id -u)"
printf 'done\n'
"""


def _address(proto: str, local: str) -> str:
    host, _, port = local.partition(":")
    number = int(port, 16) if port else 0
    if proto == "tcp" and len(host) == 8:
        octets = [str(int(host[i:i + 2], 16)) for i in range(6, -1, -2)]
        return f"{'.'.join(octets)}:{number}"
    if set(host) == {"0"}:
        return f"[::]:{number}"
    return f"[ipv6]:{number}"


def parse(stdout: str, comm: dict[str, str]) -> tuple[list[str], dict]:
    repos: dict[str, dict[str, str]] = {}
    listen: list[tuple[str, str, str]] = []
    owners: dict[str, str] = {}
    uid = None
    for line in stdout.splitlines():
        fields = line.split("\t")
        if fields[0] == "R" and len(fields) == 4:
            repos.setdefault(fields[1], {})[fields[2]] = fields[3].strip()
        elif fields[0] == "L" and len(fields) == 4:
            listen.append((fields[1], fields[2], fields[3]))
        elif fields[0] == "U" and len(fields) == 2:
            uid = fields[1].strip()
        elif fields[0] == "S" and len(fields) == 3 and fields[2].startswith("socket:["):
            owners.setdefault(fields[2][8:-1], fields[1].split("/")[2])
    lines = []
    for path, facts in list(repos.items())[:MAX_REPOS]:
        if "error" in facts:
            lines.append(f"- git repository {path}: git reported: {facts['error']}")
            continue
        branches = facts.get("branches", "").split()
        count = int(facts.get("branch_count") or len(branches) or 0)
        more = f" (+{count - len(branches)} more)" if count > len(branches) else ""
        lines.append(
            f"- git repository {path}: on {facts.get('branch') or '?'}; HEAD {facts.get('head') or '(no commits)'}; "
            f"{facts.get('commits') or 0} commits on all refs; branches: {' '.join(branches) or 'none'}{more}; "
            f"tags {facts.get('tags') or 0}, stashes {facts.get('stashes') or 0}, HEAD reflog entries "
            f"{facts.get('reflog') or 0}; remotes: {facts.get('remotes') or 'none'}; "
            f"changed or untracked paths: {facts.get('changed') or 0}"
        )
    sockets, outside = [], 0
    for proto, local, inode in listen[:MAX_LISTEN]:
        pid = owners.get(inode)
        if pid is None and uid == "0":
            outside += 1  # root sees every in-sandbox owner: this socket belongs to the runtime outside the sandbox
            continue
        name = comm.get(pid, "") if pid else ""
        sockets.append(_address(proto, local) + (f" ({name}, pid {pid})" if name else " (owner not visible)"))
    if sockets:
        lines.append("- listening TCP: " + ", ".join(sockets))
    return lines, {"repos": len(repos), "listening": len(listen), "owned": sum(1 for _, _, i in listen if i in owners),
                   "outside_sandbox": outside}


async def take(env: Environment, workdir: str) -> tuple[str, dict]:
    """The start note ('' when nothing was found or the probe failed) and a trace row."""
    script = _SCRIPT.replace("{max_repos}", str(MAX_REPOS)).replace("{max_listen}", str(MAX_LISTEN))
    try:
        result = await run(env, f"sh -c {shlex.quote(script)} core-env-map {shlex.quote(workdir)}", timeout_s=60)
        if result.code != 0 or not result.stdout.rstrip().endswith("done"):
            return "", {"ok": False, "reason": (result.stderr or f"exit {result.code}")[:300]}
        pids = sorted({row.split("\t")[1].split("/")[2] for row in result.stdout.splitlines()
                       if row.startswith("S\t") and row.count("/") >= 3})
        comm: dict[str, str] = {}
        if pids:
            names = await run(env, "for p in " + " ".join(shlex.quote(p) for p in pids[:400])
                              + "; do printf '%s\\t%s\\n' \"$p\" \"$(cat /proc/$p/comm 2>/dev/null)\"; done", timeout_s=10)
            comm = dict(line.split("\t", 1) for line in names.stdout.splitlines() if "\t" in line)
    except Exception as exc:  # an instrument: no note, no claim
        return "", {"ok": False, "reason": f"{type(exc).__name__}: {exc}"[:300]}
    lines, row = parse(result.stdout, comm)
    if not lines:
        return "", {"ok": True, **row, "chars": 0}
    text = "\n".join(lines)
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + "\n  ..."
    return f"(Repositories and services, measured by the harness before your first action:\n{text})", {
        "ok": True, **row, "chars": len(text)}
