# Variant Family Seed Schema

## Purpose

Use this schema to record one surviving variant-family seed in a form that supports swappable block design, ablation planning, and eval planning.

## Required fields

```text
VARIANT_FAMILY_SEED
- seed_id:
- name:
- short_definition:
- source_mechanism_families:
- source_failure_families:
- source_eval_implications:
- evidence_paths:
- affected_block_types:
- expected_interface_pressure:
- atomic_or_combo:
- composition_constraints:
- minimal_sufficient_baseline:
- required_ablation_hooks:
- required_eval_hooks:
- likely_tradeoffs:
- contradictory_or_complicating_evidence:
- confidence:
- open_questions:
```

## Field guidance

- `affected_block_types`
  - use the repo’s harness block language where possible, such as:
    - `orientation`
    - `tool`
    - `execution`
    - `context`
    - `verification`
    - `recovery`
    - `runner`
    - `eval`

- `expected_interface_pressure`
  - describe which interfaces or contracts would need to change, stay stable, or grow

- `atomic_or_combo`
  - one of:
    - `atomic`
    - `combo`
    - `unclear`

- `composition_constraints`
  - note where the seed is only valid if other block assumptions also hold

- `minimal_sufficient_baseline`
  - identify the simpler contender that must remain visible against this seed

- `required_ablation_hooks`
  - what needs to be turned on or off cleanly to test this seed

- `required_eval_hooks`
  - what eval surfaces or measurements are required to test this seed honestly

## Rules

1. No seed without upstream evidence.
2. No seed without explicit block or interface mapping.
3. Keep atomic seeds separate from combo seeds when the distinction matters.
4. Preserve the simplest serious baseline for each seed family.
5. If block mapping or interface pressure is weakly supported, keep it explicitly unresolved instead of pretending the implementation path is already clear.
