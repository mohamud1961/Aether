"""What the model sees each turn: recent turns verbatim, older turns as pointers.

The full history is kept unchanged in the run trace; only the request is
projected. Older turns are trimmed in blocks so the request prefix stays stable
between trims (provider prompt caching), and every trimmed item says where the
full content still lives.

Every tool result long enough to be trimmed is also saved, exactly as the model
first saw it, in the sandbox (``saved_path``): a re-read shows the file as it is
now and a re-run may differ, but the saved copy is the observation itself, and it
survives trims, CLM edits and checkpoints alike.
"""
from __future__ import annotations

from copy import deepcopy
import json
from typing import Any

from . import images

KEEP_RECENT = 4  # assistant turns always kept verbatim (with reasoning)
BLOCK = 6  # older turns are trimmed in blocks of this many turns
OLD_RESULT_HEAD = 600
OLD_RESULT_TAIL = 900
TIGHT_HEAD, TIGHT_TAIL = 200, 300
SAVE_OVER = min(OLD_RESULT_HEAD + OLD_RESULT_TAIL, TIGHT_HEAD + TIGHT_TAIL) + 80  # results this long can be trimmed later, so they are saved
SAVED_NOTE = "[this result is saved in full at {path}]"
BODY_KEYS = {"write_file": ("content",), "edit_file": ("old_str", "new_str")}


def _cut(n_assistant: int) -> int:
    """Number of oldest assistant turns to trim; advances only every BLOCK turns."""
    return max(0, (n_assistant - KEEP_RECENT) // BLOCK * BLOCK)


def saved_path(control_dir: str, step: int) -> str:
    return f"{control_dir}/results/{step}.txt"


def _shorten(text: str, head: int, tail: int) -> str:
    if len(text) <= head + tail + 80:
        return text
    where = ("its full text is saved at the path below" if SAVED_NOTE.split("{")[0] in text[-tail:]
             else "re-run, re-read, or grep the terminal log to see them")
    return (f"{text[:head]}\n…[{len(text) - head - tail} chars of this older result omitted; "
            f"{where}]…\n{text[-tail:]}")


def _stub_arguments(name: str, raw: str) -> str:
    keys = BODY_KEYS.get(name)
    if not keys:
        return raw
    try:
        args = json.loads(raw)
    except ValueError:
        return raw
    if not isinstance(args, dict):
        return raw
    for key in keys:
        value = args.get(key)
        if isinstance(value, str) and len(value) > 200:
            args[key] = f"[{len(value)} chars; the file on disk holds the current text — read_file it]"
    return json.dumps(args, ensure_ascii=False)


def project(messages: list[dict[str, Any]], *, tight: bool = False) -> list[dict[str, Any]]:
    """Return the request view of ``messages`` (system + task first, then turns)."""
    assistant_idx = [i for i, m in enumerate(messages) if m.get("role") == "assistant"]
    cut = len(assistant_idx) if tight else _cut(len(assistant_idx))
    cut = min(cut, max(0, len(assistant_idx) - (2 if tight else KEEP_RECENT)))
    boundary = assistant_idx[cut] if cut < len(assistant_idx) else len(messages)
    head, tail = (TIGHT_HEAD, TIGHT_TAIL) if tight else (OLD_RESULT_HEAD, OLD_RESULT_TAIL)
    out: list[dict[str, Any]] = []
    for i, msg in enumerate(messages):
        if i >= boundary or msg.get("role") in ("system",) or i < 2:
            out.append(msg)
            continue
        msg = deepcopy(msg)
        if msg.get("role") == "assistant":
            msg.pop("reasoning_content", None)
            for call in msg.get("tool_calls") or ():
                fn = call.get("function") or {}
                fn["arguments"] = _stub_arguments(fn.get("name", ""), fn.get("arguments", ""))
        elif msg.get("role") == "tool" and isinstance(msg.get("content"), str):
            msg["content"] = _shorten(msg["content"], head, tail)
        out.append(msg)
    return images.limit(out)


def size_chars(messages: list[dict[str, Any]]) -> int:
    return images.size_chars(messages)
