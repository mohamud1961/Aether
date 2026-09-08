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
from .environment_probe import probe_environment
from .harbor_workspace_state import (
    RemoteWorkspaceSnapshot,
    diff_remote_workspace_snapshots,
    parse_remote_workspace_snapshot,
    remote_workspace_snapshot_command,
)
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
        self._verifier_world_roots: tuple[str, ...] = (self.workspace_root,)
        self.default_env = dict(default_env or {})
        if local_state_dir is None:
            local_state_dir = Path(tempfile.mkdtemp(prefix="aether-next-harbor-"))
        self.local_state_dir = Path(local_state_dir).resolve()
        self.local_state_dir.mkdir(parents=True, exist_ok=True)
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
    ) -> dict[str, Any]:
        """Run a PCR Verifier command in a disposable Docker sibling.

        The exact Harbor parent is snapshotted while Aether explicitly owns and
        closes a short pause transaction.  The parent must be proven runnable
        again before the snapshot is used. A networkless sibling then copies only
        the verifier command-child into /app, executes once, and is destroyed.
        """
        child = str(workspace_root or "").strip()
        if not child.startswith("/app.verifier_overlay_") or ".command_" not in child:
            return {
                "error": "verifier_independent_isolation_invalid_harbor_child",
                "metadata": {
                    "execution_isolation": "harbor_docker_snapshot_sibling",
                    "isolation_backend": "harbor0200_docker_snapshot_sibling",
                    "independent_isolation_verified": False,
                    "isolation_cleanup_verified": False,
                },
            }
        container_id, lookup_error = self._harbor_docker_main_container_id()
        nonce = uuid.uuid4().hex[:16]
        image_tag = f"aether-harbor-verifier-{nonce}:snapshot"
        sibling_name = f"aether-harbor-verifier-{nonce}"
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
            "workspace_snapshot_path_sha256": hashlib.sha256(child.encode("utf-8")).hexdigest(),
            "parent_runnable_after_snapshot": False,
            "parent_runnable_probe_count": 0,
        }
        if lookup_error:
            return {"error": lookup_error, "metadata": metadata}
        metadata["parent_container_id_sha256"] = hashlib.sha256(container_id.encode("ascii")).hexdigest()

        error = ""
        result: CommandResult | None = None
        image_created = False
        with self._verifier_snapshot_lock:
            try:
                image_created, snapshot_error, snapshot_metadata = self._snapshot_harbor_parent_image(
                    container_id, image_tag,
                )
                metadata.update(snapshot_metadata)
                if snapshot_error:
                    error = snapshot_error
                if image_created and not error:
                    ready_marker = f"/.__aether_verifier_ready_{nonce}"
                    bootstrap = (
                        'set -eu; src="$1"; ready="$2"; '
                        'rm -rf /app; mkdir -p /app; cp -a "$src"/. /app/; '
                        'touch "$ready"; exec bash -lc "while :; do sleep 3600; done"'
                    )
                    run_args = [
                        "docker", "run", "--detach", "--name", sibling_name,
                        "--network", "none", "--workdir", "/",
                        "--entrypoint", "bash", image_tag,
                        "-lc", bootstrap, "aether-harbor-verifier", child, ready_marker,
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
                        else:
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
            finally:
                # The parent pause transaction has already been closed before this
                # point. Cleanup must never require a paused Harbor parent.
                self._docker_host_call(["docker", "rm", "-f", sibling_name], timeout_s=30)
                sibling_inspect, sibling_inspect_error = self._docker_host_call(
                    ["docker", "inspect", sibling_name], timeout_s=15,
                )
                sibling_absent, sibling_absence_error = self._docker_inspect_proves_absent(
                    sibling_inspect, sibling_inspect_error, kind="sibling container",
                )
                if image_created:
                    self._docker_host_call(["docker", "image", "rm", "-f", image_tag], timeout_s=60)
                image_inspect, image_inspect_error = self._docker_host_call(
                    ["docker", "image", "inspect", image_tag], timeout_s=15,
                )
                image_absent, image_absence_error = self._docker_inspect_proves_absent(
                    image_inspect, image_inspect_error, kind="snapshot image",
                )
                parent_runnable, parent_runnable_error, parent_probe_count = (
                    self._wait_for_docker_container_runnable(container_id, timeout_s=10.0)
                )
                metadata.update({
                    "sibling_container_removed": sibling_absent,
                    "snapshot_image_removed": image_absent,
                    "isolation_cleanup_verified": bool(sibling_absent and image_absent),
                    "sibling_inspect_error": sibling_inspect_error or sibling_absence_error,
                    "snapshot_image_inspect_error": image_inspect_error or image_absence_error,
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

    def _await(self, awaitable: Awaitable[_T], *, timeout_s: float) -> _T:
        if not self.event_loop.is_running():
            raise RuntimeError("Harbor event loop is not running")
        future = asyncio.run_coroutine_threadsafe(awaitable, self.event_loop)
        return future.result(timeout=max(1.0, float(timeout_s) + 5.0))

    def _exec(self, command: str, *, cwd: str | None = None, timeout_s: int = 30) -> Any:
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
        remote_dir = f"{self.workspace_root}/.aether/harbor_jobs/foreground-{generation}"
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
        started = time.monotonic()
        effective_timeout = max(1, int(timeout_s))
        # Timeout authority begins when run_command is invoked, not after the
        # remote launch handshake returns. The child may already be executing
        # while launch/upload/transport acknowledgement is in flight; granting
        # a fresh timeout after that handshake can let a timed-out command
        # mutate task state beyond its declared authority under host load.
        deadline = started + effective_timeout
        record = self._launch_supervised_foreground_command(command, cwd=cwd)
        timed_out = False
        exit_code: int | None = None
        try:
            exit_visibility_deadline: float | None = None
            last_status_detail = ""
            while True:
                live, observed_exit, status_detail = self._remote_status(record)
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
                terminated, cleanup_detail = self._terminate_supervised_foreground(record)
                if not terminated:
                    raise RuntimeError(
                        "Harbor command timeout cleanup could not prove process-group termination: "
                        + cleanup_detail
                    )
            stdout, child_stderr = self._download_remote_process_streams(record)
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
                metrics={"wall_time_s": time.monotonic() - started},
                provenance=(("harbor:subreaper_descendant_tree",) if self._docker_environment_type() else ("harbor:supervised_process_group",)),
            )
        finally:
            self._cleanup_supervised_foreground(record)

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
        remote_dir = f"{self.workspace_root}/.aether/harbor_jobs/{generation}"
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
                "alive=false; if kill -0 \"$pid\" 2>/dev/null && [ -z \"$code\" ]; then alive=true; fi;",
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
        completed = not live and exit_code is not None
        status = "running" if live else ("completed" if exit_code == 0 else "failed" if exit_code is not None else "unknown")
        return JobProbeResult(
            target=target,
            found=True,
            status=status,
            completed=completed,
            succeeded=(exit_code == 0) if completed else None,
            exit_code=exit_code,
            detail=detail or status,
            job_id=record.process_id,
            process_id=record.process_id,
            process_generation=record.generation,
            process_generation_verified=True,
            lifecycle_authority="harbor_environment_registered_process",
            pid=record.pid,
        )

    def stop_process(self, target: str) -> bool:
        record = self._process_for(target)
        if record is None:
            return False
        result = self._exec(
            f"kill -TERM -- -{record.pid} 2>/dev/null || kill -TERM {record.pid} 2>/dev/null || true",
            timeout_s=15,
        )
        _code, _stdout, _stderr = self._result_fields(result)
        return True

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
        remote_dir = f"{self.workspace_root}/.aether/harbor_terminals/{generation}"
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
        semantic_binary_modes = {"auto", "preview", "image", "ocr", "pdf", "frames"}
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
        return replace(
            envmap,
            task_metadata=metadata,
            network_scope=network_scope,
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
