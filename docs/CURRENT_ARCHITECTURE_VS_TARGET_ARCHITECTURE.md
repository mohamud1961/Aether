# Current Architecture vs Target Architecture

Status: pre-plan architecture audit. This document maps current code to the
target harness design. It is not an implementation plan and does not authorize
code changes by itself.

Date: 2026-07-02

## Target Spine

```text
Architect designs the workbench
->
Solver works inside it
->
Verifier judges with evidence and verifier capabilities
->
Agent terminates
->
Official grader evaluates
->
Ledger records
```

The official grader is not part of the agent loop. It measures the completed
run after termination.

## Non-Negotiable Principles

The harness must never compensate for the model.

The harness must not solve, simplify, infer, benchmark-specialize, or patch over
model weakness. If the model improves, benchmark performance should improve
without changing task-specific harness logic.

Every behavior has exactly one owner:

- Architect owns workbench design.
- Solver owns solving.
- Verifier owns task-state judgement.
- Harness owns execution, routing, safety, context mechanics, and recording.
- Official grader owns benchmark measurement.
- Ledger owns durable memory and audit evidence.

Shared ownership is treated as a design smell. The known bad pattern is:
verifier plus proof contract both judging, architect plus static solver prompt
both instructing, solver plus no-progress controller both deciding next action,
and completion gate plus verifier both deciding done.

## Implementation Split

There are two relevant code lines today.

`harness/aether2/` is the repo-declared active public Aether-2 line. It contains
the current loop, runtime config, tool registry, verifier rounds, read-only
verification context, receipts, traces, Harbor/Docker integration, and eval
plumbing.

`aether_next_build/aether_next/` is the workbench/architect prototype line that
Opus audited. It contains the clearest WorkbenchArchitect, HarnessConfigIR, and
architect-authored solver/verifier prompt schema, but it also contains the
repeated-action context bug, duplicate old architect paths, static solver prompt
conflicts, and completion-gate/proof-contract judgement machinery.

Before implementation planning, the integration target must be named. The
recommended target is a subtractive convergence: preserve the robust substrate
from `harness/aether2/`, import the useful workbench ownership ideas from
`aether_next_build/aether_next/`, and delete duplicate or judgement-heavy paths.

## Runtime Invariants vs Judgement

Permanent runtime invariants are not optional and should not be deleted:

- action schema parsing;
- model output parsing;
- workspace creation;
- sandbox/container creation;
- permission enforcement;
- tool routing;
- receipt writing;
- trace writing;
- model exchange recording;
- context assembly;
- prompt-cacheable stable prefix mechanics;
- artifact capture;
- verifier verdict parsing;
- certified sandbox/workspace contract;
- grader separation.

Judgement to shrink, delete, or move into model-owned roles:

- task-family proof analyzers;
- deterministic completion vetoes above the verifier;
- hardcoded benchmark/task assumptions;
- solver behavioral prompts not authored by the architect;
- no-progress enforcement that compensates for hidden context;
- fake or advisory config knobs presented as real;
- broad prebuilt check libraries that encode benchmark task shapes;
- silent fallback from failed architect/config generation to a baseline agent.

## Component Audit

