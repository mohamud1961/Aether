"""Terminal sessions: what one terminal is, and how Terminals starts, restarts and stops them.

Split from terminal.py (module-size cap, 2026-10-26) with the code unchanged; ``Terminals`` inherits
``TerminalLifecycle`` and supplies ``_write`` and ``_poll``.
"""

from __future__ import annotations

import asyncio
import shlex
import time
from dataclasses import dataclass, field

from .env import (
    ProcessCleanupError,
    list_process_tree,
    process_identities,
    run,
    stop_process_tree,
)
from .transfer import put_bytes

MAX_TERMINALS = 8
# util-linux / busybox ``script`` gives the shell a pseudo-terminal; anything else falls back to a plain pipe.
_PTY_TEST = "command -v bash >/dev/null 2>&1 && script -qfc true /dev/null >/dev/null 2>&1 </dev/null"

_INIT = (
    "stty -echo 2>/dev/null; export PS1='' PS2='' PROMPT_COMMAND='' TERM=dumb PAGER=cat "
    "GIT_PAGER=cat SYSTEMD_PAGER=cat DEBIAN_FRONTEND=noninteractive; "
    "bind 'set enable-bracketed-paste off' 2>/dev/null; true\n"
)


class TerminalGone(RuntimeError):
    """The terminal's shell or its log is gone."""


@dataclass
class Session:
    name: str
    root: str
    pid: int
    pty: bool
    bash: bool = False  # the shell is bash (PIPESTATUS is available)
    cursor: int = 0
    seq: int = 0
    pending: int = 0  # command whose completion marker has not been seen yet
    last_size: int = 0
    grew_at: float = 0.0  # monotonic time the log last grew
    ready: bool = False
    identity: dict[str, str] = field(default_factory=dict)
    cleanup_warning: str = ""

    @property
    def log(self) -> str:
        return f"{self.root}/out.log"

    @property
    def fifo(self) -> str:
        return f"{self.root}/in"


