"""Study arm (12 Nov): the solver's step-0 list delivered as its own first turn.

The XL arm appends the list to the task message. The filing study found the solver then reads its own lines as the
requester's words ("since the user specified not to include a prefix"; it credits the list to itself in 1 of 94
runs), so a wrong line outranks what the machine shows. Here the first messages replay what actually happened:
the question that was put to the model with the task, the model's answer as an assistant turn, then the go-ahead.
Nothing is added to the model's own text, and the task text itself is unchanged.
"""

from __future__ import annotations

import json
from typing import Any

GO = "Now do the task."


def task_messages(path: str, task: str, appendix: str, tail: str) -> list[dict[str, Any]]:
    """The messages that follow the system prompt. Without a step-0 record this is the one task message as before."""
    if not path:
        return [{"role": "user", "content": f"{task}{appendix}\n\n{tail}"}]
    with open(path, encoding="utf-8") as handle:
        record = json.load(handle)
    question, answer = str(record["question"]).strip(), str(record["answer"]).strip()
    if not question or not answer:
        raise ValueError(f"step-0 record {path} needs a non-empty question and answer")
    return [
        {"role": "user", "content": f"{question}\n\n{task}{appendix}"},
        {"role": "assistant", "content": answer},
        {"role": "user", "content": f"{GO}\n\n{tail}"},
    ]
