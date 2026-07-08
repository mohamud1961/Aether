# Canonical Aether Consolidation Plan

Status: execution in progress on canonical Aether-Next; diagnostic alignment
board produced, fresh model-backed promotion rows still pending.

Date: 2026-07-03

Update, 2026-07-03: Opus reviewed the governance fix and confirmed the drift
stopper is real. This plan now clarifies that "migration" means direct same-repo
implementation on the canonical Aether-Next files, not a separate repo transfer
or folder copy.

Execution update, 2026-07-03:

- Safety snapshot created at
  `tracking/snapshots/20260703T032335Z_canonical_aether_safety/`.
- Canonical `aether` import shim added over `aether_next_build/aether_next/`;
  physical rename remains deferred because `.git/index.lock` cannot be created
  from the current sandbox.
- Direct Aether-Next vision deltas landed: workbench architect failure is now
  `config_invalid` initialization failure; unsupported top-level config fields
  fail clearly; no-progress controls reach solver context as action constraints;
  runner trace rows preserve `trace_path` and real trace-write error details.
- Historical replay tooling now strips recorder-owned config metadata before
  parsing saved architect configs, preserving strict live validation while
  keeping old evidence readable.
- Diagnostic alignment board produced at
  `aether_next_build/alignment_boards/20260703_canonical_aether_alignment_board.json`
  and `.md` from existing real rows: 7 rows, 1 verifier false clean, 5 aligned
  fail/block rows, 1 invalid grader-unavailable row.
- Validation: Aether-Next full suite passed (`250 passed, 8 skipped`), root
  canonical import test passed, and `tools/aether2_genericity_check.py` passed.
- Fresh deterministic integration sentinel passed at
  `aether_next_build/deterministic_integration_eval_20260703_034019/`.
- Fresh benchmark-native/model-backed promotion rows are environment-blocked in
  this sandbox: Docker daemon is not reachable and no usable model API key is
  present. The current board is therefore diagnostic, not promotional.

## Decision

Aether-Next is the canonical agent/harness line.

- Canonical implementation today: `aether_next_build/aether_next/`.
- Intended consolidated package name: `aether/`.
- Aether-2 status: reference and compatibility source, not production target.
- Runner/eval substrate status: keep and integrate; do not confuse substrate
  ownership with agent ownership.

This reverses the stale governance sentence that pointed new work at
`harness/aether2/`. The Aether-2 carve-down slices remain useful, tested
reference work, but further production work should land on the Aether-Next line
unless a future evidence-backed decision says otherwise.

## Plain-Language Plan

1. Save the current state before moving anything.
2. Clean up the canonical name/path so agents work against `aether/`, not a
   temporary-looking `aether_next_build/aether_next/` path.
3. Build the vision directly into Aether-Next's files, using the Aether-2 slices
   as reference implementations where useful.
4. Prove the result on real Terminal-Bench-style rows with verifier/grader
   alignment, not local-only green checks.
5. Run the loop: eval, diagnose gaps, make one generic fix, rerun target rows
   plus sentinels, keep/kill/iterate.
6. Call it production-ready only after repeated real rows show the verifier,
   harness result row, and official grader are aligned with acceptable invalid
   rates and no task-specific leakage.

## Same-Repo Implementation, Not A Separate Migration

Both lines already live in this checkout:

- canonical line: `aether_next_build/aether_next/`;
- reference line: `harness/aether2/`;
- eval/runner substrate: `runner/` and `eval_suite/`.

So the work is not a cross-repo migration. It is a direct implementation/port
inside the same repository:

- identify the Aether-Next file that owns each behavior;
- compare it to the proven Aether-2 slice behavior;
- apply the same generic ownership rule in the Aether-Next structure;
- test that behavior in Aether-Next;
- delete or quarantine only duplicate judgement paths proven replaced.

Do not copy Aether-2 files wholesale into Aether-Next. The code shapes differ.
Port the behavior, not the file.

