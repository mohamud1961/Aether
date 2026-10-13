"""Host side of the persistent Python REPL (see ``repl_server`` for the in-container half).

Prime Agent's RLM idea on a Harbor sandbox: one persistent Python namespace in
the task container, with ``sh``/``read``/``write``/``edit``/``llm`` as functions
in it, so the model can hold and process data in variables instead of pulling
it into its context. ``llm()`` requests are answered here, on the host, so no
credential ever enters the container.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path
import shlex
import time
from typing import Awaitable, Callable

from .env import CONTROL_DIR, INLINE_BYTES, Environment, put_bytes, run
from .terminal import MAX_WAIT_S

SERVER_SOURCE = (Path(__file__).with_name("repl_server.py")).read_bytes()
VIEW_HEAD, VIEW_TAIL = 3_000, 8_000
POLL_SLICE_S = 5.0
MAX_LLM_CALLS = 40
MAX_LLM_PROMPT_CHARS = 100_000  # ~30k tokens: llm() shares the route's tokens-per-minute limit
LlmAnswer = Callable[[str, int], Awaitable[str]]


class Repl:
    def __init__(self, env: Environment, workdir: str, remaining: Callable[[], float],
                 llm_answer: LlmAnswer | None, base: str = f"{CONTROL_DIR}/repl") -> None:
        self._env, self._workdir, self._remaining, self._llm = env, workdir, remaining, llm_answer
        self.base = base
        self.pid = 0
        self.seq = 0
        self.pending = 0
        self.cursor = 0
        self.python = ""
        self.llm_calls = 0
        self.llm_errors = 0

    async def start(self) -> str:
        """Launch the server. Returns the Python version, or "" when the container has no usable Python."""
        q = shlex.quote
        res = await run(self._env, "command -v python3 >/dev/null 2>&1 && python3 -c "
                                   "'import sys; print(\"%d.%d\" % sys.version_info[:2]) if sys.version_info >= (3, 6) "
                                   "else None'")
        version = res.stdout.strip()
        if res.code != 0 or not version:
            return ""
        await put_bytes(self._env, SERVER_SOURCE, f"{self.base}/server.py")
        launch = (f"cd {q(self.base)} && rm -rf in out llm && mkdir -p in out llm && "
                  f"if command -v setsid >/dev/null 2>&1; then S=setsid; else S=; fi; "
                  f"nohup $S python3 -u server.py {q(self.base)} {q(self._workdir)} > server.log 2>&1 < /dev/null & "
                  f"echo $!")
        res = await run(self._env, launch)
        pid = res.stdout.strip().split()[-1:] or [""]
        if res.code != 0 or not pid[0].isdigit():
            raise RuntimeError(f"python REPL launch failed: {(res.stderr or res.stdout).strip()[:300]}")
        self.pid, self.python = int(pid[0]), version
        return version

    async def close(self) -> None:
        """Stop the kernel process (it dies with the container anyway; outside one it would linger)."""
        if self.pid:
            await run(self._env, f"kill -TERM {self.pid} 2>/dev/null; true")
            self.pid = 0

    async def run(self, code: str = "", *, wait_s: float = 60.0, interrupt: bool = False) -> str:
        if not self.pid and self.python and code:  # it died earlier: a fresh interpreter, and the model is told
            await self.start()
            self.pending = 0
            return "[python REPL restarted; variables from before are gone]\n" + await self.run(code, wait_s=wait_s)
        if not self.pid:
            raise RuntimeError("the python tool is not available in this environment")
        q = shlex.quote
        started = time.monotonic()
        if interrupt and self.pending:
            await run(self._env, f"kill -INT {self.pid} 2>/dev/null; true")
        submit = ""
        if code:
            if self.pending:
                return ("[python] a cell is still running; call python with empty code to keep waiting, or "
                        "interrupt=true to stop it")
            self.seq += 1
            self.pending, self.cursor = self.seq, 0
            tmp, cell = q(f"{self.base}/in/{self.seq}.tmp"), q(f"{self.base}/in/{self.seq}.py")
            data = code.encode()
            if len(data) <= INLINE_BYTES:  # submit, wait and read in one container call
                submit = f"printf %s {base64.b64encode(data).decode()} | base64 -d > {tmp} && mv {tmp} {cell}; "
            else:
                await put_bytes(self._env, data, f"{self.base}/in/{self.seq}.tmp")
                submit = f"mv {tmp} {cell}; "
        if not self.pending:
            return "[python] nothing is running"
        seq = self.pending
        wait_s = max(0.0, min(float(wait_s), MAX_WAIT_S, self._remaining() - 5))
        while True:
            left = wait_s - (time.monotonic() - started)
            done, requests, alive, size, text = await self._poll(seq, min(POLL_SLICE_S, max(0.2, left)), submit)
            submit = ""
            for rid in requests:
                await self._answer(rid)
            if done is not None or not alive or (time.monotonic() - started >= wait_s and not requests):
                break
        if size - self.cursor > VIEW_HEAD + VIEW_TAIL:
            text = await self._read(seq, self.cursor, size)
        self.cursor = size
        elapsed = time.monotonic() - started
        if done is not None:
            self.pending = 0
            status = f"[python cell {seq}: {done.get('status')} · {done.get('seconds')}s]"
        elif not alive:
            self.pending, self.pid = 0, 0
            status = "[python REPL exited; its state is lost. The next python call starts a fresh one]"
        else:
            status = (f"[python cell {seq} still running after {elapsed:.0f}s; call python with empty code to keep "
                      "waiting, or interrupt=true to stop it]")
        return (text.rstrip("\n") + "\n" if text.strip() else "(no output)\n") + status

    async def _poll(self, seq: int, slice_s: float, submit: str = "") -> tuple[dict | None, list[str], bool, int, str]:
        """One container call: (submit,) wait up to ``slice_s`` for completion or an llm() request, then report
        status, pending llm() requests, liveness, log size and new output (when small)."""
        q = shlex.quote
        done, llm, log = f"{self.base}/out/{seq}.done", f"{self.base}/llm", f"{self.base}/out/{seq}.log"
        loops = max(1, int(slice_s / 0.05))
        cmd = (f"{submit}i=0; while [ $i -lt {loops} ]; do [ -f {q(done)} ] && break; "
               f"ls {q(llm)}/*.req >/dev/null 2>&1 && break; sleep 0.05; i=$((i+1)); done; "
               f"echo __REQ__; ls {q(llm)} 2>/dev/null | grep '\\.req$'; echo __DONE__; cat {q(done)} 2>/dev/null; "
               f"echo; echo __ALIVE__; kill -0 {self.pid} 2>/dev/null && echo yes || echo no; echo __SIZE__; "
               f"wc -c < {q(log)} 2>/dev/null || echo 0; echo __LOG__; "
               f"tail -c +{self.cursor + 1} {q(log)} 2>/dev/null | head -c {VIEW_HEAD + VIEW_TAIL}")
        res = await run(self._env, cmd, timeout_s=int(slice_s) + 30)
        out = res.stdout

        def part(name: str, nxt: str | None) -> str:
            body = out.split(f"__{name}__\n", 1)[-1] if f"__{name}__" in out else ""
            return body.split(f"__{nxt}__", 1)[0] if nxt else body
        reqs = part("REQ", "DONE").split()
        done_raw = part("DONE", "ALIVE").strip()
        status = None
        if done_raw:
            try:
                status = json.loads(done_raw)
            except ValueError:
                status = None
        try:
            size = int(part("SIZE", "LOG").strip() or 0)
        except ValueError:
            size = 0
        return (status, [r[:-4] for r in reqs if r.endswith(".req")], part("ALIVE", "SIZE").strip() == "yes",
                size, part("LOG", None))

    async def _answer(self, rid: str) -> None:
        q = shlex.quote
        req, resp = f"{self.base}/llm/{rid}.req", f"{self.base}/llm/{rid}.resp"
        raw = await run(self._env, f"cat {q(req)} && rm -f {q(req)}")
        try:
            data = json.loads(raw.stdout)
            prompt, max_tokens = str(data["prompt"]), int(data.get("max_tokens") or 4096)
            if self._llm is None:
                raise RuntimeError("llm() is not enabled in this run")
            if self.llm_calls >= MAX_LLM_CALLS:
                raise RuntimeError(f"llm() call budget of {MAX_LLM_CALLS} is used up")
            if len(prompt) > MAX_LLM_PROMPT_CHARS:
                raise RuntimeError(f"prompt is {len(prompt)} chars; the limit is {MAX_LLM_PROMPT_CHARS}")
            self.llm_calls += 1
            answer = {"text": await self._llm(prompt, max(256, min(max_tokens, 16_384)))}
        except Exception as exc:  # returned to the cell as an exception, never swallowed
            self.llm_errors += 1
            answer = {"error": f"{type(exc).__name__}: {str(exc)[:300]}"}
        await put_bytes(self._env, json.dumps(answer).encode(), resp + ".tmp")
        await run(self._env, f"mv {q(resp + '.tmp')} {q(resp)}")

    async def _read(self, seq: int, start: int, end: int) -> str:
        log = shlex.quote(f"{self.base}/out/{seq}.log")
        n = end - start
        if n <= 0:
            return ""
        if n <= VIEW_HEAD + VIEW_TAIL:
            return (await run(self._env, f"tail -c +{start + 1} {log} | head -c {n}")).stdout
        res = await run(self._env, f"tail -c +{start + 1} {log} | head -c {VIEW_HEAD}; printf '\\n\\x00SPLIT\\x00\\n'; "
                                   f"tail -c +{start + 1} {log} | head -c {n} | tail -c {VIEW_TAIL}")
        head, _, tail = res.stdout.partition("\n\x00SPLIT\x00\n")
        return (f"{head}\n…[{n - VIEW_HEAD - VIEW_TAIL} bytes omitted; the full output is in "
                f"{self.base}/out/{seq}.log]…\n{tail}")


def sub_llm(provider, remaining: Callable[[], float], usage: dict[str, int]) -> LlmAnswer:
    """``llm()`` answers: same model, plain text, no tools. Token usage is added to ``usage``."""
    async def answer(prompt: str, max_tokens: int) -> str:
        turn = await provider.complete([{"role": "user", "content": prompt}], None, max_tokens=max_tokens,
                                       remaining_s=remaining, role="llm")
        for key, value in turn.usage.items():
            usage[key] = usage.get(key, 0) + value
        return turn.content
    return answer
