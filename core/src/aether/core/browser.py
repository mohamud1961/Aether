"""A real browser for the model, outside the graded container (AETHER_CORE_BROWSER=on).

Why (5 Nov, 47 Luna runs of a browser-graded HTML task): 0 passes, and no run ever installed or ran a browser; the
behaviour the task is judged on (what a browser executes) was never observed. The one pass of the sibling task drove
Selenium/Chrome. A capability, not advice: the model writes the browser code, Core only runs it.

The ``browser`` tool runs the model's Python in a sidecar container (image ``BROWSER_IMAGE``: Playwright with Chromium,
and the browser-use library, whose ``Browser`` is used without any LLM) that shares the task container's network
namespace, so ``http://localhost:<port>`` reaches the task's own servers. Files the call names are copied from the
task container into the sidecar at the same paths before the code runs (a snapshot; nothing is copied back, nothing
is installed into or written to the task container). Output is returned raw, head and tail kept when long.

The task container is proven from the host (clone.identify with the compose service's id) before anything runs.
Core owns the sidecar until run cleanup. Its finite lifetime bounds leftovers if Core itself is killed.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import posixpath
import re
import signal
import tempfile
import uuid
from pathlib import Path
from typing import Any, Awaitable, Callable

from . import images
from .clone import HostRun, compose_container, host_run, identify
from .env import Environment

BROWSER_ENV = "AETHER_CORE_BROWSER"
BROWSER_IMAGE = "aether-browser:1"
MAX_OUT = 12_000
GRACE_S = 120
SCREENSHOT_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}\.png")
SCREENSHOT_MAX = 8_000_000

_PUBLISH_INPUT = """import ctypes, errno, os, shutil, sys
stage, target = sys.argv[1:]
staged = os.path.join(stage, 'incoming', os.path.basename(target))
try:
    os.replace(staged, target)
except OSError as error:
    if error.errno not in (errno.ENOTEMPTY, errno.EEXIST, errno.EISDIR, errno.ENOTDIR):
        raise
    # The sidecar is Linux. Exchange a complete staged entry with the old entry.
    at_fdcwd, rename_exchange = -100, 2
    exchange = ctypes.CDLL(None, use_errno=True).renameat2
    if exchange(at_fdcwd, os.fsencode(staged), at_fdcwd, os.fsencode(target), rename_exchange) != 0:
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code), target)
shutil.rmtree(stage)
"""

TOOL = {
    "type": "function",
    "function": {
        "name": "browser",
        "description": (
            "Run Python code against a real headless Chromium. The code runs in a separate machine that shares this "
            "container's network (http://localhost:<port> reaches servers running here) and has Playwright "
            "(`from playwright.sync_api import sync_playwright`) and browser-use (`from browser_use import Browser`) "
            "installed. Files listed in `files` are copied from this container to the same paths there first (a "
            "snapshot; changes there are not copied back). Each call is a fresh Python process; print what you need. "
            "Returns a bounded stdout/stderr preview and the command status. To see a screenshot, save it under "
            "/tmp and pass its PNG basename as screenshot."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Python source to run."},
                "files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Absolute paths (files or directories) in this container to copy over first.",
                },
                "wait_s": {"type": "number", "description": "Time limit in seconds (default 120, max 600)."},
                "screenshot": {"type": "string", "description": "Optional PNG basename written in /tmp by this call."},
            },
            "required": ["code"],
        },
    },
}


def with_tool(definitions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The tool list with ``browser`` before ``finish``."""
    return [*definitions[:-1], TOOL, definitions[-1]]