## Goal Definition

Objective: consolidate the project around one canonical Aether line, preserve
the useful Aether-2 ownership-boundary lessons, and prove the result with real
eval evidence instead of trace prose.

Scope:

- rename or expose Aether-Next as the clean canonical `aether/` package;
- update governance and docs so agents no longer continue Aether-2 by default;
- port only generic, evidence-backed Aether-2 carve-down improvements;
- wire canonical Aether to the eval substrate needed for result rows and
  verifier/grader alignment measurement;
- build the first real alignment board before promotion.

Out of scope:

- deleting Aether-2 before its useful patterns and integration surfaces are
  inventoried;
- task-specific grader mimicry;
- new solver helpers without eval-backed failure pressure;
- promotion claims from local-only sentinels or replay-only wins.

Entry criteria:

- production-target decision recorded: Aether-Next canonical, Aether-2 reference;
- current Aether-2 closeout evidence preserved;
- current Aether-Next evidence and tests identified;
- no unreviewed broad rewrite started.
- current dirty tree is snapshotted, committed in coherent slices, or explicitly
  waived before any mechanical rename/move.

Exit criteria:

- canonical package and import plan completed;
- governance and docs point at the canonical path;
- Aether-2 reference status is explicit;
- required generic ports are implemented or consciously deferred;
- eval substrate can produce result rows for canonical Aether;
- verifier/grader alignment confusion matrix exists for real task rows;
- promotion decision is based on scored evidence, not implementation claims.

Evidence outputs:

- migration map;
- import/entry-point inventory;
- slice docs with Adds/Changes/Deletes/Deferred/Tests/Risk/Rollback;
- result rows and scoreboards;
- verifier/grader confusion matrix;
- raw ledger handoffs under `tracking/ledger/inbox/`.

Stop conditions:

- canonical target becomes ambiguous again;
- a broad commit or mechanical rename would sweep unrelated dirty work into the
  same change;
- rename breaks evidence or import paths without a clean rollback;
- eval rows cannot distinguish verifier, grader, launch, provider, and
  environment outcomes;
- proposed verifier change requires task-specific grader knowledge;
- substrate integration work exceeds the approved slice boundary.

Review gate: `codex_review_skill_plus_adversarial` for code-bearing migration
slices; `adversarial_only` is enough for this planning/governance slice.

## Ownership Model

Architect owns:

- solver prompt;
- verifier prompt;
- context policy;
- compression policy;
- success definition;
- verifier capability request within harness-owned safety bounds.

Solver owns:

- task execution;
- evidence acquisition;
- final artifact production;
- honest uncertainty and blockers.

Verifier owns:

- task-state judgement from task-visible evidence;
- read-only inspection loop;
- verdict and unresolved risks.

Harness owns:

- executor;
- sandbox/workspace;
- tool routing;
- model routing;
- trace and receipt writing;
- artifact capture;
- runtime invariants;
- result-row assembly.

Official grader owns:

- benchmark measurement after agent termination only.

Ledger owns:

- durable memory of evidence, decisions, failures, and open questions.

No behavior should have shared ownership. Shared ownership caused the prior
failures: static prompt versus architect prompt, proof contract versus verifier,
completion gate versus verifier, and solver proof object versus result row.

## Verifier/Grader Alignment Artifact

The alignment proof is a result-row confusion matrix over real task attempts.

| Verifier | Official grader | Meaning | Action |
| --- | --- | --- | --- |
| clean | pass | true clean | preserve |
| clean | fail | false clean | highest-risk verifier failure |
| not clean | pass | false block / too strict | improve verifier evidence classifier |
| not clean | fail | true block | preserve or improve diagnosis |

Rules:

- The verifier never sees the official grader during the agent run.
- The official grader never participates in the agent loop.
- Post-run grader disagreement is diagnostic evidence for the next iteration.
- Fixes must improve general verifier capability from task-visible evidence.
- Do not encode task-specific grader checks, task names, expected answers, fixed
  ports, or hidden-test assumptions into the verifier or harness.