| Component | Exists | Used | Current Owner | Desired Owner | Current Behavior | Desired Behavior | Action |
|---|---:|---:|---|---|---|---|---|
| Governing vision | Yes | Yes | Docs / human governance | Docs / human governance | `docs/HARNESS_VISION.md` states the better-model litmus and role boundaries. One prompt still says "grader decides." | Vision text, prompts, and runtime docs all say grader evaluates after the agent terminates. | Keep and align wording. |
| Public active loop | Yes | Yes | Harness | Harness | `harness/aether2/control/loop.py` runs orientation, optional AHP startup, model calls, tool dispatch, verification rounds, compaction, and finalization. | Generic loop only. No task-specific judgement. Solver and verifier behavior comes from architect-owned config/prompt surfaces. | Keep substrate, simplify judgement branches. |
| Workbench prototype loop | Yes | Prototype / audit | Harness | Either retire or merge selectively | `aether_next_build/aether_next/kernel.py` runs Workbench/Contract/IR config paths, static solver hook, completion gate, verifier calls, reconfiguration, no-progress, and proof contract. | Only one architect path and one loop authority. No duplicate config systems. | Rewrite/selectively port, then retire duplicate path. |
| Architect role | Yes in two forms | AHP used behind flag; Workbench prototype selectable | AHP model plus harness adapter; WorkbenchArchitect in prototype | Architect | `harness/aether2` AHP generates an adaptive profile and maps it into `HarnessRunConfig`. `aether_next` WorkbenchArchitect emits `HarnessConfigIR`. | One architect designs the task workbench: solver prompt, verifier prompt, success definition, evidence priorities, context policy, verifier capabilities, feedback style. | Converge into one architect surface. |
| Architect failure handling | Yes | Yes | Harness | Harness for parse/runtime validity only | AHP and Workbench both attempt JSON/schema repair. Workbench gives one repair retry, then falls back to baseline with `workbench_architect_configure_failed`. | One format/schema repair retry is allowed. If still invalid, certified run is `agent_initialization_failure`; no certified baseline fallback. | Rewrite failure policy. |
| Semantic architect quality | Partial | Audit only | Harness rubric / offline eval | Open | `aether_next_build/aether_next/architect_quality.py` scores prompt/config quality for architect-only evals. It is not a certified startup gate. | Leave semantic retry open until there is eval-backed evidence for who may judge weak configs. | Do not gate certified runs on this yet. |
| Solver prompt ownership | Partial | Yes | Shared: static harness prompt plus generated guidance | Architect, with harness mechanical frame only | `harness/aether2/runtime/prompts.py` has a large static behavioral `SYSTEM_PROMPT`. AHP by default keeps it and adds task block as extra prefix. `aether_next/model_hooks.py` has static `SOLVER_SYSTEM_PROMPT`. | Architect-authored solver prompt is the substantive system prompt. Harness adds only mechanical interface/tool/schema invariants. | Rewrite prompt assembly. |
| Verifier prompt ownership | Partial | Yes | Shared: static verifier prompt plus policy fields | Architect | `harness/aether2/runtime/verify.py` uses a static fresh-context verifier system prompt. AHP can add verifier requirements/focus. Workbench prototype has architect-authored verifier prompt but one-shot verifier. | Architect-authored verifier prompt defines success criteria, false-positive traps, evidence requirements, and feedback style. Harness supplies schema and read-only capability mechanics. | Rewrite prompt assembly. |
| Runtime config object | Yes | Yes | Harness | Harness schema, Architect content | `harness/aether2/runtime/run_config.py` defines `HarnessRunConfig` with tool, context, completion, verifier, repeat, compaction, and loop policy. `aether_next/runtime_ir.py` has `RuntimeConfigIR` and `CompiledRuntime`. | One typed config spine. Harness validates schema/invariants; architect fills task-specific fields. | Keep, consolidate. |
| Workbench config schema | Yes | Prototype | Architect plus harness parser | Architect content, harness parser | `aether_next/workbench_config.py` includes solver/verifier prompts, tool policy, context, memory, verification, feedback, helper-script, limits. Some fields are advisory or misleading. | Schema exposes only real realized knobs. Remove fake/dead fields. | Rewrite schema before promotion. |
| Tool policy in config | Yes | Mixed | Architect/AHP currently selects or declares tools | Harness for solver core; Architect only for verifier focus if needed | `harness/aether2` can select tools in `ToolPolicy`. `aether_next` records `tool_policy` but stable-core tools remain visible. | Solver gets stable core tools unless safety disables. Architect should not pretend to hide solver tools. Verifier capabilities may be architect-focused within a generic read-only set. | Demote/remove from architect config. |
| Helper script policy | Yes in Workbench schema | Advisory | Architect/harness | Solver via normal tools | `aether_next` has `helper_script_policy`, but there is no distinct helper action. Solver can already write/run scripts. | No separate config surface. Task-local helpers are normal solver artifacts and untrusted for completion unless independently verified. | Delete from config. |
| Compiler / config realization | Yes | Yes | Harness | Harness | `harness/aether2` maps AHP profile into `HarnessRunConfig`. `aether_next/compiler.py` compiles IR into prefix sections, action schema, policies, and realization metadata. | Compiler realizes architect config honestly and records every realized, rejected, or unsupported field. No silent ignored config. | Keep and harden realization audit. |
| Prompt assembly / caching | Yes | Yes | Harness | Harness mechanics, Architect content | `harness/aether2/runtime/context.py` builds prefix from system prompt, task, orientation, tool schemas, frozen contract, extra prefix. `aether_next/compiler.py` puts architect identity among many prefix sections; static solver prompt may sit outside cacheable prefix. | Cacheable stable prefix contains mechanical frame, architect solver/verifier prompts, tool schema, task, orientation, and invariant context. Only per-step packet changes. | Rewrite assembly where static behavioral prompts conflict. |
| Context ownership | Yes | Yes | Shared | Split by rule | `harness/aether2` transcript contains tool result messages and tail telemetry. `aether_next` context packet can drop stdout and expose only summaries under some modes. | Harness invariant: recent tool outputs, receipts, schema/tool errors, active findings, workspace/process state. Architect-owned: preservation priorities, compression strategy, retrieval policy. | Codify invariant, fix `aether_next` if retained. |
| Recent tool outputs | Yes in Aether-2; broken in Aether-Next | Yes | Harness | Harness invariant | `harness/aether2` appends tool observations to transcript. `aether_next/context_compiler.py` can show only `recent_progress` summaries, causing rational repeated actions. | Recent command/read/write/check outputs are always visible or preserved through compacted receipt continuity. Never optional. | Keep in Aether-2, fix/delete broken Aether-Next path. |
| Context compaction | Yes | Yes | Harness with some config knobs | Harness mechanics plus Architect priorities | `harness/aether2` rebases at 60 percent of `context_window_tokens` defaulting to 128k and preserves fact ledger plus last turns. `aether_next` defaults model window to 8000. | Harness supplies real model window. Architect can set ratio and preservation/deprioritization policy. Required evidence and recent outputs must survive. | Keep Aether-2 mechanics; fix 8000-token prototype bug if reused. |
| Receipt-driven context pack | Yes | Variant path | Harness | Harness mechanics, Architect priorities | `harness/aether2/control/receipt_driven_variant.py` and `receipt_store.py` provide context packs, task-local tools, proof state, and receipt continuity. | Durable, queryable evidence store for context and replay. Does not decide task success. | Keep as substrate, remove judgement coupling. |
| Action schema | Yes | Yes | Harness | Harness | Native tools are registered in `harness/aether2/tools/native.py` and `tools/registry.py`; `aether_next` uses action kinds in `runtime_ir.py`. | Stable mechanical contract. Parser rejects invalid calls. Architect does not own syntax. | Keep. |
| Tool routing / permissions | Yes | Yes | Harness | Harness | `ToolRegistry.invoke`, `dispatch_with_hooks`, and `PermissionManager` route tools with permissions and hook traces. | Same, with no task-specific affordance hidden in routing. | Keep and audit genericity. |
| Solver tools | Yes | Yes | Harness | Harness | Aether-2 native tools include run/read/write/jobs/sessions/wait/task_done/task_blocked/query_evidence/inspect_artifact. | Stable core toolset. Add solver tools only when they are generic substrate, not benchmark shortcuts. | Keep, resist expansion. |
| Verifier capabilities | Yes in Aether-2; missing in Aether-Next | Yes in Aether-2 | Harness | Architect policy plus harness enforcement | `harness/aether2/control/verification_context.py` exposes read-only run/read/job/session tools and records attempts. `aether_next` verifier is one-shot packet judge. | Bounded read-only verifier agent. Architect defines evidence priorities and capability focus; harness enforces read-only sandbox and records probes. | Use Aether-2 design, not Aether-Next one-shot. |
| Verifier architecture | Partial | Yes | Shared | Verifier | `harness/aether2/runtime/verify.py` allows one inspection tool-call turn, then final report; outer loop can run 1-3 rounds via config. | Target: bounded read-only verifier with small budget, initially 3 rounds max. It may inspect/probe, but cannot mutate or solve. | Keep and refine. |
| Verifier judgement | Partial | Yes | Verifier plus harness evidence classifiers/gates | Verifier | `verify.py` parses report, classifies evidence strength/provenance, adds uncovered constraint gaps, and may mark unresolved. `completion.py` can add pre-verifier gate reports. | Verifier owns readiness judgement. Harness may parse/normalize and enforce runtime invariants, but should not add task-specific verdicts. | Audit and demote hard gate logic. |
| Completion gate | Yes | Yes | Shared harness/verifier | Verifier plus thin runtime floor | `harness/aether2/control/completion.py` builds proof state, warnings, task_done warning, evidence gate reports. `aether_next/completion.py` has multi-blocker gate. | "Done" means verifier says complete and generic runtime floor holds. No task-specific deterministic veto above verifier. | Rewrite/shrink. |
| Generic completion floor | Partial | Yes | Harness | Harness | Current proof state rejects weak/self-authored evidence and task-local helper proof. Useful but intertwined with readiness. | Keep only generic floors: output schema parses, required declared artifacts exist/non-empty, tool/verifier outputs parse, workspace contract holds. | Keep thin subset, delete the rest. |
| Deterministic checks | Yes | Yes | Solver/harness/completion | Verifier evidence | Aether-2 `task_done.checks` are replayed and fed to verifier. Aether-Next compiles visible smoke tests into checks and completion gate blockers. | Checks are evidence, not authority. They can inform verifier but not override verifier except generic runtime invariants. | Keep replay, demote veto. |
| Smoke-test library | Yes in Aether-Next | Prototype | Architect plus compiler | Harness generic primitives only | `aether_next/smoke_compile.py` compiles typed file/syntax/content/run fixture checks. | Keep tiny generic typed primitives only if they avoid benchmark specialization. Prefer verifier capabilities over a growing check catalog. | Shrink/avoid expansion. |
| Proof contract / task-family logic | Yes in Aether-Next; analogous requirement logic in Aether-2 | Yes | Harness | Verifier / Architect | `aether_next/proof_contract.py` contains task-family semantic findings. Aether-2 evidence classification has domain-ish service/process heuristics. | No task-family harness judgement. Architect/verifier handle task semantics. Harness only records and normalizes. | Delete/demote after verifier can inspect. |
| Automatic memory / query | Yes | Yes | Harness | Harness evidence store and context | `aether_next/automatic_memory.py` and `memory_query.py`; Aether-2 `query_evidence` searches receipts/tool outputs. Some repeat handling blocks actions. | Always surface prior evidence. Query is optional retrieval, not a ritual. Repeat guidance should not compensate for hidden outputs. | Keep retrieval, shrink enforcement. |
| No-progress / repeat enforcement | Yes | Yes | Harness | Last-resort runtime guard | Aether-2 blocks blind repeat of same failed command. Aether-Next has stronger no-progress controller and automatic-memory messages. | Prefer model-visible evidence and verifier feedback. Keep only generic blind-loop safety rails with audit evidence. | Shrink after context fix. |
| Reconfiguration | Yes in Aether-Next; not central in Aether-2 | Prototype | Solver/completion/harness | Architect init; verifier may recommend future redesign | Aether-Next solver can request reconfigure, parse failure maps to reconfigure, completion gate can recommend. Reconfig may use old IR path. | No solver-frustration reconfig. Architect failure is initialization failure. Environment mismatch can abort/retry init. Verifier can classify workbench mismatch for next run. | Delete/rewrite. |
| Substrate executor | Yes | Yes | Harness | Harness | Aether-2 `ContainerExecutor`, Harbor backend, jobs/sessions, workspace snapshots. Aether-Next `SubprocessExecutor`/Docker runner. | Certified runs use benchmark-native Linux/container workspace contract. Substrate failures are fixed and reported separately from model capability. | Keep/harden. |
| Docker / Harbor runtime | Yes | Yes | Harness | Harness | `harness/aether2/runtime/bridge_harbor.py`, `harbor_backend.py`, executor, row isolation, VM scripts. Official grader reward is attached post-run. | On-demand eval backend, clean lifecycle, grader external after agent. | Keep and audit lifecycle. |
| Workspace / sandbox contract | Yes | Yes | Harness | Harness | Aether-2 has task spec, executor, permissions, workspace snapshots. Eval-first AGENTS requires certified Linux/container conditions. | Canonical cwd/root/Python/artifact contract for certified evals. | Keep/harden. |
| Artifact capture / inspection | Yes | Yes | Harness | Harness | Aether-2 captures deltas, artifact registry, `inspect_artifact`, receipt artifact observations. | Generic artifact capture and inspection; verifier may inspect artifacts read-only. | Keep. |
| Receipts | Yes | Yes | Harness / Ledger | Ledger substrate | Aether-2 has `ReceiptWriter` and `QueryableReceiptStore`; Aether-Next has `ExecutionLedger` receipts. | Every run records model exchanges, tool invocations, verifier probes, outcomes, and evidence refs. | Keep/consolidate. |
| Traces / decision traces | Yes | Yes | Harness / Ledger | Ledger substrate | Aether-2 records model exchanges, reasoning trace steps, envelopes, decision bundles, failure cards. Aether-Next has `RunTrace`. | Durable audit trail for eval evidence and trace-diff workbench. | Keep/consolidate. |
| Evidence ledger | Yes | Yes | Shared harness/verifier | Ledger records; verifier judges | Aether-2 evidence ledger tracks requirements, provenance, blockers, terminal claims. Some functions classify and block readiness. | Ledger stores evidence and unresolved findings. It does not independently decide semantic completion. | Keep data model, shrink judgement. |
| Mirror / semantic tracker | Yes | Yes | Harness | Harness last-resort feedback | Aether-2 `Mirror` observes repeated signatures, facts, unused affordances, and notes. | Model-visible reflection only. No task-specific solving or hidden task inference. | Keep only generic reflection. |
| Model routing / client | Yes | Yes | Harness | Harness | Aether-2 model routes support Azure/OpenAI-compatible calls, pacing, response normalization. Aether-Next has model hooks/providers. | Stable routing, pacing, usage accounting, prompt caching hints. | Keep. |
| Prompt caching | Yes | Yes | Harness | Harness mechanics | Aether-2 passes `cache_prefix_len=context.prefix.token_estimate`; Aether-Next relies on stable sections but has ordering issue with static solver prompt. | Stable prefix is truly stable and includes architect prompts and mechanical contract. Per-step context is uncached tail. | Keep/fix ordering. |
| Official grader boundary | Yes | Mostly | Harness/eval backend | Official grader external | Aether-2 Harbor attaches grader reward after loop. `docs/HARNESS_VISION.md` says grader external. Static prompt still says "grader decides." | Grader evaluates after agent termination and never influences solver/verifier loop. | Keep boundary, fix wording. |
| Eval substrate / result rows | Yes | Yes | Measurement plane | Eval substrate, not agent | `runner/eval_substrate_*`, adapters, scoreboards, route schemas, and eval suite exist. | Promotion authority comes from benchmark-grade eval evidence, not trace prose or internal gates. | Keep/build separately from agent internals. |
| Research ledger | Yes | Yes | Historian / ledger agent | Historian | `tracking/ledger/` receives raw updates via recorder. | Material architecture/experiment changes persist as raw ledger updates. | Keep process. |
| Multi-agent handoff | Yes | Yes for collaboration | Orchestrator/workers | Orchestrator/workers | `harness/aether2/agents/` and AGENTS governance define worker packets and handoffs. | Outside inner benchmark agent unless explicitly running governed collaboration. | Keep separate from agent loop. |

