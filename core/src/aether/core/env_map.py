"""Environment map: repository state and listening services, measured once at start (AETHER_CORE_ENV_MAP=on).

Off by default (``CoreConfig.env_map``). The stock start (managed facts, start copy) reports tools, files and
processes, but not version-control state or which services already listen. Both decide where evidence lives: the
commit-timing study (12 Nov) found failing runs that never visited the git history the passes used (4/16 vs 18/18),
and service tasks start with a server the model has to locate. Leading coding agents put this in the first request:
Claude Code's start context carries the branch, working-tree status and recent commits; Codex carries the
environment and repository instructions. This module adapts that to fresh sandboxes of any kind.

Measured, bounded, read-only, never interpreted:

- Repositories with a local, non-symlink .git directory inside the workspace. Per repository: branch, HEAD,
  local refs and observed status. Linked worktrees can be inspected with an explicit model-directed command.
- Listening TCP sockets in the task network namespace, with the owning process when observed. A bounded
  descriptor scan may miss owners, including when run as root.

The note is placed in the task message after the start copy is taken, so nothing here runs before originals are
preserved. A failed probe adds nothing and is recorded in the trace.
"""

from __future__ import annotations

from ipaddress import IPv6Address
import shlex
import sys

from .env import Environment, run

MAX_REPOS, MAX_LISTEN, MAX_CHARS = 4, 12, 2000

_SCRIPT = r"""
wd=$(cd "$1" && pwd -P) || exit 1
unset GIT_DIR GIT_COMMON_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES
export GIT_OPTIONAL_LOCKS=0 GIT_TERMINAL_PROMPT=0 GIT_PAGER=cat PAGER=cat LC_ALL=C
T=""; command -v timeout >/dev/null 2>&1 && T="timeout 5"
g() { $T git --git-dir="$r/.git" --work-tree="$r" -c core.fsmonitor=false -c core.untrackedCache=false -C "$r" "$@" 2>/dev/null; }
if command -v git >/dev/null 2>&1; then
  find -P "$wd" -xdev -mindepth 1 -maxdepth 3 \( -name .git -type d -print -prune -o -name '.*' -type d -prune \) 2>/dev/null | head -n {max_repos} | sed 's#/\.git$##' | while IFS= read -r r; do
    [ -n "$r" ] || continue
    [ ! -e "$r/.git/commondir" ] && [ ! -L "$r/.git/commondir" ] || continue
    [ ! -e "$r/.git/objects/info/alternates" ] && [ ! -L "$r/.git/objects/info/alternates" ] || continue
    if ! g rev-parse --git-dir >/dev/null; then
      printf 'R\t%s\terror\tGit metadata unavailable\n' "$r"; continue
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
    changed=$({ g status --porcelain=v1 --untracked-files=normal; printf '%%git-status=%s\n' "$?"; } |
      awk '/^%git-status=/ {if ($0 == "%git-status=0") print NR-1; exit}
           NR == 1001 {print "1000+"; exit}')
    printf 'R\t%s\tchanged\t%s\n' "$r" "$changed"
  done
fi
for f in /proc/net/tcp /proc/net/tcp6; do
  [ -r "$f" ] && awk -v f="${f##*/}" 'NR>1 && $4=="0A" {print "L\t" f "\t" $2 "\t" $10}' "$f"
done | head -n {max_listen}
if [ -r /proc/net/tcp ]; then
  find -P /proc/[0-9]*/fd -maxdepth 1 -lname 'socket:\[*' -printf 'S\t%h\t%l\n' 2>/dev/null | head -n 4000
fi
printf 'done\n'
"""


def _address(proto: str, local: str) -> str:
    host, _, port = local.partition(":")
    number = int(port, 16) if port else 0
    if proto == "tcp" and len(host) == 8:
        octets = [str(int(host[i:i + 2], 16)) for i in range(6, -1, -2)]
        return f"{'.'.join(octets)}:{number}"
    if proto == "tcp6" and len(host) == 32:
        # Linux prints each 32-bit word in its native byte order.
        packed = b"".join(int(host[i:i + 8], 16).to_bytes(4, sys.byteorder)
                          for i in range(0, 32, 8))
        return f"[{IPv6Address(packed)}]:{number}"
    return f"[address unavailable]:{number}"


def parse(stdout: str, comm: dict[str, str]) -> tuple[list[str], dict]:
    repos: dict[str, dict[str, str]] = {}
    listen: list[tuple[str, str, str]] = []
    owners: dict[str, str] = {}
    for line in stdout.splitlines():
        fields = line.split("\t")
        if fields[0] == "R" and len(fields) == 4:
            repos.setdefault(fields[1], {})[fields[2]] = fields[3].strip()
        elif fields[0] == "L" and len(fields) == 4:
            listen.append((fields[1], fields[2], fields[3]))
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
            f"changed or untracked paths: {facts.get('changed') or 'unknown'}"
        )
    sockets = []
    for proto, local, inode in listen[:MAX_LISTEN]:
        pid = owners.get(inode)
        name = comm.get(pid, "") if pid else ""
        sockets.append(_address(proto, local) + (f" ({name}, pid {pid})" if name else " (owner not visible)"))
    if sockets:
        lines.append("- listening TCP: " + ", ".join(sockets))
    return lines, {"repos": len(repos), "listening": len(listen), "owned": sum(1 for _, _, i in listen if i in owners),
                   "unknown_owner": sum(1 for _, _, i in listen if i not in owners)}


async def take(env: Environment, workdir: str, task: str = "") -> tuple[str, dict]:
    """The start note ('' when nothing was found or the probe failed) and a trace row."""
    from . import env_map_more
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
    more, more_row = await env_map_more.take(env, workdir, task)
    lines, row = lines + more, {**row, **more_row}
    if not lines:
        return "", {"ok": True, **row, "chars": 0}
    text = "\n".join(lines)
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + "\n  ..."
    return f"(Repositories, services, data files and paths, measured by the harness before your first action:\n{text})", {
        "ok": True, **row, "chars": len(text)}
