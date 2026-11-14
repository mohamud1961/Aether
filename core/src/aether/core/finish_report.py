"""Finish report: what the run delivered and did, from the harness's own records, beside the model's account.

Audits found final summaries that the delivered state contradicts ("17 documents ... 10 invoices ... 10 other",
"verified against synonyms.txt" over a file that does not match it, "written to out.txt" over prose plus the
answer). A same-model check shares the reading that made the error, so the report does not judge. It states only
what the harness observed:
- current regular files observed with mtime or ctime newer than the start marker, plus recorded successful file-tool writes, with size and sha256;
- every terminal and Python step, with its exit code where the terminal reported one;
- for each delivered file, the step that last wrote it when a file tool did (shell and Python writes are not
  attributable), and the later steps whose command names the file. Naming a file is not checking it; the report
  says which steps named it, nothing more;
- the processes still running at the end, and the run's status;
- claims in the model's summary with nothing recorded behind them (see ``claims``): one-directional flags.
The model's finish summary is reproduced verbatim under its own heading, as its account, not as a finding.

The report is written to the run record. The model never sees it, so it cannot change the work.
"""

from __future__ import annotations

import posixpath
import json
import re
import shlex
from dataclasses import dataclass
from typing import Any

from . import claims, receipt
from .env import Environment, exit_code

EXIT = re.compile(r"\[exit (-?\d+) ·")
STAGES = re.compile(r"\[exit -?\d+ · last pipeline's stage exits ")
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
    numbers: frozenset[str] = frozenset()  # numbers in the step's output, for grounding the summary's numbers
    stage_failed: bool = False  # the terminal reported a failed stage in the command's last pipeline


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
        claims.numbers(out),
        bool(STAGES.search(out)) if name == "terminal" else False,
    )


