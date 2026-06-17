# Case Studies

This directory holds promoted case studies that connect real runs, public-safe
source evidence, and careful behavioral reconstruction.

The purpose is to guarantee that Deep Synthesis includes:

- per-run depth
- cross-run depth
- cross-system comparison
- failure-point comparison
- source linkage where visible

instead of stopping at high-level wave prose.

## Required use

Every serious `mechanism_map` or `failure_taxonomy` wave should produce case studies for the active domain.

Minimum expectation:

- at least two source-linked case studies when source-backed families are materially discussed
- at least one `behavioral reconstruction` case study when a no-source family is materially discussed

## Default structure

```text
TRAJECTORY_CASE_STUDY
- case_id:
- wave:
- task_family:
- systems_compared:
- run_paths:
- outcome_profile:
- per_run_notes:
- cross_run_comparison:
- failure_point_comparison:
- source_or_architecture_links:
- behavioral_reconstruction_caveats:
- mechanism_implications:
- failure_implications:
- confidence_notes:
```

## Operating rules

1. Case studies should stay concrete.
2. They are not generic summaries of a task family.
3. If source linkage is weak, say so explicitly.
4. If explanation is only behavioral reconstruction, label it clearly.
