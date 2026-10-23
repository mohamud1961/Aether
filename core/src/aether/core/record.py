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

With ``measure`` (AETHER_CORE_RECORD=measure) the record also keeps the lines each check printed. At the first finish
it states, as facts: a check whose printed results differ between an earlier version of the delivered files (saved)
and the newest one; a fresh-shell re-run that exits 0 but prints different results from the run it repeats; and
delivered files changed after the newest check ran. Which result is better is the model's call, never the harness's.

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
RECORD_ENV, RECORD_MODES = "AETHER_CORE_RECORD", ("off", "on", "measure", "paths")  # on: record, facts, re-run;
# paths: only the task-named paths that do not exist yet (at half time, 80% and the first finish)
HOLD_ENV, HOLD_MODES = "AETHER_CORE_FINISH_HOLD", ("off", "neutral")  # neutral: first finish held once, no facts
MAX_FILES = 300
SAVE_BYTES = 5_000_000
RERUN_MAX_ORIG_S = 120.0
RERUN_MAX_S = 180.0
RERUNS = 2
VIEW_CHECKS = 6
OUT_TAIL = 1500
KEEP_OUT = 1200  # printed output kept per check (measure)
# absolute paths in the task statement; those missing at the first command are what the work must create
_TASK_PATH = re.compile(r"(?<![\w.:/])(/(?:[\w.-]+/)*[\w-][\w.-]*\w)")
MID_AT = 0.5  # measure: named paths still missing are stated at half time
LATE_AT = 0.8  # measure: once this share of the time is used, the finish facts are stated in the stream (timeouts
               # never reach finish: P2 replay, 5 of 11 pilot tasks failed by timeout)
RESULT_LINES = 3
_FOOTER = re.compile(r"\n?\[(exit \d+|still running)[^\n]*\]\s*$")


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


def results(out: str) -> list[str]:
    """The printed lines that carry numbers or a verdict word: what a check reports, in order, without duplicates."""
    seen: list[str] = []
    for line in _FOOTER.sub("", out).splitlines():
        line = " ".join(line.split())
        if line and len(line) <= 300 and line not in seen and re.search(r"\d|\b(pass|fail|ok|error|true|false|mismatch|"
                                                                        r"match|differ|wrong|correct)", line, re.I):
            seen.append(line)
    return seen


# run-to-run noise, never a result: shell `time`, process ids, wall-clock durations, timestamps, addresses
_NOISE = re.compile(r"^(real|user|sys)\s|\bpid\b|\belapsed\b|\btook\b|\d(\.\d+)?\s*(ms|s|sec|secs|seconds)\b|"
                    r"\d\d:\d\d:\d\d|0x[0-9a-f]{6,}", re.I)


def differing(a: str, b: str) -> tuple[list[str], list[str]]:
    """The result lines only in ``a`` and only in ``b``, the last ones (where checks print verdicts), noise dropped."""
    ra = [x for x in results(a) if not _NOISE.search(x)]
    rb = [x for x in results(b) if not _NOISE.search(x)]
    return [x for x in ra if x not in rb][-RESULT_LINES:], [x for x in rb if x not in ra][-RESULT_LINES:]


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
    out: str = ""  # tail of what it printed (measure)

    @property
    def passed(self) -> bool:
        return self.exit == 0

    @property
    def failed(self) -> bool:  # an exit status of the command itself, not a signal (interrupt, kill, timeout)
        return 0 < self.exit < 124


