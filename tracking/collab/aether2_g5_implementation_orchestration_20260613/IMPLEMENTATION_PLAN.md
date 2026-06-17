# Aether-2 G5 Harness Upgrade Implementation Plan

**Status:** ACTIVE  
**Created:** 2026-06-13  
**Owner:** Codex orchestrator  
**Execution teams:** Runner/Measurement Team (GPT-5.4-mini) and Harness/Agent Team (GPT-5.4)  
**Review gate:** `codex_review_skill_plus_adversarial`

## 1. Objective

Implement the evidence-backed Aether-2 upgrades identified by the valid Attempt 1
failure atlas, without using contaminated Attempt 2 as scoring evidence and without
adding benchmark-specific behavior.

The implementation must:

1. preserve and finish runner validity, truthful rows, and complete receipts;
2. keep the stated task contract salient at decision time;
3. maintain a compact, durable requirement/evidence/issue ledger;
4. treat `task_done` as a request for bounded verification rather than proof;
5. distinguish weak evidence from end-to-end evidence using generic rules;
6. detect semantic no-progress loops rather than only byte-identical retries;
7. remove multiline-command and detached-job execution distortion;
8. surface decisive errors from truncated output;
9. pass deterministic harness-behavior evals before any real task rerun;
10. validate on a targeted board of no more than ten tasks before considering a
    broader checkpoint.

This plan supersedes the implementation portions of:

- `tracking/collab/aether2_g5_run_analysis_20260613/G5_EXECUTION_PLAN.md`
- the orchestration material pasted in
  `/Users/mohamud/.codex/attachments/c47871a9-f5eb-4baf-bf33-97c73d25fecb/pasted-text.txt`

The earlier documents remain evidence and history.

## 2. Governing Evidence

Read before implementation:

- `AGENTS.md`
- `tracking/collab/aether2_build_spec/AETHER2_BUILD_SPEC.md`
- `tracking/collab/aether2_g5_run_analysis_20260613/`
- `tracking/collab/variant_hypothesis_backlog.md`
- frozen VM pull:
  `tracking/collab/vm_pulls/tracking/collab/aether2_g5_failure_analysis_clean_20260613T121431Z/`
- the supplied transcript:
  `/Users/mohamud/.codex/attachments/c47871a9-f5eb-4baf-bf33-97c73d25fecb/pasted-text.txt`

Evidence rules:

- Attempt 1 is the authoritative scoring population.
- Attempt 2 is contaminated diagnostic evidence only.
- No score, failure count, or projected flip may merge Attempt 2 into Attempt 1.
- `error_grep.txt` is an index, never primary evidence.
- Claims must be grounded in rows, logs, receipts, grader output, traces, or source
  snapshots.

## 3. Doctrine And Governance Reconciliation

The implementation may use only:

- the task-visible instruction;
- model-visible messages;
- model actions and claims;
- tool observations;
- file, artifact, process, job, and session state;
- the model's declared checks;
- generic evidence-quality rules;
- verifier feedback derived from visible evidence.

It must not use:

- hidden tests or hidden grader behavior;
- expected answers;
- task IDs or task-specific branches in `runner/aether2/`;
- benchmark vocabulary in prompts;
- task-family playbooks;
- action rewriting;
- harness-side planning;
- unbounded completion vetoes.

### Completion semantics

`task_done` is a request for verification, not proof of completion.

To remain compatible with the active Aether-2 doctrine:

- `SATISFIED` may mark the run internally clean.
- `UNSATISFIED` or `UNVERIFIABLE` triggers a factual repair reflection.
- Repair remains bounded by the existing maximum of three verification rounds.
- The harness does not rewrite actions or loop forever.
- If gaps remain after the bounded rounds, the run terminates honestly as
  internally unresolved; it must not be labelled `verifier_clean=True`.
- The external grader remains the only benchmark pass/fail authority.

This is bounded reflection and truthful status reporting, not an unbounded
completion-control doctrine.