Minimum first board:

- at least the recent real Terminal-Bench pressure rows already used for
  Aether-Next validation;
- one filesystem/open-workflow row;
- one runtime/tool-contract row;
- one structured retrieval/reduction row;
- one BFCL/tool-calling sentinel when the substrate is ready;
- contamination and invalid-row labels in every row.

Known Stage-1 Aether-Next evidence gaps to close before expansion:

- trace writing regressed in the canonical Stage-1 run;
- verifier evidence directories must be task-namespaced so rows cannot overwrite
  one another;
- verifier prompt persistence must be consistent across verifier paths;
- architect contracts must populate for every task rather than passing
  vacuously with empty proof/evidence fields;
- no-progress signals must become enforceable recovery constraints, not merely
  advisory text the solver can ignore.

These are not promotion blockers because promotion has not happened yet. They
are the first reliability repairs before a broader eval loop.

## Direct Implementation Map

Use this as the first pass for Slice 1 and Slice 3 inventory. Confirm each item
against live code before editing.

| Vision behavior | Likely Aether-Next owner | Current evidence | Build action |
| --- | --- | --- | --- |
| Architect owns solver/verifier prompts | `workbench_hooks.py`, `workbench_config.py`, `workbench_compile.py`, `compiler.py`, `model_hooks.py` | WorkbenchArchitect and HarnessConfigIR exist; compiler records prompt hashes and inserts solver/verifier identity sections | Verify no competing hidden default prompt can override architect prompt; harden missing/empty prompt handling |
| Architect failure is initialization failure, not silent baseline | `kernel_config.py`, `workbench_hooks.py`, `workbench_config.py` | `_workbench_resolve` still falls back to baseline when config is `None`, with fallback codes | Decide whether certified runs should hard-fail instead of fallback; record as agent initialization failure when workbench cannot be built |
| Solver sees recent tool outputs and active findings | `context_compiler.py`, `ledger.py`, `compiler.py`, `kernel_messages.py` | Context compiler includes recent progress, active findings, automatic memory findings, and compression policy | Add tests proving recent command/check outputs and active verifier findings survive compaction and reach solver messages |
| Verifier is bounded and read-only | `kernel_verifier.py`, `verifier_packets.py`, `model_hooks.py`, `verifier.py` | Model verifier exists and is packet-bound; prompt says grader is external | Verify bounded loop/tool capabilities; prevent verifier from requesting repeated display when proof/no-progress says execute/repair |
| Fake/dead config surfaces are rejected or audited | `workbench_config.py`, `workbench_compile.py`, `compiler.py` | `config_realization_audit` exists; some policy surfaces still parse into advisory/default behavior | Reject unsupported fields clearly or mark realized/not-realized in audit; avoid fake configurability |
| Deterministic checks are evidence, not authority above verifier | `kernel.py`, `completion.py`, `proof_contract.py`, `kernel_checks.py`, `kernel_verifier.py` | Kernel calls verifier on deterministic success/failure paths; proof/visible checks still influence completion | Ensure checks feed verifier/result-row evidence and cannot create task-specific veto authority above verifier |
| Compaction uses real context window | `runtime_ir.py`, `context_compiler.py`, `workbench_compile.py` | `model_context_window_tokens` exists and compression uses policy ratio | Tie window to model route/config rather than a stale hardcoded default; test exact-preserve sections |
| Grader separation and alignment matrix | `classifier.py`, `runners/docker_runner.py`, future eval substrate adapter | `reconcile_grader_alignment` already records grader-vs-kernel status post-run | Promote this into a board-level confusion matrix with invalid-row labels |

## Build Slices

Every slice must say what it deletes, not only what it adds.

### Slice 0: Decision Lock And Evidence Freeze

Adds:

