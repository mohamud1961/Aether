# Aether-2 Carve-Down Build Plan

Superseded, 2026-07-03: this plan is retained as historical evidence and a
portable-pattern reference only. The production target decision is now
Aether-Next canonical / Aether-2 reference. Do not start new active-harness work
from this plan; use `docs/CANONICAL_AETHER_CONSOLIDATION_PLAN.md` instead.

Historical status: this was the Aether-2 build-planning source of truth and
long-running goal baseline before the 2026-07-03 production-target decision. It
no longer authorizes new active-harness work.

Date: 2026-07-02

Planning baseline:

- `docs/HARNESS_VISION.md`
- `docs/CURRENT_ARCHITECTURE_VS_TARGET_ARCHITECTURE.md`
- `aether_next_build/HARNESS_VISION_CURRENT_STATE_AND_DELTA.md`
- `aether_next_vnext_takeover/CURRENT_STATE.md`

Readiness:

- Ready for build planning: yes.
- Ready for execution: Slice 0 baseline evidence.
- Ready for runtime coding: no, not until Slice 1 or another code slice is
  explicitly approved.

## Integration Target Decision

Historical target: this plan selected `harness/aether2/` as the implementation
target. That target decision is superseded by the canonical Aether-Next
consolidation plan.

`runner/aether2/` remains the runner-facing compatibility/export surface. Today
it aliases implementation modules from `harness/aether2/`, so it should stay
thin unless a slice explicitly needs adapter work.

`aether_next_build/aether_next/` is a reference source for workbench ownership
ideas, not the target runtime. Do not promote it wholesale. Selectively port
concepts only when they are rewritten onto the Aether-2 substrate and covered by
tests.

Rationale:

- `harness/aether2/` already has the robust substrate: loop, executor, Harbor
  backend, receipts, traces, context manager, verifier capabilities, tool
  registry, and public tests.
- `aether_next_build/aether_next/` contains the clearest WorkbenchArchitect and
  HarnessConfigIR concepts, but it also contains known prototype liabilities:
  repeated-action context risk, static prompt conflicts, silent baseline
  fallback after architect failure, duplicate architect/config paths, and
  judgement-heavy completion/proof machinery.
- A subtractive merge keeps the working substrate and imports only the ownership
  boundary, not the prototype's extra machinery.

### Post-Slice-6 Target Audit Guardrail

After Slices 0-6 landed on `harness/aether2/`, a forensic target audit in
`docs/PRODUCTION_HARNESS_DECISION_BRIEF.md` challenged the original target
choice. The audit observes that `harness/aether2/` is the repo-integrated
runner/eval-suite path, while `aether_next_build/aether_next/` carries the
recent successor-line VM evidence, standalone Terminal-Bench runner scripts, and
validated session fixes.

Until the production harness decision is explicit, this plan may continue only
with changes that are safe under either outcome:

- preserve the completed Aether-2 slices as real, tested ownership-boundary
  work;
- do not delete, sideline, or label `aether_next_build/aether_next/` as dead
  solely because this plan previously selected Aether-2;
- do not introduce new judgement logic while the target decision is unsettled;
- use Slice 7 only to inventory, quarantine clearly historical paths, and record
  deletion candidates with evidence.

The active question is not whether Slices 0-6 were real. They were. The open
question is whether those patterns should remain on Aether-2, be ported to
Aether-Next, or be used as a reference while the repo converges on one
production harness.

## Build Philosophy

This is a carve-down, not a feature expansion.

Every behavior must have one owner:

- Architect owns workbench design.
- Solver owns solving.
- Verifier owns task-state judgement.
- Harness owns substrate, routing, context mechanics, safety, traces, and
  runtime invariants.
- Official grader evaluates after agent termination.
- Ledger records evidence.

The harness must never compensate for the model. Better models should improve
the architect, solver, and verifier without new task-specific harness logic.

## Slice Contract

Every build slice must include:

```text
Adds:
Changes:
Deletes:
Deferred:
Tests:
Risk:
Rollback:
```

Every slice must say what it deletes, even when the answer is "nothing yet."
That is the guard against regrowing the harness.