## 4. Current State And Work Already Completed

Do not duplicate these blindly:

- `scripts/run_aether2_tournament.sh` exists with PYTHONPATH preflight,
  fail-fast launch detection, and `invalid_launch` recording.
- `tests/test_aether2_entrypoint_import_hygiene.py` exists.
- `tracking/collab/aether2_g5_run_analysis_20260613/L1_vm_patch.md` contains
  the VM-only `run_aether2_g3_official.py` import fix and L1 measurement checklist.
- The VM received an observable decision-trace prototype:
  `runner/aether2/decision_trace.py`, `tools/aether2_decision_trace.py`,
  `tests/test_aether2_decision_trace.py`, and
  `scripts/run_aether2_one_safe.sh`.
  These files are not all present in the Mac checkout. They are harvest sources,
  not automatically approved production code.
- `ReceiptWriter.record_model_exchange` already records complete request messages,
  response text, and tool calls.
- The loop already has bounded fresh-context verification and repair rounds.
- The loop already carries delta state, tail telemetry, receipts, compaction,
  mirror notes, job/session registries, and raw-log paths.

Before editing, each team must compare live Mac files, frozen VM source snapshots,
and any VM-only prototype. Preserve useful work but revalidate its design.

## 5. Ownership Boundary

### Team R: Runner And Measurement

Model: GPT-5.4-mini, with bounded subagents.

Exclusive production ownership:

- `tools/run_aether2_g3_official.py` if/when synced from VM;
- `tools/run_aether2_g2.py`;
- runner/eval CLI utilities under `tools/`;
- tournament and safe-run scripts under `scripts/`;
- result-row, run-journaling, mount, grader-launch, bundle, and decision-trace
  extraction infrastructure outside `runner/aether2/`;
- runner/eval infrastructure tests that do not alter model behavior;
- targeted-board manifests and runbooks.

Team R must not modify model-facing behavior in `runner/aether2/`.

### Team H: Harness And Agent Behavior

Model: GPT-5.4, with bounded subagents.

Exclusive production ownership:

- `runner/aether2/*.py`;
- model-facing state, context, prompts, verification, execution tools, deltas,
  receipts, mirrors, compaction, and metrics;
- `tests/test_aether2_*.py` for harness behavior.

Team H must not own official-task scheduling, VM runner orchestration, official
test mounting, or external grader result classification.

### Shared files

The teams must not edit the same file concurrently.

Potentially shared documentation:

- this implementation directory;
- `tracking/collab/variant_hypothesis_backlog.md`;
- ledger inbox handoffs.

Each team writes a separate handoff. The parent orchestrator integrates shared
documentation after both teams return.

## 6. Dependency Graph

```text
R0/H0 source reconciliation
        |
        +---------------------------+
        |                           |
R1 runner validity             H1 receipt/input truth
R2 row journaling                   |
R3 grader/mount fidelity       H2 contract rebinding
R4 trace extraction                 |
        |                      H3 durable evidence ledger
        |                           |
        |                      H4 evidence strength
        |                           |
        |                      H5 bounded verifier semantics
        |                           |
        |                      H6 semantic no-progress
        |                           |
        |                      H7 tool-channel cleanup
        |                           |
        |                      H8 structured truncation
        |                           |
        +-----------+---------------+
                    |
             I1 behavior eval board
                    |
             I2 full local regression
                    |
             I3 targeted run manifest
                    |
             I4 <=10 task VM board
```

No task board may run before I1 and I2 are green.

## 7. Team R Work Packages

### R0. Reconcile Mac And VM Runner State

Deliverables:

- inventory live Mac, frozen VM snapshot, and VM-only prototype;
- identify which runner files need syncing rather than recreation;
- document checksums or diffs for `run_aether2_g3_official.py`,
  decision-trace utilities, and safe-run launcher;
- write `runner_state_reconciliation.md`.

No behavior change in this package.

### R1. Entrypoint And Launcher Integrity

Files:

- `scripts/run_aether2_tournament.sh`
- `tests/test_aether2_entrypoint_import_hygiene.py`
- VM/live `tools/run_aether2_g3_official.py`
- narrowly scoped launcher tests.

Requirements:

- every `tools/run_aether2_*.py` self-locates from a foreign cwd with an empty
  `PYTHONPATH`;
- launcher preflight fails before touching a corpus;
- repeated instant crashes stop the board;
- no broad Docker/process killing;
- launch failures produce attributable, structured invalid rows;
- dry-run must exercise real argument and preflight construction.

### R2. Truthful Phase Journaling And Invalid Classification

Implement durable phase rows:

- initialized;
- agent run started;
- agent run completed;
- grader run started;
- grader run completed.

Classify separately:

- `invalid_launch`;
- `invalid_environment`;
- `invalid_provider`;
- `invalid_resource_killed`;
- `invalid_grader`;
- valid external pass/fail.

Requirements:

- provider 400, Docker 137, missing grader toolchain/127, timeout, and killed
  phases cannot silently become capability failures;
- interrupted runs retain the last phase row;
- scoring denominators exclude invalid populations;
- existing Attempt 1/Attempt 2 provenance is retained.

### R3. Official Test Mount And Hermetic Grader

Runner-only responsibilities:

- provide official tests at the official path and runner path without exposing
  them to the model before the agent phase;
- ensure the grader invokes its own known toolchain rather than an agent-mutated
  PATH or environment;
- preserve hidden-test isolation;
- record mount manifest and grader environment manifest;
- add deterministic tests for dual-path availability and agent/grader isolation.

No grader expectations may enter model-visible context.

### R4. Observable Decision Trace And Receipt Bundling

Harvest the VM prototype carefully.

Produce a generic post-run analysis utility that:

- reads result rows and actual receipts;
- labels every event with source run and attempt provenance;
- records visible action, preceding observation, resulting observation,
  evidence classification, and unresolved verifier gaps;
- explicitly states that it is not private chain-of-thought;
- never invents reasoning or hidden intent;
- tolerates missing/malformed rows;
- avoids scanning permission-heavy workspaces when indexed result roots exist.

This utility is analysis-only. It must not feed classifications back into the
model; Team H owns model-facing behavior.

### R5. Fast Targeted Board Infrastructure

Create a board manifest format supporting at most ten tasks and recording:

- failure family;
- reason selected;
- expected capability pressure;
- baseline evidence;
- predicted change;
- named sentinels;
- resource class;
- timeout;
- contamination controls.

Scheduler constraints:

- no more than three light containers concurrently;
- one heavy build at a time;
- one QEMU/service-sensitive task at a time;
- disk and process-pressure preflight;
- cleanup only attributable resources;
- immutable output directory per task and attempt.

Do not execute the board until the integration gate authorizes it.

## 8. Team H Work Packages

### H0. Source Map And Contract Tests

Before production edits:

- map every proposed feature to current functions and tests;
- record the exact model-message assembly path;
- record the exact verification and repair path;
- identify existing behavior that already satisfies requirements;
- write failing characterization tests before changing semantics.

Only the Team H lead may edit `runner/aether2/loop.py`.

### H1. Receipt And Model-Input Truth

Files:

- `runner/aether2/receipts.py`
- `runner/aether2/context.py`
- `tests/test_aether2_receipts.py`
- `tests/test_aether2_context.py`

Requirements:

- each model call records exact messages supplied, tool schemas or their stable
  digest, response text, response tool calls, and call role;
- receipts identify normal, closing, compaction, verifier, and repair calls;
- record the live ledger/tail state associated with the call;
- receipts remain model-invisible and credential-free;
- no hidden reasoning telemetry is requested or fabricated.

### H2. Top And Bottom Completion-Contract Rebinding

Files:

- `runner/aether2/context.py`
- `runner/aether2/prompts.py`
- integration in `runner/aether2/loop.py` by the Team H lead.

