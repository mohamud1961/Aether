"""``apply_patch``: file edits as one patch text, the format and tool shape Codex gives GPT models (study arm CX,
AETHER_CORE_TOOLSET=codex). Off by default.

Codex (openai/codex main, 16 Nov 2026) offers ``exec_command`` + ``apply_patch`` as its coding interface; apply_patch
is a freeform tool whose input is constrained by a Lark grammar (``codex-rs/core/src/tools/handlers/apply_patch_spec.rs``)
instead of JSON arguments. The 16 Nov probe: Luna's Azure deployment accepts the custom tool and wrote a valid patch.

Semantics follow Codex's parser: Add File (``+`` lines), Delete File, Update File (optional ``*** Move to:``) with
chunks of `` ``/``-``/``+`` lines, each optionally anchored by an ``@@ <context>`` line. Old lines are located in
order from the previous chunk, exactly first, then ignoring trailing whitespace, then ignoring surrounding
whitespace. Every file's result is computed before anything is written; a patch that does not apply writes nothing.
"""

from __future__ import annotations

import hashlib
import posixpath
import shlex
from dataclasses import dataclass, field
from typing import Any

from .env import get_bytes, put_bytes, run

NAME = "apply_patch"
GRAMMAR = r'''start: begin_patch hunk+ end_patch
begin_patch: "*** Begin Patch" LF
end_patch: "*** End Patch" LF?

hunk: add_hunk | delete_hunk | update_hunk
add_hunk: "*** Add File: " filename LF add_line+
delete_hunk: "*** Delete File: " filename LF
update_hunk: "*** Update File: " filename LF change_move? change?

filename: /(.+)/
add_line: "+" /(.*)/ LF -> line

change_move: "*** Move to: " filename LF
change: (change_context | change_line)+ eof_line?
change_context: ("@@" | "@@ " /(.+)/) LF
change_line: ("+" | "-" | " ") /(.*)/ LF
eof_line: "*** End of File" LF

%import common.LF
'''
DESCRIPTION = (
    "Use the `apply_patch` tool to edit files. The input is a patch:\n"
    "*** Begin Patch\n[one or more file sections]\n*** End Patch\n\n"
    "Each file section starts with one header:\n"
    "*** Add File: <path> - create a file; every following line starts with +\n"
    "*** Delete File: <path> - remove a file; nothing follows\n"
    "*** Update File: <path> - patch a file in place; optionally followed by *** Move to: <new path>\n"
    "An Update section has one or more chunks. A chunk may start with `@@ <a line near the change>` to locate it, "
    "then lists lines prefixed with ' ' (context, kept), '-' (removed) or '+' (added). Give about 3 lines of "
    "context around each change. Paths may be relative to the working directory or absolute."
)
TOOL = {
    "type": "function",
    "function": {
        "name": NAME,
        "description": DESCRIPTION,
        "parameters": {"type": "object", "properties": {"input": {"type": "string", "description": "The patch."}},
                       "required": ["input"]},
    },
    # Responses sends this tool as a freeform grammar tool; the call's text arrives as {"input": text}.
    "aether_freeform": {"type": "grammar", "syntax": "lark", "definition": GRAMMAR},
}


class PatchError(ValueError):
    pass


@dataclass
class Chunk:
    context: str | None
    old: list[str] = field(default_factory=list)
    new: list[str] = field(default_factory=list)
    eof: bool = False


@dataclass
class Hunk:
    kind: str  # add, delete, update
    path: str
    lines: list[str] = field(default_factory=list)  # add
    move_to: str | None = None
    chunks: list[Chunk] = field(default_factory=list)


def parse(text: str) -> list[Hunk]:
    lines = text.strip().split("\n")
    if not lines or lines[0].strip() != "*** Begin Patch":
        raise PatchError("the first line of the patch must be '*** Begin Patch'")
    if lines[-1].strip() != "*** End Patch":
        raise PatchError("the last line of the patch must be '*** End Patch'")
    body, hunks, i = lines[1:-1], [], 0
    while i < len(body):
        line = body[i]
        if line.startswith("*** Add File: "):
            hunk, i = Hunk("add", line[14:].strip()), i + 1
            while i < len(body) and body[i].startswith("+"):
                hunk.lines.append(body[i][1:]); i += 1
            if not hunk.lines:
                raise PatchError(f"Add File {hunk.path}: no '+' lines")
            hunks.append(hunk)
        elif line.startswith("*** Delete File: "):
            hunks.append(Hunk("delete", line[17:].strip())); i += 1
        elif line.startswith("*** Update File: "):
            hunk, i = Hunk("update", line[17:].strip()), i + 1
            if i < len(body) and body[i].startswith("*** Move to: "):
                hunk.move_to, i = body[i][13:].strip(), i + 1
            i = _chunks(body, i, hunk)
            if not hunk.chunks and not hunk.move_to:
                raise PatchError(f"Update File {hunk.path}: no changes")
            hunks.append(hunk)
        elif not line.strip():
            i += 1
        else:
            raise PatchError(f"line {i + 2}: expected a '*** Add/Delete/Update File:' header, got {line[:80]!r}")
    if not hunks:
        raise PatchError("the patch has no file sections")
    return hunks


