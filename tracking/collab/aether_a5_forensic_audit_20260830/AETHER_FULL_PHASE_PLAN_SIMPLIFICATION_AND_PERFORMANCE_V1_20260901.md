# Aether full phase plan: simplification, canonical runner, cognition/performance, and final evaluation

Date: 2026-09-01
Owner: Main / ChatGPT
Status: implementation plan only. No paid benchmark launch is authorised by this document.

## 0. Mission and end state

Build the smallest truthful Aether that gives Luna the best validated chance of solving hard benchmark tasks without the harness becoming the semantic planner.

Frozen doctrine:

> Luna decides. Aether executes and preserves reality. The Verifier independently falsifies. Harbor owns benchmark lifecycle/grading. The ledger preserves history.

Final runtime flow:

`task -> one Aether launcher -> Harbor -> tiny packaged Aether Harbor adapter -> Aether runtime -> Luna <-> truthful world/execution -> independent Verifier -> Harbor official grader`

Board controllers are outside Aether. Research/replay/history are outside production. No Architect, no production sub-agents, no skill packs, no task-specific benchmark logic, no hidden-grader access, no harness-authored semantic replanning.

### Non-negotiable invariants

1. Raw user task is the sole semantic authority.
2. One Solver decision -> at most one external action -> one authoritative observation -> next Solver decision.
3. Aether may preserve facts, state, provenance, freshness, budgets, failures, lifecycle and evidence. It may not choose semantic strategy.
4. Solver submit means: candidate believed complete and ready for independent verification. Submit is not success.
5. Terminal success requires an independent Verifier completed verdict plus all deterministic completion gates.
6. Failed/falsifying evidence is durable until a kernel-observed supersession proves relevant changed state.
7. Official grader remains outside Solver/Verifier context.
8. No benchmark/task-specific branches in Aether, runner or task launcher.
9. Correctness dominates token, latency and cost improvements.
10. Losing experiments do not stay in production.
11. A new mechanism must solve a demonstrated failure or replace more complexity than it adds.
12. H10 remains untouched until the user explicitly decides what happens after the agreed final audit.

## 1. Current authority and checkpoint

Behavioural source authority is the PCR/A5 lineage at `5c1a54f68c88e5c9fe6ec08bdee6cc865947586c` plus the independently audited local correctness patch in workspace `d17cee6f49`.

Do not merge the divergent Workbench-only `fix/postrun-p0-harness-fixes` branch as architecture authority. Do not merge B5 board/scheduler machinery wholesale. The exact Codex `bench_launch.py` implementation on PCR lineage (`084f4a85c...`) is a source of tested custody invariants, not the final launcher.

Pre-simplification qualification already obtained before the lazy-import carve-down:

- full deterministic Aether suite: 3,487 passed, 17 skipped, 0 failed;
- Codex generic launcher independently re-run from PCR branch blobs: 29/29 passed;
- first S1 import carve-down: production Harbor import closure reduced from 115 to 105 Aether modules and Architect/Workbench imports reduced from 7 to zero;
- 88 targeted production + legacy Architect/Workbench tests passed after that lazy-import change.

Before further source mutation, separate the current work into explicit commits so causal boundaries stay auditable.

## 2. Phase map

| Phase | Purpose | Provider calls? | Benchmark rows? | Main output |
|---|---|---:|---:|---|
| S0 | Freeze authority and finish known correctness closure | provider canaries only when authorised | 0 | clean qualified behavioural baseline |
| S1 | Remove alternate cognition architectures | no | 0 | PCR-only production graph |
| S2 | Collapse runtime/state/control types | no | 0 | one mechanical runtime, one factual context path |
| S3 | Make Harbor the one runner | no | provider-free Harbor smoke only | one packaged Harbor agent entrypoint |
| S4 | Build one minimal task launcher | provider canary only when authorised | 0 | one strict `aether run` boundary |
| S5 | Physically clean/package repository + S5b remediation | no | 0 | one production package, history outside production, deterministic seal candidate |
| S5c | Clean live baseline qualification | exactly one authorised live Luna run per source candidate; failed candidates are frozen and replaced | 1 sacrificial non-A5/B5/C5/H10 task per source candidate | packaged pre-S6 baseline proven end-to-end and microscopically audited |
| S5d | Capability completeness gate | no by default; provider canary only if a native modality boundary cannot otherwise be proven | 0 benchmark rows | exact clean wheel proves its existing senses/actuators; gaps classified without automatic implementation |
| S6 | Controlled cognition/performance optimisation | yes, staged and capped | calibration tasks only | globally frozen best treatment |
| E2 | A5+B5+fresh C5 under frozen candidate | yes | 15 | transfer evidence |
| A2 | microscopic forensic/system audit | no | 0 | final generic improvement set |
| F | final improvements + final A5+B5+C5 | yes | 15 | final sealed candidate |
| STOP | final audit and freeze | no | 0 | no D5/H10 without user instruction |

A5 and B5 are now known diagnostic/regression sets. C5 is the next fresh forward-generalisation set. H10 remains untouched.

---

# S0 - Authority freeze and residual correctness closure

## S0 objective

Produce one clean commit/tree that contains every known generic correctness/reliability repair, no performance treatment, and no simplification whose behavioural effect is uncertain.

## S0.1 Split the current uncommitted work into causal commits

### Correctness commit

Expected touched source:

- `aether_next_build/aether_next/compiler_prefix.py`
- `aether_next_build/aether_next/harbor_runtime.py`
- `aether_next_build/aether_next/kernel.py`
- `aether_next_build/aether_next/pcr_context.py`
- `aether_next_build/aether_next/pcr_provider_protocol.py`
- `aether_next_build/aether_next/submission_coherence.py`
- `aether_next_build/aether_next/providers/azure_model.py` if currently modified by the audited patch
- `aether_next_build/scripts/run_workspace_harbor_v1.py`
- regenerated runtime manifests
- directly related tests only

Correctness already represented in this slice:

- background Responses for Solver and Verifier;
- independent Verifier may inspect a bound candidate when Solver evidence/current-state coherence is uncertain, without allowing terminal completion;
- submit semantics clarified as candidate-ready-for-verification;
- prescriptive next-turn fields removed from Thin Solver projection;
- Harbor monetary cost remains unknown when provider billing is unknown;
- exact configured Harbor `module:symbol` import preflight;
- no provider retry laundering for uncertain foreground outcomes.

### S1a import-isolation commit

Separate the already-started lazy import changes from correctness. Expected files include:

- `aether_next_build/aether_next/kernel_config.py`
- `aether_next_build/aether_next/kernel_messages.py`
- `aether_next_build/aether_next/run_adapter.py`
- any other file changed only to delay legacy Architect/Workbench imports.

Proof target: real Harbor/PCR import graph has zero Architect/Workbench modules while explicit legacy tests still work.

## S0.2 Close residual known correctness gaps before structural deletion

### C3 semantic-negative finding preservation, end-to-end

Known risk: a correct negative Verifier finding can be destroyed before it reaches the ledger if the Verifier overstates evidence class/protocol metadata.

Touch/audit:

- `aether_next_build/aether_next/verify_completion_protocol.py`
- `aether_next_build/aether_next/verify_completion_gates.py`
- `aether_next_build/aether_next/verifier.py`
- `aether_next_build/aether_next/finding_evidence.py`
- `aether_next_build/aether_next/ledger.py`
- `aether_next_build/aether_next/solver_facing_projection.py`

Add an end-to-end regression reproducing the B5 DNA shape: current inspection establishes the missing BsaI clamp; Verifier labels the evidence too strongly; protocol correction may reject the label but the factual negative finding must remain durable and Solver-visible. Completed/acceptance verdicts remain fail-closed.

### H2 truthful top-level latest-action state

Current PCR latest-result projection can say generic `observed` while nested task outcome failed.

Touch:

- `aether_next_build/aether_next/pcr_context.py`
- primary-action result index creation site in kernel/dispatch/ledger
- tests for success/failure/mixed/missing.

Required top-level states:

- `succeeded`
- `failed`
- `mixed`
- `missing`

No semantic interpretation, only mechanical aggregation of result receipts.

### Image/perception discoverability

The body already supports same-Primary native image perception behind artifact inspection. Make the factual consequence explicit without telling Luna when to use it.

Audit/touch:

- `aether_next_build/aether_next/pcr_provider_protocol.py`
- `aether_next_build/aether_next/compiler_prefix.py`
- `aether_next_build/aether_next/native_primary_perception.py`
- `aether_next_build/aether_next/harbor_executor.py`
- relevant perception tests.

Do not add a task-specific CAD hint.

## S0.3 Qualification

Required before S1b:

