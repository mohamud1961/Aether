"""Bounded, read-only workspace snapshots for checkpoint v2.

The executor receives only commands built by this module. Path arguments are
quoted, and the command parser is deliberately closed over the fixed read-only
command vocabulary so a snapshot can never become a solver action. Harbor's
remote filesystem also needs a fixed-argument ``realpath`` containment probe;
those trusted resolver probes are recorded separately in ``path_resolution``
and are never part of the model-visible snapshot command allow-list.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
import json
import os
import re
import shlex
import time
import math
import stat as stat_module
from pathlib import Path
from typing import Any, Iterable, Mapping

from .shell_writes import command_write_targets

MAX_COMMAND_SECONDS = 5
MAX_SNAPSHOT_SECONDS = 15
MAX_SNAPSHOT_BYTES = 48_000
MAX_PATHS = 20
MAX_RECENT_FILES = 50
MAX_RECENT_WRITES = 20
MAX_TEXT_EXCERPT = 2048
MAX_BINARY_EXCERPT = 512
MAX_LOG_TAIL_READ_BYTES = 64 * 1024
MAX_LOG_TAIL_LINES = 30
_ALLOWED = frozenset({"stat", "file", "head", "tail", "ls", "ps", "ss", "find", "cat"})


def validate_read_only_command(command: str) -> bool:
    """Accept only one simple invocation from the snapshot command allow-list."""
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in command):
        return False
    try:
        words = shlex.split(command, posix=True)
        lex = shlex.shlex(command, posix=True, punctuation_chars=";&|<>")
        punctuation_tokens = set(lex)
    except ValueError:
        return False
    if (not words or words[0] not in _ALLOWED or
            any(token and all(ch in ";&|<>" for ch in token) for token in punctuation_tokens) or
            "`" in command or command != shlex.join(words)):
        return False
    if words[0] == "find":
        return len(words) == 6 and words[2:5] == ["-type", "f", "-newer"] and not words[1].startswith("-")
    if words[0] == "cat":
        return words[1:] == ["/proc/net/tcp"]
    if words[0] == "ps":
        return words[1:] == ["-eo", "pid,ppid,etime,stat,args"]
    if words[0] == "ss":
        return words[1:] == ["-ltnp"]
    if words[0] == "stat":
        return len(words) == 4 and words[1:3] == ["-c", "%n|%F|%s|%Y"] and not words[3].startswith("-")
    if words[0] == "file":
        return len(words) == 3 and words[1] == "-b" and not words[2].startswith("-")
    if words[0] == "head":
        return len(words) == 4 and words[1] == "-c" and words[2].isdigit() and 0 <= int(words[2]) <= MAX_TEXT_EXCERPT and not words[3].startswith("-")
    if words[0] == "tail":
        return len(words) == 4 and words[1:3] == ["-n", "30"] and not words[3].startswith("-")
    if words[0] == "ls":
        return len(words) == 3 and words[1] == "-1A" and not words[2].startswith("-")
    return False


def extract_task_paths(task_text: str) -> list[str]:
    """Reuse the v5 task-path extractor and keep its deterministic order."""
    from tools.aether_program.judge_bench_targeted import extract_output_paths
    return [str(row["path"]) for row in extract_output_paths(str(task_text), limit=MAX_PATHS)]


def _paths_from_receipts(ledger: Any, workspace_root: str) -> list[str]:
    out: list[str] = []
    for receipt in ledger.all_receipts():
        payload = receipt.payload if isinstance(receipt.payload, Mapping) else {}
        candidates: Iterable[str] = ()
        if receipt.kind in {"write_file", "edit_file"} and payload.get("path"):
            candidates = (str(payload["path"]),)
        elif receipt.kind == "run_command":
            candidates = tuple(payload.get("modified_paths") or ()) + command_write_targets(
                str(payload.get("command", "")))
        for path in candidates:
            clean = str(path).strip()
            if clean:
                if clean in out:
                    out.remove(clean)
                out.append(clean)
    return out[-MAX_RECENT_WRITES:]


def _workspace_path(path: str, root: str, executor: Any,
                    command_log: list[dict[str, Any]]) -> str | None:
    """Resolve an observed path and reject lexical or symlink escapes from the workspace."""
    try:
        resolver = getattr(executor, "resolve_state_snapshot_path", None)
        if callable(resolver):
            return resolver(path, workspace_root=root, command_log=command_log)
        base = Path(root).resolve(strict=False)
        candidate = Path(path)
        absolute = (candidate if candidate.is_absolute() else base / candidate).resolve(strict=False)
        absolute.relative_to(base)
        return str(absolute)
    except (OSError, RuntimeError, ValueError):
        return None


def _workspace_path_bounded(path: str, root: str, executor: Any,
                            command_log: list[dict[str, Any]], channel: ThreadPoolExecutor,
                            deadline: float) -> str | None:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        return None
    local_log: list[dict[str, Any]] = []
    future = channel.submit(_workspace_path, path, root, executor, local_log)
    try:
        resolved = future.result(timeout=min(float(MAX_COMMAND_SECONDS), remaining))
        command_log.extend(local_log)
        return resolved
    except FutureTimeout:
        future.cancel()
        command_log.append({"command": "resolve_state_snapshot_path", "path": str(path)[:300],
                            "exit_code": 124, "stdout": "", "stderr": "path resolver exceeded wall budget"})
        return None


def secure_local_snapshot_read(path: str, *, workspace_root: str,
                               text_limit: int = MAX_TEXT_EXCERPT,
                               binary_limit: int = MAX_BINARY_EXCERPT,
                               tail: bool = False) -> dict[str, Any]:
    """Read one regular workspace file via a root dirfd and no-follow openat walk.

    This is deliberately an executor-internal primitive, not a model-visible shell
    command. Every directory component and the final file are opened relative to
    an already-open descriptor with O_NOFOLLOW, closing the validate-then-open
    symlink race in snapshot evidence collection.
    """
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
        raise OSError("platform lacks no-follow directory opens")
    root = os.path.realpath(os.path.abspath(workspace_root or "."))
    raw = os.fspath(path)
    if not raw or "\x00" in raw:
        raise ValueError("empty or invalid snapshot path")
    if ".." in raw.split(os.sep):
        raise ValueError("snapshot path contains parent traversal")
    candidate = raw if os.path.isabs(raw) else os.path.join(root, raw)
    candidate = os.path.normpath(candidate)
    if os.path.commonpath((root, candidate)) != root or candidate == root:
        raise ValueError("snapshot path is outside the workspace")
    relative = os.path.relpath(candidate, root)
    parts = relative.split(os.sep)
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("snapshot path contains an unsafe component")

    dir_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    root_fd = os.open(os.sep, dir_flags)
    opened: list[int] = [root_fd]
    try:
        current = root_fd
        for part in root.strip(os.sep).split(os.sep):
            if not part:
                continue
            current = os.open(part, dir_flags, dir_fd=current)
            opened.append(current)
        for part in parts[:-1]:
            current = os.open(part, dir_flags, dir_fd=current)
            opened.append(current)
        file_fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_NONBLOCK", 0),
                          dir_fd=current)
        opened.append(file_fd)
        info = os.fstat(file_fd)
        if not stat_module.S_ISREG(info.st_mode):
            raise ValueError("snapshot candidate is not a regular file")
        tail_meta: dict[str, Any] = {}
        if tail:
            # Read a bounded suffix, then select the last 30 complete lines.
            # Very long logs remain bounded; metadata states when the byte cap
            # prevented reaching the beginning of the 30-line window.
            read_size = min(info.st_size, MAX_LOG_TAIL_READ_BYTES)
            os.lseek(file_fd, max(0, info.st_size - read_size), os.SEEK_SET)
            sample = os.read(file_fd, read_size)
            line_parts = sample.splitlines(keepends=True)
            selected_lines = line_parts[-MAX_LOG_TAIL_LINES:]
            selected = b"".join(selected_lines)
            line_window_truncated = len(line_parts) > len(selected_lines)
            read_cap_truncated = info.st_size > len(sample) and len(line_parts) < MAX_LOG_TAIL_LINES
            output_cap_truncated = len(selected) > text_limit
            if len(selected) > text_limit:
                selected = selected[-text_limit:]
            tail_meta = {
                "tail_line_limit": MAX_LOG_TAIL_LINES,
                "tail_lines_returned": len(selected_lines),
                "tail_truncated": bool(read_cap_truncated or output_cap_truncated or line_window_truncated),
                "tail_truncation_reasons": [reason for condition, reason in (
                    (read_cap_truncated, "read_byte_cap"),
                    (output_cap_truncated, "output_byte_cap"),
                    (line_window_truncated, "older_lines_omitted"),
                ) if condition],
                "tail_bytes_read": len(sample),
                "tail_bytes_omitted_by_output_cap": max(0, len(b"".join(selected_lines)) - len(selected)),
            }
            sample = selected
        else:
            sample = os.read(file_fd, min(max(text_limit, binary_limit), MAX_TEXT_EXCERPT))
        is_binary = b"\x00" in sample or sum(byte < 9 or 13 < byte < 32 for byte in sample) > max(2, len(sample) // 20)
        excerpt_bytes = sample[:binary_limit if is_binary else text_limit]
        excerpt = excerpt_bytes.hex() if is_binary else excerpt_bytes.decode("utf-8", "replace")
        parent_names = sorted(os.listdir(current))[:MAX_RECENT_FILES]
        return {
            "exit_code": 0,
            "stat": f"{candidate}|regular file|{info.st_size}|{int(info.st_mtime)}",
            "file_type": "data (binary)" if is_binary else "text",
            "excerpt": excerpt,
            "excerpt_format": "hex" if is_binary else "text",
            "parent_listing": parent_names,
            **tail_meta,
        }
    finally:
        for fd in reversed(opened):
            try:
                os.close(fd)
            except OSError:
                pass


def secure_local_recent_files(*, workspace_root: str, marker: str,
                               limit: int = MAX_RECENT_FILES) -> list[str]:
    """Find recent regular files with a bounded, no-follow descriptor walk."""
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
        raise OSError("platform lacks no-follow directory opens")
    root = os.path.realpath(os.path.abspath(workspace_root or "."))
    threshold = os.stat(marker, follow_symlinks=False).st_mtime
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    root_fd = os.open(os.sep, flags)
    opened = [root_fd]
    results: list[str] = []
    visited = 0
    try:
        current = root_fd
        for part in root.strip(os.sep).split(os.sep):
            if part:
                current = os.open(part, flags, dir_fd=current)
                opened.append(current)
        stack: list[tuple[int, str, int]] = [(current, "", 0)]
        while stack and len(results) < limit and visited < 5000:
            directory_fd, prefix, depth = stack.pop()
            if depth > 16:
                continue
            with os.scandir(directory_fd) as entries:
                for entry in entries:
                    visited += 1
                    if visited > 5000:
                        break
                    rel = f"{prefix}/{entry.name}" if prefix else entry.name
                    try:
                        info = entry.stat(follow_symlinks=False)
                    except OSError:
                        continue
                    if stat_module.S_ISREG(info.st_mode) and info.st_mtime > threshold:
                        results.append(f"{root}/{rel}")
                        if len(results) >= limit:
                            break
                    elif stat_module.S_ISDIR(info.st_mode):
                        try:
                            child_fd = os.open(entry.name, flags, dir_fd=directory_fd)
                        except OSError:
                            continue
                        opened.append(child_fd)
                        stack.append((child_fd, rel, depth + 1))
        return results
    finally:
        for fd in reversed(opened):
            try:
                os.close(fd)
            except OSError:
                pass


def _command(name: str, *args: str) -> str:
    command = " ".join([name, *(shlex.quote(str(arg)) for arg in args)])
    if not validate_read_only_command(command):
        raise ValueError("snapshot command was rejected by the fixed read-only allow-list")
    return command


def _run(executor: Any, command: str, *, cwd: str, timeout_s: int = MAX_COMMAND_SECONDS) -> dict[str, Any]:
    if not validate_read_only_command(command):
        raise ValueError("snapshot command was rejected by the fixed read-only allow-list")
    started = time.monotonic()
    try:
        readonly = getattr(executor, "run_read_only_command", None)
        if not callable(readonly):
            raise RuntimeError("executor has no separate read-only snapshot channel")
        result = readonly(command, cwd=cwd, timeout_s=min(MAX_COMMAND_SECONDS, timeout_s))
        stdout = str(getattr(result, "stdout", "") or "")
        stderr = str(getattr(result, "stderr", "") or "")
        code = int(getattr(result, "exit_code", getattr(result, "returncode", 0)) or 0)
    except Exception as exc:
        stdout, stderr, code = "", f"{type(exc).__name__}: {exc}", 127
    return {"command": command, "exit_code": code, "stdout": stdout[:6000], "stderr": stderr[:2000],
            "elapsed_s": round(max(0.0, time.monotonic() - started), 6)}


def capture_state_snapshot(*, executor: Any, workspace_root: str, task_text: str,
                           ledger: Any, taken_at_unix_s: float, elapsed_fraction: float,
                           step: int = 0, run_start_marker: str | None = None,
                           run_started_monotonic: float | None = None,
                           deadline_sec: float | None = None) -> dict[str, Any]:
    """Collect a read-only, size-bounded snapshot through a background executor channel."""
    started = time.monotonic()
    observed_at_unix_s = time.time()
    deadline = started + MAX_SNAPSHOT_SECONDS
    root = str(workspace_root or ".")
    task_paths = extract_task_paths(task_text)
    writes = _paths_from_receipts(ledger, root)
    commands: list[dict[str, Any]] = []
    path_resolution: list[dict[str, Any]] = []
    path_rows: list[dict[str, Any]] = []
    channel = ThreadPoolExecutor(max_workers=1, thread_name_prefix="aether-readonly-snapshot-channel")

    def run(command: str, *, cwd: str = root) -> dict[str, Any]:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return {"command": command, "exit_code": 124, "stdout": "", "stderr": "snapshot deadline reached", "elapsed_s": 0.0}
        future = channel.submit(_run, executor, command, cwd=cwd,
                                timeout_s=max(1, min(MAX_COMMAND_SECONDS, math.ceil(remaining))))
        command_started_wall = time.time()
        try:
            result = future.result(timeout=min(float(MAX_COMMAND_SECONDS), remaining))
            result["started_at_unix_s"] = round(command_started_wall, 3)
            result["completed_at_unix_s"] = round(time.time(), 3)
            return result
        except FutureTimeout:
            future.cancel()
            return {"command": command, "exit_code": 124, "stdout": "", "stderr": "snapshot command exceeded remaining wall budget", "elapsed_s": round(MAX_SNAPSHOT_SECONDS, 6),
                    "started_at_unix_s": round(command_started_wall, 3), "completed_at_unix_s": round(time.time(), 3)}

    def read_candidate(path: str, *, tail: bool = False) -> dict[str, Any]:
        command_started_wall = time.time()
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            result = {"exit_code": 124, "error": "snapshot deadline reached"}
        else:
            reader = getattr(executor, "read_state_snapshot_file", None)
            if not callable(reader):
                result = {"exit_code": 127, "error": "executor has no atomic snapshot file reader"}
            else:
                future = channel.submit(reader, path, workspace_root=root, tail=tail)
                try:
                    result = future.result(timeout=min(float(MAX_COMMAND_SECONDS), remaining))
                except FutureTimeout:
                    future.cancel()
                    result = {"exit_code": 124, "error": "atomic snapshot file read exceeded wall budget"}
                except Exception as exc:
                    result = {"exit_code": 127, "error": f"{type(exc).__name__}: {exc}"[:500]}
        elapsed = max(0.0, time.time() - command_started_wall)
        command_row = {"command": str(result.get("command") or "secure_workspace_file_read"),
                       "path": str(path)[:300],
                       "exit_code": int(result.get("exit_code", 127)),
                       "stderr": str(result.get("error", ""))[:500],
                       "started_at_unix_s": round(command_started_wall, 3),
                       "completed_at_unix_s": round(time.time(), 3),
                       "elapsed_s": round(elapsed, 6)}
        for key in ("command_sha256", "command_args"):
            if key in result:
                command_row[key] = result[key]
        commands.append(command_row)
        return result

    path_candidates = [(p, "task_text") for p in task_paths] + [(p, "write_receipt") for p in writes]
    for path, source in path_candidates:
        if time.monotonic() - started >= MAX_SNAPSHOT_SECONDS or len(path_rows) >= 2 * MAX_PATHS:
            break
        absolute = _workspace_path_bounded(path, root, executor, path_resolution, channel, deadline)
        if absolute is None:
            continue
        inspected = read_candidate(path)
        if inspected.get("exit_code") != 0:
            continue
        path_rows.append({"path": path, "source": source, "stat": inspected["stat"],
                          "file_type": inspected["file_type"], "excerpt": inspected["excerpt"],
                          "excerpt_format": inspected["excerpt_format"],
                          "parent_listing": inspected["parent_listing"]})
    system = [run(_command("ps", "-eo", "pid,ppid,etime,stat,args"))]
    process_lines = system[0]["stdout"].splitlines()
    visible_processes = [line for line in process_lines
                         if not re.search(r"^\s*(?:1|2)\s", line)
                         and not re.search(r"aether|harbor.*(runner|worker)|thin_loop\.py", line, re.I)]
    started_commands = []
    for receipt in ledger.all_receipts():
        payload = receipt.payload if isinstance(receipt.payload, Mapping) else {}
        command_text = str(payload.get("command", ""))
        if re.search(r"\bnohup\b|(?:^|\s)&\s*$|\bdisown\b", command_text):
            started_commands.append(command_text[:240])
    system[0]["stdout"] = "\n".join(visible_processes)
    system[0]["model_started_command_hints"] = started_commands[-MAX_RECENT_WRITES:]
    ss = run(_command("ss", "-ltnp"))
    if ss["exit_code"] != 0:
        ss = run(_command("cat", "/proc/net/tcp"))
    system.append(ss)
    recent_changes: dict[str, Any]
    if run_start_marker:
        walker = getattr(executor, "list_recent_state_snapshot_files", None)
        remaining = deadline - time.monotonic()
        if callable(walker) and remaining > 0:
            wall = time.time()
            future = channel.submit(walker, workspace_root=root, marker=run_start_marker,
                                    limit=MAX_RECENT_FILES)
            try:
                walked = future.result(timeout=min(float(MAX_COMMAND_SECONDS), remaining))
                recent = walked.get("paths", []) if isinstance(walked, Mapping) else walked
                invocation = walked.get("command", "secure_workspace_recent_walk") if isinstance(walked, Mapping) else "secure_workspace_recent_walk"
                commands.append({"command": invocation, "exit_code": 0, "stdout": "",
                                 "stderr": "", "started_at_unix_s": round(wall, 3),
                                 "completed_at_unix_s": round(time.time(), 3),
                                 "elapsed_s": round(max(0.0, time.time() - wall), 6)})
                if isinstance(walked, Mapping):
                    commands[-1].update({key: walked[key] for key in ("command_sha256", "command_args")
                                         if key in walked})
                recent_changes = {"status": "captured", "paths": [str(row)[:500] for row in recent[:MAX_RECENT_FILES]]}
            except Exception as exc:
                future.cancel()
                commands.append({"command": "secure_workspace_recent_walk", "exit_code": 127,
                                 "stdout": "", "stderr": f"{type(exc).__name__}: {exc}"[:300],
                                 "started_at_unix_s": round(wall, 3), "completed_at_unix_s": round(time.time(), 3),
                                 "elapsed_s": round(max(0.0, time.time() - wall), 6)})
                recent_changes = {"status": "unavailable", "reason": "safe_workspace_tree_walk_failed", "paths": []}
        else:
            recent_changes = {"status": "unavailable", "reason": "safe_workspace_tree_walk_unavailable", "paths": []}
    else:
        recent_changes = {"status": "unavailable", "reason": "run_start_marker_not_provided", "paths": []}
    commands.extend(system)
    # Add redirected log tails using the same fixed tail command.
    for receipt in ledger.all_receipts():
        if time.monotonic() >= deadline:
            break
        payload = receipt.payload if isinstance(receipt.payload, Mapping) else {}
        command_text = str(payload.get("command", ""))
        for match in re.finditer(r"(?:2>>|2>|>>|&>|>)\s*([^\s;&|]+)", command_text):
            path = match.group(1).strip("'\"`")
            if not path or path in {"/dev/null", "-"}:
                continue
            if _workspace_path_bounded(path, root, executor, path_resolution, channel, deadline) is None:
                continue
            inspected = read_candidate(path, tail=True)
            if inspected.get("exit_code") == 0:
                commands.append({
                    "command": "secure_workspace_log_tail",
                    "path": path[:300], "exit_code": 0,
                    "stdout": str(inspected.get("excerpt", ""))[-MAX_TEXT_EXCERPT:],
                    "stderr": "", "started_at_unix_s": commands[-1].get("started_at_unix_s"),
                    "completed_at_unix_s": commands[-1].get("completed_at_unix_s"),
                    "elapsed_s": commands[-1].get("elapsed_s", 0.0),
                    **{key: inspected[key] for key in (
                        "tail_line_limit", "tail_lines_returned", "tail_truncated",
                        "tail_truncation_reasons", "tail_bytes_read",
                        "tail_bytes_omitted_by_output_cap") if key in inspected},
                })
    observation_completed_at_unix_s = time.time()
    observation_completed_mono = time.monotonic()
    # Keep the complete command manifest and outputs within the persisted cap.
    observed_fraction = (max(0.0, (started - run_started_monotonic) / deadline_sec)
                         if run_started_monotonic is not None and deadline_sec and deadline_sec > 0
                         else float(elapsed_fraction))
    completed_fraction = (max(0.0, (observation_completed_mono - run_started_monotonic) / deadline_sec)
                          if run_started_monotonic is not None and deadline_sec and deadline_sec > 0
                          else observed_fraction)
    lateness_s = max(0.0, observed_at_unix_s - float(taken_at_unix_s))
    snapshot = {"schema": "aether.state_snapshot.v1", "step": int(step),
                "taken_at_unix_s": round(observed_at_unix_s, 3),
                "triggered_at_unix_s": round(float(taken_at_unix_s), 3),
                "elapsed_fraction": round(observed_fraction, 6),
                "capture_timing": {"observed_start_unix_s": round(observed_at_unix_s, 3),
                                   "observed_completion_unix_s": round(observation_completed_at_unix_s, 3),
                                   "scheduled_elapsed_fraction": round(float(elapsed_fraction), 6),
                                   "observed_elapsed_fraction": round(observed_fraction, 6),
                                   "observation_end_elapsed_fraction": round(completed_fraction, 6),
                                   "observation_window_s": round(max(0.0, observation_completed_mono - started), 6),
                                   "lateness_s": round(lateness_s, 6),
                                   "status": "late" if lateness_s > 0.1 else "on_time"},
                "task_paths": task_paths, "write_paths": writes,
                "path_inventory": {"task_candidates": len(task_paths),
                                   "task_captured": sum(row["source"] == "task_text" for row in path_rows),
                                   "write_candidates": len(writes),
                                   "write_captured": sum(row["source"] == "write_receipt" for row in path_rows),
                                   "truncated": len(path_rows) < len(path_candidates)},
                "paths": path_rows, "processes": system[0], "listening_services": system[1],
                "recent_changes": recent_changes, "commands": commands,
                "path_resolution": path_resolution}
    def encode() -> bytes:
        return json.dumps(snapshot, sort_keys=True, ensure_ascii=False, default=str).encode()
    try:
        snapshot["elapsed_s"] = round(max(0.0, time.monotonic() - started), 6)
        for limit in (512, 128, 0):
            if len(encode()) <= MAX_SNAPSHOT_BYTES:
                break
            for row in commands:
                row["stdout"] = row.get("stdout", "")[:limit]
                row["stderr"] = row.get("stderr", "")[:min(limit, 256)]
            for row in path_resolution:
                row["stdout"] = row.get("stdout", "")[:limit]
                row["stderr"] = row.get("stderr", "")[:min(limit, 256)]
            for row in path_rows:
                row["excerpt"] = row.get("excerpt", "")[:limit]
                row["parent_listing"] = row.get("parent_listing", [])[:10]
        if len(encode()) > MAX_SNAPSHOT_BYTES:
            # Retain every command/result envelope while dropping duplicated path views.
            snapshot["paths"] = []
            snapshot["task_paths"] = task_paths[:MAX_PATHS]
            snapshot["write_paths"] = writes[:MAX_RECENT_WRITES]
        encoded = encode()
        if len(encoded) > MAX_SNAPSHOT_BYTES:
            raise ValueError("state snapshot command inventory exceeds the 48 KB evidence bound")
        snapshot["total_bytes"] = len(encoded)
        snapshot["bounded"] = True
        final_size = len(encode())
        if final_size > MAX_SNAPSHOT_BYTES:
            raise ValueError("state snapshot exceeded the 48 KB serialized evidence bound")
        snapshot["total_bytes"] = final_size
        return snapshot
    finally:
        channel.shutdown(wait=False, cancel_futures=True)
