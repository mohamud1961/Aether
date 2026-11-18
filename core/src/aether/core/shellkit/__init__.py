"""Shell kit (AETHER_CORE_SHELL_KIT=on, default off): Core's work tools as terminal commands.

Why (18 Nov Core census, 3,231 Luna runs; research/codex_gap_20261117/FINDINGS.md): Luna works in the terminal
(70% of calls, 73 h), chains commands (66% chain 3+ steps) and almost never makes two tool calls in one turn (35 of
72,600 turns). Work that needs a separate tool call breaks the chain: an edit, an image, a background job, a context
trim. The kit puts each one where Luna already works:

- ``apply_patch``: a Codex patch on stdin, all files or none (the same parser as the apply_patch tool, patch_text.py);
- ``view_image PATH...``: images shown after the command;
- ``job start|wait|status|log|kill``: named background work; Core says when a job ends (next tool result);
- ``pyk``: one persistent Python process reachable from any command chain;
- ``ctx list|drop|stub``: precise context pruning (whole turns, or one long output replaced by a saved-file note)
  instead of rewriting the mirror (1,522 context edits: median 1,947 chars written, ~95% of the context dropped).

Core facts only: the commands report what they did; nothing here reads or interprets the task.
"""

from __future__ import annotations

import copy
import os
import re
import shlex
from pathlib import Path
from typing import Any

from .. import box_python, images
from ..clm_mirror import TURN_RE
from ..env import get_bytes, put_bytes, run
from . import scripts

PY_SOURCES = ("patch_cli.py", "pyk.py")


def describe(python: bool, ctx: bool) -> str:
    """The terminal tool's extra description: only the commands that work in this run."""
    parts = ["view_image PATH... (the images are shown after the command)",
             "job start NAME 'CMD' | job wait NAME [SECONDS] | job status | job log NAME [LINES] | job kill NAME "
             "(background work; you are told when a job ends)"]
    if python:
        parts += ["apply_patch <<'EOF' with a patch (*** Begin Patch / *** Update File: path / @@ / -old / +new / "
                  "*** End Patch; also *** Add File:, *** Delete File:): every file or none is written",
                  "pyk 'CODE' or pyk <<'EOF' (one Python process whose variables and loaded data survive between "
                  "calls; pyk --reset ends it)"]
    if ctx:
        parts.append("ctx list | ctx drop TURN... | ctx stub TURN... (TURN is N or N-M from ctx list: drop removes "
                     "whole turns from your context, stub replaces an output with a note naming a file that keeps it; "
                     "applies to your next request)")
    return " Commands in this terminal, usable in any command chain: " + "; ".join(parts) + "."


def with_commands(spec: dict[str, Any], extra: str) -> dict[str, Any]:
    if spec.get("function", {}).get("name") != "terminal":
        return spec
    out = copy.deepcopy(spec)
    out["function"]["description"] += extra
    return out


class Kit:
    def __init__(self, python: str, ctx_path: str, root: str = scripts.ROOT) -> None:
        self.python, self.ctx_path, self.root = python, ctx_path, root
        self.jobs: set[str] = set()

    @property
    def init(self) -> str:
        """Appended to each new terminal's start line."""
        env = {"AETHER_KIT_PY": self.python, "AETHER_CTX": self.ctx_path, "AETHER_KIT_ROOT": self.root}
        return f"export PATH={shlex.quote(self.root)}/bin:$PATH " + " ".join(f"{k}={shlex.quote(v)}" for k, v in env.items()) + "\n"

    async def after(self, s: Any, name: str, out: str) -> str:
        """Act on what the call's kit commands queued, and report jobs that ended. One exec; none when idle."""
        if name != "terminal" and not self.jobs:
            return out
        scan = await run(s.env, scripts.scan(self.root), timeout_s=30)
        notes, ops = [], []
        for line in scan.stdout.splitlines():
            kind, _, rest = line.partition("\t")
            if kind == "view":
                notes.append(await self._view(s, rest))
            elif kind == "jobstart":
                self.jobs.add(rest)
            elif kind == "jobdone":
                job, _, code = rest.partition("\t")
                self.jobs.discard(job)
                notes.append(f"[job {job} ended: exit {code}; job log {job} shows its output]")
            elif kind == "ctx":
                ops.append(tuple(rest.split("\t", 1)))
        if ops:
            notes.append(await self._ctx(s, ops))
        if notes:
            s.trace("shell_kit", call=name, notes=notes)
        return "\n".join([out, *notes]) if notes else out

    async def _view(self, s: Any, path: str) -> str:
        if not (s.config.images and images.available()):
            return f"[view_image {path}: images are not available in this run]"
        full = getattr(s.config, "image_fidelity", "standard") == "original"
        side, detail = (images.FULL_MAX_SIDE, images.FULL_DETAIL) if full else (images.MAX_SIDE, None)
        try:
            desc, url = await images.load(s.env, path, max_side=side)
        except Exception as exc:  # stated to the model, as the view_image tool states it
            return f"[view_image {path}: {type(exc).__name__}: {str(exc)[:200]}]"
        s.pending_images.append(images.message(desc, url, detail))
        s.images_viewed += 1
        return f"[image {desc}; shown below]"

    async def _ctx(self, s: Any, ops: list[tuple[str, ...]]) -> str:
        if not s.clm:
            return "[ctx: no editable context in this run]"
        text = (await get_bytes(s.env, self.ctx_path)).decode("utf-8", "replace")
        new, report = edit(text, ops, f"{self.root}/ctx")
        if new != text:
            await put_bytes(s.env, new.encode(), self.ctx_path)  # read back at the end of the turn, as a mirror edit
        return report