1. `python3 -m pytest -q aether_next_build/tests`
2. `git diff --check`
3. production import-closure probe: zero Architect/Workbench imports
4. deterministic PCR model-visible request/packet snapshots against the pre-S1 behavioural baseline for scenarios where no intended interface change occurred
5. targeted semantic-negative finding e2e regression
6. background provider request rendering tests
7. exact Harbor agent import-preflight tests
8. runtime manifests resealed

### Provider canary gate

Only after explicit spend/provider authorisation. Use no benchmark task.

Solver canary must prove:

- Responses background request accepted;
- response/job ID obtained;
- polling reaches terminal output;
- strict PCR turn parses;
- `previous_response_id` continuation works;
- requested/effective `reasoning.context` is recorded;
- no retry.

Verifier canary must prove:

- current `verifier_turn` schema is accepted;
- background route works at selected limits;
- one direct inspection/verdict envelope parses;
- no provider-schema `$ref` failure.

S0 exit artifact:

`tracking/releases/S0_CORRECTNESS_BASELINE_V1.json`

Bind commit, tree, runtime manifest, test census, import-closure hash, provider-canary evidence if authorised, and explicit `performance_treatments_applied=false`.

---

# S1 - Excise Architect/Workbench/alternate cognition from production

## S1 objective

Production supports exactly one cognition architecture: PCR Primary Solver + independent Verifier. Historical Architect code may exist only under an explicitly non-production research/archive namespace until deleted.

## S1.1 Remove production switches and call signatures

### `aether_next_build/aether_next/harbor_runtime.py`

Change:

- `build_selected_luna_models()` returns Solver + Verifier, not disabled Architect + Solver + Verifier;
- remove `_disabled_architect`;
- call `run_task` without `architect_model` or `architect_mode`;
- selected treatment manifest no longer contains Architect vocabulary.

### `aether_next_build/aether_next/run_adapter.py`

Remove from production API:

- `architect_model` argument;
- `architect_reviewer_model`;
- `architect_mode`;
- `architect_v3_for`;
- `workbench_architect_for`;
- `_StubArchitectV3Model` and Architect-only CLI behaviour;
- `architect_mode`, `architect_defect`, `architect_defect_reasons` fields in production record.

Final production signature conceptually becomes:

`run_task(task, solver_model, verifier_model, executor, envmap, runtime_identity, vision_model, budgets/profile)`

### `aether_next_build/aether_next/model_hooks.py`

Remove from production constructor/state:

- `_architect`;
- `architect()`;
- `call_architect_model()`;
- `call_workbench_architect_model()`;
- reviewer hooks/counters;
- fallback `verifier_model or architect_model` behaviour.

Verifier must be explicit when production completion requires it.

### `aether_next_build/aether_next/kernel.py`

Remove:

- `KernelHooks.architect`;
- `workbench_architect` constructor field;
- `architect_v3_architect` constructor field;
- `persistent_primary` mode switch once PCR becomes unconditional;
- alternate runtime-path count validation;
- Architect realization branches;
- Architect repair codes/receipts;
- Architect-defect accounting fields;
- verifier-triggered Architect reconfiguration path;
- `canonical_architect` compatibility branching.

Keep only PCR state transitions.

### `aether_next_build/aether_next/kernel_config.py`

Temporary target: only PCR mechanical resolution remains. S2 should delete this abstraction entirely if it becomes a one-function wrapper.

### `aether_next_build/aether_next/kernel_messages.py`

Remove `build_architect_request`; keep only Solver message construction until S6 replaces/reduces it.

### `aether_next_build/aether_next/kernel_reconfigure.py`

Remove from production. Reconfiguration through an Architect violates the selected architecture. If historically needed for replay, move it under legacy research.

## S1.2 Quarantine Architect/Workbench files after production imports are zero

Primary 23-file island:

- `architect_field_manifest.py`
- `architect_input.py`
- `architect_interface_analysis.py`
- `architect_interface_blind_review.py`
- `architect_interface_board.py`
- `architect_interface_run_control.py`
- `architect_interface_variants.py`
- `architect_output_schema.py`
- `architect_quality.py`
- `architect_review.py`
- `architect_v2_adapter.py`
- `architect_v2_canary.py`
- `architect_v2_contract.py`
- `architect_v2_model.py`
- `architect_v3_adapter.py`
- `architect_v3_canary.py`
- `architect_v3_contract.py`
- `architect_v3_model.py`
- `architect_v3_topology_ablation.py`
- `workbench_compile.py`
- `workbench_config.py`
- `workbench_hooks.py`
- `workbench_prompt.py`

Additional legacy candidates to classify after call-site audit:

- `repair.py`
- `smoke_compile.py`
- `runtime_manual.py`
- Architect-only portions of `model_prompts.py`
- `kernel_reconfigure.py`
- old Architect trace fields in `tracing.py`
- `aether_next_build/reference_legacy/`
- Architect-only eval scripts/directories.

Preferred temporary location when replay value remains:

`research/legacy/architect/`

Do not keep these importable under the production `aether` package.

## S1.3 Test migration rule

Do not delete a test simply because it is named Architect/Workbench.

For each test:

1. identify the invariant;
2. if invariant still matters to PCR, port it to PCR test;
3. if it proves only historical Architect behaviour, move it to `tests/legacy/architect/` or archive it with the frozen legacy code;
4. if it has neither production nor replay value, delete it after the inventory records why.

High-value invariants likely worth porting include:

- fail-closed invalid configuration;
- fixed tool-surface ownership;
- provider telemetry attribution;
- parse/output strictness;
- verifier-gated completion;
- task/raw-contract identity.

## S1 qualification

Hard gates:

- production Harbor import graph: zero `architect*` / `workbench*` modules;
- `git grep` of production package has no callable Architect provider path;
- no production constructor accepts `architect_mode`;
- no model provider telemetry role `architect*` can be emitted by production;
- PCR model-visible request/packet hashes unchanged except explicitly approved removal of non-model administrative fields;
- full deterministic suite green;
- legacy replay tests, if retained, run only through explicit legacy path.

---

# S2 - Collapse runtime/control/state to one mechanical PCR architecture

## S2 objective

Remove generic configuration machinery that exists only because Aether once supported several cognition architectures. The runtime should become a small fixed body whose variability comes only from observed capabilities/world state and an explicit model treatment profile.

## S2.1 Replace `RuntimeConfigIR` as a production authority

Current problem: `RuntimeConfigIR` and `CompiledRuntime` still carry Architect-era fields and generic workflow controls.

Primary file:

- `aether_next_build/aether_next/runtime_ir.py`

Production keep candidates:

- raw task binding;
- environment digest;
- observed capability descriptors;
- action schema;
- Solver identity/invariant prompt;
- Verifier identity/invariant prompt;
- task contract custody;
- mechanical completion policy;
- process/bootstrap/helper safety/lifecycle policies actually enforced by the body;
- proof/evidence identifiers actually used by PCR;
- Thin/PCR version marker until schema is renamed.

Remove after call-site proof:

- `architect_summary`;
- `architect_model_tier`;
- `architect_v2_contract_identity` / realization;
- `architect_v3_contract_identity` / realization;
- Architect visible contract fields;
- `reconfigure_policy` if no non-Architect owner remains;
- semantic/strategy fields generated only by old Architect paths;
- `WorkflowPolicy` if it is not an actual deterministic safety/lifecycle constraint;
- old `solver_v1`-only action metadata (`intent`, `expected_observation`, `if_fail_next`, `evidence_gap`) from production types once legacy parser is quarantined.

Target production names should describe reality, not historical architecture. Prefer `RuntimeProfile`/`RuntimeState` over `RuntimeConfigIR` once the migration is complete.

## S2.2 Replace generic config resolution with direct PCR runtime construction

Current files:

- `persistent_primary.py`
- `kernel_config.py`
- `compiler.py`
- `compiler_prefix.py`

Target:

- rename/recast `persistent_primary.py` into one mechanical PCR runtime builder, e.g. `pcr_runtime.py`;
- direct `build_pcr_runtime(envmap, task, profile)` call from `run_adapter`/kernel;
- delete `kernel_config.py` when it no longer chooses between modes;
- shrink `ConfigCompiler` to only genuinely mechanical compile/validation duties or remove it if the runtime can derive those facts directly;
- capability exposure is derived only from observed availability, never task semantics.

## S2.3 Stop compiling a large generic context and then filtering it

Current path:

`ContextCompiler -> generic linked_history/strategy-shaped packet -> compile_pcr_context -> strip/neutralize fields`

Target:

`ExecutionLedger + WorldState + capability state + findings -> factual PCR context directly`

Audit/touch:

- `context_compiler.py`
- `pcr_context.py`
- `context_views.py`
- `solver_facing_projection.py`
- `pcr_context_budget.py`
- `pcr_evidence.py`
- `finding_evidence.py`
- `pcr_working_state.py`
- `pcr_helper_tools.py`

Before replacement, capture golden PCR packets for deterministic scenarios:

