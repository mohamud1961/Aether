"""Phase 6 context, completion, and tool-call repair doctrines."""

from __future__ import annotations

from typing import Any


def orient_model_led_compaction(task_prompt: str, env_info: dict[str, Any] | None = None) -> dict[str, Any]:
    return _orient(task_prompt, env_info, "candidate_plus_model_led_compaction_01", _context("model-selected compact state"))


def orient_codex_style_handoff_compaction(task_prompt: str, env_info: dict[str, Any] | None = None) -> dict[str, Any]:
    return _orient(task_prompt, env_info, "candidate_plus_codex_style_handoff_compaction_01", _context("done/next/files/commands/risk handoff"))


def orient_hybrid_receipt_handoff(task_prompt: str, env_info: dict[str, Any] | None = None) -> dict[str, Any]:
    return _orient(task_prompt, env_info, "candidate_plus_hybrid_receipt_handoff_01", _context("model summary plus concrete receipts"))


def orient_context_answer_extraction(task_prompt: str, env_info: dict[str, Any] | None = None) -> dict[str, Any]:
    doctrine = _context("answer-bearing facts, source paths, and extraction constraints")
    doctrine.append("Answer extraction: final response must quote the resolved answer fields before commentary.")
    return _orient(task_prompt, env_info, "candidate_plus_context_answer_extraction_01", doctrine)


def orient_context_budget_guard(task_prompt: str, env_info: dict[str, Any] | None = None) -> dict[str, Any]:
    doctrine = _context("highest-utility evidence under a fixed context budget")
    doctrine.append("Budget rule: drop duplicated logs before dropping task requirements, verifier output, or final answer facts.")
    return _orient(task_prompt, env_info, "candidate_plus_context_budget_guard_01", doctrine)


def orient_artifact_existence_gate(task_prompt: str, env_info: dict[str, Any] | None = None) -> dict[str, Any]:
    return _orient(task_prompt, env_info, "candidate_plus_artifact_existence_gate_01", _completion("required artifact paths exist"))


def orient_verifier_backed_completion_gate(task_prompt: str, env_info: dict[str, Any] | None = None) -> dict[str, Any]:
    return _orient(task_prompt, env_info, "candidate_plus_verifier_backed_completion_gate_01", _completion("verifier pass evidence is present"))


def orient_completion_repair_loop(task_prompt: str, env_info: dict[str, Any] | None = None) -> dict[str, Any]:
    doctrine = _completion("required artifact and verifier evidence are both present")
    doctrine.append("Repair loop: on verifier failure, perform one targeted repair and rerun the verifier before final answer.")
    return _orient(task_prompt, env_info, "candidate_plus_completion_repair_loop_01", doctrine)


def orient_required_deliverable_tracker(task_prompt: str, env_info: dict[str, Any] | None = None) -> dict[str, Any]:
    doctrine = _completion("every required deliverable is checked off with evidence")
    doctrine.append("Deliverable tracker: keep an explicit pending/done list until final closure.")
    return _orient(task_prompt, env_info, "candidate_plus_required_deliverable_tracker_01", doctrine)


def orient_tool_call_plan_tracker(task_prompt: str, env_info: dict[str, Any] | None = None) -> dict[str, Any]:
    return _orient(task_prompt, env_info, "candidate_plus_tool_call_plan_tracker_01", _toolcall("planned tool calls"))


def orient_final_required_action_tracker(task_prompt: str, env_info: dict[str, Any] | None = None) -> dict[str, Any]:
    return _orient(task_prompt, env_info, "candidate_plus_final_required_action_tracker_01", _toolcall("final required actions"))


def orient_toolcall_completion_guard(task_prompt: str, env_info: dict[str, Any] | None = None) -> dict[str, Any]:
    doctrine = _toolcall("required tool calls, required arguments, and completion gates")
    doctrine.append("Completion guard: do not close until the required call set is executed and no completion gate leaves pending actions.")
    return _orient(task_prompt, env_info, "candidate_plus_toolcall_completion_guard_01", doctrine)


