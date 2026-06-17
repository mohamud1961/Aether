"""Phase 5 workflow-doctrine orientation variants.

Interface: OrientationBlock.orient(task_prompt, env_info) -> initial_context
"""

from __future__ import annotations

from typing import Any


def orient_model_led_compaction(task_prompt: str, env_info: dict[str, Any] | None = None) -> dict[str, Any]:
    return _orient(
        task_prompt,
        env_info,
        variant_id="model_led_compaction_01",
        doctrine=[
            "Unit of work: one coherent task segment followed by model-selected compact state.",
            "Allowed actions: inspect, edit, verify, and summarize only evidence-backed state.",
            "Stopping rule: stop when verifier evidence is captured or the step budget is exhausted.",
            "Handoff/state output: preserve model-chosen goals, blockers, changed files, and verifier results.",
            "Evidence/receipts: cite concrete tool observations and artifact paths before completion.",
            "Failure handling: record failed command, inferred cause, and next repair action.",
            "Uncertainty: label assumptions separately from observed facts.",
            "Context selector: the model chooses preserved context and must justify omissions.",
        ],
    )


def orient_harness_led_receipt_compaction(task_prompt: str, env_info: dict[str, Any] | None = None) -> dict[str, Any]:
    return _orient(task_prompt, env_info, "harness_led_receipt_compaction_01", _receipt_doctrine("harness"))


def orient_hybrid_model_handoff_plus_receipts(task_prompt: str, env_info: dict[str, Any] | None = None) -> dict[str, Any]:
    return _orient(task_prompt, env_info, "hybrid_model_handoff_plus_receipts_01", _receipt_doctrine("hybrid"))


def orient_codex_style_handoff_compaction(task_prompt: str, env_info: dict[str, Any] | None = None) -> dict[str, Any]:
    return _orient(
        task_prompt,
        env_info,
        "codex_style_handoff_compaction_01",
        [
            "Unit of work: current objective, working set, and verification state.",
            "Allowed actions: keep momentum through inspect, patch, test, and concise status updates.",
            "Stopping rule: emit a handoff when work is complete, blocked, or context must compact.",
            "Handoff/state output: include done, next, files touched, commands run, and residual risk.",
            "Evidence/receipts: retain exact verifier commands and artifact refs.",
            "Failure handling: preserve failed attempts without deleting traces.",
            "Uncertainty: name what was not checked.",
            "Context selector: preserve user intent, current plan, modified files, and latest verifier truth.",
        ],
    )


def orient_bounded_episode(task_prompt: str, env_info: dict[str, Any] | None = None) -> dict[str, Any]:
    return _orient(
        task_prompt,
        env_info,
        "bounded_episode_01",
        [
            "Unit of work: one bounded episode of at most two dense tool turns plus a final no-tool report.",
            "Allowed actions: inspect first, then perform a consolidated edit/verify action.",
            "Stopping rule: stop after verifier evidence, blocker evidence, or two tool turns.",
            "Handoff/state output: report episode goal, actions, evidence, and next episode recommendation.",
            "Evidence/receipts: attach tool receipts to each claim.",
            "Failure handling: record the first failing command and avoid repeating it unchanged.",
            "Uncertainty: mark incomplete checks as open risk.",
            "Episode size: small fixed pocket, optimized for clean handoff over exhaustive probing.",
        ],
    )


def orient_adaptive_episode(task_prompt: str, env_info: dict[str, Any] | None = None) -> dict[str, Any]:
    return _orient(
        task_prompt,
        env_info,
        "adaptive_episode_01",
        [
            "Unit of work: an episode sized by risk, dependency count, and verifier availability.",
            "Allowed actions: expand only when new evidence changes the repair target.",
            "Stopping rule: stop when marginal probing becomes redundant or verifier truth is obtained.",
            "Handoff/state output: report why the episode stopped and what the next episode needs.",
            "Evidence/receipts: keep receipts for target selection, edits, and verification.",
            "Failure handling: change strategy after repeated failure rather than retrying blindly.",
            "Uncertainty: separate likely causes from proven causes.",
            "Episode size: adapt between one and three tool turns, never exceeding the run budget.",
        ],
    )