- first turn/no action;
- successful read;
- failed action;
- mixed action outcome;
- state-changing action;
- unresolved Verifier finding;
- repaired/superseded finding;
- process/service running;
- process/service failed;
- output handle paging;
- submit coherence block;
- budget near exhaustion.

The direct PCR builder must preserve every factual field intentionally retained and must not reintroduce semantic guidance.

## S2.4 Remove disabled automatic-memory/strategy machinery from production

PCR Thin production currently disables or hides several generic mechanisms. Audit exact runtime reachability before removal:

- `automatic_memory.py`
- `memory_events.py`
- `memory_query.py`
- `no_progress.py`
- generic `query_memory` action path
- generic `record_observation` path
- generic `inspect_checks`/`run_check` paths when Thin has no authoritative EvalIndex checks.

Rule: keep hard lifecycle budgets and exact repeated-action facts if useful; remove harness-generated strategy/judgment such as “stuck” or “replan now”.

## S2.5 Converge state/evidence representations

Desired authorities:

1. `ExecutionLedger`: immutable event/receipt history and accounting.
2. `WorldState`: current observed external state snapshot/projection.
3. `InspectionRegistry`: independent Verifier inspection identities/results.
4. `TaskContract`: raw-task custody, not semantic planner output.

Audit duplication among:

- `world.py`
- `workspace_state.py`
- `harbor_workspace_state.py`
- `artifact_plane.py`
- `artifact_transform.py`
- `ledger.py`
- `inspection_registry.py`
- `proof_contract.py`
- `pcr_evidence.py`
- `finding_evidence.py`
- `submission_coherence.py`
- `verify_completion_gates.py`
- `verify_completion_protocol.py`
- `completion.py`

Do not collapse concepts merely because names overlap. Collapse only duplicate ownership of the same fact/decision.

## S2.6 Introduce one explicit immutable treatment profile

Replace ambient research env-switch sprawl with one explicit profile object passed at construction and sealed in run evidence.

Current sources:

- `postmerge_research.py`
- hard-coded fields in `harbor_runtime.py`
- research env parsing in `run_workspace_harbor_v1.py`

Target new minimal production module, e.g.:

`aether_next_build/aether_next/model_profile.py`

Fields should include only real model/runtime mechanics:

- model/deployment id;
- solver reasoning effort;
- verifier reasoning effort;
- reasoning mode;
- Solver continuity mode;
- reasoning context;
- context projection mode;
- tool surface id;
- response background mode;
- prompt cache mode;
- Solver/Verifier output caps;
- provider poll/call budgets;
- Solver turn budget;
- Verifier phase budget.

Production exposes one frozen `PRODUCTION_PROFILE`. S6 research creates alternate profiles outside production and injects them explicitly. No task can choose a profile.

## S2 qualification

- full deterministic suite green;
- production packet snapshots preserved where behaviour is intended unchanged;
- no Architect/Workbench terms in production runtime records/types;
- no runtime mode switch beyond PCR version/profile mechanics;
- no semantic task classifier chooses tools/context/effort;
- no duplicate state authority identified in source audit;
- production import count and LOC recorded, but line count is not a deletion target by itself.

---

# S3 - One runner: Harbor owns benchmark lifecycle

## S3 objective

There is exactly one production benchmark runner: Harbor. Aether contributes a tiny installed external-agent adapter and never reimplements benchmark staging/grading/container lifecycle.

## S3.1 Package the Harbor adapter with Aether

Current:

- `runner/adapters/harbor_agent.py`

Target:

- move into installed production package, e.g. `aether_next_build/aether_next/harbor_agent.py` during migration and ultimately `aether/harbor_agent.py`;
- production selector becomes `aether.harbor_agent:AetherHarborAgent`;
- remove repository `sys.path` injection;
- fail honestly if Harbor dependency/runtime is unavailable.

Adapter responsibility only:

1. receive Harbor environment/context/instruction;
2. discover workspace facts;
3. call Aether runtime;
4. write Aether evidence/ATIF under Harbor logs;
5. return control to Harbor.

No provider config policy, board scheduling, retries, grader execution or task selection in adapter.

## S3.2 Retire production use of other runner families

Move/quarantine/delete after invariant migration:

- root `runner/cli.py` / `python -m runner` deterministic stub path;
- `runner/model_client.py`, `runner/schemas.py`, Aether-2 compatibility aliases;
- `runner/substrate/` synthetic eval substrate;
- `runner/adapters/harbor_verifier_replay_agent.py` -> research/eval namespace;
- `aether_next_build/aether_next/runners/docker_*` -> diagnostic/eval namespace if still needed;
- `tools/run_tbench_model_backed.py` -> legacy diagnostic only;
- `tools/run_custom_eval_board.py` -> eval/research only;
- old tournament/direct-remote runner scripts.

## S3.3 Packaging boundary

Current `pyproject.toml` still describes `harness-aether2` and does not cleanly express the final Aether/adapter distribution.

Modify:

- `pyproject.toml`
- package include/discovery config
- optional Harbor dependency or deployment pin contract
- installed console entry point later used by S4.

A fresh environment must be able to install/import:

- Aether runtime;
- `aether.harbor_agent:AetherHarborAgent`;
- provider adapter;

without `PYTHONPATH=.` and without an untracked sibling file.

Harbor itself remains lifecycle authority. Pin its qualified version in an explicit runtime/deployment lock/manifest, not by hiding an ignored `.gateway_runtime` tree inside the source identity.

## S3 qualification

- build wheel/sdist;
- create fresh temporary venv;
- install package;
- import exact Harbor agent selector;
- provider-free Harbor install/smoke task through official Harbor lifecycle;
- remove package from checkout and prove installed package still resolves;
- known missing Harbor dependency fails before task/provider work;
- no root `runner` import is required by production.

---

# S4 - One minimal plug-and-play task launcher

## S4 objective

Replace `run_workspace_harbor_v1.py` + first-submit custody utility + generic `bench_launch.py` stacking with one small launch/admission authority that delegates execution/lifecycle to Harbor.

Target user experience:

`aether run /absolute/task/path --run-id <id> --evidence <dir> --allow-provider`

A manifest mode can power boards/automation, but the same code path executes both single tasks and board-launched tasks.

## S4.1 Keep/extract from Codex `bench_launch.py`

Port these proven invariants:

- exact source commit/tree identity;
- clean installed production artifact/source identity;
- task closure hash;
- symlink/path identity refusal;
- exact command/entrypoint binding;
- no shell dispatch;
- evidence root separation/collision refusal;
- fresh run-id namespace;
- minimal environment allowlist;
- terminal launch receipt;
- stdout/stderr custody for launcher/preflight itself;
- one attempt/zero retry policy;
- repeated identity check immediately before dispatch.

Do not port as permanent launcher responsibility:

- generic arbitrary verifier executable identity;
- generic arbitrary grader executable identity;
- generic arbitrary backend identity disconnected from actual Harbor path;
- arbitrary dynamic executable checks;
- process-tree supervision that Harbor/OS/container owns;
- B5 scheduler/trigger/wave semantics;
- provider policy that is not enforced at the credential-owning boundary.

## S4.2 Strict launch spec

Create a smaller exact schema, e.g. `aether.launch.v1`.

Required fields:

- schema version;
- run id;
- source/package commit/tree or immutable build identity;
- Aether runtime manifest/profile hash;
- task path + task closure hash;
- Harbor version/runtime identity;
- model deployment/id;
- evidence root;
- `provider_calls_allowed`;
- max attempts = 1;
- max retries = 0.

Derived, not operator-supplied:

- production agent selector;
- Verifier implementation identity;
- official grader identity/command (Harbor/task owns it);
- provider transport implementation;
- production tool schema.

Schema rule:

- `additionalProperties: false` for enforced sections;
- one explicit `metadata` or `extensions` map clearly marked non-enforced.

Unknown policy-looking fields must fail, never silently seal.

## S4.3 Credential/provider admission

The boundary that actually loads Luna credentials owns permission.

Modify/converge:

- current protected-env loading in `aether_next_build/scripts/run_workspace_harbor_v1.py`;
- `harbor_runtime.py` model construction;
- final launcher.

Rules:

- no credential loading during dry-run/preflight;
- provider call requires explicit launch authorisation plus manifest/profile match;
- credentials never enter receipts;
- no blind provider retries;
- provider auth/canary is a typed preflight, not arbitrary user executable.

## S4.4 Board controller separation

Create/retain one generic eval controller outside production, e.g.:

`evals/run_board.py`

It reads a board manifest and invokes the exact same one-task launcher N times. Concurrency/leases belong here or to the external execution controller, never to Aether/launcher internals.

Delete/move B5-specific scheduler/trigger logic from `run_workspace_harbor_v1.py` after its evidence is archived.

## S4.5 Port launcher adversarial tests

