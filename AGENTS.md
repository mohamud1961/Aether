# AGENTS.md

## Mission

Build the best possible agentic harness for TerminalBench through systematic experimentation.

## Current Stage: Eval-First Harness Reset

The project is now in an eval-first reset stage. The strategic source of truth is the 5.4 Pro ordered-roadmap direction: promotion authority must move from packets, route manifests, and trace prose to benchmark-grade eval evidence.

Current priorities, in order:

1. Establish a benchmark-native sandbox/workspace contract for certified runs.
2. Build a real task-pack + verifier/grader + result-row eval substrate.
3. Build the first certified eval core before resuming variant work.
4. Use public benchmarks as calibration/audit surfaces, not as the inner optimization loop.
5. Iterate with private or sourced failure-targeted homolog evals, regression sentinels, and scored keep/kill decisions.

Broad packets are no longer the main operating unit. Use long-running Codex Goals for execution. A Goal may contain sub-goals owned by workers, but each goal still needs an objective, entry criteria, exit criteria, evidence outputs, and stop conditions.

## Codex Goal Governance

Goals are intentionally long-running execution containers. They may adapt as evidence arrives, but they must not silently redefine success.

Every serious Goal should declare:

- objective;
- scope and out of scope;
- entry criteria;
- exit criteria;
- evidence outputs;
- stop conditions;
- escape-hatch protocol;
- review gate: `none | adversarial_only | codex_review_skill | codex_review_skill_plus_adversarial`;
- blocked/out-of-scope escalation triggers.

### Orchestrator Handoff Requirement

When an orchestrator creates, delegates to, resumes, or materially redirects a
thread or subagent, that worker must hand its result back to the originating
orchestrator before the work is considered closed.

The orchestrator must require each worker handoff to include:

- final status: complete, partial, blocked, or invalid due to environment;
- objective and scope actually completed;
- files changed and ownership boundaries respected;
- requirement-by-requirement or plan-item disposition;
- tests, commands, and evidence paths;
- review findings, accepted fixes, and consciously rejected findings;
- unresolved work, blockers, risks, and exact recommended next action;
- whether any process, container, VM, server, credential home, or other
  external state remains active;
- a persisted `RAW_LEDGER_UPDATE` when the work was material;
- a delivery receipt showing the handoff was explicitly sent back to the
  originating orchestrator thread, including the target thread ID, tool used
  when available, and success/error result.

Subagents hand off to their thread lead. Thread leads integrate and review those
handoffs, then hand one consolidated result back to the originating
orchestrator. Workers must not treat a user-facing summary, an idle thread, a
final answer in their own thread, a `codex_delegation` block that was not sent
to the originating thread, or files appearing in the shared checkout as a
substitute for this handoff.

After receiving all required handoffs, the orchestrator must independently
inspect the live tree and evidence, reconcile conflicting claims, and report:

- what was implemented;
- how much of the approved plan is complete;
- what validation passed or failed;
- what remains;
- the current project/gate status;
- the next concrete action.

### Goal Escape Hatch

A Goal may mark a subtask as `blocked`, `partial_complete`, `incomplete_known_bad_input`, `invalid_due_to_environment`, `blocked_external_dependency`, or `out_of_scope` only with evidence.

The Goal may propose changing its objective or exit criteria, but it may not silently lower success criteria. A material objective change is out of scope for the active Goal unless it is already covered by the approved Goal text. Record the proposed change as a follow-up decision or next Goal; do not pause the active Goal waiting for approval.

Escape-hatch use must record:

- what failed;
- evidence path or command output;
- what was tried;
- why continuing would waste effort or damage evidence;
- impact on the overall Goal;
- what remains complete;
- whether a follow-up Goal or owner decision is recommended.

### No Mid-Goal Approval Waits

Goal creation is the approval to execute the declared objective from start to closeout. Do not introduce additional human/principal approval gates inside an active Goal.

If a Goal hits a missing dependency, unavailable backend, impossible example, unclear authority boundary, or material objective change, the orchestrator should use the escape hatch: finish the current Goal as `blocked`, `partial_complete`, `invalid_due_to_environment`, or `out_of_scope` with evidence. It should not keep polling, rerunning, spawning agents, or repeatedly posting "waiting for approval" updates.

The blocked/partial closeout must include:

- decision or follow-up recommended;
- why the active Goal cannot continue under its approved scope;
- evidence paths;
- exact consequences of continue/retry/revise in a future Goal;
- whether any VM, server, process, or agent remains running.

Never leave a Goal running solely to wait for approval. If the Goal cannot produce the requested evidence, close it honestly as blocked/partial and hand off the next concrete action.

