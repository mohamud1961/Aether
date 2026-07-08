# Aether-2 Slice 0 Baseline Validation

Status: Slice 0 complete.

Date: 2026-07-02T18:22:22Z

Goal: lock the integration target and collect baseline validation evidence
before runtime behavior changes.

## Scope

Implementation target:

- Primary: `harness/aether2/`
- Compatibility surface: `runner/aether2/`
- Reference/prototype only: `aether_next_build/aether_next/`

Runtime code changes in this slice: none.

## Results

| Command | Result | Evidence |
|---|---:|---|
| `python3 -m pytest -q tests/test_aether2_genericity.py tests/test_aether2_launch_integrity.py` | pass | `6 passed in 0.35s` |
| `python3 tools/aether2_genericity_check.py --repo-root /Users/mohamud/Downloads/harnesseng` | pass | exit code 0, no output |
| `make public-tests` | pass | `11 passed in 0.50s` |

## Slice Contract

Adds:

- `docs/AETHER2_CARVE_DOWN_BUILD_PLAN.md` tightened as the long-running goal
  baseline.
- this baseline validation manifest.

Changes:

- planning/governance only.
- Slice 1 now explicitly requires a test proving no static behavioural solver
  prompt competes with the architect-authored solver prompt when supplied.
- the plan now includes a top-level acceptance rule: a slice counts as progress
  only if it moves task-specific intelligence out of the harness and into the
  architect, solver, or verifier, unless the change is a generic runtime
  invariant.

Deletes:

- none. Deletion is deferred because Slice 0 is evidence-only.

Deferred:

- runtime prompt ownership implementation.
- architect config/init failure implementation.
- context/tool-output invariant implementation.
- verifier/completion/grader carve-down implementation.

Tests:

- baseline public/genericity checks listed above.

Risk:

- low behavior risk because no runtime code changed.
- remaining risk is that later slices expand instead of carve down; the updated
  plan now adds an explicit acceptance rule against that drift.

Rollback:

- revert this manifest and the planning-doc edits.

## Proposed Slice 1 Boundary

Recommended next approved code slice: Slice 1, Prompt Ownership Foundation.

Slice 1 should be limited to:

- making architect-authored solver and verifier prompt slots authoritative when
  supplied;
- reducing static harness prompt content to mechanical tool/action-schema,
  safety, and runtime-invariant contract;
- changing "grader decides" wording to "official grader evaluates";
- preserving stable prompt-cache prefix behavior;
- adding focused tests for prompt ownership and non-competing static behaviour.

Slice 1 should not:

- change verifier/completion semantics;
- add new task-specific checks;
- add reconfiguration machinery;
- move official grader output into the agent loop.