class Record:
    def __init__(
        self, env: Environment, workdir: str, control_dir: str, remaining: Callable[[], float], trace,
        measure: bool = False, task: str = "", paths_only: bool = False,
    ) -> None:
        self.paths_only = paths_only
        self.env, self.workdir, self.control_dir, self.measure = env, workdir, control_dir, measure
        self.remaining, self.trace = remaining, trace
        self.versions = f"{control_dir}/versions"
        self.checks: list[Check] = []
        self.pending: dict[str, str] = {}  # terminal name -> command still running in it
        self.finish_seen = False
        self.total = remaining()
        self.late_done = False
        self.mid_done = False
        self.named = sorted({p for p in _TASK_PATH.findall(task) if not p.startswith(("/dev/", "/proc/"))})[:20]
        self.to_create: list[str] | None = None  # named paths absent at the first command
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
            if self.measure and self.to_create is None:
                self.to_create = []
                self.to_create = await self._missing(self.named)
                self.trace("record_named", named=self.named, absent_at_start=self.to_create)
            if self.paths_only:
                return await self._late()
            done = self.completed(args, out)
            if done is None or not is_check(done[0]):
                return await self._late()
            command, code, elapsed, cwd = done
            files = await self.snapshot(save=code == 0)
            check = Check(len(self.checks) + 1, round(t, 1), command, code, elapsed, cwd, files,
                          _FOOTER.sub("", out)[-KEEP_OUT:] if self.measure else "")
            earlier = [c for c in self.checks if norm(c.command) == norm(command) and c.passed]
            self.checks.append(check)
            self.trace("record_check", seq=check.seq, command=short(command, 400), exit=code, cwd=cwd,
                       elapsed=elapsed, files=len(files))
            if check.failed and earlier:
                return self._regression(check, earlier[-1])
            return await self._late()
        except Exception as exc:  # the record is an instrument: its failure is traced, the run goes on
            self.errors += 1
            self.trace("record_error", where="after_terminal", error=f"{type(exc).__name__}: {exc}")
            return ""

    async def _missing(self, paths: list[str]) -> list[str]:
        if not paths:
            return []
        q = " ".join(shlex.quote(p) for p in paths)
        try:
            result = await run(self.env, f"for p in {q}; do [ -e \"$p\" ] || echo \"$p\"; done", timeout_s=30)
        except Exception as exc:  # unknown is not absent: nothing is said
            self.errors += 1
            self.trace("record_error", where="missing", error=f"{type(exc).__name__}: {exc}")
            return []
        return [line for line in result.stdout.splitlines() if line in paths]

    async def _absent(self) -> list[str]:
        """Paths the task names that were absent at the first command and are still absent."""
        return await self._missing(self.to_create or [])

    async def _late(self) -> str:
        """measure: at MID_AT of the time, named paths still missing; once at LATE_AT, the finish facts."""
        if not self.measure or self.finish_seen:
            return ""
        used = 1 - self.remaining() / self.total if self.total else 0.0
        if not self.mid_done and MID_AT <= used < LATE_AT:
            self.mid_done = True
            absent = await self._absent()
            self.trace("record_mid", absent=absent, remaining_s=round(self.remaining(), 1))
            if absent:
                return (f"[harness record, {self.remaining():.0f}s left] Paths the task names that do not exist yet: "
                        f"{', '.join(absent)}. Whatever exists when time runs out is what is delivered.")
            return ""
        if self.late_done or used < LATE_AT:
            return ""
        self.late_done = self.mid_done = True
        facts = [] if self.paths_only else self._measured(await self.snapshot(save=False), [])
        absent = await self._absent()
        if absent:
            facts.append(f"- Paths the task names that do not exist yet: {', '.join(absent)}")
        self.trace("record_late", facts=len(facts), remaining_s=round(self.remaining(), 1))
        if not facts:
            return ""
        return "\n".join([f"[harness record, {self.remaining():.0f}s left: exact results of your own commands]", *facts,
                           "Whatever is in the working directory when time runs out is what is delivered."])

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
        if self.paths_only:
            absent = await self._absent()
            row.update(absent=absent, hold=bool(absent))
            self.trace("record_finish", **row)
            if not absent:
                return False, "", row
            return True, (f"[finish not yet accepted] Paths the task names that do not exist: {', '.join(absent)}. "
                          f"You have {self.remaining():.0f}s. Create them, or call finish again to finish as is."), row
        try:
            delivered = await self.snapshot(save=True)
        except Exception as exc:
            self.errors += 1
            row["error"] = f"{type(exc).__name__}: {exc}"
            self.trace("record_finish", hold=False, **row)
            return False, "", row
        latest = self._latest()
        # a regression left in place: the newest run fails after an earlier run of the same command passed. A one-off
        # command that failed once is exploration, not a contradiction (pilot1 tune-mjcf: 10 such holds, all noise).
        passed = {norm(c.command) for c in self.checks if c.passed}
        failing = [c for c in latest if c.failed and norm(c.command) in passed]
        reruns = await self._reruns(latest, delivered, row)
        broke = [r for r in reruns if r["exit"] not in (0, None)]
        row.update(failing=[short(c.command) for c in failing], reruns=reruns)
        measured = self._measured(delivered, reruns) if self.measure else []
        absent = await self._absent() if self.measure else []
        if absent:
            measured.append(f"- Paths the task names that do not exist: {', '.join(absent)}")
        row["measured"] = len(measured)
        hold = bool(failing or broke or measured)
        row["hold"] = hold
        self.trace("record_finish", **row)
        if not hold:
            return False, "", row
        left = self.remaining()
        lines = ["[finish not yet accepted. Harness record of your own commands, exact results:]"]
        for c in failing:
            lines.append(f"- `{short(c.command)}` passed earlier; its newest run (t={c.t:.0f}s) exited {c.exit}.")
        lines += measured
        for r in reruns:
            if r["exit"] is None or r.get("differs"):
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
            gone = await self._gone(c)
            if gone:  # the work removed its own check script (delivery clean-up): nothing to re-run, nothing to say
                out.append({"command": short(c.command), "t": c.t, "cwd": c.cwd, "orig_exit": c.exit, "exit": None,
                            "skipped": f"removed since: {', '.join(gone)}", "tail": ""})
                continue
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
            if self.measure and item["exit"] == 0:
                then, now = differing(c.out, item["tail"])
                if then or now:
                    item["differs"] = {"then": then, "now": now}
            item["restored"] = await self._undo(delivered)
            out.append(item)
        return out

    def _measured(self, delivered: dict[str, str], reruns: list[dict[str, Any]]) -> list[str]:
        """Facts comparing what checks printed across versions of the delivered files (measure)."""
        lines: list[str] = []
        runs: dict[str, list[Check]] = {}
        for c in self.checks:
            if c.passed:
                runs.setdefault(norm(c.command), []).append(c)
        for group in runs.values():
            newest = group[-1]
            earlier = []
            for c in group[:-1]:
                old = sorted(p for p, h in c.files.items() if p in delivered and delivered[p] != h)
                then, _now = differing(c.out, newest.out)
                if old and then:
                    earlier.append((c, old, then))
            if not earlier:
                continue
            lines.append(f"- `{short(newest.command)}` printed different results on earlier versions of files you "
                         "are delivering:")
            for c, old, then in earlier[-2:]:
                saved = ", ".join(f"{p} saved at {self._saved(p, c.files[p])}" for p in old[:4])
                lines.append(f"    t={c.t:.0f}s: {' | '.join(then)}  ({saved})")
            _then, now = differing(earlier[-1][0].out, newest.out)
            lines.append(f"    newest, t={newest.t:.0f}s: {' | '.join(now) or '(none of those lines)'}")
        for r in reruns:
            if r.get("differs"):
                lines.append(
                    f"- `{r['command']}` printed at t={r['t']:.0f}s: {' | '.join(r['differs']['then']) or '-'}; run "
                    f"again now in a fresh shell against the files being delivered it exits 0 but prints: "
                    f"{' | '.join(r['differs']['now']) or '-'}"
                )
        if self.checks:
            last = self.checks[-1]
            stale = sorted(p for p, h in delivered.items() if last.files.get(p) != h)
            if stale:
                lines.append(f"- Changed or created after your last check ran (t={last.t:.0f}s, "
                             f"`{short(last.command, 80)}`): {', '.join(stale[:8])}")
        return lines

    async def _gone(self, c: Check) -> list[str]:
        """Files the command names that existed when it ran and are absent now (pilot1 regex-log: the model deleted
        test.pl before finishing; re-running it 'failed' with no such file, a false hold)."""
        named = {w for w in re.findall(r"[\w./-]+\.\w+", c.command) if not w.startswith("-")}
        paths = sorted(w if w.startswith("/") else f"{c.cwd.rstrip('/')}/{w}" for w in named)
        root = self.workdir.rstrip("/") + "/"
        existed = [p for p in paths if p.startswith(root) and p[len(root):] in c.files or not p.startswith(root)]
        return await self._missing(existed) if existed else []

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