- canonical target decision record;
- current evidence inventory for Aether-Next and Aether-2;
- stale-doc inventory.

Changes:

- governance points at Aether-Next as canonical.

Deletes:

- no code deletion.

Deferred:

- package rename;
- import rewiring.

Tests:

- docs lint/readback;
- `git diff --check`.

Risk:

- agents may still follow older planning docs.

Rollback:

- revert governance docs only if a new scored-evidence decision reverses the
  canonical target.

Status:

- Complete for governance and planning. The remaining pre-rename task is a
  safety snapshot/commit of the current dirty tree, scoped by the human or a
  dedicated git goal.

### Slice 0.5: Safety Snapshot

Adds:

- recoverable checkpoint before any mechanical rename or import churn.

Changes:

- no behavior change.

Deletes:

- nothing.

Deferred:

- rename and runtime implementation.

Tests:

- `git status --short`;
- optional docs-only `git diff --check` for currently touched planning files.

Risk:

- committing unrelated dirty work into one giant opaque snapshot.

Rollback:

- if committing is too broad, create a branch/tag or explicit patch bundle
  instead, then continue with scoped commits.

### Slice 1: Package Name And Import Map

Adds:

- `aether/` package plan or compatibility shim plan;
- entry-point inventory for Aether-Next runners and tests;
- import migration map.

Changes:

- choose whether to move files immediately or add a thin canonical package first;
- keep this mechanical: no behavior changes in the rename/import slice.

Deletes:

- no production code deletion.

Deferred:

- Aether-2 relocation.

Tests:

- Aether-Next existing tests before and after import-map changes;
- import smoke for canonical package.
- no runtime behavior diff unless the slice explicitly records it.

Risk:

- large rename hides behavioral changes.

Rollback:

- keep a mechanical rename commit separate from behavior commits.

Status:

- Implemented as a source-tree shim first: top-level `aether/` exposes
  `aether_next_build/aether_next/` under the canonical import path without
  moving files or changing behavior.
- Physical file move remains deferred until the checkout can create normal git
  commits; this sandbox cannot write `.git/index.lock`.
- Validation: `python3 -m pytest -q tests/test_aether_canonical_import.py`
  passed, and direct `import aether; from aether.compiler import ConfigCompiler`
  resolved to the Aether-Next source tree.

### Slice 2: Governance And Documentation Sweep

Adds:

- canonical path note in contributor docs;
- deprecation/reference note for Aether-2 docs.

Changes:

- replace active-harness language that points to Aether-2.

Deletes:

- stale active-target claims.

Deferred:

- old run archives and historical docs remain unchanged unless they mislead
  future work.

Tests:

- targeted `rg` for active-target claims;
- docs-only diff review.

Risk:

- over-editing historical evidence.

Rollback:

- restore individual historical references; keep the active-governance decision.

### Slice 3: Port Generic Aether-2 Ownership Fixes

Adds:

- canonical equivalents for the proven generic Aether-2 fixes that are missing
  in Aether-Next.

Changes:

- architect config/init failure is real, not silently absorbed;
- recent tool outputs remain model-visible;
- verifier loop is bounded and read-only;
- unsupported architect config surfaces fail clearly;
- solver proof/self-report cannot override verifier/grader/result-row authority.
- no-progress evidence becomes an enforceable recovery constraint when repeated
  display/read loops are detected.

Deletes:

- any duplicate judgement path proven active and replaced in canonical Aether.

Deferred:

- Aether-2-specific Harbor details unless needed for substrate integration.

Tests:

- focused unit tests for each port;
- genericity checks;
- known-bad cases for fake config, proof override, missing tool-output context,
  and verifier false authority.
- replay or model-free scenario proving no-progress can force repair/execute/new
  target/blocker instead of another same-evidence display action.

Risk:

- porting by analogy without matching Aether-Next structure.
- turning verifier caution into lower solve rate without grader gains.

Rollback:

- one fix per commit; revert individual ports by behavior.

