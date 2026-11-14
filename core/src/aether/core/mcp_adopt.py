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


def pointer(root: str, name: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", name)[:40] + "-" + hashlib.sha256(name.encode()).hexdigest()[:8]
    return f"{root}/current-{safe}"


def record_script(root: str, name: str, d: str) -> str:
    q, path = shlex.quote, pointer(root, name)
    return f"printf %s {q(d)} > {q(path + '.tmp')} && mv {q(path + '.tmp')} {q(path)}"


async def adopt(mcp, name: str) -> str | None:
    """The adopted session directory for server ``name`` (requests restored into ``mcp.ops``), or None."""
    q = shlex.quote
    got = await run(mcp.env, f"cat {q(pointer(mcp.root, name))} 2>/dev/null; true", timeout_s=10)
    d = got.stdout.strip()
    if not d.startswith(mcp.root + "/session-") or "\n" in d:
        return None
    state = await run(mcp.env, f"cd {q(d)} 2>/dev/null || exit 4; cat owner 2>/dev/null; echo __SEP__; "
                               "test -f ready && echo ready; echo __SEP__; ls", timeout_s=10)
    owner, ready, listing = (state.stdout.split("__SEP__\n") + ["", "", ""])[:3]
    fields = owner.split()
    if state.code != 0 or ready.strip() != "ready" or len(fields) != 2 or not fields[0].isdecimal():
        return None
    pid = int(fields[0])
    now = await run(mcp.env, f"{alive_test(pid)} && {{ {_BIRTH.format(pid=pid)}; }} || echo __DEAD__", timeout_s=10)
    if now.stdout.strip() != fields[1]:
        return None
    sent = sorted(int(m.group(1)) for m in re.finditer(r"^req_(\d+)\.json$", listing, re.M))
    staged = sorted(int(m.group(1)) for m in re.finditer(r"^req\.tmp\.(\d+)$", listing, re.M))
    mcp.seq = max([mcp.seq, *sent, *staged])
    for ident in staged:
        if ident not in sent:
            await run(mcp.env, f"cd {q(d)} && ln -s {operations.REVOKED} start_{ident} 2>/dev/null; true", timeout_s=10)
    for ident in sent:
        records = await run(mcp.env, operations.resolve_script(d, ident, revoke=False), timeout_s=10)
        parsed = operations.parse(records.stdout)
        if parsed is None or operations.seen(parsed[2], mcp.conversation):
            continue
        body = await run(mcp.env, f"cat {q(f'{d}/req_{ident}.json')}", timeout_s=10)
        try:
            request = json.loads(body.stdout)
        except ValueError:
            continue
        params = request.get("params") or {}
        action = "list" if request.get("method") == "tools/list" else "call"
        tool = params.get("name") if action == "call" else None
        key = json.dumps([action, tool, params.get("arguments") or {}], sort_keys=True)
        mcp.ops[ident] = {"server": name, "key": key, "tool": tool, "action": action, "published": True}
    return d