def orient_bfcl_strict_argument_guard(task_prompt: str, env_info: dict[str, Any] | None = None) -> dict[str, Any]:
    doctrine = _toolcall("required tool calls and required arguments")
    doctrine.append("Argument guard: do not emit a final answer while any required argument is missing or malformed.")
    return _orient(task_prompt, env_info, "candidate_plus_bfcl_strict_argument_guard_01", doctrine)


def orient_checkpoint_verify(task_prompt: str, env_info: dict[str, Any] | None = None) -> dict[str, Any]:
    doctrine = _completion("each checkpoint artifact is re-verified before advancing")
    doctrine.append("Checkpoint rule: refresh the checkpoint state after each material edit and carry only the latest verified state forward.")
    return _orient(task_prompt, env_info, "checkpoint_verify_01", doctrine)


def orient_artifact_and_verifier_hard_gate(task_prompt: str, env_info: dict[str, Any] | None = None) -> dict[str, Any]:
    doctrine = _completion("required artifacts exist and verifier evidence confirms them")
    doctrine.append("Hard gate: artifact existence alone is insufficient; verifier-backed confirmation is mandatory for closure.")
    return _orient(task_prompt, env_info, "artifact_and_verifier_hard_gate_01", doctrine)


def orient_verified_work_pocket_handoff_hybrid(task_prompt: str, env_info: dict[str, Any] | None = None) -> dict[str, Any]:
    doctrine = _context("verified work pocket, concrete receipts, and next-step handoff state")
    doctrine.append("Work pocket: preserve a compact artifact that separates verified facts from tentative notes before any handoff or final closure.")
    doctrine.append("Closure rule: handoff and final answer must cite the verified pocket artifact or equivalent receipt set.")
    return _orient(task_prompt, env_info, "verified_work_pocket_handoff_hybrid_01", doctrine)


def orient_closure_truth_ledger(task_prompt: str, env_info: dict[str, Any] | None = None) -> dict[str, Any]:
    doctrine = _completion("one authoritative closure-truth state governs solved, partial, and blocked claims")
    doctrine.append("Closure truth ledger: preserve required deliverables, required artifact path, actual written paths, verifier attempts, latest verifier result, and unresolved blockers in one state object.")
    return _orient(task_prompt, env_info, "candidate_plus_closure_truth_ledger_01", doctrine)


def orient_evidence_state_capsule_context(task_prompt: str, env_info: dict[str, Any] | None = None) -> dict[str, Any]:
    doctrine = _context("compact evidence-state capsule and freshness carry")
    doctrine.extend(
        [
            "Evidence capsule rule: preserve verified facts, artifact refs, and freshness markers in compact form.",
            "Refresh rule: after tool output or mutation, overwrite stale state with the newest observed capsule state.",
            "Anti-stale rule: do not reuse pre-mutation values when refreshed evidence is present.",
        ]
    )
    return _orient(task_prompt, env_info, "evidence_state_capsule_context_v1", doctrine)


def orient_closure_evidence_projection(task_prompt: str, env_info: dict[str, Any] | None = None) -> dict[str, Any]:
    doctrine = _completion("the final answer projects closure evidence from the latest verified state")
    doctrine.append("Evidence projection: final answer must cite the required artifact path, verifier outcome, and blocker state instead of free-form completion claims.")
    return _orient(task_prompt, env_info, "candidate_plus_closure_evidence_projection_01", doctrine)


def orient_app_workspace_path_normalizer(task_prompt: str, env_info: dict[str, Any] | None = None) -> dict[str, Any]:
    doctrine = _completion("runtime workspace paths and required artifact paths resolve to one canonical target")
    doctrine.append("Path normalization: treat local workspace paths and /app paths as aliases, and close only when the required artifact exists at the canonical normalized target.")
    return _orient(task_prompt, env_info, "candidate_plus_app_workspace_path_normalizer_01", doctrine)


def orient_service_contract_first_receipt_closure(task_prompt: str, env_info: dict[str, Any] | None = None) -> dict[str, Any]:
    doctrine = _completion("service launch, readiness probe, and receipt closure follow the visible service contract")
    doctrine.append("Service contract rule: read service_config.json first, launch via launch_service.py, probe via literal curl contract, and normalize process_identity to executable identity.")
    return _orient(task_prompt, env_info, "service_contract_first_receipt_closure_01", doctrine)