Every code slice must also:

- preserve runtime invariants;
- avoid benchmark-specific logic;
- avoid silent fallback;
- keep hidden grader information out of the agent loop;
- keep deterministic checks as evidence unless they are generic runtime
  invariants;
- add or update focused tests for the changed ownership boundary;
- pass genericity checks for Aether-2 changes;
- persist a `RAW_LEDGER_UPDATE` for material architecture or behavior changes.

Top-level acceptance rule:

A slice counts as progress only if it moves task-specific intelligence out of
the harness and into the architect, solver, or verifier. If a change adds
harness-owned judgement, it must be rejected unless it is a generic runtime
invariant.

Good movement:

- architect owns prompts and workbench design;
- verifier gets bounded read-only tools;
- recent tool outputs stay in context;
- deterministic task logic is removed or demoted to verifier evidence.

Bad movement:

- benchmark- or task-specific hardcoded logic;
- larger check libraries that become semantic authority;
- deterministic task-specific completion vetoes above the verifier;
- hidden fallback to baseline;
- harness-side stuckness logic replacing better context or verifier feedback.

## Proposed Implementation Goal

Name: `aether2_architect_owned_workbench_carve_down`

Objective: make Aether-2 follow the target ownership model by choosing
`harness/aether2/` as the integration target, moving task-specific workbench
design to the architect, making the verifier the sole semantic completion judge,
demoting deterministic checks into evidence, and deleting duplicate/dead
judgement paths.

Scope:

- `harness/aether2/` implementation changes;
- `runner/aether2/` only when compatibility aliases or runner adapters need
  updates;
- focused tests under `tests/`;
- docs and raw ledger updates;
- eval substrate or board changes only when needed to represent new result-row
  semantics such as `agent_initialization_failure`.

Out of scope:

- broad variant work;
- new benchmark-specific helpers;
- prompt tournaments, bandits, forked continuation search, or micro-step
  optimization;
- semantic architect-quality retries before an eval-backed owner exists;
- moving official grader outputs into the agent loop;
- wholesale promotion of `aether_next_build/aether_next/`.

Entry criteria:

- `docs/CURRENT_ARCHITECTURE_VS_TARGET_ARCHITECTURE.md` is accepted as the
  pre-plan audit.
- This plan is approved as the build baseline.
- The first slice has an explicit objective, files, expected deletion, tests,
  and rollback.

Historical exit criteria:

- Historically, Aether-2 would have used `harness/aether2/` as the single
  implementation target.
- Architect-owned prompt/config surfaces are the only task-specific workbench
  design path.
- Recent tool outputs and receipt continuity cannot be silently dropped from
  solver/verifier context.
- Verifier has bounded read-only inspection capability and owns semantic
  completion judgement.
- Completion gate is reduced to a thin generic runtime floor.
- Fake/dead config knobs and duplicate Aether-Next judgement paths are removed
  or quarantined as historical/prototype code.
- Official grader remains post-agent measurement only.
- Focused tests, genericity checks, eval substrate smoke, and Stage 1/sentinel
  evidence are recorded.

Stop conditions:

- a slice requires hidden grader data inside the agent loop;
- a proposed mechanism hardcodes benchmark/task semantics;
- a required substrate dependency is unavailable and cannot be represented as a
  clean `invalid_due_to_environment`;
- a slice cannot state what it deletes or why it is not deleting yet;
- validation shows a regression on the target row or sentinel board that cannot
  be explained as environment/provider invalidity.

Review gate: `codex_review_skill_plus_adversarial`.

Reason: this touches runner, verifier, completion, result-row semantics, and
measurement-critical boundaries.

## Validation Ladder

Use the narrowest validation that can falsify the slice.

Baseline static and unit checks:

```bash
python3 -m pytest -q tests/test_aether2_genericity.py tests/test_aether2_launch_integrity.py
python3 tools/aether2_genericity_check.py --repo-root /Users/mohamud/Downloads/harnesseng
make public-tests
```

Focused Aether-2 checks, selected by slice:

```bash
python3 -m pytest -q tests/test_aether2_prompts.py tests/test_aether2_run_config.py
python3 -m pytest -q tests/test_aether2_compactor.py tests/test_aether2_transcript_repair.py
python3 -m pytest -q tests/test_aether2_verification_feedback.py tests/test_aether2_post_upgrade_behaviors.py
python3 -m pytest -q tests/test_aether2_executor.py tests/test_aether2_harbor_executor.py tests/test_aether2_hooks.py
```

Eval substrate smoke:

```bash
python3 - <<'PY'
from pathlib import Path
from tools.run_eval_substrate_smoke import run_smoke
print(run_smoke(Path("/private/tmp/harnesseng_eval_substrate_smoke")))
PY
```

Adapter and board contract checks:

```bash
python3 -m pytest -q tests/test_run_custom_eval_board.py tests/test_benchmark_adapter_readiness.py tests/test_benchmark_adapter_contracts.py
```

Targeted model-backed local row, only after focused non-model evidence is clean:

```bash
./.venv/bin/python tools/run_custom_eval_board.py \
  --task-pack eval_suite/families/<family>/<row_id>/task_pack.yaml \
  --output-root tracking/local_runs/custom_eval_targeted/$(date -u +%Y%m%dT%H%M%SZ)_<slice_reason> \
  --harness aether2 \
  --run-attempts \
  --model-route azure_gpt54_mini_env \
  --max-model-rows 1 \
  --list
```

Full custom board, only after targeted signal:

```bash
./.venv/bin/python tools/run_custom_eval_board.py \
  --board eval_suite/whole_harness/final_harness_v1/local_custom_eval_full_board_v1.yaml \
  --output-root tracking/local_runs/custom_eval_full_board_model_eligible/$(date -u +%Y%m%dT%H%M%SZ)_<slice_reason> \
  --harness aether2 \
  --run-attempts \
  --model-route azure_gpt54_mini_env \
  --max-model-rows 14 \
  --list
```

Stage 1 replay evidence:

- Existing `aether_next_build/run_stage1_replay_acceptance.py` is diagnostic
  historical replay evidence, not benchmark promotion evidence.
- For promoted Aether-2 changes, Stage 1 pressure must be represented through
  current Aether-2 targeted rows or certified eval substrate result rows.

## Slice 0: Target Lock And Baseline

Objective: lock the integration target and collect baseline evidence before any
runtime behavior changes.

Adds:

- this build plan;
- a baseline validation manifest listing exact commands, outputs, and any known
  environment limitations.

Changes:

- planning state only: `harness/aether2/` is the target implementation;
  `runner/aether2/` is compatibility surface; `aether_next_build/aether_next/`
  is reference/prototype.

Deletes:

- nothing yet.

Deferred:

- all runtime code changes;
- semantic architect-quality retry policy;
- any Aether-Next deletion until equivalent Aether-2 behavior is tested.

Tests:

- docs sanity read;
- `make public-tests`;
- `python3 tools/aether2_genericity_check.py --repo-root /Users/mohamud/Downloads/harnesseng`;
- record failures as baseline facts, not blockers to be hidden.

Risk:

- low behavior risk, medium governance risk if agents treat the plan as coding
  approval.

Rollback:

- revert the planning document and ledger update.

## Slice 1: Prompt Ownership Foundation

Objective: separate harness mechanical instructions from task-specific solver
and verifier behavior so the architect can become the substantive prompt owner.

Adds:

- explicit prompt ownership tests;
- a mechanical-frame prompt surface for tool schema, action syntax, safety, and
  runtime invariants;
- an architect-authored solver prompt slot and verifier prompt slot in the
  Aether-2 config path.

Changes:

- update prompt wording from "grader decides" to "official grader evaluates"
  wherever it describes the post-agent measurement boundary;
- make static solver/verifier behavior a temporary compatibility default only
  when no architect prompt is present;
- ensure prompt caching keeps the stable mechanical frame and architect prompt
  in the stable prefix.

Deletes:

- no runtime prompt yet, unless a duplicated line is proven unreachable;
- delete or deprecate any wording that implies the grader participates in the
  agent loop.

Deferred:

- full removal of compatibility default prompts until the architect startup path
  is enforced;
