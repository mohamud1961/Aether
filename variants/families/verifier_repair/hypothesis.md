# Hypothesis: Verifier Repair

## Claim

A verifier-episode parser plus path-normalized repair projection will increase
task-pass rate on tasks where the grader requires a re-run of verification after
agent edits, by detecting and re-triggering the verification episode correctly.

## Grounding

- Phase 4 single-family closeout: both variants passed all rows — but the eval
  surface was non-discriminating (too easy). The passing result means the
  mechanism is not harmful; it does not establish that it adds value on hard tasks.
- Root cause of the family's difficulty: identifying _when_ the verifier episode
  has genuinely failed vs. when it has simply not yet run. The episode parser
  addresses this by parsing the verifier's stdout/exit pattern rather than
  relying on harness-level exit codes.
- The `path_normalized_verifier_repair_projection.py` name (original source) reflects
  that repair targeting is path-normalized to avoid off-target repair attempts.
  Renamed `verifier_repair_projection.py` in this public snapshot.

## Predicted outcome (if a valid discriminating eval is run)

On tasks where verifier exit is caused by a fixable state (wrong path, missed
re-run), the repair loop should reduce false-fail outcomes. Transfer risk: if
the eval surface is not discriminating enough, the mechanism will appear to win
without providing real uplift.

## Required before any promotion

1. A harder, more varied eval surface (per Phase 4 recommendation: "expand homolog pressure").
2. Named regression sentinels that are not trivially passed.
3. A preregistered prediction before running any mechanism variant.
4. A certified backend (not local Mac Docker) for authority.

## Status

`retest_required` — Phase 4 eval was non-discriminating. No promotion can be
claimed from that result.
