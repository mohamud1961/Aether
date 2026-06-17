"""Phase 6.5 completion follow-up 4 doctrine."""

from __future__ import annotations

from typing import Any


def orient_path_normalized_exact_target_projection(
    task_prompt: str,
    env_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    env = dict(env_info or {})
    required_artifacts = _as_paths(env.get("required_artifact_paths"))
    required_deliverables = _as_paths(env.get("required_deliverables"))
    requires_verifier = bool(env.get("requires_verifier"))
    lines = [
        "Phase 6.5 completion follow-up 4 doctrine: candidate_plus_path_normalized_exact_target_projection_01.",
        "Authority: completion-only; no Packet 07 movement, benchmark widening, leaderboard submission, transfer movement, protected holdouts, RHv1 unfreeze, or task-id routing.",
        "Carry-forward baseline: preserve /app alias normalization and verifier-repair discipline from follow-up 2.",
        "Exact-target import: use follow-up 3 target-resolution guard to avoid sibling-path substitutions on required artifacts.",
        "Exact no-call rule: if policy blocks external tools until identity is verified, the final result_attribution must use status=no_call_required and reason_code=identity_not_verified.",
        "Artifact discipline: if the task asks for a synthesized final artifact from authoritative records, inspect the source records before writing the artifact and avoid placeholder or zeroed values.",
        "Verifier discipline: on verifier failure, perform a material repair and rerun verifier before closure claims.",
        "Closure truth: keep closure_contract_status separate from task_truth_status.",
        "Final answer rule: cite required artifact paths and the latest truthful verifier state.",
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