Requirements:

- immutable prefix contains the complete stated task contract;
- dynamic tail contains a compact completion-contract reminder;
- tail identifies unresolved requirements and next required evidence;
- wording is generic and non-benchmark-specific;
- no duplicate nag is emitted when state has not changed;
- cache-stable prefix behavior remains intact;
- the model-owned plan remains separate from harness factual state.

### H3. Durable Evidence And Issue Ledger

Primary ownership:

- `runner/aether2/delta.py`
- `runner/aether2/compactor.py`
- integration in `context.py`/`loop.py`.

Ledger schema:

- stated requirements;
- status: `unproven | partial | proven | contradicted`;
- evidence references;
- evidence strength;
- failed checks;
- disproven assumptions;
- open risks;
- verifier blockers;
- repeated failure families;
- next required evidence.

Rules:

- updates derive from visible observations and verifier reports;
- exit zero alone cannot prove a requirement;
- failed checks remain visible until superseded by stronger evidence;
- evidence records cite tool step/raw-log/artifact references;
- ledger is compact, bounded, serialized in receipts, visible in tail telemetry,
  and preserved through compaction;
- the harness does not synthesize a task plan.

#### Verifier Blocker Persistence

Every `unsatisfied` or `unverifiable` verifier finding becomes a persistent
ledger blocker. Parse/schema failures also create blockers instead of
disappearing into a generic verifier error.

Each blocker records:

- stable blocker ID;
- requirement ID/text;
- verdict and reason codes;
- `created_step`, `last_updated_step`, and `age_steps`;
- rejected or insufficient evidence references;
- why the evidence was insufficient;
- required next evidence;
- evidence version/hash last evaluated;
- status:
  `active | candidate_resolved | resolved | obsolete | exhausted`;
- resolution evidence and verifier confirmation when applicable.

Blockers persist across normal model calls, repair rounds, rebases, and
compaction. A changed summary, repeated `task_done`, or unrelated delta cannot
erase or resolve them.

State transitions:

- `active`: unresolved and awaiting blocker-relevant evidence;
- `candidate_resolved`: new relevant evidence exists but is not yet confirmed;
- `resolved`: verifier confirms the requirement is satisfied;
- `obsolete`: the requirement was legitimately superseded, with the reason
  retained;
- `exhausted`: the bounded repair allowance ended without proof.

Verifier suppression and completion precheck:

- do not call the verifier again for an unchanged blocker unless new
  blocker-relevant evidence appeared;
- relevance requires a requirement/evidence link, a changed referenced
  artifact, a new declared-check result, or directly related
  service/process/session state;
- record a suppressed-verifier event instead of spending another model call;
- if `task_done` is called with active blockers and no new relevant evidence,
  pre-reject it and return the blocker plus required next evidence;
- this remains factual bounded reflection, never action rewriting or an
  unbounded completion loop;
- after the three-round allowance, terminate honestly with unresolved blockers
  marked `exhausted`.

### H4. Generic Evidence-Strength Classification

Primary ownership:

- `runner/aether2/verify.py`
- possibly factual helper functions in `delta.py`;
- tests in `tests/test_aether2_verify.py`.

Weak evidence signals include:

- existence/read-only content checks without a semantic assertion;
- `--help`, `--version`, `command -v`, or import-only checks;
- shape/count/schema checks without value or invariant checks;
- process existence or port-open-only checks;
- environment/path mutation used to make an import pass;
- partial test selection where broader discoverable tests exist;
- swallowed failures such as `|| true`.

Stronger evidence signals include:

- clean execution in the target environment;
- representative input/output;
- independent value or invariant comparison;
- artifact parse and use;
- client interaction with a service;
- observable UI/session behavior;
- task-visible provided checks without environment hacks.

Requirements:

- classifications are heuristic reflections, never hidden-grader predictions;
- output includes reasons, confidence, and evidence references;
- no task names or benchmark terms;
- a weak signal does not automatically mean failure;
- requirement proof needs appropriate evidence, not merely a regex score.

