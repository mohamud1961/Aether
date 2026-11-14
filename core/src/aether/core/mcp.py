"""Task-declared MCP servers as one Core tool (AETHER_CORE_MCP=on with servers declared by the task).

Harbor passes a task's ``environment.mcp_servers`` to the agent; Claude Code and Codex expose such servers' tools to
the model. Core previously ignored the declaration (TB4 medical-claims-processing declares a Playwright server).

The server URL usually resolves only inside the task's network, so the client runs in the sandbox: a stdlib Python
daemon per server (``mcp_client_src``), started on first use and kept for the run, so a stateful server keeps its
session. Core exchanges JSON-RPC requests with it through files in the control directory. The ``mcp`` tool lists a
server's tools or calls one; results are returned as the server sent them (text items verbatim, images saved to a
sandbox file the model can view). Nothing is interpreted. A missing interpreter, unreachable server or timeout is
reported as the tool result.

Every request is an operation (operations.py) tracked until the model has been shown its result:

- The client takes the request's start token before sending it. A request whose publication Core lost is resolved:
  sent, or cancelled for certain (then nothing reached the server).
- A request still unanswered when the model's wait ends stays tracked. Its late answer is shown at the next mcp use.
- An identical request (same server, action, tool and arguments) made while an earlier one is tracked attaches to
  it instead of being sent again. A tool call has effects outside the sandbox; a retry after an unclear failure is
  how they get repeated. Once its result has been shown, an identical request is a new, deliberate one.
"""

from __future__ import annotations

import asyncio
import base64
import json
import secrets
import shlex
import time
from typing import Any

from . import mcp_adopt, operations
from .env import ProcessCleanupError, put_bytes, run, stop_process_tree
from .mcp_client_src import SOURCE

MAX_CHARS = 30_000


