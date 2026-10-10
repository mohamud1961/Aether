"""Subprocess-backed Executor for Aether-Next against a real workspace directory."""
from __future__ import annotations

from dataclasses import replace
import fnmatch
import hashlib
import os
import platform
import pwd
import signal
import socket
import subprocess
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Mapping

from .artifact_plane import identify_file
from .evidence_finalization import export_content_addressed_files
from .execution import (
    ArtifactInspection,
    CommandResult,
    ProcessHandle,
    ProbeResult,
    JobProbeResult,
    TerminalReadResult,
    TerminalSessionHandle,
    TerminalSessionState,
)
from .runtime_ir import EnvMap, CapabilityDescriptor, normalize_relpath
from .host_terminal import HostTerminalManager
from .workspace_state import capture_workspace_state, diff_workspace_states


_STDOUT_CAP = 20_000
_STDERR_CAP = 20_000
# Full streams are kept inline up to this bound; beyond it the complete
# stream is spooled to disk and the inline text is a marked head+tail.
# Nothing is ever destroyed.
_INLINE_STREAM_CAP = 1_000_000
_SKIP_DIRS = {".git", "__pycache__", "node_modules", ".mypy_cache", ".pytest_cache"}
_MAX_SCAN_ENTRIES = 5_000


def _resolve_safe(
    workspace_root: str,
    path: str,
    *,
    for_write: bool = False,
) -> str:
    """Resolve one workspace path or fail closed on escape/symlink ambiguity.

    String-prefix checks are unsafe (``/app`` is a prefix of ``/app_evil``).
    Reads resolve the complete path and require it to remain beneath the real
    workspace root. Writes resolve the parent, reject a symlink destination,
    and require the resulting directory entry to remain beneath the root.
    """
    raw = str(path or "").strip()
    if not raw:
        raise PermissionError("empty workspace path")
    root = Path(workspace_root).resolve(strict=True)
    if raw == "/app" or raw.startswith("/app/"):
        try:
            norm = normalize_relpath(raw, "/app")
        except ValueError as exc:
            raise PermissionError(f"path escapes workspace: {raw}") from exc
        lexical = root / norm
    elif Path(raw).is_absolute():
        norm = raw
        lexical = Path(raw)
    else:
        try:
            norm = normalize_relpath(raw, workspace_root)
        except ValueError as exc:
            raise PermissionError(f"path escapes workspace: {raw}") from exc
        lexical = root / norm
    if lexical == root or norm in {"", "."}:
        candidate = root
    elif for_write:
        parent = lexical.parent.resolve(strict=False)
        try:
            parent.relative_to(root)
        except ValueError as exc:
            raise PermissionError(f"path escapes workspace: {raw}") from exc
        candidate = parent / lexical.name
        if candidate.is_symlink():
            raise PermissionError(f"refusing write through symlink: {raw}")
    else:
        candidate = lexical.resolve(strict=False)
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise PermissionError(f"path escapes workspace: {raw}") from exc
    return str(candidate)


def _truncate(text: str, cap: int) -> str:
    if len(text) <= cap:
        return text
    return text[:cap] + f"\n... [truncated at {cap} chars]"


def _decode_partial(raw: Any) -> str:
    """Decode captured subprocess output without losing invalid UTF-8 bytes."""
    if raw is None:
        return ""
    if isinstance(raw, bytes):
        return raw.decode("utf-8", "replace")
    return str(raw)


def _stream_bytes(raw: Any) -> bytes:
    if raw is None:
        return b""
    if isinstance(raw, bytes):
        return raw
    return str(raw).encode("utf-8", "replace")


def _merge_timeout_stream(partial: Any, final: Any) -> bytes:
    """Merge TimeoutExpired's prefix with post-kill pipe drainage once.

    Python/platform combinations differ: the second communicate() may return
    the complete stream or only bytes not already surfaced on TimeoutExpired.
    Preserve either representation without duplicating a shared prefix.
    """
    prefix = _stream_bytes(partial)
    suffix = _stream_bytes(final)
    if not prefix:
        return suffix
    if not suffix:
        return prefix
    if suffix.startswith(prefix):
        return suffix
    if prefix.startswith(suffix):
        return prefix
    max_overlap = min(len(prefix), len(suffix))
    for size in range(max_overlap, 0, -1):
        if prefix[-size:] == suffix[:size]:
            return prefix + suffix[size:]
    return prefix + suffix


def _run_captured_process(
    args: list[str],
    *,
    cwd: str,
    timeout_s: int,
    env: Mapping[str, str] | None = None,
) -> tuple[int, str, str, bool]:
    """Run one process group and truthfully drain output on timeout.

    ``subprocess.run`` kills only the immediate shell. Its descendants can
    retain stdout/stderr pipe descriptors, making partial output intermittently
    disappear or delaying cleanup. A private process group lets the executor
    terminate the whole command tree, then drain the pipes deterministically.
    """
    proc = subprocess.Popen(
        args,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
        env=(dict(env) if env is not None else None),
    )
    try:
        stdout_raw, stderr_raw = proc.communicate(timeout=timeout_s)
        return (
            int(proc.returncode or 0),
            _decode_partial(stdout_raw),
            _decode_partial(stderr_raw),
            False,
        )
    except subprocess.TimeoutExpired as exc:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (OSError, ProcessLookupError):
            try:
                proc.kill()
            except OSError:
                pass
        stdout_tail, stderr_tail = proc.communicate()
        stdout_raw = _merge_timeout_stream(exc.stdout, stdout_tail)
        stderr_raw = _merge_timeout_stream(exc.stderr, stderr_tail)
        return 124, _decode_partial(stdout_raw), _decode_partial(stderr_raw), True


