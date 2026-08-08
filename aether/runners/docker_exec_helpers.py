"""Runtime-neutral /proc helpers shared by the Docker executor."""
from __future__ import annotations

import re
import subprocess


def parse_tcp_probe_target(target: str) -> tuple[str, int] | None:
    raw = str(target or "").strip()
    if not raw:
        return None
    if raw.isdigit():
        port = int(raw)
        return ("127.0.0.1", port) if 0 < port <= 65535 else None
    if any(ch.isspace() for ch in raw):
        return None
    host, sep, port_text = raw.rpartition(":")
    if not sep or not port_text.isdigit():
        return None
    clean_host = host.strip() or "127.0.0.1"
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", clean_host):
        return None
    port = int(port_text)
    return (clean_host, port) if 0 < port <= 65535 else None


def _docker_bash(
    container_id: str,
    script: str,
    *args: str,
    timeout: int = 5,
) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            ["docker", "exec", container_id, "bash", "-lc", script, "_", *args],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def docker_process_generation_state(
    container_id: str,
    pid: int,
    start_ticks: str,
) -> tuple[str, str, str]:
    """Return ``(running|exited|unknown, current_start, detail)``.

    The sentinel distinguishes a real in-container "process absent/reused"
    result from a failed ``docker exec`` transport. No language runtime inside
    the task image is required.
    """
    script = (
        "current=$(awk '{print $22}' /proc/$1/stat 2>/dev/null || true); "
        "printf 'AETHER_GEN\\t%s\\n' \"$current\"; "
        "[ \"$current\" = \"$2\" ]"
    )
    proc = _docker_bash(container_id, script, str(int(pid)), str(start_ticks), timeout=5)
    if proc is None:
        return "unknown", "", "generation probe transport failure"
    marker = "AETHER_GEN\t"
    line = next((row for row in proc.stdout.splitlines() if row.startswith(marker)), "")
    if not line:
        return "unknown", "", (proc.stderr or proc.stdout).strip() or "generation probe missing sentinel"
    current = line[len(marker):].strip()
    status = "running" if proc.returncode == 0 and current == str(start_ticks) else "exited"
    detail = f"pid={int(pid)} expected_start={start_ticks} current_start={current or '<absent>'} status={status}"
    return status, current, detail


def docker_any_pid_descends_from(
    container_id: str,
    pids: tuple[int, ...],
    ancestor_pid: int,
) -> bool:
    """Prove whether any listener PID descends from one registered root PID."""
    if not pids or ancestor_pid <= 0:
        return False
    script = r'''
ancestor=$1
shift
for candidate in "$@"; do
  current=$candidate
  seen=""
  while [ "$current" -gt 1 ] 2>/dev/null; do
    [ "$current" = "$ancestor" ] && exit 0
    case " $seen " in *" $current "*) break ;; esac
    seen="$seen $current"
    [ -r "/proc/$current/stat" ] || break
    current=$(awk '{print $4}' "/proc/$current/stat" 2>/dev/null || true)
    [ -n "$current" ] || break
  done
done
exit 1
'''
    proc = _docker_bash(
        container_id,
        script,
        str(int(ancestor_pid)),
        *[str(int(pid)) for pid in pids],
        timeout=5,
    )
    return bool(proc is not None and proc.returncode == 0)


