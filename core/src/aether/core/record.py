"""The run record: what the model's own terminal commands actually did, kept by the harness (AETHER_CORE_RECORD).

The model works as it already does (terminal, files). The harness reads each finished terminal command's exit
status, and when the command ran the work (``is_check``: an interpreter, test runner, compiler, ``./x``, diff), it
hashes a bounded sample of changed files under the working directory and copies eligible passing bytes. From that
record alone it states facts, never interpretations:

- in the stream: a check that passed before and fails now, with the files changed since and where the passing
  version is saved (restoring is a plain ``cp``);
- after a context checkpoint: the latest exact result of each recent check, which the summary cannot rewrite;
- at finish: restate prior observations without re-executing arbitrary commands in the live solver environment.
  A fresh shell in the same container does not isolate file/process/dependency side effects. No safe replay
  backend is implemented here, so finish replay is explicitly skipped.

With ``measure`` (AETHER_CORE_RECORD=measure) the record also keeps the lines each check printed. At the first finish
it states, as facts: a check whose printed results differ between an earlier version of the delivered files (saved)
and the newest one; delivered files changed after the newest check ran. Which result is better is the model's call, never the harness's.

Interactive (keys) input and the python tool have no exit status and are never scored. Exit 0 says the command ran,
not that the work is right. Substrate errors here are traced and never fail the run.
"""

from __future__ import annotations

import re
import json
import posixpath
import shlex
from typing import Any, Callable

from . import task_commands
from .env import Environment, run
from .receipt import SKIP, changed
from .record_checks import _FOOTER, Check, differing, is_check, norm, results, short  # noqa: F401 (re-exported)

_DONE = re.compile(r"\[exit (\d+)(?: · last pipeline's stage exits [^\]]*?)? · ([\d.]+)s · terminal (\S+) · cwd ([^\]\n]*)\]\s*$")
_RUNNING = re.compile(r"\[still running after \d+s")
RECORD_ENV, RECORD_MODES = "AETHER_CORE_RECORD", ("off", "on", "measure", "paths", "coverage")  # on: record and
# scoped facts; paths: only the task-named paths that do not exist yet (at half time, 80% and the first finish);
# coverage: paths, plus at the first finish the commands the task shows that no command run contained (task_commands)
HOLD_ENV, HOLD_MODES = "AETHER_CORE_FINISH_HOLD", ("off", "neutral")  # neutral: first finish held once, no facts
MAX_FILES = 300
SAVE_BYTES = 5_000_000
VIEW_CHECKS = 6
OUT_TAIL = 1500
KEEP_OUT = 1200  # printed output kept per check (measure)
# absolute paths in the task statement; those missing at the first command are what the work must create
_TASK_PATH = re.compile(r"(?<![\w.:/])(/(?:[\w.-]+/)*[\w.-]+\w)")
MID_AT = 0.5  # measure: named paths still missing are stated at half time
LATE_AT = 0.8  # measure: once this share of the time is used, the finish facts are stated in the stream (timeouts
               # never reach finish: P2 replay, 5 of 11 pilot tasks failed by timeout)


def _display_paths(paths: list[str]) -> str:
    """Quote untrusted filenames in harness-authored facts; filesystem keys stay exact."""
    return ", ".join(json.dumps(path, ensure_ascii=True) for path in paths)


def _sent(args: dict[str, Any], out: str, modes: tuple[str, ...] = ("command",)) -> str:
    """The text this terminal call submitted in one of `modes` ('' for interrupts and input the terminal refused).
    A refusal is the result's first line naming this terminal (terminal.use: only a busy, already-started session
    refuses); output that merely contains the words is not one."""
    text, name = str(args.get("input", "")), str(args.get("name") or "main")
    refused = out.startswith(f"[input not sent: terminal {name} is still running")
    ok = (str(args.get("mode") or "command") in modes and not args.get("interrupt") and text.strip("\x03 \n")
          and not refused)
    return text if ok else ""


