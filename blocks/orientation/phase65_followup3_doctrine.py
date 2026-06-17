"""Phase 6.5 completion follow-up 3 doctrine."""

from __future__ import annotations

from typing import Any


def orient_path_normalized_target_resolution_guard(
    task_prompt: str,
    env_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    env = dict(env_info or {})
    required_artifacts = _as_paths(env.get("required_artifact_paths"))
    required_deliverables = _as_paths(env.get("required_deliverables"))
    requires_verifier = bool(env.get("requires_verifier"))

    lines = [
        "Phase 6.5 completion follow-up 3 doctrine: candidate_plus_path_normalized_target_resolution_guard_01.",
        "Authority: completion-only; no Packet 07 movement, benchmark widening, leaderboard submission, transfer movement, protected holdouts, RHv1 unfreeze, or task-id routing.",
        "Unit of work: one completion-only repair or extraction episode.",
        "Path normalization: treat /app paths and local workspace paths as aliases, but resolve truth against exact required /app targets.",
        "Target resolution: never substitute sibling or similar-basename paths for required targets.",
        "Closure truth: keep closure_contract_status separate from task_truth_status.",
        "Completion rule: closure-contract satisfaction alone is insufficient to claim task truth.",
        "Final answer rule: cite exact required target paths and the latest truthful verifier state.",
    ]
    if required_artifacts:
        lines.append(f"Required artifact paths: {', '.join(required_artifacts)}")
    if required_deliverables:
        lines.append(f"Required deliverables: {', '.join(required_deliverables)}")
    lines.append(f"Requires verifier: {'yes' if requires_verifier else 'no'}")
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


def _as_paths(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(path) for path in value if isinstance(path, str) and path]