def docker_tcp_listener_owners(
    container_id: str,
    port: int,
) -> tuple[bool, tuple[int, ...], tuple[str, ...], str]:
    """Return listener liveness and exact owning PIDs using only Linux /proc."""
    script = r'''
port_hex=$(printf '%04X' "$1")
inodes=""
for table in /proc/net/tcp /proc/net/tcp6; do
  [ -r "$table" ] || continue
  found=$(awk -v p="$port_hex" 'NR>1 && $4=="0A" {split($2,a,":"); if (toupper(a[2])==p) print $10}' "$table")
  for inode in $found; do
    case " $inodes " in *" $inode "*) ;; *) inodes="$inodes $inode" ;; esac
  done
done
owners=""
if [ -n "$inodes" ]; then
  for fd in /proc/[0-9]*/fd/*; do
    [ -e "$fd" ] || continue
    link=$(readlink "$fd" 2>/dev/null || true)
    case "$link" in socket:\[*\]) ;; *) continue ;; esac
    inode=${link#socket:[}
    inode=${inode%]}
    case " $inodes " in
      *" $inode "*)
        pid=${fd#/proc/}; pid=${pid%%/*}
        case " $owners " in *" $pid "*) ;; *) owners="$owners $pid" ;; esac
        ;;
    esac
  done
fi
inodes=$(printf '%s\n' "$inodes" | awk '{$1=$1; print}')
owners=$(printf '%s\n' "$owners" | awk '{$1=$1; print}')
printf 'AETHER_TCP\t%s\t%s\n' "$inodes" "$owners"
[ -n "$inodes" ]
'''
    proc = _docker_bash(container_id, script, str(int(port)), timeout=10)
    if proc is None:
        return False, (), (), "tcp ownership probe transport failure"
    marker = "AETHER_TCP\t"
    line = next((row for row in proc.stdout.splitlines() if row.startswith(marker)), "")
    if not line:
        return False, (), (), (proc.stderr or proc.stdout).strip() or "tcp ownership probe missing sentinel"
    fields = line.split("\t", 2)
    inodes = tuple(item for item in (fields[1].split() if len(fields) > 1 else []) if item)
    owner_pids = tuple(sorted({int(item) for item in (fields[2].split() if len(fields) > 2 else []) if item.isdigit()}))
    live = bool(inodes)
    detail = f"live={str(live).lower()} owner_pids={list(owner_pids)} inodes={list(inodes)}"
    return live, owner_pids, inodes, detail


def docker_stop_process_generation(
    container_id: str,
    pid: int,
    start_ticks: str,
) -> bool:
    """Terminate one exact registered generation and its exact descendants.

    Descendants are snapshotted as ``pid:start_ticks`` pairs before any signal
    is sent. Every signal revalidates that generation, so PID reuse cannot
    redirect teardown. PID 1 and the helper's own docker-exec shell are never
    eligible targets.
    """
    script = r'''
root=$1
expected=$2
self=$$
current_start() {
  awk '{print $22}' "/proc/$1/stat" 2>/dev/null || true
}
current=$(current_start "$root")
[ "$current" = "$expected" ] || exit 2
walk() {
  local parent=$1
  local stat child ppid start
  for stat in /proc/[0-9]*/stat; do
    [ -r "$stat" ] || continue
    child=${stat#/proc/}; child=${child%/stat}
    [ "$child" = "1" ] && continue
    [ "$child" = "$self" ] && continue
    ppid=$(awk '{print $4}' "$stat" 2>/dev/null || true)
    if [ "$ppid" = "$parent" ]; then
      walk "$child"
      start=$(current_start "$child")
      [ -n "$start" ] && printf '%s:%s\n' "$child" "$start"
    fi
  done
}
descendants=$(walk "$root")
for item in $descendants; do
  child=${item%%:*}
  child_start=${item#*:}
  current=$(current_start "$child")
  [ "$current" = "$child_start" ] || continue
  kill -TERM "$child" 2>/dev/null || true
done
# Give descendants and the wrapper a brief opportunity to finish normally.
i=0
while [ $i -lt 20 ]; do
  current=$(current_start "$root")
  [ "$current" != "$expected" ] && exit 0
  i=$((i+1)); sleep 0.05
done
current=$(current_start "$root")
[ "$current" = "$expected" ] && kill -TERM "$root" 2>/dev/null || true
i=0
while [ $i -lt 20 ]; do
  current=$(current_start "$root")
  [ "$current" != "$expected" ] && exit 0
  i=$((i+1)); sleep 0.05
done
current=$(current_start "$root")
[ "$current" = "$expected" ] && kill -KILL "$root" 2>/dev/null || true
# Success means the exact root generation is no longer current.
current=$(current_start "$root")
[ "$current" != "$expected" ]
'''
    proc = _docker_bash(container_id, script, str(int(pid)), str(start_ticks), timeout=10)
    return bool(proc is not None and proc.returncode == 0)