## Desired Ownership Boundary

Architect owns:

- solver system prompt, as the substantive system prompt;
- verifier system prompt;
- success definition;
- evidence priorities;
- false-positive traps;
- verifier feedback style;
- context preservation priorities;
- compression strategy within harness-supplied model window;
- verifier capability focus within a generic read-only capability set;
- local verification limits as model-visible caveats.

Harness owns:

- executor, Docker/Harbor runtime, workspace, and cwd/root contract;
- tool APIs, schemas, routing, permissions, hooks, and read-only verifier sandbox;
- model routing, TPM pacing, usage accounting, and prompt caching mechanics;
- context assembly and invariant context sections;
- compaction mechanics and receipt continuity;
- receipts, traces, artifact capture, and result-row plumbing;
- runtime invariants and failure surfacing.

Solver owns:

- inspection strategy;
- file edits;
- command execution;
- artifact production;
- deciding when to make a completion claim.

Verifier owns:

- independent task-state judgement;
- read-only inspection/probing;
- repair feedback;
- completion verdict.

Official grader owns:

- benchmark measurement after agent termination.

Ledger owns:

- durable evidence, receipts, handoffs, and research memory.

## Context Ownership Boundary

Invariant harness-owned context:

- recent tool outputs;
- command/read/write/check receipts;
- active verifier findings;
- verifier probe outputs;
- schema/tool errors;
- workspace/process state;
- artifact registry;
- environment/cwd/runtime facts;
- receipt continuity after compaction.

