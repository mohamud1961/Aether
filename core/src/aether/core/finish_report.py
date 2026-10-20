"""Finish report: what the run delivered and did, from the harness's own records, beside the model's account.

Audits found final summaries that the delivered state contradicts ("17 documents ... 10 invoices ... 10 other",
"verified against synonyms.txt" over a file that does not match it, "written to out.txt" over prose plus the
answer). A same-model check shares the reading that made the error, so the report does not judge. It states only
what the harness observed:
- the files under the working directory changed since the run started, with size and sha256;
- every terminal and Python step, with its exit code where the terminal reported one;
- for each delivered file, the step that last wrote it when a file tool did (shell and Python writes are not
  attributable), and the later steps whose command names the file. Naming a file is not checking it; the report
  says which steps named it, nothing more;
- the processes still running at the end, and the run's status.
The model's finish summary is reproduced verbatim under its own heading, as its account, not as a finding.

The report is written to the run record. The model never sees it, so it cannot change the work.
"""

from __future__ import annotations

import posixpath
import re
import shlex
from dataclasses import dataclass
from typing import Any

from . import receipt
from .env import Environment, exit_code

EXIT = re.compile(r"\[exit (-?\d+) ·")
TEXT_CHARS = 300
MAX_FILES = 200


@dataclass(frozen=True)
class StepRecord:
    """One tool step as the harness saw it. ``exit`` is the terminal's reported exit code (None when the step
    has none, e.g. a still-running command or a file tool); ``failed`` is a tool-reported error."""

    step: int
    tool: str
    text: str
    exit: int | None
    failed: bool
    wrote: str = ""


def record(step: int, name: str, args: dict[str, Any], out: str, workdir: str) -> StepRecord:
    if name == "terminal":
        text = str(args.get("input") or "")
    elif name == "python":
        text = str(args.get("code") or "")
    else:
        text = str(args.get("path") or "")
    path = str(args.get("path") or "")
    wrote = (
        posixpath.normpath(posixpath.join(workdir, path))
        if name in ("write_file", "edit_file") and path
        else ""
    )
    found = EXIT.findall(out) if name == "terminal" else []
    return StepRecord(
        step,
        name,
        text,
        int(found[-1]) if found else None,
        out.startswith("error:"),
        wrote,
    )


async def _files(env: Environment, workdir: str, control_dir: str) -> list[dict[str, Any]] | str:
    try:
        paths = await receipt.changed(env, workdir, control_dir)
    except OSError as exc:
        return f"the changed files could not be listed: {exc}"
    paths = paths[:MAX_FILES]
    if not paths:
        return []
    listing = " ".join(shlex.quote(p) for p in paths)
    command = (
        f"cd {shlex.quote(workdir)} && for f in {listing}; do "
        f'printf "%s\\t%s\\t%s\\n" "$f" "$(stat -c %s "$f" 2>/dev/null || wc -c < "$f")" '
        f'"$(sha256sum "$f" 2>/dev/null | cut -d" " -f1)"; done'
    )
    result = await env.exec(command=command, cwd=None, env=None, timeout_sec=60)
    if exit_code(result) != 0:
        return f"the changed files could not be measured: {str(getattr(result, 'stderr', ''))[:200]}"
    rows = []
    for line in str(getattr(result, "stdout", "") or "").splitlines():
        name, _, rest = line.partition("\t")
        size, _, digest = rest.partition("\t")
        rows.append(
            {
                "path": posixpath.normpath(posixpath.join(workdir, name)),
                "bytes": int(size) if size.strip().isdigit() else None,
                "sha256": digest or None,
            }
        )
    return rows


def _attribute(files: list[dict[str, Any]], steps: list[StepRecord]) -> None:
    for f in files:
        writes = [s.step for s in steps if s.wrote == f["path"] and not s.failed]
        last = writes[-1] if writes else None
        base = posixpath.basename(f["path"])
        named = [
            s.step
            for s in steps
            if s.tool in ("terminal", "python", "read_file")
            and (last is None or s.step > last)
            and (f["path"] in s.text or (base and base in s.text))
        ]
        f["last_file_tool_write"] = last
        f["steps_naming_it_after"] = named


async def build(
    env: Environment,
    workdir: str,
    control_dir: str,
    steps: list[StepRecord],
    *,
    status: str,
    finish_summary: str | None,
    left_running: list[Any],
) -> dict[str, Any]:
    """The report as data. Never raises for a listing failure: the failure is the reported fact."""
    files = await _files(env, workdir, control_dir)
    if isinstance(files, list):
        _attribute(files, steps)
    commands = [s for s in steps if s.tool in ("terminal", "python")]
    return {
        "status": status,
        "delivered_files": files,
        "steps": len(steps),
        "commands": len(commands),
        "commands_nonzero_exit": [s.step for s in commands if s.exit not in (None, 0)],
        "commands_tool_error": [s.step for s in commands if s.failed],
        "commands_without_exit": [s.step for s in commands if s.tool == "terminal" and s.exit is None],
        "left_running": left_running,
        "model_account": finish_summary,
        "command_log": [
            {"step": s.step, "tool": s.tool, "exit": s.exit, "text": s.text[:TEXT_CHARS]}
            for s in commands
        ],
    }


def render(report: dict[str, Any]) -> str:
    """Plain text for people. The harness facts first; the model's account last, under its own heading."""
    out = ["# Finish report", "", "## Observed by the harness", f"- run status: {report['status']}"]
    files = report["delivered_files"]
    if isinstance(files, str):
        out.append(f"- delivered files: unknown ({files})")
    elif not files:
        out.append("- delivered files: none changed under the working directory since the run started")
    else:
        out.append(f"- delivered files ({len(files)} changed since the run started):")
        for f in files:
            wrote = (
                f"last written by a file tool at step {f['last_file_tool_write']}"
                if f["last_file_tool_write"]
                else "written by a shell or Python step (step not attributable)"
            )
            named = f["steps_naming_it_after"]
            seen = (
                f"named by later steps {', '.join(map(str, named))}"
                if named
                else "not named by any later step"
            )
            out.append(f"  - {f['path']} · {f['bytes']} bytes · sha256 {str(f['sha256'])[:16]} · {wrote} · {seen}")
    out.append(
        f"- commands: {report['commands']} (non-zero exit at steps {report['commands_nonzero_exit'] or 'none'}; "
        f"no exit reported at steps {report['commands_without_exit'] or 'none'})"
    )
    running = report["left_running"] or []
    out.append(f"- processes still running at the end: {len(running)}")
    out += [f"  - {p}" for p in running[:20]]
    out += [
        "",
        "## The model's account (its own description; not checked by the harness)",
        report["model_account"] if report["model_account"] else "[no finish summary: the run did not finish]",
        "",
        "A step naming a file is not a check of it. Nothing here says whether the delivered files are correct.",
    ]
    return "\n".join(out) + "\n"
