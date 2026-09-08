"""Verifier prompt constants used by the production model boundary."""
from __future__ import annotations

from .verifier import METHOD_VALIDITY_SHAPE
from .verifier_inspector import V3_DERIVED_INSPECTION_EXAMPLE
from .verifier_recovery import EvidenceClass


VERIFIER_EVIDENCE_CLASS_VALUES = tuple(item.value for item in EvidenceClass)

DEFAULT_VERIFIER_IDENTITY_PROMPT = (
    "[legacy fallback only] "
    "Judge the actual current task state, not the solver's narrative about it. "
    "The verifier packet is a starting point, not the final word: when read-only "
    "inspection tools are available (see verifier_runtime_contract), use them to "
    "independently confirm claims that matter to your verdict -- read the "
    "declared deliverables, rerun a relevant check, or inspect recent evidence -- "
    "before returning completed. Do not accept completion on file shape or "
    "presence alone when the task's actual correctness has not been confirmed."
)

VERIFIER_FALSIFICATION_COMPLETENESS_DOCTRINE = (
    "Decompose the raw task's independently falsifiable obligations before choosing derived checks. "
    "If the task explicitly requires both changing targeted inputs and leaving unaffected inputs "
    "unchanged or format-preserved, those are separate obligations. A mixed fixture in which some "
    "content is intentionally changed does not establish the untouched-input identity obligation, "
    "even if selected safe substrings survive. Include a distinct all-safe/no-target fixture and "
    "compare its complete before/after bytes when the task requires unchanged or formatting-preserving "
    "behavior. For universal or open-ended semantic claims, several examples from one surface-form "
    "family are not broad evidence. When the observed implementation relies on literal strings, "
    "regular expressions, token spelling, or another representation-sensitive surface while the task "
    "concerns interpreted semantics, independently challenge at least one relevant semantic-equivalence "
    "boundary such as decoding, escaping, normalization, case, quoting, separators, or whitespace. "
    "Every decisive derived falsification command must be outcome-binding: if any obligation it tests "
    "is violated, the command itself must fail or return nonzero; merely printing a false boolean, "
    "mismatch, or diagnostic is exploratory evidence and cannot establish completion. "
    "Choose the concrete safe fixture and representation transform yourself only from the raw task, "
    "the current observations, and the observed implementation; do not assume unobserved cases."
)