class TerminalLifecycle:
    async def _start(self, name: str) -> Session:
        if len(self._sessions) + len(self._launching) >= MAX_TERMINALS:
            raise ValueError(
                f"at most {MAX_TERMINALS} terminals; reuse one of {self.names}"
            )
        generation = self._generations.get(name, 0)
        self._generations[name] = generation + 1
        # A dot is outside the accepted name alphabet, so generations cannot
        # collide with another model-chosen name (main-1 versus restarted main).
        suffix = name if generation == 0 else f"{name}.{generation}"
        root = f"{self._control_dir}/term/{suffix}"
        q = shlex.quote
        wrapper = "\n".join(
            [
                "#!/bin/sh",
                f"if [ -r /proc/$$/stat ]; then sed 's/.*) //' /proc/$$/stat | awk '{{print $20}}' > {q(root + '/birth')}; "
                f"else ps -p $$ -o lstart= | awk '{{$1=$1;print}}' > {q(root + '/birth')}; fi",
                f"echo $$ > {q(root + '/pid')}",
                f"cd {q(self._workdir)} 2>/dev/null || cd /",
                f"exec 3<> {q(root + '/in')}",
                f"if {_PTY_TEST}; then",
                f"  script -qfc 'bash --noprofile --norc -i' /dev/null <&3 >> {q(root + '/out.log')} 2>&1",
                "elif command -v bash >/dev/null 2>&1; then",
                f"  bash --noprofile --norc <&3 >> {q(root + '/out.log')} 2>&1",
                "else",
                f"  sh <&3 >> {q(root + '/out.log')} 2>&1",
                "fi",
                f"echo $? > {q(root + '/exit')}",
                "",
            ]
        )
        res = await run(
            self._env,
            f"rm -rf {q(root)} && mkdir -p {q(root)} && mkfifo {q(root + '/in')} && : > {q(root + '/out.log')}",
        )
        if res.code != 0:
            raise RuntimeError(
                f"terminal setup failed: {(res.stderr or res.stdout).strip()[:300]}"
            )
        await put_bytes(self._env, wrapper.encode(), f"{root}/run.sh")
        # `setsid -f` forks without the shell's `&`: a background job of a non-interactive shell starts with
        # SIGINT ignored, that disposition is inherited by every command in the terminal, and Ctrl-C did
        # nothing (found on Linux in D1; the macOS tests use the pipe path and never saw it).
        run_sh, pid_file = q(root + "/run.sh"), q(root + "/pid")
        # setsid changes sessions, not inherited ignored signal dispositions.
        # Reset the new shell's initial SIGINT, preserving later task traps.
        launch = (
            "python3 -c "
            + q(
                "import os,signal,sys;signal.signal(signal.SIGINT,signal.SIG_DFL);"
                'os.execvp("sh",["sh",*sys.argv[1:]])'
            )
            + " "
            + run_sh
        )
        self._launching.add(root)
        res = await run(
            self._env,
            f"if command -v setsid >/dev/null 2>&1 && setsid -f true >/dev/null 2>&1; then "
            f"nohup setsid -f {launch} >/dev/null 2>&1 </dev/null; "
            f"elif command -v setsid >/dev/null 2>&1; then nohup setsid {launch} >/dev/null 2>&1 </dev/null & "
            f"else nohup {launch} >/dev/null 2>&1 </dev/null & fi; "
            f"i=0; while [ ! -s {pid_file} ] && [ $i -lt 100 ]; do sleep 0.1; i=$((i+1)); done; cat {pid_file}; "
            f"{_PTY_TEST} && echo pty || echo nopty; command -v bash >/dev/null 2>&1 && echo bash || echo sh",
        )
        lines = res.stdout.split()
        if res.code != 0 or len(lines) < 2 or not lines[0].isdigit():
            # A reply came back and no PID file appeared within the launch's 10 s wait: nothing is owned to
            # resolve at close. Kept in _launching, every later close() raised and the root held a terminal slot.
            self._launching.discard(root)
            self.cleanup_uncertainties.append(
                f"{root}: launch reported failure with no PID; a shell starting after the 10 s wait is unobserved"
            )
            raise RuntimeError(
                f"terminal launch failed: {(res.stderr or res.stdout).strip()[:300]}"
            )
        session = Session(
            name,
            root,
            int(lines[0]),
            lines[1] == "pty",
            bash=lines[2:3] == ["bash"],
            grew_at=time.monotonic(),
        )
        self._sessions[name] = session  # ownership precedes fallible initialization
        self._launching.remove(root)
        try:
            session.identity = await process_identities(self._env, [session.pid])
        except OSError as exc:
            session.cleanup_warning = (
                "[process identity unavailable; later cleanup may be unverified: "
                + str(exc)[:160]
                + "]\n"
            )
        init = _INIT
        if session.pty and session.bash:
            # SIGINT can skip the sourced line's normal completion writer.
            # A prompt callback proves Bash regained control and captures the
            # real exit status, without queuing text into a live interpreter.
            init += (
                "__aether_prompt_seq=0; __aether_prompt_owner=$$; __aether_prompt_receipt() { "
                "local __aether_prompt_rc=$1; "
                'if [ "${__aether_prompt_seq:-0}" -gt 0 ] && '
                '[ "$$" = "${__aether_prompt_owner:-0}" ]; then '
                f'local __aether_prompt_file={q(root)}/done_"$__aether_prompt_seq"; '
                'if [ ! -f "$__aether_prompt_file" ]; then '
                "builtin printf '__AETHER_DONE_%s_%s__ %s\\n' "
                '"$__aether_prompt_seq" "$__aether_prompt_rc" "$PWD" '
                '> "$__aether_prompt_file.tmp" && '
                'command mv -f "$__aether_prompt_file.tmp" "$__aether_prompt_file"; '
                'fi; fi; return "$__aether_prompt_rc"; };\n'
            )
        await self._write(
            session, init + 'printf \'\\n__AETHER_DONE_%s_%s__ %s\\n\' 0 "$?" "$PWD"\n'
        )
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            size, mark, _alive = await self._poll(session, 0)
            if mark:
                session.cursor = size
                break
            await asyncio.sleep(0.2)
        else:
            raise RuntimeError("terminal did not become ready within 15 s")
        session.ready = True
        return session

    async def close(self, keep: bool = False) -> None:
        """Stop every terminal and everything started in it. The shell runs under ``script`` in a session of its
        own, so a process-group kill does not reach it or its jobs; the whole process tree is collected from
        /proc first (while parents are alive, so nohup'd jobs are still descendants), then TERM, then KILL.

        ``keep``: kill nothing. The processes still running under the terminals are recorded in ``left_running``
        (pid and command line, wrapper shells excluded) and the container is left as the agent left it."""
        pids = [s.pid for s in self._sessions.values()]
        unresolved = []
        identities = {
            k: v
            for session in self._sessions.values()
            for k, v in session.identity.items()
        }
        for root in list(self._launching):
            try:
                result = await run(
                    self._env,
                    f"cat {shlex.quote(root + '/pid')}; cat {shlex.quote(root + '/birth')}",
                )
                parts = result.stdout.splitlines()
                if (
                    result.code != 0
                    or len(parts) != 2
                    or not parts[0].isdigit()
                    or int(parts[0]) <= 1
                    or not parts[1].strip()
                ):
                    raise OSError("owned PID/birth identity unavailable")
                pids.append(int(parts[0]))
                identities[parts[0]] = parts[1].strip()
            except Exception as exc:
                unresolved.append(f"{root}: {type(exc).__name__}: {exc}")
        if pids and keep:
            self.left_running = await list_process_tree(
                self._env, list(set(pids)), identities=identities
            )
            self.cleanup_receipt = {
                "status": "retained",
                "observed_processes": self.left_running,
                "scope": "observed live descendants/groups; no signals sent",
            }
        elif pids:
            self.cleanup_receipt = await stop_process_tree(
                self._env, list(set(pids)), identities=identities
            )
        self._sessions.clear()
        if unresolved:
            raise OSError(
                "terminal cleanup could not resolve startup: " + "; ".join(unresolved)
            )
        self._launching.clear()
        if self.cleanup_uncertainties:
            self.cleanup_receipt = {
                **self.cleanup_receipt,
                "status": "partial_unverified",
                "prior_uncertainties": list(self.cleanup_uncertainties),
            }


    async def _restart(self, session: Session, start: bool = True) -> Session:
        warning = ""
        try:
            await stop_process_tree(
                self._env, [session.pid], identities=session.identity
            )
        except ProcessCleanupError as exc:
            if not exc.receipt.get("missing_roots"):
                raise
            warning = "[previous terminal root exited before cleanup observation; detached descendants unverified]\n"
            self.cleanup_uncertainties.append(str(exc))
        self._sessions.pop(session.name, None)
        fresh = await self._start(session.name) if start else session
        fresh.cleanup_warning += warning
        return fresh
