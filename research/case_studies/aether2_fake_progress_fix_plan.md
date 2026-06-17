# Aether-2 Implementation Fix Plan

Date: 2026-06-14

Status: preregistered implementation plan; no mechanisms implemented in this plan

Source diagnosis:
- `tracking/collab/aether2_fake_progress_analysis_20260614/older_vm_and_trace_rerun_fake_progress_analysis_20260614.md`
- Older VM pull: `tracking/collab/vm_pulls/tracking/collab/tbench2_invalid64_envfixed_lean_20260614T192349Z`
- Trace reruns: `/private/tmp/aether2_trace_reruns/`

## Objective

Make Aether-2 consistently reward requirement-grounded engineering progress instead of model-authored activity, proxy checks, or plausible completion packets, while upgrading the rest of the harness surfaces needed for reliable TerminalBench work:

- model input and task-contract projection;
- orientation and EnvContract;
- tool execution and receipts;
- evidence ledger and progress classification;
- semantic no-progress detection;
- completion/status semantics;
- verifier and evidence-strength classification;
- blocker persistence;
- service, job, session, VM, and long-build monitoring;
- compaction;
- trace and decision instrumentation;
- runner/container/grader boundary;
- scheduling and resource handling;
- model routing and cost controls.

## Non-Goals and Guardrails

- Do not add task names or benchmark vocabulary to `runner/aether2/`.
- Do not create task-specific solve packs or hidden solution hints.
- Do not add harness-side planning, action rewriting, phase gates, or a hard completion veto.
- Keep `task_done` model-callable. Improve the claim format, context, evidence reflection, and verifier response rather than blocking the action.
- Treat public benchmark rows as calibration and audit surfaces. Implement and optimize against generic custom homolog evals.
- Do not promote from trace interpretation alone. Promotion requires fresh scored runs.
- Run `tools/aether2_genericity_check.py` for every `runner/aether2/` change.

## Baseline Facts

The older VM pull produced:
- 35 rows total;
- 15 scoreable;
- 7 pass and 8 fail;
- 5 scoreable `verifier_clean=true` / grader-fail disagreements;
- 66.7% scoreable verifier/grader agreement;
- 58.3% clean precision.

The live code explains several mechanisms:

1. `record_observation_evidence()` changes an unproven requirement to partial and adds weak evidence for any successful tool step with an artifact path or note.
2. `_ledger_progress()` treats a new evidence reference as stronger evidence even when the new reference is only an output write or status note.
3. `SemanticObservation.has_meaningful_artifact_change` treats any artifact change as meaningful by default, resetting semantic no-progress detection.
4. Tool observations are attached to `_primary_requirement()`, usually the first unresolved line extracted from the instruction, rather than a requirement selected by evidence relevance.
5. `_extract_stated_requirements()` is line-oriented and can turn prose, headings, context, and constraints into noisy or incomplete requirement entries.
6. `task_done` asks the model to supply its own checks, and replay success is not evidence independence.
7. The verifier computes `evidence_strength`, but `DiscrepancyReport.has_discrepancies` considers only verdict/unresolved state. A satisfied requirement with weak evidence can therefore produce `verifier_clean=true`.
8. Repair model exchanges are saved, but repair rounds are not represented as first-class steps in `reasoning_trace.json`.
9. The decision-trace bundler failed to parse the recent trace-enabled reruns and emitted empty event timelines.
10. EnvContract contains useful fields but leaves several operationally decisive facts unknown, including artifact root, install scope, lifecycle ownership, network constraints, process persistence model, and grader-visible paths.

## Success Metrics

Primary outcome metrics:

| Metric | Baseline | Local promotion target |
|---|---:|---:|
| Official grader pass rate on 13-task diagnostic board | establish frozen baseline | improve by at least 3 task passes with no control regression |
| Scoreable false-clean count | 5 / 8 failures in older pull | zero on custom homolog board; at most one on public diagnostic board |
| Verifier/grader agreement | 66.7% older pull | at least 90% on valid diagnostic rows |
| Clean precision | 58.3% older pull | at least 90% on valid diagnostic rows |
| Premature `task_done` before independent evidence | establish from trace baseline | reduce by at least 60% |
| Self-authored/circular evidence accepted as strong | establish from trace baseline | zero accepted as strong without another evidence source |
| Repeated semantic no-progress steps | establish per task | reduce by at least 30% without lowering pass rate |
| Invalid run rate | 20 / 35 older pull, mixed causes | no regression; environment/provider/resource invalids separated from capability |
| Median model calls and tool calls | establish per board | no more than 20% increase unless pass gain justifies it |

