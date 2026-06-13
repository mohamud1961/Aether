# Hypothesis: Filesystem Target Selection

## Claim

Combining a cwd/workdir invariant execution guard with a decoy-resistant
context-state manager (path-normalized target projection + target resolution guard)
will reduce target-file misses and decoy-file false positives on filesystem tasks.

## Grounding

- Phase 5 family-level diagnostic (2026-05-30): filesystem/cwd rows scored 0/6.
  Root causes identified: wrong cwd/root at start and wrong target-file pattern
  matching throughout execution. Both issues are directly addressed by the
  two mechanisms in this family.
- Phase 4 single-family closeout: no scored result for this specific combination.
  The individual cwd invariant guard (v04_ex_02) and decoy-resistant selection
  (v04_cb_01) were design targets for the next bounded Goal after Phase 4.
- Variant cards `v04_ex_02` and `v04_cb_01` (see `variant_cards/`) document the
  atomic eval requirements and bounded claims for each mechanism.

## Predicted outcome (if a valid eval is run)

The 0/6 baseline creates a high ceiling for improvement. Both mechanisms target
the root causes directly. Transfer risk: strict path normalization can reject
valid symlink/alias flows; context pruning can drop multi-file task evidence.

## Required before any promotion

1. A valid eval baseline on filesystem/cwd target rows with a certified backend.
2. Named regression sentinels (at minimum BFCL and long-horizon families).
3. A preregistered prediction delta before running any mechanism variant.

## Status

`blocked_pending_target_eval` — the 0/6 failure is documented but no mechanism
tournament has been run on a certified backend. This family has the highest
potential upside in the repo given the 0/6 baseline.
