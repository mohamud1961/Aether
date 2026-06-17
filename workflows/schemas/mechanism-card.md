# Mechanism Card Schema

## Purpose

Use this schema to record one harness mechanism in a form that supports synthesis, eval design, and variant design.

## Required fields

```text
MECHANISM_CARD
- mechanism_id:
- name:
- short_definition:
- mechanism_family:
- harness_area:
- location_in_harness:
- operational_shape:
- problem_it_addresses:
- direct_observations:
- inferred_behavior:
- evidence_paths:
- evidence_types:
- source_families:
- task_regimes_observed:
- likely_failure_modes_addressed:
- failure_role:
- contradictory_or_complicating_evidence:
- interaction_notes:
- likely_tradeoffs:
- simplicity_note:
- likely_eval_implications:
- likely_variant_axes:
- confidence:
- open_questions:
```

## Field guidance

- `mechanism_id`
  - stable short identifier such as `post_tool_context_reinjection`

- `name`
  - human-readable label

- `short_definition`
  - one-sentence description of what the mechanism is

- `harness_area`
  - primary harness area such as tooling, context, verification, recovery, workflow, state, memory, environment, evals

- `mechanism_family`
  - larger family or cluster this mechanism belongs to

- `location_in_harness`
  - where it lives operationally, such as planner loop, tool gateway, workspace manager, verifier, or recovery controller

- `operational_shape`
  - concise description of how it behaves in practice, not just what it is called

- `problem_it_addresses`
  - the operational problem the mechanism is meant to solve

- `direct_observations`
  - facts directly seen in trajectories, code, docs, or eval repos

- `inferred_behavior`
  - synthesis-level interpretation derived from the observations

- `evidence_paths`
  - absolute file paths or stable source references

- `evidence_types`
  - one or more of:
    - trajectory
    - source_code
    - eval_code
    - paper
    - official_doc
    - engineering_writeup
    - informal_source

- `source_families`
  - which systems or source families support the card

- `task_regimes_observed`
  - what task families or operating regimes the evidence comes from

- `likely_failure_modes_addressed`
  - failures this mechanism appears to mitigate

- `failure_role`
  - one or more of:
    - preventive
    - detection
    - containment
    - recovery
    - mixed
    - unclear

- `contradictory_or_complicating_evidence`
  - evidence that weakens, narrows, or complicates the mechanism claim

- `interaction_notes`
  - important interactions with other mechanisms or harness areas

- `likely_tradeoffs`
  - costs, risks, or complexity added by the mechanism

- `simplicity_note`
  - whether this appears minimal sufficient, overly bundled, or likely more complex than necessary

- `likely_eval_implications`
  - what should be tested if this mechanism becomes a variant family

- `likely_variant_axes`
  - the main ways this mechanism could vary

- `confidence`
  - low | medium | high

- `open_questions`
  - unresolved points that should remain visible

## Rules

1. Keep direct observation separate from inference.
2. Do not record a mechanism without evidence.
3. One card should describe one mechanism, not an entire harness philosophy.
4. If the same mechanism appears in multiple systems, preserve that cross-system evidence rather than making duplicate cards.
5. If interaction, failure-role, or simplicity information is weakly supported, keep it explicitly unresolved instead of manufacturing certainty.
