"""Exact container process-generation helpers for Docker terminal sessions."""
from __future__ import annotations

import os
import signal
import subprocess
import time


def wait_identity(
    container_id: str,
    identity_path: str,
    client: subprocess.Popen[bytes],
    *,
    timeout_s: float,
) -> tuple[int, str, int, int] | None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        proc = subprocess.run(
            ["docker", "exec", container_id, "cat", identity_path],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=2,
        )
        if proc.returncode == 0:
            fields = proc.stdout.strip().split("\t")
            if len(fields) == 4 and all(field.isdigit() for field in fields):
                return int(fields[0]), fields[1], int(fields[2]), int(fields[3])
        if client.poll() is not None:
            return None
        time.sleep(0.05)
    return None


def generation_live(
    container_id: str,
    client: subprocess.Popen[bytes],
    *,
    pid: int,
    start_ticks: str,
    process_group_id: int,
    session_leader_id: int,
) -> bool:
    if client.poll() is not None:
        return False
    script = (
        "current=$(awk '{print $22}' /proc/$1/stat 2>/dev/null || true); "
        "pgrp=$(awk '{print $5}' /proc/$1/stat 2>/dev/null || true); "
        "sid=$(awk '{print $6}' /proc/$1/stat 2>/dev/null || true); "
        "[ \"$current\" = \"$2\" ] && [ \"$pgrp\" = \"$3\" ] && [ \"$sid\" = \"$4\" ]"
    )
    try:
        proc = subprocess.run(
            [
                "docker", "exec", container_id, "bash", "-lc", script, "_",
                str(pid), start_ticks, str(process_group_id), str(session_leader_id),
            ],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=3,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0


def terminate_descendants_exact(
    container_id: str,
    *,
    pid: int,
    start_ticks: str,
    process_group_id: int,
    session_leader_id: int,
    signal_name: str,
) -> None:
    """Signal descendants post-order while the exact root can still reap."""
    script = (
        "current=$(awk '{print $22}' /proc/$1/stat 2>/dev/null || true); "
        "pgrp=$(awk '{print $5}' /proc/$1/stat 2>/dev/null || true); "
        "sid=$(awk '{print $6}' /proc/$1/stat 2>/dev/null || true); "
        "[ \"$current\" = \"$2\" ] || exit 2; "
        "[ \"$pgrp\" = \"$3\" ] || exit 3; "
        "[ \"$sid\" = \"$4\" ] || exit 4; "
        "walk() { parent=\"$1\"; for f in /proc/[0-9]*/stat; do "
        " [ -r \"$f\" ] || continue; "
        " child=${f#/proc/}; child=${child%/stat}; "
        " ppid=$(awk '{print $4}' \"$f\" 2>/dev/null || true); "
        " if [ \"$ppid\" = \"$parent\" ]; then walk \"$child\"; printf '%s\\n' \"$child\"; fi; "
        "done; }; "
        "for child in $(walk \"$1\"); do kill -$5 \"$child\" 2>/dev/null || true; done"
    )
    proc = subprocess.run(
        [
            "docker", "exec", container_id, "bash", "-lc", script, "_",
            str(pid), start_ticks, str(process_group_id), str(session_leader_id), signal_name,
        ],
        capture_output=True,
        text=True,
        errors="replace",
        timeout=8,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"refusing terminal descendant signal: exit={proc.returncode}: "
            f"{(proc.stderr or proc.stdout).strip()}"
        )


def group_live(
    container_id: str,
    *,
    process_group_id: int,
    session_leader_id: int,
) -> bool:
    script = (
        "for f in /proc/[0-9]*/stat; do "
        " [ -r \"$f\" ] || continue; "
        " pgrp=$(awk '{print $5}' \"$f\" 2>/dev/null || true); "
        " sid=$(awk '{print $6}' \"$f\" 2>/dev/null || true); "
        " if [ \"$pgrp\" = \"$1\" ] && [ \"$sid\" = \"$2\" ]; then exit 0; fi; "
        "done; exit 1"
    )
    try:
        proc = subprocess.run(
            [
                "docker", "exec", container_id, "bash", "-lc", script, "_",
                str(process_group_id), str(session_leader_id),
            ],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=3,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0


def signal_group_after_root_exit(
    container_id: str,
    *,
    process_group_id: int,
    session_leader_id: int,
    signal_name: str,
) -> None:
    """Signal only a surviving member of the exact recorded group/session."""
    if not group_live(
        container_id,
        process_group_id=process_group_id,
        session_leader_id=session_leader_id,
    ):
        return
    script = (
        "found=0; for f in /proc/[0-9]*/stat; do "
        " [ -r \"$f\" ] || continue; "
        " pgrp=$(awk '{print $5}' \"$f\" 2>/dev/null || true); "
        " sid=$(awk '{print $6}' \"$f\" 2>/dev/null || true); "
        " if [ \"$pgrp\" = \"$1\" ] && [ \"$sid\" = \"$2\" ]; then found=1; break; fi; "
        "done; [ $found -eq 1 ] || exit 2; kill -$3 -- -$1"
    )
    proc = subprocess.run(
        [
            "docker", "exec", container_id, "bash", "-lc", script, "_",
            str(process_group_id), str(session_leader_id), signal_name,
        ],
        capture_output=True,
        text=True,
        errors="replace",
        timeout=5,
    )
    if proc.returncode not in {0, 1}:
        raise RuntimeError(
            f"refusing post-root terminal group signal: exit={proc.returncode}: "
            f"{(proc.stderr or proc.stdout).strip()}"
        )


def signal_exact_group(
    container_id: str,
    *,
    pid: int,
    start_ticks: str,
    process_group_id: int,
    session_leader_id: int,
    signal_name: str,
) -> None:
    script = (
        "current=$(awk '{print $22}' /proc/$1/stat 2>/dev/null || true); "
        "pgrp=$(awk '{print $5}' /proc/$1/stat 2>/dev/null || true); "
        "sid=$(awk '{print $6}' /proc/$1/stat 2>/dev/null || true); "
        "[ \"$current\" = \"$2\" ] || exit 2; "
        "[ \"$pgrp\" = \"$3\" ] || exit 3; "
        "[ \"$sid\" = \"$4\" ] || exit 4; "
        "[ \"$pgrp\" = \"$1\" ] || exit 5; "
        "kill -$5 -- -$pgrp"
    )
    proc = subprocess.run(
        [
            "docker", "exec", container_id, "bash", "-lc", script, "_",
            str(pid), start_ticks, str(process_group_id), str(session_leader_id), signal_name,
        ],
        capture_output=True,
        text=True,
        errors="replace",
        timeout=5,
    )
    if proc.returncode not in {0, 1}:
        raise RuntimeError(
            f"refusing to signal terminal generation: exit={proc.returncode}: "
            f"{(proc.stderr or proc.stdout).strip()}"
        )


def terminate_client(client: subprocess.Popen[bytes]) -> None:
    if client.poll() is not None:
        return
    try:
        os.killpg(os.getpgid(client.pid), signal.SIGTERM)
    except (OSError, ProcessLookupError):
        try:
            client.terminate()
        except OSError:
            return
    try:
        client.wait(timeout=1.0)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(client.pid), signal.SIGKILL)
        except (OSError, ProcessLookupError):
            try:
                client.kill()
            except OSError:
                pass
