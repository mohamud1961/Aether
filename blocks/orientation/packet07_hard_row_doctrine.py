"""Packet 07 hard-row doctrine for answer robustness follow-up."""

from __future__ import annotations

from typing import Any


_DIRECT_ANSWER_CUES = (
    "direct answer",
    "answer only",
    "final answer only",
    "respond with only",
    "output only",
    "just the answer",
)

_SCALAR_VALUE_CUES = (
    "scalar",
    "value",
    "count",
    "number",
    "integer",
    "total",
    "sum",
    "how many",
)


def _is_direct_answer_scalar_task(task_prompt: str) -> bool:
    text = task_prompt.lower()
    has_direct_answer_cue = any(cue in text for cue in _DIRECT_ANSWER_CUES)
    has_scalar_value_cue = any(cue in text for cue in _SCALAR_VALUE_CUES)
    return has_direct_answer_cue and has_scalar_value_cue


def orient(
    task_prompt: str,
    env_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    env = dict(env_info or {})
    lines: list[str]
    if _is_direct_answer_scalar_task(task_prompt):
        lines = [
            "Packet 07 hard-row doctrine: candidate_plus_path_normalized_reduction_discipline_guard_01.",
            "Authority: bounded Packet 07 hard-row answer-robustness follow-up only.",
            "Scope: late-stage helper for direct-answer tasks after successful compute output or broad evidence reads.",
            "Reduction discipline: identify the selected candidate set or winner before final closure.",
            "Operation discipline: state the exact reduction operation used to derive the final scalar/value.",
            "Focused recount: perform one focused recount from the selected set to recompute the final scalar/value.",
            "Closure guard: answer only after that focused recount, and avoid immediate closure on weak empty/zero scalars without grounded reduced-set evidence.",
            "Evidence rule: source-backed tool output and path-grounded records outrank memory or guesses.",
        ]
    else:
        lines = [
            "General orientation: prioritize grounded tool evidence, follow task instructions, and avoid unsupported assumptions.",
        ]
    if env.get("cwd"):
        lines.append(f"Workspace cwd: {env['cwd']}")
    if env.get("task_id"):
        lines.append(f"Task id: {env['task_id']}")
    return {
        "task_prompt": task_prompt,
        "env_info": env,
        "messages": [
            {"role": "system", "content": "\n".join(lines)},
            {"role": "user", "content": task_prompt},
        ],
    }
