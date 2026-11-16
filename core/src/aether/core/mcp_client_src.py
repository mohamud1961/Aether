"""Source of the in-sandbox MCP client daemon (stdlib only); uploaded and run by ``mcp.py``.

One daemon per declared server holds the server session for the whole run, so stateful servers (a browser) keep
their state between calls. It speaks JSON-RPC over the declared transport (sse, streamable-http or stdio) and
exchanges requests with Core through files in its directory: Core writes ``req_<id>.json`` atomically, the daemon
writes ``resp_<id>.json``. ``ready`` holds the server's initialize result; ``error`` a startup failure.

Before sending a request the daemon takes its start token ``start_<id>`` (a symlink, "run"; see operations.py). Core
takes it as "revoked" when it lost a request's publication and must know for certain that it was never sent; the
daemon then never sends it. A sent request is waited on as long as the connection lives (up to ``ANSWER_CAP_S``), not
the model's wait, so a late answer is still written and Core can show it.
"""

SOURCE = r'''
import glob, json, os, select, subprocess, sys, threading, time, urllib.parse, urllib.request

D, KIND, TARGET = sys.argv[1], sys.argv[2], sys.argv[3:]
LOCK = threading.Condition()
GOT = {}
STATE = {"closed": False}
ANSWER_CAP_S = 3600


def write(name, value):
    tmp = os.path.join(D, name + ".tmp")
    with open(tmp, "w") as handle:
        json.dump(value, handle)
    os.replace(tmp, os.path.join(D, name))


def deliver(message):
    if isinstance(message, list):
        for item in message:
            deliver(item)
        return
    if isinstance(message, dict) and "id" in message and ("result" in message or "error" in message):
        with LOCK:
            GOT[message["id"]] = message
            LOCK.notify_all()


def events(stream):
    event, data = "message", []
    for raw in stream:
        line = raw.decode("utf-8", "replace").rstrip("\r\n")
        if not line:
            if data:
                yield event, "\n".join(data)
            event, data = "message", []
        elif line.startswith(":"):
            continue
        elif line.startswith("event:"):
            event = line[6:].strip()
        elif line.startswith("data:"):
            data.append(line[5:].lstrip())
    if data:
        yield event, "\n".join(data)


def closed():
    with LOCK:
        STATE["closed"] = True
        LOCK.notify_all()


class Sse:
    def __init__(self, url):
        self.endpoint = None
        found = threading.Event()
        stream = urllib.request.urlopen(urllib.request.Request(url, headers={"Accept": "text/event-stream"}))

        def read():
            try:
                for event, data in events(stream):
                    if event == "endpoint":
                        self.endpoint = urllib.parse.urljoin(url, data)
                        found.set()
                    elif event == "message":
                        try:
                            deliver(json.loads(data))
                        except ValueError:
                            pass
            finally:
                closed()

        threading.Thread(target=read, daemon=True).start()
        if not found.wait(30):
            raise RuntimeError("the server sent no endpoint event within 30 s")

    def send(self, message):
        request = urllib.request.Request(self.endpoint, data=json.dumps(message).encode(), method="POST",
                                         headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read()
        if body.strip().startswith((b"{", b"[")):
            deliver(json.loads(body))


class Http:
    def __init__(self, url):
        self.url, self.session = url, None

    def send(self, message):
        headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        if self.session:
            headers["Mcp-Session-Id"] = self.session
        request = urllib.request.Request(self.url, data=json.dumps(message).encode(), headers=headers, method="POST")
        with urllib.request.urlopen(request, timeout=600) as response:
            self.session = response.headers.get("Mcp-Session-Id") or self.session
            if "text/event-stream" in response.headers.get("Content-Type", ""):
                for _, data in events(response):
                    try:
                        reply = json.loads(data)
                    except ValueError:
                        continue
                    deliver(reply)
                    if isinstance(reply, dict) and reply.get("id") == message.get("id"):
                        break
            else:
                body = response.read()
                if body.strip():
                    deliver(json.loads(body))


class Stdio:
    def __init__(self, argv):
        self.proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=open(os.path.join(D, "server.stderr"), "ab"))

        def read():
            try:
                for line in self.proc.stdout:
                    try:
                        deliver(json.loads(line))
                    except ValueError:
                        pass
            finally:
                closed()

        threading.Thread(target=read, daemon=True).start()

    def send(self, message):
        self.proc.stdin.write((json.dumps(message) + "\n").encode())
        self.proc.stdin.flush()


def call(transport, ident, method, params, timeout):
    try:
        transport.send({"jsonrpc": "2.0", "id": ident, "method": method, "params": params})
    except Exception as exc:
        return {"id": ident, "error": {"message": "send failed: %s: %s" % (type(exc).__name__, exc)}}
    deadline = time.time() + timeout
    with LOCK:
        while ident not in GOT:
            left = deadline - time.time()
            if left <= 0 or STATE["closed"]:
                why = "the server connection closed" if STATE["closed"] else "no response within %g s" % timeout
                return {"id": ident, "error": {"message": why}}
            LOCK.wait(min(left, 1.0))
        return GOT.pop(ident)


def main():
    with open("/proc/self/stat") as stat:
        birth = stat.read().rsplit(")", 1)[1].split()[19]
    with open(os.path.join(D, "owner.tmp"), "w") as handle:
        handle.write("%d %s\n" % (os.getpid(), birth))
    os.replace(os.path.join(D, "owner.tmp"), os.path.join(D, "owner"))
    transport = None
    try:
        transport = {"sse": Sse, "streamable-http": Http}[KIND](TARGET[0]) if KIND != "stdio" else Stdio(TARGET)
        init = call(transport, 0, "initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                                                 "clientInfo": {"name": "aether-core", "version": "1"}}, 60)
        if "error" in init:
            raise RuntimeError(init["error"].get("message", "initialize failed"))
        transport.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
    except Exception as exc:
        if isinstance(transport, Stdio) and transport.proc.poll() is None:
            transport.proc.kill()
            transport.proc.wait()
        write("error", {"message": type(exc).__name__})
        return 1
    write("ready", init.get("result") or {})
    served = set()
    wake = None  # a publisher may write a byte to D/wake after publishing a request: a hint only, never authority
    try:
        if not os.path.exists(os.path.join(D, "wake")):
            os.mkfifo(os.path.join(D, "wake"), 0o600)
        wake = os.open(os.path.join(D, "wake"), os.O_RDWR | os.O_NONBLOCK)  # own writer end: no EOF busy loop
    except (OSError, AttributeError):
        wake = None
    while True:
        for path in sorted(glob.glob(os.path.join(D, "req_*.json"))):
            if path in served:
                continue
            served.add(path)
            ident = os.path.basename(path)[len("req_"):-len(".json")]
            try:
                os.symlink("run", os.path.join(D, "start_" + ident))
            except FileExistsError:
                continue  # Core cancelled it before the daemon took it: never sent
            with open(path) as handle:
                request = json.load(handle)

            def answer(request=request):
                reply = call(transport, request["id"], request["method"], request.get("params") or {}, ANSWER_CAP_S)
                write("resp_%s.json" % request["id"], reply)

            threading.Thread(target=answer, daemon=True).start()
        # Look again after 0.05 s, or at once when a publisher wrote to the wake pipe; the files stay the authority.
        if wake is None:
            time.sleep(0.05)
        elif select.select([wake], [], [], 0.05)[0]:
            try:
                os.read(wake, 65536)
            except OSError:
                pass


sys.exit(main())
'''
