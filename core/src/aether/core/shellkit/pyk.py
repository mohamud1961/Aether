"""``pyk``: one persistent Python process reachable from the shell (AETHER_CORE_SHELL_KIT).

``pyk 'code'`` or ``pyk <<'EOF' ... EOF`` runs code in a long-lived interpreter whose variables, imports and loaded
data survive between calls, like a notebook kernel, so a terminal command chain can reuse an expensive load. The
last expression's value is printed. ``pyk --reset`` ends the process (state is lost). The first call starts it.
One cell runs at a time; output is returned when the cell ends.
"""

import ast
import contextlib
import hashlib
import io
import json
import os
import signal
import socket
import subprocess
import sys
import time
import traceback

HOME = os.environ.get("AETHER_KIT_ROOT", "/tmp/.aether") + "/pyk"
SOCK, PID = f"{HOME}/sock", f"{HOME}/pid"
if len(SOCK) > 100:  # AF_UNIX paths are limited to ~104 bytes
    SOCK = f"/tmp/aether-pyk-{hashlib.sha256(HOME.encode()).hexdigest()[:12]}.sock"


def _recv(conn: socket.socket) -> bytes:
    parts = []
    while chunk := conn.recv(65536):
        parts.append(chunk)
    return b"".join(parts)


def _run(code: str, scope: dict) -> str:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        try:
            tree = ast.parse(code, "<pyk>")
            last = tree.body.pop() if tree.body and isinstance(tree.body[-1], ast.Expr) else None
            exec(compile(tree, "<pyk>", "exec"), scope)
            if last is not None:
                value = eval(compile(ast.Expression(last.value), "<pyk>", "eval"), scope)
                if value is not None:
                    print(repr(value))
        except SystemExit as exc:
            print(f"[SystemExit {exc.code}; the pyk process keeps running]")
        except BaseException:
            traceback.print_exc()
    return buf.getvalue()


def serve() -> None:
    os.makedirs(HOME, exist_ok=True)
    with contextlib.suppress(FileNotFoundError):
        os.unlink(SOCK)
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(SOCK)
    server.listen(4)
    with open(PID, "w") as f:
        f.write(str(os.getpid()))
    scope: dict = {"__name__": "__main__"}
    while True:
        conn, _ = server.accept()
        with conn:
            request = json.loads(_recv(conn))
            with contextlib.suppress(OSError):
                os.chdir(request["cwd"])
            conn.sendall(_run(request["code"], scope).encode())


def _connect() -> socket.socket | None:
    conn = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        conn.connect(SOCK)
        return conn
    except OSError:
        conn.close()
        return None


def main(argv: list[str]) -> int:
    if argv[1:] == ["--serve"]:
        serve()
        return 0
    if argv[1:] == ["--reset"]:
        with contextlib.suppress(OSError, ValueError):
            os.kill(int(open(PID).read()), signal.SIGTERM)
        for path in (SOCK, PID):
            with contextlib.suppress(FileNotFoundError):
                os.unlink(path)
        print("pyk: process ended; the next call starts a fresh one")
        return 0
    code = " ".join(argv[1:]) if len(argv) > 1 else sys.stdin.read()
    conn = _connect()
    if conn is None:
        os.makedirs(HOME, exist_ok=True)
        subprocess.Popen([sys.executable, os.path.abspath(__file__), "--serve"], stdin=subprocess.DEVNULL,
                         stdout=open(f"{HOME}/log", "a"), stderr=subprocess.STDOUT)
        for _ in range(100):
            time.sleep(0.05)
            if (conn := _connect()) is not None:
                break
        else:
            print(f"pyk: the python process did not start (see {HOME}/log)", file=sys.stderr)
            return 1
    with conn:
        conn.sendall(json.dumps({"code": code, "cwd": os.getcwd()}).encode())
        conn.shutdown(socket.SHUT_WR)
        out = _recv(conn).decode("utf-8", "replace")
    sys.stdout.write(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