Secondary metrics:
- time to first requirement-grounded evidence;
- fraction of steps classified as evidence-producing, setup, redundant, harmful, or no-progress;
- blocked-status truthfulness;
- active blocker age and relevant-evidence resolution rate;
- service evidence completeness;
- EnvContract unknown-field count;
- compaction fact-loss rate;
- repair-round trace coverage;
- decision-trace parse success.

## Eval Substrate Before Mechanisms

### Public Diagnostic Board

Use the staged 13-task board in `TARGETED_BOARD.md`. These are calibration rows, not the private optimization loop.

### Generic Custom Homologs

Create benchmark-grade custom evals before implementing corresponding mechanisms:

1. Candidate-label extraction homolog:
   - input contains a plausible metadata label and a different value encoded in underlying structure;
   - grader checks the structural value;
   - red herrings and realistic paths required.

2. Circular recovery homolog:
   - partial records are visible through a naive method;
   - complete recovery requires an independent structure-aware method;
   - grader scores completeness.

3. Constraint-preserving edit homolog:
   - visible symptom can be fixed by destructive rewriting;
   - grader checks both symptom and allowed-diff invariant.

4. Semantic matrix/artifact homolog:
   - right-shaped output is easy;
   - semantic equivalence is the actual target.

5. External service protocol homolog:
   - self-authored client can pass against a wrong protocol;
   - grader uses a separately generated compatible client.

6. Final-state/filesystem homolog:
   - requested artifact works;
   - extra helper artifacts or wrong install path cause failure.

7. Exact serialization homolog:
   - shape and values are plausible;
   - exact schema/type representation matters.

8. Environment-map homolog:
   - host and task paths differ;
   - one dependency is present under a non-default executable/version;
   - one install root is writable and another is not;
   - grader runs from a fresh process.

9. Long-job/service survival homolog:
   - process binds then crashes or is replaced;
   - correct behavior requires bounded survival and stateful client validation.

Each homolog requires:
- deterministic fixture and grader;
- known-good ceiling implementation;
- known-bad case that reproduces the target failure;
- contamination check;
- baseline run with current Aether-2;
- immutable result rows and trace bundle;
- replay checkpoint near the first decisive pivot where feasible.

## Workstream 0: Instrumentation Reliability

Implement first because every later keep/kill decision depends on trustworthy traces.

### W0.1 Repair Decision-Trace Parsing

Owner:
- `tools/aether2_decision_trace.py`
- `tests/test_aether2_decision_trace.py`

Change:
- Parse `reasoning_trace.json` steps directly into decision events.
- Follow `model_exchange_ref` and tool receipt references.
- Emit explicit parse issues with receipt path and schema mismatch.
- Fail the diagnostic bundle when a referenced reasoning trace yields zero events.

Tests:
- Use the trace schema emitted by current `runner/aether2/loop.py`.
- Fixture with normal, `task_done`, verifier, repair, closing, and compaction calls.
- Regression for recent `event_count=0`, `parse_issue_count=4`.

Acceptance:
- 100% event extraction from all five existing local reruns.

Risk:
- Technical drift between old and new receipt formats. Support versioned parsers rather than heuristics that silently guess.

### W0.2 First-Class Repair-Round Trace Steps

Owner:
- `runner/aether2/loop.py`
- `runner/aether2/receipts.py`
- `tests/test_aether2_loop.py`

Change:
- Append a reasoning-trace step for each verifier repair call.
- Link request input, response, tool calls, observation receipts, pre/post ledger, blocker state, and subsequent completion claim.
- Preserve `call_role="repair"` and verification round index.

Tests:
- Failed first `task_done`, repair action, second `task_done`.
- Repair without tool call.
- Suppressed verifier retry with unchanged blockers.

Acceptance:
- Every model call has exactly one discoverable model-exchange receipt and one trace event or explicit non-step role.

Risk:
- Trace growth. Keep raw receipts complete and summaries bounded.

### W0.3 Per-Step Input and State Digests

Owner:
- `runner/aether2/loop.py`
- `runner/aether2/context.py`
- `runner/aether2/receipts.py`

Change:
- Record immutable prefix digest, task-instruction digest, orientation digest, tool-schema digest, tail digest, completion-contract digest, and compaction generation.
- Record exact model-visible unresolved requirements and next-required evidence per step.

Tests:
- Input digest changes only when its corresponding surface changes.
- Compaction preserves task/orientation identity while changing generation.

Acceptance:
- Trace diff can identify what changed between any two adjacent model calls.

Risk:
- Avoid duplicating full prompt content in summaries; raw model exchange remains canonical.

## Workstream 1: Task Contract and Model Input

### W1.1 Requirement Projection v2