### Review Gates

The orchestrator or principal chooses the review gate at Goal creation based on task risk.

- `none`: tiny docs-only or mechanical work.
- `adversarial_only`: strategy, eval design, analysis, policy, or trace interpretation.
- `codex_review_skill`: non-trivial code changes where code-review findings are the main closeout risk.
- `codex_review_skill_plus_adversarial`: runner, sandbox, eval substrate, grader, result-row, contamination, promotion, or other measurement-critical code.

When a Codex Review skill/helper is available, use it as the preferred code closeout gate for `codex_review_skill*` goals. Treat review output as advisory: verify findings against the real code, accept or reject each actionable finding with reasons, rerun focused tests after review-triggered fixes, and rerun review until no accepted/actionable findings remain or the remaining findings are consciously rejected.

If the skill/helper is unavailable, record that fact in the evidence handoff and either run the raw `codex review` command when appropriate or escalate to the orchestrator/principal for an alternate review gate.

### Adversarial Closeout

For `adversarial_only` and `codex_review_skill_plus_adversarial` goals, the Goal is not complete until an adversarial reviewer tries to disprove completion.

The orchestrator must either:

- accept the adversarial findings and repair/reclassify the Goal; or
- rebut each material finding with concrete evidence.

Unresolved material findings must be repaired, rebutted with evidence, or cause the Goal to close as partial/blocked with a concrete follow-up recommendation. Do not wait inside the active Goal for approval.

## Rules

1. **No hardcoded task knowledge.** Nothing in `runner/` or core orchestration should reference specific tasks by name.
2. **Log everything.** Every run must produce a trajectory that can be analyzed later.
3. **Report material work to the research ledger.** Significant research, decisions, failures, experiment outcomes, and implementation changes must emit a `RAW_LEDGER_UPDATE` handoff for historian review.
4. **Commit in coherent slices.** Do not let work accumulate into one giant end-of-task commit when a smaller logical checkpoint is already complete.
5. **Keep multi-agent work governed.** Use `GOVERNED_MULTI_AGENT_OPERATING_MODEL.md` and `tracking/collab/` for structured collaboration artifacts instead of ad hoc shared chats.


## Experiment Discipline

Move fast, but make every experiment measurable.

- No new variant may be created without a target eval, a predicted score delta, and named regression sentinels.
- When a failure becomes the target of a new lane, create or choose a **proper eval** for that failure before implementing helper mechanisms, unless the work is strictly an environment/runtime repair.
- A proper eval should have a task contract, fixture/workspace, ground truth, deterministic grader when feasible, baseline run, ceiling check, admission level, and score rows.
- For a newly opened failure lane, the default order is: failure classification -> proper eval or targeted diagnostic -> baseline and ceiling -> one small mechanism -> scored board -> keep/kill/iterate. Do not skip straight from traces to helper implementation.
- Promotion requires scored eval evidence. Trace reading is for diagnosis only, not promotion.
- Separate environment/tooling failures from capability failures before proposing architecture changes. Step-budget exhaustion, missing commands, path confusion, timeouts, sandbox errors, and grader failures must be classified as such.
- Every experiment must emit a compact evidence bundle: hypothesis, variant/config, eval rows, scores, trace paths, failure classification, and keep/kill/iterate decision.
- Keep task packets small: inputs, files likely touched, deliverable, exit criterion, and evidence output. Avoid open-ended tasks like "improve the harness."
- Prefer one decisive diagnostic over broad variant exploration.
- The scoreboard is the source of truth for the current best route. Planning documents, route manifests, trace volume, and variant count are not proof of improvement.
- Run regression sentinels with promoted changes, including BFCL/tool-calling and a simple TerminalBench-style verifier row when available.
- Parallel diagnosis is allowed; lane-local promotion is not. Multiple failure families may be investigated or homolog-designed in parallel, but every proposed fix must pass a shared global sentinel board before it can be kept or promoted.
- When multiple fixes target related failures, test the interaction explicitly before promotion: fix A alone, fix B alone, and A+B together. Promote only the board result that is net-positive on target scores, sentinels, contamination/invalid rates, and cost/step budget.
- If a prediction fails, record the failed prediction. Do not silently reinterpret the variant as successful.
- Orchestrators may still propose new variants, but only against an eval-governed failure class with predicted score movement and named sentinels. Variants are still allowed; unguided variant fishing is not.
- New variants and helpers are still allowed, but they must be attached to a proper eval, a baseline score, a ceiling check when feasible, and explicit regression sentinels before implementation begins.
- Agents may propose evals, variants, interpretations, and admission decisions inside an approved Goal. Benchmark-critical eval contracts, ground truth, and promotion to certified status still require the selected review gate and evidence bundle, but they should not create ad hoc mid-Goal approval waits. If the decision is outside the approved Goal scope, emit it as a follow-up Goal recommendation.