Use Codex `tests/test_bench_launch.py` as source material. Port relevant tests to the final launcher suite, e.g.:

`tests/test_launch_admission.py`

Preserve coverage for:

- source tamper;
- task tamper;
- manifest/receipt tamper;
- assume-unchanged/sparse/dirty identity where relevant to source mode;
- symlink path escape;
- run-id collision;
- evidence overlap;
- argv/entrypoint mismatch;
- no-shell execution;
- missing dependency/import;
- environment secret inheritance;
- provider explicit opt-in;
- terminal blocked receipt;
- stdout/stderr full custody.

Drop process-race adversarial machinery only when Harbor/container is the explicit process-custody owner and the launcher no longer claims process custody.

## S4 qualification

One command from fresh installed environment must:

1. validate source/runtime/task/profile;
2. prove exact Harbor agent import;
3. create one evidence namespace;
4. execute one provider-free Harbor smoke;
5. produce one terminal launch receipt + Harbor result + Aether run record;
6. require no manual `PYTHONPATH`, sibling worktree, hard-coded VM IP, task-specific wrapper or command editing.

---

# S5 - Physical repository cleanup and canonical package convergence

## S5 objective

Production source should look like the architecture we actually have, not the archaeological route by which we discovered it.

## S5.1 Separate production, eval/research and evidence

Final top-level shape target:

- `aether/` - production package only
- `tests/` - production-bound tests
- `evals/` - research/performance/board controllers
- `tracking/` - immutable evidence/manifests/audits, not importable production code
- `docs/` - current architecture + archived historical docs clearly labelled
- minimal `tools/` only for repository/release utilities

No generated run directory under production package roots.

## S5.2 Remove Aether-2 compatibility from production

Audit dependants, port any unique invariant, then remove from installed/source production surface:

- `harness/aether2/`
- `runner/aether2` aliases if present
- obsolete root runner compatibility.

Git history is the historical archive. Do not retain tens of thousands of LOC in production merely so old imports still happen to work.

If a pinned historical replay still requires Aether-2, preserve it as an immutable archive/reproduction bundle outside the production package.

## S5.3 Remove old launch families

Archive/delete after recording commit/hash/purpose:

- dated VM scripts with fixed IP/path/commit;
- `run_*` scripts superseded by `aether run` or generic `evals/run_board.py`;
- custom benchmark staging/grading runners;
- Architect-only launch/eval scripts;
- B5-specific trigger/scheduler scripts after evidence retention.

Do not keep 55 competing `run_*` commands in the default navigation surface.

## S5.4 Physical package rename/convergence

The current root `aether/` is only a shim into `aether_next_build/aether_next`.

After S1-S4 are stable:

- `git mv` the selected production implementation into real root `aether/`;
- remove the shim;
- update imports/tests/entrypoints;
- make `pyproject.toml` package the real root package;
- remove `aether_next_build` from production authority.

A temporary `aether_next` compatibility shim may exist only during the migration commit sequence and must be removed before S6 candidate freeze unless a proven external dependency requires it.

## S5.5 Documentation authority

Update at minimum:

- `README.md`
- `AGENTS.md`
- `CLAUDE.md`
- `docs/architecture/public-architecture.md`
- current architecture/target docs
- runner/launcher docs.

The only current architecture description should say:

- PCR Solver owns strategy;
- Aether is reality/execution/evidence layer;
- independent Verifier falsifies;
- Harbor runs/grades;
- one launcher;
- no Architect.

Historical docs must be clearly archived/datestamped, not silently contradictory.

## S5.6 CI/guardrails

Add one production-surface audit, e.g. `tools/check_production_surface.py`, asserting:

- zero production imports from `legacy`, `research`, `harness.aether2`, old `runner`, Architect/Workbench;
- one registered Harbor agent entrypoint;
- one console launcher;
- no hard-coded VM IP/source worktree in production;
- no untracked runtime import dependency in clean-install test;
- runtime manifest closure matches actual installed production closure;
- unknown launch-policy fields rejected;
- no board/task IDs in production package source.

## S5 exit gate

Re-run:

- full deterministic suite;
- fresh wheel/venv install;
- provider-free Harbor smoke;
- production import/reachability census;
- request/packet equivalence snapshot against S0 for any surface not deliberately changed;
- source/evidence retention audit.

Then freeze an **S5 seal candidate**, not the final pre-S6 baseline. No cognition/performance treatment may change after this point until S5c is complete.

---

# S5c - Clean live baseline qualification (mandatory pre-S6 gate)

## S5c mission

Prove that the completely cleaned and packaged S5 Aether actually functions as one end-to-end agent before any optimisation experiment changes cognition. This is not a performance board. It is a substrate qualification of the exact final S5 wheel.

The required topology is exactly:

`task -> aether run -> Harbor -> aether.harbor_agent:AetherHarborAgent -> one Aether runtime -> one Luna Solver -> real actions/observations -> submit -> one independent Luna Verifier -> repair/re-entry if required -> completion -> Harbor official grader`

Forbidden during S5c: Architect, Workbench, Aether2, alternate runner, source-checkout imports, synthetic executor, manual intervention, fallback text transport, worker/sub-agent cognition, benchmark-controller cognition, automatic benchmark retry, or any implementation/treatment change after the pre-run manifest is frozen.

## S5c task admission

Select exactly one sacrificial qualification task **before observing its run result**. It must:

- not be A5, B5, C5 or H10;
- not have been used to design S5b;
- have an actual Harbor task environment and official grader;
- exercise ordinary filesystem/command work;
- be medium/simple enough to have a reasonable probability of an official pass;
- be used only for this one baseline qualification run.

Record the task ID, source closure and task hash in the preregistration. Do not substitute a second task after seeing the outcome.

## S5c clean-package requirement

Create a brand-new environment on the qualification VM and install exactly:

- the final S5 candidate wheel by SHA-256;
- Harbor `0.20.0`.

Run the installed `aether` console from an unrelated directory such as `/tmp/aether-clean-baseline/`, with `PYTHONPATH` unset. Prove `aether.__file__`, `aether.harbor_agent.__file__`, and `aether.launch.__file__` resolve under that clean environment's `site-packages`, not the source checkout.

## S5c pre-run treatment freeze

Before the live provider call, write `PRE_S6_UNOPTIMISED_BASELINE_V1.json` binding at minimum:

- Git commit and tree;
- wheel filename/SHA and Aether version;
- Harbor version and canonical adapter;
- task closure/hash;
- model deployment;
- Solver and Verifier reasoning effort;
- fixed provider transport;
- continuity and reasoning context;
- context projection;
- Primary/Verifier prompt hashes;
- provider schema and tool-schema hashes;
- Solver and Verifier output ceilings;
- Solver turn ceiling and Verifier budgets;
- background Responses setting;
- provider/model retry policy (`0` for benchmark attempt);
- cache mode;
- all other positive treatment controls from the sealed production profile.

The live run must either prove every recorded treatment value reached execution or fail qualification.

## S5c microscopic audit

Audit the complete trajectory, not only reward. Prove:

- startup loaded one launcher, one Harbor lifecycle, one packaged Aether agent/runtime, one Solver identity and one independent Verifier identity;
- no alternate production architecture/module was loaded;
- every Solver cycle obeyed one decision -> at most one external action -> one authoritative observation -> next decision;
- filesystem, command, process, mutation and artifact receipts represented current reality truthfully;
- failed actions remained visible and stale state was not presented as fresh;
- submit occurred only through the intended submit boundary and submit was not treated as success;
- the independent Verifier actually ran when required;
- any Verifier finding re-entered as factual state, without a hidden strategy/repair instruction selecting the Solver's action;
- terminal completion required candidate submit + Verifier completion + mechanical completion custody;
- Harbor independently ran the official grader and its result was retained unchanged.

Fail immediately for checkout import, alternate runner/runtime, Architect/Workbench/Aether2 import, multiple cognitive agents, unexpected retry, provider call not bound to the frozen treatment, profile/runtime disagreement, action without authoritative observation, observation without receipt, incorrect Verifier skip, false terminal success, grader bypass, task-specific production code, or manual intervention. Any such failure keeps S6 blocked and returns to substrate remediation.

## S5c verdicts and exit gate

Record both:

1. **architecture qualification**: may pass with official grader `0` only if the microscopic evidence cleanly attributes the semantic failure to Solver/Verifier behavior rather than Aether/Harbor/substrate corruption;
2. **strong baseline qualification**: requires official grader `1`. This is the preferred target and task selection should give it a reasonable chance.

Write `S5C_CLEAN_LIVE_BASELINE_V1.json` with one unambiguous terminal state, for example `CLEAN_LIVE_BASELINE_PASS` or `CLEAN_RUNTIME_PASS_MODEL_TASK_FAIL`, plus the full evidence directory and hashes.