Owner:
- `runner/aether2/loop.py`
- `runner/aether2/context.py`
- `tests/test_aether2_context.py`
- `tests/test_aether2_loop.py`

Problem:
- Current line-based extraction is noisy and evidence is attached to the first unresolved line.

Change:
- Preserve official task instruction verbatim as immutable authority.
- Create a compact generic contract projection that distinguishes:
  - requested outcome;
  - required artifact/path;
  - behavioral checks;
  - constraints and forbidden side effects;
  - environment or persistence requirements;
  - unknowns.
- Begin conservatively: deterministic syntactic extraction plus an umbrella requirement for the full task contract.
- Never infer hidden grader facts.
- Attach observations to the best matching requirement using visible path/command/relevance facts; use an explicit `unassigned_activity` bucket when relevance is unclear.

Tests:
- Multiline prose, numbered lists, headings, negative constraints, path requirements, service requirements, and single-sentence tasks.
- `overfull-hbox`-style instruction yields both behavior and allowed-edit constraints.
- `polyglot-c-py`-style instruction preserves final-directory-state constraint.
- Genericity test contains no task identifiers.

Acceptance:
- Human audit of custom homolog contracts shows all decisive visible requirements and no invented ones.

Risk:
- Over-extraction can add noise. The full verbatim task remains authoritative.

Expected score impact:
- +0 to +2 board tasks alone; larger interaction benefit with evidence and verifier work.

### W1.2 Model-Visible Evidence Question

Owner:
- `runner/aether2/prompts.py`
- `runner/aether2/loop.py`

Change:
- Replace generic completion repetition with a concise per-turn question derived from visible state:
  - what requirement is unresolved;
  - what evidence currently exists;
  - whether that evidence was generated by the same method/artifact;
  - what independent or externally observable evidence is still missing.
- Keep `task_done` available.
- Make the tool description explicit that reading a just-written deliverable proves contents/existence only, not task semantics.

Tests:
- Snapshot tests for candidate-label, circular-check, service-self-client, wrong-path, and blocker-status states.
- Prompt genericity check.

Acceptance:
- Model input immediately before premature completion visibly distinguishes candidate/proxy evidence from requested behavior.

Risk:
- Prompt verbosity. Keep the dynamic surface bounded and structured.

Expected score impact:
- +1 to +3 tasks, especially candidate lock-in and completion ritual cases.

## Workstream 2: Evidence Ledger and Provenance

### W2.1 Separate Activity From Evidence

Owner:
- `runner/aether2/delta.py`
- `runner/aether2/loop.py`
- `tests/test_aether2_delta.py`
- `tests/test_aether2_loop.py`

Problem:
- Successful writes and generic notes automatically become weak evidence and progress.

Change:
- Add distinct `activity_refs` and `evidence_refs`.
- A write, successful command, process start, or `task_done` claim is activity by default.
- Promote activity into requirement evidence only when a check/observation has an explicit visible relationship to a requirement.
- Do not mark a requirement partial merely because its output file changed.
- `task_done` itself never adds completion evidence.

Tests:
- Writing `UNRESOLVED` to an output file records activity but no requirement advancement.
- Writing a requested file records artifact activity; parsing or executing it records separate evidence.
- A successful irrelevant command does not advance a requirement.

Acceptance:
- Missing-file `gcode-to-text` trace would classify output write and `task_done` as no semantic progress.

Risk:
- Under-crediting legitimate file-generation tasks. File content inspection and task-specified format checks must still become evidence.

Expected score impact:
- +1 to +3 tasks; strong reduction in fake-progress metrics.

### W2.2 Evidence Provenance and Independence

Owner:
- `runner/aether2/delta.py`
- `runner/aether2/verify.py`
- `runner/aether2/receipts.py`

Change:
- Add provenance metadata:
  - `task_supplied`;
  - `external_tool_observation`;
  - `model_authored_artifact`;
  - `model_authored_check`;
  - `same_method_check`;
  - `fresh_process`;
  - `fresh_client`;
  - `task_environment`;
  - `unknown`.
- Record construction/check dependency facts without pretending to solve semantic equivalence.
- Surface provenance to the verifier and trace analyzer.

Tests:
- `cat` of a just-written file is model-authored readback.
- Re-running the same extraction method is same-method evidence.
- Official/provided tests are task-supplied.
- Fresh process importing installed artifact is distinct from source-tree process.
- Self-authored service client is distinguished from task/provided client.

Acceptance:
- Circular and self-client evidence cannot be classified as independent strong evidence without another source.

Risk:
- Provenance inference can be wrong. Prefer `unknown` over confident guesses.

