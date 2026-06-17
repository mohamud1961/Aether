"""Environment-only orientation snapshot for bounded successor trials.

Interface: OrientationBlock.orient(task_prompt, env_info) -> initial_context
"""

from __future__ import annotations

from typing import Any


def orient(task_prompt: str, env_info: dict[str, Any] | None = None) -> dict[str, Any]:
    """Prepare a bounded environment map instruction without task-solution hints."""
    env = dict(env_info or {})
    cwd = _text(env.get("cwd"))
    task_id = _text(env.get("task_id"))
    data_root = _text(env.get("data_root"))
    python_binary = _text(env.get("python_binary"))
    safe_listing = _string_list(env.get("safe_file_listing"))
    environment_flags = _mapping_lines(env.get("environment_flags"))
    snapshot_lines = [
        "Use an environment-only snapshot before deciding edits or final claims.",
        "The snapshot may include cwd, top-level files, obvious package metadata,",
        "and entrypoint/test-command candidates discovered from repository files.",
        "Do not infer hidden answers, benchmark routing, protected holdout data,",
        "or task-specific solution hints from this instruction.",
        "Keep the snapshot compact and cite concrete observed paths.",
    ]
    if cwd:
        snapshot_lines.append(f"Workspace cwd: {cwd}")
    if data_root:
        snapshot_lines.append(f"Data root: {data_root}")
    if safe_listing:
        snapshot_lines.append("Safe file listing:")
        snapshot_lines.extend(f"- {item}" for item in safe_listing[:32])
    if python_binary:
        snapshot_lines.append(f"Use `{python_binary}` for Python commands in this environment.")
    if environment_flags:
        snapshot_lines.append("Environment flags:")
        snapshot_lines.extend(environment_flags)
    if task_id:
        snapshot_lines.append(f"Task id: {task_id}")
    return {
        "task_prompt": task_prompt,
        "env_info": env,
        "messages": [
            {"role": "system", "content": "\n".join(snapshot_lines)},
            {"role": "user", "content": task_prompt},
        ],
    }


def _text(value: Any) -> str:
    return value if isinstance(value, str) and value else ""


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _mapping_lines(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return []
    lines: list[str] = []
    for key in sorted(value):
        if not isinstance(key, str) or not key:
            continue
        item = value[key]
        if isinstance(item, bool):
            rendered = "true" if item else "false"
        elif isinstance(item, (int, float, str)) and str(item):
            rendered = str(item)
        else:
            continue
        lines.append(f"- {key}: {rendered}")
    return lines