Architect-owned context policy:

- what evidence categories matter most;
- preservation priorities;
- compression/deprioritization preferences;
- retrieval policy;
- verifier feedback style.

Never optional:

- recent tool outputs visible to the solver;
- enough receipt/probe evidence for the verifier to judge;
- compaction must not erase required evidence;
- hidden grader information must never enter the agent loop.

## Verifier Architecture Decision

Target verifier architecture: bounded read-only verifier agent.

The verifier should run under a small budget, initially no more than three
verification rounds. Within a round, it may request read-only capability calls
such as reading files, running conservative inspection commands, checking job
status, or reading sessions. It then returns a structured judgement.

This is not a second solver:

- no writes;
- no package installs;
- no service mutation;
- no broad shell freedom;
- no task repair;
- no official grader access.

Current `harness/aether2` already has the right seed:

- `harness/aether2/control/verification_context.py` exposes read-only verifier
  capabilities and records attempts.
- `harness/aether2/runtime/verify.py` provides verifier tool schemas and
  supports one inspection tool-call turn.
- `harness/aether2/control/verification_rounds.py` can run bounded verification
  rounds.

The main target change is ownership: the architect should author the verifier
prompt and capability focus, while the verifier becomes the sole semantic judge.
Harness evidence classifiers must be audited so they normalize and record
evidence rather than becoming hidden completion authority.