def orient_winning_harness_v1(task_prompt: str, env_info: dict[str, Any] | None = None) -> dict[str, Any]:
    doctrine = [
        "Winning harness v1: terminal-first execution with evidence-preserving verification discipline.",
        "Persistent terminal: keep cwd/env/process state consistent across steps; do not re-bootstrap without cause.",
        "Raw bash escape hatch remains available for unknown tasks and unexpected repo layouts.",
        "Native function-call mode: when a task requires strict tool-call semantics, satisfy call order and required arguments.",
        "Script-runner discipline: prefer one asserted script for multi-step edit/verify flows instead of many brittle micro-calls.",
        "Safe path lineage: bind read path -> write path -> verifier path -> final artifact path before closure.",
        "Structured receipts: every action should preserve command/tool, cwd, exit code, key outputs, and touched artifact refs.",
        "Evidence capsule: carry forward verified facts, rejected decoys, freshness markers, and latest failure signature.",
        "Verifier/artifact gates: no completion claim without required artifact existence and verifier execution when available.",
        "Bounded recovery: classify failures, perform one targeted repair, then rerun verifier/probe before closure.",
        "Service readiness primitive: require process, route/port, and content proof; port-open alone is insufficient.",
        "Compression rule: preserve decisive error anchors, selected paths/ids/ports/hashes, and verifier assertion lines.",
    ]
    return _orient(task_prompt, env_info, "winning_harness_v1", doctrine)


def _context(selector: str) -> list[str]:
    return [
        "Unit of work: one bounded context-heavy task segment.",
        "Allowed actions: inspect, aggregate, compact, verify, and answer with evidence.",
        "Stopping rule: stop only after answer-bearing evidence is preserved or a blocker is documented.",
        f"Handoff/state output: preserve {selector}.",
        "Evidence/receipts: source paths and verifier outputs outrank model memory.",
        "Completion rule: final answer must be grounded in preserved context, not unstated recall.",
        "Failure handling: record missing context as a blocker before retrying.",
        "Uncertainty handling: separate observed facts from inferred facts.",
    ]


def _completion(proof: str) -> list[str]:
    return [
        "Unit of work: one deliverable-oriented repair or extraction task.",
        "Allowed actions: inspect, edit, create artifacts, run verifiers, and repair once on failure.",
        f"Stopping rule: done claims require proof that {proof}.",
        "Handoff/state output: list required deliverables, evidence paths, verifier results, and unresolved blockers.",
        "Evidence/receipts: progress is not completion; intermediate artifacts are not final deliverables.",
        "Completion rule: explicit artifact or verifier evidence is mandatory before final closure.",
        "Failure handling: verifier failure routes to targeted repair plus rerun, not self-acceptance.",
        "Uncertainty handling: unresolved deliverables stay open in the final state.",
    ]


def _toolcall(tracked: str) -> list[str]:
    return [
        "Unit of work: one strict tool-call completion episode.",
        "Allowed actions: plan required calls, execute calls with complete arguments, inspect results, and answer.",
        f"Stopping rule: final closure requires all {tracked} resolved.",
        "Handoff/state output: required actions, supplied arguments, missing arguments, and final call status.",
        "Evidence/receipts: tool results and argument checks must be retained.",
        "Completion rule: no final answer while any required action or argument remains pending.",
        "Failure handling: surface malformed or missing calls as behavioral failure evidence.",
        "Uncertainty handling: ask for missing external inputs only when impossible to infer from context.",
    ]


def _orient(
    task_prompt: str,
    env_info: dict[str, Any] | None,
    variant_id: str,
    doctrine: list[str],
) -> dict[str, Any]:
    env = dict(env_info or {})
    lines = [
        f"Phase 6 operating doctrine: {variant_id}.",
        "Authority: no Packet 07 movement, benchmark widening, leaderboard submission, transfer movement, protected holdouts, RHv1 unfreeze, full RHv1 revival, or task-id routing.",
        *doctrine,
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
