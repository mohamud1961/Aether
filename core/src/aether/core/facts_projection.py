"""Append-only presentation of scoped observations from the existing facts service."""

from __future__ import annotations

from uuid import uuid4

from .facts_workspace import ManagedFactsText

POLICY = (
    "\n\nCore facts are scoped observations. For the same service use the newest generation and revision "
    "in this conversation. Earlier revisions describe earlier observations. Unmeasured fields remain unknown."
)


def render(generation: str, revision: int, step: int, source: str, body: str) -> str:
    return f"[Core observation {source} {generation}/{revision} at step {step}]\n{body}"


class FactsTimeline:
    def __init__(self, source: str):
        self.source = source
        self.generation = uuid4().hex[:8]
        self.revision = -1
        self.body: str | None = None
        self.latest: dict | None = None

    def observe(self, body: str, step: int, checkpoint=None) -> dict | None:
        if body == self.body:
            return None
        self.revision += 1
        self.body = body
        text = render(self.generation, self.revision, step, self.source, body)
        self.latest = {
            "role": "assistant",
            "content": ManagedFactsText(text, checkpoint),
        }
        return self.latest
