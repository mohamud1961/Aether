"""Phase 6.5 completion follow-up 2 doctrine."""

from __future__ import annotations

from typing import Any


def orient_path_normalized_verifier_repair_projection(
    task_prompt: str,
    env_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    env = dict(env_info or {})
    lines = [
        "Phase 6.5 completion follow-up 2 doctrine: candidate_plus_path_normalized_verifier_repair_projection_01.",
        "Authority: completion-only; no Packet 07 movement, benchmark widening, leaderboard submission, transfer movement, protected holdouts, RHv1 unfreeze, or task-id routing.",
        "Unit of work: one completion-only repair or extraction episode.",
        "Path normalization: treat /app paths and the local workspace as aliases and operate on the canonical local target.",
        "Verifier discipline: on verifier failure, perform a material repair, rerun the verifier, and preserve the latest truthful verifier result.",
        "Closure truth: keep closure_contract_status separate from task_truth_status.",
        "Handoff/state output: preserve required deliverables, required artifact paths, actual written paths, verifier attempts, unresolved blockers, and final answer projection.",
        "Completion rule: closure-contract satisfaction alone is insufficient to claim task truth.",
        "Final answer rule: cite the required artifact path, latest verifier outcome, and any remaining blockers.",
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
