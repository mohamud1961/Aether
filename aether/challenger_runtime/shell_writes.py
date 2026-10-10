"""Conservative detection of workspace files a shell command clearly writes.

Only four plain forms count: ``>``/``>>`` redirection, ``tee``, ``sed -i`` and
heredocs feeding a redirection. Quoted text and heredoc bodies are removed
first, and any target containing a shell expansion is ignored, so an unclear
command is never reported as a write.
"""
from __future__ import annotations

import re

_HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1")
_QUOTED = re.compile(r"'[^']*'|\"[^\"]*\"")
_REDIRECT = re.compile(r"(?<![<>&])\d*>>?(?![>&])\s*([^\s;|&<>()]+)")
_TEE = re.compile(r"\btee\s+(?:-[a-zA-Z]+\s+)*([^\s;|&<>()]+)")
_SED_I = re.compile(r"\bsed\s+(?:-[a-zA-Z]*\s+)*(?:-[a-zA-Z]*i\S*|--in-place\S*)\s+([^;|&\n]*)")


def _strip_heredoc_bodies(command: str) -> str:
    out: list[str] = []
    terminator = ""
    for line in command.split("\n"):
        if terminator:
            if line.strip() == terminator:
                terminator = ""
            continue
        out.append(line)
        match = _HEREDOC.search(line)
        if match:
            terminator = match.group(2)
    return "\n".join(out)


def _clean(target: str) -> str | None:
    if not target or target.startswith(("/dev/", "&", "-")) or any(c in target for c in "$`*?{}!"):
        return None
    return target


def command_write_targets(command: str) -> tuple[str, ...]:
    """Paths the command clearly writes, in order of appearance."""
    text = _QUOTED.sub(" ", _strip_heredoc_bodies(command))
    found: list[str] = []
    for match in _REDIRECT.finditer(text):
        found.append(match.group(1))
    for match in _TEE.finditer(text):
        found.append(match.group(1))
    for match in _SED_I.finditer(text):
        tokens = [t for t in match.group(1).split() if not t.startswith("-")]
        if tokens:
            found.append(tokens[-1])
    return tuple(dict.fromkeys(t for t in map(_clean, found) if t))
