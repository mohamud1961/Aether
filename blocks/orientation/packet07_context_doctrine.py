"""Packet 07 Cycle 1 context-targeted doctrines."""
from __future__ import annotations
from typing import Any

def orient_work_pocket_answer_projection(
    task_prompt: str,
    env_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _orient(
        task_prompt,
        env_info,
        "candidate_plus_work_pocket_answer_projection_01",
        [
            "Cycle focus: context carry-forward, answer extraction, and final answer projection.",
            "Work pocket rule: preserve source-grounded answer facts, artifact paths, and evidence paths in a compact handoff state.",
            "Projection rule: once the answer-bearing facts are found, project the exact requested fields into the final answer rather than narrating the search.",
            "Budget rule: stop rereading once the required row, direct answer, or work-pocket total is grounded.",
            "Closure rule: if the task asks for one direct answer or one exact JSON object, the final turn should match that shape.",
        ],
    )

def orient_context_answer_closure_guard(
    task_prompt: str,
    env_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _orient(
        task_prompt,
        env_info,
        "candidate_plus_context_answer_closure_guard_01",
        [
            "Cycle focus: answer closure discipline on context-heavy tasks.",
            "Closure guard: do not spend an extra turn after the answer-bearing evidence is already sufficient to answer.",
            "Answer-only rule: if the task asks for one direct answer, return only that answer on the closing turn.",
            "Exactness rule: if the task asks for exact JSON keys or a required artifact path, include them explicitly before any commentary.",
            "Grounding rule: copy source-backed values exactly and keep derived or uncertain fields separate.",
        ],
    )

def orient_post_compute_answer_dispatch(
    task_prompt: str,
    env_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _orient(
        task_prompt,
        env_info,
        "candidate_plus_path_normalized_post_compute_answer_dispatch_01",
        [
            "Cycle focus: preserve app-evidence projection while improving direct-answer closeout under a tight step budget.",
            "Dispatch rule: once a compute step produces the decisive answer-bearing value, the next assistant turn should answer directly with no extra tool step.",
            "Record-format rule: when plain-text files use ### record headers with fields like owner, name, state, or license_plate, parse them as block records rather than CSV tables.",
            "Artifact-closeout rule: after writing a required artifact successfully, use the next turn to report the required total and artifact path instead of rereading.",
            "Budget rule: do not spend the last available step on another inspection if the answer or artifact state is already determined.",
        ],
    )

def orient_open_workflow_answer_candidate_dispatch(
    task_prompt: str,
    env_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _orient(
        task_prompt,
        env_info,
        "candidate_plus_path_normalized_open_workflow_answer_candidate_dispatch_01",
        [
            "Cycle focus: preserve app-evidence projection while surfacing a direct answer immediately after decisive open-workflow compute output.",
            "Answer-candidate rule: if a successful compute step emits one final person or value candidate, close with that exact answer on the next assistant turn.",
            "Header rule: for ### plain-text records, preserve ids and owner annotations from headers instead of assuming CSV field names.",
            "Artifact-closeout rule: after writing a required artifact successfully, use the next turn to report the required total and artifact path instead of rereading.",
            "Budget rule: do not spend the last available step on another inspection once a successful compute step already narrowed the answer to one grounded candidate.",
        ],
    )

def orient_grounded_fact_projection_dispatch(
    task_prompt: str,
    env_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _orient(
        task_prompt,
        env_info,
        "candidate_plus_path_normalized_grounded_fact_projection_dispatch_01",
        [
            "Cycle focus: preserve path normalization while surfacing machine-readable grounded facts from successful compute output.",
            "Grounded-fact rule: if stdout emits GROUNDED_FACT markers, treat them as the compact source-grounded carry-forward state.",
            "Closeout rule: if a GROUNDED_FACT direct_answer is present, answer from that fact on the next assistant turn without another inspection step.",
            "Artifact rule: if GROUNDED_FACT markers include artifact_path or evidence_path entries, reuse those exact /app paths rather than rereading for path recovery.",
            "Budget rule: use grounded-fact markers to avoid spending the last step on redundant confirmation after the decisive compute result lands.",
        ],
    )

def orient_semistructured_parser_app_evidence_projection(
    task_prompt: str,
    env_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _orient(
        task_prompt,
        env_info,
        "candidate_plus_semistructured_parser_app_evidence_projection_01",
        [
            "Cycle focus: preserve app-evidence projection while creating grounded facts from semi-structured evidence.",
            "Parsing rule: prefer direct inspection of files, logs, reports, and record blocks before ad hoc compute that assumes a rigid schema.",
            "Grounded-fact rule: if successful tool output includes parser fact receipts with provenance, treat them as the authoritative compact evidence state.",
            "Projection rule: when grounded facts already contain the requested answer fields or artifact evidence, project those exact values and paths instead of re-reading.",
            "Budget rule: once grounded facts isolate the answer-bearing records, use the remaining budget for one decisive compute or the final answer, not redundant inspection.",
        ],
    )

def orient_semistructured_header_record_parser_app_evidence_projection(
    task_prompt: str,
    env_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _orient(
        task_prompt,
        env_info,
        "candidate_plus_semistructured_header_record_parser_app_evidence_projection_01",
        [
            "Cycle focus: preserve app-evidence projection while extracting grounded facts from header-led records and nearby evidence lines.",
            "Header rule: when a record starts with a visible section header, preserve both the header identity and any inline metadata instead of treating the body lines as isolated fields.",
            "Line-hit rule: when a line match includes a numeric prefix plus a field assignment, treat the prefix as provenance and the assignment as the fact.",
            "Projection rule: once grounded facts identify the right record and its linked metadata, project those exact values and /app paths rather than rereading the same file.",
            "Budget rule: after a line match finds the target record, spend the next step on the surrounding block or the final answer, not another redundant line search.",
        ],
    )

def orient_semistructured_record_bundle_parser_app_evidence_projection(
    task_prompt: str,
    env_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _orient(
        task_prompt,
        env_info,
        "candidate_plus_semistructured_record_bundle_parser_app_evidence_projection_01",
        [
            "Cycle focus: preserve app-evidence projection while compacting matched semi-structured records into grounded bundles.",
            "Bundle rule: when a matched record has a visible header and body fields, keep it as one compact source-grounded record bundle instead of many isolated scalar fields.",
            "Provenance rule: preserve the matched line number or block identity as source_span while keeping /app paths canonical.",
            "Projection rule: when one compact record bundle already carries the requested identifiers or linked metadata, project those exact values rather than re-deriving them from repeated reads.",
            "Budget rule: after one matched record bundle is grounded, spend the next step on the linked record or the final answer, not another flat reparse of the same block.",
        ],
    )

def orient_linked_record_query_state(
    task_prompt: str,
    env_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _orient(
        task_prompt,
        env_info,
        "candidate_plus_linked_record_query_state_01",
        [
            "Cycle focus: preserve app-evidence projection while linking grounded record bundles into a compact query state.",
            "Linking rule: when grounded facts expose ids, owner references, shared attributes, or repeated keys across source families, treat them as join candidates rather than isolated records.",
            "Query-state rule: track which anchor terms, linked entities, grouping keys, ranking keys, and tie-break fields are already resolved versus unresolved.",
            "Reduction rule: once the linked query state is sufficiently resolved, spend the next step on one decisive reduction over the linked records instead of more raw inspection.",
            "Closure rule: derive the final answer or artifact from the linked grounded records, not from an ungrounded guess or repeated reread.",
        ],
    )
def orient_linked_record_anchor_window_reduction(
    task_prompt: str,
    env_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _orient(
        task_prompt,
        env_info,
        "candidate_plus_linked_record_anchor_window_reduction_01",
        [
            "Cycle focus: preserve app-evidence projection while promoting anchored record windows into linked grounded reductions.",
            "Anchor rule: when the task contains an exact quoted identifier, label, or code, locate it first and treat the surrounding record window as the primary grounding target.",
            "Window rule: when a numbered line window exposes a header-led block plus nearby key-value rows, promote that whole window into one grounded record bundle before doing more broad reads.",
            "Linking rule: after one anchored record is grounded, join outward through ids, owners, shared attributes, grouping keys, and ranking fields rather than rereading unrelated files.",
            "Reduction rule: once the anchor record and its linked candidates are grounded, spend the next step on one decisive reduction or direct answer instead of another wide scan.",
        ],
    )
def _orient(
    task_prompt: str,
    env_info: dict[str, Any] | None,
    variant_id: str,
    doctrine: list[str],
) -> dict[str, Any]:
    env = dict(env_info or {})
    lines = [
        f"Packet 07 Cycle 1 context doctrine: {variant_id}.",
        "Authority: context-targeted Packet 07 work only; no benchmark widening, leaderboard submission, transfer movement, protected holdouts, RHv1 unfreeze, or task-id routing.",
        "Unit of work: one bounded context-heavy extraction, handoff, or projection episode.",
        "Allowed actions: inspect, aggregate, compact, verify, write required artifacts, and close with source-grounded answers.",
        "Evidence rule: source paths, artifact state, and tool receipts outrank model memory.",
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
