"""Optional candidate-check mechanics (AETHER_CORE_DIFFCHECK).

Isolated mode (a clone factory is given; Harbor docker): before the solver's first action the task container is
committed and started as a separate, no-network container (the box). The author, a second Core run of the same model
with a fresh context, works only in the box, from the task text alone: it never sees the solver's files, actions or
reasoning, and the solver cannot reach the check. Each new version of the target file is copied into the box and the
check runs there. A disagreement reaches the solver with the check's own input / expected / actual lines; at the
first finish, the check runs once more on the final file (waiting for the author when time allows) and a
disagreement holds that finish once. A second finish always takes effect. The check is the same model's reading of
the task and can be wrong; the solver decides.

Without a factory the author would run in the solver's unrestricted environment and can read/change the candidate or race the
solver. That path therefore fails closed in the solver's unrestricted environment and can read/change the candidate or race the
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
from .transfer import get_bytes, put_bytes
from .oversight import ReviewPlan
from .diffcheck_text import AGREES, AGREES_ISOLATED, FINISH_HOLD, FOUND, FOUND_ISOLATED, INCONCLUSIVE, ISOLATED_BRIEF

DIFFCHECK_ENV = "AETHER_CORE_DIFFCHECK"
DIFFCHECK_MODES = ("off", "on")
AUTHOR_ROLE = "diffcheck"
AUTHOR_SHARE, AUTHOR_MAX_S, AUTHOR_MIN_S = 0.6, 900.0, 120.0  # 0.35 timed out authors (y2, 28 Oct)
CHECK_S, MIN_GAP_S, RESERVE_S = 300, 60.0, 90.0
SHOWN_CHARS = 2_500
MAX_CANDIDATE_BYTES = 16 * 1024 * 1024
TRACE_FILE = "diffcheck_trace.jsonl"
_UNVERIFIED_REASON = "same-container author has unrestricted solver-workspace access; no isolation certificate provider exists"

_NOISE = re.compile(r"\b\d+(\.\d+)?\s*(ms|s|sec|seconds)\b|0x[0-9a-f]+", re.I)
# input / expected / actual, separated by " / " or by line breaks (authors write both)
_DISAGREEMENT = re.compile(r"input:\s*.+?\s*(/|\n)\s*expected:\s*.+?\s*(/|\n)\s*actual:\s*.+", re.I | re.S)


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
                 trace: Callable[..., None], author: Callable[..., Awaitable[Any]],
                 clock: Callable[[], float], box: Callable[[float], Awaitable[Any]] | None = None) -> None:
        self.env, self.task, self.dir = env, task, check_dir
        self._box_factory, self.box, self.held = box, None, False  # isolated mode: the author's own container
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
        self.last_output = ""

    @property
    def cenv(self) -> Environment:
        """Where the check lives and runs: the box in isolated mode."""
        return self.box if self.box is not None else self.env

    async def start(self) -> None:
        """Isolated mode: commit the box now (before the solver acts), then author in it in the background.
        Without a box factory, fail closed: this source has no runtime-provided isolation."""
        if self._started:
            return
        self._started = True
        if self._box_factory is None:
            self.state = "unverified"
            self.trace("diffcheck_admission_blocked", reason=_UNVERIFIED_REASON,
                       provenance="unverified", author_started=False)
            return
        timeout = author_timeout(self.remaining())
        if timeout is None:
            self.trace("diffcheck_skipped", reason="too little time", remaining_s=round(self.remaining()))
            return
        t0 = self.clock()
        try:
            self.box = await self._box_factory(min(300.0, timeout))
            probe = await run(self.box, f"mkdir -p {shlex.quote(self.dir)} && command -v python3", timeout_s=30)
        except Exception as exc:  # an instrument: no box, no check; the run goes on
            self.state = "failed"
            self.trace("diffcheck_box_failed", error=f"{type(exc).__name__}: {exc}"[:500])
            return
        if probe.code != 0:  # the check and its harness-side manifest run on python3
            self.state = "failed"
            self.trace("diffcheck_skipped", reason="no python3 in the task container")
            return
        timeout = author_timeout(self.remaining()) or AUTHOR_MIN_S
        brief = ISOLATED_BRIEF.format(dir=self.dir, task=self.task, check_s=CHECK_S)
        self.state, self.job = "authoring", asyncio.ensure_future(self._author(brief, timeout, self.box))
        self.trace("diffcheck_author_started", timeout_s=round(timeout), box_s=round(self.clock() - t0, 1),
                   provenance="isolated_clone")

    async def at_finish(self) -> str:
        """The first finish: run the check on the final file (waiting for the author while time allows). A
        disagreement holds this finish once ('' = the finish takes effect)."""
        if self.held or self.box is None:
            return ""
        try:
            if self.state == "authoring" and self.job is not None:
                wait = self.remaining() - RESERVE_S - CHECK_S
                if wait > 0:
                    self.trace("diffcheck_finish_wait", max_s=round(wait))
                    await asyncio.wait({self.job}, timeout=wait)
                if self.job.done():
                    await self._accept()
            if self.state != "ready" or self.remaining() < RESERVE_S:
                self.trace("diffcheck_finish", state=self.state, held=False)
                return ""
            note = await self._run(force=True)
        except Exception as exc:
            self.errors += 1
            self.trace("diffcheck_error", error=f"{type(exc).__name__}: {exc}")
            return ""
        held = note.startswith("[independent check:") and "disagrees" in note.split("\n", 1)[0]
        self.trace("diffcheck_finish", state=self.state, held=held)
        if held:
            self.held = True
            return note + FINISH_HOLD
        return ""

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
        found = await run(self.cenv, f"cat {q(self.dir)}/target 2>/dev/null | head -1; echo; "
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
        if self.box is not None:
            try:  # a readable copy for the solver; the harness runs only its own copy, in the box
                await put_bytes(self.env, self.source, self._copy())
            except OSError as exc:
                self.trace("diffcheck_copy_failed", error=str(exc)[:300])
            self.trace("diffcheck_ready", target=self.target, check_sha256=hashlib.sha256(self.source).hexdigest(),
                       exits=codes, provenance="isolated_clone")
            return
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
        result = await run(self.cenv, f"python3 -c {shlex.quote(script)} {shlex.quote(self.dir)}", timeout_s=30)
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
                return await run(self.cenv, command, timeout_s=CHECK_S + 1)
        except (TimeoutError, asyncio.TimeoutError):
            return ExecResult(124, "", "checker timed out")

    def _copy(self) -> str:
        return f"{self.dir}/check.py"

    async def _run(self, force: bool = False) -> str:
        issue = await self._verify_inputs()
        if issue is not None:
            return issue
        digest, snapshot, failure = await (self._snapshot_into_box() if self.box is not None
                                           else self._snapshot_target())
        if failure == "missing":
            return self._inconclusive("target_missing", self.target, "candidate file is missing")
        if failure == "too_large":
            return self._inconclusive("target_too_large", self.target,
                                      f"candidate exceeds {MAX_CANDIDATE_BYTES} byte snapshot limit")
        if failure:
            return self._inconclusive("target_unstable", self.target, "candidate changed while snapshotting")
        if digest in self._seen_hashes and not (force and digest == self.last_sha and self.last_shown):
            await self._remove_snapshot(snapshot)
            return ""
        if force and digest in self._seen_hashes:  # the final file is the one already shown disagreeing
            await self._remove_snapshot(snapshot)
            return self._found(self.last_output)
        if not force and self.clock() - self.last_run < MIN_GAP_S:
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
            self.last_output = out[-SHOWN_CHARS:]
            if key == self.last_shown and not force:
                return ""
            self.last_shown = key
            return self._found(self.last_output)
        if status == "inconclusive":
            return INCONCLUSIVE.format(target=self.target, reason="exit 1 without input/expected/actual evidence")
        if status == "agrees" and self.last_shown:
            self.last_shown = ""
            if self.box is not None:
                return AGREES_ISOLATED.format(target=self.target)
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
            await put_bytes(self.cenv, self.source, self.check)
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

    def _found(self, output: str) -> str:
        if self.box is not None:
            return FOUND_ISOLATED.format(target=self.target, output=output, copy=self._copy())
        return FOUND.format(target=self.target, output=output, check=self.check)

    async def _snapshot_into_box(self) -> tuple[str, str, str]:
        """Copy the solver's target file into the box (isolated mode)."""
        q = shlex.quote
        probe = ("import os,stat,sys; s=os.lstat(sys.argv[1]); "
                 "print(s.st_size, oct(stat.S_IMODE(s.st_mode))[2:]) if stat.S_ISREG(s.st_mode) else sys.exit(3)")
        st = await run(self.env, f"python3 -c {q(probe)} {q(self.target)} 2>/dev/null", timeout_s=30)
        if st.code != 0 or not st.stdout.strip():
            return "", "", "missing"
        size, mode = st.stdout.split()[:2]
        if int(size) > MAX_CANDIDATE_BYTES:
            return "", "", "too_large"
        data = await get_bytes(self.env, self.target)
        if len(data) != int(size):
            return "", "", "unstable"
        suffix = os.path.splitext(self.target)[1] or ".candidate"
        snapshot = f"{self.dir}/.candidate-{uuid.uuid4().hex[:8]}{suffix}"
        await put_bytes(self.box, data, snapshot, mode=mode)
        return hashlib.sha256(data).hexdigest(), snapshot, ""

    async def _target_hash(self) -> str | None:
        script = "import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())"
        result = await run(self.env, f"python3 -c {shlex.quote(script)} {shlex.quote(self.target)} 2>/dev/null",
                           timeout_s=30)
        return result.stdout.strip() if result.code == 0 else None

    async def _remove_snapshot(self, snapshot: str) -> None:
        if not snapshot:
            return
        await run(self.cenv, f"rm -f -- {shlex.quote(snapshot)}", timeout_s=10)

    async def close(self) -> None:
        if self.job is not None and not self.job.done():
            self.job.cancel()
            try:
                await self.job
            except BaseException:  # the author's cancellation is the expected outcome here
                pass
            self.state = "cancelled"
            self.trace("diffcheck_author_cancelled", reason="author task cancelled during close")
        if self.box is not None:
            try:
                await self.box.close()
            except Exception as exc:
                self.trace("diffcheck_box_close_failed", error=f"{type(exc).__name__}: {exc}"[:300])

    def summary(self) -> dict[str, Any]:
        return {"state": self.state, "target": self.target, "runs": self.runs, "errors": self.errors,
                "shown": sum(1 for r in self.runs if r.get("status") == "disagrees"),
                "provenance": "isolated_clone" if self.box is not None else "unverified",
                "oracle_correctness": "unverified", "held": self.held,
                "validation": self.validation}