Expected score impact:
- +1 to +3 tasks through verifier and model-input interactions.

### W2.3 Evidence Versioning and Relevance

Owner:
- `runner/aether2/delta.py`

Change:
- Evidence versions include requirement id, provenance, artifact hashes, command fingerprint, environment boundary, and result digest.
- Blocker candidate resolution requires a new relevant evidence version, not any artifact path change.

Tests:
- Unrelated file edit does not resolve blocker.
- Same check with unchanged inputs does not create a new relevant version.
- Fresh check after a real artifact hash change does.

Acceptance:
- Repeated completion packets cannot age out blockers through unrelated activity.

Risk:
- Hash churn from generated files. Normalize volatile paths and timestamps.

## Workstream 3: Semantic No-Progress and Strategy Control

### W3.1 Requirement-State Progress

Owner:
- `runner/aether2/mirror.py`
- `runner/aether2/loop.py`
- `tests/test_aether2_mirror.py`

Change:
- Remove `bool(artifact_paths)` as automatic meaningful progress.
- Reset no-progress only for:
  - changed failure class with useful diagnostic information;
  - requirement evidence with a new relevant version;
  - resolved uncertainty about environment/substrate;
  - legitimate bounded polling;
  - a real artifact change tied to a requirement and followed by validation.
- Track repeated successful-but-irrelevant commands.

Tests:
- Repeated output rewrites do not reset no-progress.
- Repeated same-method checks trigger semantic no-progress.
- Long build log growth remains legitimate polling.
- New environment diagnosis resets the repeated strategy counter.

Acceptance:
- `code-from-image`-style repeated heredoc actions trigger by the third same-family no-progress attempt.

Risk:
- False no-progress on incremental implementation. Use evidence version and artifact relationship, not command-family identity alone.

Expected score impact:
- 0 to +2 tasks directly; 15-35% step reduction expected on looping failures.

### W3.2 Strategy-Change Telemetry

Owner:
- `runner/aether2/mirror.py`
- `runner/aether2/metrics.py`

Change:
- Record whether the next action after a no-progress note changed:
  - action family;
  - target;
  - hypothesis/failure class;
  - evidence question.
- This remains telemetry, not action control.

Tests:
- Same command with altered whitespace is not a strategy change.
- Different diagnostic against the same target is a strategy change.

Acceptance:
- Every no-progress intervention has a measurable behavioral response.

## Workstream 4: Completion and Blocked Status

### W4.1 Structured Completion Claim

Owner:
- `runner/aether2/tools.py`
- `runner/aether2/loop.py`
- `tests/test_aether2_tools.py`
- `tests/test_aether2_loop.py`

Change:
- Extend `task_done` with a bounded requirement-evidence mapping:
  - requirement text/id;
  - check command or observation ref;
  - claimed boundary;
  - known limitations.
- Keep the action callable and do not reject it before verification.
- Record missing mappings as weak claim structure for the verifier.

Tests:
- Legacy-compatible parsing if migration requires it.
- Claim with only `cat out.txt` is explicitly model-authored readback.
- Claim can admit a limitation without converting it into success.

Acceptance:
- Verifier receives a structured claim instead of inferring requirement coverage from prose.

Risk:
- More complex tool schema may reduce tool-call reliability. Measure BFCL sentinel and schema error rate.

Expected score impact:
- +0 to +2 tasks; main value is verifier precision.

### W4.2 Explicit Blocked/Unresolved Terminal Affordance

Owner:
- `runner/aether2/tools.py`
- `runner/aether2/loop.py`
- result-row schema/runner adapter

Change:
- Add a generic `task_blocked` or `report_unresolved` terminal claim with:
  - blocker;
  - evidence;
  - attempts;
  - missing external state;
  - recommended next evidence.
- This is not a completion veto; it gives the model an honest alternative to writing blocker text into the deliverable or abusing `task_done`.
- Emit truthful `blocked`/`unresolved` finalization distinct from pass/fail/invalid.

Tests:
- Missing input file produces blocked status without modifying required output.
- Missing dependency/network/permission/path/build-running reasons remain distinct.

Acceptance:
- Blocker-string completion disappears from the blocked homolog.

Risk:
- Model may overuse blocked status. Prompt should require visible blocker evidence and bounded attempts.

Expected score impact:
- Small direct pass impact; high truthfulness and efficiency impact.

## Workstream 5: Verifier and Blocker Ledger

### W5.1 Evidence Strength Affects `verifier_clean`

Owner:
- `runner/aether2/verify.py`
- `runner/aether2/loop.py`
- `tests/test_aether2_verify.py`
- `tests/test_aether2_loop.py`