def tool(servers: list[dict[str, Any]]) -> dict:
    names = [s["name"] for s in servers]
    listed = "; ".join(f"{s['name']} ({s['transport']})" for s in servers)
    return {"type": "function", "function": {
        "name": "mcp",
        "strict": False,  # The selected server tool supplies the argument schema at runtime.
        "description": (f"Use an MCP server declared by this task's environment: {listed}. action=list returns the "
                        "server's tools with their input schemas; action=call runs one tool with arguments. The "
                        "server session persists for the whole run."),
        "parameters": {"type": "object", "properties": {
            "server": {"type": "string", "enum": names},
            "action": {"type": "string", "enum": ["list", "call"]},
            "tool": {"type": "string", "description": "Tool name (action=call)."},
            "arguments": {"type": "object", "additionalProperties": True,
                          "description": "Tool arguments from its listed input schema (action=call)."},
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
    def __init__(self, env, control_dir: str, servers: list[dict[str, Any]], adopt: bool = False):
        self.env, self.root = env, f"{control_dir}/mcp"
        # Adoption across controllers (mcp_adopt) and delivery authority (operations.seen), as for terminals.
        self.adopt = adopt
        self.delivery_tag = lambda: ""
        self.conversation: set[str] | None = None
        self.adopted_notes: dict[str, str] = {}
        self.servers = {s["name"]: s for s in servers}
        self.started: dict[str, str] = {}
        self.launched: list[str] = []
        self.seq = 0
        self.calls: list[dict[str, Any]] = []
        # Requests whose result the model has not been shown: ident -> {server, key, tool, action, published}.
        self.ops: dict[int, dict[str, Any]] = {}

    async def _start(self, name: str, remaining: float) -> str:
        if name in self.started:
            return self.started[name]
        if self.adopt and (adopted := await mcp_adopt.adopt(self, name)):
            self.started[name] = adopted
            self.launched.append(adopted)
            self.adopted_notes[name] = (f"[MCP client for server {name} adopted from an earlier controller of this task: "
                                        "its server session is kept]\n")
            return adopted
        spec = self.servers[name]
        d = f"{self.root}/session-{secrets.token_hex(12)}"
        q = shlex.quote
        await put_bytes(self.env, SOURCE.encode(), f"{self.root}/client.py")
        target = [spec["url"]] if spec["transport"] != "stdio" else [spec["command"], *spec["args"]]
        found = await run(self.env, "command -v python3 || command -v python", timeout_s=10)
        python = found.stdout.strip().splitlines()[0] if found.code == 0 and found.stdout.strip() else ""
        if not python:
            raise RuntimeError("no python3 in the task environment; the MCP client needs one")
        launch = (f"mkdir -m 700 {q(d)} && cd {q(d)} && "
                  f"{{ nohup {q(python)} {q(self.root + '/client.py')} {q(d)} "
                  f"{q(spec['transport'])} {' '.join(q(str(x)) for x in target)} "
                  f"</dev/null > {q(d + '/client.log')} 2>&1 & echo $! > pid; }}")
        self.launched.append(d)
        if (await run(self.env, launch, timeout_s=10)).code != 0:
            raise RuntimeError(f"MCP server {name}: client launch failed")
        deadline = time.monotonic() + max(1.0, min(60.0, remaining - 5))
        while time.monotonic() < deadline:
            state = await run(self.env, f"if test -f {q(d + '/error')}; then echo error; "
                                        f"elif test -f {q(d + '/ready')}; then echo ready; fi", timeout_s=10)
            if state.stdout.strip() == "error":
                raise RuntimeError(f"MCP server {name}: client initialization failed")
            if state.stdout.strip() == "ready":
                self.started[name] = d
                if self.adopt:
                    await run(self.env, mcp_adopt.record_script(self.root, name, d), timeout_s=10)
                return d
            await asyncio.sleep(0.2)
        raise TimeoutError(f"MCP server {name}: the client was not ready before its startup deadline")

    async def use(self, args: dict[str, Any], remaining: float) -> str:
        name, action = args["server"], args["action"]
        if name not in self.servers:
            return f"error: no declared MCP server named {name!r}"
        if action == "call" and not args.get("tool"):
            return "error: action=call requires tool"
        d = await self._start(name, remaining)
        timeout = max(1.0, min(float(args.get("timeout_s") or 120), 600.0, remaining - 5))
        key = json.dumps([action, args.get("tool"), args.get("arguments") or {}], sort_keys=True)
        earlier = self.adopted_notes.pop(name, "") + await self._settle(name, d, key)
        same = next((i for i, op in self.ops.items() if op["server"] == name and op["key"] == key), None)
        if same is not None:
            # A retry of a request already sent and not yet shown: attach to it, never send it twice.
            return earlier + await self._await(d, same, timeout, attached=True)
        self.seq += 1
        ident = self.seq
        method, params = (("tools/list", {}) if action == "list" else
                          ("tools/call", {"name": args["tool"], "arguments": args.get("arguments") or {}}))
        body = json.dumps({"id": ident, "method": method, "params": params}).encode()
        # Tracked before anything is written: from here a lost reply leaves the request to be resolved, never resent.
        self.ops[ident] = {"server": name, "key": key, "tool": args.get("tool"), "action": action, "published": False}
        await put_bytes(self.env, body, f"{d}/req.tmp.{ident}")
        q = shlex.quote
        published = await run(self.env, f"mv -f {q(f'{d}/req.tmp.{ident}')} {q(f'{d}/req_{ident}.json')}", timeout_s=10)
        if published.code != 0:
            del self.ops[ident]  # mv is atomic: a failed rename published nothing
            return earlier + f"error: MCP server {name}: could not publish request"
        self.ops[ident]["published"] = True
        return earlier + await self._await(d, ident, timeout)

    async def _settle(self, name: str, d: str, key: str) -> str:
        """Resolve this server's tracked requests before a new one: cancel any whose publication was lost and that the
        client has not taken, and show answers that arrived since. Requests identical to ``key`` are left to attach."""
        q, notes = shlex.quote, []
        for ident, op in sorted(self.ops.items()):
            if op["server"] != name:
                continue
            if not op["published"]:
                took = await run(self.env, f"cd {q(d)} || exit 4; ln -s {operations.REVOKED} start_{ident} 2>/dev/null; "
                                           f"readlink start_{ident}; true", timeout_s=10)
                token = took.stdout.strip()
                if took.code != 0 or token not in (operations.RUN, operations.REVOKED):
                    continue  # unreadable: stays tracked, and an identical request still attaches to it
                if token == operations.REVOKED:
                    del self.ops[ident]
                    notes.append(f"[MCP request #{ident} ({op['tool'] or op['action']}) was never sent: its publication "
                                 "failed before the client took it, and it is now cancelled. Nothing reached the server.]")
                    continue
                op["published"] = True
            if op["key"] == key:
                continue
            got = await run(self.env, f"cat {q(f'{d}/resp_{ident}.json')} 2>/dev/null; true", timeout_s=30)
            if got.stdout.strip():
                rendered = await self._finish(d, ident, json.loads(got.stdout), 0.0)
                notes.append(f"[result of earlier MCP request #{ident} ({op['tool'] or op['action']}), not shown before]\n"
                             f"{rendered}")
        return "".join(note + "\n" for note in notes)

    async def _await(self, d: str, ident: int, timeout: float, attached: bool = False) -> str:
        q, op = shlex.quote, self.ops[ident]
        started = time.monotonic()
        head = (f"[this request matches MCP request #{ident}, sent earlier and not yet shown; it was not sent again. "
                "Its result:]\n") if attached else ""
        while time.monotonic() - started < timeout:
            got = await run(self.env, f"cat {q(f'{d}/resp_{ident}.json')} 2>/dev/null; true", timeout_s=30)
            if got.stdout.strip():
                return head + await self._finish(d, ident, json.loads(got.stdout), time.monotonic() - started)
            await asyncio.sleep(0.2)
        return (f"[MCP request #{ident} to {op['server']} ({op['tool'] or op['action']}) has no result after "
                f"{timeout:g} s. It was published to the client, so its effect is unknown until its answer arrives. "
                "Core shows that answer at the next mcp use; an identical request attaches to it instead of being "
                "sent again.]")

    async def _finish(self, d: str, ident: int, reply: dict, seconds: float) -> str:
        op = self.ops[ident]
        if reply.get("id") != ident:
            return f"error: MCP server {op['server']}: response identity does not match the request"
        rendered = await self._render(d, ident, op["action"], reply)
        if self.adopt:  # the continued conversation acknowledges the token
            tag = self.delivery_tag()
            recorded = await run(self.env, operations.mark_delivered(d, ident, tag), timeout_s=10)
            if recorded.code != 0:
                raise RuntimeError(f"MCP request #{ident}: result delivery could not be recorded")
        del self.ops[ident]
        self.calls.append({"server": op["server"], "action": op["action"], "tool": op["tool"],
                           "error": "error" in reply, "s": round(seconds, 2)})
        return rendered

    async def _render(self, d: str, ident: int, action: str, reply: dict) -> str:
        if "error" in reply:
            message = str((reply["error"] or {}).get("message", ""))
            if message.startswith(("send failed", "the server connection closed")):
                # The request may have reached the server before the failure: its effect is unknown.
                return ("error: MCP " + json.dumps(reply["error"])[:2000] + "\n[the request may have reached the "
                        "server before this failure; its effect is unknown. Check the result before calling again.]")
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
                ext = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}.get(item.get("mimeType"), "bin")
                path = f"{d}/image_{ident}_{i}.{ext}"
                await put_bytes(self.env, base64.b64decode(item["data"]), path)
                parts.append(f"[image returned by the server, saved at {path}]")
            else:
                parts.append(json.dumps(item)[:2000])
        text = "\n".join(parts) if parts else json.dumps(result)[:2000]
        return (("[the tool reported an error]\n" if result.get("isError") else "") + text)[:MAX_CHARS]

    async def close(self) -> None:
        unresolved = []
        for d in self.launched:
            identity = await run(self.env, f"cat {shlex.quote(d + '/owner')} 2>/dev/null", timeout_s=10)
            fields = identity.stdout.split()
            if len(fields) != 2 or any(not field.isdecimal() for field in fields):
                unresolved.append("client ownership receipt missing")
                continue
            pid, birth = fields
            try:
                await stop_process_tree(self.env, [int(pid)], identities={pid: birth})
            except ProcessCleanupError as exc:
                if int(pid) not in exc.receipt.get("missing_roots", []):
                    unresolved.append("client cleanup unverified")
        if unresolved:
            raise RuntimeError("; ".join(unresolved))