## Architect Failure Policy

Current facts:

- `aether_next_build/aether_next/workbench_hooks.py` gives WorkbenchArchitect one
  repair retry after parse failure.
- `harness/aether2/runtime/adaptive_profile.py` gives AHP JSON/schema repair
  attempts.
- `aether_next_build/aether_next/kernel_config.py` currently falls back to
  baseline after WorkbenchArchitect failure while surfacing
  `workbench_architect_configure_failed`.

Target policy:

- one automatic retry is allowed for malformed JSON or schema-invalid config;
- if retry fails, this is `agent_initialization_failure`;
- this is not a task result and not a model capability score row;
- debug fallback may exist only if explicitly labeled debug-only;
- certified runs must not silently continue on a baseline-shaped config.

Open semantic-quality question:

How do we know a parseable config is weak, and who may judge that? The current
answer should remain conservative: do not add semantic config retries until an
eval-backed architect-quality gate exists. Offline quality audits may inform
future work, but they should not become hidden harness judgement.

## Slice 0 Acceptance Principles

Every future slice must:

- remove complexity where possible;
- preserve runtime invariants;
- never add benchmark-specific logic;
- never introduce silent fallback;
- delete redundant code after replacement;
- improve better-model-to-better-system scaling;
- preserve official grader separation;
- preserve architect ownership of task-specific behavior;
- reduce harness judgement;
- record what changed and why in evidence/ledger artifacts.