Only after the S5c microscopic audit proves the packaged runtime cleanly operational may the final `S5_SIMPLIFIED_BASELINE_V1` be sealed. **S6 remains blocked until this gate is complete.**

---

# S5d - Capability completeness gate (mandatory pre-S6 proof)

## S5d mission

Prove that the exact clean packaged Aether already exposes the generic computer body Luna needs, before spending S6 budget on cognition optimisation or adding new capabilities. S5d is a **proof and classification gate**, not an automatic implementation phase.

The governing admission question for every capability is:

> **Does this capability give Luna reliable access to reality it could not otherwise faithfully access, or does it tell Luna how to solve the problem?**

- If it exposes otherwise inaccessible reality or provides a generic actuator, it may be a legitimate body primitive.
- If it selects strategy, decomposition, debugging method, task semantics, or domain workflow, it is cognition and must not be added to Aether.
- If Luna can already obtain the same authoritative information through generic composition, classify the proposed direct primitive as an ergonomics/performance experiment rather than a missing core capability.

No Architect, browser agent, database agent, coding agent, audio agent, CAD agent, proof agent, task router, skill pack, benchmark-specific helper, or domain workflow may be introduced by S5d.

## S5d exact-package requirement

Run the gate from the exact S5c-qualified wheel in a clean environment, not a source checkout. Reuse S5c package/source/treatment custody and prove that all tested modules and entrypoints resolve from the qualified install.

S5d must not alter Solver/Verifier prompts, reasoning effort, continuity, budgets, cache, provider transport, action schema, Verifier policy, or completion semantics. Any source/treatment mutation invalidates the S5c package qualification and returns to S5c with a different sacrificial task.

## S5d primitive proof matrix

At minimum prove the following existing body capabilities with small generic microcases and exact receipts:

| Primitive | Required proof | Expected current classification |
|---|---|---|
| Filesystem | read -> write -> fresh reread; exact bytes/state delta | direct |
| Large file | bounded paging without information destruction | direct |
| Shell | stdout + stderr + exit code + truthful state delta | direct |
| Large output | overflow/retention handle -> exact later retrieval/search | direct |
| PTY | start -> observe -> send -> observe -> interrupt/terminate/close | direct |
| Managed process/job | launch/start -> probe -> complete or stop with generation custody | direct |
| HTTP/service | actual live service -> port/HTTP observation in task namespace | direct |
| Environment discovery | discover a non-hardcoded executable/module/resource fact | direct |
| Dependency acquisition | generic package/tool acquisition -> use -> receipt | direct |
| Network | truthful allowed success or truthful denial/failure | direct/conditional on environment |
| Artifact custody | exact bytes/hash/type/history | direct |
| Artifact transform | source -> generic command -> derivative with provenance | direct |
| Image perception | exact supported image bytes -> same-Primary native perception boundary | direct; provider boundary may reuse frozen canary evidence if source/interface identical |
| Independent image verification | Verifier independently perceives image evidence | direct |
| PDF | exact PDF -> deterministic text/page render -> Luna-accessible text/image | compositional |
| Audio | exact audio -> deterministic decode/features/spectrogram or task-local model input | compositional |
| Video | exact video -> deterministic frame/audio extraction -> perception | compositional |
| CAD/3D | exact asset -> task tool/CLI/Python inspection -> render/derived artifact | compositional/conditional on environment |
| Surface capture | Luna-selected render/screenshot command -> fresh exact captured artifact | direct compositional actuator |
| External MCP | task-declared server discovery -> tools/list -> tools/call -> exact result | direct/conditional on task environment |
| GPU | when present: truthful detection -> minimal compute; when absent: truthful absence | conditional |
| Verifier falsification | independent current-state inspection and at least one derived falsifier | direct |

For each row record: package/source identity, microcase, action route, authoritative observation, freshness/generation binding, result, and whether the capability is `PROVEN_DIRECT`, `PROVEN_COMPOSITIONAL`, `PROVEN_CONDITIONAL`, or `NOT_PROVEN`.

## S5d Frontier/TB body map

Map the frozen Frontier/TB task families onto the proven primitives without opening fresh held-out task content. The map is structural only: software engineering, systems, databases, distributed systems, ML/GPU, formal methods, security, science, CAD/hardware, documents, browser/web, images/layout, audio/music, video, spreadsheets/workbooks.

A task family is body-complete when its authoritative reality is reachable through already-proven primitives or task-declared external tools. This does **not** claim Luna will solve the task; it only rules out a missing generic sense/actuator as the primary blocker.

## S5d capability candidates

Carry forward, but do not automatically implement:

1. **Universal GUI/computer control**: generic screen observation plus click/type/scroll/keypress actuators independent of task-specific Playwright/MCP. This is a legitimate future body candidate because GUI-only state may be authoritative reality otherwise inaccessible.
2. **Native audio perception**: exact audio bytes -> native model perception, if the selected provider/model supports it. This is a legitimate sense candidate because hearing the source directly is not equivalent to harness-authored task strategy.
3. **Direct PDF/document perception**: classify as an S6 ergonomics experiment unless evidence shows the current render/extract pipeline loses authoritative information Luna cannot otherwise recover.
4. **Direct video perception**: classify as an S6 ergonomics experiment unless evidence shows frame/audio composition is insufficient.

Do not introduce any candidate before the current-body proof is complete.

## S5d exit gate

Write one immutable `S5D_CAPABILITY_COMPLETENESS_V1.json` plus a concise human audit. S5d passes when:

- every existing production primitive is exercised or explicitly classified conditional with a truthful unavailable-environment result;
- no claimed capability exists only as a registry label without an executable path;
- the 22 Primary-visible actions reconcile exactly with executor/provider routes;
- no capability test reveals hidden strategy/cognition in the harness;
- every frozen Frontier/TB task family maps to at least one proven direct/compositional/conditional body route, or is explicitly listed as a genuine gap;
- genuine gaps are separated from ergonomics/performance candidates;
- S5c source/wheel/treatment identity remains unchanged throughout the gate.

If S5d discovers a body bug, fix it generically, invalidate the current S5c seal, rebuild/requalify, and repeat S5c on a different sacrificial task before rerunning S5d.

Only after **S5c + S5d** are both sealed may S6 begin.

---

# S6 - Cognition/performance optimisation

## S6 mission

Now that harness correctness and architecture are clean, maximise Luna's whole-task correctness while reducing unnecessary context/tool/protocol burden. Every treatment is benchmark-neutral, preregistered, independently measurable and removable.

The main observed performance failures to attack are:

- narrow/local evidence -> whole-task overclaim;
- failure/falsifier salience losing prominence over time;
- weak falsification cases by Verifier on concurrency/state-interaction tasks;
- giant duplicated model-facing tool/protocol surface;
- repeated static context despite native previous-response reasoning continuity;
- low reasoning effort on hard semantic integration tasks;
- image capability discoverability;
- long-provider-call reliability;
- long-horizon budget/compaction only when genuinely pressured.

### S6 constitutional limits

- no task-specific prompt patches;
- no semantic task classifier choosing tools/effort/context;
- no per-row effort selection after results;
- no Architect/critic/sub-agent;
- no hidden grader in-loop;
- no H10/C5 content used for tuning;
- one variable family at a time;
- correctness first, then steps/tokens/latency/cost.

## S6.0 Build one experimental measurement harness

Do not use the historical dozens of one-off PCR scripts as the new permanent framework.

Create one small research-only package, final-path concept:

- `evals/performance/profile.py`
- `evals/performance/run.py`
- `evals/performance/adjudicate.py`
- `evals/performance/profile.schema.json`
- `evals/performance/CALIBRATION_BOARD_V1.json`
- `evals/performance/RESERVED_BOARD_IDS_V1.json`
- `evals/performance/SENTINELS_V1.json`

The runner calls the same production `aether run`/Harbor path. It never forks a custom Solver/runtime.

### Reserved-board protection

Before selecting calibration tasks, load only task IDs/hashes for A5/B5/C5/H10 from the frozen board authority. Do not open C5/H10 prompts. Reject any calibration task ID that overlaps a reserved set.

Known A5/B5 IDs are regression-only. B5 is no longer fresh.

### Calibration set construction

Pre-register a non-reserved set stratified by generic task pressure, preferably 12 tasks total after availability checks:

- semantic/contract integration;
- stateful/concurrency;
- service/process lifecycle;
- resource/performance constraint;
- multimodal/artifact construction;
- parser/compiler/polyglot;
- dependency/bootstrap;
- long-horizon/multi-step transformation.

Historical candidates such as `gcode-to-text`, `video-processing`, `nginx-request-logging`, `filter-js-from-html`, `sparql-university`, `fix-code-vulnerability`, `protein-assembly`, `regex-log`, `cancel-async-tasks`, `configure-git-webserver`, `openssl-selfsigned-cert`, `kv-store-grpc` may be used only after mechanically proving no reserved-board overlap. Their role is calibration, not forward evidence.

