# Hypothesis: Dependency / Config / Environment

## Claim

A cwd/workdir invariant guard combined with workspace path normalization will
reduce environment bootstrap failures (wrong python invocation, stale package
resolution, wrong canonical-runner discovery) on tasks where the agent fails
before it can attempt the core task.

## Grounding

- Phase 5 family-level diagnostic (2026-05-30): environment/toolchain rows scored
  4/7. Root causes: stale docs source, wrong canonical-runner discovery, wrong
  python invocation — all addressable by path normalization and cwd invariant
  enforcement.
- Phase 4 single-family closeout: target uplift existed (the mechanism did help)
  but the improvement did not carry to sentinels or the global board. This
  indicates the mechanism is not harmful and provides some lift, but is not
  sufficient alone.
- Phase 4 recommended next step: "better bounded slate around
  `cwd_workdir_invariant_guard` + `candidate_plus_app_workspace_path_normalizer_01`"
  — this is exactly the variant set documented here.

## Predicted outcome (if a valid eval is run)

A bounded slate combining both variants should show improvement on environment
rows where path/cwd misconfiguration is the proximate failure. Transfer risk:
the guard may over-constrain environments where non-standard paths are correct
(e.g. tasks requiring a specific non-default virtualenv).

## Required before any promotion

1. A valid eval baseline on environment/toolchain target rows with a certified backend.
2. Named regression sentinels (at minimum from filesystem and long-horizon families).
3. A preregistered prediction delta before running any mechanism variant.

## Status

`paused_hypothesis` — target uplift was observed in Phase 4 but did not carry
to sentinels. No promotion can be claimed. Next action: bounded re-run with
proper authority backend.
