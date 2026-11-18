"""Codex patch text: parsing and applying a patch to file text, standard library only (split from apply_patch.py).

Self-contained on purpose: the shell kit (AETHER_CORE_SHELL_KIT) copies this file into the task container, so the
``apply_patch`` shell command applies exactly the semantics of the ``apply_patch`` tool.
"""

from __future__ import annotations

from dataclasses import dataclass, field


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