### Deterministic sentinels

Include microcases for:

- `/app/app/...` path identity;
- failed action persistence/supersession;
- mixed action result;
- uncertain state -> Verifier activation without false success;
- negative semantic finding surviving evidence-label correction;
- state mutation custody;
- one action per turn;
- incomplete provider output never executes;
- image/perception discoverability;
- managed process/service lifecycle;
- long background provider response lifecycle using provider-free/fake client where possible.

### Per-call metrics

Extend/reuse:

- `postmerge_observability.py`
- `request_anatomy.py`
- `model_interface.py`
- `providers/azure_model.py`

Record:

- request/instructions/input/tools serialized bytes;
- static-prefix bytes;
- fresh-delta bytes;
- tool schema bytes;
- input tokens;
- cached input tokens;
- cache-write tokens when provider reports them;
- output tokens;
- reasoning tokens;
- reasoning effort/mode/context requested + effective;
- previous-response id presence/chain integrity;
- create latency;
- poll latency;
- total provider latency;
- provider job status;
- model/Verifier call count;
- action count;
- submit count;
- repeated/equivalent inspection count;
- state-changing action count;
- timeout/budget termination;
- monetary cost only when authoritatively measured, otherwise `unknown`.

### Task-level primary metric

1. whole-task official grader pass/reward;
2. validity: no harness/provider/launch invalidity;
3. per-test outcome only as diagnostic/tie-break information;
4. Verifier false-clean/false-block/concordance;
5. first-submit completion quality;
6. action/provider-turn efficiency;
7. latency/tokens/cost.

## S6.1 Continuity-aware context projection

Current selected treatment:

- `previous_response_id`;
- `reasoning.context=all_turns`;
- `minimal_v1` PCR context;
- repeated stable prefix/instructions;
- full durable history retained internally;
- working-state checkpoint disabled.

Current OpenAI GPT-5.6 guidance says all-turns + previous-response makes earlier reasoning available, while previous `instructions` are not carried forward. Therefore continuing calls must resend the small invariant instructions, but they do not automatically need full old task/environment/history replay.

### Files

- `aether/pcr_context.py` (current `aether_next_build/aether_next/pcr_context.py`)
- `aether/model_hooks.py`
- `aether/providers/azure_model.py`
- current `kernel_messages.py` / future Solver request builder
- current `postmerge_research.py` -> explicit S6 treatment profile
- observability files above.

### Arms

C0 incumbent control:

- current simplified S5 request projection;
- previous_response + all_turns;
- current repeated prefix behaviour.

C1 native-continuity + fresh reality delta:

- first call receives raw task + initial factual environment/capability bootstrap;
- subsequent calls resend only minimal invariant instructions required on every request;
- current call receives latest exact action result, changed external state, unresolved failures/falsifiers, open Verifier findings, current evidence handles, capability changes and remaining budgets;
- no full historical receipt replay;
- historical receipts remain queryable on demand.

C2 C1 + tiny task anchor only if needed:

- stable task/run ID and raw-task hash/custody binding;
- not a semantic summary.

C3 bounded-history diagnostic only if C1/C2 loses correctness:

- mechanically recent bounded observations, not semantic relevance selection;
- used to identify what provider continuity failed to make usable.

Diagnostic `current_turn` reasoning context is permitted only if all-turns appears to preserve stale reasoning despite clear fresh contradictions; it is not a default candidate.

### Fresh-delta content

Always include current truth for mutable reality:

- latest action outcome with top-level succeeded/failed/mixed/missing;
- exact handles for full observation;
- created/modified/removed paths since prior boundary;
- current process/job/service state changes;
- unresolved runtime failures;
- active factual Verifier findings;
- current task-state generation/digest when needed for submission custody;
- remaining hard budgets;
- capability availability changes.

Do not include harness-authored hypotheses, next diagnostic, replan instruction or semantic summary.

### Promotion

Context treatment wins only if whole-task correctness is preserved/improved. Token savings alone cannot win. If correctness ties, prefer lower request surface, fewer repeated inspections and lower latency/cost.

## S6.2 Lean Solver prompt and remove duplicated protocol/tool descriptions

A5 forensic measurement found every Solver request exposed approximately 3.1k chars of human-readable action schema plus approximately 23.5k chars of native `pcr_turn` tool schema. The native tool schema alone was roughly 51-59% of serialized Solver request surface across A1-A5.

GPT-5.6 guidance explicitly recommends leaner prompts/tools and reports directional internal coding-agent gains from removing repeated instructions, but our own eval decides promotion.

### Files

- `compiler_prefix.py` / future `solver_prompt.py`
- `pcr_provider_protocol.py`
- `providers/azure_model.py`
- `runtime_ir.py` action-schema projection
- `model_interface.py`

### Sequential treatments

P0: incumbent simplified prompt.

P1: remove human-readable `[action_schema]` duplication while keeping exact native `pcr_turn` schema authoritative.

P2: remove/merge repeated protocol prose that the strict provider schema already enforces. Candidate repeated concepts include:

- one action only;
- no prose outside tool object;
- exact arguments only;
- submit versus act exclusivity;
- kernel-generated action IDs.

Keep each hard behavioural rule stated once where the model actually needs it.

P3: simplify `PRIMARY_AGENT_CONSTITUTION` + PCR protocol cards to the smallest version that preserves raw-task authority, autonomy boundary, evidence grounding and submit meaning.

Do not add examples unless a measured failure proves the schema/rule is misunderstood.

### Promotion

Same correctness-first rule. Also measure first-submit quality and action selection, because an over-aggressive prompt reduction that saves tokens but increases malformed/low-quality turns is killed.

## S6.3 Direct native tool experiment

Current architecture forces one huge provider function `pcr_turn`, whose arguments contain a nested union of almost the entire action catalogue.

Test direct native tools without changing the causal loop.

### Files

- `pcr_provider_protocol.py`
- `providers/azure_model.py`
- `model_parse.py`
- `runtime_ir.py`
- `kernel_dispatch.py`
- `model_interface.py`
- corresponding provider/parser/action tests.

### Direct surface design

Expose one provider function per mechanically available action, generated from the same single action-argument authority currently used by PCR. Examples:

- `read_file`
- `read_file_page`
- `read_output`
- `grep_output`
- `write_file`
- `run_command`
- `start_terminal_session`
- `terminal_send`
- `terminal_read`
- `launch_process`
- `start_job`
- `probe_job`
- `probe_service`
- `inspect_artifact`
- bootstrap/environment-extension actions that are actually available
- `submit_candidate` for the completion claim.

Mechanical availability may hide unavailable actions; task semantic relevance must never be used to choose the subset.

Keep:

- `parallel_tool_calls=false`;
- `max_tool_calls=1`;
- exactly one action or one submit per response;
- one authoritative observation before next model decision;
- same kernel dispatch and receipt path;
- same action arguments;
- same completion semantics.

### Vision

If the existing body can natively return image perception from `inspect_artifact`, state that in the tool description. If a separate factual `perceive_artifact` function better maps to the existing body without adding new semantic authority, test it as a separate direct-tool variant.

### Controls

T0: giant `pcr_turn` after prompt de-duplication.

T1: direct functions, same action set, same prompt/context/effort.

T2 only if T1 still exposes excessive irrelevant schema: direct functions filtered solely by observed capability availability.

Do not combine direct tools with batching.

### Programmatic Tool Calling

Do not make PTC the default Aether loop. GPT-5.6 guidance says direct calls are preferable when each result may change the model's next decision, exactly matching Aether's causal architecture.

Only permit a late research microcase for bounded read-only aggregation where no intermediate result requires model judgment. It cannot perform state-changing task actions and cannot replace the core loop unless independent evidence later overturns this design.

## S6.4 Verifier performance optimisation

The current Verifier prompt is architecturally good. Do not add more instructions first.

Observed misses on WAL/session were falsification-strength failures: the model tested nearby/easier cases rather than the strongest raw-task interaction. Current effort is low.

### Files

- `pcr_verifier_prompt.py`
- `pcr_verifier_context.py`
- `verifier.py`
- `verifier_generation.py`
- `verifier_budget.py`
- `verify_completion_protocol.py`
- `providers/azure_model.py`
- experimental profile only; no task-specific prompt.

### V1 effort comparison on frozen candidate states

Use fixed, reproducible candidate world states from non-reserved calibration tasks so Solver variability is removed.

Compare:

- low
- medium
- high

Hold prompt, packet, tools and budgets fixed.

Metrics:

- detects known current defect;
- false clean;
- false repair/block;
- strongest-boundary challenge quality;
- independent versus Solver-mirroring inspection;
- inspection/model-call count;
- duplicate inspection rate;
- latency/tokens.

If high clearly improves and there are still misses, xhigh/max can be a second-stage challenger on the hardest predeclared states.

