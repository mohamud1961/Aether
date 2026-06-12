# Dependency / Config / Environment Family

**SNAPSHOT** — code is a verbatim copy from `blocks/` as of 2026-06-16.
These files reference `blocks.*` imports and are not standalone-runnable outside the repo root.

Note: the code in this family is shared with `filesystem_target_selection_family`.
The distinction is the failure class targeted: this family focuses on environment
bootstrap failures (wrong python invocation, stale docs, wrong canonical-runner
discovery), while `filesystem_target_selection_family` focuses on path drift
during task execution.

## What this family is

Environment bootstrap and config resolution mechanisms for tasks where the agent
fails because it cannot correctly discover or invoke the environment (wrong cwd,
wrong python, stale package docs, wrong dependency resolution).

## Variants

| Variant | File | Role |
|---|---|---|
| `cwd_workdir_invariant_guard` | `code/cwd_invariant_loop.py` | Preserves cwd/workdir invariants at each execution step |
| `candidate_plus_app_workspace_path_normalizer_01` | `code/app_workspace_path_normalizer.py` | Normalizes workspace paths for environment resolution |

## Phase evidence

Phase 4 single-family closeout (2026-05-18): target uplift existed but did not
carry to sentinels or the global board.

Phase 5 family-level diagnostic: environment/toolchain scored 4/7 on target rows.
Root causes identified: stale docs source, wrong canonical-runner discovery,
wrong python invocation. These match the mechanism claim above.

The Phase 4 authority audit explicitly flagged this family's 4/7 score as a
promising lead requiring a bounded slate around the two variants listed here,
with properly named sentinels before any next tournament run.

## Status

No tournament scoreboard exists. No variant has been promoted.
See `variants/harness/decision_history.md` Phase 4 and Phase 5 for authority audit details.
