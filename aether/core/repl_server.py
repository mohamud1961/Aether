"""Persistent Python REPL server that runs INSIDE the task container (stdlib only, Python >= 3.6).

Design follows Prime Agent's RLM REPL (one persistent namespace; tools are
functions in it; data lives in variables, not in the prompt). Protocol is
file-based so it needs nothing but a shell on the host side:

  <base>/in/<seq>.py      cell source (renamed into place atomically by the host)
  <base>/out/<seq>.log    everything the cell writes (fd 1 and fd 2), appended live
  <base>/out/<seq>.done   JSON status, written last
  <base>/llm/<id>.req     JSON request from llm() inside a cell; the host answers with
  <base>/llm/<id>.resp    JSON {"text": ...} or {"error": ...}

SIGINT interrupts the running cell (KeyboardInterrupt), never the server.
This file is shipped to the container as data; it is not imported on the host.
"""
import ast
import json
import os
import shlex
import signal
import subprocess
import sys
import time
import traceback

BASE = sys.argv[1]
WORKDIR = sys.argv[2] if len(sys.argv) > 2 else "/"
for sub in ("in", "out", "llm"):
    os.makedirs(os.path.join(BASE, sub), exist_ok=True)


class ShResult(object):
    def __init__(self, code, output):
        self.code, self.output = code, output

    def __repr__(self):
        out = self.output if len(self.output) <= 4000 else self.output[:1500] + "\n...[%d chars]...\n" % (
            len(self.output) - 3500) + self.output[-2000:]
        return "[exit %d]\n%s" % (self.code, out)

    def __str__(self):
        return self.output


def sh(command, timeout=600, cwd=None):
    """Run a shell command; return ShResult(code, output) with stdout+stderr combined."""
    shell = "/bin/bash" if os.path.exists("/bin/bash") else "/bin/sh"
    try:
        p = subprocess.run([shell, "-c", command], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           timeout=timeout, cwd=cwd)
        return ShResult(p.returncode, p.stdout.decode("utf-8", "replace"))
    except subprocess.TimeoutExpired as exc:
        out = (exc.output or b"").decode("utf-8", "replace")
        return ShResult(124, out + "\n[timed out after %ss]" % timeout)


def read(path):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def read_bytes(path):
    with open(path, "rb") as fh:
        return fh.read()


def write(path, text):
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    mode = "wb" if isinstance(text, (bytes, bytearray)) else "w"
    with open(path, mode) as fh:
        fh.write(text)
    return "wrote %d to %s" % (len(text), path)


def edit(path, old, new, replace_all=False):
    text = read(path)
    n = text.count(old)
    if n == 0:
        raise ValueError("old text not found in %s" % path)
    if n > 1 and not replace_all:
        raise ValueError("old text occurs %d times in %s; make it unique or pass replace_all=True" % (n, path))
    write(path, text.replace(old, new) if replace_all else text.replace(old, new, 1))
    return "edited %s (%d replacement%s)" % (path, n if replace_all else 1, "s" if replace_all and n > 1 else "")


_llm_seq = [0]


def llm(prompt, max_tokens=4096, timeout=600):
    """Ask a sub-model (same model, no tools) and return its text. Use it to process large data
    held in variables without putting the data into your own context."""
    _llm_seq[0] += 1
    rid = "%d-%d" % (os.getpid(), _llm_seq[0])
    req, resp = os.path.join(BASE, "llm", rid + ".req"), os.path.join(BASE, "llm", rid + ".resp")
    tmp = req + ".tmp"
    with open(tmp, "w") as fh:
        json.dump({"prompt": str(prompt), "max_tokens": int(max_tokens)}, fh)
    os.rename(tmp, req)
    end = time.time() + timeout
    while time.time() < end:
        if os.path.exists(resp):
            with open(resp) as fh:
                data = json.load(fh)
            os.remove(resp)
            if "error" in data:
                raise RuntimeError("llm() failed: %s" % data["error"])
            return data["text"]
        time.sleep(0.1)
    raise TimeoutError("llm() got no answer in %ss" % timeout)


NS = {"__name__": "__main__", "sh": sh, "read": read, "read_bytes": read_bytes, "write": write, "edit": edit,
      "llm": llm, "shlex": shlex, "os": os, "json": json}
TOP_AWAIT = getattr(ast, "PyCF_ALLOW_TOP_LEVEL_AWAIT", 0)


def run_cell(source):
    tree = ast.parse(source, "<cell>", "exec")
    last = None
    if tree.body and isinstance(tree.body[-1], ast.Expr):
        last = ast.Expression(tree.body.pop().value)
    for node, mode in ((ast.Module(tree.body, []) if sys.version_info >= (3, 8) else ast.Module(tree.body),
                        "exec"), (last, "eval")):
        if node is None:
            continue
        code = compile(node, "<cell>", mode, flags=TOP_AWAIT)
        # Executing model-written code is this server's purpose; it runs only inside the task sandbox.
        value = eval(code, NS)
        if TOP_AWAIT and hasattr(value, "__await__"):
            import asyncio
            value = asyncio.get_event_loop().run_until_complete(value)
        if mode == "eval" and value is not None:
            NS["_"] = value
            print(repr(value))


def main():
    if os.path.isdir(WORKDIR):
        os.chdir(WORKDIR)
    signal.signal(signal.SIGINT, signal.default_int_handler)
    saved_out, saved_err = os.dup(1), os.dup(2)
    seq = 1
    while True:
        cell = os.path.join(BASE, "in", "%d.py" % seq)
        try:
            if not os.path.exists(cell):
                time.sleep(0.05)
                continue
        except KeyboardInterrupt:  # an interrupt with nothing running is ignored
            continue
        log = os.path.join(BASE, "out", "%d.log" % seq)
        status, started = "ok", time.time()
        fd = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
        os.dup2(fd, 1)
        os.dup2(fd, 2)
        sys.stdout = os.fdopen(os.dup(1), "w", buffering=1, encoding="utf-8", errors="replace")
        sys.stderr = sys.stdout
        try:
            run_cell(read(cell))
        except KeyboardInterrupt:
            status = "interrupted"
            print("KeyboardInterrupt")
        except BaseException:  # the model's error, shown to the model
            status = "error"
            traceback.print_exc()
        finally:
            try:
                sys.stdout.flush()
                sys.stdout.close()
            except Exception:
                pass
            os.dup2(saved_out, 1)
            os.dup2(saved_err, 2)
            os.close(fd)
            sys.stdout = os.fdopen(os.dup(1), "w", buffering=1)
            sys.stderr = sys.stdout
        done = os.path.join(BASE, "out", "%d.done" % seq)
        with open(done + ".tmp", "w") as fh:
            json.dump({"status": status, "seconds": round(time.time() - started, 2), "cwd": os.getcwd()}, fh)
        os.rename(done + ".tmp", done)
        seq += 1


if __name__ == "__main__":
    main()
