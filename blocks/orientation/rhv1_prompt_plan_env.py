"""RHv1 orientation with stricter evidence and completion discipline.

Interface: OrientationBlock.orient(task_prompt, env_info) -> initial_context
"""

from __future__ import annotations

from typing import Any

from blocks.orientation.prompt_plan_env import _extract_workspace_paths, orient as base_orient


def orient(task_prompt: str, env_info: dict[str, Any] | None = None) -> dict[str, Any]:
    """Wrap the shared prompt-plan-env orientation with RHv1-specific discipline."""
    context = base_orient(task_prompt, env_info)
    messages = context.get("messages")
    if not isinstance(messages, list) or not messages:
        return context

    system_message = messages[0]
    if not isinstance(system_message, dict):
        return context
    content = system_message.get("content")
    if not isinstance(content, str):
        return context

    additions = [
        "RHv1 discipline: keep an explicit target state, evidence ledger, and verification status in view throughout the run.",
        "RHv1 discipline: if a run fails, state the failure source explicitly instead of implying completion.",
    ]
    lowered = task_prompt.lower() if isinstance(task_prompt, str) else ""
    if "classification_report.json" in lowered and "justification" in lowered:
        additions.extend(
            [
                "For discovery/report tasks, end with a no-tool final report that cites the exact evidence files inspected.",
                "Do not spend the last tool turn on formatting; reserve it for the final completion decision.",
            ]
        )
    if "verify_changes.py" in lowered:
        target_paths = _extract_workspace_paths(task_prompt)
        target_hint = ""
        if target_paths:
            target_hint = f" Exact target paths from the task prompt: {', '.join(target_paths)}."
        additions.extend(
            [
                "For verify_changes tasks, reserve the final model turn for a no-tool completion report.",
                "Complete all inspection, edits, and verifier execution within at most 2 tool turns.",
                "If you use inline Python for edits, invoke python3, not python.",
                "Use the exact patch_plan.json path found in the workspace; do not invent aliases like patch_plan or workspace/patch_plan.",
                "Inspect patch_plan.json and the required target files first, apply the exact planned final replacements, run the verifier once, then report pass/fail explicitly.",
                "Use one consolidated inspection command first, then one consolidated edit+verify command." + target_hint,
            ]
        )

    system_message["content"] = content + "\n" + "\n".join(additions)
    return context