def _parse_tcp_probe_target(target: str) -> tuple[str, int] | None:
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
    if any(ch not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-" for ch in clean_host):
        return None
    port = int(port_text)
    return (clean_host, port) if 0 < port <= 65535 else None


def _linux_listener_owner_pids(port: int) -> tuple[int, ...]:
    inodes: set[str] = set()
    for table in (Path("/proc/net/tcp"), Path("/proc/net/tcp6")):
        try:
            lines = table.read_text(encoding="utf-8").splitlines()[1:]
        except OSError:
            continue
        for line in lines:
            parts = line.split()
            if len(parts) < 10 or parts[3] != "0A":
                continue
            try:
                local_port = int(parts[1].rsplit(":", 1)[1], 16)
            except (IndexError, ValueError):
                continue
            if local_port == port:
                inodes.add(parts[9])
    owners: set[int] = set()
    if not inodes:
        return ()
    proc_root = Path("/proc")
    try:
        candidates = tuple(proc_root.iterdir())
    except OSError:
        return ()
    for candidate in candidates:
        if not candidate.name.isdigit():
            continue
        fd_dir = candidate / "fd"
        try:
            fds = tuple(fd_dir.iterdir())
        except OSError:
            continue
        for fd in fds:
            try:
                link = os.readlink(fd)
            except OSError:
                continue
            if link.startswith("socket:[") and link[8:-1] in inodes:
                owners.add(int(candidate.name))
                break
    return tuple(sorted(owners))


def _linux_pid_descends_from(pid: int, ancestor_pid: int) -> bool:
    current = int(pid)
    ancestor = int(ancestor_pid)
    seen: set[int] = set()
    while current > 1 and current not in seen:
        if current == ancestor:
            return True
        seen.add(current)
        try:
            fields = Path(f"/proc/{current}/stat").read_text(encoding="utf-8").split()
            current = int(fields[3])
        except (OSError, IndexError, ValueError):
            return False
    return current == ancestor


class StreamSpooler:
    """Truthful stream retention: full inline up to a cap, full spool beyond.

    ``finalize(stream_text, tag)`` returns ``(inline_text, overflow_path)``.
    When the stream fits the inline cap, it is returned verbatim with no
    overflow file.  When it exceeds the cap, the COMPLETE stream is written to
    a spool file and the inline text is a clearly marked head+tail excerpt.
    """

    def __init__(self, *, inline_cap: int = _INLINE_STREAM_CAP) -> None:
        self._inline_cap = max(1_000, int(inline_cap))
        self._spool_dir: str | None = None
        self._counter = 0

    def _ensure_dir(self) -> str:
        if self._spool_dir is None:
            import tempfile
            self._spool_dir = tempfile.mkdtemp(prefix="aether_output_spool_")
        return self._spool_dir

    def finalize(self, stream_text: str, tag: str) -> tuple[str, str]:
        if len(stream_text) <= self._inline_cap:
            return stream_text, ""
        directory = self._ensure_dir()
        self._counter += 1
        safe_tag = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in tag)[:60]
        path = os.path.join(directory, f"{self._counter:06d}_{safe_tag}.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(stream_text)
        half = self._inline_cap // 2
        omitted = len(stream_text) - (half * 2)
        inline = (
            stream_text[:half]
            + f"\n... [omitted {omitted} chars inline; full {len(stream_text)}-char stream spooled to {path}]\n"
            + stream_text[-half:]
        )
        return inline, path

    def overflow_paths(self) -> tuple[str, ...]:
        if self._spool_dir is None or not os.path.isdir(self._spool_dir):
            return ()
        return tuple(
            str(path)
            for path in sorted(Path(self._spool_dir).iterdir())
            if path.is_file()
        )

    def export_to(self, destination: str) -> dict[str, Any]:
        return export_content_addressed_files(self.overflow_paths(), destination)


def _snapshot_local_stats(
    root: str,
    *,
    max_entries: int = _MAX_SCAN_ENTRIES,
) -> tuple[dict[str, tuple[str, int, int, int, int, int, int]], bool]:
    """Return one bounded stat-only freshness inventory for task files.

    This is deliberately cheaper than the exact artifact/workspace hasher. It
    exists only to detect whether older evidence can still be considered fresh.
    Exact bytes are content-addressed when a file is actually inspected.
    """
    result: dict[str, tuple[str, int, int, int, int, int, int]] = {}
    limit = max(1, int(max_entries))
    seen = 0
    try:
        for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
            dirnames[:] = sorted(
                d for d in dirnames
                if d not in _SKIP_DIRS and not (Path(dirpath) / d).is_symlink()
            )
            for fname in sorted(filenames):
                full = os.path.join(dirpath, fname)
                try:
                    info = os.lstat(full)
                except OSError:
                    continue
                seen += 1
                if seen > limit:
                    return result, True
                rel = os.path.relpath(full, root)
                kind = 'symlink' if os.path.islink(full) else 'file'
                result[rel] = (
                    kind,
                    int(info.st_size),
                    int(info.st_mtime_ns),
                    int(info.st_ctime_ns),
                    int(info.st_mode & 0o7777),
                    int(info.st_uid),
                    int(info.st_gid),
                )
    except OSError:
        return result, True
    return result, False


def _diff_local_stat_snapshots(
    before: tuple[dict[str, tuple[str, int, int, int, int, int, int]], bool],
    after: tuple[dict[str, tuple[str, int, int, int, int, int, int]], bool],
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], dict[str, Any]]:
    before_map, before_truncated = before
    after_map, after_truncated = after
    truncated = bool(before_truncated or after_truncated)
    produced = () if truncated else tuple(sorted(set(after_map) - set(before_map)))
    removed = () if truncated else tuple(sorted(set(before_map) - set(after_map)))
    modified = tuple(sorted(
        path for path in set(before_map) & set(after_map)
        if before_map[path] != after_map[path]
    ))
    state_delta = {
        'created_paths': list(produced),
        'removed_paths': list(removed),
        'content_changed_paths': [],
        'metadata_changed_paths': list(modified),
        'before_truncated': bool(before_truncated),
        'after_truncated': bool(after_truncated),
        'mutation_detection_status': 'truncated' if truncated else 'complete',
        'path_set_delta_status': 'unknown_due_truncation' if truncated else 'complete',
        'mutation_detection_basis': 'bounded_stat_kind_size_mtime_ctime_mode_uid_gid',
        'mutation_actor_status': 'mutation_actor_unknown',
        'mutation_actor_detail': (
            'change is bounded to this action interval; no subprocess actor is asserted'
        ),
    }
    return modified, produced, removed, state_delta