Problem:
- Satisfied + weak evidence currently counts as clean.

Change:
- Add a verification-quality outcome distinct from the model verifier verdict:
  - `supported`;
  - `weakly_supported`;
  - `unsupported`;
  - `contradicted`.
- `verifier_clean=true` requires every requirement to be satisfied with strong support, or moderate/mixed support with no dominant weak reason and an independent evidence source.
- Weak satisfied findings become unresolved reflection and request stronger evidence.
- Keep official grader authoritative.

Tests:
- Existence/readback-only satisfied claim is not clean.
- Shape-only semantic claim is not clean.
- Provided full test with no environment hack can be clean.
- Service evidence requires survival plus external response/state validation.
- Unsatisfied evidence remains strong evidence of failure.

Acceptance:
- All five older scoreable false-clean patterns are rejected by generic fixtures.
- No regression on clean verifier fixtures.

Risk:
- Over-strict verifier causes extra repair rounds. Bound rounds and measure cost.

Expected score impact:
- +1 to +4 tasks through repair; clean precision target above 90%.

### W5.2 Constraint and Final-State Coverage

Owner:
- `runner/aether2/verify.py`
- verifier prompt and inspection context

Change:
- Require requirement enumeration to include:
  - positive behavior;
  - negative constraints;
  - path/install/final-state requirements;
  - side-effect constraints;
  - persistence/service requirements.
- Add read-only final directory inventory and targeted diff inspection where relevant.

Tests:
- Allowed-edit invariant.
- Extra helper binary.
- Wrong install path.
- Exact serialized type.

Acceptance:
- Generic homologs for constraint, side-effect, path, and schema all produce unresolved verifier findings before grader.

Risk:
- Verifier may invent constraints. It must cite exact task text or visible contract projection.

### W5.3 Persistent Blockers With Provenance-Aware Resolution

Owner:
- `runner/aether2/delta.py`
- `runner/aether2/loop.py`

Change:
- A blocker records rejected evidence provenance and required evidence class.
- Candidate resolution requires new evidence matching the required class.
- Exhausted blockers remain visible through compaction and final result.

Tests:
- A browser-execution blocker cannot be resolved by another string grep.
- An external-client blocker cannot be resolved by the same self-client.
- A final-path blocker cannot be resolved by editing a nested path.

Acceptance:
- Repeated `task_done` without the requested evidence class suppresses redundant verifier calls and remains unclean.

Risk:
- Evidence-class vocabulary must remain generic and small.

## Workstream 6: EnvContract and Environment Mapping

### W6.1 EnvContract v2 Coverage

Owner:
- `runner/aether2/orientation.py`
- `tests/test_aether2_orientation.py`

Change:
- Add or strengthen:
  - OS distribution/version;
  - kernel and architecture;
  - shell executable and semantics;
  - Python executable/path/version, active virtual environment, site paths;
  - R executable/version/library paths;
  - compiler/build tool versions;
  - package-manager availability and install scopes;
  - DNS, TCP, and HTTPS network probes as separate facts;
  - effective user/group/capabilities;
  - writable and executable roots;
  - mount/filesystem and host-to-task path mapping;
  - process namespace and persistence ownership;
  - listener ownership snapshot;
  - task-visible tests and explicitly unknown grader-only boundary;
  - artifact/install root when supplied by runner configuration.
- Keep unknown facts honestly unknown.

Tests:
- Docker path translation.
- Missing Python but present Python 3.
- R present/missing.
- Network DNS succeeds but TCP fails.
- Writable workspace but non-writable system prefix.
- Listener visible but owner unavailable.

Acceptance:
- Environment-map homolog can plan without guessing OS, arch, executable, path mapping, network, permissions, or writable install scope.

Risk:
- Orientation latency and probe side effects. Keep probes bounded, read-only, and cached.

Expected score impact:
- +1 to +3 environment/build tasks; lower invalid/path-confusion rate.

### W6.2 Environment Failure Taxonomy

Owner:
- `runner/aether2/envelope.py`
- `runner/aether2/executor.py`
- `runner/aether2/loop.py`

Change:
- Distinguish:
  - missing executable/dependency;
  - wrong version;
  - network DNS/TCP/TLS unavailable;
  - wrong cwd/path namespace;
  - permission denied/non-writable target;
  - build still running;
  - process terminated/resource killed;
  - provider failure;
  - grader failure.
- Surface the class in tool observations, ledger, result rows, and trace summaries.

Tests:
- One fixture per failure class with stable reason code.

Acceptance:
- No generic "command failed" classification when a decisive substrate reason is observable.

Risk:
- Shell output varies. Use exit codes, errno, backend metadata, and bounded patterns.