def orient_failure_autopsy_repair_loop(task_prompt: str, env_info: dict[str, Any] | None = None) -> dict[str, Any]:
    return _orient(task_prompt, env_info, "failure_autopsy_repair_loop_01", _repair_doctrine("failure autopsy"))


def orient_verification_repair_loop(task_prompt: str, env_info: dict[str, Any] | None = None) -> dict[str, Any]:
    return _orient(task_prompt, env_info, "verification_repair_loop_01", _repair_doctrine("verification"))


def orient_bigai_style_manager_worker_verifier(task_prompt: str, env_info: dict[str, Any] | None = None) -> dict[str, Any]:
    return _orient(
        task_prompt,
        env_info,
        "bigai_style_manager_worker_verifier_01",
        [
            "Unit of work: manager plan, worker execution, verifier challenge, then final synthesis.",
            "Allowed actions: manager assigns bounded work; worker inspects/edits; verifier tests claims.",
            "Stopping rule: stop only after verifier pass, explicit verifier fail, or hard blocker.",
            "Handoff/state output: include manager decision, worker evidence, verifier verdict, and next action.",
            "Evidence/receipts: worker and verifier claims require tool receipts or artifact refs.",
            "Failure handling: verifier failures route back to one targeted repair, not broad replanning.",
            "Uncertainty: unresolved disagreements remain explicit in the final report.",
            "Coordination boundaries: roles are simulated in one context; no hidden shared chat or task-ID routing.",
        ],
    )


def _receipt_doctrine(selector: str) -> list[str]:
    chooser = "the harness receipt chain" if selector == "harness" else "model summary plus harness receipts"
    return [
        "Unit of work: task segment with receipt-backed state compaction.",
        "Allowed actions: inspect, edit, verify, and compact only receipt-supported claims.",
        "Stopping rule: stop when required receipts cover target, change, and verification state.",
        "Handoff/state output: preserve receipts, unresolved blockers, and next repair hypothesis.",
        "Evidence/receipts: receipts outrank free-form memory when they conflict.",
        "Failure handling: keep failure receipts and route the next attempt through a changed hypothesis.",
        "Uncertainty: record unknowns as missing receipts.",
        f"Context selector: {chooser} selects preserved context.",
    ]


def _repair_doctrine(loop_name: str) -> list[str]:
    return [
        f"Unit of work: one {loop_name} diagnosis followed by one targeted repair attempt.",
        "Allowed actions: reproduce or inspect failure, infer cause, repair, and verify.",
        "Stopping rule: stop after a changed repair is verified or the repeated mistake is detected.",
        "Handoff/state output: failed attempt, root-cause hypothesis, repair action, verifier result.",
        "Evidence/receipts: failed and passing verifier outputs must both be retained.",
        "Failure handling: do not repeat the same command or edit without a new hypothesis.",
        "Uncertainty: mark root cause as tentative unless verifier evidence confirms it.",
    ]


def _orient(
    task_prompt: str,
    env_info: dict[str, Any] | None,
    variant_id: str,
    doctrine: list[str],
) -> dict[str, Any]:
    env = dict(env_info or {})
    lines = [
        f"Phase 5 operating doctrine: {variant_id}.",
        "No Packet 07 movement, transfer, benchmark widening, protected holdouts, RHv1 unfreeze, or task-ID routing.",
        *doctrine,
    ]
    cwd = env.get("cwd")
    task_id = env.get("task_id")
    if isinstance(cwd, str) and cwd:
        lines.append(f"Workspace cwd: {cwd}")
    if isinstance(task_id, str) and task_id:
        lines.append(f"Task id: {task_id}")
    return {
        "task_prompt": task_prompt,
        "env_info": env,
        "messages": [
            {"role": "system", "content": "\n".join(lines)},
            {"role": "user", "content": task_prompt},
        ],
    }