- semantic quality review of architect prompts.

Tests:

- `python3 -m pytest -q tests/test_aether2_prompts.py tests/test_aether2_run_config.py`;
- a new or updated test proving architect prompt content becomes the solver and
  verifier substantive prompt when supplied;
- a new or updated test proving no static behavioural solver prompt competes
  with the architect-authored solver prompt when that prompt is supplied;
- a test proving the remaining harness prompt is limited to mechanical tool,
  action-schema, safety, and runtime-invariant contract;
- genericity check.

Risk:

- prompt assembly regressions can break launch integrity or cache assumptions.

Rollback:

- revert prompt assembly changes while keeping the wording fix if it is isolated
  and tested.

## Slice 2: Architect Workbench Config And Init Failure

Objective: make architect-generated workbench config the only task-specific
design path and classify repeated format/schema failure as agent initialization
failure.

Adds:

- a narrow Aether-2 workbench config surface for solver prompt, verifier prompt,
  success definition, evidence priorities, context priorities, verifier
  capability focus, and verifier feedback style;
- one malformed/schema-invalid architect retry;
- explicit `agent_initialization_failure` representation in run metadata or
  result rows, without counting it as a task attempt.

Changes:

- evolve AHP or replace it with a WorkbenchArchitect-style config path inside
  `harness/aether2/`;
- map architect config into `HarnessRunConfig` with realization metadata;
- unsupported config fields must be rejected or reported, never silently ignored.

Deletes:

- silent fallback from failed architect/config generation to baseline for
  certified runs;
- duplicate startup paths that can both own task-specific guidance.

Deferred:

- semantic retry for weak-but-parseable architect configs;
- architect-quality rubric as a certified gate.

Tests:

- focused config tests in `tests/test_aether2_run_config.py` or a new architect
  config test file;
- launch-integrity tests for valid config, one repair success, and repair
  failure;
- eval substrate row-shape test for `agent_initialization_failure`;
- genericity check.

Risk:

- initialization failure semantics can be confused with task failure if result
  rows are not clear.

Rollback:

- revert to previous startup path for debug runs only; do not keep certified
  silent fallback.

## Slice 3: Context And Tool-Output Invariants

Objective: make recent tool outputs, verifier findings, verifier probe outputs,
and receipt continuity impossible to lose silently.

Adds:

- invariant context tests proving recent `run_command`, `read_file`,
  `write_file`, verifier capability outputs, tool errors, and active findings
  remain visible across normal turns and compaction;
- a compact receipt-continuity summary when raw output is too large.

Changes:

- audit `harness/aether2/runtime/context.py`, `compactor.py`, receipt store,
  tail helpers, and transcript repair for invariant preservation;
- architect context policy may prioritize and compress, but cannot remove
  invariant recent evidence.

Deletes:

- no-progress or repeat guidance whose only purpose was compensating for hidden
  recent outputs, once tests prove the outputs are visible.

Deferred:

- broader retrieval/replay engine work;
- any Aether-Next context compiler repair unless that path remains active.

Tests:

- `python3 -m pytest -q tests/test_aether2_compactor.py tests/test_aether2_transcript_repair.py`;
- new regression tests for the repeated-action failure family;
- targeted row only if a model-backed repeat failure is already represented in
  the eval suite.

Risk:

- context can grow too large if invariants preserve raw output naively.

Rollback:

- revert compaction changes and keep the invariant test as expected-failing
  evidence for the next attempt.

## Slice 4: Bounded Read-Only Verifier Loop

Objective: make the verifier a bounded read-only agent with small inspection
budget, not a one-shot packet judge and not a second solver.

Adds:

- verifier loop budget defaults, initially no more than three rounds;
- tests proving verifier capabilities are read-only and recorded as receipts;
- architect-owned verifier prompt and capability focus mapped into verifier
  context.

Changes:

- use existing `harness/aether2/control/verification_context.py`,
  `runtime/verify.py`, and `control/verification_rounds.py` as the foundation;
- ensure verifier probe outputs feed the next verifier judgement and the solver
  repair context when appropriate.

Deletes:

- any Aether-Next one-shot verifier packet path from the active target;
- any verifier capability surface that pretends to mutate or solve.