class Sidecar:
    def __init__(self, cid: str, host: HostRun) -> None:
        self.cid, self.host, self.name = cid, host, f"aether-browser-{uuid.uuid4().hex[:12]}"
        self.started = False

    async def start(self, life_s: float) -> None:
        code, _, err = await self.host(
            ["docker", "run", "-d", "--rm", "--name", self.name, "--label", "aether.browser=1",
             "--network", f"container:{self.cid}", "--memory", "2g", "--cpus", "1", "--shm-size", "1g",
             "--entrypoint", "sleep", BROWSER_IMAGE, str(int(life_s + GRACE_S))], 300)
        if code != 0:
            raise RuntimeError(f"browser could not start: {err.strip()[:300]}")
        self.started = True

    async def close(self) -> None:
        _, _, removal_error = await self.host(["docker", "rm", "-f", self.name], 6)
        code, _, inspect_error = await self.host(
            ["docker", "container", "inspect", self.name], 4
        )
        if code != 1 or "no such container" not in inspect_error.lower():
            raise RuntimeError(f"browser sidecar removal unverified: {removal_error or inspect_error}")

    async def copy(self, path: str) -> None:
        """Stage an exact snapshot and publish it before running dependent code."""
        if not posixpath.isabs(path):
            raise ValueError(f"[files] {path}: expected an absolute path")
        path = posixpath.normpath(path)
        if not posixpath.basename(path):
            raise ValueError("[files] copy a file or directory below the filesystem root")
        parent = posixpath.dirname(path)
        stage = posixpath.join(parent, f".aether-browser-{uuid.uuid4().hex}")
        code, _, err = await self.host(
            ["docker", "exec", self.name, "sh", "-c",
             'mkdir -p -- "$1" && mkdir -m 700 -- "$2" && mkdir -- "$2/incoming"',
             "core-browser-copy", parent, stage], 60,
        )
        if code != 0:
            raise OSError(f"[files] {path}: sidecar destination failed: {err.strip()[:200]}")
        published = False
        try:
            proc = await asyncio.create_subprocess_exec(
                "/bin/bash", "-o", "pipefail", "-c", 'docker cp "$1" - | docker cp - "$2"',
                "core-browser-copy", f"{self.cid}:{path}", f"{self.name}:{stage}/incoming",
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
                start_new_session=True,
            )
            try:
                _, detail = await asyncio.wait_for(proc.communicate(), 300)
            except (TimeoutError, asyncio.CancelledError):
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                await proc.wait()
                raise
            if proc.returncode != 0:
                raise OSError(f"[files] {path}: {detail.decode(errors='replace').strip()[:200]}")
            code, _, err = await self.host(
                ["docker", "exec", self.name, "python3", "-c", _PUBLISH_INPUT, stage, path], 60,
            )
            if code != 0:
                raise OSError(f"[files] {path}: snapshot publication failed: {err.strip()[-250:]}")
            published = True
        finally:
            if not published:
                await self.host(["docker", "exec", self.name, "rm", "-rf", "--", stage], 10)

    async def run(self, code: str, wait_s: float) -> str:
        proc = await asyncio.create_subprocess_exec(
            "docker", "exec", "-i", "-w", "/tmp", self.name, "timeout", "-k", "5", str(int(wait_s)), "python3", "-",
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        try:
            out, _ = await asyncio.wait_for(proc.communicate(code.encode()), wait_s + 30)
        except (TimeoutError, asyncio.CancelledError) as exc:
            if proc.returncode is None:
                proc.kill()
            await proc.wait()
            if isinstance(exc, asyncio.CancelledError):
                raise
            return "[browser] host wait expired before a result arrived. Remote command completion unconfirmed."
        text = out.decode(errors="replace")
        status = "" if proc.returncode == 0 else f"\n[browser command exit status {proc.returncode}]"
        return _clip(text) + status

    async def screenshot(self, name: str) -> tuple[str, str]:
        target = f"/tmp/{name}"
        code, info, _ = await self.host(
            ["docker", "exec", self.name, "sh", "-c",
             'test -f "$1" && test ! -L "$1" && stat -c %s -- "$1" && sha256sum < "$1"',
             "core-browser-image", target], 5,
        )
        fields = info.split()
        if code or len(fields) < 2 or not fields[0].isdigit() or not 0 < int(fields[0]) <= SCREENSHOT_MAX:
            raise ValueError("browser screenshot missing, nonregular or too large")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "capture.png"
            status, _, _ = await self.host(["docker", "cp", f"{self.name}:{target}", str(path)], 10)
            if status or path.is_symlink() or not path.is_file() or path.stat().st_size != int(fields[0]):
                raise ValueError("browser screenshot transfer could not be confirmed")
            data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != fields[1]:
            raise ValueError("browser screenshot changed while being copied")
        if not data.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("browser screenshot is not PNG data")
        return images.encode(data, f"browser screenshot {name}")


Factory = Callable[[Environment], Awaitable[str]]  # the task container's proven id


def configure(config: Any, environment: Any, environ: Any) -> Any:
    """``config`` with a browser for a Harbor docker environment when AETHER_CORE_BROWSER=on ('off'/unset: unchanged)."""
    mode = (environ.get(BROWSER_ENV) or "off").strip()
    if mode not in ("on", "off"):
        raise ValueError(f"{BROWSER_ENV} must be on or off, got {mode!r}")
    if mode == "off":
        return config
    from dataclasses import replace

    from harbor.environments.docker.docker import _sanitize_docker_compose_project_name as name
    return replace(config, browser=compose_factory(name(environment.session_id)))


def compose_factory(project: str) -> Factory:
    """Harbor docker: the compose project's ``main`` container, proven through the environment (clone.identify)."""
    async def find(env: Environment) -> str:
        return await identify(env, known=await compose_container(project))
    return find


class BrowserSession:
    def __init__(self, factory: Factory, env: Environment, host: HostRun = host_run) -> None:
        self.factory, self.env, self.host = factory, env, host
        self.sidecar: Sidecar | None = None
        self.image: tuple[str, str] | None = None

    async def use(self, args: dict[str, Any], remaining_s: float) -> str:
        self.image = None
        try:
            screenshot = args.get("screenshot")
            if screenshot is not None and (not SCREENSHOT_NAME.fullmatch(screenshot) or not images.available()):
                raise ValueError("screenshot requires a PNG basename and image support")
            if self.sidecar is None:
                self.sidecar = Sidecar(await self.factory(self.env), self.host)
                await self.sidecar.start(remaining_s)
            car = self.sidecar
            if not car.started:
                raise RuntimeError("sidecar startup was unconfirmed")
            for path in args.get("files") or []:
                await car.copy(path)
            if screenshot:
                status, _, _ = await self.host(["docker", "exec", car.name, "rm", "-f", "--", f"/tmp/{screenshot}"], 5)
                if status:
                    raise ValueError("prior browser screenshot could not be cleared")
            wait = max(1.0, min(float(args.get("wait_s") or 120), 600.0, max(1.0, remaining_s - 10)))
            out = await car.run(str(args.get("code", "")), wait)
            if screenshot:
                try:
                    self.image = await car.screenshot(screenshot)
                except (OSError, RuntimeError, ValueError) as error:
                    return f"{out}\n[browser screenshot unavailable: {error}]"
        except Exception as exc:
            return f"error: browser unavailable ({type(exc).__name__}: {str(exc)[:300]})"
        return out

    async def close(self) -> None:
        if self.sidecar is not None:
            await self.sidecar.close()


def _clip(text: str) -> str:
    if len(text) <= MAX_OUT:
        return text
    half = MAX_OUT // 2
    return f"{text[:half]}\n[... {len(text) - MAX_OUT} characters omitted ...]\n{text[-half:]}"
