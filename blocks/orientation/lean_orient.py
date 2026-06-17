"""Lean Orientation Block: establishes a cache-friendly, high-density system prompt.

Interface: orient(task_prompt: str, env_info: dict) -> dict
"""

from __future__ import annotations
from typing import Any

SYSTEM_PROMPT = """You are an elite software architect and Principal Harness Engineer.
Your objective is to solve the given systems-engineering or software repair task with absolute correctness, minimal steps, and peak token efficiency.

Rules of Engagement:
1. Direct Verification: Never guess or assume a process or file is ready. If you launch a service, verify it with a probe (e.g. curl, nc) before declaring success.
2. Command Compaction: Group logical commands together into single self-checking shell scripts inside raw_bash tool calls (e.g., compile, run, verify) rather than executing tiny atomic steps.
3. Path Rigor: Always check if target files exist before modifying them. Never edit or write to hallucinated paths.
4. Clean Workspace: Delete any temporary script or log files you create prior to finishing.
5. Absolute Truth: Only call the task complete when you have verifiable proof that the final artifact exists, is populated, and satisfies all requirements.
"""

def orient(task_prompt: str, env_info: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build the initial, cache-optimized context for the Zero-Abstraction Lean Harness."""
    env = dict(env_info or {})
    cwd = env.get("cwd", "/workspace")
    task_id = env.get("task_id", "unknown")

    # The Target Anchor is dynamically prepended to the user task prompt in history.
    # The system prompt remains 100% static and identical to maximize the Prompt Cache hit rate.
    anchor_header = f"=== TARGET ANCHOR STATE ===\n- CWD: {cwd}\n- Task ID: {task_id}\n===========================\n\n"
    user_content = f"{anchor_header}Task Instructions:\n{task_prompt}"

    return {
        "task_prompt": task_prompt,
        "env_info": env,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content}
        ],
    }
