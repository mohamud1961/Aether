"""Sandboxed verifier execution with provenance-bound disposable children.

The verifier receives a pristine copy of the Solver workspace for one
verification activation.  Verifier-authored fixtures are registered against
that pristine copy but are not allowed to overwrite task state.  Every command
runs in a fresh child copied from the pristine snapshot, with only explicitly
bound verifier fixtures materialized into that child.  The child is destroyed
immediately after the command, so no verifier command mutation can influence a
later command unless it is represented as an explicit input in a future design.

The Solver workspace is never mutated by verification.  Copying, command
execution, fixture materialization, and teardown all use the same executor
substrate as the Solver (host or container).
"""
from __future__ import annotations

import base64
from hashlib import sha256
import os
import posixpath
import time
import uuid
from typing import Any, Iterable


_OVERLAY_COMMAND_TIMEOUT_S = 300
_OVERLAY_INLINE_OUTPUT_CAP = 4_000


def _shell_quote(text: str) -> str:
    return "'" + text.replace("'", "'\\''") + "'"


def _bounded_output(text: str, *, cap: int = _OVERLAY_INLINE_OUTPUT_CAP) -> tuple[str, bool]:
    """Keep both command-output boundaries visible to the verifier."""
    if len(text) <= cap:
        return text, False
    marker = f"\n... [overlay output truncated: {len(text)} chars; tail follows]\n"
    budget = max(1, cap - len(marker))
    head_size = budget // 2
    tail_size = budget - head_size
    return text[:head_size] + marker + text[-tail_size:], True


