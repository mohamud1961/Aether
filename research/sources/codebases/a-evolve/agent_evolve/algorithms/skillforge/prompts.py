"""Prompt templates for A-Evolve."""

from __future__ import annotations

import json
from typing import Any

from ...contract.workspace import AgentWorkspace

DEFAULT_EVOLVER_SYSTEM_PROMPT = """\
You are a meta-learning agent that improves another agent by modifying its workspace files.

The workspace follows a standard directory structure:
- prompts/system.md  -- the agent's system prompt
- skills/*/SKILL.md  -- reusable skill definitions
- skills/_drafts/    -- draft skills from the solver
- memory/*.jsonl     -- episodic and semantic memory
- tools/             -- tool implementations

Your job each cycle:
1. Analyze task observation logs -- identify patterns, common failures, recurring themes
2. Review draft skills -- refine into real skills, merge with existing, or discard
3. Improve the system prompt if needed
4. Update memory with high-level insights, prune redundant entries
5. Use the provided bash tool to read/write files in the workspace
6. Verify your changes with `git diff` before finishing

Guidelines:
- Quality over quantity. Only create skills that genuinely help future tasks.
- Skills use SKILL.md format with YAML frontmatter (name, description).
- Keep memory concise and actionable.
- When modifying files, use precise edits.
"""


def build_evolution_prompt(
    workspace: AgentWorkspace,
    logs: list[dict[str, Any]],
    drafts: list[dict[str, str]],
    evo_number: int,
    *,
    evolve_prompts: bool = True,
    evolve_skills: bool = True,
    evolve_memory: bool = True,
    evolve_tools: bool = False,
) -> str:
    """Build the user-message prompt for one evolution cycle."""
    summaries = []
    for log in logs[-30:]:
        entry: dict[str, Any] = {"task_id": log.get("task_id", "")}
        if "success" in log:
            entry["success"] = log["success"]
        if "score" in log:
            entry["score"] = log["score"]
        feedback = log.get("evolver_feedback_detail") or log.get("feedback_detail", "")
        if feedback:
            entry["feedback"] = feedback
        summaries.append(entry)

    skills = workspace.list_skills()
    skill_names = [s.name for s in skills]

    draft_section = "No draft skills this batch."
    if drafts:
        parts = []
        for d in drafts:
            parts.append(f"#### Draft: {d['name']}\n```markdown\n{d['content'][:1000]}\n```")
        draft_section = "\n\n".join(parts)

    permission_lines = []
    if evolve_prompts:
        permission_lines.append("- You CAN modify prompts/system.md")
    if evolve_skills:
        permission_lines.append("- You CAN create/modify/delete skills in skills/")
    if evolve_memory:
        permission_lines.append("- You CAN add/prune entries in memory/*.jsonl")
    if evolve_tools:
        permission_lines.append("- You CAN create/modify tools in tools/")

    return f"""\
## Evolution Cycle #{evo_number}

### Permissions
{chr(10).join(permission_lines)}

### Task Summaries (this batch)
```json
{json.dumps(summaries, indent=2)}
```

### Draft Skills
{draft_section}

### Current Skills
{chr(10).join(f'- {s}' for s in skill_names) if skill_names else 'No skills yet.'}

### Instructions
1. Review the task summaries -- identify patterns, common failures, recurring themes
2. Review draft skills -- decide: refine into a real skill, merge with existing, or discard
3. Review current skills -- any need updating based on new evidence?
4. Review memory -- prune redundant entries, add high-level insights
5. Use the workspace_bash tool to read/write files in the workspace
6. Verify your changes with `git diff` before finishing

When done, summarize what you changed and why.
"""