Deferred:

- expanding verifier tools beyond conservative read-only inspection;
- full replay/fork verifier experiments.

Tests:

- `python3 -m pytest -q tests/test_aether2_verification_feedback.py`;
- new tests for verifier read-only enforcement, probe receipt recording, and
  bounded budget exhaustion;
- genericity check.

Risk:

- verifier can become a second solver if capability scope expands too quickly.

Rollback:

- revert to previous bounded verification rounds while preserving read-only
  safety tests.

## Slice 5: Completion Authority Carve-Down

Objective: make the verifier the sole semantic completion judge and reduce the
completion gate to a thin generic runtime floor.

Adds:

- tests that deterministic checks are passed to the verifier as evidence;
- tests that generic runtime invariants still block malformed runs.

Changes:

- completion readiness becomes: verifier says complete plus generic runtime
  floor holds;
- generic runtime floor should initially include valid action/schema parsing,
  valid verifier verdict, workspace contract, required declared artifacts
  exist/non-empty when such declarations are harness-level, and no substrate
  failure.

Deletes:

- deterministic task-specific vetoes above the verifier;
- task-family proof-contract logic from the then-active Aether-2 completion
  path;
- readiness blockers based on hidden semantic inference by the harness.

Deferred:

- final deletion of historical proof modules until no active import or test
  needs them;
- any richer semantic confidence scoring.

Tests:

- focused completion/verifier tests;
- known-bad generic invariant case must fail;
- known-good verifier-complete case must pass without a deterministic semantic
  veto;
- genericity check.

Risk:

- removing too much at once can allow malformed runtime states to be called
  complete.

Rollback:

- restore only the generic runtime floor, not task-family semantic vetoes.

## Slice 6: Remove Fake Or Dead Config Surfaces

Objective: ensure every exposed config knob is real, realized, and owned by the
right role.

Adds:

- config realization audit output that lists realized, rejected, and unsupported
  fields;
- tests that unsupported architect config fields fail clearly.

Changes:

- architect config contains only real workbench design surfaces;
- solver tools stay harness-owned stable core tools unless safety disables them;
- verifier capability focus is allowed only within the generic read-only set.

Deletes:

- fake or advisory `tool_policy` knobs that imply architect-owned solver tool
  routing when the harness still exposes stable tools;
- `helper_script_policy` as a special config surface;
- solver-frustration or parse-error reconfiguration paths.

Deferred:

- any future new tool capability until a proper eval justifies it.

Tests:

- config schema and realization tests;
- prompt/config launch tests;
- genericity check.

Risk:

- deleting unused fields can break old configs or stored traces.

Rollback:

- keep a compatibility reader that rejects/records deprecated fields instead of
  silently honoring them.

## Slice 7: Duplicate Judgement Path Retirement

Objective: inventory duplicate judgement paths and retire or quarantine only
paths proven inactive or historical. Because the post-Slice-6 audit leaves the
production target unsettled, this slice is non-destructive unless an import and
entry-point inventory proves a path is unused under both Aether-2 and
Aether-Next outcomes.

Adds:

- an inventory of active imports and CLI entry points that still reference
  Aether-Next judgement modules;
- quarantine docs for any historical prototype code kept for trace replay.

Changes:

- then-active Aether-2 docs, tests, and launch paths continue to point to
  `harness/aether2/`;
- Aether-Next code is not relabeled prototype/historical merely because it is
  outside the runner-integrated Aether-2 path;
- deletion candidates are classified as `active`, `standalone-active`,
  `historical-evidence`, `reference`, or `safe-to-delete-candidate`.
- Slice 7B removed Aether-2's then-active blocker/verifier suppression path;
  blockers are now verifier-visible evidence rather than a harness-owned reason
  to skip verifier judgement.

Deletes:

- nothing from `aether_next_build/` until the production target is explicitly
  decided or a path is proven inactive under both possible targets;
- Aether-2's `should_suppress_verifier_call` authority surface and
  suppressed-blocker report path were removed in Slice 7B;
- stale tests only after replacement tests land and import/entry-point inventory
  proves they no longer protect current behavior.

