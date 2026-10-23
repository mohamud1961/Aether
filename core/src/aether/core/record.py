"""The run record: what the model's own terminal commands actually did, kept by the harness (AETHER_CORE_RECORD).

The model works as it already does (terminal, files). The harness reads each finished terminal command's exit
status, and when the command ran the work (``is_check``: an interpreter, test runner, compiler, ``./x``, diff), it
hashes the files the run changed under the working directory and keeps a copy of every passing version. From that
record alone it states facts, never interpretations:

- in the stream: a check that passed before and fails now, with the files changed since and where the passing
  version is saved (restoring is a plain ``cp``);
- after a context checkpoint: the latest exact result of each recent check, which the summary cannot rewrite;
- at the first finish: the newest passing checks are run again in a fresh shell (a new exec in the same container,
  as the grader's commands run: no terminal variables, functions, venv activation or REPL memory) against the files
  being delivered. If a re-run fails where the terminal run passed, or a check's newest run failed, the finish is
  held once with those facts; the next finish is always accepted. A re-run that changes delivered files is undone.

Interactive (keys) input and the python tool have no exit status and are never scored. Exit 0 says the command ran,
not that the work is right. Substrate errors here are traced and never fail the run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
import shlex
from typing import Any, Callable

from .env import Environment, run
from .receipt import MARKER, SKIP

_DONE = re.compile(r"\[exit (\d+)(?: · last pipeline's stage exits [^\]]*?)? · ([\d.]+)s · terminal (\S+) · cwd ([^\]\n]*)\]\s*$")
_RUNNING = re.compile(r"\[still running after \d+s")
_EXEC = {
    "python", "python3", "pytest", "py.test", "bash", "sh", "node", "deno", "bun", "make", "cargo", "go", "gcc",
    "g++", "cc", "c++", "clang", "clang++", "java", "javac", "rustc", "ruby", "perl", "rscript", "julia", "ocaml",
    "dune", "npm", "npx", "yarn", "pnpm", "uv", "poetry", "tox", "ctest", "diff", "cmp", "ghc", "coqc", "php",
    "lua", "swift", "dotnet", "mvn", "gradle", "sqlite3", "psql", "gdb", "valgrind", "tsc", "tsx", "ts-node",
}
_PREFIX = {"sudo", "time", "nice", "env", "nohup", "stdbuf", "exec", "command"}
_NOT_RUN = re.compile(r"(-m pip\b|\bpip3? |\buv (pip|add|venv|sync)|\bnpm (i|install|ci)\b|\bapt(-get)? )")
RECORD_ENV = "AETHER_CORE_RECORD"  # on: this record, its facts and the finish re-run
HOLD_ENV, HOLD_MODES = "AETHER_CORE_FINISH_HOLD", ("off", "neutral")  # neutral: first finish held once, no facts
MAX_FILES = 300
SAVE_BYTES = 5_000_000
RERUN_MAX_ORIG_S = 120.0
RERUN_MAX_S = 180.0
RERUNS = 2
VIEW_CHECKS = 6
OUT_TAIL = 1500


def is_check(command: str) -> bool:
    """True when some segment of the command runs code: an interpreter, test runner, compiler, ./x, diff or cmp."""
    if _NOT_RUN.search(command) or re.search(r"&\s*$", command.strip()):
        return False
    for seg in re.split(r"&&|\|\||;|\n|\|", command):
        words = seg.strip().split()
        while words and ("=" in words[0] and not words[0].startswith(("=", "./", "/")) or words[0] in _PREFIX):
            words = words[1:]
        if words and words[0] == "timeout":
            words = [w for w in words[1:] if not w.startswith("-")][1:]
        if not words:
            continue
        first = words[0]
        if first.startswith("./") or first.split("/")[-1].lower().rstrip("0123456789.") in _EXEC:
            return True
    return False


def norm(command: str) -> str:
    return " ".join(command.split())


def short(command: str, limit: int = 160) -> str:
    one = norm(command)
    return one if len(one) <= limit else one[: limit - 3] + "..."


@dataclass
class Check:
    seq: int
    t: float
    command: str
    exit: int
    elapsed: float
    cwd: str
    files: dict[str, str] = field(default_factory=dict)  # relative path -> sha256 when it finished

    @property
    def passed(self) -> bool:
        return self.exit == 0

    @property
    def failed(self) -> bool:  # an exit status of the command itself, not a signal (interrupt, kill, timeout)
        return 0 < self.exit < 124


class Record:
    def __init__(
        self, env: Environment, workdir: str, control_dir: str, remaining: Callable[[], float], trace
    ) -> None:
        self.env, self.workdir, self.control_dir = env, workdir, control_dir
        self.remaining, self.trace = remaining, trace
        self.versions = f"{control_dir}/versions"
        self.checks: list[Check] = []
        self.pending: dict[str, str] = {}  # terminal name -> command still running in it
        self.finish_seen = False
        self.errors = 0

    # -- observing -------------------------------------------------------------------------------------------
    def completed(self, args: dict[str, Any], out: str) -> tuple[str, int, float, str] | None:
        """(command, exit, seconds, cwd) when this terminal call's result reports a command finishing."""
        name = str(args.get("name") or "main")
        text = str(args.get("input", ""))
        mode = str(args.get("mode") or "command")
        sent = text if mode == "command" and text.strip("\x03 \n") and "[input not sent" not in out else ""
        if sent:
            self.pending.pop(name, None)
        done = _DONE.search(out)
        if done is None:
            if sent and _RUNNING.search(out):
                self.pending[name] = sent
            return None
        command = sent or self.pending.pop(name, "")
        if not command:
            return None
        return command, int(done.group(1)), float(done.group(2)), done.group(4).strip()

    async def after_terminal(self, args: dict[str, Any], out: str, t: float) -> str:
        """Record a finished check; return a regression fact for the model ('' when there is none)."""
        try:
            done = self.completed(args, out)
            if done is None or not is_check(done[0]):
                return ""
            command, code, elapsed, cwd = done
            files = await self.snapshot(save=code == 0)
            check = Check(len(self.checks) + 1, round(t, 1), command, code, elapsed, cwd, files)
            earlier = [c for c in self.checks if norm(c.command) == norm(command) and c.passed]
            self.checks.append(check)
            self.trace("record_check", seq=check.seq, command=short(command, 400), exit=code, cwd=cwd,
                       elapsed=elapsed, files=len(files))
            if not (check.failed and earlier):
                return ""
            return self._regression(check, earlier[-1])
        except Exception as exc:  # the record is an instrument: its failure is traced, the run goes on
            self.errors += 1
            self.trace("record_error", where="after_terminal", error=f"{type(exc).__name__}: {exc}")
            return ""

    def _regression(self, now: Check, then: Check) -> str:
        changed = sorted(p for p, h in then.files.items() if now.files.get(p) != h)
        lines = [f"[harness record] this command exited 0 at t={then.t:.0f}s and exits {now.exit} now."]
        if changed:
            lines.append("Files changed since then (the t=%.0fs version of each is saved):" % then.t)
            for path in changed[:8]:
                lines.append(f"  {path}: {self._saved(path, then.files[path])}")
        else:
            lines.append("No file the run changed under the working directory differs since then.")
        return "\n".join(lines)

    def _saved(self, path: str, digest: str) -> str:
        return f"{self.versions}/{digest}/{path.rsplit('/', 1)[-1]}"

    async def snapshot(self, save: bool) -> dict[str, str]:
        """sha256 of each file the run changed under the working directory; with ``save``, keep a copy of each
        version not kept yet (content-addressed, files under SAVE_BYTES)."""
        q = shlex.quote
        prune = " -o ".join(f"-name {q(name)}" for name in SKIP)
        marker = q(f"{self.control_dir}/{MARKER}")
        store = q(self.versions)
        keep = (
            f'if [ ! -e {store}/"$h" ] && [ "$(wc -c < "$f")" -lt {SAVE_BYTES} ]; then '
            f'mkdir -p {store}/"$h" && cp -p "$f" {store}/"$h"/"$(basename "$f")"; fi; '
            if save else ""
        )
        command = (
            f"cd {q(self.workdir)} && test -e {marker} && "
            f"find . -xdev \\( {prune} \\) -prune -o -type f -newer {marker} -size -20M -print 2>/dev/null | "
            f"head -n {MAX_FILES} | while IFS= read -r f; do "
            f'h=$( (sha256sum "$f" 2>/dev/null || shasum -a 256 "$f") | cut -c1-64); '
            f'[ -n "$h" ] || continue; {keep}printf "%s %s\\n" "$h" "${{f#./}}"; done'
        )
        result = await run(self.env, command, timeout_s=max(5.0, min(60.0, self.remaining())))
        if result.code != 0:
            raise OSError(f"snapshot failed: {(result.stderr or result.stdout).strip()[:200]}")
        files: dict[str, str] = {}
        for line in result.stdout.splitlines():
            digest, _, path = line.partition(" ")
            if len(digest) == 64 and path:
                files[path] = digest
        return files

    # -- after a checkpoint ----------------------------------------------------------------------------------
    async def after_checkpoint(self) -> str:
        if not self.checks:
            return ""
        try:
            now = await self.snapshot(save=False)
        except Exception as exc:
            self.errors += 1
            self.trace("record_error", where="after_checkpoint", error=f"{type(exc).__name__}: {exc}")
            now = None
        latest = self._latest()[-VIEW_CHECKS:]
        lines = ["[harness record of your recent checks: exact exit statuses, not a summary]"]
        for c in latest:
            line = f"  t={c.t:.0f}s exit {c.exit}: {short(c.command)}"
            if now is not None:
                changed = sorted(p for p, h in c.files.items() if now.get(p) != h)
                line += f" (files changed since: {', '.join(changed[:5])})" if changed else " (files unchanged since)"
            lines.append(line)
        return "\n".join(lines)

    def _latest(self) -> list[Check]:
        """The newest run of each distinct check command, oldest first."""
        seen: dict[str, Check] = {}
        for c in self.checks:
            seen.pop(norm(c.command), None)
            seen[norm(c.command)] = c
        return list(seen.values())

    # -- at finish ------------------------------------------------------------------------------------------
    async def at_finish(self) -> tuple[bool, str, dict[str, Any]]:
        """(hold, text for the model, trace row). Only the first finish is examined."""
        if self.finish_seen:
            return False, "", {"examined": False}
        self.finish_seen = True
        row: dict[str, Any] = {"examined": True, "checks": len(self.checks)}
        try:
            delivered = await self.snapshot(save=True)
        except Exception as exc:
            self.errors += 1
            row["error"] = f"{type(exc).__name__}: {exc}"
            self.trace("record_finish", hold=False, **row)
            return False, "", row
        latest = self._latest()
        failing = [c for c in latest if c.failed]
        reruns = await self._reruns(latest, delivered, row)
        broke = [r for r in reruns if r["exit"] not in (0, None)]
        row.update(failing=[short(c.command) for c in failing], reruns=reruns)
        hold = bool(failing or broke)
        row["hold"] = hold
        self.trace("record_finish", **row)
        if not hold:
            return False, "", row
        left = self.remaining()
        lines = ["[finish not yet accepted. Harness record of your own commands, exact results:]"]
        for c in failing:
            lines.append(f"- The newest run of `{short(c.command)}` (t={c.t:.0f}s) exited {c.exit}; it has not passed since.")
        for r in reruns:
            if r["exit"] is None:
                continue
            if r["exit"] == 0:
                lines.append(f"- `{r['command']}` passed again in a fresh shell against the files being delivered.")
            else:
                result = (f"did not finish within {r['limit']:.0f}s" if r["exit"] == 124 else f"exits {r['exit']}")
                lines.append(
                    f"- `{r['command']}` exited 0 in your terminal at t={r['t']:.0f}s; run again now in a fresh shell "
                    f"(same container, cwd {r['cwd']}, none of your terminal's variables or Python session) against "
                    f"the files being delivered, it {result}. Output tail:\n{r['tail']}"
                )
        for r in reruns:
            if r.get("restored"):
                lines.append(f"- That re-run changed {', '.join(r['restored'])}; they were put back as you left them.")
        lines.append(
            f"Passing versions you ran are saved under {self.versions}/<sha256>/<name>. You have {left:.0f}s. "
            "Fix what this shows, restore a saved version, or call finish again to finish as is."
        )
        return True, "\n".join(lines), row

    async def _reruns(self, latest: list[Check], delivered: dict[str, str], row: dict) -> list[dict[str, Any]]:
        left = self.remaining()
        if left < 90:
            row["reruns_skipped"] = f"{left:.0f}s left"
            return []
        picks = [c for c in latest if c.passed and c.elapsed <= RERUN_MAX_ORIG_S][-RERUNS:]
        out = []
        for c in picks:
            limit = min(RERUN_MAX_S, max(30.0, 3 * c.elapsed + 10), self.remaining() * 0.25)
            q = shlex.quote
            body = f"cd {q(c.cwd)} && bash -c {q(c.command)}"
            command = (
                f"if command -v timeout >/dev/null 2>&1; then timeout -k 5 {int(limit)} bash -c {q(body)}; "
                f"else bash -c {q(body)}; fi 2>&1 | tail -c {OUT_TAIL}; exit ${{PIPESTATUS[0]}}"
            )
            item: dict[str, Any] = {"command": short(c.command), "t": c.t, "cwd": c.cwd, "orig_exit": c.exit,
                                    "limit": limit}
            try:
                result = await run(self.env, f"bash -c {q(command)}", timeout_s=limit + 20)
                item.update(exit=result.code, tail=(result.stdout or result.stderr)[-OUT_TAIL:])
            except Exception as exc:  # no result is not a failure of the work: reported to the trace only
                item.update(exit=None, error=f"{type(exc).__name__}: {exc}", tail="")
            item["restored"] = await self._undo(delivered)
            out.append(item)
        return out

    async def _undo(self, delivered: dict[str, str]) -> list[str]:
        """Put back any delivered file the re-run changed (its copy was saved by the finish snapshot)."""
        try:
            now = await self.snapshot(save=False)
        except Exception as exc:
            self.trace("record_error", where="undo", error=f"{type(exc).__name__}: {exc}")
            return []
        moved = sorted(p for p, h in delivered.items() if now.get(p) != h)
        q = shlex.quote
        restored = []
        for path in moved:
            source = self._saved(path, delivered[path])
            result = await run(
                self.env, f"cd {q(self.workdir)} && test -f {q(source)} && cp -p {q(source)} {q(path)}", timeout_s=30
            )
            if result.code == 0:
                restored.append(path)
        return restored

    def summary(self) -> dict[str, Any]:
        return {
            "checks": len(self.checks),
            "passed": sum(c.passed for c in self.checks),
            "failed": sum(c.failed for c in self.checks),
            "errors": self.errors,
        }


NEUTRAL_HOLD = (
    "[finish not yet accepted] You have {left:.0f}s left. If there is anything you want to check or change, do it "
    "now; otherwise call finish again to finish as is."
)