### H5. Bounded Verifier Completion Semantics

Primary ownership:

- `runner/aether2/verify.py`
- Team H lead integration in `runner/aether2/loop.py`.

Required invariant:

- any `unsatisfied` or `unverifiable` requirement remains an unresolved gap;
- parse/schema failure remains unresolved;
- unresolved gaps imply `verifier_clean=False`;
- unresolved gaps trigger factual repair feedback for at most three rounds;
- after exhaustion, the run exits honestly as unresolved rather than claiming
  internal completion;
- external grader truth remains separate.

Integrate the H3 blocker state machine:

- verifier output creates or updates persistent blockers;
- only relevant evidence moves `active` to `candidate_resolved`;
- only verifier confirmation moves it to `resolved`;
- repeated `task_done` with unchanged evidence is pre-rejected without another
  verifier model call;
- compaction preserves blocker identity, age, status, rejected evidence, and
  required next evidence;
- metrics count suppressed verifier calls and repeated completion requests
  rejected without new evidence.

This intentionally reverses the temporary G2 behavior that treated all
`unverifiable` requirements as non-discrepant. Tests must cover the interaction
and prevent infinite loops.

### H6. Semantic No-Progress Detection

Primary ownership:

- `runner/aether2/mirror.py`
- factual state from `delta.py`;
- Team H lead integration in `loop.py`.

Track:

- normalized action family;
- target path/package/service/process;
- failure class before and after;
- requirement advancement;
- new artifact or file evidence;
- stronger evidence added;
- repeated failed strategy count.

Trigger a factual reflection when:

- one strategy family repeats at least three times;
- the same failure class persists;
- no requirement advances;
- no stronger evidence or meaningful artifact change appears.

Reflection must:

- identify observed repetition and unchanged state;
- request a new hypothesis or strategy family;
- never prescribe the solution;
- reset when meaningful progress occurs;
- avoid false positives on legitimate polling and bounded retries.

### H7. Tool-Channel Cleanup

Primary ownership:

- `runner/aether2/executor.py`
- `runner/aether2/jobs.py`
- relevant tests.

Requirements:

- multiline `run_command` executes via a literal generated script, not `eval`;
- detached jobs execute a literal script, not `eval`;
- preserve quoting, newlines, exit status, cwd, and container path translation;
- generated scripts remain inside `.aether2` under the task workspace;
- boundary failures give actionable reason codes without leaking host paths;
- local and Docker backends behave consistently;
- exact ten model-visible tools remain unchanged.

### H8. Structured Truncation Digest

Primary ownership:

- `runner/aether2/envelope.py`
- integration in `loop.py`/receipts.

When output is truncated, preserve bounded head/tail plus a structured digest:

- failed test names;
- assertion/error summary lines;
- traceback frames and exception line;
- compiler/linker fatal lines;
- missing file/import/undefined-symbol lines;
- timeout/kill indicators;
- raw-log path.

Requirements:

- digest is deterministic and bounded;
- source ordering is preserved;
- ANSI/CR normalization still works;
- no task-specific patterns;
- raw logs remain the source of truth.

### H9. Harness Behavior Eval Core

No production mechanism is complete without a deterministic eval.

Required evals:

1. exact model-visible messages and ledger are present in receipts;
2. contract appears in immutable prefix and dynamic bottom block;
3. ledger updates after tool evidence and retains failed checks;
4. ledger survives compaction;
5. weak evidence cannot make an unresolved requirement proven;
6. `unsatisfied` blocks clean completion;
7. `unverifiable` blocks clean completion;
8. three repair rounds remain the hard maximum;
9. semantic repeated-strategy loop triggers one factual reflection;
10. legitimate polling does not false-trigger;
11. multiline foreground command preserves content and exit status;
12. multiline detached job preserves content and exit status;
13. truncated middle traceback appears in the digest;
14. grader reward remains separate from advisory verifier status;
15. genericity checker remains green.
16. unresolved blockers persist across turns, rebases, and compaction;
17. blocker age and status transitions are deterministic;
18. repeated `task_done` without relevant evidence is pre-rejected without a
    new verifier model call;