### V2 prompt subtraction only after effort result

The current `PCR_VERIFIER_SEMANTIC_GUIDE` and `PCR_VERIFIER_CONSTITUTION` repeat several concepts. Test subtraction/merging, not prompt expansion.

Keep once:

- raw task sole authority;
- Solver claims are not proof;
- independent current inspection;
- strongest material boundary/falsification;
- completed only with evidence for every visible material requirement;
- do not guess hidden tests.

Provider/schema mechanics should live in schema/host, not a long manual.

### V3 activation-scoped continuity if redundancy remains

Independence means a new Solver candidate should start a fresh Verifier conversation. But the several inspection turns inside one Verifier activation may benefit from provider continuity.

If current Verifier repeatedly asks for the same receipt/inspection because each generation loses prior local reasoning, test:

- fresh chain per activation;
- `previous_response_id + all_turns` inside that activation only;
- reset completely on next Solver submission.

Do not use persistence across candidate generations unless separately justified.

### V4 budget only if proven constrained

Current phase budget is up to 7 model calls, 3 investigation batches, 12 direct requests/batch, etc. Increase only if logs show a high-quality Verifier was cut off before its intended falsification. Do not reward wandering with unlimited calls.

## S6.5 Solver reasoning-effort selection

Run only after context/prompt/tool interface is frozen.

### Primary approved comparison

- low
- medium
- high

Same:

- source commit;
- task set;
- tool surface;
- context projection;
- Solver prompt;
- Verifier treatment;
- max steps;
- output cap;
- transport/background mode;
- retry policy;
- grader.

Correctness is primary. Higher reasoning is not rejected simply because it costs more if it materially increases whole-task success.

### Staged funnel

Stage R1:

- all three efforts on a small preregistered calibration slice covering semantic integration, concurrency and resource/performance tasks.

Stage R2:

- best two efforts on the remaining calibration set.

Tie-break only if needed:

- one preregistered extra run on disagreement tasks, never A5/B5/C5/H10.

No repeated reruns until a favourite wins.

### xhigh/max ceiling challenger

GPT-5.6 Luna currently supports `none`, `low`, `medium`, `high`, `xhigh`, and `max` reasoning effort.

If the low->medium->high curve shows positive quality returns, compare:

- winning high/medium incumbent;
- xhigh;
- max.

Use only the hardest predeclared calibration slice first. Promote only if quality gain survives the expanded calibration set.

Do not use per-task adaptive effort. Aether would need to semantically classify task difficulty, which risks harness-led cognition and contaminates comparability. Freeze one global Solver effort for the benchmark candidate.

## S6.6 Standard versus GPT-5.6 pro mode

GPT-5.6 now exposes `reasoning.mode="pro"` independently from reasoning effort.

This is a separate experiment, never bundled with an effort change.

Preflight first:

- current Azure deployment accepts pro mode;
- strict function/tool calling remains compatible;
- background Responses lifecycle works;
- usage/cost/latency are captured;
- no change to action-count boundary.

If compatible, compare standard versus pro at the already-selected reasoning effort on a small hard calibration slice. Expand only if pro gains whole-task correctness.

Kill pro if it mainly adds latency/tokens without additional passes or if it conflicts with iterative tool calling.

## S6.7 Provider/context cost and latency treatments

Do only after request shape is selected.

### Prompt caching

Current Solver production explicitly uses `prompt_cache_mode="off"`. GPT-5.6 supports implicit/explicit caching and reports cache-write tokens; OpenAI notes cache writes are billed above uncached input while reads are discounted.

Azure support/semantics must be proven with a provider canary before changing production.

Compare identical semantic request content under:

- cache off/current;
- provider implicit caching if supported;
- explicit stable breakpoint mode if supported.

This is a cost/latency treatment. It cannot win over a correctness regression.

Update deprecated request fields such as `prompt_cache_retention` only after confirming Azure parity with the current Responses API.

### Background/poll budgets

Background mode stays selected. Tune polling interval/timeout only from observed job durations.

Rules:

- never retry a timed-out request with uncertain server-side fate unless the provider proves cancellation/terminal failure;
- leave enough wall-clock reserve for Verifier and Harbor grading;
- high/xhigh/max/pro may require different fixed provider call timeout, but that timeout must be globally frozen with the selected profile.

## S6.8 Output, turn, compaction and working-state budgets

### Output tokens

Current Solver cap: 16k. Current A5/B5 runs did not hit it; observed outputs were much smaller. Historical A3 did hit 16k twice.

Therefore:

- do not raise cap by default;
- add 32k/64k only as a separate treatment if calibration reproduces `provider_output_incomplete`/length pressure;
- record max output as a treatment field.

Verifier current selected cap is 12k; same rule.

GPT-5.6 Luna supports up to 128k output, but maximum capability is not a reason to allocate it.

### Solver turn/max-step budget

Increase only if a task is demonstrably near completion and terminated solely because the fixed turn budget exhausted. Do not mask looping with more steps.

### Native compaction

Current selected mode is off and A5 showed no native compaction pressure. GPT-5.6 context is large, and a successful fresh-delta projection should reduce growth further.

Test `previous_response_compaction` only on long-horizon calibration/synthetic runs that actually cross a preregistered threshold. Preserve raw task, current world truth, unresolved falsifiers, identifiers and provider continuity semantics.

Do not tune compaction on H10.

### Model-owned working state

Current production disables the optional PCR working-state checkpoint.

Only test it if fresh-delta/native continuity loses long-horizon task state. If tested:

- checkpoint is authored by Luna, not Aether;
- it is not task evidence;
- Aether stores/returns it mechanically;
- it cannot override current observed reality;
- measure added schema/output tokens versus actual correctness gain.

If all-turns continuity already preserves cognition, keep it disabled.

## S6.9 Integrated-candidate interaction check

Sequential winners can interact. Before board freeze:

1. assemble only treatments that independently won;
2. run the full non-reserved calibration set once under the integrated candidate;
3. compare to S5 simplified baseline and to each last-step parent;
4. if integrated performance regresses, isolate only the interacting variables on the disagreement subset;
5. remove the losing mechanism rather than layering compensation.

No A5/B5/C5/H10 used to select the integrated treatment.

## S6.10 Freeze final pre-board treatment

Create a cryptographic candidate manifest binding:

- source commit/tree;
- installed package/wheel hash;
- Harbor version;
- task-launcher hash;
- Solver/Verifier model/deployment;
- Solver effort;
- Verifier effort;
- reasoning mode;
- reasoning context/effective expectation;
- continuity mode;
- context projection id;
- prompt hashes;
- tool schema/surface hash;
- output caps;
- turn/Verifier budgets;
- background/poll settings;
- caching mode;
- retries = 0;
- one action boundary;
- deterministic suite results;
- provider canary receipts;
- calibration result/adjudication artifact.

No model-facing or runtime change after this freeze before C5 is consumed.

---

# S6 promotion/adjudication rules

## Hard validity gates

An arm cannot win if it introduces:

- invalid task/run;
- provider schema/protocol failure;
- false terminal success path;
- hidden-grader leakage;
- task-specific benchmark logic;
- more than one causal external action per Solver observation boundary;
- Architect/sub-agent/critic planning;
- loss of failed/falsifying evidence;
- stale/incorrect world state;
- secret leakage;
- launch/custody ambiguity.

## Quality ordering

1. whole-task passes;
2. fewer false-clean Verifier outcomes / better transfer across task families;
3. completion quality/first-submit quality;
4. fewer harness-owned invalid/failure modes;
5. fewer provider/action turns;
6. lower latency;
7. lower token/cost footprint;
8. lower implementation complexity.

A token-saving treatment that loses a whole-task pass is normally rejected.

## When evidence is close

Prefer the incumbent/simpler mechanism unless a predeclared tie-break gives consistent quality evidence. Do not add more and more reruns until statistical noise chooses the desired arm.

---

# Failure-family -> improvement map

| Known failure family | Primary phase/treatment |
|---|---|
| circuit hard-coded examples + ignored wrong sample outputs | S6 context/prompt salience + Solver reasoning; submit semantics already fixed |
| data 64MB constraint ignored after exit137/high memory | S0/S2 failed-result salience + S6 Solver reasoning |
| polyglot Rust-only recovery / repeated incomplete submits | S6 Solver reasoning; output cap only if truncation recurs |
| session narrow checks miss lifetime/retraction interactions | S6 Verifier effort/falsification quality + Solver reasoning |
| WAL weak concurrency inversion tests | S6 Verifier effort/falsification quality |
| CAD invalid STEP/coarse visual understanding | S0 perception discoverability + S6 direct tools/reasoning |
| DNA exact clamp finding degraded before Solver | S0 semantic-negative finding preservation; then Solver/Verifier reasoning |
| LLM batching optimises proxy instead of performance objective | S6 Solver reasoning + leaner context/tool interface |
| MIPS no frame/long-horizon failure | S6 direct tools/reasoning; budget only if true exhaustion demonstrated |
| 1260s foreground provider deaths | S0 background Responses fix |
| `bn-fit-modify` no-model startup | S0/S3/S4 exact installed agent import and one launcher |

