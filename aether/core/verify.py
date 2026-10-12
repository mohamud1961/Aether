"""Finish verification against the real state, in a disposable clone of the task container.

When the worker calls finish, the harness commits the task container to an image and starts a throwaway
container from it. A verifier agent (the same model, its own context) is given only the task statement and the
files changed during the run -- never the worker's reasoning, summary or claims -- and checks each requirement
itself. It may build, run, test and modify anything: nothing it does reaches the state that is graded.

A commit copies files, not processes, so servers the worker left running are absent from the clone. The
verifier can check those with ``live_probe``: allowlisted read-only commands (ps, ss, curl GET, ls, cat ...)
in the original container. The clone has no network (it must not escape the task's egress policy), a memory,
CPU and process limit, and no privilege escalation.

The finish is held only for a requirement the verifier observed failing (``not_met`` with the command and its
output); the worker gets that evidence verbatim, so it can reproduce it. A clone or verifier failure is recorded
as status "error" and the finish proceeds: substrate failures are reported, never hidden or turned into holds.

D1 evidence for the change: the transcript-reading finish review caught 0 of 3 confidently wrong finishes and
held 2 correct ones; 13 of its 17 progress holds only said "incomplete".
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import json
import re
import shlex
import time
from types import SimpleNamespace
from typing import Any, Awaitable, Callable
import uuid

from .env import CONTROL_DIR, Environment, run
from .files import Files
from .provider import ChatProvider
from .terminal import Terminals
from .tools import READ_FILE, TERMINAL

VERIFY_MAX_S = 420.0
VERIFY_MIN_S = 120.0
MAX_TURNS = 40
MAX_RESULT_CHARS = 6_000
MAX_OBSERVED_CHARS = 1_200
CHANGED_LIMIT = 80
VERIFY_CONTROL_DIR = "/tmp/.aether-verify"
CLONE_MEMORY = "8g"
CLONE_CPUS = "2"

HostRun = Callable[[list[str], float], Awaitable[tuple[int, str, str]]]


async def host_run(argv: list[str], timeout_s: float) -> tuple[int, str, str]:
    """Run a host command (the docker CLI) without a shell."""
    proc = await asyncio.create_subprocess_exec(*argv, stdin=asyncio.subprocess.DEVNULL,
                                                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return 124, "", f"timed out after {timeout_s:.0f}s"
    return proc.returncode or 0, out.decode(errors="replace"), err.decode(errors="replace")


class CloneError(RuntimeError):
    pass


class Clone:
    """A throwaway container started from a commit of the task container (Harbor-environment interface)."""

    def __init__(self, name: str, image: str, host: HostRun, owns_image: bool = True) -> None:
        self.name, self.image, self._host, self._owns_image = name, image, host, owns_image

    @staticmethod
    def _run_args(name: str, image: str) -> list[str]:
        # No network: the clone must not escape the task's egress policy (live_probe covers live services).
        return ["docker", "run", "-d", "--rm", "--name", name, "--network", "none", "--security-opt",
                "no-new-privileges", "--pids-limit", "4096", "--memory", CLONE_MEMORY, "--cpus", CLONE_CPUS,
                "--entrypoint", "sh", image, "-c", "while :; do sleep 3600; done"]

    @classmethod
    async def create(cls, env: Environment, host: HostRun = host_run) -> "Clone":
        # The container's own hostname file is bind-mounted from /var/lib/docker/containers/<id>/, which names it
        # even when a compose file sets a custom hostname; the hostname itself is the fallback.
        res = await run(env, "grep -o 'containers/[0-9a-f]\\{64\\}' /proc/self/mountinfo 2>/dev/null | head -n 1 "
                             "| cut -d/ -f2; cat /etc/hostname 2>/dev/null || hostname")
        cid = (res.stdout.split() or [""])[0]
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", cid):
            raise CloneError(f"cannot identify the task container (hostname {cid!r})")
        tag = f"aether-verify:{uuid.uuid4().hex[:12]}"
        code, _, err = await host(["docker", "commit", cid, tag], 900)
        if code != 0:
            raise CloneError(f"docker commit failed: {err.strip()[:300]}")
        name = tag.replace(":", "-")
        code, _, err = await host(cls._run_args(name, tag), 180)
        if code != 0:
            await host(["docker", "rmi", "-f", tag], 120)
            raise CloneError(f"docker run of the clone failed: {err.strip()[:300]}")
        return cls(name, tag, host)

    async def exec(self, command: str, cwd: str | None = None, env: dict | None = None,
                   timeout_sec: int | None = None) -> Any:
        argv = ["docker", "exec", *(["-w", cwd] if cwd else []), self.name, "sh", "-c", command]
        code, out, err = await self._host(argv, float(timeout_sec or 60))
        return SimpleNamespace(return_code=code, stdout=out, stderr=err)

    async def upload_file(self, source_path: Any, target_path: str) -> None:
        code, _, err = await self._host(["docker", "cp", str(source_path), f"{self.name}:{target_path}"], 120)
        if code != 0:
            raise OSError(f"docker cp into the clone failed: {err.strip()[:200]}")

    async def download_file(self, source_path: str, target_path: Any) -> None:
        code, _, err = await self._host(["docker", "cp", f"{self.name}:{source_path}", str(target_path)], 120)
        if code != 0:
            raise OSError(f"docker cp from the clone failed: {err.strip()[:200]}")

    async def sibling(self) -> "Clone":
        """Another throwaway container from the same commit (the image stays owned by this clone)."""
        name = f"{self.name}-{uuid.uuid4().hex[:6]}"
        code, _, err = await self._host(self._run_args(name, self.image), 180)
        if code != 0:
            raise CloneError(f"docker run of a sibling clone failed: {err.strip()[:300]}")
        return Clone(name, self.image, self._host, owns_image=False)

    async def close(self) -> None:
        await self._host(["docker", "rm", "-f", self.name], 120)
        if self._owns_image:
            await self._host(["docker", "rmi", "-f", self.image], 300)


# ----- read-only probes of the live container --------------------------------------------------------
_PROBE_COMMANDS = {"ps", "pgrep", "ss", "netstat", "curl", "ls", "cat", "head", "tail", "stat", "wc", "file",
                   "sha256sum", "md5sum", "grep", "find", "du", "df", "id", "uname", "test", "readlink"}
# Options are allowlisted where a command has state-changing or file-writing ones (a denylist leaks: curl alone
# writes files with -o -O -D -c --trace --libcurl --etag-save --hsts ...). Values follow their option.
_CURL_FLAGS = {"-s", "--silent", "-S", "--show-error", "-I", "--head", "-i", "--include", "-L", "--location", "-v",
               "--verbose", "-f", "--fail", "-k", "--insecure", "-G", "--get", "-4", "-6", "--compressed"}
_CURL_VALUED = {"-m", "--max-time", "--connect-timeout", "-H", "--header", "-A", "--user-agent", "-w",
                "--write-out", "-r", "--range"}
# Denied options of the other commands. Long options are refused by any prefix (GNU accepts unambiguous
# abbreviations: --fol is --follow) and short ones anywhere in a cluster (-5f, -tK, -bc).
_DENY = {"ss": ("-K", "--kill", "-D", "--diag", "-F", "--filter"), "file": ("-C", "--compile", "-m", "--magic-file"),
         "find": ("-delete", "-exec", "-execdir", "-ok", "-okdir", "-fprint", "-fprint0", "-fprintf", "-fls"),
         "tail": ("-f", "-F", "--follow"), "sha256sum": ("-c", "--check"), "md5sum": ("-c", "--check"),
         "netstat": ("-c", "--continuous")}


def _curl_refusal(args: list[str]) -> str | None:
    i = 0
    while i < len(args):
        a = args[i]
        if a in _CURL_VALUED:
            value = args[i + 1] if i + 1 < len(args) else ""
            # -w %output{file} (curl >= 8.3) and -w @file write or read files
            if a in ("-w", "--write-out") and (value.startswith("@") or "output" in value.lower()):
                return "curl -w may only format to stdout (no @file, no %output{})"
            i += 2
            continue
        if a.startswith("-") and a not in _CURL_FLAGS:
            if re.fullmatch(r"-[sSIiLvfkG46]+", a):  # a cluster of allowed short flags, e.g. -sSL
                i += 1
                continue
            return f"curl option {a} is not allowed (GET-only probes: {' '.join(sorted(_CURL_FLAGS))}, " \
                   f"{' '.join(sorted(_CURL_VALUED))} VALUE)"
        if not a.startswith("-") and not re.match(r"https?://", a):
            return "curl takes http(s) URLs only"
        i += 1
    return None


def _denied(arg: str, deny: tuple[str, ...]) -> bool:
    for d in deny:
        if d.startswith("--"):
            name = arg.split("=", 1)[0]
            if len(name) > 2 and d.startswith(name):
                return True
        elif len(d) == 2:
            if arg.startswith("-") and not arg.startswith("--") and d[1] in arg[1:]:
                return True
        elif arg == d:  # find's single-dash primaries
            return True
    return False


def probe_command(command: str) -> tuple[str | None, str | None]:
    """(shell command to run, None) for an allowed read-only probe, else (None, why it is refused).

    The command run is re-quoted from the checked argv, so the shell sees exactly the tokens that were checked:
    no globbing, tilde or comment handling can turn into options the check never saw. curl gets -q first so a
    planted .curlrc cannot add options."""
    if re.search(r"[;&|`$<>\n\\]", command):
        return None, "one plain command only: no ; & | ` $ < > or backslashes"
    try:
        argv = shlex.split(command)
    except ValueError as exc:
        return None, f"cannot parse: {exc}"
    if not argv or argv[0] not in _PROBE_COMMANDS:
        return None, f"allowed commands: {', '.join(sorted(_PROBE_COMMANDS))}"
    if argv[0] == "curl":
        refusal = _curl_refusal(argv[1:])
        return (None, refusal) if refusal else (shlex.join(["curl", "-q", *argv[1:]]), None)
    deny = _DENY.get(argv[0], ())
    for a in argv[1:]:  # no stop at "--": find primaries such as -delete still apply after it
        if _denied(a, deny):
            return None, f"{argv[0]} option {a} can change state or block"
    return shlex.join(argv), None


def probe_refusal(command: str) -> str | None:
    """None if ``command`` is an allowed read-only probe, else why it is refused."""
    return probe_command(command)[1]


LIVE_PROBE = {"type": "function", "function": {
    "name": "live_probe",
    "description": "Run one read-only command in the ORIGINAL container (where the worker's processes are still "
                   "running): ps, pgrep, ss, netstat, curl (GET only), ls, cat, head, tail, stat, wc, file, "
                   "sha256sum, md5sum, grep, find (no -exec/-delete), du, df, id, uname, test, readlink.",
    "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}}
VERDICT = {"type": "function", "function": {
    "name": "verdict",
    "description": "Report your verification and stop. One entry per requirement of the task.",
    "parameters": {"type": "object", "properties": {"requirements": {"type": "array", "items": {
        "type": "object", "properties": {
            "requirement": {"type": "string"},
            "status": {"type": "string", "enum": ["met", "not_met", "unchecked"]},
            "command": {"type": "string", "description": "The check you ran."},
            "observed": {"type": "string", "description": "What it showed (the relevant output)."},
        }, "required": ["requirement", "status", "command", "observed"]}}},
        "required": ["requirements"]}}}

PROMPT = """You verify whether a task has been completed. Another agent worked on it in a Linux container and \
says it is done. You are given the task and the files changed during its work, nothing it said or thought. \
Decide from the real state.