## Workstream 7: Service, VM, Job, Session, and Long-Build Monitoring

### W7.1 Attributable Listener and Process Evidence

Owner:
- `runner/aether2/jobs.py`
- `runner/aether2/sessions.py`
- `runner/aether2/orientation.py`
- service monitoring in `runner/aether2/loop.py`

Change:
- Associate listeners with PID, command, job/session id, container, cwd, and start time where visible.
- Distinguish pre-existing listener from model-launched listener.
- Record crash, restart, PID replacement, and exit status.

Tests:
- Port already occupied by unrelated process.
- Job binds then exits.
- Supervisor replaces child PID.
- Listener exists in host but not task container.

Acceptance:
- Service evidence never credits an unattributed port as the task service.

Risk:
- PID attribution differs by platform/container. Unknown is acceptable and must remain weak.

### W7.2 Bounded Survival and Stateful External Probe

Owner:
- service monitor in `runner/aether2/loop.py`
- `runner/aether2/verify.py`

Change:
- Capture two or more bounded observations when time permits:
  - liveness;
  - log growth/error tail;
  - listener ownership;
  - fresh client probe from task/grader-equivalent environment;
  - response/state validation;
  - crash/restart/replacement.
- Do not invent semantic probes. Record whether client evidence is task-supplied, model-authored, or unknown.

Tests:
- Self-client passes wrong protocol.
- External client fails wrong field/schema.
- Service survives first probe then crashes.
- State write/read across bounded interval.

Acceptance:
- `kv-store-grpc`-style self-authored protocol success remains weak.
- Long-lived service claims have survival plus semantic probe evidence.

Risk:
- Added latency. Use bounded windows based on remaining budget and task type evidence, not fixed long sleeps.

Expected score impact:
- +1 to +2 service tasks; fewer false-clean services.

### W7.3 Long Job and Build Completion Truth

Owner:
- `runner/aether2/jobs.py`
- `runner/aether2/loop.py`
- scheduling runner

Change:
- Preserve true exit code, complete log reference, last log growth time, and stalled/running/finished state.
- Do not treat log growth as build success.
- Distinguish timeout, resource kill, and still-running at finalization.

Tests:
- Build emits output then fails.
- Build stalls with no log growth.
- Detached build completes after normal command timeout.
- Resource-killed build reports invalid/resource rather than capability fail.

Acceptance:
- `compile-compcert` positive control remains pass.
- Resource-killed rows are classified truthfully.

Risk:
- Long-running tests consume resources. Scheduler serialization and cleanup are required.

## Workstream 8: Compaction

### W8.1 Decisive Fact Preservation

Owner:
- `runner/aether2/compactor.py`
- `tests/test_aether2_compactor.py`

Change:
- Preserve in deterministic ledger:
  - exact requirements and constraints;
  - evidence provenance/strength/version;
  - failed checks;
  - active/exhausted blockers;
  - disproven assumptions;
  - environment facts and unknowns used by the plan;
  - job/session/service identifiers and state;
  - next-required evidence;
  - prior candidate labels explicitly marked unverified.
- The model-written handoff is advisory; deterministic facts remain authoritative.

Tests:
- Candidate label remains unverified after compaction.
- Failed check and blocker survive multiple rebases.
- Service PID/job id and path mapping survive.
- No status upgrades occur during serialization.

Acceptance:
- Replay of pre/post-compaction model input shows no decisive fact loss.

Risk:
- Context growth. Cap history while preserving state, provenance, and blockers.

Expected score impact:
- 0 to +2 long tasks; reduced repeated rediscovery.

## Workstream 9: Runner, Container, Grader, and Scheduling

### W9.1 Grader-Boundary Contract

Owner:
- `tools/run_aether2_g3_official.py`
- `runner/aether2/bridge_harbor.py`
- grader isolation tooling/tests

Change:
- Surface only legitimate boundary facts:
  - fresh process/container expectations;
  - task workspace root;
  - install persistence expectations;
  - model-visible tests;
  - explicitly hidden grader details.
- Capture final environment manifest and artifact inventory used by grader.
- Diff model-visible final state against grader-visible state without exposing hidden answers.

Tests:
- Source-tree import succeeds but fresh installed import fails.
- Artifact exists in host path but not task path.
- Environment mutation affects local shell but not fresh grader process.

Acceptance:
- Build/install tasks receive enough legitimate boundary information to test fresh-process behavior.

Risk:
- Avoid leaking hidden test paths or answers.

### W9.2 Invalid-Run Attribution

Owner:
- official runner and result-row construction