def _turns(spec: str) -> list[int]:
    out = []
    for part in spec.split():
        a, _, b = part.partition("-")
        out += list(range(int(a), int(b or a) + 1))
    return out


def edit(text: str, ops: list[tuple[str, ...]], saved_dir: str = scripts.ROOT + "/ctx") -> tuple[str, str]:
    """(new mirror text, one-line report). drop takes whole turns: a call with all of its results."""
    marks = list(TURN_RE.finditer(text))
    blocks = [(int(m.group(1)), m.group(2), m.start(), marks[k + 1].start() if k + 1 < len(marks) else len(text))
              for k, m in enumerate(marks)]
    at = {n: k for k, (n, *_) in enumerate(blocks)}
    drop: set[int] = set()
    stub: set[int] = set()
    errors: list[str] = []
    for op in ops:
        verb, spec = op[0], op[1] if len(op) > 1 else ""
        for n in _turns(spec):
            if n not in at:
                errors.append(f"turn {n} is not in your context")
            elif verb == "stub":
                if blocks[at[n]][1] == "assistant":
                    errors.append(f"turn {n} is your own turn: stub replaces outputs; drop removes a whole turn")
                else:
                    stub.add(n)
            else:
                k = at[n]
                while blocks[k][1] == "tool" and k > 0 and blocks[k - 1][1] in ("tool", "assistant"):
                    k -= 1  # a result belongs to the call before it
                drop.add(blocks[k][0])
                k += 1
                if blocks[k - 1][1] == "assistant":
                    while k < len(blocks) and blocks[k][1] == "tool":
                        drop.add(blocks[k][0])
                        k += 1
    pieces, removed = [], 0
    for n, role, start, end in blocks:
        body = text[start:end]
        if n in drop:
            removed += len(body)
            continue
        if n in stub:
            header, _, content = body.partition("\n")
            saved = f"{saved_dir}/turn-{n}.txt"
            note = f"[output removed by ctx stub; its full text ({len(content)} chars) is saved in {saved}]\n"
            removed += len(content) - len(note)
            body = f"{header}\n{note}"
        pieces.append(body)
    new = text[: blocks[0][2]] + "".join(pieces) if blocks else text
    done = []
    if drop:
        done.append(f"dropped turns {_ranges(sorted(drop))}")
    if stub:
        done.append(f"stubbed turns {_ranges(sorted(stub))}")
    report = "[ctx: " + ("; ".join(done) or "nothing changed")
    report += f"; ~{max(removed, 0) // 4} tokens fewer from your next request" if done else ""
    return new, report + ("; " + "; ".join(errors) if errors else "") + "]"


def _ranges(ns: list[int]) -> str:
    out: list[str] = []
    for n in ns:
        if out and re.fullmatch(rf"(\d+-)?{n - 1}", out[-1]):
            out[-1] = f"{out[-1].split('-')[0]}-{n}"
        else:
            out.append(str(n))
    return ",".join(out)


async def start(s: Any, root: str = "") -> Kit:
    """Install the kit in the task container and have every new terminal put it on PATH."""
    root = root or scripts.ROOT
    found = await run(s.env, "command -v python3", timeout_s=30)
    python, how = found.stdout.strip(), "task python3"
    tarball = os.environ.get(box_python.REPL_PYTHON_ENV, "")
    if found.code != 0 or not python:
        python, how = await box_python.install(s.env, tarball, box_python.REPL_ROOT) if tarball else ("", "none")
    here = Path(__file__).parent
    sources = {name: (here / name).read_text() for name in PY_SOURCES}
    sources["patch_text.py"] = (here.parent / "patch_text.py").read_text()
    kit_files = scripts.files(root, sources)
    await run(s.env, "mkdir -p " + " ".join(shlex.quote(f"{root}/{d}") for d in ("kit", "bin", "jobs")), timeout_s=30)
    for path, (text, _) in kit_files.items():
        await put_bytes(s.env, text.encode(), path)
    executables = " ".join(shlex.quote(p) for p, (_, x) in kit_files.items() if x)
    await run(s.env, f"chmod 755 {executables}", timeout_s=30)
    clm = s.config.clm if s.config.context == "clm" else None  # the CLM context itself is built after the tools
    kit = Kit(python, clm.mirror_path if clm else "", root)
    s.terminals.extra_init = kit.init
    s.trace("shell_kit_installed", python=python or None, how=how, ctx=bool(clm))
    return kit
