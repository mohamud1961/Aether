# Hypothesis: Filesystem Open-Workflow

## Claim

Path evidence normalization at the answer-candidate and context-dispatch layers
will reduce incorrect-target submissions on open-file tasks where path evidence
is noisy, aliased, or partially-qualified.

## Grounding

- Phase 5 family-level diagnostic: filesystem/cwd cluster scored 0/6 on its
  target rows. Root causes included wrong cwd/root and wrong target-file pattern
  matching (decision_history.md Phase 5).
- Phase 4 single-family closeout: both open-workflow routes failed entirely;
  classified as "target uplift non-existent" rather than "target uplift present
  but sentinel regression."
- The distinction from `filesystem_target_selection_family` is mechanism layer:
  this family addresses open-workflow answer candidate normalization (what the
  agent reports as the answer), while `filesystem_target_selection_family`
  addresses cwd/target-path invariants during execution.

## Predicted outcome (if a valid eval is run)

Improved path-evidence normalization should reduce wrong-file submissions on
open-file tasks. Transfer risk: normalizer may over-generalize and strip valid
path evidence for tasks where exact path specificity is required.

## Required before any promotion

1. A valid eval baseline on open-workflow target rows with a certified backend.
2. Named regression sentinels from at least one other family (per AGENTS.md rules).
3. A preregistered prediction before running any mechanism variant.

## Status

No eval run has been completed since Phase 4. This hypothesis is `blocked_pending_eval_substrate`.