Change:
- Separate launch, provider, environment, grader, timeout, resource, and capability outcomes.
- `verifier_clean` never overrides invalid attribution.
- Preserve subprocess/container exit, signal, disk/memory pressure, and grader launch evidence.

Tests:
- Provider exception.
- Docker build `137`.
- Missing runner import.
- Grader exit `127`.
- Model task failure with healthy runner.

Acceptance:
- Every invalid row has one primary and optional contributing reason codes with evidence refs.

### W9.3 Scheduler and Cleanup

Owner:
- tournament/official scheduling scripts

Change:
- Keep:
  - max three light containers;
  - one heavy build;
  - one QEMU/service-sensitive task;
  - disk/process preflight;
  - attributable cleanup only;
  - immutable per-attempt output directories.
- Add resource-watermark pause, job/container ownership registry, and bounded cleanup verification.

Tests:
- No cross-attempt port/state collision.
- Heavy build serialization.
- Cleanup does not kill unrelated processes.
- Low disk creates invalid/preflight result, not capability fail.

Acceptance:
- Diagnostic board completes without unexplained resource kills or cross-task contamination.

Risk:
- Lower throughput. Prefer trustworthy score rows over parallel invalid runs.

## Workstream 10: Model Routing and Cost

### W10.1 Evidence-Aware Escalation Experiment

Owner:
- model route configuration and metrics, not task-specific runner logic

Change:
- Test a generic escalation policy only after core mechanisms:
  - repeated semantic no-progress;
  - two verifier rounds with new relevant evidence but unresolved semantic gap;
  - high-difficulty environment/service/build class.
- Do not route by task name.

Tests:
- BFCL/tool schema sentinel.
- Easy file task remains on base route.
- Hard semantic task escalation is measurable.

Acceptance:
- Net score/cost improvement on shared board.

Risk:
- Cost increase and confounding. This is last, not first.

## Implementation Order

### Slice A: Measurement Foundation

Implement:
- W0.1 decision-trace parsing;
- W0.2 repair trace steps;
- W0.3 input/state digests;
- custom homolog fixtures and frozen baseline.

Exit:
- complete trace diff for every baseline run;
- no empty trace bundles;
- baseline and ceiling rows recorded.

### Slice B: Core Pre-Verifier Mechanism

Experiment independently:
- A1: W1.2 model-visible evidence question;
- A2: W2.1 activity/evidence separation;
- A3: W2.2 provenance;
- A4: W3.1 semantic no-progress.

Run:
- each alone;
- A1+A2;
- A2+A3;
- A1+A2+A3+A4.

Promote:
- only the smallest combination that reduces premature completion and improves target score without sentinel regression.

### Slice C: Completion and Verifier

Experiment:
- B1: W4.1 structured claim;
- B2: W4.2 blocked status;
- B3: W5.1 strength-aware clean;
- B4: W5.2 constraint/final-state coverage;
- B5: W5.3 blocker resolution.

Run:
- B1 alone;
- B3 alone;
- promoted Slice B + B1;
- promoted Slice B + B3;
- B1+B3;
- full promoted Slice B + smallest positive B combination.

### Slice D: Environment and Runtime

Experiment:
- C1: EnvContract v2;
- C2: environment failure taxonomy;
- C3: listener/process attribution;
- C4: bounded service monitor;
- C5: long-job truth.

Run:
- environment extension board;
- service extension board;
- build positive control;
- C1, C3+C4, and C1+C3+C4 separately.

### Slice E: Compaction and Runner

Implement/test:
- W8.1 fact preservation;
- W9.1 grader-boundary contract;
- W9.2 invalid attribution;
- W9.3 scheduler/cleanup.

Run:
- long-context homolog with forced compaction;
- build/install board;
- full 13-task local diagnostic board.

### Slice F: Model Routing

Only after Slices A-E are stable:
- W10.1 routing experiment;
- target + all sentinels;
- cost-normalized keep/kill.

## Interaction Matrix

| Experiment | Purpose |
|---|---|
| Contract input only | Does clearer model input reduce fake progress before ledger/verifier changes? |
| Activity/evidence split only | Does removing false progress improve behavior without prompt changes? |
| Provenance only | Can the verifier/model distinguish circular evidence? |
| No-progress only | Does repetition fall without harming incremental work? |
| Contract + activity/evidence | Tests whether input and state semantics reinforce each other |
| Activity/evidence + provenance | Tests whether semantic progress becomes measurable |
| Structured claim only | Measures tool-schema burden and claim coverage |
| Strength-aware verifier only | Measures false-clean repair benefit and extra cost |
| Pre-verifier bundle + verifier | Tests full fake-progress repair |
| EnvContract only | Measures planning and path/dependency improvements |
| Service monitor only | Measures external protocol/survival improvements |
| EnvContract + service monitor | Tests correct-environment probes and attribution |
| Full bundle | Final local promotion candidate |

