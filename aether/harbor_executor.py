"""Canonical Aether-Next Executor facade over a Harbor BaseEnvironment.

Harbor remains the world authority. This module provides the synchronous
``Executor`` contract expected by the Aether-Next kernel while all task-world
operations are executed through Harbor's asynchronous environment API.

The kernel must run off the Harbor event-loop thread (for example via
``asyncio.to_thread``). Calls from that worker thread are marshalled back onto
the owning Harbor loop with ``run_coroutine_threadsafe``.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shlex
import subprocess
import tempfile
import threading
import time
from typing import Any, Awaitable, Mapping, TypeVar
import uuid

from .artifact_plane import identify_bytes
from .environment_extensions import extension_probe_payload, normalize_mcp_servers
from .evidence_finalization import export_content_addressed_files
from .environment_probe import probe_environment
from .harbor_workspace_state import (
    HARBOR_CONTROL_ROOT,
    RemoteWorkspaceSnapshot,
    diff_remote_workspace_snapshots,
    parse_remote_workspace_snapshot,
    remote_workspace_snapshot_command,
)
from .run_deadline import KernelRunTimeout, raise_if_run_deadline_exceeded, run_deadline_cleanup_authority
from .execution import (
    ArtifactInspection,
    CommandResult,
    ComputerActionResult,
    JobProbeResult,
    ProcessHandle,
    ProbeResult,
    TerminalReadResult,
    TerminalSessionHandle,
    TerminalSessionState,
)
from .runtime_ir import EnvMap
from .verifier_deadline import remaining_verifier_generation_s

_T = TypeVar("_T")

# Read-only Verifier world inspection may need task state outside the solver
# workspace (for example /git/server or /var/www/server).  Resolve remotely
# before applying these mechanical privacy boundaries so a symlink cannot
# tunnel into a denied root.  Workspace-relative Solver file APIs remain
# unchanged.
_VERIFIER_SNAPSHOT_TIMEOUT_DEFAULT_S = 300
_VERIFIER_SNAPSHOT_TIMEOUT_FLOOR_S = 120
_VERIFIER_SNAPSHOT_TIMEOUT_CAP_S = 600
_VERIFIER_SNAPSHOT_DEADLINE_RESERVE_S = 30


def _verifier_snapshot_timeout_s() -> int:
    """Bound Docker snapshot custody by the active verifier generation deadline.

    Large Harbor task root filesystems can legitimately need more than the old
    fixed 120-second commit ceiling.  Give one snapshot enough mechanical time
    while preserving deadline headroom for unpause/cleanup and later verifier
    work.  Outside a bound verifier generation, use a conservative provider-free
    default rather than an unbounded host call.
    """
    remaining = remaining_verifier_generation_s()
    if remaining is None:
        return _VERIFIER_SNAPSHOT_TIMEOUT_DEFAULT_S
    available = max(1.0, float(remaining) - _VERIFIER_SNAPSHOT_DEADLINE_RESERVE_S)
    desired = max(_VERIFIER_SNAPSHOT_TIMEOUT_FLOOR_S, available / 2.0)
    return max(1, int(min(_VERIFIER_SNAPSHOT_TIMEOUT_CAP_S, available, desired)))


_VERIFIER_WORLD_DENIED_PREFIXES = (
    "/proc",
    "/sys",
    "/dev",
    "/run/secrets",
    "/var/run/secrets",
    "/tests",
    "/grader",
    "/graders",
    "/solution",
    "/solutions",
    "/root/.ssh",
    "/root/.aws",
    "/root/.azure",
    "/root/.config/gcloud",
)


@dataclass(frozen=True)
class _RemoteProcess:
    process_id: str
    name: str
    command: str
    remote_dir: str
    pid: int
    generation: str
    interactive: bool
    stdout_path: str
    stderr_path: str
    exit_path: str
    input_path: str = ""
    cleanup_path: str = ""
    container_id: str = ""


def _computer_key_name(value: Any) -> str:
    raw = str(value or "").strip().lower()
    aliases = {
        "control":"ctrl","ctl":"ctrl","command":"super","cmd":"super","option":"alt",
        "return":"enter","esc":"escape","del":"delete","pgup":"pageup","pgdn":"pagedown",
        "arrowleft":"left","arrowright":"right","arrowup":"up","arrowdown":"down",
    }
    return aliases.get(raw, raw)


def _scroll_click_count(delta: int) -> int:
    value = abs(int(delta))
    return 0 if value == 0 else max(1, (value + 99) // 100)


def _xdotool_action_command(action: Mapping[str, Any]) -> str:
    kind = str(action.get("type") or "")
    keys = [_computer_key_name(value) for value in action.get("keys", ()) or ()]
    held_prefix = held_suffix = ""
    if keys and kind in {"click","double_click","move","scroll","drag"}:
        held_prefix = " && ".join(f"xdotool keydown {shlex.quote(key)}" for key in keys) + " && "
        held_suffix = " && " + " && ".join(f"xdotool keyup {shlex.quote(key)}" for key in reversed(keys))
    if kind == "screenshot": body = ":"
    elif kind == "wait": body = "sleep 2"
    elif kind == "type": body = f"xdotool type --clearmodifiers --delay 0 -- {shlex.quote(str(action.get('text') or ''))}"
    elif kind == "keypress":
        combo = "+".join(_computer_key_name(value) for value in action.get("keys", ()) or ())
        if not combo: raise ValueError("computer keypress requires at least one key")
        body = f"xdotool key --clearmodifiers {shlex.quote(combo)}"
    elif kind in {"click","double_click","move","scroll"}:
        x, y = int(action["x"]), int(action["y"]); move = f"xdotool mousemove --sync {x} {y}"
        if kind == "move": body = move
        elif kind in {"click","double_click"}:
            button = {"left":1,"wheel":2,"right":3,"back":8,"forward":9}[str(action.get("button") or "left")]
            body = f"{move} && xdotool click --repeat {2 if kind == 'double_click' else 1} --delay 100 {button}"
        else:
            sx, sy = int(action.get("scroll_x",0)), int(action.get("scroll_y",0)); parts=[move]
            if sy: parts.append(f"xdotool click --repeat {_scroll_click_count(sy)} --delay 20 {5 if sy > 0 else 4}")
            if sx: parts.append(f"xdotool click --repeat {_scroll_click_count(sx)} --delay 20 {7 if sx > 0 else 6}")
            body = " && ".join(parts)
    elif kind == "drag":
        path=list(action.get("path") or ())
        if not path: raise ValueError("computer drag requires a non-empty path")
        first=path[0]; parts=[f"xdotool mousemove --sync {int(first['x'])} {int(first['y'])}","xdotool mousedown 1"]
        parts += [f"xdotool mousemove --sync {int(pt['x'])} {int(pt['y'])}" for pt in path[1:]] + ["xdotool mouseup 1"]
        body = " && ".join(parts)
    else: raise ValueError(f"unsupported computer action: {kind}")
    return held_prefix + body + held_suffix


def _pyautogui_action_script(request: Mapping[str, Any], screenshot_path: str) -> str:
    import base64 as _b64
    actions = [dict(row) for row in (request.get("actions") or ())]
    encoded=_b64.b64encode(json.dumps(actions,separators=(",",":")).encode()).decode()
    target=repr(str(screenshot_path))
    return f"""python3 - <<'PYCOMPUTER'
