# Aether-2 Slice 7 Duplicate Judgement Path Inventory

Status: completed as inventory; Aether-2 verifier-suppression cleanup completed in Slice 7B

Date: 2026-07-03

## Purpose

Slice 7 was originally planned as duplicate judgement path retirement. The
post-Slice-6 target audit in `docs/PRODUCTION_HARNESS_DECISION_BRIEF.md`
changed the risk profile: `harness/aether2/` is the repo-integrated Aether-2
runner/eval-suite path, while `aether_next_build/aether_next/` has recent
successor-line VM evidence and standalone Terminal-Bench runner scripts.

Because the production harness decision is not explicit, this slice does not
delete or quarantine Aether-Next runtime code. It records the active surfaces and
sets the deletion rules for the next owner.

## Adds

- A non-destructive inventory of Aether-2 and Aether-Next judgement surfaces.
- A target-ambiguity guardrail in `docs/AETHER2_CARVE_DOWN_BUILD_PLAN.md`.
- A classification rule for future cleanup:
  - `active`: repo-integrated code referenced by runner, tools, or top-level tests.
  - `standalone-active`: self-contained code with its own runner, tests, or recent
    run evidence.
  - `historical-evidence`: traces, reports, snapshots, and replay bundles needed
    to audit prior claims.
  - `reference`: design material not used as an executable path.
  - `safe-to-delete-candidate`: no active imports, no entry point, no evidence
    dependency, and replacement behavior covered by tests.

## Changes

- Slice 7 is now explicitly non-destructive until the production target is
  resolved.
- Aether-Next is not labeled dead or prototype-only solely because
  `docs/AETHER2_CARVE_DOWN_BUILD_PLAN.md` previously selected Aether-2.
- Aether-2 Slices 0-6 remain real tested work and can be retained, ported, or
  used as reference depending on the target decision.

## Deletes

- No files were deleted.
- No runtime import path was changed.
- No judgement logic was added or removed.

## Inventory

### Aether-2 Repo-Integrated Path

Classification: `active`.

Observed surfaces:

- `harness/aether2/`: canonical implementation modules.
- `runner/aether2/`: compatibility aliases to `harness/aether2`.
- `runner/model_client.py`, `runner/schemas.py`, `runner/board_preflight.py`,
  `runner/substrate/eval_substrate_execution.py`, and
  `runner/adapters/harbor_agent.py`: top-level runner/eval integration references.
- `tools/run_custom_eval_board.py` and `tools/run_tbench_model_backed.py`:
  model/eval entry points that import `harness.aether2`.
- `tests/test_aether2_*.py`, `tests/test_run_custom_eval_board.py`, and related
  adapter tests: top-level test coverage for Aether-2 behavior.

Inventory command summary:

```text
runner/tools/tests/docs files mentioning harness.aether2: 45
runner/tools/tests/docs files mentioning runner.aether2: 7
```

Active duplicate-judgement areas that remain inside Aether-2:

- `harness/aether2/control/completion.py`: still contains proof-state,
  task-done warning, and completion evidence-floor helpers. Slice 5 demoted the
  no-evidence `task_done` precheck into verifier evidence; Slice 7B removed the
  suppressed-blocker report path.
- `harness/aether2/control/verification_rounds.py`: no longer suppresses
  verifier calls for active blockers. Active blockers stay in the ledger and
  verifier context as evidence; the verifier remains the task-state judge.
- `harness/aether2/traces/blockers.py` and related blocker helpers: verifier
  blocker recording and lifecycle machinery. This is acceptable substrate when
  it records verifier findings; Slice 7B removed the exported
  `should_suppress_verifier_call` authority surface.

### Aether-Next Standalone Path

Classification: `standalone-active` plus `historical-evidence`.

Observed surfaces:

- `aether_next_build/aether_next/`: standalone Aether-Next runtime modules.
- `aether_next_build/run_pilot.py`: standalone Terminal-Bench pilot entry point.
- `aether_next_build/run_stage1_replay_acceptance.py`,
  `run_trace_verifier_replay_ab.py`, `run_verifier_only_eval.py`,
  `run_verifier_prompt_replay_eval.py`, `run_architect_only_eval.py`, and related
  scripts: replay/eval/audit entry points.
- `aether_next_build/tests/`: 31 test files for the standalone path.
- `aether_next_build/vm_goal_runs/` and reports such as
  `aether_next_build/VM_STAGE1_AUDIT.md`: recent VM evidence and mirrored run
  artifacts.

Inventory command summary:

```text
aether_next_build python files: 106
aether_next_build tests: 31
aether_next_build run scripts: 9
```

Judgement-heavy surfaces present in Aether-Next:

- `aether_next_build/aether_next/completion.py`: `CompletionGate` with blockers.
- `aether_next_build/aether_next/proof_contract.py`: proof-contract analysis and
  proof-contract receipts.
- `aether_next_build/aether_next/no_progress.py`: no-progress controller.
- `aether_next_build/aether_next/kernel.py`: wires completion gate,
  no-progress controller, proof-contract receipting, and verifier calls.
- `aether_next_build/aether_next/verifier_packets.py` and
  `context_compiler.py`: include proof-contract and no-progress evidence in
  verifier/solver context.

These are deletion candidates only if the production decision explicitly makes
Aether-2 the sole target and their replay/evidence obligations are preserved
elsewhere. If Aether-Next becomes production, these are migration targets for
the Slice 1-6 ownership boundaries, not deletion targets.

## Deferred

- Actual Aether-Next quarantine or deletion.
- Renaming or shrinking Aether-2 completion/blocker helpers.
- Stage 1/sentinel validation of Slices 1-6 against a certified eval surface.

## Tests

Passed:

```bash
python3 tools/aether2_genericity_check.py --repo-root /Users/mohamud/Downloads/harnesseng
```

Result: exit 0, no output

Passed:

```bash
python3 -m pytest -q tests/test_aether2_genericity.py tests/test_aether2_launch_integrity.py
```

Result: 6 passed in 0.66s

Passed:

```bash
make public-tests
```

Result: 11 passed in 1.04s

## Risk

- Treating Aether-Next as dead would risk deleting recent VM evidence and
  successor-line work.
- Treating Aether-2 Slices 0-6 as invalid would discard real tested ownership
  boundary improvements.
- Leaving both lines unresolved creates drift; the next substantive code slice
  should either resolve production ownership or operate only on changes that are
  safe under both outcomes.

## Rollback

Revert this document and the Slice 7 guardrail edits in
`docs/AETHER2_CARVE_DOWN_BUILD_PLAN.md`. No runtime behavior would change because
this slice is documentation and inventory only.
