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
from typing import Any

from .env import get_bytes, put_bytes, run
from .patch_text import Chunk, Hunk, PatchError, parse, updated  # noqa: F401  (re-exported)

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
