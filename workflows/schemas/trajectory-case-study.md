# Trajectory and Source Case Study Template

## Purpose

Use this template when analyzing one external harness or system through both:

- behavior evidence from trajectories or runs
- mechanism evidence from source code and eval code

The goal is to reconcile what the system appears to do with how it is implemented.

## Template

```text
CASE_STUDY
- system_name:
- source_family:
- priority:
- evidence_paths:
- task_or_run_scope:

## 1. Why this case matters
- why_selected:
- main_questions:

## 2. Trajectory evidence
- observed_workflow_driver:
- observed_context_behavior:
- observed_tool_behavior:
- observed_verification_behavior:
- observed_recovery_behavior:
- observed_failures:
- observed_strengths:
- uncertainty_from_behavior:

## 3. Source and eval evidence
- topology_and_structure:
- visible_mechanisms:
- tool_gateway_design:
- state_memory_artifact_design:
- verification_recovery_design:
- eval_patterns:
- hidden_or_unconfirmed_mechanisms:

## 4. Trace/source reconciliation
- where_behavior_matches_source:
- where_behavior_exceeds_visible_source:
- where_source_suggests_mechanisms_not_seen_in_runs:
- where_evidence_conflicts:

## 5. Mechanism candidates
- candidate_mechanisms:

## 6. Failure candidates
- candidate_failures:

## 7. Eval implications
- what_should_be_tested:
- what_should_be_held_fixed:
- what_could_be_gamed_or_misread:

## 8. Variant implications
- which_variant_families_this_informs:
- what_simple_contenders_should_exist:
- what_complexity_needs_justification:

## 9. Confidence and unknowns
- confidence:
- open_questions:
```

## Rules

1. Do not rely on trajectories alone when source is available.
2. Do not rely on source alone when trajectories are available.
3. Preserve disagreements between behavior and source.
4. Keep evidence paths explicit.
5. Prefer one high-quality case study over many shallow summaries.
