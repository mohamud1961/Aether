# Local Vision Delta Current State Addendum — 2026-07-05

This addendum supersedes stale current-state claims elsewhere in this file for the local snapshot. It does not claim Docker/VM/model-backed certification.

## Locally implemented in this snapshot

- No-progress is advisory-only in the certified runtime. It records `no_progress_control` but no longer blocks dispatch or completion.
- Automatic memory strict modes are advisory-only in the certified runtime. Repeats can surface `automatic_memory_advisory`, but dispatch continues.
- Verifier parsing accepts plain JSON, fenced JSON, and prose-wrapped JSON objects while still failing closed on invalid/no-object output.
- `model_limit` classification is conservative: solver protocol errors, missing context handles, unsupported solver reconfiguration, reported blockers, verifier-missing receipts, context failures, unprobed-env indicators, timeout/substrate failures, and non-advisory no-progress receipts disqualify model-limit attribution.
- `run_command` accepts optional `timeout_s`; the kernel bounds it by generic task public budget metadata and records the effective timeout policy in the receipt.
- EnvMap ingests public `task.toml` metadata when supplied: category, difficulty, tags, agent/verifier/build timeouts, docker image/resources. These are task-surface facts, not hidden grader facts.
- EnvMap emits generic `capability_requirements` and `required_tool_hints` using task instructions, public metadata, and visible environment files. These are explicitly `inferred_not_fact`; they must never be presented as proven environment facts.
- Environment probing has a broader generic command/module surface for compiler, media, OCR/PDF, QEMU, service, binary/security, scientific, and ML tasks.
- A local static official-task capability audit script exists: `scripts/audit_official_task_capabilities.py`. It ignores `solution/` and `tests/` contents and uses official tasks only as a generic coverage corpus.

## Local deterministic evidence

- `pytest -q`: 290 passed, 10 skipped.
- Skipped tests still include Docker-dependent checks; local green does not prove container mount isolation or grader execution.
- Official task capability audit generated `OFFICIAL_TASK_CAPABILITY_AUDIT_LOCAL.csv` and `OFFICIAL_TASK_CAPABILITY_AUDIT_LOCAL.md` for 90 tasks.

## Still requires Docker/VM/model validation

- Real Docker proof that `/task` and `/tests` are absent during solver phase and copied only for grading.
- Official grader smoke after mount isolation.
- VM/model-backed sentinel runs.
- Actual measured pass rate or model-limit claims.

## Still open for future local work

- Sandboxed verifier overlay execution.
- Full service/media/QEMU verifier probes.
- True unlimited stdout/stderr capture beyond executor caps.
- Stable/volatile prompt-cache split beyond local invariants.
- Physical quarantine/removal of legacy reference code like `proof_contract.py` from production import reachability.

---

# Aether-Next Canonical Implementation Plan

> **Status:** Specification / source of truth. No code changes, no VM batch, no model-backed runs are authorized by this document itself.
> **Date:** 2026-07-04
> **Revision:** v1.2 (2026-07-04) — amended after owner review. Changes: verifier packet evidence hygiene is explicit: no `solver_claim`, `submit_summary`, or privileged solver-proof fields; solver commands/checks are labeled as `solver_authored_evidence`; `proof_contract_analysis` must be removed or quarantined outside verdict context; verifier inspection must prioritize raw files/artifacts/services/source inputs/independent reruns while keeping solver history only as audit trail. Prior v1.1 changes remain: P0-5 split into six narrow sub-commits; provenance test-mode carve-out (`provenance_mode`); raw-output secret redaction with logged byte ranges; `report_blocker` action schema defined; mount-isolation golden-grader smoke; proof_contract quarantined-not-physically-deleted; new invariant *Prompt cache stability*; new invariant *Repeats are not model failures until information availability is proven* (incl. the `query_memory` vs. retrieval-handle split). Every P0 item is one narrow patch — see the hard rule in §6.
> **Production target:** `aether_next_build/aether_next/` (canonical Aether-Next). `harness/aether2/` and `runner/aether2/` are reference only.
> **Source material:** the 2026-07-04 full root-cause audit and the second-pass target operating model. Every claim relied on here was checked against production code; file/line anchors are given where an implementer will need them. Where a claim is inferred rather than code-verified, it is marked *(inferred)*.

This is the engineering path from the current harness to a harness whose only limiter is the model. It is ordered: **P0 (evidence-trust) → P1 (vision alignment) → P2 (max capability) → promotion.** Implement P0 fully and in order before anything else. Do not re-litigate architecture inside an implementation task; if a decision here is wrong, amend this document first.

---

## 1. Executive summary

**What we are building.** A four-role agent harness — architect designs the workbench, solver does the work, verifier judges actual task state, official grader scores externally — where the substrate is robust and the judgment/config layer has zero silent fallbacks. The design already exists in production at roughly 70% fidelity; this plan closes the remaining 30% and removes the harness from the failure denominator.

**Why current Aether-Next is not yet model-limited.** Across the 13 audited task-runs, at most 2 failures were primarily model-capability. The rest were harness faults, each of which is a distinct, fixable defect:

- **Silent reconfigure loop.** After the 2-reconfiguration budget is spent, `request_reconfigure` turns fall through the kernel loop with **no receipt** ([kernel.py:270-279](aether_next_build/aether_next/kernel.py#L270)). train-fasttext burned 184/201 turns, configure-git-webserver 170/201, install-windows 199/201 this way. Their `model_limit` labels are false.
- **Context starvation.** Command stdout/stderr truncated to the first 1000 chars and file reads to a 500-char excerpt **at capture time** ([kernel.py:565](aether_next_build/aether_next/kernel.py#L565), [kernel.py:620](aether_next_build/aether_next/kernel.py#L620)), inside an ~8k-token packet ([runtime_ir.py:270](aether_next_build/aether_next/runtime_ir.py#L270)). sparql-university could never see its 10 KB graph file; the no-progress controller then hard-blocked the shell workaround.
- **Parse-failure step burn.** A strict single-JSON turn protocol fed by a provider that returns partial text on token exhaustion produced "Solver output could not be parsed" on 19/30 (filter-js) and 14/30 (sparql) steps; the raw failed output is discarded ([model_hooks.py:368-386](aether_next_build/aether_next/model_hooks.py#L368)).
- **Fabricated environment facts.** `network_scope="workspace_only"` is a hardcoded, unprobed default ([envmap_builder.py:235](aether_next_build/aether_next/envmap_builder.py#L235)); the architect then told the solver to report a tooling block instead of installing fastText.
- **Benchmark-integrity leak.** The runner bind-mounts the full task dir including `tests/` and `solution/` (89/95 tasks ship solutions) into the solver container for the whole run ([docker_runner.py:362-370](aether_next_build/aether_next/runners/docker_runner.py#L362)). Unexploited in traces, but every pass is challengeable until fixed.
- **Semantic crutch.** `proof_contract.py` has three task-family analyzers mirroring the stage-1 TB tasks; on filter-js it fabricated "missing preservation evidence" and misled the verifier.
- **Verifier underpowered.** Read-only inspection only → three false-cleans (zero inspections) and one false-reject (extract-elf: needs_repair 70+ times on a grader-passing state).
- **Provenance gap.** The VM code copy is not a git repo; the flagship batch ran code that no longer exists inspectably; manifests carry no code SHA.

**Target architecture.** `task_loaded → environment_probed → architect_config_requested → architect_config_validated → workbench_compiled → solver_loop → verifier_inspection → verifier_verdict → agent_terminal → official_grader → result_row → audit_classification`, governed by the invariants in §2, with a small universal context floor plus an architect-tuned recipe above it, a verifier-only single-shot reconfiguration path, and result rows that separate kernel/verifier/grader/audit truths.

**Fix before another real run (P0).** (1) Stop mounting `/task` and `/tests` during solving; (2) receipt for every solver signal, killing the silent loop; (3) neutralize solver-requested reconfiguration; (4) capture raw malformed solver output + one parse-feedback retry; (5) preserve full command/file outputs with paging handles and tail-biased truncation; (6) enforce the context floor; (7) probe network/tooling truthfully; (8) record code SHA + prompt/task hashes in every manifest. No VM batch until all pass.

**Do not work on yet.** Architect-layer redesign, new memory features, native tool calling, multi-pass verifier, the `aether/` consolidation rename, prompt-caching optimization, Stage-2 task expansion. None blocks P0/P1 (see §17).

---

## 2. Target invariants

```text
INVARIANT: No silent fallback (judgment/config layer)
WHY: A fallback that hides failure turns architect/config defects into fake task attempts.
CURRENT VIOLATION / RISK: _baseline_resolve / _workbench_resolve substitute compiler.guaranteed_default_ir() on fatal config; ModelHooks._safe_default_ir / _safe_fallback_turn produce "careful software engineer" config and a fabricated request_reconfigure turn (kernel_config.py:93,156,219,273; model_hooks.py:364,384,525).
FIX: Workbench path must terminate on unrepairable config (config_invalid already surfaces at kernel.py:128); remove default-IR substitution from the production workbench path; quarantine legacy IR/contract fallbacks behind an explicit --reference flag.
TEST: Fault-injection replay: malformed architect output → row status=architect_config_failure, no solver step receipts. Grep test: no guaranteed_default_ir / _safe_default_ir call reachable from the workbench run path.
```

```text
INVARIANT: No silent solver-signal loss
WHY: Ignored signals make the solver loop blind; 550+ wasted steps across 3 tasks.
CURRENT VIOLATION / RISK: request_reconfigure over budget falls through kernel.py:270-279 with no receipt; malformed turns produce a fabricated reconfigure turn, not a visible parse receipt.
FIX: Every turn kind × every harness decision (execute / deny / error / over-budget) emits a receipt that appears in the next context packet.
TEST: Kernel invariant test enumerating {act, submit_outcome, report_blocker, malformed} × {ok, denied, error} → assert a receipt exists and is present in the next compiled context.
```

```text
INVARIANT: No information destruction
WHY: Destroyed bytes cannot be recovered by any stronger model; made sparql unsolvable.
CURRENT VIOLATION / RISK: stdout[:1000], stderr[:1000], excerpt[:500] at capture (kernel.py:565,600,620); head-only truncation; trace observations strip payloads.
FIX: Store full bytes in the ledger payload; inline a tail-biased (head+tail) slice with a retrieval handle; add read_output/grep_output paging tools; raise context window default.
TEST: Property test: for any tool result, full bytes retrievable via handle. Replay sparql inputs → full-file visibility path exists.
```

```text
INVARIANT: No grader leakage
WHY: Grader-blind solving is what makes a pass valid; 89/95 task dirs ship solution/.
CURRENT VIOLATION / RISK: docker_runner.py:362-370 mounts /tests:ro and /task:ro at container start for the whole run.
FIX: Solver-phase container mounts only /app; tests are introduced only for the post-terminal grader phase.
TEST: Runner test: solver-phase container has no /task,/tests; grader still runs. Trace lint: zero /task,/tests,reward.txt,ctrf references before terminal state.
```

```text
INVARIANT: No solver self-report authority
WHY: Solver claims are hypotheses; gcode submitted 55 times claiming done.
CURRENT VIOLATION / RISK: Non-workbench auto_submit path can complete on deterministic checks (kernel.py:200-215); acceptable only because workbench mode is certified default — must be enforced, not incidental.
FIX: In the certified path, no terminal accepted state without a verifier completed verdict backed by inspection (kernel.py:231-268 already gates this — keep and test it).
TEST: Kernel test: submit with verifier available never completes without a verifier completed verdict; submit with no verifier never yields accepted terminal state in the certified path.
```

```text
INVARIANT: No harness semantic-judgement crutches
WHY: proof_contract fabricated "missing preservation evidence" on filter-js and misled the verifier.
CURRENT VIOLATION / RISK: proof_contract.py _semantic_query_findings / _filter_security_findings / _openssl_cert_findings branch on task-domain vocabulary; wired into completion gate (completion.py:236-244) and verifier packet (verifier_packets.py:369).
FIX: Delete the analyzers and their gate/packet hooks (P1). Replace intent with verifier sandboxed execution (P2).
TEST: Sentinel: a correct-but-differently-worded solution trips no deterministic gate. No harness module branches on task-domain terms.
```

```text
INVARIANT: Explicit provenance
WHY: The code that produced the flagship batch is unrecoverable; manifests carry no SHA.
CURRENT VIOLATION / RISK: run_pilot.py / launch manifests record model+params but no code SHA / tree hash / prompt hash / task hash; VM is not a git checkout.
FIX: Runner writes a provenance block (code SHA or tree hash, architect+solver+verifier prompt hashes, model+params, task-pack hash) into every manifest and refuses to start without it; deploy VM as a checkout.
TEST: Manifest schema validation; runner refuses to start with unresolved provenance.
```

```text
INVARIANT: Every failure classified with evidence
WHY: model_limit labels that a trace audit overturns end investigation prematurely.
CURRENT VIOLATION / RISK: classifier.py assigns model_limit from state-change + diversity heuristics blind to starvation and silent loops; 3 of 4 model_limit labels across the two runs are unsupported.
FIX: Deterministic candidate classification + evidence refs + an audit-confirmation gate; model_capability_limit requires the §14 evidence bar.
TEST: Every non-pass row carries resolvable evidence refs; injected starvation/silent-loss makes model_capability_limit unreachable.
```

```text
INVARIANT: Substrate failures separated from model failures
WHY: install-windows (no qemu in container) was labeled model_limit.
CURRENT VIOLATION / RISK: environment/provider/docker failures can reach model-attribution; network_scope asserted unprobed.
FIX: Distinct row validity classes (invalid_environment/provider/grader); reward excluded from capability stats for non-valid rows; probe before asserting environment facts.
TEST: Fault injection (kill docker/key/image) → invalid_* rows, excluded from capability denominator.
```

```text
INVARIANT: Verifier judges state, not story
WHY: Three false-cleans occurred with zero independent inspections.
CURRENT VIOLATION / RISK: Packet is solver-story-heavy (recent_actions, memory events, proof_contract_analysis pseudo-facts); read-only inspection cannot judge behavioral correctness.
FIX: Enforce "completed requires >=1 fresh inspection" (model_hooks.py:496-521 at HEAD — keep, and note the VM copy lacks it); add sandboxed execution (P2); trim story fields from the packet. Verifier packets must not include `solver_claim`, `submit_summary`, or privileged solver-proof fields. Solver command/check history remains visible only under an explicit audit namespace such as `solver_authored_evidence`. `proof_contract_analysis` must be removed from the verifier packet or quarantined outside the verifier's judgment context as non-authoritative diagnostics.
TEST: Replay known-bad workspace → verifier does not accept on packet text alone; uninspected completed is rejected (never fabricated into another verdict). Regression test: verifier packet contains no `solver_claim`, `submit_summary`, or privileged solver proof field; solver-authored commands/checks are labeled as audit trail.
```

```text
INVARIANT: No unprobed environment facts
WHY: The architect encoded a fabricated network constraint as truth.
CURRENT VIOLATION / RISK: envmap_builder.py:235 default network_scope="workspace_only"; probe covers commands/modules but not egress.
FIX: environment_probe tests egress and reports probed value or "unknown"; envmap never emits an unprobed fact as fact.
TEST: Probe unit test both ways; envmap for a task with no probe emits "unknown", not "workspace_only".
```

```text
INVARIANT: Harness answers within bounded time or fails loudly
WHY: Wedged tools/providers must become receipts, not hangs.
CURRENT VIOLATION / RISK: docker exec timeouts surface as exit 124 with generic stderr; kernel wall timeout exists (docker_runner.py:747) — keep.
FIX: Timeout produces a typed receipt naming the budget and the killed command.
TEST: Timeout injection → typed receipt, not empty output.
```

---

## 3. Target architecture

```text
STAGE: task_loaded
OWNER: substrate
INPUTS: task.toml, instruction.md, image
OUTPUTS: seeded workspace; solver container with ONLY /app mounted; manifest (provenance block)
RECEIPTS: manifest with code SHA + prompt/task hashes
FAILURE MODES: image pull, workspace seed, container start
FORBIDDEN FALLBACK: default image substitution; mounting /task or /tests
```
```text
STAGE: environment_probed
OWNER: substrate (probe_environment)
INPUTS: live container
OUTPUTS: command/module availability, python variant, network egress, resource limits — each with method recorded
RECEIPTS: probe result; "unknown" where unprobed
FAILURE MODES: probe crash
FORBIDDEN FALLBACK: asserting network/capability facts without a probe
```
```text
STAGE: architect_config_requested
OWNER: architect model
INPUTS: task prompt, probed envmap, capability registry, runtime+verification manuals, schema
OUTPUTS: raw architect output (persisted)
RECEIPTS: raw output (all attempts)
FAILURE MODES: malformed output, vacuous/unrealizable config
FORBIDDEN FALLBACK: none at this stage — output goes to validation as-is
```
```text
STAGE: architect_config_validated
OWNER: compiler
INPUTS: raw config
OUTPUTS: validated contract; realization audit; prompt hashes
RECEIPTS: field-by-field disposition (realized/advisory/rejected)
FAILURE MODES: schema-invalid, vacuous, unrealizable → one repair round → terminal
FORBIDDEN FALLBACK: inventing/substituting semantic content; silent generic default
```
```text
STAGE: workbench_compiled
OWNER: compiler → kernel
INPUTS: contract
OUTPUTS: slim solver prefix (protocol card + architect solver prompt); verifier prompt stored (NOT shown to solver); context recipe; budgets
RECEIPTS: config_realization (to trace, NOT solver context)
FAILURE MODES: compiler cannot realize schema-valid config
FORBIDDEN FALLBACK: dropping fields silently
```
```text
STAGE: solver_loop
OWNER: solver model
INPUTS: context floor + architect recipe context + budget state
OUTPUTS: turns (raw preserved), tool results at full fidelity + handles
RECEIPTS: one per turn incl. denials, errors, parse failures — visible next step
FAILURE MODES: malformed output, wrong work, premature claim
FORBIDDEN FALLBACK: fabricated reconfigure turn; capture-time truncation; ignored signal
```
```text
STAGE: verifier_inspection
OWNER: verifier model + inspector
INPUTS: packet + read-only tools (P1) / + sandboxed overlay execution (P2)
OUTPUTS: inspection requests+results; raw verdict
RECEIPTS: full packet, raw output, every inspection req+result — persisted every call
FAILURE MODES: malformed verdict, refuses to inspect, inspection tooling broken
FORBIDDEN FALLBACK: completed without fresh inspection; fabricating a verdict
```
```text
STAGE: verifier_verdict
OWNER: kernel (routes on verdict)
INPUTS: parsed verdict
OUTPUTS: terminal decision or finding insertion or reconfiguration adjudication
RECEIPTS: verdict + alignment bookkeeping
FAILURE MODES: bounded-disagreement / stalemate
FORBIDDEN FALLBACK: deterministic gate overriding an accepted completed
```
```text
STAGE: agent_terminal
OWNER: kernel
INPUTS: verdict / budget / blocker
OUTPUTS: terminal_reason (verifier_accepted | steps_exhausted | time_exhausted | blocked_by_harness_config | substrate_failure | architect_config_failure)
RECEIPTS: terminal reason
FAILURE MODES: n/a
FORBIDDEN FALLBACK: none
```
```text
STAGE: official_grader
OWNER: substrate
INPUTS: terminal workspace, tests introduced now, isolated from solver influence
OUTPUTS: reward + CTRF detail
RECEIPTS: grader exit, reward source, wall time
FAILURE MODES: grader crash/timeout/missing reward
FORBIDDEN FALLBACK: grader result feeding any pre-terminal context/memory
```
```text
STAGE: result_row
OWNER: result writer
INPUTS: kernel + verifier + grader outputs + provenance
OUTPUTS: row with separated authority fields + validity + evidence refs
RECEIPTS: row persisted; write errors preserved
FAILURE MODES: write failure → row quarantined
FORBIDDEN FALLBACK: collapsing statuses into one "completed"
```
```text
STAGE: audit_classification
OWNER: auditor (deterministic candidate + confirm pass)
INPUTS: row + receipts + trace
OUTPUTS: primary/secondary cause + confidence + evidence refs
RECEIPTS: classification with resolvable refs
FAILURE MODES: insufficient evidence → insufficient_evidence, not model_limit
FORBIDDEN FALLBACK: model_capability_limit without the §14 evidence bar
```

---

## 4. Role boundaries

| Role | Owns | Must never do | Allowed failures (class) | Evidence required |
|---|---|---|---|---|
| **Architect** | task understanding; solver+verifier system prompts; success definition; evidence/false-positive/min-completion; context recipe (above floor); declared checks; budget class | see grader/tests/solutions; restrict stable-core tools; assert unprobed facts; author deterministic semantic gates | malformed (architect_protocol_failure); vacuous/unrealizable (architect_config_invalid) | raw output all attempts, validation errors, repair I/O, config hash |
| **Compiler** | schema validation; normalization; realization; realization audit | invent/substitute semantic content; silently drop fields; repair meaning | cannot realize schema-valid config (compiler_realization_failure) | field-by-field disposition; every rejected/quarantined item + reason |
| **Runtime/kernel** | step loop; protocol enforcement (schema, budgets, verdict-requires-inspection); receipt ledger; verifier routing; terminal decision | judge task success; fabricate turns/verdicts; ignore a turn kind; complete without verifier; block on semantic grounds | crash/timeout/enforcement bug (harness_runtime_failure) | one receipt per turn per decision, visible next step |
| **Context compiler** | assembling floor + recipe; paging handles; explicit compression receipts | drop floor items; truncate without handle; hide compression | floor alone exceeds budget (harness_context_failure) | per-packet realization stats; compression receipts; handle table |
| **Solver** | all task work; local self-verification; the completion claim; blocker reports with evidence | be completion authority; see grader artifacts; be silently overridden | wrong work / malformed / premature (model_capability_limit or model_protocol_limit, evidence-gated) | every turn (raw on failure); every result full fidelity |
| **Verifier** | state judgment vs contract; verdicts; findings + repair; blocked_by_harness_config adjudication | mutate solver workspace; see grader/hidden tests; accept from narrative alone; invent facts | malformed (verifier_protocol_error); refuses/broken inspection (verifier_inspection_failed); judgment error (surfaced via alignment) | full packet, raw output, every inspection req+result, findings lifecycle |
| **Substrate/tools** | Docker; execution; full-fidelity capture; probing; snapshots; timeouts; redaction | judge semantics; alter outputs beyond redaction; present defaults as facts | image/container/exec/fs/timeout (environment_failure/docker_runner_failure/timeout) | full stdout/stderr/exit/duration; probe methods; mount table |
| **Official grader** | score; runs only post-terminal, isolated | influence anything pre-terminal; leak into future context | grader crash/timeout/missing reward (grader_unavailable → invalid_grader) | exit, reward source, CTRF, wall time |
| **Result writer/auditor** | result row (separated authorities); candidate classification; audit confirm; alignment fields | collapse truths; emit model_limit without evidence bar | write failure (result_write_failure → quarantine) | row + evidence refs + provenance |

**Protocol vs. judgment line:** the harness may enforce *form* (schema validity, budgets, "completed requires fresh inspection," mount isolation, timeouts). Only models decide *content* (is the task done, is evidence sufficient, is a blocker real, is work wrong). A rule whose correctness depends on task meaning is on the wrong side of the line.

---

## 5. Current gap map

```text
GAP: Solver-requested / silent reconfigure loop
WHY IT MATTERS: 550+ wasted steps; false model_limit labels
ROOT CAUSE: request_reconfigure over budget falls through with no receipt (kernel.py:270-279); ModelHooks._safe_fallback_turn emits request_reconfigure on parse failure (model_hooks.py:384,564)
FILES: kernel.py, model_hooks.py
FIX PHASE: P0 (receipt + neutralize), P1 (delete solver path, verifier-only reconfig)
TEST/REPLAY: train-fasttext sentinel — no silent loop; 3 denials → terminal blocked
```
```text
GAP: Command/file context starvation
WHY IT MATTERS: sparql unsolvable; all long tasks degraded
ROOT CAUSE: capture-time truncation (kernel.py:565,600,620); 8k packet (runtime_ir.py:270); head-only slice
FILES: kernel.py, real_executor.py, context_compiler.py, runtime_ir.py
FIX PHASE: P0
TEST/REPLAY: sparql sentinel — full file retrievable
```
```text
GAP: Raw malformed model output discarded
WHY IT MATTERS: 19/30 & 14/30 steps burned; root cause unprovable from evidence
ROOT CAUSE: ModelHooks.solve catches all, keeps only last error, fabricates reconfigure turn (model_hooks.py:368-386); azure returns partial text on incomplete (azure_model.py:229)
FILES: model_hooks.py, kernel.py, providers/azure_model.py
FIX PHASE: P0
TEST/REPLAY: filter-js sentinel — raw captured, one retry, 1 step
```
```text
GAP: Fake/unprobed network_scope
WHY IT MATTERS: architect told solver to report tooling block instead of pip install
ROOT CAUSE: hardcoded default (envmap_builder.py:235); no egress probe
FILES: envmap_builder.py, environment_probe.py
FIX PHASE: P0
TEST/REPLAY: probe unit test both ways
```
```text
GAP: /task and /tests leakage risk
WHY IT MATTERS: grader isolation broken; every pass challengeable (89/95 tasks ship solutions)
ROOT CAUSE: docker_runner.py:362-370 mounts tests+task ro for whole run
FILES: runners/docker_runner.py, runners/docker_helpers.py
FIX PHASE: P0
TEST/REPLAY: mount-leak sentinel — solver-phase container clean
```
```text
GAP: proof_contract semantic crutch
WHY IT MATTERS: fabricated findings misled verifier on filter-js
ROOT CAUSE: task-family analyzers (proof_contract.py:83-227) wired to gate (completion.py:236) + packet (verifier_packets.py:369)
FILES: proof_contract.py, completion.py, verifier_packets.py, kernel.py
FIX PHASE: P1 delete/quarantine
TEST/REPLAY: filter-js sentinel — no fabricated finding
```
```text
GAP: Verifier lacks sandboxed execution
WHY IT MATTERS: false-cleans (behavioral) + extract-elf false-reject
ROOT CAUSE: verifier_inspector limited to read/rerun-compiled-check/receipt browsing
FILES: verifier_inspector.py, kernel_verifier.py, real_executor.py
FIX PHASE: P2
TEST/REPLAY: behavioral known-bad sentinel — not accepted
```
```text
GAP: Verifier strict parsing
WHY IT MATTERS: openssl "Extra data" verifier error while solver/architect parsers are lenient
ROOT CAUSE: verifier.py:188 json.loads(text) with no fence/prose tolerance
FILES: verifier.py
FIX PHASE: P1
TEST/REPLAY: prose-wrapped verdict JSON parses
```
```text
GAP: No-progress hard-blocking
WHY IT MATTERS: punished sparql for the harness's own starvation
ROOT CAUSE: escalation to hard_block (no_progress.py:62-90); blocker into completion gate (completion.py:226)
FILES: no_progress.py, context_compiler.py, completion.py
FIX PHASE: P1 (advisory + paging nudge)
TEST/REPLAY: truncated-then-paged sentinel — no block
```
```text
GAP: Fat static prompt stack (27 messages)
WHY IT MATTERS: buries architect voice; ~1/3 meta-noise
ROOT CAUSE: stable_prefix_sections rendered as many system messages (runtime_ir.py:462; kernel_messages.py:69) incl. config_realization dump + verifier prompt to solver
FILES: runtime_ir.py, kernel_messages.py, workbench_compile.py
FIX PHASE: P1
TEST/REPLAY: solver context excludes verifier prompt + realization dump
```
```text
GAP: Missing code provenance
WHY IT MATTERS: flagship batch code unrecoverable; runs not reproducible
ROOT CAUSE: manifests lack SHA/hashes; VM not a checkout
FILES: run_pilot.py, runner manifest writer
FIX PHASE: P0
TEST/REPLAY: manifest schema validation
```
```text
GAP: Result labels overclaiming model_limit
WHY IT MATTERS: ends investigation; 3/4 labels unsupported
ROOT CAUSE: classifier heuristics blind to starvation/silent loops (classifier.py:116-148)
FILES: classifier.py, docker_runner.py record
FIX PHASE: P1 (authority separation + evidence bar), P2 (audit confirm)
TEST/REPLAY: injected starvation → model_limit unreachable
```

---

## 6. P0 plan — before any real VM/model run

Implement all nine in order. No VM batch until every acceptance criterion passes.

```text
FIX 1: Stop mounting /task and /tests into the solver container
WHY P0: Grader-leakage invariant; every pass challengeable
FILES: runners/docker_runner.py (362-370, 481-533), runners/docker_helpers.py
MINIMAL PATCH: Start the solver container with only -v {workspace}:/app. Introduce tests for the grader phase only — either docker cp the tests dir in immediately before running the grader, or run the grader in a separate short-lived container/exec with the tests mounted, after agent terminal.
TESTS: test_docker_runner: solver-phase container inspect shows no /task,/tests binds; grader still executes and reward.txt is read.
REPLAY / TRACE CHECK: Trace lint over any run: zero commands referencing /task,/tests,/logs/verifier before terminal state.
ACCEPTANCE CRITERIA: Solver phase provably has no access to tests/solution; grader unchanged in behavior.
RISK: Low. Watch: graders that assume /tests present during solving (should be none — grader runs post-terminal).
```
```text
FIX 2: Every solver signal produces a receipt visible next step
WHY P0: No-silent-signal-loss; kills the largest measured waste
FILES: kernel.py (200-282 loop; 270-279 reconfigure branch)
MINIMAL PATCH: In the over-budget request_reconfigure branch, record a reconfigure_denied receipt (budget state + "act with current config or report a blocker via submit_outcome/report_blocker"); ensure it is surfaced by context_compiler._enforce_safety_sections. Treat N (=3) consecutive denied requests as terminal blocked_by_harness_config.
TESTS: Kernel test: over-budget request → receipt present in next compiled context; 3 consecutive → terminal blocked.
REPLAY / TRACE CHECK: train-fasttext sentinel replays without a silent loop; reconfigure_denied receipts appear.
ACCEPTANCE CRITERIA: No turn kind can be consumed without a next-step-visible receipt.
RISK: Low.
```
```text
FIX 3: Neutralize solver-requested reconfiguration path
WHY P0: Removes the loop's fuel now; full deletion is P1
FILES: kernel.py, model_hooks.py (_safe_fallback_turn)
MINIMAL PATCH: On parse failure, do NOT emit request_reconfigure (see FIX 4). Convert any solver request_reconfigure into a recorded no-op-with-receipt in the certified workbench path (it is already largely inert there — make it explicit and visible), pending P1 removal.
TESTS: Solver emitting request_reconfigure → receipt, no reconfiguration, no silent loop.
REPLAY / TRACE CHECK: No trace shows an unrecorded reconfigure.
ACCEPTANCE CRITERIA: Solver cannot drive reconfiguration; every attempt is visible.
RISK: Low.
```
```text
FIX 4: Capture raw malformed solver output + parse-feedback retry
WHY P0: No-signal-loss + no-information-destruction; recovers 30-50% of burned steps
FILES: model_hooks.py (368-386), kernel.py (malformed branch), providers/azure_model.py (incomplete status)
MINIMAL PATCH: On solve parse/validate failure, persist a parse_error receipt containing the raw output and the specific error; issue ONE same-step retry with the error appended to the messages (mirror the architect repair at workbench_hooks.py:244-275). If still bad, consume the step but keep the raw receipt. Log provider incomplete status distinctly.
TESTS: Fake model bad-then-good JSON → 1 step consumed, raw captured, retry succeeds. Fake provider incomplete → distinct receipt.
REPLAY / TRACE CHECK: filter-js sentinel: parse-turn storm replaced by captured raw + retry.
ACCEPTANCE CRITERIA: No raw model output is ever discarded; solver sees its own malformed output next step.
RISK: Low. Watch: retry cost — one retry only.
```
```text
FIX 5: Preserve full command/file outputs with paging handles
WHY P0: No-information-destruction; made sparql unsolvable
FILES: kernel.py (565,600,620 payloads), real_executor.py (_STDOUT_CAP already 20000 — capture is fine; kernel re-truncates), context_compiler.py, runtime_ir.py (ContextPolicy defaults)
MINIMAL PATCH: Store full stdout/stderr and full file content in the ledger payload (executor already captures up to 20k). Inline a head+tail slice (>=8k chars combined) with a retrieval handle. Add read_output(handle, offset, span) and grep_output(handle, pattern) kernel-owned tools; add file paging for reads beyond the excerpt. Raise ContextPolicy.model_context_window_tokens default (>=32000) — measure token cost.
TESTS: Property test: full bytes retrievable via handle for any tool result. Head+tail slice marked with elision + handle.
REPLAY / TRACE CHECK: sparql sentinel: the 10 KB graph is fully reachable.
ACCEPTANCE CRITERIA: Solver can always retrieve the full content of anything it produced or read.
RISK: Medium (token cost). Mitigation: inline caps + handles keep default packet small; measure before/after.
```
```text
FIX 6: Enforce the context floor
WHY P0: Prevents architect policy from starving the model
FILES: context_compiler.py (_enforce_safety_sections, compile), workbench_compile.py (context sections)
MINIMAL PATCH: Define the mandatory floor (§12) as non-removable regardless of architect recipe/mode. If the floor alone exceeds budget, emit harness_context_failure with a receipt naming the elided items and their handles — never a silent drop.
TESTS: Architect recipe omitting command_results/file reads → floor still present. Oversized floor → loud harness_context_failure.
REPLAY / TRACE CHECK: Any run: floor items present in every packet.
ACCEPTANCE CRITERIA: No architect policy can hide a floor item; overflow is loud.
RISK: Low.
```
```text
FIX 7: Probe network / tool availability truthfully
WHY P0: No-unprobed-facts; misdirected train-fasttext
FILES: environment_probe.py, envmap_builder.py (235)
MINIMAL PATCH: Add an egress probe (e.g. short-timeout HEAD to a package index) to probe_environment; envmap reports probed network value or "unknown". Remove the hardcoded network_scope default.
TESTS: Probe unit test both ways; task with no probe → envmap network="unknown".
REPLAY / TRACE CHECK: Architect request for a network-needing task carries a probed fact, not a fabricated one.
ACCEPTANCE CRITERIA: No environment fact is asserted without a probe.
RISK: None (probe is read-only, short timeout).
```
```text
FIX 8: Record provenance in every run manifest
WHY P0: Reproducibility; flagship batch unrecoverable
FILES: run_pilot.py, runner manifest writer
MINIMAL PATCH: Write code SHA (or tree hash for non-git deploys), architect/solver/verifier prompt hashes, model+params, and task-pack hash into launch_manifest.json; refuse to start without a resolvable code hash. Deploy the VM as a git checkout.
TESTS: Manifest schema validation; runner aborts with a clear error when provenance is unresolved.
REPLAY / TRACE CHECK: Every new results.json row carries a provenance block.
ACCEPTANCE CRITERIA: Any future run is reproducible from its manifest.
RISK: None.
```
```text
FIX 9: Gate — no new VM batch until 1-8 pass
WHY P0: A batch now re-measures known harness faults
FILES: n/a (process gate)
MINIMAL PATCH: CI/checklist gate referencing the P0 acceptance criteria + sentinel replays.
TESTS: All P0 sentinels green.
ACCEPTANCE CRITERIA: P0 test/replay matrix (§15) fully green.
RISK: None.
```

---

## 7. P1 plan — vision alignment

```text
FIX: Verifier-triggered-only, single-shot reconfiguration
FILES: kernel.py, kernel_verifier.py, verifier.py, model_hooks.py, classifier.py (record)
DETAIL: Delete the solver-requested path entirely. Verifier blocked_by_harness_config with concrete inspection-backed evidence → kernel adjudicates → one architect repair segment (segment 2, provenance-tagged, step counter continues) → sets architect_defect=true even if the task then passes. Second block → terminal blocked_by_harness_config. New config invalid → architect_config_failure. (Full design §10.)
TEST: solver blocker → verifier adjudication; <=1 segment; architect_defect recorded.
```
```text
FIX: One architect repair attempt with exact validation errors; invalid config terminates
FILES: kernel_config.py, workbench_hooks.py, kernel.py
DETAIL: Keep the single repair round (workbench_hooks.py:244-275); ensure the ONLY failure exit is architect_config_failure (remove guaranteed_default_ir substitution from the production workbench path). (Full design §11.)
TEST: two-fail architect → terminal architect_config_failure, no solver step.
```
```text
FIX: Delete/quarantine proof_contract semantic gates
FILES: proof_contract.py (remove analyzers), completion.py (236-244), verifier_packets.py (369), kernel.py (439-441)
DETAIL: Remove _semantic_query_findings/_filter_security_findings/_openssl_cert_findings and their gate/packet wiring. Remove `proof_contract_analysis` from the verifier packet unless it is strongly labeled outside verdict context as non-authoritative diagnostics. Keep only honest contract_missing accounting if any value remains, else delete the module.
TEST: filter-js sentinel — no fabricated finding; differently-worded correct solution trips no gate. Packet regression: no proof-contract field can be read by the verifier as task proof.
```
```text
FIX: Slim solver prompt/context stack; solver must not see verifier prompt
FILES: kernel_messages.py (build_solver_messages), runtime_ir.py (stable_prefix_sections / prefix_messages:462), workbench_compile.py
DETAIL: Reduce to protocol card (action schema, output format, runtime facts) + architect solver prompt + envmap essentials. Remove the config_realization dump and the [verifier_identity] section from solver context (keep both in the trace).
TEST: solver context assertion excludes verifier prompt + realization dump; message count materially reduced.
```
```text
FIX: No-progress becomes advisory + paging nudge, not hard block
FILES: no_progress.py (62-90), context_compiler.py, completion.py (226-234)
DETAIL: Disable hard_block escalation; emit an advisory receipt offering the paging handle for the repeated target. Remove no_progress_control from the completion gate blockers.
TEST: truncated-then-paged sentinel — handle offered, no block.
```
```text
FIX: Verifier verdict protocol hardened
FILES: verifier.py (188 parse), model_hooks.py (verify path)
DETAIL: Lenient verdict parsing (reuse _extract_json_object). Keep "completed requires >=1 fresh inspection" (HEAD model_hooks.py:496-521). On unparsable-after-retry → verifier_protocol_error; never fabricate a verdict.
TEST: prose-wrapped JSON parses; garbage → verifier_protocol_error, not acceptance.
```
```text
FIX: Result-row authority separation + model_limit evidence bar
FILES: classifier.py, runners/docker_runner.py (record assembly)
DETAIL: Separate fields (§14). Row validity gate on capability stats. Deterministic candidate classification with evidence refs. (Audit-confirm pass is P2.)
TEST: env fault → invalid_environment excluded from capability stats; injected starvation → model_limit unreachable.
```

---

## 8. P2 plan — max capability

```text
FIX: Verifier sandboxed execution / overlay checks
FILES: verifier_inspector.py, kernel_verifier.py, real_executor.py
DETAIL: Copy-on-write overlay / throwaway clone of the workspace; verifier can create fixtures and run the deliverable without mutating solver state. Closes behavioral false-clean/false-reject. Inspection priority is raw state first: files, artifacts, service/process state, source inputs, and verifier-owned independent reruns. Solver command history remains visible, but only as audit trail to inspect or challenge.
CAPABILITY vs RISK: High capability, medium risk (overlay substrate correctness). This is the last structural harness cap — not optional polish.
```
```text
FIX: Native tool calling / robust action protocol
FILES: providers/, model_hooks.py, runtime_ir.py
DETAIL: Replace the strict single-JSON turn with native tool calls (or a far more lenient protocol) to remove the parse tax at the source.
CAPABILITY vs RISK: High / low-medium.
```
```text
FIX: Per-task budget class from architect
FILES: workbench_config.py, run_pilot.py, kernel.py
DETAIL: Architect emits a budget_class → per-task step/time/verification budgets (some TB tasks need hours/hundreds of steps). Guard against it becoming a task-name lookup.
CAPABILITY vs RISK: Medium / low.
```
```text
FIX: Bounded verifier disagreement / stalemate protocol
FILES: verifier.py, kernel.py
DETAIL: After N consecutive needs_repair with no new named gap → escalate to uncertain_missing_evidence with a mandatory concrete missing list; optional single second-opinion pass; then terminal verification_stalemate (candidate verifier-quality issue, NOT auto model_limit).
CAPABILITY vs RISK: Medium / medium (a second pass adds cost — justify by stalemate rate).
```
```text
FIX: Deterministic replay harness for known failures
FILES: tests/
DETAIL: Turn the sentinels (§15) into a replay suite so regressions are caught without VM runs.
CAPABILITY vs RISK: Medium (iteration speed) / low.
```
```text
FIX: Stronger trace/audit tooling + audit-confirm classification
FILES: analysis/audit tooling, classifier.py
DETAIL: Model/human confirm pass before model_capability_limit is finalized; alignment board generation.
CAPABILITY vs RISK: Trust / low.
```
```text
FIX: EnvMap hardening
FILES: envmap_builder.py, environment_probe.py
DETAIL: Remove remaining TB-shaped hint lists; keep probing substrate-only; ensure no fabricated facts.
CAPABILITY vs RISK: Correctness / low.
```
```text
FIX: Full promotion eval
FILES: run_pilot.py, scoreboards
DETAIL: One SHA-stamped batch over the 13 sentinels + broader set per §16.
CAPABILITY vs RISK: Evidence / n/a.
```

---

## 9. Delete / quarantine list

```text
COMPONENT: proof_contract
KEEP/REVISE/DELETE/QUARANTINE: DELETE
WHY: Task-family analyzers are the textbook crutch; misled the verifier; correctness depends on task meaning
REPLACEMENT: verifier sandboxed execution (P2) + architect-declared evidence requirements
TEST: differently-worded correct solution trips no gate
```
```text
COMPONENT: no_progress
KEEP/REVISE/DELETE/QUARANTINE: REVISE → advisory + paging nudge only
WHY: hard-blocked the model during starvation
REPLACEMENT: paging handles remove the repeat's cause; advisory notice for genuine stuckness
TEST: truncated-then-paged → no block
```
```text
COMPONENT: automatic_memory
KEEP/REVISE/DELETE/QUARANTINE: REVISE → advisory surfacing only
WHY: surfacing prior evidence is useful; blocking modes (require_justification/soft_block) are crutch-shaped
REPLACEMENT: keep advisory findings; delete blocking modes (kernel.py:367-388)
TEST: repeated action → advisory only, never a completion blocker
```
```text
COMPONENT: solver-requested reconfiguration
KEEP/REVISE/DELETE/QUARANTINE: DELETE
WHY: pure loop fuel
REPLACEMENT: report_blocker (evidence) → verifier adjudication
TEST: solver cannot drive reconfiguration
```
```text
COMPONENT: legacy architect paths (IR / contract, _safe_default_ir, guaranteed_default_ir in prod)
KEEP/REVISE/DELETE/QUARANTINE: QUARANTINE behind explicit --reference
WHY: silent generic fallback is the biggest zero-fallback violation
REPLACEMENT: single workbench path with loud config failure
TEST: production path never reaches a default-IR substitution
```
```text
COMPONENT: static harness prompt stack (27 messages)
KEEP/REVISE/DELETE/QUARANTINE: REVISE → thin protocol card
WHY: buries the architect's voice; ~1/3 meta-noise
REPLACEMENT: protocol card + architect solver prompt + envmap essentials
TEST: solver message count reduced; no realization dump / verifier prompt in solver context
```
```text
COMPONENT: config_realization dumps in solver context
KEEP/REVISE/DELETE/QUARANTINE: DELETE from solver context (keep in trace)
WHY: 4KB internal audit noise to the model
REPLACEMENT: trace-only
TEST: solver context excludes config_realization
```
```text
COMPONENT: EnvMap
KEEP/REVISE/DELETE/QUARANTINE: KEEP, harden probing
WHY: real, useful architect signal
REPLACEMENT: n/a; remove fabricated facts + TB-shaped hint lists
TEST: no unprobed fact emitted
```
```text
COMPONENT: visible smoke checks
KEEP/REVISE/DELETE/QUARANTINE: KEEP as advisory evidence
WHY: cheap solver self-check; never grader authority
REPLACEMENT: n/a
TEST: smoke check never completes a task by itself
```
```text
COMPONENT: verifier read-only tools
KEEP/REVISE/DELETE/QUARANTINE: KEEP
WHY: necessary inspection floor
REPLACEMENT: n/a
TEST: verifier can read files/rerun compiled checks/browse receipts
```
```text
COMPONENT: verifier sandboxed execution
KEEP/REVISE/DELETE/QUARANTINE: ADD (P2)
WHY: only way to catch behavioral false-cleans/rejects
REPLACEMENT: replaces proof_contract's intent honestly
TEST: behavioral known-bad → not accepted
```
```text
COMPONENT: result classifier
KEEP/REVISE/DELETE/QUARANTINE: REVISE → deterministic candidate + evidence bar + audit confirm
WHY: current labels overturn under audit
REPLACEMENT: §14 model
TEST: injected starvation → model_limit unreachable
```
```text
COMPONENT: retired Aether-2 paths (harness/aether2, runner/aether2)
KEEP/REVISE/DELETE/QUARANTINE: KEEP as reference; do not build on
WHY: portable patterns only; not production
REPLACEMENT: n/a
TEST: no production import from aether2 (grep gate)
```
```text
COMPONENT: stale audit docs (PHASE*, VERIFIER_ONLY_*, superseded MDs)
KEEP/REVISE/DELETE/QUARANTINE: QUARANTINE (add SUPERSEDED banner or move to archive/)
WHY: describe superseded builds; mislead agents
REPLACEMENT: this document is the source of truth
TEST: n/a
```

---

## 10. Reconfiguration design (final)

- **Should the solver request reconfiguration?** No. Deleted. The solver's only config-related signal is `report_blocker` with evidence.
- **Should the verifier trigger it?** Yes — the only role that inspects state before concluding the workbench is at fault. That precondition is what keeps reconfiguration from being a fallback.
- **Should the harness auto-reconfigure?** No.
- **How many times?** Once per run. A second block → terminal `blocked_by_harness_config`.
- **Evidence required?** A verifier `blocked_by_harness_config` verdict with >=1 completed inspection naming the specific config/env defect (e.g., success_definition references a path the task never produces; a declared check is unrunnable in the probed env).
- **Fed back to architect?** Original request + verifier's blocking evidence + full prior config + what the solver already did.
- **Recorded how?** New run segment (segment 2), explicit provenance, new config hash, step counter continues (not reset); receipts: verifier_blocked, reconfiguration_adjudicated (approved/denied + reason), new architect I/O, segment boundary. Result fields: `reconfigured=true`, `reconfiguration_reason`, `architect_defect=true`, `segment_count`.
- **If denied?** Verdict downgraded to uncertain_missing_evidence with the adjudication reason surfaced to the solver; run continues.
- **If new config invalid?** `architect_config_failure` terminal — no third try, no fallback.
- **Why it does not hide failure:** every reconfiguration sets `architect_defect=true` even when the task then passes. Reconfiguration rate is a tracked architect-quality metric. Rarity is *earned* by a good architect and by making config non-fatal (tool floor, honest probes, forgiving contract) — not achieved by banning the mechanism, which would also suppress the diagnostic.

---

## 11. Architect config design

- **Required fields (presence is hard protocol; content is model-owned):** `success_definition`, `solver_system_prompt.role`, `verifier_system_prompt.role`, `evidence_requirements` (non-empty), `minimum_completion_evidence` (non-empty), `tool_policy.enabled_tools` (non-empty, but advisory — cannot hide stable-core tools).
- **Optional:** `declared_checks` (typed, advisory to solver, never grader authority), `context_recipe` overrides, `budget_class`, memory advisory, `local_verification_limits`, `false_positive_risks`.
- **Forbidden defaults:** no generic "careful software engineer" solver prompt; no default success definition/evidence list; no default verifier prompt substituted for a missing one. Absence of a required field is a validation failure, not a default trigger.
- **Safe compiler normalization:** whitespace/casing/enum canonicalization; list-vs-scalar coercion; dedup; quarantining unsupported typed smoke-test specs (recording each). These reshape, never author.
- **Forbidden semantic repair:** inventing/substituting prompts, success definitions, evidence lists; "fixing" meaning; converting a vacuous contract into a plausible one.
- **Repair protocol:** exactly one architect repair round, fed the precise validation errors + schema reminder (workbench_hooks.py:244-275). Not more — a second failure on the same task is an offline design signal (schema/prompt/model), not a runtime patch.
- **Terminal failure:** post-repair still schema-invalid / vacuous / unrealizable → `architect_config_failure`; reward excluded from capability stats; both attempts + errors recorded.
- **Tests proving no silent fallback:** malformed architect output → architect_config_failure (never a running solver); vacuous success_definition → terminal; grep gate: no default-IR producer reachable from the workbench path.

---

## 12. Context design

**Mandatory baseline floor (architect cannot remove):** task prompt; current deliverables / declared output paths; workspace summary (tree + changed files); recent tool calls (>=8); recent stdout (tail-biased, generous inline cap); recent stderr (same); command exit codes; full-output handles; recent file reads (paths + excerpts); full-file handles; diffs / artifact history (compact + handle); active verifier findings (until resolved/superseded); verifier feedback; parse errors; the solver's own last malformed output; budget state (steps/reconfig/verification passes left); probed environment facts ("unknown" where unprobed); tool availability; blocked/denied action receipts; prior reconfiguration/config events.

**Architect-tunable (above floor):** prioritization/ordering; domain evidence to preserve exact; key files to pin; memory/repeat mode; compaction recipe; which check results to surface; verifier focus; local verification limits framing. The recipe may add and prioritize; it may never subtract from the floor.

**Paging / full-output retrieval:** full bytes stored in the ledger; `read_output(handle, offset, span)` and `grep_output(handle, pattern)`; file paging beyond the excerpt. This replaces the "cat the file again" loop that no-progress used to punish.

**Truncation policy:** head+tail with a marked elision and a handle to the full text (errors live at the tail, setup at the head, the middle is the safe cut). Never head-only; never at capture time.

**Overflow handling:** if the floor alone exceeds budget → `harness_context_failure` (loud, with a receipt naming what was elided and how to retrieve it). Never a silent drop. Handles keep the inline floor small, so this should be rare enough to be a bug.

**Never omitted:** any floor item — especially the solver's own outputs, its own malformed output, active findings, budget state, and probed facts.

**Tests proving the solver sees outputs/feedback:** architect recipe omitting command_results → still present; a verifier finding is present in the next solver packet and persists until resolved; the solver's malformed output is present next step.

---

## 13. Verifier design

- **Prompt ownership:** the architect authors the verifier system prompt; it becomes the real verifier system prompt (model_hooks.py:328-335, HEAD `_verifier_identity_prompt_for`). Absence of an architect verifier prompt is a config failure, not a fallback to a generic prompt.
- **Static wrapper allowed:** a thin protocol card only — verdict schema, "judge state not story," inspection-request format. Nothing task-semantic.
- **Read-only inspection (P1):** read files, rerun compiled (file-exists/syntax/size) checks, browse receipts/history/diffs/active findings, request bounded additional inspection.
- **Sandboxed execution (P2):** copy-on-write overlay / throwaway clone; create fixtures; run the deliverable; never mutate the solver workspace.
- **Verdicts and required evidence:**
  - `completed` — state satisfies success definition, backed by >=1 fresh inspection. → terminal_agent_completed → grader.
  - `needs_repair` — >=1 finding with evidence + repair instruction + applies_to. → insert finding, continue.
  - `uncertain_missing_evidence` — concrete missing-evidence requests. → continue; solver may produce evidence.
  - `blocked_by_harness_config` — named defect + inspection backing. → reconfiguration adjudication (§10).
  - `verifier_protocol_error` — raw output + parse error. → one retry; then record as harness/verifier fault, do not fabricate a verdict.
  - `verifier_inspection_failed` — substrate error. → retry once; then invalid_environment for verification, not model failure.
- **Feedback lifecycle:** findings inserted into the floor (always visible until cleared); persist across steps; **resolved** when the verifier confirms the defect gone via fresh inspection, or `resolved_by_evidence` when the runtime confirms the requested evidence category now exists; **superseded** when a new finding with the same applies_to + verdict replaces it; stale-cycle tracked (verifier.py ActiveFindingStore already models this — keep).
- **Bounded disagreement:** after N consecutive needs_repair with no new named gap → escalate to uncertain_missing_evidence with a mandatory concrete missing list; optional single second-opinion pass; then terminal `verification_stalemate` (candidate verifier-quality issue, not auto model_limit). This is protocol (a counter), not judgment.
- **Grader isolation:** verifier never sees grader output or hidden tests; approaches grader-equivalence by testing the *property* the grader tests via its own fixtures, never by reproducing the grader's inputs. The residual gap (the grader's exact adversarial corpus) is the legitimate local-verification limit the architect declares.

---

## 14. Result / status design

Separate authority fields — never one "status":

- **Kernel:** `terminal_reason` ∈ {verifier_accepted, steps_exhausted, time_exhausted, blocked_by_harness_config, substrate_failure, architect_config_failure}. (Rename kernel "completed" → `verifier_accepted`; "completed" as a bare word is banned from scoreboards.)
- **Verifier:** `internal_completion_status` ∈ {completed, incomplete, blocked} + verdict history.
- **Solver self-report:** `solver_claimed_done` (bool) — no authority.
- **Grader:** `official_grader_status` ∈ {pass, fail, unavailable} + `reward`.
- **Row validity:** `valid | invalid_environment | invalid_provider | invalid_grader | architect_config_failure | evidence_low_trust`. Only `valid` rows enter capability statistics.
- **Audit:** `primary_cause`, `secondary_cause`, `cause_confidence`, `evidence_refs[]`.
- Keep the existing `verifier_alignment_status` reconciliation (classifier.py:194) — it correctly caught the false-cleans.

**Cause classes:** model_capability_limit, model_protocol_limit, architect_task_understanding, architect_config_invalid, architect_defect_reconfigured, compiler_realization, context_starvation, context_floor_overflow, solver_execution, solver_self_verification, verifier_false_clean, verifier_false_reject, verifier_protocol, verification_stalemate, environment_setup, provider, docker, timeout, grader_issue, evidence_integrity, insufficient_evidence.

**Evidence required before a label:**
- `model_capability_limit`: row validity==valid AND no context_starvation/floor-overflow receipts AND no silent-signal-loss events AND all environment facts probed AND verifier feedback delivered+legible AND the info-availability test passes (the model had full information available). Fail any one → not a model limit.
- `harness_fault`: a receipt/trace step showing the harness destroyed information, ignored a signal, asserted an unprobed fact, or fabricated judgment.
- `environment_failure` / `provider_failure` / `grader_issue`: a substrate/provider/grader receipt; row validity set accordingly; excluded from capability stats.
- `insufficient_evidence`: no receipt supports any attribution — the honest default, never model_limit.

**Labels are deterministic-candidate + audit-confirmed.** The classifier proposes from receipts; a model/human confirm pass (P2) finalizes any model_capability_limit.

---

## 15. Test and replay matrix

Sentinels are derived from the audited runs and become a deterministic replay suite (P2 turns them into CI).

| Item | Unit test | Integration test | Replay/sentinel | Expected before fix | Expected after fix |
|---|---|---|---|---|---|
| P0-1 mount isolation | container args exclude /task,/tests | grader still scores | mount-leak sentinel (trace lint) | tests+task mounted during solve | solver-phase clean; grader unchanged |
| P0-2 signal receipt | over-budget request → receipt | 3 denials → terminal blocked | train-fasttext silent-loop sentinel | 184/201 silent turns | no silent loop; denials visible |
| P0-3 neutralize solver reconfig | solver request → receipt, no reconfig | — | (shares train-fasttext) | reconfigure drives loop | inert + visible |
| P0-4 raw output + retry | bad-then-good JSON → 1 step, raw kept | provider incomplete → distinct receipt | filter-js parse-storm sentinel | 19/30 steps burned, raw lost | raw captured, retry recovers |
| P0-5 full output + paging | full bytes via handle | read_output/grep_output round-trip | sparql starvation sentinel | 10KB file unseeable | full file reachable |
| P0-6 context floor | recipe omits command_results → still present | oversized floor → harness_context_failure | (sparql) | floor items droppable | floor guaranteed; overflow loud |
| P0-7 network probe | probe both ways | envmap emits probed/unknown | train-fasttext network sentinel | network_scope fabricated | probed or "unknown" |
| P0-8 provenance | manifest schema valid | runner aborts w/o SHA | — | no SHA in manifest | SHA+hashes present |
| P1 reconfig verifier-only | solver cannot trigger | blocked → 1 segment, architect_defect | — | solver-driven | verifier-adjudicated, once |
| P1 architect repair/terminal | one repair with errors | two-fail → architect_config_failure | malformed-architect-config sentinel | silent generic fallback | terminal, no solver |
| P1 proof_contract delete | no analyzer import | differently-worded solution → no gate | filter-js proof-contract sentinel | fabricated finding | no fabricated finding |
| P1 verifier packet hygiene | no solver_claim/submit_summary/privileged proof fields | solver commands/checks under solver_authored_evidence | false-clean packet sentinel | solver story/proof fields steer verifier | raw-state-first packet with solver audit trail only |
| P1 slim prompt | solver context excludes verifier prompt+realization | message count reduced | — | 27-message stack | slim card |
| P1 no-progress advisory | display-loop → handle, no block | — | truncated-then-paged sentinel | hard block | advisory + handle |
| P1 verifier parse + inspection | prose JSON parses; uninspected completed rejected | — | uninspected-verifier-completed sentinel; extract-elf false-reject sentinel | Extra-data error; 70+ false rejects | lenient parse; escalation bound |
| P1 result authority | env fault → invalid_environment excluded | injected starvation → model_limit unreachable | — | model_limit overclaimed | evidence-gated labels |
| P2 verifier sandbox exec | behavioral known-bad → not accepted | overlay no-mutation | extract-elf + gcode/raman/video sentinels | false-clean/false-reject | correct behavioral verdict |
| P2 native tool calling | tool-call round-trip | — | (filter-js/sparql regression) | JSON parse tax | no parse tax |
| P2 bounded disagreement | N rejects → escalation | stalemate → verification_stalemate | extract-elf sentinel | 200-step grind | escalates early |

**Named sentinels (must exist as replay fixtures):** train-fasttext silent reconfigure loop; sparql context starvation; filter-js parse-failure + proof-contract interference; extract-elf verifier false-reject loop; /task-/tests mount leak; uninspected verifier completed; malformed architect config; malformed solver output.

---

## 16. Promotion gate

Aether-Next may be called **default/certified** only when ALL hold:

1. No P0 invariant violation (all P0 acceptance criteria + sentinels green).
2. P1 vision alignment complete (reconfiguration verifier-only; proof_contract removed; slim prompt; no-progress advisory; verifier parse/inspection hardened; result authority separation + evidence bar).
3. One SHA-stamped real run (manifest carries code SHA + prompt/task hashes).
4. Full raw traces and model IO persisted (including raw malformed outputs).
5. Verifier packets persisted for every verification (evidence dir set, per-task scoped).
6. No solver access to grader/test mounts (trace-lint clean).
7. Every non-pass row audit-classified with resolvable evidence refs.
8. No unsupported model_limit labels (each passes the §14 evidence bar).
9. Verifier/grader alignment board produced with zero false-cleans where inspection was enabled.
10. No silent fallback, no context starvation, no unprobed environment facts anywhere in the run (receipt/trace-lint clean).

Until then Aether-Next remains a candidate, and any scoreboard must say so.

---

## 17. Non-goals for now

Do **not** do these before P0/P1 land — none blocks the model-limiter goal, and each risks re-introducing complexity:

- Broad architect redesign (the architect layer is the strongest part; leave it).
- New memory features (advisory surfacing only; no new mechanisms).
- Any VM batch before P0 passes.
- Stage-2 task expansion.
- The `aether/` consolidation rename (cosmetic; do after promotion).
- Aether-2 mining beyond reference reading.
- Prompt-caching optimization.
- New overfitted proof gates of any kind.

---

## 18. First implementation sequence

Numbered, ordered. Each step names files, tests, done-criterion, and whether it blocks the next.

1. **Provenance (P0-8).** Files: run_pilot.py, manifest writer. Tests: manifest schema; abort-without-SHA. Done: every run writes a provenance block; runner refuses to start without one. Blocks next? No (do first so all later test runs are reproducible).
2. **Mount isolation (P0-1).** Files: runners/docker_runner.py, docker_helpers.py. Tests: solver-phase container clean; grader still scores. Done: mount-leak sentinel green. Blocks next? No, but highest-integrity — do early.
3. **Signal receipts + neutralize solver reconfig (P0-2, P0-3).** Files: kernel.py, model_hooks.py. Tests: over-budget → receipt; 3 denials → terminal; solver reconfig inert+visible. Done: train-fasttext sentinel shows no silent loop. Blocks next? Yes — FIX 4 depends on the parse-failure branch being reshaped here.
4. **Raw output capture + parse retry (P0-4).** Files: model_hooks.py, kernel.py, providers/azure_model.py. Tests: bad-then-good → 1 step, raw kept; provider incomplete distinct. Done: filter-js parse-storm sentinel green. Blocks next? No.
5. **Full outputs + paging + floor (P0-5, P0-6).** Files: kernel.py, real_executor.py, context_compiler.py, runtime_ir.py, workbench_compile.py. Tests: full bytes via handle; floor guaranteed; overflow loud. Done: sparql starvation sentinel green. Blocks next? No.
6. **Truthful network/tool probe (P0-7).** Files: environment_probe.py, envmap_builder.py. Tests: probe both ways; envmap unknown default. Done: train-fasttext network sentinel green. Blocks next? No. **← P0 complete; run the P0 test/replay matrix (§15) before any P1 work.**
7. **Verifier-only reconfiguration + architect repair/terminal (P1).** Files: kernel.py, kernel_verifier.py, verifier.py, kernel_config.py, workbench_hooks.py. Tests: solver cannot trigger; <=1 segment; two-fail → architect_config_failure. Done: malformed-architect-config sentinel green. Blocks next? No.
8. **Delete proof_contract + slim prompt + no-progress advisory (P1).** Files: proof_contract.py, completion.py, verifier_packets.py, kernel.py, kernel_messages.py, runtime_ir.py, no_progress.py. Tests: no fabricated finding; solver context slim; display-loop → handle. Done: filter-js proof-contract + truncated-then-paged sentinels green. Blocks next? No.
9. **Verifier parse/inspection hardening + result authority (P1).** Files: verifier.py, model_hooks.py, classifier.py, docker_runner.py. Tests: prose JSON parses; uninspected completed rejected; env fault excluded; starvation → model_limit unreachable. Done: uninspected-verifier-completed sentinel green. Blocks next? No. **← P1 complete; eligible for one SHA-stamped validation run.**
10. **P2 (post-validation):** verifier sandboxed execution → native tool calling → per-task budgets → bounded disagreement → replay suite → audit-confirm classification → EnvMap hardening → full promotion eval.

---

## 19. Final direct recommendations

1. **What should we do first?** Provenance (so all later runs are reproducible), then the mount isolation and the signal-receipt fix — the receipt fix kills the single largest measured waste for ~15 lines.
2. **What should we delete first?** The solver-requested/silent reconfiguration behavior (neutralize in P0, delete in P1); then proof_contract's task-family analyzers.
3. **Biggest current harness cap?** Context starvation compounded by the verifier's lack of execution power. Starvation blocks the solver from seeing state; read-only verification blocks honest judgment of behavioral tasks.
4. **Biggest evidence-integrity issue?** No code provenance — the flagship batch's code is unrecoverable, so its conclusions are unfalsifiable. Fix before any run.
5. **Biggest model-capability unknown?** Whether gcode-to-text and video-processing are genuine model limits or artifacts of parse-burn + false-clean termination — currently unknowable; a clean rerun decides it. raman-fitting and filter-js robustness are the clearest true-model-limit candidates.
6. **When should we run the next VM batch?** Only after the full P0 matrix is green (step 6). Ideally after P1 too, so the run is interpretable end-to-end.
7. **What should the next batch include?** The same 13 tasks as sentinels + the P0/P1 sentinel replays, one SHA-stamped run, full raw traces + model IO, verifier packets persisted, effort/model held constant for comparability.
8. **What would prove the harness is closer to model-limited?** A valid-row batch with zero starvation/silent-loss/unprobed-fact/fallback receipts, verifier inspection enabled, and every non-pass row carrying an audit-sustained classification — where remaining failures are wrong *work* on fully-exposed tasks.
9. **What would prove we are still fooling ourselves?** Any recurrence of silent no-ops, any fabricated verdict/default, any new model_limit label a trace audit overturns, any solver access to /task or /tests, or a verifier false-clean with inspection enabled.

---

*End of canonical implementation plan. Amend this document before deviating from it.*
