# Failure Card Schema

## Purpose

Use this schema to record one failure pattern in a form that supports synthesis, eval design, and mechanism selection.

## Required fields

```text
FAILURE_CARD
- failure_id:
- name:
- short_definition:
- visible_symptoms:
- severity:
- recoverability:
- likely_failure_class:
- likely_stage:
- direct_observations:
- inferred_root_causes:
- evidence_paths:
- evidence_types:
- affected_harness_areas:
- contradictory_or_complicating_evidence:
- downstream_effects:
- candidate_mitigating_mechanisms:
- likely_eval_implications:
- confidence:
- open_questions:
```

## Field guidance

- `failure_id`
  - stable short identifier such as `false_completion_without_evidence`

- `name`
  - human-readable label

- `short_definition`
  - one-sentence description of the failure

- `visible_symptoms`
  - what an observer would see in the trace, repo, or results

- `severity`
  - one or more of:
    - low
    - medium
    - high
    - unclear

- `recoverability`
  - one or more of:
    - recoverable
    - partially_recoverable
    - terminal
    - unclear

- `likely_failure_class`
  - one or more of:
    - model
    - harness
    - environment
    - eval
    - mixed

- `likely_stage`
  - where it appears:
    - orientation
    - exploration
    - tool_use
    - context_update
    - verification
    - recovery
    - completion
    - multi_stage

- `direct_observations`
  - raw facts from trajectories, code, docs, issues, or eval artifacts

- `inferred_root_causes`
  - synthesis-level hypotheses about what is causing the failure

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

- `affected_harness_areas`
  - the parts of the harness most implicated

- `contradictory_or_complicating_evidence`
  - evidence that weakens, narrows, or complicates the attribution

- `downstream_effects`
  - what this failure tends to break, distort, or mask downstream

- `candidate_mitigating_mechanisms`
  - mechanisms that appear promising, without overclaiming

- `likely_eval_implications`
  - how the failure should shape eval design or scoring

- `confidence`
  - low | medium | high

- `open_questions`
  - unresolved uncertainty that matters

## Rules

1. Keep symptoms separate from root-cause inference.
2. Do not collapse model failure and harness failure unless the evidence really supports that.
3. Preserve mixed or uncertain cases honestly.
4. One card should capture one distinct failure pattern, not a whole family of vague bad behavior.
5. If severity, recoverability, or downstream effects are weakly supported, keep them explicitly unresolved instead of guessing.