## Eval-First Reset Rules

- Do not open broad continuation packets. Use bounded goals or lanes with explicit entry/exit criteria.
- Do not create or promote variants before the relevant eval substrate exists.
- Do not treat packet-specific eval runners as a durable eval suite until they are migrated or replaced by task packs with verifiers, result rows, contamination labels, and scoreboards.
- Certified TerminalBench-style/file/verifier evals must run in benchmark-native Linux/container conditions. Local `sandbox_type=none` runs are debug-only unless explicitly admitted as no-model/unit contract checks.
- Azure VM Docker is an on-demand eval backend, not an always-on service. Agents that start or use the VM for eval/build work must record whether the VM should remain running for active jobs. If no active job needs it, deallocate it at handoff with `scripts/deallocate_harnesseng_vm.sh` when Azure CLI access is available, and report the lifecycle action. If the current sandbox cannot reach Azure control-plane APIs, record that limitation and require Mac-side/manual execution of the script.
- Azure VM auto-shutdown is a cost-safety guardrail, not the primary lifecycle mechanism. Configure it with `scripts/configure_harnesseng_vm_autoshutdown.sh` from a normal Azure-authenticated terminal. Do not rely on guest OS shutdown alone as proof of Azure deallocation.
- Custom evals are required. Do not rely only on cloned public benchmark rows. Public benchmarks are calibration and audit surfaces; private/sourced/custom homolog evals are the main iteration surface.
- Custom evals must preserve real failure pressure: messy files, realistic paths, shell constraints, verifier scripts, red herrings, noisy outputs, and environment contracts. Clean toy evals stay exploratory.
- Benchmark-derived custom evals must abstract the failure family, not copy the public row. Change names, values, layouts, distractors, and fixtures while preserving causal structure.
- Original custom benchmark-grade evals are also required. Do not limit the suite to benchmark-derived homologs. Build our own messy repo/verifier/file-system tasks from sourced or synthetic-realistic environments.
- Homolog-generated evals must be validated end-to-end before replay is used for optimization. First prove the homolog naturally reproduces the failure pressure; then create replay checkpoints near the failure point for fast mechanism/model comparison.
- Every diagnostic/certified eval needs a ceiling check, a baseline run, at least one known-bad failing case, contamination checks, and deterministic grading where feasible.
- Trace reading must classify failures before mechanism work. At minimum classify: environment/runtime, provider, tool contract, path/cwd, schema/parsing, evidence acquisition, reduction/selection, verification/grading, model capability, or unclear.
- Important trace conclusions need exact trace paths and event citations. If evidence is insufficient, say `UNCLEAR` and build a narrower diagnostic.
- For non-trivial model-backed failures, prefer a Certified Trace Diff Workbench before mechanism work. The workbench is an action/state/verifier diff, not a prose diff. It should compare baseline/candidate result rows, traces, artifact bundles, environment manifests, cwd/path, tool call names and arguments, tool exit codes, normalized tool output summaries, files read/written, file hashes/deltas, verifier outputs, hidden grader outputs, final answers/artifacts, contamination labels, and reason codes. Assistant text and provider-visible reasoning telemetry may be used only as supporting hints; do not diff them as primary evidence. Normalize or ignore timestamps, container IDs, absolute temp paths, token-level text changes, and other technical drift. It should emit a divergence report, failure classification, replay checkpoint candidates, and hypothesis seed. Manual trace reading remains allowed, but hard conclusions should be backed by structured diff evidence where possible.
- The Time-Travel Replay Engine is not the immediate blocker. Capture replay-enabling data now where cheap: tool input/output, cwd, environment manifest, file hashes or deltas, grader output, and visible model messages. Build full resume/fork replay only after real eval throughput proves it is needed.
- Replay is part of the workflow from the beginning as capture/checkpoint discipline. Full fork/resume replay is not a substitute for end-to-end eval validity; it is used after a failure surface is validated to jump back near the failure step and compare continuations.
- Micro-step optimization, prompt tournaments, Bayesian bandits, and forked continuation search are future mechanisms, not current proof surfaces. They are only admissible after end-to-end eval validity, trace-diff reliability, replay checkpoint fidelity, and a global sentinel board are in place. Do not use local fork/replay wins as promotion evidence without fresh end-to-end certified reruns.
- Goals can implement the autoresearch loop. A long-running Goal should repeatedly run: score -> diagnose -> hypothesize -> predict -> validate -> compare -> learn, but only inside its approved eval scope.
- If a Goal's prediction fails, record the failed prediction and update the backlog. Do not reinterpret the result into a success after the fact.
- The reset-stage variant/mechanism backlog lives at `tracking/collab/variant_hypothesis_backlog.md`. Add or update mechanism ideas there instead of scattering them across chat or packet memos.