async def _files(
    env: Environment, workdir: str, control_dir: str, written: set[str], *, check_absence: bool = False,
) -> tuple[list[dict[str, Any]] | str, int]:
    """The changed files (at most MAX_FILES, those a file tool wrote first) and how many changed in all."""
    try:
        paths = await receipt.changed(env, workdir, control_dir)
    except OSError as exc:
        return f"the changed files could not be listed: {exc}", 0
    # File tools are also known effects even when timestamps were preserved.
    # An absent/unreadable known output makes measurement unknown below.
    absolute = lambda p: posixpath.normpath(posixpath.join(workdir, p))
    paths = sorted({absolute(p) for p in paths} | {absolute(p) for p in written})
    total = len(paths)
    # Over the cap, sorted order alone kept 200 build artefacts and dropped the sources the model edited
    # (R5.base.build-cython-ext e1), and the count read as the cap.
    paths = sorted(paths, key=lambda p: p not in written)[:MAX_FILES]
    if not paths:
        return [], 0
    listing = " ".join(shlex.quote(p) for p in paths)
    # NUL-delimited triples keep legal tabs/newlines/backslashes in pathnames.
    # Hash stdin so GNU SHA utilities do not escape a pathname into the digest.
    command = (
        f"cd {shlex.quote(workdir)} && for f in {listing}; do "
        + ('if [ ! -e "$f" ] && [ ! -L "$f" ] && [ -x "${f%/*}/" ]; then '
           'printf "%s\\0-\\0-\\0" "$f"; continue; fi; ' if check_absence else '')
        + 'test -f "$f" && ! test -L "$f" || exit 1; '
        'size=$(wc -c < "$f") || exit 1; '
        'digest=$(sha256sum < "$f" 2>/dev/null || shasum -a 256 < "$f" 2>/dev/null) || exit 1; '
        'printf "%s\\0%s\\0%s\\0" "$f" "$size" "${digest%% *}"; done'
    )
    result = await env.exec(command=command, cwd=None, env=None, timeout_sec=60)
    if exit_code(result) != 0:
        return f"the changed files could not be measured: {str(getattr(result, 'stderr', ''))[:200]}", total
    output = str(getattr(result, "stdout", "") or "")
    parts = output.split("\0")
    if not output.endswith("\0") or len(parts) != len(paths) * 3 + 1:
        return "the changed files measurement was incomplete", total
    rows = []
    for index, expected_name in enumerate(paths):
        name, size, digest = parts[index * 3 : index * 3 + 3]
        if check_absence and name == expected_name and size == digest == "-":
            continue
        if name != expected_name or not size.strip().isdigit() or not re.fullmatch(r"[0-9a-f]{64}", digest):
            return "the changed files could not be fingerprinted exactly", total
        rows.append(
            {
                "path": posixpath.normpath(posixpath.join(workdir, name)),
                "bytes": int(size),
                "sha256": digest,
            }
        )
    return rows, total


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
    task: str = "",
) -> dict[str, Any]:
    """The report as data. Never raises for a listing failure: the failure is the reported fact."""
    written = {s.wrote for s in steps if s.wrote and not s.failed}
    files, total = await _files(env, workdir, control_dir, written)
    if isinstance(files, list):
        _attribute(files, steps)
    commands = [s for s in steps if s.tool in ("terminal", "python")]
    return {
        "status": status,
        "delivered_files": files,
        "delivered_files_total": total,
        "delivery_inventory_complete": False,
        "delivery_inventory_scope": "current regular files with mtime or POSIX ctime newer than the start marker, plus recorded successful file-tool writes; deletions, special files, and externally restored filesystem state are outside this observation",
        "workdir": workdir,
        "steps": len(steps),
        "commands": len(commands),
        "commands_nonzero_exit": [s.step for s in commands if s.exit not in (None, 0)],
        "commands_tool_error": [s.step for s in commands if s.failed],
        "commands_without_exit": [s.step for s in commands if s.tool == "terminal" and s.exit is None],
        "commands_failed_pipeline_stage": [s.step for s in commands if s.stage_failed],
        "left_running": left_running,
        "model_account": finish_summary,
        "unbacked_claims": await claims.check(env, finish_summary, files, steps, workdir, task),
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
        out.append("- delivered files: none identified by timestamp scan or recorded file-tool writes")
    else:
        total = report.get("delivered_files_total", len(files))
        where = f" under {report['workdir']}" if report.get("workdir") else ""
        listed = (
            f"; {len(files)} listed, those a file tool wrote first" if total > len(files) else ""
        )
        out.append(f"- delivered files ({total} identified{where}{listed}):")
        for f in files:
            wrote = (
                f"last written by a file tool at step {f['last_file_tool_write']}"
                if f["last_file_tool_write"]
                else "no file-tool write attributed"
            )
            named = f["steps_naming_it_after"]
            seen = (
                f"named by later steps {', '.join(map(str, named))}"
                if named
                else "not named by any later step"
            )
            out.append(f"  - {json.dumps(f['path'], ensure_ascii=True)} · {f['bytes']} bytes · sha256 {str(f['sha256'])[:16]} · {wrote} · {seen}")
    out.append("- inventory scope: current regular files with newer mtime or POSIX change time, plus recorded file-tool writes; deletions and special files are not enumerated, so this is not an exhaustive change inventory or complete custody inventory")
    out.append(
        f"- commands: {report['commands']} (non-zero exit at steps {report['commands_nonzero_exit'] or 'none'}; "
        f"no exit reported at steps {report['commands_without_exit'] or 'none'}; a failed pipeline stage hidden "
        f"by exit 0 at steps {report.get('commands_failed_pipeline_stage') or 'none'})"
    )
    running = report["left_running"] or []
    out.append(f"- processes still running at the end: {len(running)}")
    out += [f"  - {p}" for p in running[:20]]
    out += _render_claims(report.get("unbacked_claims"))
    out += [
        "",
        "## The model's account (its own description; not checked by the harness)",
        report["model_account"] if report["model_account"] else "[no finish summary: the run did not finish]",
        "",
        "A step naming a file is not a check of it. Nothing here says whether the delivered files are correct.",
    ]
    return "\n".join(out) + "\n"


def _render_claims(found: dict[str, Any] | None) -> list[str]:
    if not found:
        return []
    out = [
        "",
        "## Claims in the model's account with no supporting observation identified",
        "Identified in the captured record only. A flag does not mean the claim is false or the action did not "
        "happen (test runners read files without naming them; numbers can be calculated; shell writes are not "
        "attributed to steps). No flag does not mean the claim is true.",
    ]
    for c in found["verification_no_step_identified"]:
        out.append(
            f"- verification claim; no captured step names {', '.join(c['no_step_identified_on'])} after its last "
            f"recorded write: {c['claim']}"
        )
    for c in found["verification_possibly_covered_by_test_run"]:
        runs = "; ".join(
            f"{x['file']} (test run at steps {', '.join(map(str, x['test_run_steps']))})" for x in c["possibly_covered_by"]
        )
        out.append(f"- verification claim; file not named, possibly covered by a test run: {runs}: {c['claim']}")
    for c in found["verification_unscoped"]:
        out.append(f"- verification claim naming no file (nothing specific to look up): {c}")
    if found["numbers_not_found_verbatim"]:
        out.append(
            "- numbers not found verbatim in any captured output or the task (may be calculated): "
            + ", ".join(found["numbers_not_found_verbatim"])
        )
    missing = found["named_files_not_found"]
    if isinstance(missing, str):
        out.append(f"- named files: unknown ({missing})")
    elif missing:
        out.append(f"- named files not found at the end of the run: {', '.join(missing)}")
    if len(out) == 3:
        out.append("- none identified")
    return out
