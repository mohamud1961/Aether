"""In-sandbox library for the Python-only interface (B18, toolset "python"); uploaded as ``lib.py`` next to the REPL
server, which executes it into the cell namespace (stdlib only, Python >= 3.6).

- ``bash(cmd)`` starts a shell command in the background and returns a handle at once. A command that ends without
  the model having looked at it is reported once at the next cell boundary (no model turn is ever started for it).
- ``mcp(server, tool, **arguments)`` calls a task-declared MCP server through the same in-sandbox client daemon the
  ``mcp`` tool uses (mcp_client_src): the request and response files stay in the sandbox, so a script's nested calls
  cost no host round trip each. Only the first use of a server asks the host to start its client.

Each MCP request id is unique per REPL process ("py<pid>_<n>"); its request and response files stay in the client's
directory as receipts. A request the client never took (no start token) is reported as never sent; one it took but
did not answer is reported as of unknown effect, never retried here.
"""

SOURCE = r'''
import asyncio as _asyncio
import json as _json
import os as _os
import signal as _signal
import subprocess as _subprocess
import threading as _threading
import time as _time

_BASH_DIR = _os.path.join(_AETHER_BASE, "bash")
_HANDLES = []
_SHELL = "/bin/bash" if _os.path.exists("/bin/bash") else "/bin/sh"


def _bounded(text, limit=4000):
    if len(text) <= limit:
        return text
    return text[:1500] + "\n...[%d chars]...\n" % (len(text) - 3500) + text[-2000:]


class BashHandle(object):
    """A background shell command. ``code`` is None while it runs."""

    def __init__(self, cmd, timeout, cwd):
        if not _os.path.isdir(_BASH_DIR):
            _os.makedirs(_BASH_DIR)
        self.id = len(_HANDLES) + 1
        self.cmd = cmd
        self.log = _os.path.join(_BASH_DIR, "%d.log" % self.id)
        self.timed_out = False
        self._seen = self._noticed = False
        self._ended = None
        with open(self.log, "wb") as out:
            self._proc = _subprocess.Popen([_SHELL, "-c", cmd], stdout=out, stderr=_subprocess.STDOUT,
                                           stdin=_subprocess.DEVNULL, cwd=cwd, start_new_session=True)
        self.started = _time.time()
        self._timer = _threading.Timer(timeout, self._expire)
        self._timer.daemon = True
        self._timer.start()

    def _expire(self):
        if self._proc.poll() is None:
            self.timed_out = True
            self.kill()

    @property
    def code(self):
        rc = self._proc.poll()
        if rc is not None and self._ended is None:
            self._ended = _time.time()
            self._timer.cancel()
        return rc

    def poll(self):
        return self.code

    def wait(self, timeout=None):
        """Block until the command ends (or ``timeout`` seconds pass); returns the handle."""
        try:
            self._proc.wait(timeout)
        except _subprocess.TimeoutExpired:
            return self
        self.code
        self._seen = True
        return self

    def __await__(self):
        yield from _asyncio.get_event_loop().run_in_executor(None, self._proc.wait).__await__()
        self.code
        self._seen = True
        return self

    def output(self):
        """The whole output so far (stdout and stderr together)."""
        if self.code is not None:
            self._seen = True
        with open(self.log, "rb") as fh:
            return fh.read().decode("utf-8", "replace")

    def tail(self, n=2000):
        with open(self.log, "rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            fh.seek(max(0, size - int(n)))
            return fh.read().decode("utf-8", "replace")

    def kill(self):
        """Stop the command and everything it started (TERM, then KILL after 2 s)."""
        for sig, grace in ((_signal.SIGTERM, 2.0), (_signal.SIGKILL, 2.0)):
            try:
                _os.killpg(self._proc.pid, sig)
            except OSError:
                break
            try:
                self._proc.wait(grace)
                break
            except _subprocess.TimeoutExpired:
                continue
        return self

    def _state(self):
        rc = self.code
        if rc is None:
            return "running %.0fs" % (_time.time() - self.started)
        why = " (timed out, killed)" if self.timed_out else ""
        return "exit %d%s after %.1fs" % (rc, why, self._ended - self.started)

    def __repr__(self):
        if self.code is None:
            return "[bash #%d %s: %s]" % (self.id, self._state(), self.cmd[:200])
        return "[bash #%d %s]\n%s" % (self.id, self._state(), _bounded(self.output()))


def bash(cmd, timeout=600, cwd=None):
    """Start ``cmd`` in the background; returns a BashHandle at once."""
    handle = BashHandle(cmd, timeout, cwd)
    _HANDLES.append(handle)
    return handle


def _aether_notices():
    for handle in _HANDLES:
        if handle.code is not None and not handle._seen and not handle._noticed:
            handle._noticed = True
            print("[bash #%d finished: %s: %s]" % (handle.id, handle._state(), handle.cmd[:200]))


class McpError(Exception):
    pass


_MCP_DIRS = {}
_MCP_SEQ = [0]
_HOST_SEQ = [0]


def _host(request, timeout=120):
    """A request the host answers (the llm() channel): returns its text or raises."""
    _HOST_SEQ[0] += 1
    rid = "h%d-%d" % (_os.getpid(), _HOST_SEQ[0])
    req = _os.path.join(_AETHER_BASE, "llm", rid + ".req")
    resp = _os.path.join(_AETHER_BASE, "llm", rid + ".resp")
    with open(req + ".tmp", "w") as fh:
        _json.dump(request, fh)
    _os.rename(req + ".tmp", req)
    end = _time.time() + timeout
    while _time.time() < end:
        if _os.path.exists(resp):
            with open(resp) as fh:
                data = _json.load(fh)
            _os.remove(resp)
            if "error" in data:
                raise McpError(data["error"])
            return data["text"]
        _time.sleep(0.02)
    raise McpError("the host did not answer within %gs" % timeout)


def _client(server):
    if server not in _MCP_DIRS:
        _MCP_DIRS[server] = _host({"kind": "mcp_start", "server": str(server)})
    return _MCP_DIRS[server]


def _publish(d, method, params):
    _MCP_SEQ[0] += 1
    ident = "py%d_%06d" % (_os.getpid(), _MCP_SEQ[0])  # zero-padded: the client takes requests in name order
    tmp = _os.path.join(d, "req.tmp." + ident)
    with open(tmp, "w") as fh:
        _json.dump({"id": ident, "method": method, "params": params}, fh)
    _os.rename(tmp, _os.path.join(d, "req_%s.json" % ident))
    _wake(d)
    return ident


_WAKE = {}


def _wake(d):
    """Nudge the client to look now (it looks every 0.05 s anyway); a missing or full pipe changes nothing."""
    try:
        fd = _WAKE.get(d)
        if fd is None:
            fd = _WAKE[d] = _os.open(_os.path.join(d, "wake"), _os.O_WRONLY | _os.O_NONBLOCK)
        _os.write(fd, b"x")
    except BlockingIOError:
        pass  # pipe full: the client has unread wakes already
    except OSError:
        fd = _WAKE.pop(d, None)
        if fd is not None:
            try:
                _os.close(fd)
            except OSError:
                pass


def _alive(d):
    try:
        with open(_os.path.join(d, "owner")) as fh:
            pid = int(fh.read().split()[0])
        _os.kill(pid, 0)
        return True
    except (OSError, ValueError, IndexError):
        return False


def _collect(d, ident, timeout):
    path = _os.path.join(d, "resp_%s.json" % ident)
    end, delay, checked = _time.time() + timeout, 0.001, _time.time()
    while True:
        try:
            with open(path) as fh:
                text = fh.read()
        except OSError:
            text = ""
        if text.strip():
            return _json.loads(text)
        now = _time.time()
        if now - checked > 1.0:
            checked = now
            if not _alive(d):
                taken = _os.path.lexists(_os.path.join(d, "start_" + ident))
                raise McpError("MCP request %s: the client exited %s" % (
                    ident, "after taking it; its effect is unknown" if taken else "before taking it; it was never sent"))
        if now > end:
            raise McpError("MCP request %s: no reply within %gs; its effect is unknown (not retried)" % (ident, timeout))
        _time.sleep(delay)
        delay = min(delay * 2, 0.02)


def _value(reply, label):
    if "error" in reply:
        raise McpError("%s: %s" % (label, (reply["error"] or {}).get("message", reply["error"])))
    result = reply.get("result") or {}
    if "tools" in result:
        return result["tools"]
    text = "\n".join(c.get("text", "") for c in result.get("content") or [] if c.get("type") == "text")
    if result.get("isError"):
        raise McpError("%s: %s" % (label, text))
    return result["structuredContent"] if "structuredContent" in result else text


def mcp(server, tool=None, arguments=None, timeout=120, **keywords):
    """Call ``tool`` on a declared MCP server with ``arguments`` (a dict) and/or keywords; with no tool, list its
    tools."""
    d = _client(server)
    if tool is None:
        return _value(_collect(d, _publish(d, "tools/list", {}), timeout), "tools/list")
    args = dict(arguments or {})
    args.update(keywords)
    ident = _publish(d, "tools/call", {"name": tool, "arguments": args})
    return _value(_collect(d, ident, timeout), tool)


def mcp_many(server, calls, timeout=120):
    """Send several (tool, arguments) calls at once; returns their results in order, an McpError in place of a failed
    one (the others are kept)."""
    d = _client(server)
    idents = [(_publish(d, "tools/call", {"name": tool, "arguments": dict(args)}), tool) for tool, args in calls]
    out = []
    for ident, tool in idents:
        try:
            out.append(_value(_collect(d, ident, timeout), tool))
        except McpError as exc:
            out.append(exc)
    return out
'''