import base64,json,time
import pyautogui as p
actions=json.loads(base64.b64decode({encoded!r}).decode())
def wheel_steps(delta):
 value=abs(int(delta)); return 0 if value==0 else max(1,(value+99)//100)
def mouse_button(value):
 value=str(value or 'left').lower()
 if value=='wheel': return 'middle'
 if value in ('left','right','middle'): return value
 raise ValueError('pyautogui backend cannot faithfully execute mouse button '+value)
def execute(a):
 k=a.get('type'); keys=[str(x).lower() for x in a.get('keys',[]) or []]
 held = keys if k in ('click','double_click','move','scroll','drag') else []
 for key in held: p.keyDown(key)
 try:
  if k=='click': p.click(a['x'],a['y'],button=mouse_button(a.get('button','left')))
  elif k=='double_click': p.doubleClick(a['x'],a['y'],button='left')
  elif k=='move': p.moveTo(a['x'],a['y'])
  elif k=='type': p.write(a.get('text',''),interval=0)
  elif k=='keypress': p.hotkey(*keys)
  elif k=='scroll':
   p.moveTo(a['x'],a['y']); sy=int(a.get('scroll_y',0)); sx=int(a.get('scroll_x',0))
   if sy: p.scroll((-1 if sy>0 else 1)*wheel_steps(sy))
   if sx and hasattr(p,'hscroll'): p.hscroll((1 if sx>0 else -1)*wheel_steps(sx))
  elif k=='drag':
   pts=a.get('path',[])
   if not pts: raise ValueError('empty drag path')
   p.moveTo(pts[0]['x'],pts[0]['y']); p.mouseDown()
   for pt in pts[1:]: p.moveTo(pt['x'],pt['y'])
   p.mouseUp()
  elif k=='wait': time.sleep(2)
  elif k!='screenshot': raise ValueError('unsupported computer action: '+str(k))
 finally:
  for key in reversed(held): p.keyUp(key)
try:
 for action in actions: execute(action)
finally:
 p.screenshot().save({target})
PYCOMPUTER"""


class HarborEnvironmentExecutor:
    """Synchronous Aether Executor backed only by a Harbor environment.

    This class deliberately does not import Harbor. Its runtime contract is the
    small public surface Aether actually requires: ``exec``, ``upload_file`` and
    ``download_file`` awaitables. A real Harbor integration test is still
    required before this class may be called production-qualified.
    """

    # Harbor can snapshot the pristine activation once and create disposable
    # verifier siblings from that immutable image. VerifierOverlay uses this
    # capability to avoid parent-side cp -a for every inspection command.
    supports_activation_scoped_verifier_snapshot = True

    def __init__(
        self,
        environment: Any,
        *,
        event_loop: asyncio.AbstractEventLoop,
        workspace_root: str = "/app",
        local_state_dir: str | Path | None = None,
        default_env: Mapping[str, str] | None = None,
        mcp_servers: tuple[Mapping[str, Any], ...] = (),
    ) -> None:
        self.environment = environment
        self.event_loop = event_loop
        self.workspace_root = self._normalize_workspace_root(workspace_root)
        self._state_snapshot_marker: str | None = None
        self._verifier_world_roots: tuple[str, ...] = (self.workspace_root,)
        self.default_env = dict(default_env or {})
        if local_state_dir is None:
            local_state_dir = Path(tempfile.mkdtemp(prefix="aether-next-harbor-"))
        self.local_state_dir = Path(local_state_dir).resolve()
        self.local_state_dir.mkdir(parents=True, exist_ok=True)
        self._spool_archive_dir = self.local_state_dir / "spool_archive"
        self._spool_archive: dict[tuple[str, str], Path] = {}
        self._spool_archive_errors: list[str] = []
        self._processes: dict[str, _RemoteProcess] = {}
        self._process_workspace_state: dict[str, RemoteWorkspaceSnapshot] = {}
        self._terminal_cursors: dict[str, int] = {}
        self._mcp_servers = {
            str(row["name"]): dict(row)
            for row in normalize_mcp_servers(mcp_servers)
        }
        self._mcp_client_uploaded = False
        self._rfb_client_uploaded = False
        self._subreaper_uploaded = False
        self._terminal_workspace_state: RemoteWorkspaceSnapshot | None = None
        # Independent verifier snapshots briefly pause the Harbor parent. Serialize
        # that lifecycle so Aether owns at most one pause transaction per task world.
        self._verifier_snapshot_lock = threading.Lock()
        # Activation-scoped immutable images keyed by pristine verifier overlay root.
        # The overlay owner releases them in teardown; per-command siblings are still disposable.
        self._verifier_snapshot_cache: dict[str, dict[str, Any]] = {}
        self._mcp_client_remote_path = (
            "/tmp/aether-next-mcp-client-"
            + hashlib.sha256(self.workspace_root.encode("utf-8")).hexdigest()[:16]
            + ".py"
        )
        self._rfb_client_remote_path = (
            "/tmp/aether-next-rfb-client-"
            + hashlib.sha256(self.workspace_root.encode("utf-8")).hexdigest()[:16]
            + ".py"
        )
        self._subreaper_remote_path = "/tmp/aether-harbor-subreaper-linux-x86_64"

    @staticmethod
    def _normalize_workspace_root(value: str) -> str:
        root = "/" + str(value or "/app").strip().strip("/")
        return str(PurePosixPath(root))

    def _remote_path(self, path: str) -> str:
        raw = str(path or "").strip().replace("\\", "/")
        if not raw:
            raise ValueError("path must be non-empty")
        if raw.startswith("/"):
            candidate = PurePosixPath(raw)
        else:
            candidate = PurePosixPath(self.workspace_root) / raw
        normalized = str(candidate)
        root = self.workspace_root.rstrip("/")
        if normalized != root and not normalized.startswith(root + "/"):
            raise ValueError(f"workspace path escape rejected: {path}")
        if any(part == ".." for part in candidate.parts):
            raise ValueError(f"workspace path escape rejected: {path}")
        return normalized

    def _cwd(self, cwd: str | None) -> str:
        return self.workspace_root if not cwd else self._remote_path(cwd)

    def for_workspace(self, workspace_root: str) -> "HarborEnvironmentExecutor":
        """Return a facade constrained to one trusted sibling workspace.

        VerifierOverlay creates the sibling itself through the original Harbor
        environment before calling this factory. The clone shares only the same
        Harbor world and event loop; path resolution is rebound to the supplied
        root and host-side transport scratch is kept separate.
        """
        child_state = self.local_state_dir / (
            "workspace-" + hashlib.sha256(str(workspace_root).encode("utf-8")).hexdigest()[:16]
        )
        return HarborEnvironmentExecutor(
            self.environment,
            event_loop=self.event_loop,
            workspace_root=workspace_root,
            local_state_dir=child_state,
            default_env=self.default_env,
            mcp_servers=tuple(self._mcp_servers.values()),
        )

    def _harbor_docker_main_container_id(self) -> tuple[str, str]:
        """Resolve the exact Harbor Docker main container via Harbor 0.20's compose seam.

        This is deliberately fail-closed. Non-Docker Harbor providers, or a
        future Harbor version that no longer exposes the compose command seam,
        are not silently treated as equivalent isolation substrates.
        """
        env_type = getattr(self.environment, "type", None)
        try:
            raw_type = env_type() if callable(env_type) else ""
        except Exception as exc:  # noqa: BLE001 - capability discovery
            return "", f"harbor_environment_type_probe_failed: {type(exc).__name__}: {exc}"
        type_value = getattr(raw_type, "value", raw_type)
        if str(type_value).strip().lower() != "docker":
            return "", f"verifier_independent_isolation_unsupported_harbor_provider:{type_value}"
        compose = getattr(self.environment, "_run_docker_compose_command", None)
        if not callable(compose):
            return "", "verifier_independent_isolation_harbor_docker_compose_seam_unavailable"
        try:
            result = self._await(
                compose(["ps", "-q", "main"], check=False, timeout_sec=30),
                timeout_s=35,
            )
        except Exception as exc:  # noqa: BLE001 - Harbor transport failure is evidence
            return "", f"verifier_independent_isolation_container_lookup_failed: {type(exc).__name__}: {exc}"
        code, stdout, stderr = self._result_fields(result)
        candidates = [line.strip() for line in stdout.splitlines() if line.strip()]
        if code != 0 or len(candidates) != 1:
            detail = (stderr or stdout)[-1000:]
            return "", (
                "verifier_independent_isolation_container_lookup_ambiguous:"
                f"exit={code}:count={len(candidates)}:{detail}"
            )
        container_id = candidates[0].lower()
        if not (12 <= len(container_id) <= 64 and all(ch in "0123456789abcdef" for ch in container_id)):
            return "", "verifier_independent_isolation_container_id_invalid"
        return container_id, ""

    @staticmethod
    def _docker_host_call(args: list[str], *, timeout_s: int) -> tuple[subprocess.CompletedProcess[str] | None, str]:
        try:
            return subprocess.run(
                args, capture_output=True, text=True, errors="replace",
                timeout=max(1, int(timeout_s)), check=False,
            ), ""
        except (OSError, subprocess.SubprocessError) as exc:
            return None, f"{type(exc).__name__}: {exc}"

    @staticmethod
    def _docker_inspect_proves_absent(
        result: subprocess.CompletedProcess[str] | None, error: str, *, kind: str,
    ) -> tuple[bool, str]:
        """Return true only when Docker explicitly reports the inspected object absent."""
        if result is None:
            return False, error or "docker inspect unavailable"
        if result.returncode == 0:
            return False, "object still present"
        detail = str(error or result.stderr or result.stdout or "").strip()
        lowered = detail.lower()
        absence_markers = (
            "no such object", "no such container", "no such image",
            "not found", "does not exist",
        )
        if any(marker in lowered for marker in absence_markers):
            return True, ""
        return False, f"{kind} absence unverified: {detail or 'inspect failed'}"

    def _docker_container_state(
        self, container_id: str,
    ) -> tuple[bool | None, bool | None, str]:
        """Return Docker running/paused state for the exact Harbor parent."""
        result, error = self._docker_host_call(
            [
                "docker", "inspect", "--format",
                "{{.State.Running}} {{.State.Paused}}", container_id,
            ],
            timeout_s=3,
        )
        if result is None or result.returncode != 0:
            detail = error or (
                ((result.stderr or result.stdout)[-500:]) if result is not None else "inspect_failed"
            )
            return None, None, detail
        state = str(result.stdout or "").strip().lower().split()
        if len(state) < 2 or state[0] not in {"true", "false"} or state[1] not in {"true", "false"}:
            return None, None, "invalid_state=" + " ".join(state[:2])
        return state[0] == "true", state[1] == "true", ""

    def _wait_for_docker_container_runnable(
        self, container_id: str, *, timeout_s: float = 10.0,
    ) -> tuple[bool, str, int]:
        """Observe the exact Harbor parent until it is running and unpaused."""
        deadline = time.monotonic() + max(0.1, float(timeout_s))
        probes = 0
        last = ""
        while True:
            probes += 1
            running, paused, error = self._docker_container_state(container_id)
            if running is True and paused is False:
                return True, "", probes
            if error:
                last = error
            else:
                last = f"state={str(running).lower()} {str(paused).lower()}"
            if time.monotonic() >= deadline:
                return False, last, probes
            time.sleep(0.05)

    def _snapshot_harbor_parent_image(
        self, container_id: str, image_tag: str,
    ) -> tuple[bool, str, dict[str, Any]]:
        """Capture a parent rootfs snapshot under an Aether-owned pause transaction.

        Docker's implicit ``commit --pause=true`` pause proved non-restoring on a
        real Harbor run: the daemon left the task container paused after commit,
        causing every later Harbor exec to fail.  Aether therefore owns the
        lifecycle explicitly: prove the parent starts runnable, pause it, commit
        with Docker's implicit pause disabled, unpause in ``finally``, and prove
        runnable state again before any verifier sibling work is admitted.
        """
        metadata: dict[str, Any] = {
            "parent_runnable_before_snapshot": False,
            "parent_pause_owned": False,
            "parent_unpause_attempted": False,
            "parent_unpause_succeeded": False,
            "parent_runnable_after_snapshot": False,
            "parent_runnable_probe_count": 0,
            "parent_runnable_probe_error": "",
        }
        running, paused, state_error = self._docker_container_state(container_id)
        if state_error or running is not True or paused is not False:
            detail = state_error or f"state={str(running).lower()} {str(paused).lower()}"
            return False, "verifier_independent_isolation_parent_not_runnable_before_snapshot:" + detail, metadata
        metadata["parent_runnable_before_snapshot"] = True

        pause, pause_error = self._docker_host_call(["docker", "pause", container_id], timeout_s=15)
        if pause is None or pause.returncode != 0:
            detail = pause_error or ((pause.stderr or pause.stdout)[-1000:] if pause else "")
            return False, "verifier_independent_isolation_parent_pause_failed:" + detail, metadata
        metadata["parent_pause_owned"] = True

        snapshot_created = False
        error = ""
        try:
            running, paused, state_error = self._docker_container_state(container_id)
            if state_error or running is not True or paused is not True:
                detail = state_error or f"state={str(running).lower()} {str(paused).lower()}"
                error = "verifier_independent_isolation_parent_pause_not_observed:" + detail
            else:
                snapshot_timeout_s = _verifier_snapshot_timeout_s()
                snapshot_started = time.monotonic()
                commit, commit_error = self._docker_host_call(
                    ["docker", "commit", "--pause=false", container_id, image_tag],
                    timeout_s=snapshot_timeout_s,
                )
                metadata["snapshot_timeout_s"] = snapshot_timeout_s
                metadata["snapshot_elapsed_s"] = round(time.monotonic() - snapshot_started, 6)
                if commit is None or commit.returncode != 0:
                    detail = commit_error or ((commit.stderr or commit.stdout)[-1000:] if commit else "")
                    error = "verifier_independent_isolation_docker_commit_failed:" + detail
                else:
                    snapshot_created = True
                    snapshot_id = commit.stdout.strip()
                    metadata["snapshot_image_id_sha256"] = hashlib.sha256(
                        snapshot_id.encode("utf-8")
                    ).hexdigest()
        finally:
            metadata["parent_unpause_attempted"] = True
            unpause, unpause_error = self._docker_host_call(
                ["docker", "unpause", container_id], timeout_s=15,
            )
            if unpause is not None and unpause.returncode == 0:
                metadata["parent_unpause_succeeded"] = True
            else:
                detail = unpause_error or (
                    ((unpause.stderr or unpause.stdout)[-1000:]) if unpause is not None else ""
                )
                error = error or "verifier_independent_isolation_parent_unpause_failed:" + detail
            parent_runnable, runnable_error, probe_count = self._wait_for_docker_container_runnable(
                container_id, timeout_s=10.0,
            )
            metadata.update({
                "parent_runnable_after_snapshot": parent_runnable,
                "parent_runnable_probe_count": probe_count,
                "parent_runnable_probe_error": runnable_error,
            })
            if not parent_runnable:
                error = error or (
                    "verifier_independent_isolation_parent_not_runnable_after_snapshot:" + runnable_error
                )
        return snapshot_created and not error, error, metadata

    def run_independent_verifier_command(
        self,
        command: str,
        *,
        workspace_root: str,
        timeout_s: int = 30,
        fixture_contents: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        """Run a PERSISTENT Verifier command in a disposable Docker sibling.

        A pristine ``/app.verifier_overlay_*`` root identifies one Verifier
        activation. Its Harbor parent is snapshotted exactly once, then every
        inspection command starts a fresh networkless sibling from that same
        immutable image. The sibling moves the pristine overlay into ``/app``
        (rename, not recursive copy), materializes only explicitly bound fixtures,
        executes once, and is destroyed. Legacy ``.command_*`` callers retain
        one-shot snapshot cleanup for compatibility.
        """
        source = str(workspace_root or "").strip()
        valid_overlay = source.startswith("/app.verifier_overlay_")
        legacy_command_child = valid_overlay and ".command_" in source
        activation_scoped = valid_overlay and not legacy_command_child
        metadata: dict[str, Any] = {
            "execution_isolation": "harbor_docker_snapshot_sibling",
            "isolation_backend": "harbor0200_docker_snapshot_sibling",
            "independent_isolation_verified": False,
            "isolation_cleanup_verified": False,
            "mount_namespace_private": True,
            "pid_namespace_private": True,
            "network_namespace_private": True,
            "network_scope": "docker_none",
            "world_domain_contract": {
                "filesystem_view": "task_rootfs_snapshot",
                "parent_processes_preserved": False,
                "parent_network_namespace_preserved": False,
                "outbound_network_enabled": False,
            },
            "harbor_provider": "docker",
            "workspace_snapshot_path_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
            "parent_runnable_after_snapshot": False,
            "parent_runnable_probe_count": 0,
            "snapshot_scope": "verifier_activation" if activation_scoped else "one_shot_legacy",
        }
        if not valid_overlay:
            return {
                "error": "verifier_independent_isolation_invalid_harbor_child",
                "metadata": metadata,
            }

        fixtures = dict(fixture_contents or {})
        clean_fixtures: dict[str, str] = {}
        for raw_path, content in fixtures.items():
            clean = str(PurePosixPath(str(raw_path or "").lstrip("/")))
            if clean.startswith("app/"):
                clean = clean[4:]
            if clean in {"", ".", ".."} or clean.startswith("../"):
                return {"error": f"invalid verifier fixture path: {raw_path!r}", "metadata": metadata}
            clean_fixtures[clean] = str(content)

        container_id, lookup_error = self._harbor_docker_main_container_id()
        if lookup_error:
            return {"error": lookup_error, "metadata": metadata}
        metadata["parent_container_id_sha256"] = hashlib.sha256(container_id.encode("ascii")).hexdigest()

        error = ""
        result: CommandResult | None = None
        sibling_name = ""
        image_tag = ""
        image_created_here = False
        with self._verifier_snapshot_lock:
            cached = self._verifier_snapshot_cache.get(source) if activation_scoped else None
            if cached is not None:
                if cached.get("container_id") != container_id:
                    return {
                        "error": "verifier_independent_isolation_parent_identity_changed",
                        "metadata": metadata,
                    }
                image_tag = str(cached["image_tag"])
                metadata.update(dict(cached.get("snapshot_metadata") or {}))
                metadata["snapshot_reused"] = True
            else:
                nonce = uuid.uuid4().hex[:16]
                image_tag = f"aether-harbor-verifier-{nonce}:snapshot"
                image_created_here, snapshot_error, snapshot_metadata = self._snapshot_harbor_parent_image(
                    container_id, image_tag,
                )
                metadata.update(snapshot_metadata)
                metadata["snapshot_reused"] = False
                if snapshot_error:
                    error = snapshot_error
                if image_created_here and not error and activation_scoped:
                    self._verifier_snapshot_cache[source] = {
                        "container_id": container_id,
                        "image_tag": image_tag,
                        "snapshot_metadata": dict(snapshot_metadata),
                    }
            if not image_tag or error:
                return {"error": error or "verifier_independent_isolation_snapshot_missing", "metadata": metadata}

            nonce = uuid.uuid4().hex[:16]
            sibling_name = f"aether-harbor-verifier-{nonce}"
            ready_marker = f"/.__aether_verifier_ready_{nonce}"
            bootstrap = (
                'set -eu; src="$1"; ready="$2"; '
                'test -d "$src"; rm -rf /app; mv "$src" /app; '
                'touch "$ready"; exec bash -lc "while :; do sleep 3600; done"'
            )
            run_args = [
                "docker", "run", "--detach", "--name", sibling_name,
                "--network", "none", "--workdir", "/",
                "--entrypoint", "bash", image_tag,
                "-lc", bootstrap, "aether-harbor-verifier", source, ready_marker,
            ]
            setup, setup_error = self._docker_host_call(run_args, timeout_s=120)
            if setup is None or setup.returncode != 0:
                detail = setup_error or ((setup.stderr or setup.stdout)[-1000:] if setup else "")
                error = "verifier_independent_isolation_docker_run_failed:" + detail
            else:
                ready = False
                ready_deadline = time.monotonic() + 120.0
                ready_error = ""
                while time.monotonic() < ready_deadline:
                    probe, probe_error = self._docker_host_call(
                        ["docker", "exec", sibling_name, "test", "-f", ready_marker],
                        timeout_s=5,
                    )
                    if probe is not None and probe.returncode == 0:
                        ready = True
                        break
                    ready_error = probe_error or (
                        ((probe.stderr or probe.stdout)[-500:]) if probe is not None else ""
                    )
                    time.sleep(0.1)
                if not ready:
                    error = "verifier_independent_isolation_docker_ready_failed:" + ready_error

            if not error:
                for clean, content in clean_fixtures.items():
                    encoded = __import__('base64').b64encode(content.encode('utf-8')).decode('ascii')
                    target = "/app/" + clean
                    parent = str(PurePosixPath(target).parent)
                    fixture_cmd = (
                        f"test ! -e {shlex.quote(target)} && test ! -L {shlex.quote(target)} && "
                        f"mkdir -p {shlex.quote(parent)} && "
                        f"printf '%s' {shlex.quote(encoded)} | base64 -d > {shlex.quote(target)}"
                    )
                    written, write_error = self._docker_host_call(
                        ["docker", "exec", "--workdir", "/app", sibling_name, "bash", "-lc", fixture_cmd],
                        timeout_s=60,
                    )
                    if written is None or written.returncode != 0:
                        detail = write_error or ((written.stderr or written.stdout)[-1000:] if written else "")
                        error = "verifier_independent_isolation_fixture_materialization_failed:" + detail
                        break
            metadata["materialized_fixture_count"] = len(clean_fixtures)

            if not error:
                exec_args = [
                    "docker", "exec", "--workdir", "/app", sibling_name,
                    "bash", "-lc", str(command),
                ]
                command_started = time.monotonic()
                executed, exec_error = self._docker_host_call(
                    exec_args, timeout_s=max(1, int(timeout_s)),
                )
                command_elapsed = time.monotonic() - command_started
                if executed is None:
                    error = "verifier_independent_isolation_docker_exec_failed:" + exec_error
                else:
                    result = CommandResult(
                        command=str(command),
                        exit_code=int(executed.returncode),
                        stdout=str(executed.stdout or ""),
                        stderr=str(executed.stderr or ""),
                        stdout_bytes_total=len(str(executed.stdout or "").encode("utf-8", "replace")),
                        stderr_bytes_total=len(str(executed.stderr or "").encode("utf-8", "replace")),
                        timed_out=False,
                        metrics={"command_execution_elapsed_s": command_elapsed},
                        provenance=("harbor:docker_snapshot_sibling",),
                    )
                    metadata["command_execution_elapsed_s"] = round(command_elapsed, 6)
                    metadata["independent_isolation_verified"] = True

            # Per-command cleanup: sibling must disappear. The immutable image is
            # intentionally retained only for activation-scoped reuse and is
            # released by VerifierOverlay.teardown.
            if sibling_name:
                self._docker_host_call(["docker", "rm", "-f", sibling_name], timeout_s=30)
                sibling_inspect, sibling_inspect_error = self._docker_host_call(
                    ["docker", "inspect", sibling_name], timeout_s=15,
                )
                sibling_absent, sibling_absence_error = self._docker_inspect_proves_absent(
                    sibling_inspect, sibling_inspect_error, kind="sibling container",
                )
            else:
                sibling_absent, sibling_inspect_error, sibling_absence_error = True, "", ""
            metadata["sibling_container_removed"] = sibling_absent
            metadata["sibling_inspect_error"] = sibling_inspect_error or sibling_absence_error

            image_absent = False
            image_error = ""
            if not activation_scoped:
                if image_created_here:
                    self._docker_host_call(["docker", "image", "rm", "-f", image_tag], timeout_s=60)
                image_inspect, image_inspect_error = self._docker_host_call(
                    ["docker", "image", "inspect", image_tag], timeout_s=15,
                )
                image_absent, image_absence_error = self._docker_inspect_proves_absent(
                    image_inspect, image_inspect_error, kind="snapshot image",
                )
                image_error = image_inspect_error or image_absence_error
                metadata["snapshot_image_removed"] = image_absent
            else:
                metadata["snapshot_image_retained_for_activation"] = True
                metadata["snapshot_cleanup_deferred_to_activation"] = True

            parent_runnable, parent_runnable_error, parent_probe_count = (
                self._wait_for_docker_container_runnable(container_id, timeout_s=10.0)
            )
            metadata.update({
                "isolation_cleanup_verified": bool(sibling_absent and (activation_scoped or image_absent)),
                "snapshot_image_inspect_error": image_error,
                "parent_runnable_after_snapshot": parent_runnable,
                "parent_runnable_probe_count": max(
                    int(metadata.get("parent_runnable_probe_count", 0) or 0), parent_probe_count,
                ),
                "parent_runnable_probe_error": parent_runnable_error,
            })
            if not metadata["isolation_cleanup_verified"]:
                error = error or "verifier_independent_isolation_docker_cleanup_failed"
            if not parent_runnable:
                error = error or (
                    "verifier_independent_isolation_parent_not_runnable_after_snapshot:"
                    + parent_runnable_error
                )

        if (
            error
            or result is None
            or not metadata["independent_isolation_verified"]
            or not metadata["isolation_cleanup_verified"]
        ):
            return {"error": error or "verifier_independent_isolation_not_verified", "metadata": metadata}
        return {"result": result, "metadata": metadata}

    def release_independent_verifier_snapshot(self, workspace_root: str) -> dict[str, Any]:
        """Release one activation-scoped immutable verifier image and prove absence."""
        source = str(workspace_root or "").strip()
        with self._verifier_snapshot_lock:
            cached = self._verifier_snapshot_cache.pop(source, None)
            if cached is None:
                return {"released": True, "snapshot_present": False}
            image_tag = str(cached.get("image_tag") or "")
            if not image_tag:
                return {"released": False, "error": "verifier_snapshot_cache_missing_image_tag"}
            self._docker_host_call(["docker", "image", "rm", "-f", image_tag], timeout_s=60)
            inspected, inspect_error = self._docker_host_call(
                ["docker", "image", "inspect", image_tag], timeout_s=15,
            )
            absent, absence_error = self._docker_inspect_proves_absent(
                inspected, inspect_error, kind="snapshot image",
            )
            return {
                "released": bool(absent),
                "snapshot_present": True,
                "snapshot_image_removed": bool(absent),
                "snapshot_image_inspect_error": inspect_error or absence_error,
                "workspace_snapshot_path_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
            }

    def _await(self, awaitable: Awaitable[_T], *, timeout_s: float) -> _T:
        raise_if_run_deadline_exceeded()
        if not self.event_loop.is_running():
            raise RuntimeError("Harbor event loop is not running")
        future = asyncio.run_coroutine_threadsafe(awaitable, self.event_loop)
        return future.result(timeout=max(1.0, float(timeout_s) + 5.0))

    def _exec(self, command: str, *, cwd: str | None = None, timeout_s: int = 30) -> Any:
        raise_if_run_deadline_exceeded()
        return self._await(
            self.environment.exec(
                command=str(command),
                cwd=self._cwd(cwd),
                env=self.default_env or None,
                timeout_sec=max(1, int(timeout_s)),
            ),
            timeout_s=max(1, int(timeout_s)),
        )

    @staticmethod
    def _result_fields(result: Any) -> tuple[int, str, str]:
        code = int(
            getattr(
                result, "return_code",
                getattr(result, "exit_code", getattr(result, "returncode", 0)),
            )
            or 0
        )
        stdout = str(getattr(result, "stdout", "") or "")
        stderr = str(getattr(result, "stderr", "") or "")
        return code, stdout, stderr

    def _download_workspace_file(self, remote: str, local: Path) -> None:
        """Download one workspace file while preserving Executor missing-file semantics.

        Harbor 0.20 Docker surfaces a missing ``docker compose cp`` source as a
        generic RuntimeError. Kernel file actions rely on FileNotFoundError to
        distinguish a legitimately absent pre-write artifact from transport
        failure. Probe existence only after a failed download: absence is
        normalized, while a file that still exists preserves the original
        Harbor error and therefore fails closed.
        """
        try:
            self._await(self.environment.download_file(remote, local), timeout_s=60)
        except Exception as exc:  # noqa: BLE001 - classify Harbor transport failure by world state
            try:
                present = self.exists(remote)
            except Exception:  # noqa: BLE001 - retain the original transport authority
                raise exc
            if not present:
                raise FileNotFoundError(remote) from exc
            raise

    def read_file(self, path: str) -> str:
        remote = self._remote_path(path)
        local = self.local_state_dir / f"download-{uuid.uuid4().hex}"
        try:
            self._download_workspace_file(remote, local)
            return local.read_text(encoding="utf-8", errors="replace")
        finally:
            local.unlink(missing_ok=True)

    def read_file_bytes(self, path: str) -> bytes:
        remote = self._remote_path(path)
        local = self.local_state_dir / f"download-{uuid.uuid4().hex}"
        try:
            self._download_workspace_file(remote, local)
            return local.read_bytes()
        finally:
            local.unlink(missing_ok=True)

    @staticmethod
    def _verifier_world_path_denied(path: str) -> bool:
        normalized = str(PurePosixPath(path))
        for prefix in _VERIFIER_WORLD_DENIED_PREFIXES:
            clean = prefix.rstrip("/")
            if normalized == clean or normalized.startswith(clean + "/"):
                return True
        return False

    def set_verifier_world_roots(self, roots: tuple[str, ...] | list[str]) -> None:
        """Install literal task-public absolute roots for independent verification.

        The workspace is always included. Roots are lexical task-surface facts,
        not semantic interpretations. Each actual read re-resolves both target
        and matching root remotely before containment is accepted.
        """
        normalized: list[str] = [self.workspace_root]
        for value in roots:
            raw = str(value or "").strip().replace("\\", "/")
            if not raw.startswith("/") or raw == "/" or "\x00" in raw:
                continue
            candidate = str(PurePosixPath(raw))
            if self._verifier_world_path_denied(candidate):
                continue
            if candidate not in normalized:
                normalized.append(candidate)
        self._verifier_world_roots = tuple(normalized)

    @staticmethod
    def _path_within(path: str, root: str) -> bool:
        clean = str(PurePosixPath(root)).rstrip("/") or "/"
        value = str(PurePosixPath(path))
        return value == clean or (clean != "/" and value.startswith(clean + "/"))

    def _verifier_world_root_allows(self, raw: str, resolved: str) -> bool:
        for root in self._verifier_world_roots:
            if not self._path_within(raw, root):
                continue
            root_result = self._exec(
                f"realpath {shlex.quote(root)}", cwd=self.workspace_root, timeout_s=15,
            )
            code, stdout, _stderr = self._result_fields(root_result)
            if code != 0:
                continue
            rows = [line.strip() for line in stdout.splitlines() if line.strip()]
            if len(rows) == 1 and rows[0].startswith("/") and self._path_within(resolved, rows[0]):
                return True
        return False


    def resolve_verifier_read_path(self, path: str) -> str:
        """Resolve one absolute task-world file path for read-only verification.

        This capability is intentionally separate from ``read_file``: it does
        not widen Solver workspace access or any write surface.  Remote realpath
        resolution happens before the privacy policy so symlink aliases cannot
        bypass denied pseudo-filesystems, secret roots, or benchmark-private
        grader/solution roots.
        """
        raw = str(path or "").strip().replace("\\", "/")
        if not raw.startswith("/") or "\x00" in raw:
            raise ValueError("verifier world read requires one absolute path")
        if any(token in raw for token in ("*", "?", "[")):
            raise ValueError("verifier world read does not accept path globs")
        result = self._exec(
            f"realpath {shlex.quote(raw)}",
            cwd=self.workspace_root,
            timeout_s=15,
        )
        code, stdout, stderr = self._result_fields(result)
        if code != 0:
            raise FileNotFoundError(raw)
        rows = [line.strip() for line in stdout.splitlines() if line.strip()]
        if len(rows) != 1 or not rows[0].startswith("/"):
            raise RuntimeError(
                "verifier world path resolution returned an invalid result: "
                + (stderr or stdout)[-500:]
            )
        resolved = str(PurePosixPath(rows[0]))
        if self._verifier_world_path_denied(resolved):
            raise ValueError(f"verifier world path denied by privacy boundary: {resolved}")
        if not self._verifier_world_root_allows(raw, resolved):
            raise ValueError(
                f"verifier world path is not under a task-public absolute root: {raw}"
            )
        return resolved

    def resolve_task_artifact_read_path(self, path: str) -> str:
        """Resolve one dynamic task-container artifact for exact-byte staging.

        Solver-created artifacts are not necessarily named in the original task
        text (for example a rendered frame under /tmp). Artifact inspection may
        therefore read an exact absolute task-world file after remote realpath
        resolution, while retaining the hard privacy boundary for grader,
        solution, secret, and pseudo-filesystem roots. This capability is
        read-only and does not widen ordinary Solver file or write access.
        """
        raw = str(path or "").strip().replace("\\", "/")
        if not raw.startswith("/") or "\x00" in raw:
            raise ValueError("task artifact read requires one absolute path")
        if any(token in raw for token in ("*", "?", "[")):
            raise ValueError("task artifact read does not accept path globs")
        result = self._exec(
            f"realpath {shlex.quote(raw)}", cwd=self.workspace_root, timeout_s=15,
        )
        code, stdout, stderr = self._result_fields(result)
        if code != 0:
            raise FileNotFoundError(raw)
        rows = [line.strip() for line in stdout.splitlines() if line.strip()]
        if len(rows) != 1 or not rows[0].startswith("/"):
            raise RuntimeError(
                "task artifact path resolution returned an invalid result: "
                + (stderr or stdout)[-500:]
            )
        resolved = str(PurePosixPath(rows[0]))
        if self._verifier_world_path_denied(resolved):
            raise ValueError(f"task artifact path denied by privacy boundary: {resolved}")
        return resolved

    def read_verifier_file(self, path: str) -> str:
        resolved = self.resolve_verifier_read_path(path)
        local = self.local_state_dir / f"verifier-world-{uuid.uuid4().hex}"
        try:
            self._await(self.environment.download_file(resolved, local), timeout_s=60)
            return local.read_text(encoding="utf-8", errors="replace")
        finally:
            local.unlink(missing_ok=True)

    def read_verifier_file_bytes(self, path: str) -> bytes:
        resolved = self.resolve_verifier_read_path(path)
        local = self.local_state_dir / f"verifier-world-{uuid.uuid4().hex}"
        try:
            self._await(self.environment.download_file(resolved, local), timeout_s=60)
            return local.read_bytes()
        finally:
            local.unlink(missing_ok=True)

    def write_file(self, path: str, content: str) -> None:
        remote = self._remote_path(path)
        parent = str(PurePosixPath(remote).parent)
        mkdir = self._exec(f"mkdir -p {shlex.quote(parent)}", timeout_s=30)
        code, _stdout, stderr = self._result_fields(mkdir)
        if code != 0:
            raise RuntimeError(f"failed to create remote parent {parent}: {stderr}")
        local = self.local_state_dir / f"upload-{uuid.uuid4().hex}"
        try:
            local.write_text(content, encoding="utf-8")
            self._await(self.environment.upload_file(local, remote), timeout_s=60)
        finally:
            local.unlink(missing_ok=True)

    def _capture_remote_workspace_snapshot(self) -> RemoteWorkspaceSnapshot:
        command = remote_workspace_snapshot_command(self.workspace_root)
        try:
            result = self._exec(command, cwd=self.workspace_root, timeout_s=30)
            code, stdout, stderr = self._result_fields(result)
        except Exception as exc:  # noqa: BLE001 - observation availability is explicit state
            return parse_remote_workspace_snapshot(
                "",
                root=self.workspace_root,
                command_succeeded=False,
                detail=f"{type(exc).__name__}: {exc}",
            )
        return parse_remote_workspace_snapshot(
            stdout,
            root=self.workspace_root,
            command_succeeded=(code == 0),
            detail=(stderr or stdout)[-1000:] if code != 0 else "",
        )

    def run_tracked_command(
        self,
        command: str,
        *,
        cwd: str | None = None,
        timeout_s: int = 30,
    ) -> CommandResult:
        """Run one task-authorized command with bounded remote workspace deltas.

        Environment/configuration probes intentionally continue to use the raw
        ``run_command`` route, so read-only setup does not pay two workspace
        inventories per probe. Kernel task-action frontiers opt into this method
        through the generic stateful-command helper.
        """
        before = self._capture_remote_workspace_snapshot()
        transport_error: Exception | None = None
        try:
            result = self.run_command(command, cwd=cwd, timeout_s=timeout_s)
        except Exception as exc:  # noqa: BLE001 - preserve post-action state truth
            # A Harbor transport failure does not prove the attempted command
            # had no effect. Capture the post-frontier state before returning a
            # failure result so proof freshness/integrity can still fail closed.
            transport_error = exc
            result = CommandResult(
                command=command,
                exit_code=125,
                stderr=f"{type(exc).__name__}: {exc}",
                provenance=("harbor:BaseEnvironment.exec:transport_failure",),
            )
        after = self._capture_remote_workspace_snapshot()
        state_delta = diff_remote_workspace_snapshots(before, after)
        if transport_error is not None:
            state_delta = {
                **state_delta,
                "action_transport_status": "failed_after_action_attempt",
                "action_transport_error_type": type(transport_error).__name__,
            }
        modified = tuple(sorted(set(
            tuple(state_delta.get("content_changed_paths", ()))
            + tuple(state_delta.get("metadata_changed_paths", ()))
        )))
        produced = tuple(state_delta.get("created_paths", ()))
        removed = tuple(state_delta.get("removed_paths", ()))
        return replace(
            result,
            modified_paths=modified,
            produced_artifacts=produced,
            removed_paths=removed,
            state_delta=state_delta,
        )

    def _terminal_state_delta(self) -> dict[str, Any]:
        """Observe task-workspace changes since the previous terminal frontier."""
        current = self._capture_remote_workspace_snapshot()
        previous = self._terminal_workspace_state or current
        delta = diff_remote_workspace_snapshots(previous, current)
        self._terminal_workspace_state = current
        return delta

    def _docker_environment_type(self) -> bool:
        env_type = getattr(self.environment, "type", None)
        try:
            raw = env_type() if callable(env_type) else ""
        except Exception:
            return False
        value = getattr(raw, "value", raw)
        return str(value).strip().lower() == "docker"

    def _docker_exec_container(
        self, container_id: str, command: str, *, cwd: str | None = None, timeout_s: int = 30,
    ) -> subprocess.CompletedProcess[str]:
        """Execute against one exact Docker container, never a Compose service alias."""
        if not container_id:
            raise RuntimeError("exact Docker container identity is required")
        args = ["docker", "exec", "--workdir", self._cwd(cwd)]
        for key, value in sorted(self.default_env.items()):
            args.extend(["--env", f"{key}={value}"])
        args.extend([container_id, "sh", "-lc", str(command)])
        result, error = self._docker_host_call(args, timeout_s=max(1, int(timeout_s)))
        if result is None:
            raise RuntimeError("exact Docker exec failed: " + (error or "unknown host error"))
        return result

    def _remote_exec_for_process(
        self, record: _RemoteProcess, command: str, *, cwd: str | None = None, timeout_s: int = 30,
    ) -> Any:
        if record.container_id:
            return self._docker_exec_container(
                record.container_id, command, cwd=cwd, timeout_s=timeout_s
            )
        return self._exec(command, cwd=cwd, timeout_s=timeout_s)

    def _ensure_subreaper_uploaded(self, container_id: str = "") -> str:
        """Upload the static child-subreaper to the exact Docker owner when known."""
        if self._subreaper_uploaded:
            return self._subreaper_remote_path
        arch = (
            self._docker_exec_container(container_id, "uname -m", cwd=self.workspace_root, timeout_s=10)
            if container_id
            else self._exec("uname -m", cwd=self.workspace_root, timeout_s=10)
        )
        code, stdout, stderr = self._result_fields(arch)
        value = stdout.strip().lower()
        if code != 0 or value not in {"x86_64", "amd64"}:
            raise RuntimeError(
                "Harbor safe foreground command supervision requires Linux x86_64; "
                f"observed architecture={value!r} detail={(stderr or stdout)[-500:]}"
            )
        local = Path(__file__).with_name("harbor_subreaper_linux_x86_64")
        if not local.is_file():
            raise RuntimeError("packaged Harbor subreaper helper is missing")
        observed = hashlib.sha256(local.read_bytes()).hexdigest()
        expected = "b5c68b3f11f357ba14fed69d82a192d7a2853e05f059af32a0415da0301dc2f4"
        if observed != expected:
            raise RuntimeError(
                f"packaged Harbor subreaper helper hash mismatch: {observed} != {expected}"
            )
        if container_id:
            copied, copy_error = self._docker_host_call(
                ["docker", "cp", str(local), f"{container_id}:{self._subreaper_remote_path}"],
                timeout_s=60,
            )
            if copied is None or copied.returncode != 0:
                detail = copy_error or (
                    ((copied.stderr or copied.stdout)[-1000:]) if copied is not None else "copy failed"
                )
                raise RuntimeError("failed to upload packaged Harbor subreaper to exact owner: " + detail)
            chmod = self._docker_exec_container(
                container_id, f"chmod 700 {shlex.quote(self._subreaper_remote_path)}", timeout_s=15
            )
        else:
            self._await(
                self.environment.upload_file(local, self._subreaper_remote_path), timeout_s=60
            )
            chmod = self._exec(
                f"chmod 700 {shlex.quote(self._subreaper_remote_path)}", timeout_s=15
            )
        c, _o, e = self._result_fields(chmod)
        if c != 0:
            raise RuntimeError(f"failed to activate packaged Harbor subreaper: {e}")
        self._subreaper_uploaded = True
        return self._subreaper_remote_path

    def _launch_supervised_foreground_command(
        self, command: str, *, cwd: str | None = None,
    ) -> _RemoteProcess:
        """Launch one synchronous command under timeout-safe remote supervision."""
        generation = uuid.uuid4().hex
        remote_dir = f"{HARBOR_CONTROL_ROOT}/harbor_jobs/foreground-{generation}"
        stdout_path = f"{remote_dir}/stdout.log"
        stderr_path = f"{remote_dir}/stderr.log"
        exit_path = f"{remote_dir}/exit_code"
        cleanup_path = f"{remote_dir}/cleanup_status"
        pid_path = f"{remote_dir}/pid"
        wrapper_path = f"{remote_dir}/run.sh"
        remote_cwd = self._cwd(cwd)
        container_id = ""
        if self._docker_environment_type():
            container_id, lookup_error = self._harbor_docker_main_container_id()
            if lookup_error or not container_id:
                raise RuntimeError(
                    "Harbor supervised foreground exact-owner lookup failed: "
                    + (lookup_error or "missing container id")
                )
            mkdir = self._docker_exec_container(
                container_id, f"mkdir -p {shlex.quote(remote_dir)}", timeout_s=30
            )
            code, stdout, stderr = self._result_fields(mkdir)
            if code != 0:
                raise RuntimeError(
                    "Harbor supervised foreground exact-owner mkdir failed: "
                    + (stderr or stdout)[-1000:]
                )
            helper = self._ensure_subreaper_uploaded(container_id)
            launch_command = (
                f"nohup setsid {shlex.quote(helper)} "
                f"{shlex.quote(exit_path)} {shlex.quote(cleanup_path)} "
                f"{shlex.quote(remote_cwd)} {shlex.quote(str(command))} "
                f">{shlex.quote(stdout_path)} 2>{shlex.quote(stderr_path)} </dev/null & "
                f"pid=$!; printf '%s\\n' \"$pid\" > {shlex.quote(pid_path)}; "
                f"printf '%s\\n' \"$pid\""
            )
        else:
            self._exec(f"mkdir -p {shlex.quote(remote_dir)}", timeout_s=30)
            # Non-Docker test providers retain the lightweight process-group path.
            wrapper = "\n".join([
                "#!/usr/bin/env sh",
                "set +e",
                f"cd {shlex.quote(remote_cwd)} || exit 125",
                f"bash -c {shlex.quote(str(command))}",
                "code=$?",
                f"printf '%s\\n' \"$code\" > {shlex.quote(exit_path)}",
                "exit \"$code\"",
                "",
            ])
            self._upload_script(wrapper, wrapper_path)
            python_setsid = (
                "import os,sys; os.setsid(); "
                "os.execvp('sh', ['sh', sys.argv[1]])"
            )
            launch_command = (
                f"chmod +x {shlex.quote(wrapper_path)} && "
                f"if command -v setsid >/dev/null 2>&1; then "
                f"nohup setsid sh {shlex.quote(wrapper_path)} >{shlex.quote(stdout_path)} "
                f"2>{shlex.quote(stderr_path)} </dev/null & "
                f"elif command -v python3 >/dev/null 2>&1; then "
                f"nohup python3 -c {shlex.quote(python_setsid)} {shlex.quote(wrapper_path)} "
                f">{shlex.quote(stdout_path)} 2>{shlex.quote(stderr_path)} </dev/null & "
                f"elif command -v python >/dev/null 2>&1; then "
                f"nohup python -c {shlex.quote(python_setsid)} {shlex.quote(wrapper_path)} "
                f">{shlex.quote(stdout_path)} 2>{shlex.quote(stderr_path)} </dev/null & "
                f"else printf '%s\\n' 'aether: no setsid-capable launcher' >&2; exit 126; fi; "
                f"pid=$!; printf '%s\\n' \"$pid\" > {shlex.quote(pid_path)}; "
                f"printf '%s\\n' \"$pid\""
            )

        result = (
            self._docker_exec_container(container_id, launch_command, cwd=remote_cwd, timeout_s=30)
            if container_id
            else self._exec(launch_command, cwd=remote_cwd, timeout_s=30)
        )
        code, stdout, stderr = self._result_fields(result)
        if code != 0:
            try:
                self._exec(f"rm -rf {shlex.quote(remote_dir)}", timeout_s=15)
            except Exception:
                pass
            raise RuntimeError(
                "Harbor supervised foreground launch failed: " + (stderr or stdout)[-1000:]
            )
        try:
            pid = int(stdout.strip().splitlines()[-1])
        except (IndexError, ValueError) as exc:
            raise RuntimeError(
                f"Harbor supervised foreground launch returned invalid pid: {stdout!r}"
            ) from exc
        return _RemoteProcess(
            process_id=f"harbor-foreground:{generation}",
            name="aether-foreground-command",
            command=command,
            remote_dir=remote_dir,
            pid=pid,
            generation=generation,
            interactive=False,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            exit_path=exit_path,
            cleanup_path=cleanup_path,
            container_id=container_id,
        )

    def _download_remote_process_streams(self, record: _RemoteProcess) -> tuple[str, str]:
        outputs: list[str] = []
        for label, remote in (("stdout", record.stdout_path), ("stderr", record.stderr_path)):
            local = self.local_state_dir / f"foreground-{record.generation}-{label}.log"
            try:
                try:
                    if record.container_id:
                        copied, copy_error = self._docker_host_call(
                            ["docker", "cp", f"{record.container_id}:{remote}", str(local)],
                            timeout_s=60,
                        )
                        if copied is None or copied.returncode != 0:
                            detail = copy_error or (
                                ((copied.stderr or copied.stdout)[-1000:])
                                if copied is not None else "copy failed"
                            )
                            raise RuntimeError(
                                "exact-owner docker cp failed for " + label + ": " + detail
                            )
                    else:
                        self._await(self.environment.download_file(remote, local), timeout_s=60)
                    outputs.append(local.read_text(encoding="utf-8", errors="replace"))
                except Exception as exc:
                    raise RuntimeError(
                        f"Harbor supervised foreground {label} download failed: "
                        f"{type(exc).__name__}: {exc}"
                    ) from exc
            finally:
                local.unlink(missing_ok=True)
        return outputs[0], outputs[1]

    def _terminate_supervised_foreground(self, record: _RemoteProcess) -> tuple[bool, str]:
        """Terminate a timed-out foreground command and prove cleanup authority."""
        pid = int(record.pid)
        if self._docker_environment_type() and record.cleanup_path:
            script = " ".join([
                f"pid={pid};",
                f"cleanup={shlex.quote(record.cleanup_path)};",
                "pid_alive() { kill -0 \"$pid\" 2>/dev/null; };",
                "kill -TERM \"$pid\" 2>/dev/null || true;",
                "i=0; while pid_alive && [ \"$i\" -lt 120 ]; do "
                "sleep 0.05; i=$((i+1)); done;",
                "if pid_alive; then printf '%s\\n' 'aether: subreaper did not drain' >&2; exit 125; fi;",
                "status=$(cat \"$cleanup\" 2>/dev/null || true);",
                "if [ \"$status\" != ok ]; then "
                "printf '%s\\n' 'aether: subreaper cleanup proof missing' >&2; exit 125; fi;",
                "printf '%s\\n' 'aether: remote descendant tree terminated and reaped'",
            ])
            result = self._remote_exec_for_process(
                record, script, cwd=self.workspace_root, timeout_s=10
            )
            code, stdout, stderr = self._result_fields(result)
            return code == 0, (stderr or stdout)[-2000:]

        # Non-Docker test provider fallback: process-group authority only.
        script = " ".join([
            f"pid={pid};",
            "group_alive() { kill -0 -\"$pid\" 2>/dev/null; };",
            "pid_alive() { kill -0 \"$pid\" 2>/dev/null; };",
            "kill -TERM -\"$pid\" 2>/dev/null || true;",
            "kill -TERM \"$pid\" 2>/dev/null || true;",
            "i=0; while { group_alive || pid_alive; } && [ \"$i\" -lt 20 ]; do "
            "sleep 0.05; i=$((i+1)); done;",
            "if group_alive || pid_alive; then "
            "kill -KILL -\"$pid\" 2>/dev/null || true; "
            "kill -KILL \"$pid\" 2>/dev/null || true; fi;",
            "i=0; while { group_alive || pid_alive; } && [ \"$i\" -lt 20 ]; do "
            "sleep 0.05; i=$((i+1)); done;",
            "if group_alive || pid_alive; then exit 125; fi;",
            "printf '%s\\n' 'aether: remote process group terminated'",
        ])
        result = self._exec(script, cwd=self.workspace_root, timeout_s=10)
        code, stdout, stderr = self._result_fields(result)
        return code == 0, (stderr or stdout)[-2000:]

    def _cleanup_supervised_foreground(self, record: _RemoteProcess) -> None:
        try:
            self._remote_exec_for_process(
                record, f"rm -rf {shlex.quote(record.remote_dir)}", timeout_s=15
            )
        except Exception:
            pass

    def run_command(
        self,
        command: str,
        *,
        cwd: str | None = None,
        timeout_s: int = 30,
    ) -> CommandResult:
        raise_if_run_deadline_exceeded()
        started = time.monotonic()
        effective_timeout = max(1, int(timeout_s))
        # Timeout authority begins when run_command is invoked, not after the
        # remote launch handshake returns. The child may already be executing
        # while launch/upload/transport acknowledgement is in flight; granting
        # a fresh timeout after that handshake can let a timed-out command
        # mutate task state beyond its declared authority under host load.
        deadline = started + effective_timeout
        launch_perf_started = time.perf_counter()
        record = self._launch_supervised_foreground_command(command, cwd=cwd)
        supervision_launch_elapsed_s = time.perf_counter() - launch_perf_started
        supervision_status_probe_count = 0
        supervision_status_probe_elapsed_s = 0.0
        timed_out = False
        run_deadline_error: KernelRunTimeout | None = None
        exit_code: int | None = None
        try:
            exit_visibility_deadline: float | None = None
            last_status_detail = ""
            while True:
                status_perf_started = time.perf_counter()
                try:
                    live, observed_exit, status_detail = self._remote_status(record)
                except KernelRunTimeout as exc:
                    # Global task authority expired while this already-started
                    # command was live. Stop normal observation immediately,
                    # then use the narrow cleanup scope below to terminate the
                    # owned process before propagating the task timeout.
                    run_deadline_error = exc
                    timed_out = True
                    break
                supervision_status_probe_elapsed_s += time.perf_counter() - status_perf_started
                supervision_status_probe_count += 1
                last_status_detail = status_detail
                now = time.monotonic()
                if not live:
                    if observed_exit is not None:
                        exit_code = observed_exit
                        break
                    # The wrapper writes exit_code immediately before it exits,
                    # but Harbor transports/filesystems can expose process death
                    # one observation before that tiny status file is readable.
                    # Do not misclassify this visibility race as a task failure.
                    if exit_visibility_deadline is None:
                        exit_visibility_deadline = min(deadline, now + 1.0)
                    if now >= exit_visibility_deadline:
                        raise RuntimeError(
                            "Harbor supervised foreground command exited without a "
                            "recorded exit code after status visibility grace"
                            + ((": " + last_status_detail) if last_status_detail else "")
                        )
                    time.sleep(min(0.05, max(0.0, exit_visibility_deadline - now)))
                    continue
                remaining = deadline - now
                if remaining <= 0:
                    timed_out = True
                    break
                time.sleep(min(0.05, remaining))
            if timed_out:
                with run_deadline_cleanup_authority():
                    terminated, cleanup_detail = self._terminate_supervised_foreground(record)
                    if not terminated:
                        raise RuntimeError(
                            "Harbor command timeout cleanup could not prove process-group termination: "
                            + cleanup_detail
                        )
                    output_download_perf_started = time.perf_counter()
                    stdout, child_stderr = self._download_remote_process_streams(record)
                    supervision_output_download_elapsed_s = time.perf_counter() - output_download_perf_started
                if run_deadline_error is not None:
                    raise run_deadline_error
            else:
                output_download_perf_started = time.perf_counter()
                stdout, child_stderr = self._download_remote_process_streams(record)
                supervision_output_download_elapsed_s = time.perf_counter() - output_download_perf_started
            if timed_out:
                timeout_detail = (
                    f"command timed out after {timeout_s}s; remote descendant tree terminated"
                    if self._docker_environment_type()
                    else f"command timed out after {timeout_s}s; remote process group terminated"
                )
                stderr = timeout_detail + (("\n" + child_stderr) if child_stderr else "")
                return CommandResult(
                    command=command,
                    exit_code=124,
                    stdout=stdout,
                    stderr=stderr,
                    timed_out=True,
                    metrics={
                        "wall_time_s": time.monotonic() - started,
                        "remote_process_group_terminated": True,
                        "remote_descendant_tree_terminated": self._docker_environment_type(),
                        "supervision_launch_elapsed_s": supervision_launch_elapsed_s,
                        "supervision_status_probe_count": supervision_status_probe_count,
                        "supervision_status_probe_elapsed_s": supervision_status_probe_elapsed_s,
                        "supervision_output_download_elapsed_s": supervision_output_download_elapsed_s,
                    },
                    provenance=(("harbor:subreaper_descendant_tree",) if self._docker_environment_type() else ("harbor:supervised_process_group",)),
                )
            if exit_code is None:
                raise RuntimeError(
                    "Harbor supervised foreground command exited without a recorded exit code"
                )
            return CommandResult(
                command=command,
                exit_code=int(exit_code),
                stdout=stdout,
                stderr=child_stderr,
                timed_out=False,
                metrics={
                    "wall_time_s": time.monotonic() - started,
                    "supervision_launch_elapsed_s": supervision_launch_elapsed_s,
                    "supervision_status_probe_count": supervision_status_probe_count,
                    "supervision_status_probe_elapsed_s": supervision_status_probe_elapsed_s,
                    "supervision_output_download_elapsed_s": supervision_output_download_elapsed_s,
                },
                provenance=(("harbor:subreaper_descendant_tree",) if self._docker_environment_type() else ("harbor:supervised_process_group",)),
            )
        finally:
            with run_deadline_cleanup_authority():
                self._cleanup_supervised_foreground(record)

    def run_read_only_command(
        self, command: str, *, cwd: str | None = None, timeout_s: int = 5,
    ) -> CommandResult:
        """Run one allow-listed snapshot command outside the solver supervisor.

        The direct Harbor exec has its own timeout and is marshalled onto the
        event loop independently; it does not touch solver process registries,
        workspace snapshots, or action receipts.
        """
        from .challenger_runtime.state_snapshot import validate_read_only_command
        if not validate_read_only_command(command):
            raise ValueError("read-only executor refused a command outside the snapshot allow-list")
        started = time.monotonic()
        effective_timeout = max(1, min(5, int(timeout_s)))
        result = self._exec(command, cwd=cwd, timeout_s=effective_timeout)
        code, stdout, stderr = self._result_fields(result)
        return CommandResult(command=command, exit_code=code, stdout=stdout[:6000],
                             stderr=stderr[:2000], timed_out=code == 124,
                             metrics={"wall_time_s": max(0.0, time.monotonic() - started)},
                             provenance=("harbor:read_only_snapshot",))

    def resolve_state_snapshot_path(self, path: str, *, workspace_root: str | None = None,
                                    command_log: list[dict[str, Any]] | None = None) -> str | None:
        """Resolve a candidate inside the remote workspace before any snapshot read.

        This uses a fixed remote realpath probe because host-side pathlib cannot see
        symlinks inside Harbor's container filesystem. Failure to resolve either the
        trusted root or candidate is fail-closed.
        """
        try:
            if workspace_root and self._normalize_workspace_root(workspace_root) != self.workspace_root:
                return None
            candidate = self._remote_path(path)
            root_command = f"realpath -e -- {shlex.quote(self.workspace_root)}"
            root_started = time.monotonic()
            root_started_wall = time.time()
            root_result = self._exec(root_command, cwd=self.workspace_root, timeout_s=1)
            root_code, root_out, root_err = self._result_fields(root_result)
            if command_log is not None:
                command_log.append({"command": root_command, "exit_code": root_code,
                                    "stdout": root_out[:1000], "stderr": root_err[:500],
                                    "started_at_unix_s": round(root_started_wall, 3),
                                    "completed_at_unix_s": round(time.time(), 3),
                                    "elapsed_s": round(time.monotonic() - root_started, 6)})
            if root_code != 0 or not root_out.strip():
                return None
            candidate_command = f"realpath -m -- {shlex.quote(candidate)}"
            candidate_started = time.monotonic()
            candidate_started_wall = time.time()
            candidate_result = self._exec(candidate_command, cwd=self.workspace_root, timeout_s=1)
            candidate_code, candidate_out, candidate_err = self._result_fields(candidate_result)
            if command_log is not None:
                command_log.append({"command": candidate_command, "exit_code": candidate_code,
                                    "stdout": candidate_out[:1000], "stderr": candidate_err[:500],
                                    "started_at_unix_s": round(candidate_started_wall, 3),
                                    "completed_at_unix_s": round(time.time(), 3),
                                    "elapsed_s": round(time.monotonic() - candidate_started, 6)})
            if candidate_code != 0 or not candidate_out.strip():
                return None
            base = PurePosixPath(root_out.strip().splitlines()[-1])
            resolved = PurePosixPath(candidate_out.strip().splitlines()[-1])
            resolved.relative_to(base)
            return str(resolved)
        except (OSError, RuntimeError, ValueError):
            return None

    def read_state_snapshot_file(self, path: str, *, workspace_root: str | None = None,
                                 tail: bool = False) -> dict[str, Any]:
        """Read one candidate inside the container with a fixed no-follow openat probe."""
        if workspace_root and self._normalize_workspace_root(workspace_root) != self.workspace_root:
            raise ValueError("snapshot root does not match the executor workspace")
        script = (
            "import json,os,stat,sys\n"
            "root_arg,path_arg,tail_arg=sys.argv[1],sys.argv[2],sys.argv[3]=='tail'\n"
            "flags=os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW\n"
            "def open_dir_abs(path):\n"
            "  if not path.startswith('/') or any(x in ('.','..') for x in path.split('/')): raise ValueError('unsafe root')\n"
            "  fd=os.open('/',flags)\n"
            "  try:\n"
            "    for part in path.split('/'):\n"
            "      if part: fd2=os.open(part,flags,dir_fd=fd); os.close(fd); fd=fd2\n"
            "    return fd\n"
            "  except BaseException: os.close(fd); raise\n"
            "root=os.path.normpath(root_arg)\n"
            "if not root.startswith('/') or any(x in ('.','..') for x in root_arg.split('/')): raise ValueError('unsafe root')\n"
            "if not path_arg or '\\x00' in path_arg or any(x=='..' for x in path_arg.split('/')): raise ValueError('unsafe path')\n"
            "target=os.path.normpath(path_arg if path_arg.startswith('/') else root+'/'+path_arg)\n"
            "if os.path.commonpath((root,target))!=root or target==root: raise ValueError('outside workspace')\n"
            "rel=os.path.relpath(target,root); parts=rel.split('/')\n"
            "if any(x in ('','.','..') for x in parts): raise ValueError('unsafe component')\n"
            "rfd=open_dir_abs(root); opened=[rfd]; parent=rfd\n"
            "try:\n"
            "  for part in parts[:-1]: parent=os.open(part,flags,dir_fd=parent); opened.append(parent)\n"
            "  ffd=os.open(parts[-1],os.O_RDONLY|os.O_NOFOLLOW|getattr(os,'O_NONBLOCK',0),dir_fd=parent); opened.append(ffd)\n"
            "  st=os.fstat(ffd)\n"
            "  if not stat.S_ISREG(st.st_mode): raise ValueError('not regular file')\n"
            "  tail_meta={}\n"
            "  if tail_arg:\n"
            "    read_size=min(st.st_size,65536); os.lseek(ffd,max(0,st.st_size-read_size),os.SEEK_SET); sample=os.read(ffd,read_size)\n"
            "    line_parts=sample.splitlines(keepends=True); selected_lines=line_parts[-30:]; selected=b''.join(selected_lines)\n"
            "    line_window_truncated=len(line_parts)>len(selected_lines); read_cap_truncated=st.st_size>len(sample) and len(line_parts)<30; output_cap_truncated=len(selected)>2048\n"
            "    if output_cap_truncated: selected=selected[-2048:]\n"
            "    tail_meta={'tail_line_limit':30,'tail_lines_returned':len(selected_lines),'tail_truncated':bool(read_cap_truncated or output_cap_truncated or line_window_truncated),'tail_truncation_reasons':[reason for condition,reason in ((read_cap_truncated,'read_byte_cap'),(output_cap_truncated,'output_byte_cap'),(line_window_truncated,'older_lines_omitted')) if condition],'tail_bytes_read':len(sample),'tail_bytes_omitted_by_output_cap':max(0,len(b''.join(selected_lines))-len(selected))}\n"
            "    data=selected\n"
            "  else: data=os.read(ffd,2048)\n"
            "  binary=b'\\x00' in data or sum(b<9 or 13<b<32 for b in data)>max(2,len(data)//20)\n"
            "  excerpt=data[:512].hex() if binary else data.decode('utf-8','replace')\n"
            "  out={'exit_code':0,'stat':f'{target}|regular file|{st.st_size}|{int(st.st_mtime)}','file_type':'data (binary)' if binary else 'text','excerpt':excerpt,'excerpt_format':'hex' if binary else 'text','parent_listing':sorted(os.listdir(parent))[:50],**tail_meta}\n"
            "  print(json.dumps(out,separators=(',',':')))\n"
            "finally:\n"
            "  [os.close(fd) for fd in reversed(opened)]\n"
        )
        tail_arg = "tail" if tail else "head"
        command = ("python3 -c " + shlex.quote(script) + " " + shlex.quote(self.workspace_root) + " " +
                   shlex.quote(str(path)) + " " + tail_arg)
        result = self._exec(command, cwd=self.workspace_root, timeout_s=5)
        code, stdout, stderr = self._result_fields(result)
        if code != 0:
            raise RuntimeError(f"remote atomic snapshot read failed ({code}): {stderr[:300]}")
        try:
            payload = json.loads(stdout)
        except (TypeError, ValueError) as exc:
            raise RuntimeError("remote atomic snapshot read returned invalid JSON") from exc
        if not isinstance(payload, dict) or payload.get("exit_code") != 0:
            raise RuntimeError("remote atomic snapshot read did not return a valid file result")
        payload["command"] = f"harbor_snapshot_read_openat_v1:{tail_arg}"
        payload["command_sha256"] = hashlib.sha256(command.encode()).hexdigest()
        payload["command_args"] = [self.workspace_root, str(path), tail_arg]
        return payload

    def list_recent_state_snapshot_files(self, *, workspace_root: str | None = None,
                                         marker: str, limit: int = 50) -> dict[str, Any]:
        """Bounded no-follow remote tree walk rooted by openat descriptors."""
        if workspace_root and self._normalize_workspace_root(workspace_root) != self.workspace_root:
            raise ValueError("snapshot root does not match the executor workspace")
        safe_limit = max(0, min(50, int(limit)))
        script = (
            "import json,os,stat,sys\n"
            "root_arg,marker=sys.argv[1],sys.argv[2]; limit=max(0,min(50,int(sys.argv[3])))\n"
            "if not root_arg.startswith('/') or any(x in ('.','..') for x in root_arg.split('/')): raise ValueError('unsafe root')\n"
            "st=os.stat(marker,follow_symlinks=False)\n"
            "if not stat.S_ISREG(st.st_mode): raise ValueError('invalid marker')\n"
            "flags=os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW; root=os.path.normpath(root_arg)\n"
            "fd=os.open('/',flags); opened=[fd]\n"
            "try:\n"
            "  for part in root.split('/'):\n"
            "    if part: fd=os.open(part,flags,dir_fd=fd); opened.append(fd)\n"
            "  stack=[(fd,'',0)]; found=[]; seen=0\n"
            "  while stack and len(found)<limit and seen<5000:\n"
            "    d,prefix,depth=stack.pop()\n"
            "    if depth>16: continue\n"
            "    with os.scandir(d) as entries:\n"
            "      for e in entries:\n"
            "        seen+=1\n"
            "        if seen>5000: break\n"
            "        rel=(prefix+'/'+e.name) if prefix else e.name\n"
            "        try: info=e.stat(follow_symlinks=False)\n"
            "        except OSError: continue\n"
            "        if stat.S_ISREG(info.st_mode) and info.st_mtime>st.st_mtime: found.append(root+'/'+rel)\n"
            "        elif stat.S_ISDIR(info.st_mode):\n"
            "          try: child=os.open(e.name,flags,dir_fd=d)\n"
            "          except OSError: continue\n"
            "          opened.append(child); stack.append((child,rel,depth+1))\n"
            "  print(json.dumps({'paths':found[:limit]},separators=(',',':')))\n"
            "finally:\n"
            "  [os.close(x) for x in reversed(opened)]\n"
        )
        command = ("python3 -c " + shlex.quote(script) + " " + shlex.quote(self.workspace_root) + " " +
                   shlex.quote(str(marker)) + " " + shlex.quote(str(safe_limit)))
        result = self._exec(command, cwd=self.workspace_root, timeout_s=5)
        code, stdout, stderr = self._result_fields(result)
        if code != 0:
            raise RuntimeError(f"remote atomic recent-file walk failed ({code}): {stderr[:300]}")
        payload = json.loads(stdout)
        if not isinstance(payload, dict) or not isinstance(payload.get("paths"), list):
            raise RuntimeError("remote atomic recent-file walk returned invalid JSON")
        return {"paths": [str(row)[:500] for row in payload["paths"][:safe_limit]],
                "command": "harbor_snapshot_recent_openat_v1",
                "command_sha256": hashlib.sha256(command.encode()).hexdigest(),
                "command_args": [self.workspace_root, str(marker), str(safe_limit)]}

    def prepare_state_snapshot_marker(self) -> str:
        """Create a per-run marker in remote /tmp, outside the task workspace."""
        if self._state_snapshot_marker:
            return self._state_snapshot_marker
        path = f"/tmp/aether-state-runstart-{uuid.uuid4().hex}"
        code, _stdout, stderr = self._result_fields(self._exec(f"touch {shlex.quote(path)}", timeout_s=5))
        if code != 0:
            raise RuntimeError(f"could not create state snapshot run marker: {stderr[:200]}")
        self._state_snapshot_marker = path
        return path

    def cleanup_state_snapshot_marker(self) -> None:
        if self._state_snapshot_marker:
            self._exec(f"rm -f {shlex.quote(self._state_snapshot_marker)}", timeout_s=5)
            self._state_snapshot_marker = None

    def _upload_script(self, content: str, remote_path: str) -> None:
        local = self.local_state_dir / f"script-{uuid.uuid4().hex}.sh"
        try:
            local.write_text(content, encoding="utf-8")
            self._await(self.environment.upload_file(local, remote_path), timeout_s=60)
        finally:
            local.unlink(missing_ok=True)

    def launch_process(
        self,
        name: str,
        command: str,
        *,
        interactive: bool = False,
        cwd: str | None = None,
    ) -> ProcessHandle:
        if interactive:
            workspace_before = self._capture_remote_workspace_snapshot()
            terminal = self.start_terminal_session(name, command, cwd=cwd)
            self._process_workspace_state[terminal.session_id] = workspace_before
            return ProcessHandle(
                process_id=terminal.session_id,
                name=name,
                command=command,
                interactive=True,
                live=terminal.live,
                pid=terminal.pid,
                start_time_ticks=terminal.start_time_ticks,
                command_sha256=terminal.command_sha256,
                process_generation=terminal.process_generation,
                status="running" if terminal.live else "failed",
                detail="Harbor line-oriented terminal session",
            )

        workspace_before = self._capture_remote_workspace_snapshot()
        generation = uuid.uuid4().hex
        process_id = f"harbor-job:{generation}"
        remote_dir = f"{HARBOR_CONTROL_ROOT}/harbor_jobs/{generation}"
        stdout_path = f"{remote_dir}/stdout.log"
        stderr_path = f"{remote_dir}/stderr.log"
        exit_path = f"{remote_dir}/exit_code"
        pid_path = f"{remote_dir}/pid"
        wrapper_path = f"{remote_dir}/run.sh"
        remote_cwd = self._cwd(cwd)
        self._exec(f"mkdir -p {shlex.quote(remote_dir)}", timeout_s=30)
        wrapper = "\n".join([
            "#!/usr/bin/env sh",
            "set +e",
            f"cd {shlex.quote(remote_cwd)} || exit 125",
            # A task command may legitimately use `exit`. Keep it inside a
            # child shell so the wrapper always records its status and leaves
            # bounded diagnostics available to a later probe.
            f"bash -c {shlex.quote(str(command))}",
            "code=$?",
            f"printf '%s\\n' \"$code\" > {shlex.quote(exit_path)}",
            "exit \"$code\"",
            "",
        ])
        self._upload_script(wrapper, wrapper_path)
        launch_command = (
            f"chmod +x {shlex.quote(wrapper_path)} && "
            f"if command -v setsid >/dev/null 2>&1; then "
            f"nohup setsid sh {shlex.quote(wrapper_path)} >{shlex.quote(stdout_path)} "
            f"2>{shlex.quote(stderr_path)} </dev/null & "
            f"else nohup sh {shlex.quote(wrapper_path)} >{shlex.quote(stdout_path)} "
            f"2>{shlex.quote(stderr_path)} </dev/null & fi; "
            f"pid=$!; printf '%s\\n' \"$pid\" > {shlex.quote(pid_path)}; printf '%s\\n' \"$pid\""
        )
        result = self._exec(launch_command, cwd=remote_cwd, timeout_s=30)
        code, stdout, stderr = self._result_fields(result)
        if code != 0:
            raise RuntimeError(f"Harbor background launch failed: {stderr}")
        try:
            pid = int(stdout.strip().splitlines()[-1])
        except (IndexError, ValueError) as exc:
            raise RuntimeError(f"Harbor background launch returned invalid pid: {stdout!r}") from exc
        command_sha = hashlib.sha256(command.encode("utf-8")).hexdigest()
        record = _RemoteProcess(
            process_id=process_id,
            name=name,
            command=command,
            remote_dir=remote_dir,
            pid=pid,
            generation=generation,
            interactive=False,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            exit_path=exit_path,
        )
        self._processes[process_id] = record
        self._process_workspace_state[process_id] = workspace_before
        return ProcessHandle(
            process_id=process_id,
            name=name,
            command=command,
            interactive=False,
            live=True,
            detail="started through Harbor BaseEnvironment",
            pid=pid,
            start_time_ticks=generation,
            command_sha256=command_sha,
            process_generation=generation,
            stdout_log=stdout_path,
            stderr_log=stderr_path,
            status_log=exit_path,
            status="running",
        )

    def _process_for(self, target: str) -> _RemoteProcess | None:
        if target in self._processes:
            return self._processes[target]
        matches = [row for row in self._processes.values() if row.name == target]
        return matches[-1] if matches else None

    def observe_process_state(self, target: str) -> dict[str, Any]:
        record = self._process_for(target)
        if record is None:
            return {}
        current = self._capture_remote_workspace_snapshot()
        previous = self._process_workspace_state.get(record.process_id, current)
        delta = diff_remote_workspace_snapshots(previous, current)
        self._process_workspace_state[record.process_id] = current
        delta["mutation_detection_scope"] = "managed_process_async_workspace_effects"
        return delta

    def _remote_status(self, record: _RemoteProcess) -> tuple[bool, int | None, str]:
        result = self._remote_exec_for_process(
            record,
            " ".join([
                f"pid={record.pid};",
                f"code=$(cat {shlex.quote(record.exit_path)} 2>/dev/null || true);",
                "proc_state=$(awk '{print $3}' /proc/\"$pid\"/stat 2>/dev/null || true);",
                "wait_status=$(awk '{print $52}' /proc/\"$pid\"/stat 2>/dev/null || true);",
                (
                    "if [ -z \"$code\" ] && [ \"$proc_state\" = Z ] "
                    "&& [ -n \"$wait_status\" ]; then "
                    "sig=$((wait_status & 127)); "
                    "if [ \"$sig\" -ne 0 ]; then code=$((128 + sig)); "
                    "else code=$(((wait_status >> 8) & 255)); fi; fi;"
                ),
                (
                    "alive=false; if kill -0 \"$pid\" 2>/dev/null "
                    "&& [ -z \"$code\" ] && [ \"$proc_state\" != Z ]; "
                    "then alive=true; fi;"
                ),
                "printf '__ALIVE__%s\\n' \"$alive\";",
                "printf '__EXIT__%s\\n' \"$code\";",
                "printf '__AETHER_CHILD_STDOUT_BEGIN__\\n';",
                f"tail -c 2048 {shlex.quote(record.stdout_path)} 2>/dev/null || true;",
                "printf '\\n__AETHER_CHILD_STDERR_BEGIN__\\n';",
                f"tail -c 2048 {shlex.quote(record.stderr_path)} 2>/dev/null || true",
            ]),
            timeout_s=15,
        )
        code, stdout, stderr = self._result_fields(result)
        if code != 0:
            return False, None, stderr or stdout
        lines = stdout.splitlines()
        alive = any(line == "__ALIVE__true" for line in lines)
        exit_code: int | None = None
        for line in lines:
            if line.startswith("__EXIT__"):
                raw = line.removeprefix("__EXIT__").strip()
                if raw:
                    try:
                        exit_code = int(raw)
                    except ValueError:
                        pass
                break
        stdout_marker = "__AETHER_CHILD_STDOUT_BEGIN__"
        stderr_marker = "__AETHER_CHILD_STDERR_BEGIN__"
        try:
            stdout_start = lines.index(stdout_marker) + 1
        except ValueError:
            # Preserve unstructured transport output rather than dropping it.
            detail = "\n".join(
                line for line in lines
                if not line.startswith("__ALIVE__") and not line.startswith("__EXIT__")
            )[-2048:]
            return alive, exit_code, detail
        try:
            stderr_start = lines.index(stderr_marker, stdout_start)
        except ValueError:
            stderr_start = len(lines)
        stdout_tail = "\n".join(lines[stdout_start:stderr_start])[-2048:]
        stderr_tail = "\n".join(lines[stderr_start + 1:])[-2048:]
        detail_parts = []
        if stdout_tail:
            detail_parts.append("child_stdout:\n" + stdout_tail)
        if stderr_tail:
            detail_parts.append("child_stderr:\n" + stderr_tail)
        detail = "\n".join(detail_parts)[-4096:]
        return alive, exit_code, detail

    def probe_process(self, target: str) -> ProbeResult:
        record = self._process_for(target)
        if record is None:
            return ProbeResult(target=target, live=False, detail="unregistered Harbor process", service_name=target)
        live, _exit, detail = self._remote_status(record)
        return ProbeResult(
            target=target,
            live=live,
            detail=detail or ("live" if live else "not live"),
            service_name=record.name,
            process_id=record.process_id,
            process_generation=record.generation,
            process_generation_verified=True,
            endpoint_owner_pids=(record.pid,) if live else (),
        )

    def probe_job(self, target: str) -> JobProbeResult:
        record = self._process_for(target)
        if record is None:
            return JobProbeResult(target=target, found=False, status="unknown", completed=False, detail="unregistered Harbor job")
        live, exit_code, detail = self._remote_status(record)
        cancelled = False
        if not live:
            cancel_path = f"{record.remote_dir}/cancelled"
            try:
                cancel_probe = self._remote_exec_for_process(
                    record, f"test -f {shlex.quote(cancel_path)}", timeout_s=10
                )
                cancel_code, _cancel_stdout, _cancel_stderr = self._result_fields(cancel_probe)
                cancelled = cancel_code == 0
            except Exception:
                cancelled = False
        completed = bool(not live and (exit_code is not None or cancelled))
        status = (
            "running" if live else
            "cancelled" if cancelled else
            "completed" if exit_code == 0 else
            "failed" if exit_code is not None else
            "unknown"
        )
        return JobProbeResult(
            target=target,
            found=True,
            status=status,
            completed=completed,
            succeeded=False if cancelled else ((exit_code == 0) if completed else None),
            exit_code=exit_code,
            detail=detail or status,
            job_id=record.process_id,
            process_id=record.process_id,
            process_generation=record.generation,
            process_generation_verified=True,
            lifecycle_authority="harbor_environment_registered_process",
            pid=record.pid,
        )

    def job_output(self, target: str, *, tail_lines: int = 40) -> dict[str, str]:
        record = self._process_for(target)
        if record is None:
            return {"stdout": "", "stderr": ""}
        count = max(1, min(200, int(tail_lines)))
        outputs: dict[str, str] = {}
        for label, path in (("stdout", record.stdout_path), ("stderr", record.stderr_path)):
            result = self._remote_exec_for_process(
                record, f"tail -n {count} {shlex.quote(path)} 2>/dev/null || true", timeout_s=10,
            )
            _code, stdout, _stderr = self._result_fields(result)
            outputs[label] = stdout
        return outputs

    _JOB_FULL_OUTPUT_MAX_BYTES = 16_000_000

    def job_output_full(self, target: str) -> dict[str, Any]:
        """Complete captured output of a finished job (bounded, not a line tail)."""
        record = self._process_for(target)
        outputs: dict[str, Any] = {"stdout": "", "stderr": "", "stdout_overflow_path": "",
            "stderr_overflow_path": ""}
        if record is None:
            return {**outputs, "stdout_bytes_total": 0, "stderr_bytes_total": 0}
        for label, path in (("stdout", record.stdout_path), ("stderr", record.stderr_path)):
            result = self._remote_exec_for_process(
                record,
                f"head -c {self._JOB_FULL_OUTPUT_MAX_BYTES} {shlex.quote(path)} 2>/dev/null || true",
                timeout_s=30,
            )
            _code, stdout, _stderr = self._result_fields(result)
            outputs[label] = stdout
            outputs[f"{label}_bytes_total"] = len(stdout)
        return outputs

    def stop_process(self, target: str) -> bool:
        record = self._process_for(target)
        if record is None:
            return False
        live_before, _exit_before, _detail_before = self._remote_status(record)
        if not live_before:
            # An already-terminal process was not cancelled by this request.
            # Let an explicit probe report its observed terminal state instead
            # of fabricating a cancellation edge.
            return False

        terminate = (
            f"kill -TERM -- -{record.pid} 2>/dev/null || "
            f"kill -TERM {record.pid} 2>/dev/null"
        )
        terminate_result = self._remote_exec_for_process(record, terminate, timeout_s=15)
        terminate_code, _terminate_stdout, _terminate_stderr = self._result_fields(terminate_result)
        if terminate_code != 0:
            # The process may have exited naturally after the liveness check.
            # Do not relabel that race as an accepted cancellation.
            return False
        deadline = time.monotonic() + 3.0
        live = True
        while live and time.monotonic() < deadline:
            live, _exit_code, _detail = self._remote_status(record)
            if live:
                time.sleep(0.05)
        if live:
            force = (
                f"kill -KILL -- -{record.pid} 2>/dev/null || "
                f"kill -KILL {record.pid} 2>/dev/null"
            )
            force_result = self._remote_exec_for_process(record, force, timeout_s=15)
            force_code, _force_stdout, _force_stderr = self._result_fields(force_result)
            if force_code != 0:
                return False
            deadline = time.monotonic() + 2.0
            while live and time.monotonic() < deadline:
                live, _exit_code, _detail = self._remote_status(record)
                if live:
                    time.sleep(0.05)
        if live:
            return False

        # Persist a cancellation fact only after the registered generation is
        # observed non-live.  This marker distinguishes a model-requested stop
        # from natural success/failure when the wrapper dies before writing its
        # ordinary exit-code file.
        cancel_path = f"{record.remote_dir}/cancelled"
        marker = self._remote_exec_for_process(
            record, f": > {shlex.quote(cancel_path)}", timeout_s=10
        )
        marker_code, _marker_stdout, _marker_stderr = self._result_fields(marker)
        return marker_code == 0

    def start_terminal_session(
        self,
        name: str,
        command: str,
        *,
        cwd: str | None = None,
    ) -> TerminalSessionHandle:
        self._terminal_workspace_state = self._capture_remote_workspace_snapshot()
        generation = uuid.uuid4().hex
        session_id = f"harbor-terminal:{generation}"
        remote_dir = f"{HARBOR_CONTROL_ROOT}/harbor_terminals/{generation}"
        input_path = f"{remote_dir}/input.fifo"
        stdout_path = f"{remote_dir}/screen.log"
        stderr_path = f"{remote_dir}/stderr.log"
        exit_path = f"{remote_dir}/exit_code"
        pid_path = f"{remote_dir}/pid"
        wrapper_path = f"{remote_dir}/run.sh"
        remote_cwd = self._cwd(cwd)
        self._exec(
            f"mkdir -p {shlex.quote(remote_dir)} && rm -f {shlex.quote(input_path)} && "
            f"mkfifo {shlex.quote(input_path)} && : > {shlex.quote(stdout_path)}",
            timeout_s=30,
        )
        wrapper = "\n".join([
            "#!/usr/bin/env sh",
            "set +e",
            f"cd {shlex.quote(remote_cwd)} || exit 125",
            f"exec 3<> {shlex.quote(input_path)}",
            f"sh -lc {shlex.quote(command)} <&3 > {shlex.quote(stdout_path)} 2>{shlex.quote(stderr_path)}",
            "code=$?",
            "exec 3>&-",
            f"printf '%s\\n' \"$code\" > {shlex.quote(exit_path)}",
            "exit \"$code\"",
            "",
        ])
        self._upload_script(wrapper, wrapper_path)
        result = self._exec(
            f"chmod +x {shlex.quote(wrapper_path)} && "
            f"if command -v setsid >/dev/null 2>&1; then nohup setsid sh {shlex.quote(wrapper_path)} >/dev/null 2>&1 </dev/null & "
            f"else nohup sh {shlex.quote(wrapper_path)} >/dev/null 2>&1 </dev/null & fi; "
            f"pid=$!; printf '%s\\n' \"$pid\" > {shlex.quote(pid_path)}; printf '%s\\n' \"$pid\"",
            timeout_s=30,
        )
        code, stdout, stderr = self._result_fields(result)
        if code != 0:
            raise RuntimeError(f"Harbor terminal launch failed: {stderr}")
        pid = int(stdout.strip().splitlines()[-1])
        record = _RemoteProcess(
            process_id=session_id,
            name=name,
            command=command,
            remote_dir=remote_dir,
            pid=pid,
            generation=generation,
            interactive=True,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            exit_path=exit_path,
            input_path=input_path,
        )
        self._processes[session_id] = record
        self._terminal_cursors[session_id] = 0
        command_sha = hashlib.sha256(command.encode("utf-8")).hexdigest()
        return TerminalSessionHandle(
            session_id=session_id,
            name=name,
            command=command,
            live=True,
            pid=pid,
            start_time_ticks=generation,
            command_sha256=command_sha,
            process_generation=generation,
            transcript_path=stdout_path,
            state_delta=self._terminal_state_delta(),
        )

    def terminal_send(
        self,
        session_id: str,
        data: str,
        *,
        append_newline: bool = True,
    ) -> TerminalSessionState:
        record = self._process_for(session_id)
        if record is None or not record.interactive:
            raise KeyError(f"unknown Harbor terminal session: {session_id}")
        payload = str(data) + ("\n" if append_newline else "")
        local = self.local_state_dir / f"terminal-input-{uuid.uuid4().hex}"
        remote_temp = f"{record.remote_dir}/input-{uuid.uuid4().hex}.txt"
        try:
            local.write_text(payload, encoding="utf-8")
            self._await(self.environment.upload_file(local, remote_temp), timeout_s=60)
            self._exec(
                f"cat {shlex.quote(remote_temp)} > {shlex.quote(record.input_path)}; rm -f {shlex.quote(remote_temp)}",
                timeout_s=30,
            )
        finally:
            local.unlink(missing_ok=True)
        live, exit_code, _detail = self._remote_status(record)
        return TerminalSessionState(
            session_id=session_id,
            live=live,
            exit_code=exit_code,
            bytes_sent=len(payload.encode("utf-8")),
            process_generation=record.generation,
            process_group_id=record.pid,
            session_leader_id=record.pid,
            state_delta=self._terminal_state_delta(),
        )

    def terminal_read(
        self,
        session_id: str,
        *,
        max_bytes: int = 20_000,
        wait_ms: int = 1000,
    ) -> TerminalReadResult:
        record = self._process_for(session_id)
        if record is None or not record.interactive:
            raise KeyError(f"unknown Harbor terminal session: {session_id}")
        if wait_ms > 0:
            self._exec(f"sleep {max(0.0, min(float(wait_ms) / 1000.0, 5.0)):.3f}", timeout_s=10)
        result = self._exec(f"cat {shlex.quote(record.stdout_path)} 2>/dev/null || true", timeout_s=15)
        _code, stdout, _stderr = self._result_fields(result)
        raw = stdout.encode("utf-8", errors="replace")
        cursor = self._terminal_cursors.get(session_id, 0)
        chunk = raw[cursor: cursor + max(1, int(max_bytes))]
        new_cursor = cursor + len(chunk)
        self._terminal_cursors[session_id] = new_cursor
        live, exit_code, _detail = self._remote_status(record)
        return TerminalReadResult(
            session_id=session_id,
            output=chunk.decode("utf-8", errors="replace"),
            bytes_read=len(chunk),
            cursor=new_cursor,
            total_bytes=len(raw),
            more_available=new_cursor < len(raw),
            live=live,
            exit_code=exit_code,
            process_generation=record.generation,
            process_group_id=record.pid,
            session_leader_id=record.pid,
            state_delta=self._terminal_state_delta(),
        )

    def terminal_wait(
        self,
        session_id: str,
        *,
        timeout_s: float = 30.0,
    ) -> TerminalSessionState:
        record = self._process_for(session_id)
        if record is None or not record.interactive:
            raise KeyError(f"unknown Harbor terminal session: {session_id}")
        deadline = time.monotonic() + max(0.0, float(timeout_s))
        live = True
        exit_code: int | None = None
        while live and time.monotonic() < deadline:
            live, exit_code, _detail = self._remote_status(record)
            if live:
                time.sleep(min(0.25, max(0.0, deadline - time.monotonic())))
        return TerminalSessionState(
            session_id=session_id,
            live=live,
            exit_code=exit_code,
            cursor=self._terminal_cursors.get(session_id, 0),
            process_generation=record.generation,
            process_group_id=record.pid,
            session_leader_id=record.pid,
            state_delta=self._terminal_state_delta(),
        )

    def terminal_interrupt(self, session_id: str) -> TerminalSessionState:
        record = self._process_for(session_id)
        if record is None or not record.interactive:
            raise KeyError(f"unknown Harbor terminal session: {session_id}")
        self._exec(
            f"kill -INT -- -{record.pid} 2>/dev/null || kill -INT {record.pid} 2>/dev/null || true",
            timeout_s=15,
        )
        live, exit_code, _detail = self._remote_status(record)
        return TerminalSessionState(
            session_id=session_id,
            live=live,
            exit_code=exit_code,
            signal="SIGINT",
            process_generation=record.generation,
            process_group_id=record.pid,
            session_leader_id=record.pid,
            state_delta=self._terminal_state_delta(),
        )

    def terminal_close(self, session_id: str) -> TerminalSessionState:
        record = self._process_for(session_id)
        if record is None or not record.interactive:
            raise KeyError(f"unknown Harbor terminal session: {session_id}")
        self.stop_process(session_id)
        live, exit_code, _detail = self._remote_status(record)
        self._archive_remote_process_logs(record)
        self._exec(f"rm -rf {shlex.quote(record.remote_dir)}", timeout_s=30)
        return TerminalSessionState(
            session_id=session_id,
            live=live,
            exit_code=exit_code,
            signal="SIGTERM",
            process_generation=record.generation,
            process_group_id=record.pid,
            session_leader_id=record.pid,
            state_delta=self._terminal_state_delta(),
        )

    def _rfb_backend_info(self) -> dict[str, Any]:
        """Discover one live localhost RFB endpoint without mutating task state."""
        probe = r"""if ! command -v python3 >/dev/null 2>&1; then exit 31; fi
python3 - <<'PY'
import re,socket,subprocess
ports=[]
try:
    out=subprocess.run(['ss','-ltnH'],capture_output=True,text=True,timeout=2,check=False).stdout
    for token in re.findall(r'(?:^|\s)(?:\[[^]]+\]|[^\s:]+):(\d+)(?:\s|$)',out,re.M):
        p=int(token)
        if 1 <= p <= 65535 and p not in ports: ports.append(p)
except Exception:
    pass
# Socket inventory is authoritative when available. Probe in stable order so
# multiple RFB services never depend on process/listing order. If the task
# image lacks a socket-listing utility, fall back to the conventional VNC
# range rather than scanning every TCP port.
ports=sorted(ports) if ports else list(range(5900,6000))
def recv_exact(sock,n):
    out=b''
    while len(out)<n:
        chunk=sock.recv(n-len(out))
        if not chunk: raise ConnectionError('closed')
        out+=chunk
    return out
for port in ports:
    sock=None
    try:
        sock=socket.create_connection(('127.0.0.1',port),timeout=0.08)
        sock.settimeout(0.25); banner=recv_exact(sock,12)
        if not banner.startswith(b'RFB '): continue
        server_minor=int(banner[8:11]); minor=8 if server_minor>=8 else (7 if server_minor>=7 else 3)
        sock.sendall(f'RFB 003.{minor:03d}\n'.encode('ascii'))
        if minor>=7:
            count=recv_exact(sock,1)[0]
            if not count: continue
            security=recv_exact(sock,count)
            if 1 not in security: continue
            sock.sendall(b'\x01')
            if int.from_bytes(recv_exact(sock,4),'big')!=0: continue
        else:
            if int.from_bytes(recv_exact(sock,4),'big')!=1: continue
        print(f'rfb:127.0.0.1:{port}'); raise SystemExit(0)
    except Exception:
        pass
    finally:
        if sock is not None:
            try: sock.close()
            except Exception: pass
raise SystemExit(32)
PY"""
        try:
            result=self._exec(probe,timeout_s=8); code,stdout,stderr=self._result_fields(result)
        except Exception as exc:
            return {"available":False,"backend":"","detail":f"rfb_probe_error:{type(exc).__name__}:{exc}"[:1000]}
        backend=stdout.strip().splitlines()[-1] if code==0 and stdout.strip() else ""
        return {"available":bool(code==0 and backend.startswith("rfb:")),"backend":backend,"detail":stderr[-1000:]}

    def computer_backend_info(self) -> dict[str, Any]:
        # Prefer a directly attached X desktop when one is genuinely usable.
        # RFB is an independent fallback for VM/remote-framebuffer tasks and is
        # probed even when DISPLAY is absent.
        x_probe = r"""if [ -z "${DISPLAY:-}" ]; then exit 20; fi
if command -v python3 >/dev/null 2>&1 && python3 - <<'PY' >/dev/null 2>&1
import pyautogui
im=pyautogui.screenshot(); assert getattr(im,'size',None)
PY
then printf '%s\n' pyautogui; exit 0; fi
if command -v xdotool >/dev/null 2>&1 && xdotool getmouselocation >/dev/null 2>&1; then
 tmp=/tmp/aether-computer-probe-$$.png
 if command -v import >/dev/null 2>&1 && import -window root "$tmp" >/dev/null 2>&1 && test -s "$tmp"; then rm -f "$tmp"; printf '%s\n' xdotool_import; exit 0; fi
 if command -v scrot >/dev/null 2>&1 && scrot "$tmp" >/dev/null 2>&1 && test -s "$tmp"; then rm -f "$tmp"; printf '%s\n' xdotool_scrot; exit 0; fi
 if command -v gnome-screenshot >/dev/null 2>&1 && gnome-screenshot -f "$tmp" >/dev/null 2>&1 && test -s "$tmp"; then rm -f "$tmp"; printf '%s\n' xdotool_gnome_screenshot; exit 0; fi
fi
exit 21"""
        try:
            result=self._exec(x_probe,timeout_s=15); code,stdout,stderr=self._result_fields(result)
        except Exception as exc:
            code,stdout,stderr=99,"",f"x_probe_error:{type(exc).__name__}:{exc}"
        backend=stdout.strip().splitlines()[-1] if code==0 and stdout.strip() else ""
        if code==0 and backend:
            return {"available":True,"backend":backend,"detail":stderr[-1000:]}
        rfb=self._rfb_backend_info()
        if rfb.get("available"):
            return rfb
        return {"available":False,"backend":"","detail":f"x:{stderr[-400:]}; rfb:{str(rfb.get('detail') or '')[-400:]}"}

    def _ensure_rfb_client(self) -> tuple[str, str]:
        result = self._exec("command -v python3 2>/dev/null || true", timeout_s=10)
        _code, stdout, _stderr = self._result_fields(result)
        interpreter = stdout.strip().splitlines()[0] if stdout.strip() else ""
        if not interpreter:
            raise RuntimeError("task environment has no Python 3 interpreter for generic RFB bridge")
        remote=self._rfb_client_remote_path
        if not self._rfb_client_uploaded:
            local=Path(__file__).with_name("rfb_computer_client.py")
            self._await(self.environment.upload_file(local,remote),timeout_s=60)
            self._rfb_client_uploaded=True
        return interpreter,remote

    def computer_available(self) -> bool:
        return bool(self.computer_backend_info().get("available"))

    def computer_action(self, action: Mapping[str, Any]) -> ComputerActionResult:
        info=self.computer_backend_info(); requested=dict(action or {})
        actions=[dict(row) for row in (requested.get("actions") or ())]
        if not actions:
            return ComputerActionResult(requested,False,b"",detail="computer call requires at least one action")
        if not info.get("available"):
            return ComputerActionResult(requested,False,b"",detail="computer backend unavailable")
        backend=str(info.get("backend") or ""); remote=f"/tmp/aether-computer-{uuid.uuid4().hex}.png"; local=self.local_state_dir/f"computer-{uuid.uuid4().hex}.png"
        try:
            if backend=="pyautogui":
                command=_pyautogui_action_script(requested,remote)
                result=self._exec(command,timeout_s=60)
            elif backend.startswith("xdotool_"):
                action_command=" && ".join(_xdotool_action_command(row) for row in actions)
                result=self._exec(action_command,timeout_s=60)
                capture={"xdotool_import":f"import -window root {shlex.quote(remote)}","xdotool_scrot":f"scrot {shlex.quote(remote)}","xdotool_gnome_screenshot":f"gnome-screenshot -f {shlex.quote(remote)}"}[backend]
                capture_result=self._exec(capture,timeout_s=30)
                ccode,cstdout,cstderr=self._result_fields(capture_result)
                if ccode!=0:
                    code,stdout,stderr=self._result_fields(result)
                    return ComputerActionResult(requested,False,b"",detail=f"{backend} screenshot exit={ccode}: {(cstderr or cstdout)[-1000:]}; action_exit={code}: {(stderr or stdout)[-500:]}")
            elif backend.startswith("rfb:"):
                _tag,host,port_text=backend.split(":",2)
                interpreter,bridge=self._ensure_rfb_client()
                command=(
                    f"{shlex.quote(interpreter)} {shlex.quote(bridge)} "
                    f"--host {shlex.quote(host)} --port {int(port_text)} "
                    f"--actions-json {shlex.quote(json.dumps(actions,separators=(',',':'),ensure_ascii=False))} "
                    f"--screenshot {shlex.quote(remote)} --timeout-s 20"
                )
                result=self._exec(command,timeout_s=90)
            else: raise RuntimeError(f"unknown computer backend: {backend}")
            code,stdout,stderr=self._result_fields(result)
            try:
                self._await(self.environment.download_file(remote,local),timeout_s=60); raw=local.read_bytes()
            except Exception as capture_exc:
                return ComputerActionResult(requested,False,b"",detail=f"{backend} screenshot unavailable after action_exit={code}: {type(capture_exc).__name__}: {capture_exc}"[:1000])
            if not raw: return ComputerActionResult(requested,False,b"",detail="computer screenshot was empty")
            width=height=None
            if raw.startswith(b"\x89PNG\r\n\x1a\n") and len(raw)>=24:
                width=int.from_bytes(raw[16:20],"big"); height=int.from_bytes(raw[20:24],"big")
            success=code==0
            detail=(f"{backend} executed {len(actions)} action(s) + fresh screenshot" if success else f"{backend} action sequence exit={code}; fresh screenshot preserved: {(stderr or stdout)[-700:]}")
            return ComputerActionResult(requested,success,raw,media_type="image/png",width=width,height=height,detail=detail,state_delta={"computer_backend":backend,"computer_action_count":len(actions),"computer_action_types":[str(row.get("type") or "") for row in actions],"gui_state_may_have_changed":any(str(row.get("type") or "") not in {"screenshot","wait"} for row in actions)})
        except Exception as exc:
            return ComputerActionResult(requested,False,b"",detail=f"{backend} computer action failed: {type(exc).__name__}: {exc}"[:1000])
        finally:
            local.unlink(missing_ok=True)
            try: self._exec(f"rm -f {shlex.quote(remote)}",timeout_s=10)
            except Exception: pass

    def inspect_task_artifact(self, path: str, mode: str) -> ArtifactInspection:
        """Stage one readable absolute task-world artifact into the Solver workspace.

        The source may be created dynamically by the Solver and therefore need
        not occur literally in the original task text. The exact path is
        realpath-resolved inside the task container and must pass the hard
        artifact privacy boundary before any bytes are downloaded.
        """
        requested = str(path or "").strip()
        try:
            resolved = self.resolve_task_artifact_read_path(requested)
        except FileNotFoundError as exc:
            return ArtifactInspection(
                path=requested,
                mode=mode,
                success=False,
                detail=f"task-world artifact does not exist: {requested}",
                outcome="unavailable",
                reason_code="task_world_artifact_missing",
                execution="not_started",
                recovery_operations=("create_or_refresh_the_declared_artifact_then_reinspect",),
                replay_safe=True,
            )
        except Exception as exc:  # noqa: BLE001 - preserve exact policy refusal
            return ArtifactInspection(
                path=requested,
                mode=mode,
                success=False,
                detail=f"task-world artifact path rejected: {type(exc).__name__}: {exc}",
                outcome="rejected_before_execution",
                reason_code="task_world_artifact_path_not_authorized",
                execution="not_started",
                recovery_operations=("use_a_workspace_path_or_a_readable_non_private_task_world_path",),
                replay_safe=True,
            )

        local = self.local_state_dir / f"task-artifact-{uuid.uuid4().hex}"
        try:
            self._await(self.environment.download_file(resolved, local), timeout_s=60)
            data = local.read_bytes()
            source_identity = identify_bytes(
                data,
                path=resolved,
                source="harbor:task_world_absolute_path",
            )
            basename = PurePosixPath(resolved).name or "artifact.bin"
            safe_basename = "".join(
                character if character.isalnum() or character in {".", "_", "-"} else "_"
                for character in basename
            )[:120] or "artifact.bin"
            staged_relative = (
                f".aether/task_artifacts/{source_identity.sha256[:16]}-{safe_basename}"
            )
            staged_remote = self._remote_path(staged_relative)
            parent = str(PurePosixPath(staged_remote).parent)
            mkdir_result = self._exec(
                f"mkdir -p {shlex.quote(parent)}",
                cwd=self.workspace_root,
                timeout_s=15,
            )
            mkdir_code, mkdir_stdout, mkdir_stderr = self._result_fields(mkdir_result)
            if mkdir_code != 0:
                raise RuntimeError(
                    "artifact staging directory creation failed: "
                    + (mkdir_stderr or mkdir_stdout)[-500:]
                )
            self._await(self.environment.upload_file(local, staged_remote), timeout_s=60)
            staged = self.inspect_artifact(staged_relative, mode)
            metadata = dict(staged.metadata or {})
            staged_identity = dict(metadata.get("artifact_identity", {}) or {})
            staged_sha = str(staged_identity.get("sha256") or metadata.get("sha256") or "")
            hash_match = bool(staged_sha) and staged_sha == source_identity.sha256
            metadata.update({
                "source_task_path": resolved,
                "source_artifact_identity": source_identity.as_dict(),
                "staged_path": staged_relative,
                "staging_hash_match": hash_match,
                "staging_policy": "dynamic_task_world_absolute_path_via_privacy_resolver",
            })
            if not hash_match:
                return ArtifactInspection(
                    path=staged_relative,
                    mode=mode,
                    success=False,
                    extracted_text=staged.extracted_text,
                    metadata=metadata,
                    detail="task artifact staging hash mismatch; staged bytes are not trusted",
                    outcome="failed",
                    reason_code="task_artifact_staging_hash_mismatch",
                    execution="exited",
                    recovery_operations=("reconcile_source_and_staged_artifact_identity",),
                    replay_safe=False,
                )
            return ArtifactInspection(
                path=staged_relative,
                mode=mode,
                success=staged.success,
                extracted_text=staged.extracted_text,
                metadata=metadata,
                detail=(
                    f"staged task-world artifact {resolved} as {staged_relative}; "
                    + str(staged.detail or "inspection complete")
                )[:1000],
                outcome=staged.outcome,
                reason_code=staged.reason_code,
                execution=staged.execution,
                recovery_operations=staged.recovery_operations,
                replay_safe=staged.replay_safe,
            )
        except Exception as exc:  # noqa: BLE001 - transport/staging outcome is explicit
            return ArtifactInspection(
                path=requested,
                mode=mode,
                success=False,
                detail=f"task artifact staging failed: {type(exc).__name__}: {exc}",
                outcome="failed",
                reason_code="task_artifact_staging_failed",
                execution="unknown",
                recovery_operations=("inspect_the_staging_failure_before_retry",),
                replay_safe=False,
            )
        finally:
            local.unlink(missing_ok=True)

    def inspect_artifact(self, path: str, mode: str) -> ArtifactInspection:
        remote = self._remote_path(path)
        try:
            data = self.read_file_bytes(remote)
        except Exception as exc:  # noqa: BLE001 - truthful inspection failure
            return ArtifactInspection(
                path=remote,
                mode=mode,
                success=False,
                detail=f"artifact unavailable: {type(exc).__name__}: {exc}",
            )
        identity = identify_bytes(
            data,
            path=remote,
            source="harbor:BaseEnvironment.download_file",
        )
        metadata = {
            "bytes": identity.bytes,
            "size_bytes": identity.bytes,
            "sha256": identity.sha256,
            "media_type": identity.media_type,
            "artifact_handle": identity.handle,
            "artifact_identity": identity.as_dict(),
            "content_addressed": True,
            "source": "harbor:BaseEnvironment.download_file",
        }
        requested_mode = str(mode or "").strip().lower()
        text_modes = {"text", "read", "json", "csv", "html", "source"}
        semantic_binary_modes = {
            "auto", "preview", "image", "image_semantic", "ocr", "pdf", "frames"
        }
        extracted = ""
        if requested_mode in text_modes or not requested_mode:
            extracted = data.decode("utf-8", errors="replace")
            metadata["semantic_content_available"] = True
            metadata["semantic_content_status"] = "deterministic_text_decode"
            success = True
            detail = f"inspected exact Harbor artifact {remote}"
        else:
            metadata["semantic_content_available"] = False
            metadata["semantic_content_status"] = (
                "exact_bytes_available_semantic_view_not_yet_derived"
            )
            success = requested_mode not in semantic_binary_modes
            detail = (
                f"exact Harbor artifact metadata for {remote}; semantic content unavailable"
                if not success
                else f"exact Harbor binary metadata for {remote}"
            )
        return ArtifactInspection(
            path=remote,
            mode=mode,
            success=success,
            extracted_text=extracted,
            metadata=metadata,
            detail=detail,
        )

    def _ensure_mcp_client(self) -> tuple[str, str]:
        """Upload the stdlib MCP bridge into the task world exactly once."""
        result = self._exec("command -v python3 2>/dev/null || command -v python 2>/dev/null || true", timeout_s=10)
        _code, stdout, _stderr = self._result_fields(result)
        interpreter = stdout.strip().splitlines()[0] if stdout.strip() else ""
        if not interpreter:
            raise RuntimeError("task environment has no Python interpreter for generic MCP bridge")
        remote = self._mcp_client_remote_path
        if not self._mcp_client_uploaded:
            # Harness transport code is execution infrastructure, not a task
            # artifact. Keep it out of the grader-visible workspace and remove
            # it when the executor closes.
            local = Path(__file__).with_name("mcp_environment_client.py")
            self._await(self.environment.upload_file(local, remote), timeout_s=60)
            self._mcp_client_uploaded = True
        return interpreter, remote

    def call_environment_extension(
        self,
        *,
        server_name: str,
        operation: str,
        tool_name: str = "",
        arguments: Mapping[str, Any] | None = None,
        timeout_s: int = 30,
    ) -> dict[str, Any]:
        """Invoke one Harbor-declared MCP tool through the task environment.

        The server name must match exact task configuration. Network execution
        happens inside the task world, so Compose-only DNS names remain valid.
        """
        server = self._mcp_servers.get(str(server_name))
        if server is None:
            return {
                "success": False,
                "failure_class": "environment_extension_unknown",
                "error": f"MCP server is not task-declared: {server_name}",
            }
        try:
            interpreter, remote = self._ensure_mcp_client()
        except Exception as exc:
            return {
                "success": False,
                "failure_class": "environment_extension_client_unavailable",
                "error": f"{type(exc).__name__}: {exc}",
                "server": str(server_name),
                "transport": str(server.get("transport") or ""),
            }
        config_json = json.dumps(server, sort_keys=True, separators=(",", ":"))
        arguments_json = json.dumps(dict(arguments or {}), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        command_parts = [
            shlex.quote(interpreter),
            shlex.quote(remote),
            "--config-json", shlex.quote(config_json),
            "--operation", shlex.quote(str(operation)),
            "--tool-name", shlex.quote(str(tool_name or "")),
            "--arguments-json", shlex.quote(arguments_json),
            "--timeout-s", shlex.quote(str(max(1, int(timeout_s)))),
        ]
        command = " ".join(command_parts)
        runner = self.run_tracked_command if operation == "tools_call" else self.run_command
        result = runner(command, cwd=self.workspace_root, timeout_s=max(2, int(timeout_s) + 5))
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        payload: dict[str, Any] = {}
        if lines:
            try:
                decoded = json.loads(lines[-1])
                if isinstance(decoded, dict):
                    payload = decoded
            except json.JSONDecodeError:
                payload = {}
        success = bool(result.success and payload.get("ok") is True)
        return {
            "success": success,
            "failure_class": "" if success else "environment_extension_call_failed",
            "server": str(server_name),
            "transport": str(server.get("transport") or ""),
            "operation": str(operation),
            "tool_name": str(tool_name or ""),
            "result": payload.get("result"),
            "error": str(payload.get("error") or result.stderr or "").strip(),
            "error_type": str(payload.get("error_type") or ""),
            "exit_code": result.exit_code,
            "modified_paths": tuple(result.modified_paths),
            "artifact_paths": tuple(result.produced_artifacts),
            "removed_paths": tuple(result.removed_paths),
            "state_delta": dict(result.state_delta),
            "bridge_provenance": "harbor_task_environment:mcp_environment_client_v1",
        }

    def refresh_envmap(self, envmap: EnvMap) -> EnvMap:
        probe = dict(probe_environment(self, workspace_root=self.workspace_root))
        extension_facts = extension_probe_payload(self._mcp_servers.values())
        probe["environment_extensions"] = extension_facts
        metadata = dict(envmap.task_metadata)
        metadata["environment_probe"] = probe
        metadata["environment_extensions"] = extension_facts
        network_scope = envmap.network_scope
        network = probe.get("network") if isinstance(probe, dict) else None
        if isinstance(network, dict) and network.get("status") in {"probed_true", "probed_false"}:
            network_scope = "unenforced_probe_observation"
        from .envmap_builder import network_available, with_network_capability

        return replace(
            envmap,
            task_metadata=metadata,
            network_scope=network_scope,
            capabilities=with_network_capability(
                envmap.capabilities,
                available=network_available(network_scope, probe),
            ),
        )

    def exists(self, path: str) -> bool:
        remote = self._remote_path(path)
        result = self._exec(f"test -e {shlex.quote(remote)}", timeout_s=10)
        code, _stdout, _stderr = self._result_fields(result)
        return code == 0

    def glob(self, pattern: str) -> tuple[str, ...]:
        remote_pattern = self._remote_path(pattern)
        result = self._exec(
            f"find {shlex.quote(self.workspace_root)} -path {shlex.quote(remote_pattern)} -print 2>/dev/null | LC_ALL=C sort",
            timeout_s=30,
        )
        code, stdout, _stderr = self._result_fields(result)
        if code != 0:
            return ()
        return tuple(line.strip() for line in stdout.splitlines() if line.strip())

    def _archive_remote_process_logs(self, record: _RemoteProcess) -> None:
        """Copy managed-process logs into host-local custody before remote teardown.

        Harbor command results are already embedded in Aether receipts. This
        archive covers the separate long-lived process/terminal surfaces whose
        stdout/stderr live only in the task container and would otherwise vanish
        when a terminal directory or Harbor container is removed.
        """
        self._spool_archive_dir.mkdir(parents=True, exist_ok=True)
        for label, remote in (
            ("stdout", record.stdout_path),
            ("stderr", record.stderr_path),
            ("exit", record.exit_path),
        ):
            key = (record.process_id, label)
            if key in self._spool_archive:
                continue
            target = self._spool_archive_dir / (
                f"{record.generation}-{label}.log"
            )
            try:
                probe = self._exec(
                    f"test -f {shlex.quote(remote)}", timeout_s=10,
                )
                code, _stdout, _stderr = self._result_fields(probe)
                if code != 0:
                    continue
                self._await(
                    self.environment.download_file(remote, target), timeout_s=60,
                )
                if not target.is_file():
                    raise RuntimeError("Harbor download returned without a local file")
                self._spool_archive[key] = target
            except Exception as exc:
                target.unlink(missing_ok=True)
                detail = (
                    f"{record.process_id}:{label}:{type(exc).__name__}: {exc}"
                )
                if detail not in self._spool_archive_errors:
                    self._spool_archive_errors.append(detail)

    def export_spools(self, destination: str) -> dict[str, Any]:
        """Export Harbor-managed process/terminal streams as durable evidence.

        Unlike ``SubprocessExecutor``, ordinary Harbor foreground command output
        is already returned losslessly in the action result. The only distinct
        spool surface is long-lived process/terminal output stored remotely.
        Capture those bytes while the Harbor executor is alive and export them
        content-addressed on the host.
        """
        for record in tuple(self._processes.values()):
            self._archive_remote_process_logs(record)
        if self._spool_archive_errors:
            raise RuntimeError(
                "Harbor spool custody failed: "
                + " | ".join(self._spool_archive_errors[:8])
            )
        all_files = tuple(self._spool_archive.values())
        manifest = export_content_addressed_files(all_files, destination)
        terminal_files = tuple(
            path
            for (process_id, _label), path in self._spool_archive.items()
            if (self._processes.get(process_id) is not None
                and self._processes[process_id].interactive)
            or process_id.startswith("harbor-terminal:")
        )
        manifest["terminal_transcripts"] = export_content_addressed_files(
            terminal_files, str(Path(destination) / "terminals")
        )
        manifest["backend"] = "harbor_environment"
        manifest["managed_process_count"] = len(self._processes)
        return manifest

    def close(self) -> None:
        """Close task-scoped interactive sessions and harness-only temp helpers.

        This mirrors ``SubprocessExecutor.close`` for task processes. Noninteractive
        jobs may be part of required final state and remain Harbor-owned. The MCP
        bridge is harness transport infrastructure under /tmp, never a task artifact,
        and is removed deterministically.
        """
        if self._mcp_client_uploaded:
            try:
                self._exec(f"rm -f {shlex.quote(self._mcp_client_remote_path)}", timeout_s=10)
            except Exception:
                pass
            try:
                self._exec(f"rm -f {shlex.quote(self._rfb_client_remote_path)}", timeout_s=10)
            except Exception:
                pass
            self._mcp_client_uploaded = False
        if self._subreaper_uploaded:
            try:
                self._exec(f"rm -f {shlex.quote(self._subreaper_remote_path)}", timeout_s=10)
            except Exception:
                pass
            self._subreaper_uploaded = False
        for process_id, record in tuple(self._processes.items()):
            if not record.interactive:
                continue
            try:
                self.terminal_close(process_id)
            except Exception:
                pass
        self._terminal_workspace_state = None


__all__ = ["HarborEnvironmentExecutor"]
