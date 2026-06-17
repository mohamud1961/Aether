# Codex Goal Governance

Derived from the Goal governance, experiment discipline, and eval-first reset rules in
the project's operating model. Private-infra references and suite-specific content
have been stripped; the methodology is generic.

---

## Codex Goal Governance

Goals are intentionally long-running execution containers. They may adapt as evidence
arrives, but they must not silently redefine success.

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

When an orchestrator creates, delegates to, resumes, or materially redirects a thread
or subagent, that worker must hand its result back to the originating orchestrator
before the work is considered closed.

The orchestrator must require each worker handoff to include:

- final status: complete, partial, blocked, or invalid due to environment;
- objective and scope actually completed;
- files changed and ownership boundaries respected;
- requirement-by-requirement or plan-item disposition;
- tests, commands, and evidence paths;
- review findings, accepted fixes, and consciously rejected findings;
- unresolved work, blockers, risks, and exact recommended next action;
- whether any process, container, server, credential home, or other external state
  remains active;
- a persisted `RAW_LEDGER_UPDATE` when the work was material;
- a delivery receipt showing the handoff was explicitly sent back to the originating
  orchestrator thread, including the target thread ID, tool used when available, and
  success/error result.

Subagents hand off to their thread lead. Thread leads integrate and review those
handoffs, then hand one consolidated result back to the originating orchestrator.
Workers must not treat a user-facing summary, an idle thread, a final answer in their
own thread, or files appearing in the shared checkout as a substitute for this handoff.

After receiving all required handoffs, the orchestrator must independently inspect the
live tree and evidence, reconcile conflicting claims, and report:

- what was implemented;
- how much of the approved plan is complete;
- what validation passed or failed;
- what remains;
- the current project/gate status;
- the next concrete action.

### Goal Escape Hatch

A Goal may mark a subtask as `blocked`, `partial_complete`,
`incomplete_known_bad_input`, `invalid_due_to_environment`,
`blocked_external_dependency`, or `out_of_scope` only with evidence.

The Goal may propose changing its objective or exit criteria, but it may not silently
lower success criteria. A material objective change is out of scope for the active Goal
unless it is already covered by the approved Goal text. Record the proposed change as a
follow-up decision or next Goal; do not pause the active Goal waiting for approval.

Escape-hatch use must record:

- what failed;
- evidence path or command output;
- what was tried;
- why continuing would waste effort or damage evidence;
- impact on the overall Goal;
- what remains complete;
- whether a follow-up Goal or owner decision is recommended.

### No Mid-Goal Approval Waits

Goal creation is the approval to execute the declared objective from start to closeout.
Do not introduce additional human/principal approval gates inside an active Goal.

If a Goal hits a missing dependency, unavailable backend, impossible example, unclear
authority boundary, or material objective change, the orchestrator should use the
escape hatch: finish the current Goal as `blocked`, `partial_complete`,
`invalid_due_to_environment`, or `out_of_scope` with evidence.

The blocked/partial closeout must include:

- decision or follow-up recommended;
- why the active Goal cannot continue under its approved scope;
- evidence paths;
- exact consequences of continue/retry/revise in a future Goal;
- whether any server, process, or agent remains running.

### Review Gates

The orchestrator or principal chooses the review gate at Goal creation based on task risk.

- `none`: tiny docs-only or mechanical work.
- `adversarial_only`: strategy, eval design, analysis, policy, or trace interpretation.
- `codex_review_skill`: non-trivial code changes where code-review findings are the main closeout risk.
- `codex_review_skill_plus_adversarial`: runner, sandbox, eval substrate, grader, result-row, contamination, promotion, or other measurement-critical code.

When a code review skill/helper is available, use it as the preferred code closeout gate
for `codex_review_skill*` goals. Treat review output as advisory: verify findings against
the real code, accept or reject each actionable finding with reasons, rerun focused tests
after review-triggered fixes, and rerun review until no accepted/actionable findings remain
or the remaining findings are consciously rejected.

### Adversarial Closeout