Deferred:

- archived run artifacts and historical traces;
- any code required solely to replay old evidence, if clearly labeled.
- actual cross-tree deletion or quarantine of Aether-Next judgement paths until
  the production harness decision is resolved.

Tests:

- import/launch integrity tests;
- public-readiness tests;
- genericity check.

Risk:

- accidental deletion of historical evidence needed for audit.

Rollback:

- restore deleted prototype files from the slice commit, but keep target docs
  pointing at Aether-2.

## Slice 8: Official Grader And Result-Row Separation

Status: completed as boundary clarification and row-semantics fix

Completion note:

- Harbor manifests now mark official grader attribution as post-agent,
  external measurement when a completed result summary exists.
- Custom eval result rows now distinguish invalid attempts from official
  pass/fail task truth, and invalid visible-verifier/model attempts are not
  counted as scored model capability runs even when the official grader
  produced an artifact.

Objective: make the official grader boundary explicit in code, prompts, traces,
and result rows.

Adds:

- tests that official grader output is attached only after agent termination;
- result-row representation for initialization/environment invalidity that is
  distinct from task fail/pass.

Changes:

- prompts, traces, and docs consistently say the official grader evaluates;
- Harbor/Docker result attachment stays post-loop;
- verifier cannot see official grader output.

Deletes:

- any language or metadata path implying grader participation in the agent loop.

Deferred:

- official benchmark-native promotion claims until certified runs exist.

Tests:

- Harbor/adapter tests;
- eval substrate smoke;
- benchmark adapter contract tests;
- genericity check.

Risk:

- result-row semantics can blur invalid infrastructure runs with real capability
  failures.

Rollback:

- revert row-shape changes while retaining the no-grader-in-loop invariant test.

## Slice 9: Stage 1 Evidence And Sentinel Validation

Status: completed as local Stage 1/sentinel evidence; no promotion claim

Completion note:

- Ran `local_custom_eval_model_smoke_v1` non-model substrate smoke and one
  bounded GPT-5.4-mini model-backed sentinel row.
- Fixed a result-row vocabulary bug found by the first model-backed run:
  successful attempts now use `attempt_completed`, so passing model-backed
  rows count as scored model attempts.
- Fixed a proof-object ownership bug found by adversarial closeout: solver
  proof object fields are preserved under `solver_proof_object` as
  self-report, but cannot override verifier acceptance, evidence artifact
  references, task truth, score, or top-level unresolved risks.
- Current evidence supports iterate/continue validation, not promotion: the
  model-backed runtime/workspace sentinel passed the visible verifier and
  official grader, but the Aether-2 run result still had `verifier_clean:
  false` and `finalize_reason: implicit_stop`.

Objective: prove the carved-down Aether-2 path with targeted evidence before
promotion or broader work.

Adds:

- evidence bundle with target rows, sentinels, traces, grader/verifier outputs,
  failure classifications, and keep/kill/iterate decision;
- raw ledger update summarizing the scored evidence.

Changes:

- no new mechanism changes in this slice unless the prior evidence classifies a
  substrate or test bug that must be fixed before scoring.

Deletes:

- no code deletion unless prior slices left explicitly staged cleanup that is
  now proven safe.

Deferred:

- broad variant search;
- public benchmark optimization;
- full replay/fork engine.

Tests:

- targeted model-backed local row for the failure family addressed by the code
  slices;
- nearby sentinel rows, including BFCL/tool-calling if available and a simple
  TerminalBench-style verifier row;
- full custom board only after the targeted row is valid;
- inspect artifact truth, not only CLI summaries.

Risk:

- model/provider/environment invalidity can masquerade as regression or win.

Rollback:

- do not roll back solely from one invalid row; classify invalidity first. Roll
  back only on valid negative evidence or failed genericity/runtime tests.

## Approval Boundary

The next actionable decision is approval of Slice 0 or a narrowed first code
slice. Until then, this plan is the planning baseline only.

Recommended first approved code slice: Slice 1, prompt ownership foundation,
because it is narrow, testable, and establishes the "grader evaluates" wording
without touching verifier/completion semantics yet.