class Record:
    def __init__(
        self, env: Environment, workdir: str, control_dir: str, remaining: Callable[[], float], trace,
        measure: bool = False, task: str = "", paths_only: bool = False, commands: bool = False,
    ) -> None:
        self.paths_only = paths_only
        self.task_commands = task_commands.shown(task) if commands else []
        self.executed: list[str] = []  # terminal input the model sent (coverage)
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
        self.retained: set[tuple[str, str]] = set()  # validated byte copies, not every hashed file

    # -- observing -------------------------------------------------------------------------------------------
    def completed(self, args: dict[str, Any], out: str) -> tuple[str, int, float, str] | None:
        """(command, exit, seconds, cwd) when this terminal call's result reports a command finishing."""
        name = str(args.get("name") or "main")
        # Ctrl-C delivery does not prove the old command completed. Preserve
        # its pending identity until a real exit marker or an actually sent
        # replacement command provides new process evidence.
        sent = _sent(args, out)
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
            if self.task_commands and (sent := _sent(args, out, ("command", "keys"))):
                self.executed.append(sent)  # keys too: typed into a shell, it runs
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
            earlier = [c for c in self.checks if (c.cwd, c.command) == (cwd, command) and c.passed]
            self.checks.append(check)
            self.trace("record_check", seq=check.seq, command=short(command, 400), exit=code, cwd=cwd,
                       elapsed=elapsed, files=len(files))
            if check.failed and earlier:
                return await self._regression(check, earlier[-1])
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
                        f"{_display_paths(absent)}. Whatever exists when time runs out is what is delivered.")
            return ""
        if self.late_done or used < LATE_AT:
            return ""
        self.late_done = self.mid_done = True
        facts = [] if self.paths_only else await self._measured(await self.snapshot(save=False), [])
        absent = await self._absent()
        if absent:
            facts.append(f"- Paths the task names that do not exist yet: {_display_paths(absent)}")
        self.trace("record_late", facts=len(facts), remaining_s=round(self.remaining(), 1))
        if not facts:
            return ""
        return "\n".join([f"[harness record, {self.remaining():.0f}s left: exact results of your own commands]", *facts,
                           "Whatever is in the working directory when time runs out is what is delivered."])

    async def _regression(self, now: Check, then: Check) -> str:
        changed = sorted(p for p, h in then.files.items() if now.files.get(p) != h)
        lines = [f"[harness record] this command exited 0 at t={then.t:.0f}s and exits {now.exit} now."]
        if changed:
            lines.append("Files changed since then (retained byte copies are named where available):")
            for path in changed[:8]:
                location = await self._retained_location(path, then.files[path])
                label = json.dumps(location, ensure_ascii=True) if location else "no validated retained copy"
                lines.append(f"  {json.dumps(path, ensure_ascii=True)}: {label}")
        else:
            lines.append("No captured file hash differs; the snapshot does not cover all workspace state.")
        return "\n".join(lines)

    def _saved(self, path: str, digest: str) -> str:
        return f"{self.versions}/{digest}/{path}"

    async def _retained_location(self, path: str, digest: str) -> str | None:
        if (path, digest) not in self.retained:
            return None
        source = self._saved(path, digest)
        q = shlex.quote
        result = await run(self.env, f"(sha256sum < {q(source)} 2>/dev/null || shasum -a 256 < {q(source)})", timeout_s=30)
        if result.code == 0 and result.stdout.split()[:1] == [digest]:
            return source
        self.retained.discard((path, digest))
        self.trace("record_copy_unavailable", path=path, expected_sha256=digest)
        return None

    def _explicit_named_relative(self) -> list[str]:
        """Task-mentioned files inside workdir, bounded and without parent traversal."""
        base = posixpath.normpath(self.workdir)
        prefix = base.rstrip("/") + "/"
        out: list[str] = []
        control = posixpath.normpath(self.control_dir)
        for absolute in self.named[:20]:
            full = posixpath.normpath(absolute)
            if not full.startswith(prefix) or full == control or full.startswith(control.rstrip("/") + "/"):
                continue
            rel = full[len(prefix):]
            parts = rel.split("/")
            if (not rel or len(rel) > 4096 or
                    any(part in ("", ".", "..") or part in SKIP for part in parts)):
                continue
            out.append(rel)
        return sorted(set(out))

    async def snapshot(self, save: bool) -> dict[str, str]:
        """Bounded sample of named outputs and current files with newer mtime/ctime; hashes are observations, not complete custody.
        With ``save``, retain eligible byte copies whose content hashes match.
        """
        q = shlex.quote
        candidates = ["./" + p for p in self._explicit_named_relative()]
        candidates += await changed(self.env, self.workdir, self.control_dir)
        candidates = list(dict.fromkeys("./" + posixpath.normpath(p).removeprefix("./") for p in candidates))
        # Keep shell requests below Linux's per-argument limit even for deep
        # paths. Eligibility filtering happens remotely before the file cap.
        batches, batch, size = [], [], 0
        for path in candidates:
            cost = len(q(path).encode()) + 1
            if batch and size + cost > 32_000:
                batches.append(batch)
                batch, size = [], 0
            batch.append(path)
            size += cost
        if batch:
            batches.append(batch)
        files: dict[str, str] = {}
        store = q(self.versions)
        # Check every path component without line splitting or dirname's
        # newline-stripping command substitution. No symlink is followed for
        # source capture or retained-copy writes. This is not atomic custody.
        source_guard = (
            'rest=${f#./}; walk=.; safe=1; '
            'while :; do part=${rest%%/*}; walk="$walk/$part"; '
            '[ ! -L "$walk" ] || { safe=0; break; }; '
            'case "$rest" in */*) rest=${rest#*/};; *) break;; esac; done; '
            '[ "$safe" = 1 ] && [ -f "$f" ] || continue; '
            'size=$(wc -c < "$f") || exit 3; [ "$size" -lt 20000000 ] || continue; '
        )
        keep = (
            f'dest={store}/"$h"/"${{f#./}}"; walk={store}/"$h"; rest=${{f#./}}; safe=1; '
            f'[ ! -L {q(self.control_dir)} ] && [ ! -L {store} ] && [ ! -L "$walk" ] || safe=0; '
            'while :; do part=${rest%%/*}; walk="$walk/$part"; '
            '[ ! -L "$walk" ] || { safe=0; break; }; '
            'case "$rest" in */*) rest=${rest#*/};; *) break;; esac; done; '
            'if [ "$safe" = 1 ]; then '
            f'if [ ! -f "$dest" ] && [ "$size" -lt {SAVE_BYTES} ]; then '
            'parent=${dest%/*}; mkdir -p "$parent" && cp -p "$f" "$dest"; fi; '
            'if [ -f "$dest" ]; then ch=$(sha256sum < "$dest" 2>/dev/null || shasum -a 256 < "$dest") || exit 3; '
            '[ "${ch%% *}" = "$h" ] && kept=1; fi; fi; '
            if save else ""
        )
        for batch in batches:
            remaining = MAX_FILES - len(files)
            if remaining <= 0:
                break
            command = (
                f"cd {q(self.workdir)} || exit 3; count=0; for f in {' '.join(q(p) for p in batch)}; do "
                f'[ "$count" -lt {remaining} ] || break; '
                + source_guard
                + 'hash=$(sha256sum < "$f" 2>/dev/null || shasum -a 256 < "$f") || exit 3; '
                + 'h=${hash%% *}; kept=0; ' + keep
                + 'printf "%s\\0%s\\0%s\\0" "$h" "$kept" "${f#./}"; count=$((count+1)); done'
            )
            result = await run(self.env, command, timeout_s=max(5.0, min(60.0, self.remaining())))
            if result.code != 0:
                raise OSError(f"snapshot failed: {(result.stderr or result.stdout).strip()[:200]}")
            fields = result.stdout.split("\0")
            if fields[-1] != "" or (len(fields) - 1) % 3:
                raise OSError("snapshot failed: incomplete filename/digest record")
            allowed = {p.removeprefix("./") for p in batch}
            for index in range(0, len(fields) - 1, 3):
                digest, kept, path = fields[index:index + 3]
                if (not re.fullmatch(r"[0-9a-f]{64}", digest) or kept not in ("0", "1")
                        or path not in allowed or path in files):
                    raise OSError("snapshot failed: invalid filename/digest record")
                files[path] = digest
                if kept == "1":
                    self.retained.add((path, digest))
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
                line += f" (files changed since: {_display_paths(changed[:5])})" if changed else " (captured file hashes unchanged since; snapshot scope is limited)"
            lines.append(line)
        return "\n".join(lines)

    def _latest(self) -> list[Check]:
        """The newest run of each distinct check command, oldest first."""
        seen: dict[tuple[str, str], Check] = {}
        for c in self.checks:
            seen.pop((c.cwd, c.command), None)
            seen[(c.cwd, c.command)] = c
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
            not_run = task_commands.not_run(self.task_commands, self.executed)
            row.update(absent=absent, not_run=not_run, shown=self.task_commands, hold=bool(absent or not_run))
            self.trace("record_finish", **row)
            if not (absent or not_run):
                return False, "", row
            facts = [f"Paths the task names that do not exist: {_display_paths(absent)}."] if absent else []
            if not_run:
                facts.append("Commands the task shows that no input sent to a terminal in this run contained (the "
                             f"harness compares text only): {'; '.join(f'`{c}`' for c in not_run)}.")
            return True, (f"[finish not yet accepted] {' '.join(facts)} You have {self.remaining():.0f}s. "
                          "Act on this, or call finish again to finish as is."), row
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
        passed = {(c.cwd, c.command) for c in self.checks if c.passed}
        failing = [c for c in latest if c.failed and (c.cwd, c.command) in passed]
        reruns = await self._reruns(latest, delivered, row)
        broke = [r for r in reruns if r["exit"] not in (0, None)]
        row.update(failing=[short(c.command) for c in failing], reruns=reruns)
        measured = await self._measured(delivered, reruns) if self.measure else []
        absent = await self._absent() if self.measure else []
        if absent:
            measured.append(f"- Paths the task names that do not exist: {_display_paths(absent)}")
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
        lines.append(
            f"Retained byte copies are under {json.dumps(self.versions, ensure_ascii=True)}/<sha256>/<relative-path>; a command exit is not semantic correctness. You have {left:.0f}s. "
            "Fix what this shows, restore a saved version, or call finish again to finish as is."
        )
        return True, "\n".join(lines), row

    async def _reruns(self, latest: list[Check], delivered: dict[str, str], row: dict) -> list[dict[str, Any]]:
        # Never replay an arbitrary terminal command on the delivered workspace: undoing selected file
        # bytes cannot roll back new/deleted files, processes, external writes or mutable dependencies.
        row["reruns_skipped"] = "no isolated replay backend; original observations retained"
        return []

    async def _measured(self, delivered: dict[str, str], reruns: list[dict[str, Any]]) -> list[str]:
        """Facts comparing what checks printed across versions of the delivered files (measure)."""
        lines: list[str] = []
        runs: dict[tuple[str, str], list[Check]] = {}
        for c in self.checks:
            if c.passed:
                runs.setdefault((c.cwd, c.command), []).append(c)
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
                locations = []
                for p in old[:4]:
                    location = await self._retained_location(p, c.files[p])
                    locations.append(f"{json.dumps(p, ensure_ascii=True)} saved at {json.dumps(location, ensure_ascii=True)}" if location else f"{json.dumps(p, ensure_ascii=True)}: no validated retained copy")
                saved = ", ".join(locations)
                lines.append(f"    t={c.t:.0f}s: {' | '.join(then)}  ({saved})")
            _then, now = differing(earlier[-1][0].out, newest.out)
            lines.append(f"    newest, t={newest.t:.0f}s: {' | '.join(now) or '(none of those lines)'}")
        if self.checks:
            last = self.checks[-1]
            stale = sorted(p for p, h in delivered.items() if last.files.get(p) != h)
            if stale:
                lines.append(f"- Changed or created after your last check ran (t={last.t:.0f}s, "
                             f"`{short(last.command, 80)}`): {_display_paths(stale[:8])}")
        return lines

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
