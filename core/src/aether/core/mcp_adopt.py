"""A restarted controller adopts the MCP client session an earlier controller left running (operation tracking on).

Before, each controller started a new client daemon in a new session directory. A stateful server (a browser, a
database session) lost its state, and a request the earlier controller had sent could still be answered unseen, so a
naive retry sent it twice. Now ``current-<server>`` names the live session directory. A new controller adopts it when
the daemon recorded in its ``owner`` file is the same live process (pid and start time) and it is ``ready``.

The requests are rebuilt from the session directory (operations.py records, the daemon's ``start_<id>`` tokens):
- ``req_<id>.json`` whose result was not shown (no delivery, or a delivery whose tool call is not in the conversation
  continued here): tracked again with its identity, so its answer is shown at the next use and an identical request
  attaches to it instead of being sent again;
- ``req.tmp.<id>`` never published: its token is taken as ``revoked``, so the daemon never sends it.
"""

from __future__ import annotations

import hashlib
import json
import re
import shlex

from . import operations
from .env import alive_test, run
from .terminal_adopt import _BIRTH

IDEMPOTENCY_META = "aether/idempotency-key"  # the params._meta field an MCP tool call carries its key in (A14)


def pointer(root: str, name: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", name)[:40] + "-" + hashlib.sha256(name.encode()).hexdigest()[:8]
    return f"{root}/current-{safe}"


def record_script(root: str, name: str, d: str) -> str:
    q, path = shlex.quote, pointer(root, name)
    return f"printf %s {q(d)} > {q(path + '.tmp')} && mv {q(path + '.tmp')} {q(path)}"


async def same_process(env, owner: str) -> bool | None:
    """Whether the daemon an ``owner`` record names (pid and start time) is the same live process: True, False (it
    ended, or its pid now belongs to another process), or None (the record or the check could not be read)."""
    fields = owner.split()
    if len(fields) != 2 or not fields[0].isdecimal():
        return None
    pid = int(fields[0])
    now = await run(env, f"{alive_test(pid)} && {{ {_BIRTH.format(pid=pid)}; }} || echo __DEAD__", timeout_s=10)
    if now.code != 0:
        return None
    return now.stdout.strip() == fields[1]


async def client_alive(env, d: str) -> bool | None:
    """``same_process`` for the client daemon of session directory ``d``."""
    got = await run(env, f"cat {shlex.quote(d + '/owner')} 2>/dev/null; true", timeout_s=10)
    return None if got.code != 0 else await same_process(env, got.stdout)


async def adopt(mcp, name: str) -> str | None:
    """The adopted session directory for server ``name`` (requests restored into ``mcp.ops``), or None."""
    q = shlex.quote
    # Every read prints a marker for each real outcome; no reply is never "nothing to adopt" (T2 adoption sweep,
    # 15 Nov: read that way, a fresh client was started and the identical retry ran the tool twice).
    got = await operations.observe(mcp.env, f"echo __PTR__; cat {q(pointer(mcp.root, name))} 2>/dev/null; true",
                                   ("__PTR__",), f"MCP server {name}'s session pointer")
    d = got.partition("__PTR__\n")[2].strip()
    if not d.startswith(mcp.root + "/session-") or "\n" in d:
        return None
    state = await operations.observe(mcp.env, f"cd {q(d)} 2>/dev/null || {{ echo __NODIR__; exit 0; }}; cat owner 2>/dev/null; "
                                     "echo __SEP__; test -f ready && echo ready; echo __SEP__; ls; echo __END__",
                                     ("__NODIR__", "__END__"), f"MCP server {name}'s session state")
    if "__NODIR__" in state:
        return None
    owner, ready, listing = (state.split("__SEP__\n") + ["", "", ""])[:3]
    fields = owner.split()
    if ready.strip() != "ready" or len(fields) != 2 or not fields[0].isdecimal():
        return None
    alive = await same_process(mcp.env, owner)
    if alive is None:
        alive = await same_process(mcp.env, owner)
    if alive is None:
        raise RuntimeError(f"whether MCP server {name}'s client is alive could not be observed; nothing was changed")
    if not alive:
        return None
    sent = sorted(int(m.group(1)) for m in re.finditer(r"^req_(\d+)\.json$", listing, re.M))
    staged = sorted(int(m.group(1)) for m in re.finditer(r"^req\.tmp\.(\d+)$", listing, re.M))
    mcp.seq = max([mcp.seq, *sent, *staged])
    for ident in staged:
        if ident not in sent:
            await run(mcp.env, f"cd {q(d)} && ln -s {operations.REVOKED} start_{ident} 2>/dev/null; true", timeout_s=10)
    for ident in sent:
        records = await operations.observe(mcp.env, operations.resolve_script(d, ident, revoke=False), ("__AETHER_OP__",),
                                           f"MCP request #{ident}'s records")
        parsed = operations.parse(records)
        if parsed is None or operations.seen(parsed[2], mcp.conversation):
            continue
        body = await operations.observe(mcp.env, f"cat {q(f'{d}/req_{ident}.json')} 2>/dev/null; echo; echo __REQ__",
                                        ("__REQ__",), f"MCP request #{ident}")
        try:
            request = json.loads(body.rpartition("__REQ__")[0])
        except ValueError:
            continue
        params = request.get("params") or {}
        action = "list" if request.get("method") == "tools/list" else "call"
        tool = params.get("name") if action == "call" else None
        key = json.dumps([action, tool, params.get("arguments") or {}], sort_keys=True)
        kid = (params.get("_meta") or {}).get(IDEMPOTENCY_META)
        mcp.ops[ident] = {"server": name, "key": key, "tool": tool, "action": action, "published": True, "kid": kid}
    return d