## Grey Areas To Resolve Before Build Planning

1. Integration target: whether the target codebase is direct modification of
   `harness/aether2`, selective porting from `aether_next_build/aether_next`, or
   another staged merge path.

2. Architect surface: whether AHP is renamed/evolved into Architect or replaced
   by WorkbenchArchitect-style HarnessConfigIR.

3. Semantic architect review: who can judge weak-but-parseable configs, and what
   evidence makes that judgement safe.

4. Completion floor: exact minimum generic floor. Recommended start: required
   declared artifacts exist/non-empty, schema/parsing invariants hold, verifier
   verdict parses, and workspace contract holds.

5. Verifier capability policy: how much the architect can narrow verifier
   capabilities without creating fake tool-policy knobs.

6. Evidence classifiers: which current Aether-2 evidence/provenance heuristics
   are runtime normalization versus hidden readiness judgement.

7. No-progress controls: which guards remain after recent tool outputs and
   receipt continuity are guaranteed.

8. Public prompt wording: update "grader decides" to "grader evaluates" without
   weakening the trace/ledger/grader separation.

9. Certified run behavior: how `agent_initialization_failure` is represented in
   result rows without counting as a task attempt.

10. Deletion order: which old/duplicate Aether-Next paths can be retired only
    after Aether-2 has equivalent tested behavior.

## Recommended Pre-Plan Conclusion

The architecture is ready for build planning only after the integration target
is chosen and the grey areas above are answered or explicitly deferred.

The build plan should not be a feature expansion. It should be a governed
carve-down:

1. preserve substrate;
2. make the architect the only task-specific workbench designer;
3. make the verifier the only semantic completion judge;
4. keep the grader external;
5. make recent evidence impossible to lose;
6. delete duplicate judgement machinery once replaced.

