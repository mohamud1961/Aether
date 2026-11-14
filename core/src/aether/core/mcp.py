"""Task-declared MCP servers as one Core tool (AETHER_CORE_MCP=on with servers declared by the task).

Harbor passes a task's ``environment.mcp_servers`` to the agent; Claude Code and Codex expose such servers' tools to
the model. Core previously ignored the declaration (TB4 medical-claims-processing declares a Playwright server).

The server URL usually resolves only inside the task's network, so the client runs in the sandbox: a stdlib Python
daemon per server (``mcp_client_src``), started on first use and kept for the run, so a stateful server keeps its
session. Core exchanges JSON-RPC requests with it through files in the control directory. The ``mcp`` tool lists a
server's tools or calls one; results are returned as the server sent them (text items verbatim, images saved to a
sandbox file the model can view). Nothing is interpreted. A missing interpreter, unreachable server or timeout is
reported as the tool result.
"""

from __future__ import annotations

import asyncio
import base64
import json
import shlex
import time
from typing import Any

from .env import put_bytes, run
from .mcp_client_src import SOURCE

MAX_CHARS = 30_000


def tool(servers: list[dict[str, Any]]) -> dict:
    names = [s["name"] for s in servers]
    listed = "; ".join(f"{s['name']} ({s['transport']}{', ' + s['url'] if s.get('url') else ''})" for s in servers)
    return {"type": "function", "function": {
        "name": "mcp",
        "description": (f"Use an MCP server declared by this task's environment: {listed}. action=list returns the "
                        "server's tools with their input schemas; action=call runs one tool with arguments. The "
                        "server session persists for the whole run."),
        "parameters": {"type": "object", "properties": {
            "server": {"type": "string", "enum": names},
            "action": {"type": "string", "enum": ["list", "call"]},
            "tool": {"type": "string", "description": "Tool name (action=call)."},
            "arguments": {"type": "object", "description": "Tool arguments (action=call)."},
            "timeout_s": {"type": "number", "description": "Seconds to wait for the result (default 120, max 600)."},
        }, "required": ["server", "action"]},
    }}


def normalize(servers: Any) -> list[dict[str, Any]]:
    out = []
    for s in servers or []:
        get = (lambda k: s.get(k)) if isinstance(s, dict) else (lambda k: getattr(s, k, None))
        transport = str(get("transport") or "sse")
        out.append({"name": str(get("name")), "transport": "streamable-http" if transport == "http" else transport,
                    "url": get("url"), "command": get("command"), "args": list(get("args") or [])})
    return out


class Mcp:
    def __init__(self, env, control_dir: str, servers: list[dict[str, Any]]):
        self.env, self.root = env, f"{control_dir}/mcp"
        self.servers = {s["name"]: s for s in servers}
        self.started: dict[str, str] = {}
        self.seq = 0
        self.calls: list[dict[str, Any]] = []

    async def _start(self, name: str) -> str:
        if name in self.started:
            return self.started[name]
        spec, d = self.servers[name], f"{self.root}/{name}"
        q = shlex.quote
        await put_bytes(self.env, SOURCE.encode(), f"{self.root}/client.py")
        target = [spec["url"]] if spec["transport"] != "stdio" else [spec["command"], *spec["args"]]
        found = await run(self.env, "command -v python3 || command -v python", timeout_s=10)
        python = found.stdout.strip().splitlines()[0] if found.code == 0 and found.stdout.strip() else ""
        if not python:
            raise RuntimeError("no python3 in the task environment; the MCP client needs one")
        launch = (f"mkdir -p {q(d)} && cd {q(d)} && nohup {q(python)} {q(self.root + '/client.py')} {q(d)} "
                  f"{q(spec['transport'])} {' '.join(q(str(x)) for x in target)} > {q(d + '/client.log')} 2>&1 "
                  f"& echo $! > {q(d + '/pid')}")
        await run(self.env, launch, timeout_s=10)
        for _ in range(300):
            state = await run(self.env, f"cat {q(d + '/error')} 2>/dev/null && echo __E__; "
                                        f"test -f {q(d + '/ready')} && echo __R__; true", timeout_s=10)
            if "__E__" in state.stdout:
                raise RuntimeError("MCP server " + name + ": " + state.stdout.split("__E__")[0].strip()[:500])
            if "__R__" in state.stdout:
                self.started[name] = d
                return d
            await asyncio.sleep(0.2)
        raise TimeoutError(f"MCP server {name}: the client was not ready within 60 s")

    async def use(self, args: dict[str, Any], remaining: float) -> str:
        name, action = args["server"], args["action"]
        if name not in self.servers:
            return f"error: no declared MCP server named {name!r}"
        if action == "call" and not args.get("tool"):
            return "error: action=call requires tool"
        d = await self._start(name)
        self.seq += 1
        ident = self.seq
        timeout = max(1.0, min(float(args.get("timeout_s") or 120), 600.0, remaining - 5))
        method, params = (("tools/list", {}) if action == "list" else
                          ("tools/call", {"name": args["tool"], "arguments": args.get("arguments") or {}}))
        body = json.dumps({"id": ident, "method": method, "params": params, "timeout": timeout}).encode()
        await put_bytes(self.env, body, f"{d}/req.tmp.{ident}")
        q = shlex.quote
        await run(self.env, f"mv -f {q(f'{d}/req.tmp.{ident}')} {q(f'{d}/req_{ident}.json')}", timeout_s=10)
        started = time.monotonic()
        while time.monotonic() - started < timeout + 10:
            got = await run(self.env, f"cat {q(f'{d}/resp_{ident}.json')} 2>/dev/null; true", timeout_s=30)
            if got.stdout.strip():
                reply = json.loads(got.stdout)
                self.calls.append({"server": name, "action": action, "tool": args.get("tool"),
                                   "error": "error" in reply, "s": round(time.monotonic() - started, 2)})
                return await self._render(d, ident, action, reply)
            await asyncio.sleep(0.2)
        return f"error: MCP server {name} gave no result within {timeout:g} s; the request may still be running"

    async def _render(self, d: str, ident: int, action: str, reply: dict) -> str:
        if "error" in reply:
            return "error: MCP " + json.dumps(reply["error"])[:2000]
        result = reply.get("result") or {}
        if action == "list":
            lines = [f"- {t.get('name')}: {(t.get('description') or '').strip()[:300]} input: "
                     f"{json.dumps(t.get('inputSchema') or {}, separators=(',', ':'))[:600]}"
                     for t in result.get("tools") or []]
            return (f"{len(lines)} tools:\n" + "\n".join(lines))[:MAX_CHARS]
        parts = []
        for i, item in enumerate(result.get("content") or []):
            kind = item.get("type")
            if kind == "text":
                parts.append(item.get("text", ""))
            elif kind == "image" and item.get("data"):
                ext = (item.get("mimeType") or "image/png").split("/")[-1].split("+")[0]
                path = f"{d}/image_{ident}_{i}.{ext}"
                await put_bytes(self.env, base64.b64decode(item["data"]), path)
                parts.append(f"[image returned by the server, saved at {path}]")
            else:
                parts.append(json.dumps(item)[:2000])
        text = "\n".join(parts) if parts else json.dumps(result)[:2000]
        return (("[the tool reported an error]\n" if result.get("isError") else "") + text)[:MAX_CHARS]

    async def close(self) -> None:
        for d in self.started.values():
            await run(self.env, f"kill $(cat {shlex.quote(d + '/pid')}) 2>/dev/null; true", timeout_s=10)