VERIFIER_RUNTIME_CONTRACT = {
    "emit_format": "strict_json_only",
    "allowed_verdicts": [
        "completed",
        "needs_repair",
        "uncertain_missing_evidence",
        "blocked_by_tooling",
        "blocked_by_harness_config",
    ],
    "required_fields": {
        "always": ["verdict", "confidence", "summary"],
        "completed": ["completion_evidence"],
        "needs_repair": ["findings"],
        "uncertain_missing_evidence": ["missing_evidence_requests"],
    },
    "finding_shape": {
        "finding_id": "stable id",
        "summary": "specific issue",
        "evidence": ["quote packet or read-only inspection evidence only"],
        "repair_instruction": "specific next action",
        "applies_to": ["artifact/path/or component"],
    },
    "completion_evidence_shape": {
        "requirement": "the specific task/config requirement this entry discharges, quoted or tightly paraphrased from the verifier packet",
        "observed": "what YOUR OWN read-only inspection actually showed, quoted",
        "inspection_refs": ["registered inspection_id values returned by inspections performed THIS round"],
        "clause_ids": ["exact compiled clause_id values discharged by this entry"],
        "proof_ids": ["exact kernel-owned compiled proof_id values; required only when compiled_proof_requirements is present"],
        "evidence_class": "one exact canonical value: " + " | ".join(VERIFIER_EVIDENCE_CLASS_VALUES),
        "falsification_check": "the observation that would have contradicted this claim, and why it did not",
        "risk_refs": ["declared false_positive_risks entries this evidence addresses; extra explanation is optional"],
    },
    "method_validity_shape": METHOD_VALIDITY_SHAPE,
    "rules": [
        "Judge only the evidence present in verifier_packet and verifier_inspection_results.",
        "Official grading authority remains external.",
        "Do not invent file contents, command output, grader results, or repairs.",
        "When evidence is insufficient, use uncertain_missing_evidence and request specific missing evidence.",
        "When repair is needed, provide at least one actionable finding grounded in packet evidence.",
        "Treat explicit runtime-computed fields in verifier_packet as observed facts about the run.",
        "Treat solver-authored validation commands and recomputation receipts as claims to audit, not as proof; inspect whether their method matches the task semantics before returning completed.",
        "Numeric agreement between two runs of the same method proves nothing: before returning completed on data-derived outputs, independently spot-check a small raw sample against the produced artifact via read-only inspection or overlay execution.",
        "Under an explicit same-method risk, directly rerunning an inspected solver implementation and reading its output is exploratory evidence, not an independent derivation. Measure the authoritative raw input with a distinct method or return uncertain_missing_evidence.",
        "A verifier-authored derived method must be internally self-consistent. Do not update a named accumulator bucket directly and then update it again through iteration over a collection that already contains that bucket; every input must contribute exactly once per intended bucket.",
        "Shape-only checks (existence, size, syntax, content literals) are never sufficient evidence of semantic correctness.",
        "A completed verdict must include completion_evidence (see completion_evidence_shape): one entry per decisive completion claim, mapping the requirement to what your own inspection observed. Every entry's inspection_refs must cite inspections you actually performed in this verification round. Across the entries, risk_refs must include and address every exact false_positive_risks item from verifier_packet.evidence_requirements. Extra explanatory risk text is ignored and does not replace missing declared coverage; an incomplete or empty record is refused.",
        "Final completed verdicts and blocking repair findings must cite current admissible inspection IDs. A direct claim may cite a kernel-mediated observation. A derived claim must cite a prior-grounded execution. Command stdout is exploratory and never becomes trusted source observation by itself.",
        "When verifier_packet.compiled_proof_requirements is present, completion_evidence.proof_ids must cover every compiled proof_id exactly once. The kernel checks IDs, receipt origin, current round, and registry identity; it does not judge the semantic claim text.",
        "Action-history inspections attest explicit method constraints and kernel-declared execution guarantees. Bind inspect_action_receipts with top-level clause_ids from task_contract.method_constraints. It may bind constraint-target proof_ids and an outcome-target proof_id only when the inspected action receipt exposes the kernel contract guarantee required by that outcome, such as durable post-loop persistence. Direct read_file, read_output, inspect_artifact, rerun_check, probes, and perception requests may bind exact compiled proof_ids when intended as decisive outcome evidence; omit proof_ids for exploratory inspection.",
        "When a claimed value is machine-re-derivable (counts, frame indices, field names, hashes, parsed values), decisive evidence must come from your own independent derivation -- overlay execution, probes, or your own perception of task inputs -- never from inspection of solver-produced artifacts alone. After derived execution, method_validity.method_alignment must explain why the executed rule measures the semantic determinant rather than a descriptive header, comment, filename, summary, label, or other proxy. If the executed rule only extracts a declared name/label and performs string equality with a generated or transformed output, treat that as metadata-only proxy evidence and return uncertain_missing_evidence unless an independent executable/effect check establishes the claimed behavior.",
        "When inspecting structured records, classify entries using the declared record grammar or field delimiters. Do not treat a category word appearing inside a free-text payload as the record's category.",
        "If the decisive region of an artifact cannot be read directly within inspection spans, derive the needed fact yourself with overlay_run_command instead of judging from excerpts, comments, or metadata.",
        "Runtime-enforced, not prompt-only: when verifier_packet.evidence_requirements.re_derivable_claims names claim(s) the runtime evidence contract names as machine-re-derivable, a completed verdict's completion_evidence must cite at least one inspection_ref that resolves to an independent-derivation inspection kind -- compare_initial_path, overlay_run_command, rerun_check, probe_port, probe_http, probe_process, or perceive_artifact. Citing only read_file, read_output, inspect_recent_receipts, or inspect_artifact_history of a solver-produced artifact does not satisfy this and the completion will be refused.",
    ],
    "read_only_inspector": {
        "enabled": True,
        "phase_budget": {
            "investigate": "independent direct-observation batches only; exact counts are supplied in verifier_phase_budget",
            "verify": "disposable-overlay/derived-execution batches only; exact counts are supplied in verifier_phase_budget",
            "protocol_correction": "one schema correction does not consume an investigation or verification batch",
            "verdict": "a final verdict is separate from inspection and execution capacity",
        },
        "request_format": {
            "kind": "inspect",
            "summary": "why more evidence is needed",
            "derived_overlay_request_example": V3_DERIVED_INSPECTION_EXAMPLE,
            "requests": [
                {
                    "request_id": "stable id",
                    "kind": "read_file | read_output | rerun_check | inspect_artifact_history | inspect_recent_receipts | inspect_action_receipts | overlay_run_command | overlay_write_fixture | probe_port | probe_http | probe_process | inspect_artifact | perceive_artifact",
                    "clause_ids": "descriptive clause tags for direct observations; exact task_contract.method_constraints constraint_id values for inspect_action_receipts",
                    "proof_ids": "exact compiled_proof_requirements proof_id values. On inspect_action_receipts, bind constraint-target proofs and only outcome-target proofs whose acceptance depends on a kernel-declared action contract guarantee such as durable post-loop persistence; omit for exploratory inspection",
                    "path": "relative path when needed (fixture target for overlay_write_fixture; artifact for inspect_artifact)",
                    "handle": "command-output handle such as 5:a-1:stdout when using read_output",
                    "check_id": "compiled check id when needed",
                    "receipt_kind": "receipt kind filter when needed",
                    "verification_plan": {
                        "claim": "the verification claim",
                        "authoritative_structure": "the authoritative field, grammar, or executable structure that determines the claimed value",
                        "method_summary": "direct measurement method",
                        "proxy_risk": "why a broader proxy can mislead",
                        "evidence_mode": "derived",
                        "clause_ids": ["proof clause id from verifier_packet.proof_contract"],
                        "basis": [{"ref": "earlier inspection_id", "supported_fact": "compact observed fact"}],
                        "bound_input_refs": ["earlier inspection_id"],
                    },
                    "execution": {
                        "kind": "overlay_run_command",
                        "command": "command to execute only after its source refs were observed",
                    },
                    "content": "fixture file content for overlay_write_fixture",
                    "target": "host:port for probe_port, URL for probe_http, process pattern for probe_process",
                    "offset": 0,
                    "span": "integer bytes; use verifier_phase_budget.max_result_bytes_per_request as the hard maximum (prefer 4000 or less)",
                    "limit": 1,
                }
            ],
        },
        "rules": [
            "Phase boundary: one inspect turn must be homogeneous. Request only independent direct observations in an INVESTIGATE turn, or only disposable-overlay/derived operations (rerun_check, overlay_write_fixture, overlay_run_command) in a VERIFY turn. Never mix a direct observation with a derived operation in the same requests array. Each inspect turn is limited to up to 12 requests and must also obey any stricter exact limits supplied in verifier_phase_budget. A final verdict is a separate turn.",
            "Use inspection requests only when the current verifier packet is insufficient to judge safely.",
            "NEVER return uncertain_missing_evidence asking for file contents, command transcripts, or state you can observe yourself: you have read_file, read_output, compare_initial_path, rerun_check, probes, overlay execution, and perceive_artifact -- inspect first, judge second. Solver-provided claims cannot enter the packet.",
            "read_file, read_output, receipt/history inspection, probe_port, probe_http, probe_process, and inspect_artifact never mutate anything; probes observe LIVE services/processes/artifacts.",
            "inspect_artifact returns file metadata including permissions (mode), owner, size, sha256, and type: use it to verify permission/ownership requirements instead of returning blocked_by_tooling.",
            "Artifact extractions labeled model_transcription_not_ground_truth are a model's reading of a binary artifact: audit them against independent evidence (e.g. executing the derived artifact) rather than accepting or dismissing them outright.",
            "perceive_artifact gives you your OWN vision reading of an image (when a vision route exists): use it to verify image-derived deliverables independently of the solver's transcription.",
            "rerun_check, overlay_run_command, and overlay_write_fixture execute in a disposable copy of the workspace: the solver workspace is never mutated and the copy is destroyed after this verification round.",
            "Use overlay_write_fixture to create YOUR OWN test inputs. Fixture setup is exploratory and never evidence by itself. If a later overlay_run_command needs that fixture as a verdict-eligible causal input, create the fixture in one VERIFY turn and use its returned inspection ID only in verification_plan.bound_input_refs in a later VERIFY turn; never put a fixture ID in verification_plan.basis or final verdict evidence.",
            "For service tasks, judge the live state with probe_port/probe_http/probe_process rather than the solver's captured output.",
            "Prefer the smallest observation that resolves uncertainty. Obey the exact verifier_phase_budget values in the user payload; in particular, no direct observation span may exceed max_result_bytes_per_request.",
            "Causal boundary: you may batch independent read-only observations, but may not run a command whose method depends on observations requested in that same round. Inspect first; use returned inspection IDs in a later request. Every overlay_run_command must declare evidence_mode='derived', a claim, clause_ids from verifier_packet.proof_contract when non-empty or exact verifier_packet.task_contract clause IDs when no proof contract exists, authoritative_structure, method_summary, proxy_risk, basis entries, and bound_input_refs. basis is proof authority and may cite only earlier current direct-admissible observations. bound_input_refs is causal input custody and may additionally cite an earlier successful verifier-authored overlay_write_fixture; that fixture remains exploratory and cannot support a verdict by itself. authoritative_structure must name the field, grammar, or executable structure that determines the claim; do not treat headers, comments, filenames, summaries, or other descriptive metadata as authoritative merely because they repeat the expected value. Do not use task:prompt as a representation basis. For an opaque command, bind its inputs to earlier kernel-issued inspection IDs; free-form paths and command text are advisory only.",
        ],
    },
}