19. unrelated deltas cannot make a blocker `candidate_resolved`;
20. blocker-relevant evidence permits one new verifier evaluation;
21. exhausted blockers terminate honestly after the bounded repair allowance.

Build original, non-benchmark homolog fixtures. Do not encode names or solutions
from the frozen task corpus.

## 8A. Environment Contract And Real Service Monitoring

These cross-team requirements preserve the existing orientation, executor,
bridge, job/session, and grader-isolation concepts. They must not be reduced to
a path map or a single port check.

### Environment contract

Maintain a structured, evidence-backed `EnvContract` or equivalent substrate
contract covering:

- canonical host and task-container workspace roots;
- task, artifact, model-visible test, and grader-only test paths;
- cwd and path-translation rules;
- shell executable and command semantics;
- Python executable/version and invocation contract;
- package managers and installation scope;
- effective user, group, permissions, and writable roots;
- network availability and constraints;
- process/session/job persistence model;
- service bind addresses and allocated ports;
- container/runtime identity and lifecycle ownership;
- grader isolation, toolchain, environment, and hidden-test boundary.

Rules:

- facts come from probes or explicit runner configuration, never guesses;
- unknown or unavailable facts are represented honestly;
- the model receives only task-visible substrate facts;
- grader-only paths, hidden tests, credentials, and control-plane details remain
  model-invisible;
- receipts and result rows record the environment-contract version/digest;
- drift between orientation, execution, verification, and grading is surfaced
  and classified;
- substrate invalidity stays separate from model capability.

### Bounded service monitoring

For declared services or persistent jobs, monitor real behavior over a bounded,
configurable observation window:

- process/job survival at the beginning and end;
- unexpected PID or process replacement;
- log growth and newly observed error lines;
- client probes from the correct environment;
- response content or state-transition validation tied to the stated claim;
- bind address and port ownership;
- crash, restart, timeout, and premature-exit classification;
- relevant file, socket, and session changes.

`process exists`, `port open`, and one startup probe remain weak evidence for a
persistence claim. Monitoring must not poll indefinitely, add a model-visible
tool, or use task names. Cleanup occurs only after required post-exit evidence
and only for attributable resources.

### Ownership

Team H owns the harness-side environment-contract data structures, task-safe
model-visible facts, service/job/session delta state, bounded monitoring
semantics, receipts, and behavior tests.

Team R owns official runner/container/test/grader manifests, resource and port
allocation, contamination checks, phase-row environment digests, drift
classification, external grader isolation, and post-run service evidence.

Both teams must use a compatible serialized contract and document the interface
in their handoffs. Neither team may silently create a competing schema.

## 9. Integration Protocol

### Patch order

1. R0 and H0 characterization.
2. R1-R4 and H1-H4 may proceed in parallel within their ownership boundaries.
3. H5 depends on H3-H4.
4. H6 depends on H3.
5. H7-H8 may proceed in parallel with H3-H6.
6. Team H lead integrates all harness work through `loop.py`.
7. H9 runs before any target task.
8. Team R produces the board manifest only after H9 and local regressions pass.

### A/B interaction matrix

At minimum test:

- ledger only;
- evidence-strength reflection only;
- ledger + evidence strength;
- verifier semantics only;
- ledger + verifier semantics;
- semantic no-progress only;
- all model-facing mechanisms together;
- tool-channel cleanup alone and with all model-facing mechanisms.
- environment-contract preservation and drift classification;
- service startup-only evidence versus bounded survival/client/state evidence;
- service crash, replacement, and timeout classification without false
  capability attribution.

Compare:

- target eval score;
- regression sentinels;
- invalid and contamination rate;
- steps/model calls/tokens;
- false reflection rate;
- unresolved-gap truthfulness.