### Slice 4: Eval Substrate Integration

Adds:

- canonical Aether adapter to result-row substrate if missing;
- row fields that separate launch/provider/environment/grader/verifier/model
  capability outcomes.
- task-namespaced trace and verifier-evidence artifact layout.

Changes:

- Aether-Next standalone Terminal-Bench runs become reproducible board rows.
- Stage-1 evidence-hygiene bugs are fixed before broader expansion.

Deletes:

- no task-specific wrappers.

Deferred:

- broad public benchmark sweeps.

Tests:

- no-model/unit contract rows;
- one debug model row if credentials/backend are available;
- known-bad row must fail.
- trace file exists per row;
- verifier evidence bundle exists per row without cross-task overwrites;
- verifier prompt is persisted for every verifier path.

Risk:

- confusing standalone task success with scoreboard-ready evidence.

Rollback:

- keep standalone runner until board rows reproduce it.

### Slice 5: Verifier/Grader Alignment Board

Adds:

- confusion-matrix report;
- per-row verifier verdict, grader result, invalid classification, and trace path.

Changes:

- verifier improvement decisions use disagreement data.

Deletes:

- no verifier mechanisms in this slice unless already approved.

Deferred:

- optimization mechanisms.

Tests:

- run the first real rows in benchmark-native/container conditions where
  possible;
- validate known-bad and ceiling rows where feasible.

Risk:

- too-small board gives false confidence.

Rollback:

- mark board diagnostic only; do not promote.

### Slice 6: Aether-2 Reference Retirement

Adds:

- archive/reference label or location for Aether-2;
- compatibility policy for any remaining imports.

Changes:

- active docs and commands stop routing new work to Aether-2.

Deletes:

- dead duplicate judgement code only after import inventory and tests prove it is
  unused.

Deferred:

- historical run archives.

Tests:

- full relevant test set;
- import inventory;
- docs active-target scan.

Risk:

- deleting substrate integrations still needed by eval workflows.

Rollback:

- keep Aether-2 code until canonical eval path has equivalent coverage.

### Slice 7: Promotion Gate

Adds:

- final evidence bundle;
- keep/kill/iterate decision.

Changes:

- project scoreboard recognizes canonical Aether result rows as the active
  evidence surface.

Deletes:

- stale promotion claims not backed by scored evidence.

Deferred:

- future optimization variants.

Tests:

- target rows plus regression sentinels;
- verifier/grader alignment report;
- review gate closeout.

Risk:

- declaring success from local evidence.

Rollback:

- demote to diagnostic if official/container evidence is incomplete.

## Port Candidates From Aether-2

Port if missing in Aether-Next:

- architect prompt ownership and static-prompt retirement;
- architect initialization failure classification;
- recent tool-output/context invariant;
- bounded read-only verifier loop;
- config realization audit and strict unsupported-field rejection;
- duplicate judgement path quarantine;
- result-row/grader separation;
- solver proof object isolated as self-report only.

Do not port:

- Aether-2-specific adaptive-profile machinery unless it survives eval pressure;
- Harbor-only assumptions unless used as substrate;
- proof-contract or completion-gate authority;
- any task-family-specific solve logic.

## Immediate Next Action

Slice 0 governance is done. The next executable sequence is:

1. Safety snapshot: preserve the current dirty tree without mixing behavior
   changes into a rename.
2. Slice 1: build the package/import map for exposing
   `aether_next_build/aether_next/` as canonical `aether/`.
3. Slice 2: finish active-doc cleanup after the import map.
4. Slice 3: implement the known vision deltas directly in Aether-Next files,
   one behavior at a time.
5. Slice 4: wire canonical Aether into result rows with clean artifacts.
6. Slice 5: run the verifier/grader alignment board.
7. Iterate with eval-backed generic fixes until the production gate is met.

The next code-bearing goal should not begin with broad runtime changes. It
should begin with the safety snapshot and Slice 1 import map.