class VerifierOverlay:
    """Pristine verifier snapshot plus disposable per-command children.

    ``ensure`` lazily copies the Solver workspace once.  That base copy is
    immutable after creation.  ``write_fixture`` registers a new verifier-only
    path and content after proving it does not collide with the base task copy.
    ``run_command`` copies the pristine base again, materializes only the
    requested registered fixtures, executes once, and removes that child before
    returning.  The activation owner tears down the pristine base in a finally
    block.
    """

    def __init__(
        self,
        executor: Any,
        workspace_root: str,
        *,
        max_command_timeout_s: int = _OVERLAY_COMMAND_TIMEOUT_S,
        require_independent_isolation: bool = False,
    ) -> None:
        self._executor = executor
        self._workspace_root = workspace_root.rstrip("/") or "/"
        self._overlay_root: str | None = None
        self._overlay_executor: Any | None = None
        self._setup_error: str = ""
        self._max_command_timeout_s = max(30, int(max_command_timeout_s))
        self._require_independent_isolation = bool(require_independent_isolation)
        self._fixture_contents: dict[str, str] = {}
        self._independent_snapshot_blocker: str = ""

    @property
    def overlay_root(self) -> str:
        """The pristine verifier snapshot root, never a command child."""
        return self._overlay_root or ""

    def ensure(self) -> dict[str, Any]:
        """Create the pristine verifier copy if needed; report failures."""
        if self._overlay_root is not None:
            return {"overlay_root": self._overlay_root, "created": False}
        if self._setup_error:
            return {"error": self._setup_error}
        escape = self._symlink_escape_error(self._workspace_root)
        if escape:
            self._setup_error = escape
            return {"error": self._setup_error}
        candidate = f"{self._workspace_root}.verifier_overlay_{uuid.uuid4().hex[:8]}"
        copy_cmd = (
            f"rm -rf {_shell_quote(candidate)} && "
            f"cp -a {_shell_quote(self._workspace_root)} {_shell_quote(candidate)}"
        )
        result = self._executor.run_command(copy_cmd, timeout_s=_OVERLAY_COMMAND_TIMEOUT_S)
        if not result.success:
            self._setup_error = (
                f"overlay setup failed (exit={result.exit_code}): "
                f"{(result.stderr or result.stdout)[:500]}"
            )
            return {"error": self._setup_error}
        factory = getattr(self._executor, "for_workspace", None)
        if not callable(factory):
            self._setup_error = "executor cannot create a constrained overlay workspace"
            self._executor.run_command(f"rm -rf {_shell_quote(candidate)}", timeout_s=120)
            return {"error": self._setup_error}
        self._overlay_root = candidate
        self._overlay_executor = factory(candidate)
        return {"overlay_root": candidate, "created": True}

    @staticmethod
    def _symlink_escape_error(root: str) -> str:
        """Reject copies containing symlinks that resolve outside the workspace."""
        root_real = os.path.realpath(root)
        for directory, names, files in os.walk(root, followlinks=False):
            for name in (*names, *files):
                path = os.path.join(directory, name)
                if not os.path.islink(path):
                    continue
                target = os.path.realpath(path)
                if target != root_real and not target.startswith(root_real + os.sep):
                    return f"overlay_symlink_escape_rejected: {os.path.relpath(path, root)}"
        return ""

    @staticmethod
    def _clean_fixture_path(relpath: str) -> tuple[str, str]:
        clean = posixpath.normpath(str(relpath or "").lstrip("/"))
        if clean.startswith("app/"):
            clean = clean[4:]
        elif clean == "app":
            clean = "."
        if clean.startswith("..") or clean in {".", ""}:
            return "", f"invalid fixture path: {relpath!r}"
        return clean, ""

    def write_fixture(self, relpath: str, content: str) -> dict[str, Any]:
        """Register one verifier-owned NEW input path without mutating the base.

        Existing task paths and duplicate fixture paths are rejected.  The
        fixture is materialized only into a later command child when that
        command explicitly binds the fixture's inspection ID.
        """
        state = self.ensure()
        if "error" in state:
            return {"error": state["error"]}
        clean, path_error = self._clean_fixture_path(relpath)
        if path_error:
            return {"error": path_error}
        if clean in self._fixture_contents:
            return {"error": f"fixture path already registered: {clean}"}
        assert self._overlay_executor is not None
        absent = self._overlay_executor.run_command(
            f"test ! -e {_shell_quote(clean)} && test ! -L {_shell_quote(clean)}",
            timeout_s=30,
        )
        if not absent.success:
            return {
                "error": f"fixture path collides with existing task entry: {clean}",
                "fixture_path": clean,
                "collision": True,
            }
        text = str(content)
        self._fixture_contents[clean] = text
        raw = text.encode("utf-8")
        return {
            "overlay_root": self._overlay_root,
            "fixture_path": clean,
            "bytes": len(raw),
            "content_sha256": sha256(raw).hexdigest(),
            "registered": True,
            "written": False,
            "success": True,
            "materialization": "deferred_until_explicitly_bound_command",
        }

    def _create_command_child(self) -> tuple[str, Any | None, str]:
        state = self.ensure()
        if "error" in state:
            return "", None, str(state["error"])
        assert self._overlay_root is not None
        candidate = f"{self._overlay_root}.command_{uuid.uuid4().hex[:8]}"
        copied = self._executor.run_command(
            f"rm -rf {_shell_quote(candidate)} && "
            f"cp -a {_shell_quote(self._overlay_root)} {_shell_quote(candidate)}",
            timeout_s=_OVERLAY_COMMAND_TIMEOUT_S,
        )
        if not copied.success:
            return "", None, (
                f"overlay command-child setup failed (exit={copied.exit_code}): "
                f"{(copied.stderr or copied.stdout)[:500]}"
            )
        factory = getattr(self._executor, "for_workspace", None)
        if not callable(factory):
            self._executor.run_command(f"rm -rf {_shell_quote(candidate)}", timeout_s=120)
            return "", None, "executor cannot create a constrained command-child workspace"
        return candidate, factory(candidate), ""

    @staticmethod
    def _write_child_fixture(child_executor: Any, clean: str, content: str) -> str:
        # Defense in depth: even though fixture registration checked the
        # pristine base, refuse to overwrite anything in the fresh child.
        absent = child_executor.run_command(
            f"test ! -e {_shell_quote(clean)} && test ! -L {_shell_quote(clean)}",
            timeout_s=30,
        )
        if not absent.success:
            return f"bound fixture collides with command-child task entry: {clean}"
        encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
        parent = posixpath.dirname(clean) or "."
        written = child_executor.run_command(
            f"mkdir -p {_shell_quote(parent)} && "
            f"printf '%s' {_shell_quote(encoded)} | base64 -d > {_shell_quote(clean)}",
            timeout_s=60,
        )
        if not written.success:
            return f"bound fixture materialization failed: {(written.stderr or written.stdout)[:500]}"
        return ""

    def run_command(
        self,
        command: str,
        *,
        timeout_s: int | None = None,
        fixture_paths: Iterable[str] = (),
    ) -> dict[str, Any]:
        """Execute once in a fresh child with only explicitly bound fixtures."""
        selected: list[str] = []
        seen: set[str] = set()
        for raw_path in fixture_paths:
            clean, error = self._clean_fixture_path(str(raw_path))
            if error:
                return {"error": error}
            if clean in seen:
                continue
            seen.add(clean)
            if clean not in self._fixture_contents:
                return {"error": f"bound verifier fixture is not registered: {clean}"}
            selected.append(clean)

        child_root, child_executor, child_error = self._create_command_child()
        if child_error:
            return {"error": child_error}
        assert child_executor is not None
        result_data: dict[str, Any]
        try:
            for path in selected:
                materialize_error = self._write_child_fixture(
                    child_executor, path, self._fixture_contents[path],
                )
                if materialize_error:
                    result_data = {"error": materialize_error}
                    break
            else:
                requested = self._max_command_timeout_s if timeout_s is None else int(timeout_s)
                capped_timeout = max(1, min(requested, self._max_command_timeout_s))
                isolation_metadata: dict[str, Any] = {}
                result = None
                command_execution_elapsed_s: float | None = None
                if self._require_independent_isolation:
                    isolated_runner = getattr(self._executor, "run_independent_verifier_command", None)
                    if not callable(isolated_runner):
                        result_data = {
                            "error": "verifier_independent_isolation_unavailable: executor has no isolated verifier runner",
                            "independent_isolation_required": True,
                            "independent_isolation_verified": False,
                            "isolation_cleanup_verified": False,
                        }
                    else:
                        isolation_started = time.monotonic()
                        if self._independent_snapshot_blocker:
                            isolated = {
                                "error": self._independent_snapshot_blocker,
                                "metadata": {
                                    "independent_isolation_verified": False,
                                    "isolation_cleanup_verified": True,
                                    "snapshot_retry_suppressed": True,
                                },
                            }
                        else:
                            isolated = isolated_runner(
                                command,
                                workspace_root=child_root,
                                timeout_s=capped_timeout,
                            )
                        isolation_elapsed_s = time.monotonic() - isolation_started
                        if not isinstance(isolated, dict):
                            result_data = {
                                "error": "verifier_independent_isolation_invalid_result",
                                "independent_isolation_required": True,
                                "independent_isolation_verified": False,
                                "isolation_cleanup_verified": False,
                            }
                        else:
                            isolation_metadata = dict(isolated.get("metadata") or {})
                            result = isolated.get("result")
                            if result is not None:
                                metrics = dict(getattr(result, "metrics", {}) or {})
                                reported_command_elapsed = metrics.get(
                                    "command_execution_elapsed_s"
                                )
                                try:
                                    parsed_command_elapsed = float(reported_command_elapsed)
                                except (TypeError, ValueError):
                                    parsed_command_elapsed = -1.0
                                # New independent runners report the semantic
                                # command window separately from isolation custody.
                                # Legacy runners remain conservative by charging
                                # their complete isolation call as execution time.
                                command_execution_elapsed_s = (
                                    parsed_command_elapsed
                                    if parsed_command_elapsed >= 0.0
                                    else isolation_elapsed_s
                                )
                            verified = (
                                isolation_metadata.get("independent_isolation_verified") is True
                                and isolation_metadata.get("isolation_cleanup_verified") is True
                                and result is not None
                            )
                            if not verified:
                                isolation_error = str(
                                    isolated.get("error") or "verifier_independent_isolation_not_verified"
                                )
                                if isolation_error.startswith(
                                    "verifier_independent_isolation_docker_commit_failed:"
                                ):
                                    self._independent_snapshot_blocker = isolation_error
                                result_data = {
                                    "error": isolation_error,
                                    "independent_isolation_required": True,
                                    "independent_isolation_verified": False,
                                    "isolation_cleanup_verified": bool(isolation_metadata.get("isolation_cleanup_verified")),
                                    **{k: v for k, v in isolation_metadata.items() if k not in {"independent_isolation_verified"}},
                                }
                else:
                    virtual_root = "/app" in command
                    virtual_runner = getattr(child_executor, "run_command_with_virtual_workspace", None)
                    command_started = time.monotonic()
                    if virtual_root and callable(virtual_runner):
                        result = virtual_runner(
                            command, virtual_workspace_root="/app", timeout_s=capped_timeout,
                        )
                    elif virtual_root and self._workspace_root != "/app":
                        result_data = {
                            "error": "overlay_virtual_workspace_unavailable: /app is not mounted for this executor"
                        }
                    else:
                        result = child_executor.run_command(command, timeout_s=capped_timeout)
                    command_execution_elapsed_s = time.monotonic() - command_started
                if result is not None:
                    escape = self._symlink_escape_error(child_root)
                    if escape:
                        result_data = {"error": escape}
                    else:
                        stdout, stdout_truncated = _bounded_output(result.stdout)
                        stderr, stderr_truncated = _bounded_output(result.stderr)
                        command_bytes = command.encode("utf-8", "replace")
                        result_data = {
                            "overlay_root": child_root,
                            "pristine_overlay_root": self._overlay_root,
                            "execution_isolation": (
                                str(isolation_metadata.get("execution_isolation") or "independent_verifier_world")
                                if self._require_independent_isolation
                                else "fresh_child_from_pristine_overlay"
                            ),
                            "independent_isolation_required": self._require_independent_isolation,
                            "independent_isolation_verified": (
                                bool(isolation_metadata.get("independent_isolation_verified"))
                                if self._require_independent_isolation else False
                            ),
                            "isolation_cleanup_verified": (
                                bool(isolation_metadata.get("isolation_cleanup_verified"))
                                if self._require_independent_isolation else False
                            ),
                            "materialized_fixture_paths": list(selected),
                            "command_sha256": sha256(command_bytes).hexdigest(),
                            "command_bytes": len(command_bytes),
                            "exit_code": result.exit_code,
                            "success": result.success,
                            "stdout": stdout,
                            "stderr": stderr,
                            "stdout_bytes": getattr(result, "stdout_bytes_total", len(result.stdout)),
                            "stderr_bytes": getattr(result, "stderr_bytes_total", len(result.stderr)),
                            "stdout_truncated": stdout_truncated,
                            "stderr_truncated": stderr_truncated,
                            "timed_out": getattr(result, "timed_out", False),
                            "tool_execution_elapsed_s": round(float(command_execution_elapsed_s or 0.0), 6),
                            **isolation_metadata,
                        }
        finally:
            try:
                removed = self._executor.run_command(
                    f"rm -rf {_shell_quote(child_root)}", timeout_s=120,
                )
                cleanup_error = ""
            except Exception as exc:
                removed = None
                cleanup_error = f"{type(exc).__name__}: {exc}"[:500]
        result_data["command_child_removed"] = bool(removed is not None and removed.success)
        if removed is None or not removed.success:
            detail = cleanup_error if removed is None else (removed.stderr or removed.stdout)[:500]
            result_data["error"] = (
                "verifier command-child cleanup failed: " + detail
            )
        return result_data

    def teardown(self) -> dict[str, Any]:
        """Delete the pristine activation copy; rollback is idempotent."""
        if self._overlay_root is None:
            self._fixture_contents.clear()
            return {"removed": False}
        target, self._overlay_root = self._overlay_root, None
        self._overlay_executor = None
        self._fixture_contents.clear()
        self._independent_snapshot_blocker = ""
        result = self._executor.run_command(
            f"rm -rf {_shell_quote(target)}", timeout_s=120,
        )
        return {"removed": result.success, "overlay_root": target}