## Regression Sentinels

Required on every promoted slice:
- `db-wal-recovery`: evidence-first semantic control.
- `compile-compcert`: long-build success control.
- `prove-plus-comm`: naturally externally checked control.
- `log-summary-date-ranges`: simple file/data task.
- BFCL/tool-call schema sentinel.
- simple TerminalBench-style verifier repair row.
- genericity check.
- blocked/missing-input truthfulness homolog.
- no-op/no-progress unit sentinel.
- invalid provider/environment attribution fixtures.

## Keep/Kill Rules

Keep a mechanism only if:
- target family improves on fresh end-to-end runs;
- no named sentinel regresses materially;
- false-clean count does not increase;
- invalid/contamination rate does not increase;
- median cost/steps stay within the preregistered bound or score gain justifies them;
- trace evidence confirms the intended behavior changed;
- code passes selected review gate.

Kill or revise if:
- score does not improve after two valid seeds;
- apparent gain comes only from verifier pessimism without more grader passes;
- blocked/implicit-stop rate rises without truthfulness benefit;
- simple tasks become materially slower;
- the mechanism relies on task names, benchmark vocabulary, or hidden assumptions;
- the prediction fails.

## Review Gate

Because this plan covers measurement-critical runner, verifier, environment, and scheduling code:

`codex_review_skill_plus_adversarial`

Each implementation slice must include:
- focused tests;
- genericity check;
- target and sentinels;
- code review;
- adversarial attempt to disprove the claimed mechanism effect;
- raw ledger handoff;
- coherent commit.

## Adversarial Plan Review

Material challenges and dispositions:

1. **A stricter verifier could improve agreement while reducing actual task completion.**
   - Accepted risk.
   - Mitigation: verifier precision is not a promotion result. Every verifier change must increase or preserve official grader passes, and verifier-only pessimism is a kill condition.

2. **Requirement projection could become prohibited harness-side planning.**
   - Accepted risk.
   - Mitigation: projection is descriptive instrumentation only, retains the verbatim task as authority, never chooses actions, and uses an `unassigned_activity` state rather than inventing requirement relationships.

3. **Evidence provenance classification could pretend to understand semantics it cannot know.**
   - Accepted risk.
   - Mitigation: record observable dependency facts and use `unknown` liberally. The harness must not claim that a check is independent merely because the command text differs.

4. **An explicit blocked tool could become an easy escape hatch.**
   - Accepted risk.
   - Mitigation: require blocker evidence and attempts in the claim, measure blocked overuse, and keep blocked rows distinct from passes and capability failures.

5. **The 13 public tasks could become benchmark-specific optimization.**
   - Rebutted by plan structure.
   - The public board is calibration only. Mechanisms require abstracted custom homolog baselines and ceiling checks before implementation and promotion.

6. **Splitting 13 tasks into 10+3 could introduce configuration drift.**
   - Accepted risk.
   - Mitigation: freeze one source revision, model route, prompt digest, environment image set, trace schema, and mechanism variant across both stages; report a combined board only when those digests match.

7. **Service monitoring could overclaim semantics or add large delays.**
   - Accepted risk.
   - Mitigation: monitoring records liveness, attribution, bounded survival, and probe provenance; it does not invent domain probes. Survival windows are bounded by remaining budget.

8. **EnvContract expansion could become noisy and expensive.**
   - Accepted risk.
   - Mitigation: bounded read-only probes, cached orientation, honest unknowns, and an explicit latency budget.

9. **Activity/evidence separation could suppress useful incremental progress.**
   - Accepted risk.
   - Mitigation: retain activity telemetry, promote requirement-related observations through explicit evidence versions, and use incremental implementation sentinels.

10. **The plan is broad enough to create a confounded mega-variant.**
    - Accepted risk.
    - Mitigation: slices and A/B interaction matrix are mandatory. No full bundle is implemented before isolated measurements identify positive mechanisms.

## Definition of Done

This implementation program is ready for a benchmark run only when:

1. The custom homolog board has baseline, ceiling, known-bad, contamination, and deterministic grader evidence.
2. The 13-task public diagnostic board has fresh local result rows and complete traces.
3. The promoted mechanism bundle improves grader passes and false-clean metrics.
4. Environment/service/long-job extension tasks are valid and attributable.
5. No regression sentinel materially worsens.
6. Decision traces cover all model calls, including repair and compaction.
7. The full bundle passes review and genericity checks.
8. The prediction, score movement, failures, and keep/kill decisions are recorded.
