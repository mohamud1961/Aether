"""Shared handles for the CHALLENGER flows (kept separate so flows stay small)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Sequence

from ..challenger_claim_ledger_state import TaskLocalClaimLedger
from ..challenger_claim_types import QuestionEvaluator
from ..ledger import ExecutionLedger
from .events import ChallengerEventLog

MAX_NOTE_CHARS = 2000
TREE_NOTE_BYTES = 480  # below M-TREE's 512-byte node so the note stays verbatim in the view


def tree_note(text: str) -> str:
    """Collapse whitespace and cap at TREE_NOTE_BYTES (UTF-8 safe)."""
    flat = " ".join(text.split())
    return flat if len(flat.encode()) <= TREE_NOTE_BYTES else flat.encode()[:TREE_NOTE_BYTES - 3].decode("utf-8", "ignore") + "..."
CardModel = Callable[[Sequence[dict[str, str]]], str]


@dataclass
class LoopBinding:
    """The loop's own objects, handed over once so the flows can run ordinary actions."""

    kernel: Any
    compiled: Any
    executor: Any
    exec_ledger: ExecutionLedger
    world_state: Any
    context_tree_adapter: Any | None = None  # M-TREE: notes and request accounting


@dataclass
class FlowContext:
    card_model: CardModel
    evaluator: QuestionEvaluator
    log: ChallengerEventLog
    ledger: TaskLocalClaimLedger
    task_text: str
    threshold: float
    binding: LoopBinding | None = None
    hold_threshold: float | None = None  # challenger_v2: holds need this; `threshold` then only gates advisory notes
    failure_mode: bool = False  # challenger_v2: add the failure-mode question to the T4 JUDGE request
    artifact_threshold: float | None = None  # challenger_v5: hold threshold of the artifact-evidence request (None: mode off)
    workspace_root: str = ""  # set by the controller from the envmap; scratch-path and receipt-path normalisation

    def note_to_tree(self, text: str) -> None:
        """Under M-TREE, CHALLENGER feedback is an ordinary event so the tree/view carries it."""
        adapter = self.binding.context_tree_adapter if self.binding else None
        if adapter is not None:
            adapter.record_note(text)

    def ask_card_model(self, messages: Any, prompt: str, label: str, extra: Any = (),
                       *, record_note: bool = True) -> str:
        """One extra same-model turn. Under M-TREE the request is the already-bounded epoch
        request (task + current view + packet) plus the card instruction, and is accounted
        against the epoch like any other request."""
        request = [dict(m) for m in messages] + [{"role": "user", "content": prompt}] + [dict(m) for m in extra]
        adapter = self.binding.context_tree_adapter if self.binding else None
        if adapter is not None:
            adapter.note_request(request)
        text = self.card_model(request)
        if record_note:
            self.note_to_tree(f"{label}: {text[:MAX_NOTE_CHARS]}")
        return text