---

# Evaluation cycle E2 - A5 + B5 + fresh C5

This is the next real board cycle because A5+B5 cycle 1 has already occurred and been audited.

## E2 rules

- same frozen S6 candidate across all 15 rows;
- one attempt per row;
- zero retries;
- no code/profile/prompt/tool/effort changes between A5, B5 and C5;
- official Harbor lifecycle/grader only;
- A5/B5 are diagnostic/regression evidence;
- C5 is forward-generalisation evidence.

Preferred order:

1. provider-free admission and environment preflight;
2. A5;
3. B5;
4. C5 immediately under the same freeze.

A5/B5 results must not trigger semantic/performance tuning before C5. The only acceptable stop before C5 is a genuine invalid execution/custody/provider failure that means the frozen candidate was not actually exercised; in that case do not consume C5, correct only the invalid substrate, reseal, and treat the previous board attempt as invalid rather than capability evidence.

## E2 evidence

For every row retain:

- exact raw task hash;
- source/task/image/runtime/Harbor identities;
- launch/preflight receipt;
- Solver/Verifier provider requests and response IDs;
- previous-response chain;
- model interface captures;
- all actions/observations;
- world-state changes;
- findings/falsifiers;
- submit attempts;
- official grader result;
- tokens/cache writes/reasoning/latency;
- authoritative or unknown monetary cost.

---

# Audit A2 - Microscopic post-E2 forensic + architecture audit

Do not merely inspect score.

For every trajectory inspect:

- first decisive semantic divergence;
- claim/evidence scope alignment;
- latest negative evidence salience;
- provider continuity/request shape;
- tool choice and unnecessary translation;
- repeated/equivalent actions;
- Verifier falsification strategy;
- Verifier finding durability;
- completion/submission decision;
- process/world-state correctness;
- timeouts/budgets;
- official grader mismatch;
- whether any harness mechanism led semantic cognition.

Cross-task clustering must classify failures among:

- Solver capability/reasoning;
- Verifier quality;
- body/capability missing;
- interface/discoverability;
- world-state/evidence bug;
- provider/transport;
- runner/launch;
- budget;
- official environment/task invalidity.

Only generic cross-task mechanisms advance.

---

# Final improvement cycle F

After A2, implement the smallest evidence-backed generic improvements only.

Rules:

- no new broad architecture;
- no task-ID branches;
- no per-row model settings;
- no C5-specific patch disguised as generic;
- deterministic tests and calibration sentinels first;
- if a change alters cognition/interface, validate on non-reserved calibration before final board.

Then freeze again and run one final:

`A5 + B5 + C5`

All are now known regression boards, so the final value is stability/closure rather than fresh generalisation. C5's first E2 result remains the important fresh-transfer evidence.

---

# Final audit and hard stop

Final audit must publish:

- final commit/tree/package hash;
- final production LOC/import closure;
- one runner/one launcher proof;
- zero Architect/Workbench/Aether-2 production dependencies;
- deterministic test census;
- provider canary evidence;
- final treatment profile;
- A5/B5/C5 outcome matrix;
- first C5 fresh score distinguished from later regression score;
- remaining Solver/Verifier/body limitations;
- cost/token/latency profile;
- confidence that scores measure Luna rather than harness corruption;
- H10 readiness assessment without opening/running H10.

Then STOP.

No D5. No H10. No extra improvement cycle until the user explicitly tells Main what happens next.

---

# File disposition summary

## Production keep/refactor core

Expected long-term production responsibilities remain in or converge from:

- `harbor_runtime.py`
- `harbor_executor.py`
- `environment_probe.py`
- `environment_extensions.py`
- `envmap_builder.py` only if still needed after runtime collapse
- `kernel.py` substantially reduced
- `kernel_dispatch.py`
- `kernel_actions.py` / body action modules only where actually used
- `pcr_context.py` as direct factual context builder
- `pcr_provider_protocol.py` or direct-tool schema authority
- `providers/azure_model.py` reduced to provider transport/telemetry/continuity
- `ledger.py`
- `world.py`
- `inspection_registry.py`
- Verifier protocol/inspection modules
- submission/evidence/finding lifecycle modules
- ATIF/evidence export
- final `harbor_agent.py`
- final `cli.py` / launch admission module
- one immutable model treatment/profile definition.

## Remove from production / move to research or archive

- all Architect V2/V3/Workbench modules;
- `reference_legacy`;
- old Architect config/repair/reconfigure path;
- old Aether-2 runtime after invariant migration;
- root runner stub/compatibility/synthetic substrate;
- old internal Docker benchmark runner;
- custom Terminal-Bench staging/grading runner;
- Verifier replay agent from production namespace;
- B5-specific scheduler/trigger logic;
- dozens of dated board/run/materialize/adjudicate scripts superseded by one eval harness;
- generated evidence under source roots;
- contradictory architecture docs as current docs.

## Use as migration evidence then retire

- `tools/bench_launch.py`
- `tools/bench_run_spec.schema.json`
- `tests/test_bench_launch.py`
- `aether_next_build/scripts/run_workspace_harbor_v1.py`
- `aether_next_build/scripts/materialize_first_submit_launch_custody_v1.py`

Their retained invariants move into S4; their duplicate frameworks should not survive final convergence.

---

# Commit/release boundaries

Recommended immutable boundaries:

1. `S0-correctness` - current audited correctness fixes only.
2. `S1a-import-isolation` - zero Architect imports on production path.
3. `S1b-pcr-only` - alternate cognition removed from production API/control flow.
4. `S2-runtime-collapse` - direct PCR runtime/context/state ownership.
5. `S3-one-runner` - packaged Harbor agent only.
6. `S4-one-launcher` - strict minimal launch boundary.
7. `S5-clean-package` - physical package/repo convergence and S5b remediation.
8. `S5c-clean-live-baseline` - exact final S5 wheel + one preregistered live task + microscopic audit; no optimisation change.
9. `S5d-capability-completeness` - exact S5c wheel; provider-free generic body microcases by default; no cognition/treatment change.
10. Experimental S6 branches/commits per treatment; losing branches not merged.
11. `S6-frozen-candidate` - only independently winning treatments.
12. `E2-freeze` - exact A5+B5+C5 candidate.
13. `F-final-candidate` - final generic improvements.
14. final audit/freeze tag.

Never squash away the boundaries needed for causal audit.

---

# Spend and resource governance

S0-S5b should require no paid model calls except explicitly authorised provider canaries. S5c requires one preregistered live Luna task for each newly changed source candidate; a failed/invalidated candidate is frozen and never retried on the same task. S5d is provider-free by default and may reuse already-frozen native-modality canary evidence when the source/interface identity is unchanged; any new provider call requires an explicit bounded canary manifest.

S6 uses a funnel to avoid combinatorial spend:

1. deterministic/provider-fake tests;
2. one/two-call provider API canaries;
3. small calibration slice per treatment;
4. only winning treatments advance to full calibration;
5. only one integrated candidate reaches boards.

Every live experiment manifest caps:

- number of task runs;
- maximum provider calls;
- maximum input/output tokens if enforceable;
- max wall clock;
- zero automatic retries;
- monetary spend only when an authoritative Azure price/meter source is available.

Do not treat current OpenAI list pricing as proof of Azure billing. For reference, current OpenAI documentation lists GPT-5.6 Luna at $0.20/M input, $0.02/M cached input and $1.20/M output, with cache writes priced above ordinary input and long-input surcharges beyond the documented threshold. Azure deployment billing must be independently established before dollar claims.

---

# Definition of success

The project is ready for the final H10 decision when all of these are true:

1. production source has one PCR architecture, one Harbor adapter, one launcher;
2. zero known harness false-success/false-block/world-corruption/provider-admission defects remain;
3. no invalid rows in the final evaluation cycle;
4. A5/B5 known failures are mostly or completely extinguished without task-specific code;
5. fresh C5 transfer is strong enough to support generalisation rather than known-set repair;
6. Verifier catches materially wrong candidates without becoming a semantic planner;
7. Solver operates at the globally best validated Luna reasoning/interface treatment;
8. context/tool/protocol surface is no larger than evidence justifies;
9. long-horizon/provider lifecycle is robust under the chosen high-quality reasoning setting;
10. every final claim is reconstructable from sealed evidence.

The target is not a pretty refactor. The target is that a benchmark failure can finally be interpreted as a real limitation of Luna/its chosen cognition rather than uncertainty about Aether, runner, launch, context, evidence or Verifier corruption.
