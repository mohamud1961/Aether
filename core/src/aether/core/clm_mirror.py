"""The CLM mirror file: how the editable context is rendered for the model, paged from history, and parsed back
after the model edits it (split from clm.py, module cap). ``ClmContext`` inherits these methods."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import re
from typing import Any

from . import images

NOTES_HEADER = (
    "[your notes] You wrote this when you condensed your context. It is your own record, not the task: the task "
    "statement at the top is the only statement of the task, and where your notes differ from it, the task "
    "statement is right."
)
NOTES_TAG = "[your notes]"
TURN_RE = re.compile(r"^\[\[CTX_TURN (\d+) role=([a-z_]+)\]\]$", re.M)


def _call_text(call: dict[str, Any]) -> str:
    fn = call.get("function") or {}
    return f"[tool_call {fn.get('name', '')}] {fn.get('arguments', '')}"


def render_message(msg: dict[str, Any]) -> str:
    parts = [images.text_of(msg.get("content"))]
    parts += [_call_text(c) for c in msg.get("tool_calls") or ()]
    return "\n".join(p for p in parts if p)


class ClmMirror:
    """Mirror rendering and parsing over a context's ``editable`` and ``raw`` messages."""

    # ----- the mirror file -----------------------------------------------------------------------
    def render(self, upto: int | None = None) -> str:
        msgs = self.editable if upto is None else self.editable[:upto]
        return "\n".join(
            f"[[CTX_TURN {i} role={m.get('role')}]]\n{render_message(m)}"
            for i, m in enumerate(msgs)
        )

    def render_history(self) -> str:
        """Original appended messages, including reasoning and structured content, with stable message IDs.

        Later harness annotations do not overwrite the original observation. JSON preserves the fields that
        the editable text mirror intentionally leaves out, including tool IDs and image data.
        """
        return "\n".join(
            f"[[MSG {i} role={m.get('role')}]]\n{json.dumps(m, ensure_ascii=False)}"
            for i, m in enumerate(self.raw)
        )

    def read_history(self, message_id: int, offset: int = 0, limit: int = 12000) -> str:
        """Page one original message without depending on the sandbox history file."""
        if not 0 <= message_id < len(self.raw):
            raise ValueError(
                f"history contains {len(self.raw)} messages; IDs are 0 through {len(self.raw) - 1}"
            )
        text = json.dumps(self.raw[message_id], ensure_ascii=False)
        if self.settings.attest_original_history:
            recorded = self.append_digest_candidate(message_id)
            if recorded != hashlib.sha256(text.encode("utf-8")).hexdigest():
                raise ValueError(f"history MSG {message_id} no longer matches its original source digest")
        if offset < 0 or offset > len(text) or limit < 1 or limit > 20000:
            raise ValueError(
                f"offset must be 0..{len(text)} and limit must be 1..20000 characters"
            )
        end = min(len(text), offset + limit)
        next_page = f"; next offset={end}" if end < len(text) else "; complete"
        return (
            f"[history MSG {message_id}; {len(self.raw)} messages; chars {offset}:{end} of {len(text)}"
            f"{next_page}]\n{text[offset:end]}"
        )

    def history_image(self, message_id: int) -> dict[str, Any]:
        """Return a copy of the exact pixels originally presented in an attested history message."""
        if self.original_message_digest(message_id) is None:
            raise ValueError(f"history MSG {message_id} has no verified original source")
        content = self.raw[message_id].get("content")
        if not isinstance(content, list) or not any(images._is_image_part(part) for part in content):
            raise ValueError(f"history MSG {message_id} has no image observation")
        return {"role": "user", "content": deepcopy(content), images.HISTORY_FIELD: message_id}

    @staticmethod
    def parse(text: str, voice: str = "legacy") -> list[dict[str, Any]]:
        """The edited mirror as messages. Blocks the model marks as its turns stay assistant turns; everything else
        it wrote (its summaries, kept outputs, any block it labels user) is its own record, so with voice "own" it
        comes back labelled as its notes (still role=user), the first with the header that ranks it below the task."""
        marks = list(TURN_RE.finditer(text))
        blocks: list[tuple[str, str]] = []
        lead = (text[: marks[0].start()] if marks else text).strip()
        if lead:
            blocks.append(("user", lead))
        for k, m in enumerate(marks):
            end = marks[k + 1].start() if k + 1 < len(marks) else len(text)
            body = text[m.end() : end].strip("\n")
            if body.strip():
                blocks.append(("assistant" if m.group(2) == "assistant" else "user", body))
        out, headed = [], False
        for role, body in blocks:
            if role == "user" and voice == "own":
                body = f"{NOTES_TAG if headed else NOTES_HEADER}\n{body}"
                headed = True
            out.append({"role": role, "content": body})
        return out

    def _unchanged(self, text: str, upto: int) -> list[dict[str, Any]]:
        """The edit as messages, keeping the original message for every block the model left exactly as rendered.

        Rebuilding every block from text turned untouched tool results into role=user (labelled as notes under
        "own") and tool calls into "[tool_call ...]" text (P1: R5.base.protein-assembly e1r2, 2 -> 52 user
        messages after a one-line edit). A call and its results stay native only together, unchanged and in order;
        anything else goes the text way, as ``parse`` builds it."""
        marks = list(TURN_RE.finditer(text))
        lead = (text[: marks[0].start()] if marks else text).strip()
        blocks: list[tuple[int | None, str, str]] = [(None, "user", lead)] if lead else []
        seen: set[int] = set()
        for k, m in enumerate(marks):
            end = marks[k + 1].start() if k + 1 < len(marks) else len(text)
            body = text[m.end() : end].strip("\n")
            if not body.strip():
                continue
            i, role = int(m.group(1)), m.group(2)
            same = (
                i < upto
                and i not in seen
                and self.editable[i].get("role") == role
                and body == render_message(self.editable[i]).strip("\n")
            )
            seen.add(i)
            blocks.append((i if same else None, role, body))
        keep = [orig is not None and blocks[j][1] != "tool" for j, (orig, _, _) in enumerate(blocks)]
        for j, (orig, _, _) in enumerate(blocks):
            msg = self.editable[orig] if orig is not None else {}
            if keep[j] and msg.get("tool_calls"):
                ids = [c.get("id") for c in msg["tool_calls"]]
                results = blocks[j + 1 : j + 1 + len(ids)]
                keep[j] = len(results) == len(ids) and all(
                    o == orig + n + 1 and r == "tool" and self.editable[o].get("tool_call_id") == ids[n]
                    for n, (o, r, _) in enumerate(results)
                )
                for n in range(len(ids)) if keep[j] else ():  # a result is native only inside its own call's unit
                    keep[j + 1 + n] = True
        out, headed = [], False
        voice = self.settings.notes_voice
        for (orig, role, body), kept in zip(blocks, keep):
            if kept:
                out.append(self.editable[orig])
                continue
            role = "assistant" if role == "assistant" else "user"
            if role == "user" and voice == "own":
                body = f"{NOTES_TAG if headed else NOTES_HEADER}\n{body}"
                headed = True
            out.append({"role": role, "content": body})
        return out
