# Hypothesis: Finalization Truth

## Claim

A Layer-2 success auditor (model-backed) combined with layered acceptance gating
and explicit trust-tier tagging will close the `ungoverned_model_claim` gap —
where the agent declares the task done but no independent verification has
confirmed it.

## Grounding

- Phase 1 kernel development (decision_history.md Phase 1): `ungoverned_model_claim`
  was identified as the recurring failure class across Phase 0 experiments.
  `GOVERNED_STATUSES` was introduced to make this explicit.
- Phase 6 (2026-06-05): `runner/kernel_layer2_audit.py` implemented; 7/7 unit
  tests pass (`tests/test_kernel_layer2_audit.py`). Adversarial review (same day)
  found the auditor was completely dead code due to a missing integration call in
  `active_evidence_kernel.py`. Integration fix applied same day.
- The adversarial review also found: "Success Contract missing" prompt instruction
  never injected; finalization gates did not block `governed_pass` when
  `success_contract_missing` was an open obligation; `render_context_pack` used
  naive character-slicing instead of adaptive compaction. All four gaps fixed
  before any eval was run — the most methodologically clean Phase in the repo.
- 7/7 unit tests pass as of HEAD.

## Predicted outcome (if a valid eval is run)

Lower `ungoverned_model_claim` false-completion rate. Transfer risk: strict
acceptance gating may reject valid completions when optional metadata is absent
but core evidence is present (documented in v04_vc_01 variant card).

## Required before any promotion

1. A valid eval baseline with a certified backend (no eval-suite run has been
   completed as of Phase 6 close).
2. Named regression sentinels from at least one other family.
3. A preregistered prediction delta.

## Status

`implementation_complete_pending_eval` — adversarially reviewed, hardened,
unit-tested. No eval-suite run completed. The implementation discipline
(adversarial review before eval) is the model for future work.
