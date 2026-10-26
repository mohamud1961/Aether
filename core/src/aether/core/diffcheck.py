"""Optional candidate-check mechanics (AETHER_CORE_DIFFCHECK).

The author currently runs in the solver's unrestricted environment and can read/change the candidate or race the
solver. The public start path therefore fails closed until the runtime provides actual isolation. A separate
directory and a prompt do not establish independence. Separating one supplied good/broken pair proves only that
those two samples are distinguished; it does not establish oracle correctness.
"""

from __future__ import annotations

import asyncio
import base64
import dataclasses
import hashlib
import json
import os
import re
import shlex
import uuid
from typing import Any, Awaitable, Callable

from .env import Environment, ExecResult, run
from .transfer import put_bytes
from .oversight import ReviewPlan

DIFFCHECK_ENV = "AETHER_CORE_DIFFCHECK"
DIFFCHECK_MODES = ("off", "on")
AUTHOR_ROLE = "diffcheck"
AUTHOR_SHARE, AUTHOR_MAX_S, AUTHOR_MIN_S = 0.35, 900.0, 120.0
CHECK_S, MIN_GAP_S, RESERVE_S = 300, 60.0, 90.0
SHOWN_CHARS = 2_500
MAX_CANDIDATE_BYTES = 16 * 1024 * 1024
TRACE_FILE = "diffcheck_trace.jsonl"
_UNVERIFIED_REASON = "same-container author has unrestricted solver-workspace access; no isolation certificate provider exists"

AUTHOR_BRIEF = """The author and solver currently share an unrestricted container. The author may see or change the \
candidate, and a prompt cannot enforce separation. Do not describe a result as independent. Separating one supplied \
good/broken pair demonstrates only discrimination of those two samples, not correctness of the check's oracle. Your \
task, if an isolated runtime explicitly enables it, is to write an executable check from task-supplied sources.

1. List each behaviour the task requires, quoting the task.
2. Identify the sources of truth available from the task and the files it supplies: an original implementation or \
program to stay equivalent to, a supplied evaluator or data, a documented format or interface, or a definition in \
the task you can compute directly. Prefer executing supplied originals over re-implementing them.
3. Build a reference for the required behaviour from those sources.
4. Choose inputs that discriminate: typical cases, boundaries, unusual combinations, and inputs beyond the examples \
the task gives.
   Where the task leaves a convention open (a tensor or matrix layout, an ordering, a number or text format, a \
rounding, an argument convention), do not pick one: accept every reading the task's wording allows, and flag a \
behaviour only if it is wrong under all of them.
5. Write {dir}/check.py: `python3 {dir}/check.py --candidate PATH` runs the candidate at PATH and the reference on \
the same inputs, through the interface the task specifies, prints each disagreement as input / expected / actual, \
and exits 1 on any disagreement, 2 if the check itself could not run, 0 if none. Under {check_s} seconds.
6. Write the absolute path of the file the task asks for (the candidate to check) as the only line of \
{dir}/target.
7. Validate: write {dir}/good_candidate.<ext> that follows the task (check exits 0) and \
{dir}/broken_candidate.<ext>, a plausible but wrong variant (check exits 1). The harness re-runs both and uses \
your check only if they behave so.

Rules: create, change or delete nothing outside {dir}. This is not enforced by the current shared environment. \
Do not report isolation or oracle correctness based only on the sample pair.

The task:
{task}"""

FOUND = """[candidate check result, provenance unverified: {target} disagrees]
The candidate check reported this difference (the check may be wrong):
{output}
This check separated one supplied good/broken pair; that does not establish oracle correctness. Re-run it: \
python3 {check} --candidate {target}"""
AGREES = "[candidate check result, provenance unverified: {target} agrees with the check; this does not establish task correctness (python3 {check} --candidate {target})]"
INCONCLUSIVE = "[candidate check inconclusive, provenance unverified: {target}: {reason}]"

_NOISE = re.compile(r"\b\d+(\.\d+)?\s*(ms|s|sec|seconds)\b|0x[0-9a-f]+", re.I)
_DISAGREEMENT = re.compile(r"input:\s*.+?\s*/\s*expected:\s*.+?\s*/\s*actual:\s*.+", re.I | re.S)