def _snapshot_mtimes(root: str) -> dict[str, float]:
    """Compatibility helper retained for older importers; not freshness authority."""
    stats, _truncated = _snapshot_local_stats(root)
    return {path: row[2] / 1_000_000_000 for path, row in stats.items()}



# Upper bound on captured bytes per background-job stream (disk and memory).
_JOB_CAPTURE_MAX_BYTES = 64 * 1024 * 1024


class SubprocessExecutor:
    """Real filesystem + subprocess executor within a workspace directory."""

    # This backend needs VerifierOverlay to bind each command to an explicit
    # disposable ``.command_*`` child. It does not own an activation-scoped
    # Docker/image snapshot, unlike HarborEnvironmentExecutor.
    supports_activation_scoped_verifier_snapshot = False

    def __init__(
        self,
        workspace_root: str,
        *,
        default_timeout_s: int = 120,
        default_env: Mapping[str, str] | None = None,
    ) -> None:
        self._root = str(Path(workspace_root).resolve())
        self._state_snapshot_marker: str | None = None
        self._default_timeout_s = max(1, default_timeout_s)
        self._default_env = dict(default_env) if default_env is not None else None
        self._processes: dict[str, subprocess.Popen[str]] = {}
        self._process_output_files: dict[str, tuple[Any, Any]] = {}
        self._process_output_locks: dict[str, threading.Lock] = {}
        self._process_output_threads: dict[str, tuple[threading.Thread, threading.Thread]] = {}
        self._process_output_final: dict[str, dict[str, str]] = {}
        self._process_output_full: dict[str, dict[str, Any]] = {}
        self._process_output_finalize_lock = threading.Lock()
        self._process_meta: dict[str, ProcessHandle] = {}
        self._process_workspace_state: dict[str, Any] = {}
        self._spooler = StreamSpooler()
        self._terminal_manager = HostTerminalManager(default_env=self._default_env)
        self._terminal_workspace_state: dict[str, Any] | None = None
        os.makedirs(self._root, exist_ok=True)

    def for_workspace(self, workspace_root: str) -> "SubprocessExecutor":
        """Return a new executor constrained to a trusted isolated workspace."""
        return SubprocessExecutor(
            workspace_root,
            default_timeout_s=self._default_timeout_s,
            default_env=self._default_env,
        )

    def run_independent_verifier_command(
        self,
        command: str,
        *,
        workspace_root: str,
        timeout_s: int = 30,
        fixture_contents: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        """Run PERSISTENT Verifier shell in private mount/PID/network namespaces.

        The already-created F78 command child remains the task filesystem
        authority.  This method only adds an independent OS execution world and
        binds that exact child to /app.  Failure to establish every namespace
        fails closed; there is no shared-world fallback.
        """
        metadata: dict[str, Any] = {
            "execution_isolation": "host_private_mount_pid_net_namespaces",
            "isolation_backend": "linux_unshare_mount_pid_net",
            "independent_isolation_verified": False,
            "isolation_cleanup_verified": False,
            "mount_namespace_private": False,
            "pid_namespace_private": False,
            "network_namespace_private": False,
            "network_scope": "isolated_namespace_no_parent_links",
            "world_domain_contract": {
                "filesystem_view": "task_workspace_snapshot",
                "parent_processes_preserved": False,
                "parent_network_namespace_preserved": False,
                "outbound_network_enabled": False,
            },
        }
        if platform.system() != "Linux":
            return {
                "error": "verifier_independent_isolation_unavailable: Linux namespaces required",
                "metadata": metadata,
            }
        if fixture_contents:
            return {
                "error": (
                    "verifier_independent_isolation_bound_fixtures_unsupported_by_subprocess_executor"
                ),
                "metadata": metadata,
            }
        child = Path(workspace_root).resolve(strict=False)
        root = Path(self._root).resolve(strict=False)
        if (
            child.parent != root.parent
            or not child.name.startswith(root.name + ".verifier_overlay_")
            or ".command_" not in child.name
            or not child.is_dir()
        ):
            return {
                "error": "verifier_independent_isolation_invalid_workspace_child",
                "metadata": metadata,
            }
        pristine = Path(str(child).split(".command_", 1)[0]).resolve(strict=False)
        if not pristine.is_dir():
            return {
                "error": "verifier_independent_isolation_pristine_overlay_missing",
                "metadata": metadata,
            }
        token = uuid.uuid4().hex
        parent_ids = {
            key: os.readlink(f"/proc/self/ns/{key}")
            for key in ("mnt", "pid", "net")
        }
        namespace_script = (
            'set -eu; token="$1"; child="$2"; solver="$3"; pristine="$4"; user="$5"; cmd="$6"; '
            'mkdir -p /app; mount --bind "$child" /app; '
            'mount --bind "$child" "$solver"; mount --bind "$child" "$pristine"; '
            'mount -t proc proc /proc; '
            'printf "%s\t%s\t%s\t%s\n" "$token" "$(readlink /proc/self/ns/mnt)" '
            '"$(readlink /proc/self/ns/pid)" "$(readlink /proc/self/ns/net)" >&2; '
            'cd /app; exec runuser -u "$user" -- bash -lc "$cmd"'
        )
        user = pwd.getpwuid(os.getuid()).pw_name
        effective_timeout = timeout_s if timeout_s > 0 else self._default_timeout_s
        result: CommandResult | None = None
        error = ""
        try:
            exit_code, raw_stdout, raw_stderr, timed_out = _run_captured_process(
                [
                    "sudo", "-n", "unshare",
                    "--mount", "--pid", "--net", "--fork", "--kill-child=KILL", "--propagation", "private",
                    "bash", "-c", namespace_script, "aether-f80",
                    token, str(child), str(root), str(pristine), user, command,
                ],
                cwd=str(child),
                timeout_s=effective_timeout,
                env=self._default_env,
            )
            if timed_out:
                raw_stderr += (
                    f"\n[harness] isolated verifier command timed out after {effective_timeout}s; "
                    "private process group terminated"
                )
            attestation = None
            clean_stderr_lines: list[str] = []
            for line in raw_stderr.splitlines(keepends=True):
                stripped = line.rstrip("\r\n")
                parts = stripped.split("\t")
                if len(parts) == 4 and parts[0] == token and attestation is None:
                    attestation = parts[1:]
                    continue
                clean_stderr_lines.append(line)
            raw_stderr = "".join(clean_stderr_lines)
            if attestation is None:
                metadata.update({
                    "isolation_setup_exit_code": exit_code,
                    "isolation_setup_stderr_tail": raw_stderr[-1000:],
                })
            if attestation is not None:
                child_ids = dict(zip(("mnt", "pid", "net"), attestation))
                metadata.update({
                    "mount_namespace_private": child_ids["mnt"] != parent_ids["mnt"],
                    "pid_namespace_private": child_ids["pid"] != parent_ids["pid"],
                    "network_namespace_private": child_ids["net"] != parent_ids["net"],
                    "namespace_identity_sha256": hashlib.sha256(
                        "\0".join(child_ids[key] for key in ("mnt", "pid", "net")).encode("utf-8")
                    ).hexdigest(),
                })
            metadata["independent_isolation_verified"] = all(
                bool(metadata[key]) for key in (
                    "mount_namespace_private", "pid_namespace_private", "network_namespace_private",
                )
            )
            if not metadata["independent_isolation_verified"]:
                error = "verifier_independent_isolation_namespace_proof_failed"
            result = CommandResult(
                command=command,
                exit_code=exit_code,
                stdout=raw_stdout,
                stderr=raw_stderr,
                stdout_bytes_total=len(raw_stdout),
                stderr_bytes_total=len(raw_stderr),
                timed_out=timed_out,
            )
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            error = f"verifier_independent_isolation_setup_failed: {type(exc).__name__}: {exc}"
        finally:
            # Namespace resources are process-scoped. _run_captured_process
            # waits for normal exit or kills the complete isolated process
            # group on timeout, so no persistent namespace custody object is
            # left behind after this call returns.
            metadata["isolation_cleanup_verified"] = True
        if error or not metadata["independent_isolation_verified"] or not metadata["isolation_cleanup_verified"]:
            return {"error": error or "verifier_independent_isolation_not_verified", "metadata": metadata}
        return {"result": result, "metadata": metadata}

    def export_spools(self, destination: str) -> dict[str, Any]:
        manifest = self._spooler.export_to(destination)
        manifest["terminal_transcripts"] = self._terminal_manager.export_to(
            str(Path(destination) / "terminals")
        )
        return manifest

    def close(self) -> None:
        for process_id, proc in list(self._processes.items()):
            if proc.poll() is None:
                self.stop_process(process_id)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except (OSError, ProcessLookupError):
                    proc.kill()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    pass
            self._finalize_process_output(process_id, proc)
        self._processes.clear()
        self._process_meta.clear()
        self._process_workspace_state.clear()
        self._process_output_final.clear()
        self._terminal_manager.cleanup()

    def _terminal_delta(self) -> dict[str, Any]:
        current = _snapshot_local_stats(self._root)
        previous = self._terminal_workspace_state or current
        modified, produced, removed, delta = _diff_local_stat_snapshots(previous, current)
        del modified, produced, removed
        self._terminal_workspace_state = current
        return delta

    # ---- Filesystem --------------------------------------------------------

    def read_file(self, path: str) -> str:
        resolved = _resolve_safe(self._root, path)
        if not os.path.isfile(resolved):
            raise FileNotFoundError(resolved)
        with open(resolved, encoding="utf-8", errors="replace") as fh:
            return fh.read()

    def read_file_bytes(self, path: str) -> bytes:
        resolved = _resolve_safe(self._root, path)
        if not os.path.isfile(resolved):
            raise FileNotFoundError(resolved)
        with open(resolved, "rb") as fh:
            return fh.read()

    def write_file(self, path: str, content: str) -> None:
        resolved = _resolve_safe(self._root, path, for_write=True)
        os.makedirs(os.path.dirname(resolved), exist_ok=True)
        # The workspace is bind-mounted into a container that runs as root; a
        # run_command executed via docker exec can create/overwrite a file at
        # this path as root before this call runs. open(path, "w") then fails
        # with PermissionError even though this process owns the enclosing
        # directory, because overwriting an existing file's contents requires
        # write permission on the FILE (owner/group/other bits), not the
        # directory. Removing the directory entry first only requires write
        # permission on the parent directory, which this process always has
        # (it created the workspace) -- sidesteps the ownership mismatch
        # entirely without needing chmod/chown (which would themselves fail
        # for a file this process doesn't own).
        try:
            os.remove(resolved)
        except FileNotFoundError:
            pass
        with open(resolved, "w", encoding="utf-8") as fh:
            fh.write(content)

    def exists(self, path: str) -> bool:
        resolved = _resolve_safe(self._root, path)
        return os.path.exists(resolved)

    def glob(self, pattern: str) -> tuple[str, ...]:
        root_path = Path(self._root)
        matches: list[str] = []
        for dirpath, dirnames, filenames in os.walk(self._root):
            dirnames[:] = [
                d for d in dirnames
                if d not in _SKIP_DIRS and not (Path(dirpath) / d).is_symlink()
            ]
            for fname in filenames:
                full = os.path.join(dirpath, fname)
                rel = os.path.relpath(full, self._root)
                if fnmatch.fnmatch(rel, pattern):
                    matches.append(rel)
                if len(matches) >= _MAX_SCAN_ENTRIES:
                    break
        return tuple(sorted(matches))

    # ---- Command execution -------------------------------------------------

    def run_command(
        self,
        command: str,
        *,
        cwd: str | None = None,
        timeout_s: int = 30,
    ) -> CommandResult:
        effective_cwd = _resolve_safe(self._root, cwd or self._root)
        if not os.path.isdir(effective_cwd):
            raise NotADirectoryError(effective_cwd)
        effective_timeout = timeout_s if timeout_s > 0 else self._default_timeout_s

        command_started = time.monotonic()
        before = _snapshot_local_stats(self._root)

        exit_code, raw_stdout, raw_stderr, timed_out = _run_captured_process(
            ["bash", "-lc", command],
            cwd=effective_cwd,
            timeout_s=effective_timeout,
            env=self._default_env,
        )
        if timed_out:
            raw_stderr += (
                f"\n[harness] command timed out after {effective_timeout}s; "
                "partial output above is preserved"
            )

        stdout_total, stderr_total = len(raw_stdout), len(raw_stderr)
        stdout, stdout_overflow = self._spooler.finalize(raw_stdout, "stdout")
        stderr, stderr_overflow = self._spooler.finalize(raw_stderr, "stderr")

        after = _snapshot_local_stats(self._root)

        modified_sorted, produced_sorted, removed_sorted, state_delta = (
            _diff_local_stat_snapshots(before, after)
        )
        command_wall_time_s = max(0.0, time.monotonic() - command_started)

        return CommandResult(
            command=command,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            modified_paths=modified_sorted,
            produced_artifacts=produced_sorted,
            removed_paths=removed_sorted,
            state_delta=state_delta,
            metrics={"wall_time_s": command_wall_time_s},
            stdout_overflow_path=stdout_overflow,
            stderr_overflow_path=stderr_overflow,
            stdout_bytes_total=stdout_total,
            stderr_bytes_total=stderr_total,
            timed_out=timed_out,
        )

    def run_read_only_command(
        self, command: str, *, cwd: str | None = None, timeout_s: int = 5,
    ) -> CommandResult:
        """Execute one allow-listed snapshot command without solver-side accounting.

        This path avoids the shared workspace before/after diff and spool state,
        so a concurrent snapshot does not serialize or perturb solver actions.
        """
        from .challenger_runtime.state_snapshot import validate_read_only_command
        if not validate_read_only_command(command):
            raise ValueError("read-only executor refused a command outside the snapshot allow-list")
        effective_cwd = _resolve_safe(self._root, cwd or self._root)
        if not os.path.isdir(effective_cwd):
            raise NotADirectoryError(effective_cwd)
        code, stdout, stderr, timed_out = _run_captured_process(
            ["bash", "-lc", command], cwd=effective_cwd,
            timeout_s=max(1, min(5, int(timeout_s))), env=self._default_env,
        )
        return CommandResult(command=command, exit_code=code, stdout=stdout[:6000], stderr=stderr[:2000],
                             timed_out=timed_out)

    def resolve_state_snapshot_path(self, path: str, *, workspace_root: str | None = None,
                                    command_log: list[dict[str, Any]] | None = None) -> str | None:
        """Resolve a snapshot candidate against this executor's real workspace."""
        try:
            base = Path(_resolve_safe(self._root, workspace_root or self._root)).resolve(strict=False)
            candidate = Path(path)
            absolute = (candidate if candidate.is_absolute() else base / candidate).resolve(strict=False)
            absolute.relative_to(base)
            return str(absolute)
        except (OSError, RuntimeError, ValueError):
            return None

    def read_state_snapshot_file(self, path: str, *, workspace_root: str | None = None,
                                 tail: bool = False) -> dict[str, Any]:
        """Read one snapshot candidate through a no-follow workspace dirfd walk."""
        from .challenger_runtime.state_snapshot import secure_local_snapshot_read
        root = _resolve_safe(self._root, workspace_root or self._root)
        return secure_local_snapshot_read(path, workspace_root=root, tail=tail)

    def list_recent_state_snapshot_files(self, *, workspace_root: str | None = None,
                                         marker: str, limit: int = 50) -> list[str]:
        """Walk recent snapshot candidates under an opened, no-follow workspace root."""
        from .challenger_runtime.state_snapshot import secure_local_recent_files
        root = _resolve_safe(self._root, workspace_root or self._root)
        return secure_local_recent_files(workspace_root=root, marker=marker, limit=limit)

    def prepare_state_snapshot_marker(self) -> str:
        """Create an Aether-owned timestamp marker outside the task workspace."""
        if self._state_snapshot_marker:
            return self._state_snapshot_marker
        fd, path = tempfile.mkstemp(prefix="aether-state-runstart-")
        os.close(fd)
        self._state_snapshot_marker = path
        return path

    def cleanup_state_snapshot_marker(self) -> None:
        if self._state_snapshot_marker:
            Path(self._state_snapshot_marker).unlink(missing_ok=True)
            self._state_snapshot_marker = None

    def run_command_with_virtual_workspace(
        self,
        command: str,
        *,
        virtual_workspace_root: str = "/app",
        timeout_s: int = 30,
    ) -> CommandResult:
        """Run against this workspace through an isolated Linux bind mount.

        Frozen host replays have no native ``/app`` namespace.  Rather than
        pretending that absolute task paths work, use a private root mount
        namespace when the host explicitly supports it.  The mount dies with
        the child process, so neither the original workspace nor the host
        ``/app`` is mutated.  Unsupported hosts fail closed for this route.
        """
        if virtual_workspace_root != "/app" or platform.system() != "Linux":
            return CommandResult(
                command=command, exit_code=126,
                stderr="overlay_virtual_workspace_unavailable: isolated /app mount requires Linux",
            )
        user = pwd.getpwuid(os.getuid()).pw_name
        namespace_script = (
            'set -eu; mkdir -p /app; mount --bind "$1" /app; '
            'exec runuser -u "$2" -- bash -lc "$3"'
        )
        effective_timeout = timeout_s if timeout_s > 0 else self._default_timeout_s
        command_started = time.monotonic()
        before = _snapshot_local_stats(self._root)
        exit_code, raw_stdout, raw_stderr, timed_out = _run_captured_process(
            [
                "sudo", "-n", "unshare", "--mount", "--fork", "--propagation", "private",
                "bash", "-c", namespace_script, "aether-overlay", self._root, user, command,
            ],
            cwd=self._root,
            timeout_s=effective_timeout,
            env=self._default_env,
        )
        if timed_out:
            raw_stderr += (
                f"\n[harness] virtual-workspace command timed out after {effective_timeout}s"
            )
        if exit_code != 0 and "sudo:" in raw_stderr:
            raw_stderr = "overlay_virtual_workspace_unavailable: " + raw_stderr
        stdout_total, stderr_total = len(raw_stdout), len(raw_stderr)
        stdout, stdout_overflow = self._spooler.finalize(raw_stdout, "stdout")
        stderr, stderr_overflow = self._spooler.finalize(raw_stderr, "stderr")
        after = _snapshot_local_stats(self._root)
        modified, produced, removed, state_delta = _diff_local_stat_snapshots(before, after)
        command_wall_time_s = max(0.0, time.monotonic() - command_started)
        return CommandResult(
            command=command, exit_code=exit_code, stdout=stdout, stderr=stderr,
            modified_paths=modified, produced_artifacts=produced, removed_paths=removed,
            state_delta=state_delta, metrics={"wall_time_s": command_wall_time_s},
            stdout_overflow_path=stdout_overflow, stderr_overflow_path=stderr_overflow,
            stdout_bytes_total=stdout_total, stderr_bytes_total=stderr_total,
            timed_out=timed_out,
        )

    # ---- Persistent terminal sessions ---------------------------------------

    def start_terminal_session(
        self, name: str, command: str, *, cwd: str | None = None
    ) -> TerminalSessionHandle:
        effective_cwd = _resolve_safe(self._root, cwd or self._root)
        if not os.path.isdir(effective_cwd):
            raise NotADirectoryError(effective_cwd)
        self._terminal_workspace_state = _snapshot_local_stats(self._root)
        handle = self._terminal_manager.start(name, command, cwd=effective_cwd)
        return replace(handle, state_delta=self._terminal_delta())

    def terminal_send(
        self, session_id: str, data: str, *, append_newline: bool = True
    ) -> TerminalSessionState:
        state = self._terminal_manager.send(
            session_id, data, append_newline=append_newline
        )
        return replace(state, state_delta=self._terminal_delta())

    def terminal_read(
        self, session_id: str, *, max_bytes: int = 20_000, wait_ms: int = 1000
    ) -> TerminalReadResult:
        result = self._terminal_manager.read(
            session_id, max_bytes=max_bytes, wait_ms=wait_ms
        )
        return replace(result, state_delta=self._terminal_delta())

    def terminal_wait(
        self, session_id: str, *, timeout_s: float = 30.0
    ) -> TerminalSessionState:
        state = self._terminal_manager.wait(session_id, timeout_s=timeout_s)
        return replace(state, state_delta=self._terminal_delta())

    def terminal_interrupt(self, session_id: str) -> TerminalSessionState:
        state = self._terminal_manager.interrupt(session_id)
        return replace(state, state_delta=self._terminal_delta())

    def terminal_close(self, session_id: str) -> TerminalSessionState:
        state = self._terminal_manager.close(session_id)
        return replace(state, state_delta=self._terminal_delta())

    # ---- Process management ------------------------------------------------

    def launch_process(
        self,
        name: str,
        command: str,
        *,
        interactive: bool = False,
        cwd: str | None = None,
    ) -> ProcessHandle:
        effective_cwd = cwd or self._root
        process_id = f"proc-{uuid.uuid4().hex[:8]}"
        workspace_before = _snapshot_local_stats(self._root)

        stdout_file = tempfile.TemporaryFile(mode="w+b")
        stderr_file = tempfile.TemporaryFile(mode="w+b")
        try:
            proc = subprocess.Popen(
                ["bash", "-lc", command],
                cwd=effective_cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
                env=(dict(self._default_env) if self._default_env is not None else None),
            )
        except OSError as exc:
            stdout_file.close()
            stderr_file.close()
            return ProcessHandle(
                process_id=process_id,
                name=name,
                command=command,
                interactive=interactive,
                live=False,
                detail=f"launch failed: {exc}",
            )

        self._processes[process_id] = proc
        self._process_output_files[process_id] = (stdout_file, stderr_file)
        output_lock = threading.Lock()
        self._process_output_locks[process_id] = output_lock
        assert proc.stdout is not None and proc.stderr is not None
        def drain(source: Any, target: Any) -> None:
            try:
                while True:
                    # Read whatever the pipe has available. readline() can hold a
                    # completed short line behind a subsequent very long line
                    # without a newline, hiding useful progress until that line
                    # finishes.
                    chunk = os.read(source.fileno(), 64 * 1024)
                    if not chunk:
                        break
                    with output_lock:
                        target.seek(0, os.SEEK_END)
                        room = _JOB_CAPTURE_MAX_BYTES - target.tell()
                        if room > 0:
                            target.write(chunk[:room])
                            target.flush()
                        # Past the cap: keep draining so the job never blocks on a
                        # full pipe, but discard the bytes (bounded disk and memory).
            except (OSError, ValueError):
                # Executor shutdown may close a pipe to unblock a stuck drain.
                pass
            finally:
                source.close()
        threads = tuple(
            threading.Thread(target=drain, args=(source, target), daemon=True)
            for source, target in zip((proc.stdout, proc.stderr), (stdout_file, stderr_file))
        )
        self._process_output_threads[process_id] = threads
        for thread in threads:
            thread.start()
        command_sha256 = hashlib.sha256(command.encode("utf-8")).hexdigest()
        generation = hashlib.sha256(
            f"subprocess\0{process_id}\0{proc.pid}\0{command_sha256}".encode("utf-8")
        ).hexdigest()[:24]
        handle = ProcessHandle(
            process_id=process_id,
            name=name,
            command=command,
            interactive=interactive,
            live=True,
            endpoint=f"pid://{proc.pid}",
            detail=f"started pid={proc.pid}",
            pid=proc.pid,
            command_sha256=command_sha256,
            process_generation=generation,
            status="running",
        )
        self._process_meta[process_id] = handle
        self._process_workspace_state[process_id] = workspace_before
        return handle

    def observe_process_state(self, target: str) -> dict[str, Any]:
        _proc, meta = self._find_process(target)
        if meta is None:
            return {}
        current = _snapshot_local_stats(self._root)
        previous = self._process_workspace_state.get(meta.process_id, current)
        _modified, _produced, _removed, delta = _diff_local_stat_snapshots(previous, current)
        self._process_workspace_state[meta.process_id] = current
        delta["mutation_detection_scope"] = "managed_process_async_workspace_effects"
        return delta

    def probe_process(self, target: str) -> ProbeResult:
        tcp_target = _parse_tcp_probe_target(target)
        if tcp_target is not None:
            return self._probe_tcp_endpoint(target, *tcp_target)
        proc, meta = self._find_process(target)
        if proc is None:
            return ProbeResult(
                target=target,
                live=False,
                detail="not found",
                service_name=target,
            )
        alive = proc.poll() is None
        return ProbeResult(
            target=target,
            live=alive,
            detail=f"pid={proc.pid} {'alive' if alive else 'exited'}",
            service_name=meta.name if meta else target,
            process_id=meta.process_id if meta else "",
            process_generation=meta.process_generation if meta else "",
            process_generation_verified=bool(meta and meta.process_generation),
            endpoint_owner_pids=((proc.pid,) if alive else ()),
        )

    def _probe_tcp_endpoint(self, target: str, host: str, port: int) -> ProbeResult:
        try:
            with socket.create_connection((host, port), timeout=2.0):
                live = True
                connect_detail = "tcp connect succeeded"
        except OSError as exc:
            live = False
            connect_detail = f"tcp connect failed: {exc}"
        owner_pids = _linux_listener_owner_pids(port) if live else ()
        owner_proc: subprocess.Popen[str] | None = None
        owner_meta: ProcessHandle | None = None
        if live and owner_pids:
            for process_id, meta in reversed(tuple(self._process_meta.items())):
                proc = self._processes.get(process_id)
                if proc is None or proc.poll() is not None:
                    continue
                if any(_linux_pid_descends_from(pid, proc.pid) for pid in owner_pids):
                    owner_proc, owner_meta = proc, meta
                    break
        return ProbeResult(
            target=target,
            live=live,
            detail=(
                f"{connect_detail}; owner_pids={list(owner_pids)}"
                if live else connect_detail
            ),
            service_name=(owner_meta.name if owner_meta is not None else target),
            process_id=(owner_meta.process_id if owner_meta is not None else ""),
            process_generation=(owner_meta.process_generation if owner_meta is not None else ""),
            process_generation_verified=bool(
                live and owner_proc is not None and owner_meta is not None
                and owner_proc.poll() is None and owner_meta.process_generation
            ),
            endpoint_owner_pids=owner_pids,
        )

    def probe_job(self, target: str) -> JobProbeResult:
        proc, meta = self._find_process(target)
        if proc is None or meta is None:
            return JobProbeResult(
                target=target, found=False, status="unknown", completed=False,
                detail="no registered job generation",
            )
        exit_code = proc.poll()
        status = "running" if exit_code is None else ("completed" if exit_code == 0 else "failed")
        if exit_code is not None:
            self._finalize_process_output(meta.process_id, proc)
        return JobProbeResult(
            target=target, found=True, status=status,
            completed=exit_code is not None,
            succeeded=(None if exit_code is None else exit_code == 0),
            exit_code=exit_code,
            detail=f"pid={proc.pid} status={status}" + ("" if exit_code is None else f" exit_code={exit_code}"),
            job_id=meta.process_id, process_id=meta.process_id,
            process_generation=meta.process_generation,
            process_generation_verified=bool(meta.process_generation),
            lifecycle_authority="host_process_handle", pid=proc.pid,
        )

    def job_output(self, target: str, *, tail_lines: int = 40) -> dict[str, str]:
        proc, meta = self._find_process(target)
        if proc is None or meta is None:
            return {"stdout": "", "stderr": ""}
        if proc.poll() is not None:
            self._finalize_process_output(meta.process_id, proc)
        count = max(1, min(200, int(tail_lines)))
        final = self._process_output_final.get(meta.process_id)
        if final is not None:
            return {key: "\n".join(final.get(key, "").splitlines()[-count:])
                    for key in ("stdout", "stderr")}
        streams = self._process_output_files.get(meta.process_id)
        if streams is None:
            return {"stdout": "", "stderr": ""}
        result: dict[str, str] = {}
        for name, stream in zip(("stdout", "stderr"), streams):
            with self._process_output_locks.get(meta.process_id, threading.Lock()):
                stream.flush()
                stream.seek(0, os.SEEK_END)
                stream.seek(max(0, stream.tell() - 1024 * 1024), os.SEEK_SET)
                lines = stream.read().splitlines()
            result[name] = b"\n".join(lines[-count:]).decode("utf-8", "replace")
        return result

    def job_output_full(self, target: str) -> dict[str, Any]:
        """Complete captured output of a finished job under the normal stream policy.

        Same inline cap / spool behaviour as ``run_command``; unlike
        ``job_output`` this is not a line tail. Meant for completed jobs.
        """
        proc, meta = self._find_process(target)
        empty: dict[str, Any] = {"stdout": "", "stderr": "", "stdout_overflow_path": "",
            "stderr_overflow_path": "", "stdout_bytes_total": 0, "stderr_bytes_total": 0}
        if proc is None or meta is None:
            return empty
        if proc.poll() is not None:
            self._finalize_process_output(meta.process_id, proc)
        return dict(self._process_output_full.get(meta.process_id, empty))

    def _finalize_process_output(self, process_id: str, proc: subprocess.Popen[str]) -> None:
        """Close completed process pipes/spools while retaining bounded readable tails."""
        with self._process_output_finalize_lock:
            if process_id in self._process_output_final:
                return
            threads = self._process_output_threads.get(process_id, ())
            for thread in threads:
                thread.join(timeout=0.25)
            lock = self._process_output_locks.get(process_id)
            streams = self._process_output_files.pop(process_id, None)
            tails: dict[str, str] = {"stdout": "", "stderr": ""}
            if streams is not None:
                for name, stream in zip(("stdout", "stderr"), streams):
                    acquired = False
                    try:
                        if lock is not None:
                            lock.acquire()
                            acquired = True
                        stream.flush()
                        stream.seek(0)
                        full_text = stream.read(_JOB_CAPTURE_MAX_BYTES).decode("utf-8", "replace")
                        inline, overflow = self._spooler.finalize(full_text, name)
                        full = self._process_output_full.setdefault(process_id, {})
                        full.update({name: inline, f"{name}_overflow_path": overflow,
                            f"{name}_bytes_total": len(full_text)})
                        stream.seek(0, os.SEEK_END)
                        end = stream.tell()
                        stream.seek(max(0, end - 1024 * 1024), os.SEEK_SET)
                        data = stream.read()
                        lines = data.splitlines()[-200:]
                        tails[name] = b"\n".join(lines)[-64 * 1024:].decode("utf-8", "replace")
                    except (OSError, ValueError):
                        pass
                    finally:
                        if acquired and lock is not None:
                            lock.release()
                        try:
                            stream.close()
                        except OSError:
                            pass
            for source in (proc.stdout, proc.stderr):
                if source is not None:
                    try:
                        source.close()
                    except OSError:
                        pass
            self._process_output_threads.pop(process_id, None)
            self._process_output_locks.pop(process_id, None)
            self._process_output_final[process_id] = tails

    def stop_process(self, target: str) -> bool:
        proc, _meta = self._find_process(target)
        if proc is None:
            return False
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except (OSError, ProcessLookupError):
            try:
                proc.terminate()
            except OSError:
                pass
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                proc.kill()
            except OSError:
                pass
        return True

    def _find_process(
        self, target: str
    ) -> tuple[subprocess.Popen[str] | None, ProcessHandle | None]:
        if target in self._processes:
            return self._processes[target], self._process_meta.get(target)
        for pid, meta in self._process_meta.items():
            if meta.name == target:
                return self._processes.get(pid), meta
        return None, None

    # ---- Artifact inspection -----------------------------------------------

    def inspect_artifact(self, path: str, mode: str) -> ArtifactInspection:
        resolved = _resolve_safe(self._root, path)
        if not os.path.exists(resolved):
            return ArtifactInspection(
                path=path,
                mode=mode,
                success=False,
                detail=f"file not found: {path}",
            )

        metadata: dict[str, Any] = {}
        try:
            identity = identify_file(
                resolved,
                logical_path=path,
                source="aether:SubprocessExecutor",
            )
            metadata.update({
                "artifact_identity": identity.as_dict(),
                "sha256": identity.sha256,
                "size_bytes": identity.bytes,
                "media_type": identity.media_type,
                "artifact_handle": identity.handle,
                "content_addressed": True,
            })
        except OSError as exc:
            return ArtifactInspection(
                path=path, mode=mode, success=False, metadata=metadata,
                detail=f"artifact identity failed: {exc}",
            )

        text_modes = {"text", "json", "csv", "html", "source"}
        if mode in text_modes or not mode:
            try:
                with open(resolved, encoding="utf-8", errors="replace") as fh:
                    content = fh.read(100_000)
                metadata["backend"] = "basic"
                metadata["chars_read"] = len(content)
                return ArtifactInspection(
                    path=path,
                    mode=mode or "text",
                    success=True,
                    extracted_text=_truncate(content, _STDOUT_CAP),
                    metadata=metadata,
                    detail=f"inspected {path} ({len(content)} chars)",
                )
            except OSError as exc:
                return ArtifactInspection(
                    path=path,
                    mode=mode,
                    success=False,
                    metadata=metadata,
                    detail=f"read error: {exc}",
                )

        # Binary / unknown mode: size + first-bytes preview. This is useful
        # metadata, not semantic content. If the caller asked for an image/OCR
        # style preview, report the semantic capability gap explicitly so the
        # solver does not loop on a "successful" non-observation.
        metadata["backend"] = "basic"
        try:
            with open(resolved, "rb") as fh:
                head = fh.read(256)
            preview = head.hex(" ", 1)[:200]
            metadata["head_hex"] = preview
            metadata["semantic_content_available"] = False
            metadata["semantic_content_status"] = (
                "metadata_only: no semantic extractor is wired for this mode"
            )
            metadata_only_modes = {
                "auto", "preview", "image", "image_semantic", "ocr", "pdf", "frames"
            }
            metadata_only = (mode or "").strip().lower() in metadata_only_modes
            return ArtifactInspection(
                path=path,
                mode=mode,
                success=not metadata_only,
                extracted_text="",
                metadata=metadata,
                detail=(
                    f"metadata-only inspection of {path} "
                    f"({metadata.get('size_bytes', '?')} bytes); semantic content unavailable"
                    if metadata_only
                    else f"binary metadata for {path} ({metadata.get('size_bytes', '?')} bytes)"
                ),
            )
        except OSError as exc:
            return ArtifactInspection(
                path=path,
                mode=mode,
                success=False,
                metadata=metadata,
                detail=f"read error: {exc}",
            )

    # ---- EnvMap refresh ----------------------------------------------------

    def refresh_envmap(self, envmap: EnvMap) -> EnvMap:
        visible_files: list[str] = []
        visible_dirs: list[str] = []
        count = 0
        for dirpath, dirnames, filenames in os.walk(self._root):
            dirnames[:] = [
                d for d in dirnames
                if d not in _SKIP_DIRS and not (Path(dirpath) / d).is_symlink()
            ]
            rel_dir = os.path.relpath(dirpath, self._root)
            if rel_dir != ".":
                visible_dirs.append(rel_dir)
            for fname in filenames:
                full = os.path.join(dirpath, fname)
                visible_files.append(os.path.relpath(full, self._root))
                count += 1
                if count >= _MAX_SCAN_ENTRIES:
                    break
            if count >= _MAX_SCAN_ENTRIES:
                break

        return EnvMap(
            task_prompt=envmap.task_prompt,
            workspace_root=envmap.workspace_root,
            visible_files=tuple(sorted(visible_files)),
            visible_dirs=tuple(sorted(visible_dirs)),
            capabilities=envmap.capabilities,
            services=envmap.services,
            resource_limits=envmap.resource_limits,
            permissions=envmap.permissions,
            grader_hints=envmap.grader_hints,
            interactive_features=envmap.interactive_features,
            task_metadata=envmap.task_metadata,
            network_scope=envmap.network_scope,
            file_tree=envmap.file_tree,
            file_map_summary=envmap.file_map_summary,
        )