### Local regression gates

Required:

```bash
python3 -m pytest tests/test_aether2_*.py -q -p no:cacheprovider
python3 -m py_compile runner/aether2/*.py tools/run_aether2_g2.py
python3 tools/aether2_genericity_check.py
```

Run affected runner/tool/script tests separately.

Three consecutive full local Aether-2 suites are required after final integration
because detached process behavior has previously been flaky.

## 10. Targeted Board

Run only after all behavior evals and integration gates pass.

Maximum: ten tasks.

Proposed board, subject to availability and a written preregistration:

Sentinels:

- `acl-permissions-inheritance`
- `analyze-access-logs`
- `assign-seats`

Failure-pressure rows:

- `break-filter-js-from-html` -- weak/self-confirming evidence
- `amuse-install` -- environment-hacked import evidence
- `build-stp` -- help/presence versus runtime usability
- `audio-synth-stft-peaks` -- shape versus numeric correctness
- `broken-python` -- semantic repeated repair loop
- `adaptive-rejection-sampler` -- repeated strategy/no-progress
- `ancient-puzzle` -- multiline/tool-channel friction

The board is not a benchmark score. It is a mechanism-validation board.

Before execution, record:

- baseline row and trace for every selected task;
- predicted outcome movement;
- mechanism(s) expected to affect it;
- resource class;
- regression and contamination sentinels;
- stop conditions.

No full corpus rerun follows automatically. The principal reviews the targeted
board first.

## 11. Subagent Rules For Both Teams

Subagents are authorized, but:

- each receives one compact, spec-complete task;
- each has an explicit file ownership set;
- no two active workers edit the same file;
- workers read `AGENTS.md` and this plan;
- workers receive entry criteria, exit criteria, tests, evidence paths, and
  stop conditions;
- workers must not thin the task into a prototype;
- workers hand back patches and evidence to their thread lead;
- thread leads inspect and integrate every patch;
- only thread leads update shared handoffs.

The Team H lead alone owns `runner/aether2/loop.py`.

## 12. Review And Closeout

Each thread must use `/Users/mohamud/.codex/skills/codex-review/SKILL.md` if
available.

If the skill or nested CLI is genuinely unavailable:

- record exact failure evidence;
- perform a source-level self-review against this plan and `AGENTS.md`;
- run an adversarial review attempting to disprove completion;
- enumerate accepted and rejected findings;
- rerun affected tests after fixes;
- do not call a failed review command clean.

Each team writes:

- `runner_team_handoff.md` or `harness_team_handoff.md`;
- file list;
- requirement-by-requirement disposition;
- tests and exact results;
- review findings and dispositions;
- residual risks;
- integration instructions;
- RAW_LEDGER_UPDATE persisted through the repository recorder.

Neither team may start the targeted VM board independently. They hand back to
the parent orchestrator for integration approval.

## 13. Goal Exit Criteria

The implementation Goal is ready for targeted validation only when:

- runner validity and truthful row tests pass;
- model-input receipts are complete;
- contract rebinding is visible and cache-safe;
- durable ledger updates and survives compaction;
- evidence-strength reflections are generic;
- unresolved verifier gaps cannot appear clean;
- semantic no-progress evals pass without polling false positives;
- multiline foreground and detached execution are literal and stable;
- structured truncation digest passes;
- verifier blockers persist and suppress redundant verifier calls;
- blocker transitions occur only on relevant evidence or verifier confirmation;
- one compatible environment contract is captured across runner and harness;
- service claims receive bounded behavioral monitoring rather than only
  process/port checks;
- all harness behavior evals pass;
- three consecutive full Aether-2 suites pass;
- compile and genericity pass;
- both team reviews are closed or honestly self-reviewed;
- no credential home, process, container, or VM is unintentionally left running.

Final status before the board:

`READY_FOR_TARGETED_G5_BOARD`

Anything less must close as:

`PARTIAL_COMPLETE_<specific blocker>`
