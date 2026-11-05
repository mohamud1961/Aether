"""A real browser for the model, outside the graded container (AETHER_CORE_BROWSER=on).

Why (5 Nov, 47 Luna runs of a browser-graded HTML task): 0 passes, and no run ever installed or ran a browser; the
behaviour the task is judged on (what a browser executes) was never observed. The one pass of the sibling task drove
Selenium/Chrome. A capability, not advice: the model writes the browser code, Core only runs it.

The ``browser`` tool runs the model's Python in a sidecar container (image ``BROWSER_IMAGE``: Playwright with Chromium,
and the browser-use library, whose ``Browser`` is used without any LLM) that shares the task container's network
namespace, so ``http://localhost:<port>`` reaches the task's own servers. Files the call names are copied from the
task container into the sidecar at the same paths before the code runs (a snapshot; nothing is copied back, nothing
is installed into or written to the task container). Output is returned raw, head and tail kept when long.

The task container is proven from the host (clone.identify with the compose service's id) before anything runs. The
sidecar is started on first use, labelled, and sleeps only until the run's deadline, so it ends by itself even if
the run is killed. A failure to start is reported to the model as a tool error, never retried silently.
"""

from __future__ import annotations

import asyncio
import posixpath
import uuid
import weakref
from typing import Any, Awaitable, Callable

from .clone import HostRun, compose_container, host_run, identify
from .env import Environment

BROWSER_ENV = "AETHER_CORE_BROWSER"
BROWSER_IMAGE = "aether-browser:1"
MAX_OUT = 12_000
GRACE_S = 120

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
            "Returns stdout and stderr."
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

    async def copy(self, path: str) -> str:
        """Copy one path from the task container to the same path in the sidecar ('' or an error line)."""
        if not posixpath.isabs(path):
            return f"[files] {path}: not an absolute path, skipped"
        parent = posixpath.dirname(path.rstrip("/")) or "/"
        await self.host(["docker", "exec", self.name, "mkdir", "-p", parent], 60)
        proc = await asyncio.create_subprocess_shell(
            f"docker cp {self.cid}:{_q(path)} - | docker cp - {self.name}:{_q(parent)}",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        _, err = await asyncio.wait_for(proc.communicate(), 300)
        return "" if proc.returncode == 0 else f"[files] {path}: {err.decode(errors='replace').strip()[:200]}"

    async def run(self, code: str, wait_s: float) -> str:
        proc = await asyncio.create_subprocess_exec(
            "docker", "exec", "-i", "-w", "/tmp", self.name, "timeout", "-k", "5", str(int(wait_s)), "python3", "-",
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        try:
            out, _ = await asyncio.wait_for(proc.communicate(code.encode()), wait_s + 30)
        except asyncio.TimeoutError:
            proc.kill()
            return f"[browser] no result within {int(wait_s)} s"
        text = out.decode(errors="replace")
        status = "" if proc.returncode == 0 else f"\n[exit {proc.returncode}{' (time limit)' if proc.returncode == 124 else ''}]"
        return _clip(text) + status


Factory = Callable[[Environment], Awaitable[str]]  # the task container's proven id
_SIDECARS: "weakref.WeakKeyDictionary[Any, Sidecar]" = weakref.WeakKeyDictionary()


def compose_factory(project: str) -> Factory:
    """Harbor docker: the compose project's ``main`` container, proven through the environment (clone.identify)."""
    async def find(env: Environment) -> str:
        return await identify(env, known=await compose_container(project))
    return find


async def use(factory: Factory, env: Environment, args: dict[str, Any], remaining_s: float,
              host: HostRun = host_run) -> str:
    try:
        car = _SIDECARS.get(env)
        if car is None:
            car = Sidecar(await factory(env), host)
            await car.start(remaining_s)
            _SIDECARS[env] = car
        notes = [n for n in [await car.copy(str(p)) for p in (args.get("files") or [])] if n]
        wait = max(1.0, min(float(args.get("wait_s") or 120), 600.0, max(1.0, remaining_s - 10)))
        out = await car.run(str(args.get("code", "")), wait)
    except Exception as exc:  # the substrate failed: say so plainly
        return f"error: browser unavailable ({type(exc).__name__}: {str(exc)[:300]})"
    return "\n".join([*notes, out]) if notes else out


def _q(path: str) -> str:
    return "'" + path.replace("'", "'\\''") + "'"


def _clip(text: str) -> str:
    if len(text) <= MAX_OUT:
        return text
    half = MAX_OUT // 2
    return f"{text[:half]}\n[... {len(text) - MAX_OUT} characters omitted ...]\n{text[-half:]}"
