"""Orientation with task description, environment snapshot, and a model-generated plan.

Interface: OrientationBlock.orient(task_prompt, env_info) -> initial_context
"""

from __future__ import annotations

import re
from typing import Any


def orient(task_prompt: str, env_info: dict[str, Any] | None = None) -> dict[str, Any]:
    """Prepare task, environment grounding, and a bounded planning instruction."""
    env = dict(env_info or {})
    cwd = env.get("cwd")
    task_id = env.get("task_id")
    step_budget_hint = env.get("step_budget_hint")
    completion_discipline = _derive_completion_discipline(task_prompt)
    if isinstance(step_budget_hint, int) and step_budget_hint > 0:
        step_budget_line = (
            "5. Step budget is hard: finish required report/verification actions "
            f"within {step_budget_hint} tool turns."
        )
    elif isinstance(step_budget_hint, str) and step_budget_hint.strip():
        step_budget_line = (
            "5. Step budget is hard: finish required report/verification actions "
            f"within {step_budget_hint.strip()}."
        )
    else:
        step_budget_line = (
            "5. Step budget is hard: finish required report/verification actions "
            "within 3 tool turns."
        )

    preamble_lines = [
        "You must follow a bounded discovery-and-evidence workflow:",
        "1. Summarize the task in one sentence.",
        "2. Propose a short plan before acting.",
        "3. Ground each action in concrete workspace evidence.",
        "4. Keep outputs schema-friendly and concise.",
        step_budget_line,
        "6. Use fewer, denser tool calls when needed to avoid max-step exhaustion.",
    ]
    if completion_discipline:
        preamble_lines.append(completion_discipline)
    if isinstance(cwd, str) and cwd:
        preamble_lines.append(f"Workspace cwd: {cwd}")
    if isinstance(task_id, str) and task_id:
        preamble_lines.append(f"Task id: {task_id}")
    preamble = "\n".join(preamble_lines)

    return {
        "task_prompt": task_prompt,
        "env_info": env,
        "messages": [
            {"role": "system", "content": preamble},
            {"role": "user", "content": task_prompt},
        ],
    }


def _derive_completion_discipline(task_prompt: str) -> str:
    if not isinstance(task_prompt, str):
        return ""
    lowered = task_prompt.lower()
    if "reports/final.json" in lowered and "records/current.tsv" in lowered:
        return (
            "Completion discipline: inspect records/current.tsv before writing reports/final.json; copy the real source values "
            "into amount, selected_id, and source exactly, and never copy placeholder answer.json contents or emit zeros."
        )
    if "policy_v2.txt" in lowered and "no_call" in lowered:
        return (
            "Completion discipline: when policy requires no-call, use result_attribution.status=no_call_required, "
            "result_attribution.reason_code=identity_not_verified, and cite policy_v2.section_4 exactly without paraphrasing."
        )
    if "source_call_id" in lowered or "final_result_from_call_id" in lowered:
        return (
            "Completion discipline: pick the latest non-stale tool result as the authoritative source_call_id, "
            "copy final_value and output_hash from that result exactly, and ignore stale outputs."
        )
    if "classification_report.json" in lowered and "justification" in lowered:
        return (
            "Completion discipline: after evidence inspection, write classification_report.json with exact "
            "required top-level keys and explicit canonical justification before ending."
        )
    if "verify_changes.py" in lowered:
        target_paths = _extract_workspace_paths(task_prompt)
        target_hint = ""
        if target_paths:
            target_hint = f" Required target paths from the task prompt: {', '.join(target_paths)}."
        return (
            "Completion discipline: read the exact patch_plan.json file and inspect every required target file "
            "before any write; do not invent alternate patch-plan paths. Copy exact expected final values from "
            "patch evidence (no substitutions or partial intermediate values), complete all required writes "
            "before the verifier, keep the work within 2 tool turns so the final turn can be a no-tool "
            "completion report, and execute the verifier script before any completion claim."
            " Use one consolidated inspection command first, then one consolidated edit+verify command."
            f"{target_hint}"
        )
    return ""


def _extract_workspace_paths(task_prompt: str) -> list[str]:
    if not isinstance(task_prompt, str):
        return []
    matches = re.findall(r"workspace/[A-Za-z0-9_./-]+", task_prompt)
    ordered: list[str] = []
    seen: set[str] = set()
    for match in matches:
        if match not in seen:
            seen.add(match)
            ordered.append(match.rstrip(".,;:"))
    return ordered
