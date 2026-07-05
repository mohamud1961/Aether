"""Subprocess-backed Executor for Aether-Next against a real workspace directory."""
from __future__ import annotations

import fnmatch
import os
import signal
import subprocess
import uuid
from pathlib import Path
from typing import Any

from .execution import (
    ArtifactInspection,
    CommandResult,
    ProcessHandle,
    ProbeResult,
)
from .runtime_ir import EnvMap, CapabilityDescriptor, normalize_relpath


_STDOUT_CAP = 20_000
_STDERR_CAP = 20_000
_SKIP_DIRS = {".git", "__pycache__", "node_modules", ".mypy_cache", ".pytest_cache"}
_MAX_SCAN_ENTRIES = 5_000


def _resolve_safe(workspace_root: str, path: str) -> str:
    """Resolve *path* relative to *workspace_root*, clamping escapes."""
    root = Path(workspace_root).resolve()
    candidate = (root / path).resolve()
    if not str(candidate).startswith(str(root)):
        # Clamp to workspace root -- never operate outside.
        candidate = root / Path(path).name
        candidate = candidate.resolve()
        if not str(candidate).startswith(str(root)):
            return str(root)
    return str(candidate)


def _truncate(text: str, cap: int) -> str:
    if len(text) <= cap:
        return text
    return text[:cap] + f"\n... [truncated at {cap} chars]"


def _snapshot_mtimes(root: str) -> dict[str, float]:
    """Return {relative_path: mtime} for files under *root*, bounded."""
    result: dict[str, float] = {}
    count = 0
    root_path = Path(root)
    try:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
            for fname in filenames:
                full = os.path.join(dirpath, fname)
                try:
                    rel = os.path.relpath(full, root)
                    result[rel] = os.path.getmtime(full)
                except OSError:
                    pass
                count += 1
                if count >= _MAX_SCAN_ENTRIES:
                    return result
    except OSError:
        pass
    return result


class SubprocessExecutor:
    """Real filesystem + subprocess executor within a workspace directory."""

    def __init__(self, workspace_root: str, *, default_timeout_s: int = 120) -> None:
        self._root = str(Path(workspace_root).resolve())
        self._default_timeout_s = max(1, default_timeout_s)
        self._processes: dict[str, subprocess.Popen[str]] = {}
        self._process_meta: dict[str, ProcessHandle] = {}
        os.makedirs(self._root, exist_ok=True)

    # ---- Filesystem --------------------------------------------------------

    def read_file(self, path: str) -> str:
        resolved = _resolve_safe(self._root, path)
        if not os.path.isfile(resolved):
            raise FileNotFoundError(resolved)
        with open(resolved, encoding="utf-8", errors="replace") as fh:
            return fh.read()

    def write_file(self, path: str, content: str) -> None:
        resolved = _resolve_safe(self._root, path)
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
            dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
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
        effective_cwd = cwd or self._root
        effective_timeout = timeout_s if timeout_s > 0 else self._default_timeout_s

        before = _snapshot_mtimes(self._root)

        try:
            proc = subprocess.run(
                ["bash", "-lc", command],
                cwd=effective_cwd,
                capture_output=True,
                text=True, errors="replace",
                timeout=effective_timeout,
            )
            exit_code = proc.returncode
            stdout = _truncate(proc.stdout, _STDOUT_CAP)
            stderr = _truncate(proc.stderr, _STDERR_CAP)
        except subprocess.TimeoutExpired:
            return CommandResult(
                command=command,
                exit_code=124,
                stdout="",
                stderr=f"command timed out after {effective_timeout}s",
            )

        after = _snapshot_mtimes(self._root)

        modified: list[str] = []
        produced: list[str] = []
        for rel, mtime in after.items():
            if rel not in before:
                produced.append(rel)
            elif before[rel] != mtime:
                modified.append(rel)

        return CommandResult(
            command=command,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            modified_paths=tuple(sorted(modified)),
            produced_artifacts=tuple(sorted(produced)),
            metrics={},
        )

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

        try:
            proc = subprocess.Popen(
                ["bash", "-lc", command],
                cwd=effective_cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
            )
        except OSError as exc:
            return ProcessHandle(
                process_id=process_id,
                name=name,
                command=command,
                interactive=interactive,
                live=False,
                detail=f"launch failed: {exc}",
            )

        self._processes[process_id] = proc
        handle = ProcessHandle(
            process_id=process_id,
            name=name,
            command=command,
            interactive=interactive,
            live=True,
            endpoint=f"pid://{proc.pid}",
            detail=f"started pid={proc.pid}",
        )
        self._process_meta[process_id] = handle
        return handle

    def probe_process(self, target: str) -> ProbeResult:
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
        )

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
            stat = os.stat(resolved)
            metadata["size_bytes"] = stat.st_size
        except OSError:
            pass

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

        # Binary / unknown mode: size + first-bytes preview.
        metadata["backend"] = "basic"
        try:
            with open(resolved, "rb") as fh:
                head = fh.read(256)
            preview = head.hex(" ", 1)[:200]
            metadata["head_hex"] = preview
            return ArtifactInspection(
                path=path,
                mode=mode,
                success=True,
                extracted_text="",
                metadata=metadata,
                detail=f"binary preview of {path} ({metadata.get('size_bytes', '?')} bytes)",
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
            dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
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
        )