def _chunks(body: list[str], i: int, hunk: Hunk) -> int:
    chunk: Chunk | None = None
    while i < len(body) and (not body[i].startswith("*** ") or body[i] == "*** End of File"):
        line = body[i]
        if line == "*** End of File":
            if chunk is None:
                raise PatchError(f"Update File {hunk.path}: '*** End of File' before any change")
            chunk.eof = True
        elif line.startswith("@@"):
            chunk = Chunk(line[2:].strip() or None)
            hunk.chunks.append(chunk)
        else:
            if chunk is None or chunk.eof:
                chunk = Chunk(None)
                hunk.chunks.append(chunk)
            tag, rest = (line[:1], line[1:]) if line else (" ", "")
            if tag not in " -+":
                raise PatchError(f"Update File {hunk.path}: line {line[:80]!r} must start with ' ', '-' or '+'")
            if tag in " -":
                chunk.old.append(rest)
            if tag in " +":
                chunk.new.append(rest)
        i += 1
    return i


def _seek(lines: list[str], pattern: list[str], start: int, eof: bool) -> int:
    if not pattern:
        return len(lines) if eof else start
    for norm in (lambda s: s, str.rstrip, str.strip):
        want = [norm(p) for p in pattern]
        first = len(lines) - len(pattern) if eof else start
        for at in range(max(first, start), len(lines) - len(pattern) + 1):
            if [norm(x) for x in lines[at:at + len(pattern)]] == want:
                return at
    return -1


def updated(text: str, hunk: Hunk) -> str:
    lines = text.split("\n")
    trailing = bool(lines) and lines[-1] == ""
    if trailing:
        lines.pop()
    cursor, edits = 0, []
    for chunk in hunk.chunks:
        if chunk.context is not None:
            at = _seek(lines, [chunk.context], cursor, False)
            if at < 0:
                raise PatchError(f"{hunk.path}: context line not found: {chunk.context[:120]!r}")
            cursor = at + 1
        at = _seek(lines, chunk.old, cursor, chunk.eof)
        if at < 0:
            shown = "\n".join(chunk.old[:6])
            raise PatchError(f"{hunk.path}: these lines were not found (in order after the previous chunk):\n{shown}")
        edits.append((at, len(chunk.old), chunk.new))
        cursor = at + len(chunk.old)
    for at, n, new in reversed(edits):
        lines[at:at + n] = new
    return "\n".join(lines) + ("\n" if trailing or not text else "")


async def apply(files: Any, env: Any, text: str) -> str:
    """Apply the patch to the task environment; returns Codex's summary. Nothing is written if any part fails."""
    hunks = parse(text)
    plan: list[tuple[str, str, bytes | None, str | None, str | None]] = []  # (tag, path, data, mode, sha)
    for hunk in hunks:
        path = files.resolve(hunk.path)
        if hunk.kind == "add":
            plan.append(("A", path, ("\n".join(hunk.lines) + "\n").encode(), await files._mode(path), None))
            continue
        mode = await files._mode(path)
        if mode is None:
            raise PatchError(f"{hunk.path}: file does not exist")
        if hunk.kind == "delete":
            plan.append(("D", path, None, mode, None))
            continue
        payload = await get_bytes(env, path)
        try:
            source = payload.decode()
        except UnicodeDecodeError as exc:
            raise PatchError(f"{hunk.path} is not UTF-8 text") from exc
        data = updated(source, hunk).encode() if hunk.chunks else payload
        sha = hashlib.sha256(payload).hexdigest()
        if hunk.move_to:
            plan.append(("D", path, None, mode, None))
            plan.append(("M", files.resolve(hunk.move_to), data, mode, None))
        else:
            plan.append(("M", path, data, mode, sha))
    done = []
    for tag, path, data, mode, sha in plan:
        if tag == "D":
            res = await run(env, f"rm -f -- {shlex.quote(path)}")
            if res.code != 0:
                raise PatchError(f"could not delete {path}: {res.stderr.strip()[:200]}")
        else:
            await run(env, f"mkdir -p -- {shlex.quote(posixpath.dirname(path) or '/')}")
            await put_bytes(env, data, path, mode=mode, expected_sha256=sha)
            files.written[path] = len(data)
        done.append(f"{tag} {path}")
    return "Success. Updated the following files:\n" + "\n".join(done)