You work in a disposable copy of that container, taken just now. Build, run, test or modify anything; nothing \
you do reaches the original. Processes do not carry over to the copy: anything the worker left running \
(servers, daemons) is not running here. Check those with live_probe, which runs read-only commands in the \
original container.

Method: list the task's requirements in the task's own words, including every stated constraint, rule and \
convention (lengths, formats, orderings, which column means what, tie-breaking rules). Check each the way the \
task will be judged: run the real program, look at its real output, decode produced files and measure them \
against what the task asks. Where the task gives a rule, apply it yourself to every case it covers and compare \
with the output item by item. Write your own checks; do not rely on tests, logs or notes the worker left behind.

Your job is to judge the state, not to finish the task. Once you have observed a requirement failing, record \
it; you do not need to find the correct result. You have about {budget}s; be efficient.

Finish with verdict: one entry per requirement with status met, not_met or unchecked, the command you ran and \
the output you observed. met means the result satisfies the requirement as the task states it. A result that \
violates a stated constraint is not_met, even if you believe no better result exists. If you could not check a \
requirement (for example it needs a process that is not running in the copy and live_probe cannot reach it), \
use unchecked."""


@dataclass
class Verification:
    status: str  # "pass" | "hold" | "error"
    requirements: list[dict[str, str]] = field(default_factory=list)
    error: str = ""
    turns: int = 0
    clone_s: float = 0.0
    usage: dict[str, int] = field(default_factory=dict)

    @property
    def failed(self) -> list[dict[str, str]]:
        return [r for r in self.requirements if r.get("status") == "not_met"]

    def feedback(self) -> str:
        lines = ["[verification] An independent verifier checked the real state in a copy of this machine (it "
                 "saw the task, not your messages). These requirements failed its checks:"]
        for r in self.failed:
            lines += [f"- {r.get('requirement', '')}", f"  ran: {r.get('command', '')}",
                      f"  observed: {str(r.get('observed', ''))[:MAX_OBSERVED_CHARS]}"]
        unchecked = [r.get("requirement", "") for r in self.requirements if r.get("status") == "unchecked"]
        if unchecked:
            lines.append("It could not check: " + "; ".join(u[:200] for u in unchecked[:5]))
        lines.append("Reproduce each failing check yourself, fix the cause, then finish again.")
        return "\n".join(lines)


def start_marker(control_dir: str) -> str:
    return f"{control_dir}/started"


async def changed_files(env: Environment, workdir: str, control_dir: str = CONTROL_DIR) -> list[str]:
    """Files modified since the run started (outside the harness's own control directories)."""
    roots = " ".join(shlex.quote(r) for r in dict.fromkeys([workdir, "/tmp", "/root"]))
    marker = shlex.quote(start_marker(control_dir))
    prune = "\\( -name .git -o -name node_modules -o -name .cache -o -name __pycache__ \\) -prune -o"
    res = await run(env, f"T=$(command -v timeout >/dev/null && echo 'timeout 30'); "
                         f"[ -e {marker} ] && $T find {roots} -xdev {prune} -type f -newer {marker} -print "
                         f"2>/dev/null | grep -v -e '^{control_dir}' -e '^{VERIFY_CONTROL_DIR}' | head -n {CHANGED_LIMIT}",
                    timeout_s=45)
    return [ln for ln in res.stdout.splitlines() if ln.strip()]


def _clip(text: str) -> str:
    if len(text) <= MAX_RESULT_CHARS:
        return text
    half = MAX_RESULT_CHARS // 2
    return f"{text[:half]}\n…[{len(text) - MAX_RESULT_CHARS} chars omitted]…\n{text[-half:]}"


def _request(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Reasoning is replayed for the newest assistant turn only."""
    last = max((i for i, m in enumerate(messages) if m.get("role") == "assistant"), default=-1)
    return [m if i == last else {k: v for k, v in m.items() if k != "reasoning_content"}
            for i, m in enumerate(messages)]


async def verify(provider: ChatProvider, env: Environment, *, task: str, workdir: str, budget_s: float,
                 control_dir: str = CONTROL_DIR,
                 make_clone: Callable[[Environment], Awaitable[Any]] = Clone.create,
                 log: Callable[[dict[str, Any]], None] = lambda row: None) -> Verification:
    """``log`` receives every verifier turn (reasoning, calls) and tool result, for the run's trace."""
    t0 = time.monotonic()
    try:
        changed = await changed_files(env, workdir, control_dir)
        clone = await make_clone(env)
    except Exception as exc:  # substrate failure: reported, never a hold
        return Verification("error", error=f"{type(exc).__name__}: {exc}", clone_s=round(time.monotonic() - t0, 1))
    clone_s = round(time.monotonic() - t0, 1)
    deadline = time.monotonic() + budget_s
    remaining = lambda: deadline - time.monotonic()  # noqa: E731
    usage: dict[str, int] = {}
    terms = Terminals(clone, workdir, remaining, control_dir=VERIFY_CONTROL_DIR)
    try:
        files = Files(clone, workdir)
        listing = "\n".join(changed) if changed else "(none found)"
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": PROMPT.format(budget=int(budget_s))},
            {"role": "user", "content": f"TASK:\n{task}\n\nWorking directory: {workdir}\n\nFiles changed during "
                                        f"the work:\n{listing}"}]
        tools = [TERMINAL, READ_FILE, LIVE_PROBE, VERDICT]
        warned = False
        for turn_no in range(1, MAX_TURNS + 1):
            if remaining() < 60 and not warned:
                messages.append({"role": "user", "content": "Time is nearly up: call verdict now with what you have."})
                warned = True
            if remaining() <= 0:
                break
            # the last turn, or too little time for another check: only the verdict is offered
            last = turn_no == MAX_TURNS or remaining() < 60
            turn = await provider.complete(_request(messages), [VERDICT] if last else tools, max_tokens=16_384,
                                           remaining_s=remaining)
            log({"turn": turn_no, "latency_s": round(turn.latency_s, 2), "usage": turn.usage,
                 "reasoning": turn.reasoning, "content": turn.content, "tool_calls": turn.tool_calls})
            for k, v in turn.usage.items():
                usage[k] = usage.get(k, 0) + v
            messages.append(turn.assistant_message())
            if not turn.tool_calls:
                messages.append({"role": "user", "content": "Use a tool; finish with verdict."})
                continue
            for call in turn.tool_calls:
                fn = call.get("function") or {}
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}
                if fn.get("name") == "verdict":
                    reqs = [r for r in args.get("requirements") or [] if isinstance(r, dict)]
                    if not reqs:
                        out = "verdict needs at least one requirement entry"
                    else:
                        status = "hold" if any(r.get("status") == "not_met" for r in reqs) else "pass"
                        return Verification(status, reqs, turns=turn_no, clone_s=clone_s, usage=usage)
                else:
                    out = await _dispatch(fn.get("name"), args, terms, files, env)
                log({"turn": turn_no, "tool": fn.get("name"), "result": _clip(out)})
                messages.append({"role": "tool", "tool_call_id": call["id"],
                                 "content": f"{_clip(out)}\n[{max(0, remaining()):.0f}s left]"})
        return Verification("error", error="verifier gave no verdict in time", turns=MAX_TURNS, clone_s=clone_s,
                            usage=usage)
    except Exception as exc:
        return Verification("error", error=f"{type(exc).__name__}: {exc}", clone_s=clone_s, usage=usage)
    finally:
        try:
            await terms.close()
        except Exception:
            pass  # the clone is removed next, with everything running in it
        await clone.close()


async def _dispatch(name: str | None, args: dict[str, Any], terms: Terminals, files: Files,
                    live: Environment) -> str:
    try:
        if name == "terminal":
            return await terms.use(name=str(args.get("name") or "main"), input=str(args.get("input") or ""),
                                   mode=str(args.get("mode") or "command"), wait_s=float(args.get("wait_s") or 30),
                                   interrupt=bool(args.get("interrupt")))
        if name == "read_file":
            return await files.read(args.get("path", ""), int(args.get("start_line") or 1),
                                    int(args.get("num_lines") or 400))
        if name == "live_probe":
            command = str(args.get("command") or "")
            safe, refusal = probe_command(command)
            if refusal:
                return f"[refused: {refusal}]"
            res = await run(live, safe, timeout_s=20)
            return f"{res.stdout}{res.stderr}\n[exit {res.code}]"
        return f"unknown tool {name!r}"
    except Exception as exc:
        return f"[error: {type(exc).__name__}: {exc}]"