def author_config(config: Any) -> Any:
    """The solver's configuration for the author's run: its own role, control directory and context files, and no
    reviews, verifier, record, state or differential check of its own."""
    root = f"{config.control_dir}-diffcheck"
    return dataclasses.replace(
        config, role=AUTHOR_ROLE, diffcheck=False, verify=False, record=False, record_measure=False, record_paths=False,
        state=False, self_check=False, finish_hold="off", fork=False, control_dir=root,
        reviews=ReviewPlan(finish=False),
        clm=dataclasses.replace(config.clm, mirror_path=f"{root}/ctx/LIVE_CTX.txt",
                                history_path=f"{root}/ctx/HISTORY.txt"),
    )


def author_timeout(remaining: float) -> float | None:
    """The author's time: a share of what is left, bounded; None when too little is left to write a check."""
    t = min(AUTHOR_SHARE * remaining, AUTHOR_MAX_S)
    return t if t >= AUTHOR_MIN_S else None


class DiffCheck:
    """``author(brief, timeout_s)`` runs the check's author (the loop passes a fresh Core run in the check directory)."""

    def __init__(self, env: Environment, task: str, check_dir: str, remaining: Callable[[], float],
                 trace: Callable[..., None], author: Callable[[str, float], Awaitable[Any]],
                 clock: Callable[[], float]) -> None:
        self.env, self.task, self.dir = env, task, check_dir
        self.remaining, self.trace, self._author, self.clock = remaining, trace, author, clock
        self.check, self.target = f"{check_dir}/check.py", ""
        self.source = b""  # the accepted check, held by the harness
        self.state = "idle"  # idle | unverified | authoring | ready | rejected | failed | cancelled
        self.job: asyncio.Task[Any] | None = None
        self.last_sha = self.last_shown = ""
        self.last_run = -MIN_GAP_S
        self.runs: list[dict[str, Any]] = []
        self.errors = 0
        self._started = False
        self._accepted_manifest: dict[str, str] = {}
        self._seen_hashes: set[str] = set()
        self._last_input_issue = ""
        self.validation = "not_run"

    def start(self) -> None:
        """Fail closed: this source has no runtime-provided isolation certificate."""
        if self._started:
            return
        self._started = True
        self.state = "unverified"
        self.trace("diffcheck_admission_blocked", reason=_UNVERIFIED_REASON,
                   provenance="unverified", author_started=False)

    async def after_action(self) -> str:
        """Called after each tool result; returns a note for the solver ('' when there is none)."""
        try:
            if self.state == "authoring" and self.job is not None and self.job.done():
                await self._accept()
            if self.state != "ready" or self.remaining() < RESERVE_S:
                return ""
            return await self._run()
        except Exception as exc:  # an instrument: its failure is traced, the run goes on
            self.errors += 1
            self.trace("diffcheck_error", error=f"{type(exc).__name__}: {exc}")
            return ""

    async def _accept(self) -> None:
        if self.job is None:
            self.state = "failed"
            self.trace("diffcheck_author_failed", reason="missing author task")
            return
        if self.job.cancelled():
            self.state = "cancelled"
            self.trace("diffcheck_author_cancelled", reason="author task cancelled before acceptance")
            return
        try:
            result = self.job.result()
        except Exception as exc:
            self.state = "failed"
            self.trace("diffcheck_author_failed", error=f"{type(exc).__name__}: {exc}")
            return
        status = getattr(result, "status", None)
        if status != "finished":
            self.state = "failed"
            self.trace("diffcheck_author_inconclusive", status=status or "missing_status",
                       reason="author did not finish successfully")
            return
        q = shlex.quote
        found = await run(self.env, f"cat {q(self.dir)}/target 2>/dev/null | head -1; echo; "
                          f"ls {q(self.dir)} 2>/dev/null; echo; base64 < {q(self.check)} 2>/dev/null | tr -d '\\n'",
                          timeout_s=30)
        head, _, rest = found.stdout.partition("\n\n")
        listing, _, encoded = rest.partition("\n\n")
        self.target = head.strip().splitlines()[0].strip() if head.strip() else ""
        names = listing.split()
        good = next((n for n in names if n.startswith("good_candidate")), "")
        broken = next((n for n in names if n.startswith("broken_candidate")), "")
        if not (self.target.startswith("/") and good and broken and encoded.strip()):
            self.state = "rejected"
            self.trace("diffcheck_rejected", reason="incomplete", target=self.target, files=names)
            return
        self.source = base64.b64decode(encoded.strip())
        self.validation = "two_sample_discrimination_only"
        self._accepted_manifest = await self._manifest()
        if any(value in {"symlink", "unreadable", "non_regular"} for value in self._accepted_manifest.values()):
            self.state = "rejected"
            self.trace("diffcheck_rejected", reason="checker inputs contain non-regular or unreadable files")
            return
        codes = {}
        for name in (good, broken):
            r = await self._exec(f"{self.dir}/{name}")
            codes[name] = r.code
            if r.code is None or r.code not in (0, 1):
                self.state = "rejected"
                self.trace("diffcheck_rejected", reason="two-sample validation inconclusive", exits=codes,
                           validation="two_sample_discrimination_only", oracle_correctness="unverified")
                return
        if codes[good] != 0 or codes[broken] != 1:
            self.state = "rejected"
            self.trace("diffcheck_rejected", reason="does not separate its two supplied samples", exits=codes,
                       validation="two_sample_discrimination_only", oracle_correctness="unverified")
            return
        if await self._manifest() != self._accepted_manifest:
            self.state = "rejected"
            self.trace("diffcheck_rejected", reason="checker or support inputs changed during sample validation",
                       validation="two_sample_discrimination_only", oracle_correctness="unverified")
            return
        self.state = "ready"
        self.trace("diffcheck_candidate_ready_unverified", target=self.target,
                   check_sha256=hashlib.sha256(self.source).hexdigest(), exits=codes,
                   validation="two_sample_discrimination_only", oracle_correctness="unverified",
                   provenance="unverified")

    async def _manifest(self) -> dict[str, str]:
        """Return hashes of every regular file under the check directory, including support dependencies."""
        script = """import hashlib,json,os,stat,sys
root=os.path.abspath(sys.argv[1]); out={}
for base,dirs,files in os.walk(root,followlinks=False):
    for name in list(dirs):
        path=os.path.join(base,name); rel=os.path.relpath(path,root)
        try: mode=os.lstat(path).st_mode
        except OSError: out[rel]="unreadable"; dirs.remove(name); continue
        if stat.S_ISLNK(mode): out[rel]="symlink"; dirs.remove(name)
    for name in sorted(files):
        path=os.path.join(base,name); rel=os.path.relpath(path,root)
        try: mode=os.lstat(path).st_mode
        except OSError: out[rel]="unreadable"; continue
        if stat.S_ISLNK(mode): out[rel]="symlink"; continue
        if not stat.S_ISREG(mode): out[rel]="non_regular"; continue
        h=hashlib.sha256()
        try:
            with open(path,"rb") as f:
                for b in iter(lambda:f.read(1024*1024),b""): h.update(b)
            out[rel]=h.hexdigest()
        except OSError: out[rel]="unreadable"
print(json.dumps(out,sort_keys=True))
"""
        result = await run(self.env, f"python3 -c {shlex.quote(script)} {shlex.quote(self.dir)}", timeout_s=30)
        if result.code != 0:
            raise OSError(f"checker-input manifest failed: {result.stderr or result.stdout}")
        manifest = json.loads(result.stdout)
        if not isinstance(manifest, dict):
            raise ValueError("checker-input manifest is not an object")
        return manifest

    async def _exec(self, candidate: str) -> Any:
        q = shlex.quote
        bound = f"$(command -v timeout >/dev/null 2>&1 && echo 'timeout {CHECK_S}')"  # not every image has it
        command = f"cd {q(self.dir)} && {bound} python3 -B {q(self.check)} --candidate {q(candidate)} 2>&1"
        try:
            async with asyncio.timeout(CHECK_S):
                return await run(self.env, command, timeout_s=CHECK_S + 1)
        except (TimeoutError, asyncio.TimeoutError):
            return ExecResult(124, "", "checker timed out")

    async def _run(self) -> str:
        issue = await self._verify_inputs()
        if issue is not None:
            return issue
        digest, snapshot, failure = await self._snapshot_target()
        if failure == "missing":
            return self._inconclusive("target_missing", self.target, "candidate file is missing")
        if failure == "too_large":
            return self._inconclusive("target_too_large", self.target,
                                      f"candidate exceeds {MAX_CANDIDATE_BYTES} byte snapshot limit")
        if failure:
            return self._inconclusive("target_unstable", self.target, "candidate changed while snapshotting")
        if digest in self._seen_hashes:
            await self._remove_snapshot(snapshot)
            return ""
        if self.clock() - self.last_run < MIN_GAP_S:
            await self._remove_snapshot(snapshot)
            return ""
        # An artifact identity gets at most one attempt, including when the checker is inconclusive.
        self._seen_hashes.add(digest)
        self.last_sha, self.last_run = digest, self.clock()
        try:
            result = await self._exec(snapshot)
        except (TimeoutError, asyncio.TimeoutError):
            await self._remove_snapshot(snapshot)
            self.runs.append({"t": round(self.clock(), 1), "sha": digest, "exit": None, "status": "timeout"})
            self.trace("diffcheck_run_inconclusive", target=self.target, sha256=digest,
                       reason="checker timed out", provenance="unverified")
            return INCONCLUSIVE.format(target=self.target, reason="checker timed out")
        await self._remove_snapshot(snapshot)
        if await self._target_hash() != digest:
            self.runs.append({"t": round(self.clock(), 1), "sha": digest, "exit": result.code,
                              "status": "inconclusive_changed_during_check"})
            self.trace("diffcheck_run_inconclusive", target=self.target, sha256=digest,
                       reason="candidate changed during check", exit=result.code, provenance="unverified")
            return INCONCLUSIVE.format(target=self.target, reason="candidate changed during check")
        issue = await self._verify_inputs(after_check=True)
        if issue is not None:
            self.runs.append({"t": round(self.clock(), 1), "sha": digest, "exit": result.code,
                              "status": "inconclusive_checker_inputs_changed"})
            return issue or INCONCLUSIVE.format(target=self.target, reason="checker/support files changed")
        out = result.stdout.strip()
        if result.code is None or result.code not in (0, 1):
            reason = "checker timed out" if result.code == 124 else f"checker exited inconclusively ({result.code})"
            self.runs.append({"t": round(self.clock(), 1), "sha": digest, "exit": result.code,
                              "status": "inconclusive"})
            self.trace("diffcheck_run_inconclusive", target=self.target, sha256=digest, exit=result.code,
                       reason=reason, output=out[-SHOWN_CHARS:], provenance="unverified")
            return INCONCLUSIVE.format(target=self.target, reason=reason)
        status = "agrees" if result.code == 0 else "disagrees"
        if result.code == 1 and not _DISAGREEMENT.search(out):
            status = "inconclusive"
        self.runs.append({"t": round(self.clock(), 1), "sha": digest, "exit": result.code, "status": status})
        self.trace("diffcheck_run", target=self.target, sha256=digest, exit=result.code, status=status,
                   output=out[-SHOWN_CHARS:], provenance="unverified")
        if status == "disagrees":
            key = _NOISE.sub("", out)
            if key == self.last_shown:
                return ""
            self.last_shown = key
            return FOUND.format(target=self.target, output=out[-SHOWN_CHARS:], check=self.check)
        if status == "inconclusive":
            return INCONCLUSIVE.format(target=self.target, reason="exit 1 without input/expected/actual evidence")
        if status == "agrees" and self.last_shown:
            self.last_shown = ""
            return AGREES.format(target=self.target, check=self.check)
        return ""

    async def _verify_inputs(self, *, after_check: bool = False) -> str | None:
        """Restore the checker source; refuse to run when any other checker/support file changed or disappeared."""
        if not self._accepted_manifest:
            return self._inconclusive("missing_input_manifest", self.dir, "checker inputs were not sealed")
        current = await self._manifest()
        changed = sorted(name for name in set(current) | set(self._accepted_manifest)
                         if current.get(name) != self._accepted_manifest.get(name))
        if "check.py" in changed:
            await put_bytes(self.env, self.source, self.check)
            self.trace("diffcheck_check_restored", check=self.check, reason="checker source changed or deleted")
            if after_check:
                return self._inconclusive("checker_changed_during_check", self.check,
                                          "checker source changed during check")
            current = await self._manifest()
            changed = sorted(name for name in set(current) | set(self._accepted_manifest)
                             if current.get(name) != self._accepted_manifest.get(name))
        if changed:
            fingerprint = hashlib.sha256(json.dumps(current, sort_keys=True).encode()).hexdigest()
            return self._inconclusive("checker_inputs_changed", ", ".join(changed),
                                      "checker/support files changed or were deleted", fingerprint)
        self._last_input_issue = ""
        return None

    def _inconclusive(self, kind: str, target: str, reason: str, fingerprint: str = "") -> str:
        identity = f"{kind}:{fingerprint or target}"
        if identity == self._last_input_issue:
            return ""
        self._last_input_issue = identity
        self.trace("diffcheck_input_inconclusive", kind=kind, target=target, reason=reason,
                   provenance="unverified")
        return INCONCLUSIVE.format(target=target, reason=reason)

    async def _snapshot_target(self) -> tuple[str, str, str]:
        """Take a stable full-content snapshot before running the checker."""
        suffix = os.path.splitext(self.target)[1] or ".candidate"
        snapshot = os.path.join(os.path.dirname(self.target), f".aether-diffcheck-{uuid.uuid4().hex}{suffix}")
        script = """import hashlib,json,os,stat,sys,tempfile
src,dst=sys.argv[1:3]; limit=int(sys.argv[3])
try: before=os.lstat(src)
except FileNotFoundError:
    print(json.dumps({"status":"missing"})); sys.exit(3)
if not stat.S_ISREG(before.st_mode):
    print(json.dumps({"status":"unstable"})); sys.exit(4)
if before.st_size > limit:
    print(json.dumps({"status":"too_large"})); sys.exit(6)
try:
    with open(src,"rb") as f: data=f.read(limit+1)
    after=os.lstat(src)
except FileNotFoundError:
    print(json.dumps({"status":"unstable"})); sys.exit(5)
if len(data) > limit:
    print(json.dumps({"status":"too_large"})); sys.exit(6)
if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns) or len(data)!=after.st_size:
    print(json.dumps({"status":"unstable"})); sys.exit(5)
h=hashlib.sha256(data).hexdigest(); parent=os.path.dirname(dst) or "."; os.makedirs(parent,exist_ok=True)
fd,tmp=tempfile.mkstemp(prefix=".diffcheck-",dir=parent)
try:
    with os.fdopen(fd,"wb") as f: f.write(data); f.flush(); os.fsync(f.fileno())
    os.chmod(tmp,stat.S_IMODE(before.st_mode))
    os.replace(tmp,dst)
except BaseException:
    try: os.unlink(tmp)
    except OSError: pass
    raise
print(json.dumps({"status":"ok","sha256":h}))
"""
        result = await run(self.env, f"python3 -c {shlex.quote(script)} {shlex.quote(self.target)} "
                           f"{shlex.quote(snapshot)} {MAX_CANDIDATE_BYTES}", timeout_s=30)
        try:
            payload = json.loads(result.stdout)
        except (ValueError, TypeError):
            return "", snapshot, "unstable"
        if payload.get("status") != "ok":
            return "", snapshot, payload.get("status", "unstable")
        return payload["sha256"], snapshot, ""

    async def _target_hash(self) -> str | None:
        script = "import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())"
        result = await run(self.env, f"python3 -c {shlex.quote(script)} {shlex.quote(self.target)} 2>/dev/null",
                           timeout_s=30)
        return result.stdout.strip() if result.code == 0 else None

    async def _remove_snapshot(self, snapshot: str) -> None:
        await run(self.env, f"rm -f -- {shlex.quote(snapshot)}", timeout_s=10)

    async def close(self) -> None:
        if self.job is not None and not self.job.done():
            self.job.cancel()
            try:
                await self.job
            except BaseException:  # the author's cancellation is the expected outcome here
                pass
            self.state = "cancelled"
            self.trace("diffcheck_author_cancelled", reason="author task cancelled during close")

    def summary(self) -> dict[str, Any]:
        return {"state": self.state, "target": self.target, "runs": self.runs, "errors": self.errors,
                "shown": sum(1 for r in self.runs if r.get("status") == "disagrees"),
                "provenance": "unverified", "oracle_correctness": "unverified",
                "validation": self.validation}
