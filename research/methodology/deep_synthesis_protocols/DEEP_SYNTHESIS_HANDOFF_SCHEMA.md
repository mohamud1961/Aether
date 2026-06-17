# Deep Synthesis Handoff Schema

Use this schema whenever one Deep Synthesis artifact hands structured findings to a downstream artifact.

This handoff is required between:

- `mechanism_map` -> `failure_taxonomy`
- `failure_taxonomy` -> `eval_implications`
- `eval_implications` -> `variant_family_seeds`

It may also be used for:

- `mechanism_map` -> `eval_implications`
- `mechanism_map` -> `variant_family_seeds`
- `failure_taxonomy` -> `variant_family_seeds`

## Purpose

Do not rely on implicit memory or prose-only carry-forward.

The handoff should preserve:

- claims
- evidence
- contradictions
- uncertainty
- coverage gaps

## Template

```text
DEEP_SYNTHESIS_HANDOFF
- from_artifact:
- to_artifact:
- handoff_date:
- upstream_principal_synthesis_path:
- carried_forward_claims:
  - claim_id:
    claim_summary:
    claim_level:
    confidence:
    evidence_paths:
    contradiction_status:
    downstream_rule: preserve | reinterpret_with_new_evidence | downstream_only_context
- carried_forward_contradictions:
  - contradiction_id:
    contradiction_summary:
    evidence_paths:
    downstream_obligation:
- unresolved_questions:
  - question_id:
    question:
    why_it_matters:
    related_paths:
- evidence_gaps_to_keep_visible:
  - gap_id:
    gap:
    affected_scope:
    related_paths:
- coverage_carry_forward:
  - coverage_used:
  - coverage_not_yet_used:
  - priority_sources_not_yet_read:
- adjudication_warnings_to_keep_visible:
  - warning_id:
    warning:
    related_paths:
- mandatory_rechecks_in_downstream_artifact:
  - item:
- notes_for_principal:
```

## Rules

1. `carried_forward_claims` must only include claims already accepted in the upstream principal synthesis.
2. A downstream artifact may reinterpret an upstream claim only with new cited evidence.
3. Contradictions must never be silently dropped.
4. Coverage gaps must remain visible until actually resolved.
5. `coverage_used` should carry concrete repo-local paths or path globs, not blanket claims like `full corpus`.
6. Adjudication warnings from a `pass_with_warnings` verdict must remain visible until explicitly resolved or accepted by the human owner.
7. If no structured handoff exists, the downstream artifact should treat the upstream artifact as not yet safely inheritable.

## Minimal storage convention

Default handoff path:

- `tracking/collab/stage_02_synthesis/<from_artifact>/synthesis/handoff_to_<to_artifact>.md`

Example:

- `tracking/collab/stage_02_synthesis/mechanism_map/synthesis/handoff_to_failure_taxonomy.md`