For `adversarial_only` and `codex_review_skill_plus_adversarial` goals, the Goal is
not complete until an adversarial reviewer tries to disprove completion.

The orchestrator must either:

- accept the adversarial findings and repair/reclassify the Goal; or
- rebut each material finding with concrete evidence.

Unresolved material findings must be repaired, rebutted with evidence, or cause the Goal
to close as partial/blocked with a concrete follow-up recommendation.

---

## Experiment Discipline

Move fast, but make every experiment measurable.

- No new variant may be created without a target eval, a predicted score delta, and named regression sentinels.
- When a failure becomes the target of a new lane, create or choose a **proper eval** for that failure before implementing helper mechanisms, unless the work is strictly an environment/runtime repair.
- A proper eval should have a task contract, fixture/workspace, ground truth, deterministic grader when feasible, baseline run, ceiling check, admission level, and score rows.
- For a newly opened failure lane, the default order is: failure classification → proper eval or targeted diagnostic → baseline and ceiling → one small mechanism → scored board → keep/kill/iterate. Do not skip straight from traces to helper implementation.
- Promotion requires scored eval evidence. Trace reading is for diagnosis only, not promotion.
- Separate environment/tooling failures from capability failures before proposing architecture changes.
- Every experiment must emit a compact evidence bundle: hypothesis, variant/config, eval rows, scores, trace paths, failure classification, and keep/kill/iterate decision.
- Keep task packets small: inputs, files likely touched, deliverable, exit criterion, and evidence output.
- Prefer one decisive diagnostic over broad variant exploration.
- The scoreboard is the source of truth for the current best route. Planning documents, route manifests, trace volume, and variant count are not proof of improvement.
- Run regression sentinels with promoted changes.
- Parallel diagnosis is allowed; lane-local promotion is not.
- When multiple fixes target related failures, test the interaction explicitly before promotion.
- If a prediction fails, record the failed prediction. Do not silently reinterpret the variant as successful.

---

## Eval-First Reset Rules

- Do not open broad continuation packets. Use bounded goals or lanes with explicit entry/exit criteria.
- Do not create or promote variants before the relevant eval substrate exists.
- Custom evals are required. Do not rely only on public eval rows. Public eval suites are calibration and audit surfaces; custom homolog evals are the main iteration surface.
- Custom evals must preserve real failure pressure: messy files, realistic paths, shell constraints, verifier scripts, red herrings, noisy outputs, and environment contracts.
- Every diagnostic/certified eval needs a ceiling check, a baseline run, at least one known-bad failing case, contamination checks, and deterministic grading where feasible.
- Trace reading must classify failures before mechanism work. At minimum classify: environment/runtime, provider, tool contract, path/cwd, schema/parsing, evidence acquisition, reduction/selection, verification/grading, model capability, or unclear.
- Important trace conclusions need exact trace paths and event citations. If evidence is insufficient, say `UNCLEAR` and build a narrower diagnostic.
- Goals can implement the autoresearch loop. A long-running Goal should repeatedly run: score → diagnose → hypothesize → predict → validate → compare → learn, but only inside its approved eval scope.
- If a Goal's prediction fails, record the failed prediction and update the backlog. Do not reinterpret the result into a success after the fact.

---

## Rules

1. **No hardcoded task knowledge.** Nothing in the harness or core orchestration should reference specific tasks by name.
2. **Log everything.** Every run must produce a trajectory that can be analyzed later.
3. **Report material work to the research ledger.** Significant research, decisions, failures, experiment outcomes, and implementation changes must emit a `RAW_LEDGER_UPDATE` handoff for historian review.
4. **Commit in coherent slices.** Do not let work accumulate into one giant end-of-task commit when a smaller logical checkpoint is already complete.
5. **Keep multi-agent work governed.** Use the governed multi-agent model and structured collaboration artifacts instead of ad hoc shared chats.

---

*Source: methodology sections of the project's `AGENTS.md`. Suite-specific references,
private infrastructure scripts, and machine-path content have been removed.*