## First Reset Goals

The first goals should happen in dependency order:

1. `certified_sandbox_contract`: benchmark-native Linux/container workspace contract, environment manifest, canonical cwd/root behavior, Python command contract, artifact capture.
2. `eval_substrate`: task-pack schema, fixture setup, verifier/grader execution, result rows, contamination labels, score dashboard.
3. `first_eval_core`: runtime/tool contract evals, one TerminalBench-style verifier repair eval, one filesystem/open-workflow eval, one BFCL/tool-call sentinel, and one structured retrieval/reduction eval.
4. `first_bounded_autoresearch_loop`: choose one failing certified eval, write a prediction, implement one mechanism, run target + sentinels, then promote/kill/pause.

Do not skip ahead to broad variant work before these goals produce scored evidence.


## Research Ledger Reporting

The project maintains a single-writer research ledger under `tracking/ledger/`.

- The historian/ledger agent owns the files in `tracking/ledger/`
- Other agents should **not** write directly to ledger files
- Other agents produce **raw historian inputs only**, not canonical ledger entries
- Other agents **must** persist raw handoffs under `tracking/ledger/inbox/` so updates survive across threads/sessions
- Emitting a raw update only in chat is insufficient if the work happened in another session
- After any material work, write the update with `python3 tracking/ledger/tools/record_update.py` and then include the same raw block in the response when useful
- The historian alone reviews raw handoffs and decides what becomes a ledger entry

Material events include:

- Research synthesis with reusable findings
- Architecture or methodology decisions
- Experiment launches, results, regressions, or invalid runs
- Major implementation changes
- Failures, dead ends, or rejected hypotheses
- New open questions that affect the research direction

Usually **not** material on their own:

- Mechanical formatting changes
- JSON cleanup or schema cleanup with no research consequence
- File moves/renames with no effect on evidence, methodology, or reproducibility
- Routine note rewording
- Incidental refactors unrelated to the harness research questions

If a cleanup changes corpus integrity, evidence availability, bucket counts, reproducibility, benchmark contamination risk, or any research conclusion, then it **is** material and should be reported.

Use this format:

```text
RAW_LEDGER_UPDATE
- actor:
- task:
- event_type: decision | experiment | failure | source_analysis | implementation | regression | open_question
- summary:
- observations:
- inference:
- evidence_paths:
- affected_components:
- decision_change:
- unresolved_questions:
- confidence:
- commit_message:
```

`commit_message` rules:

- Use a real one-line imperative commit subject when the work is ready to commit
- If the slice is not ready, use `HOLD - <reason>` so a later git agent can split or defer it intentionally
- If there are no tracked file changes, use `NONE - no tracked file changes`
- Avoid generic messages like `misc updates`, `wip`, or `changes`
- The message must describe the actual diff, not the hoped-for outcome

Rules:

- Keep updates factual and concise
- Link concrete evidence paths whenever possible
- Separate direct observations from interpretation
- Preserve negative results; do not hide failed ideas
- Treat the handoff as raw input to the historian, not as a final ledger entry

Persistence command:

```bash
cat <<'EOF' | python3 tracking/ledger/tools/record_update.py
RAW_LEDGER_UPDATE
- actor:
- task:
- event_type: decision | experiment | failure | source_analysis | implementation | regression | open_question
- summary:
- observations:
- inference:
- evidence_paths:
- affected_components:
- decision_change:
- unresolved_questions:
- confidence:
- commit_message:
EOF
```

This writes one raw handoff file per update into `tracking/ledger/inbox/`. Do not edit the canonical ledger files directly.
`LEDGER_UPDATE` is still accepted by the recorder for backward compatibility, but `RAW_LEDGER_UPDATE` is the preferred format.

## Aether-2 Continuity Harness — Active Harness Line

`runner/aether2/` is the active harness line for TB2.0 work. Its governing principle:

"The model pilots. The harness instruments. The verifier reflects. The ledger remembers. The grader decides."

No phase gates, doctrines-as-control, action-rewriting, completion vetoes, or harness-side planning may be added to `runner/aether2/`. Any change to `runner/aether2/` must pass `tools/aether2_genericity_check.py` (no hardcoded TB2.0 task names, no benchmark vocabulary in prompts, no task-conditional affordances) before merge.
