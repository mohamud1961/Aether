# Full-corpus study plan (Phases 0–4) — 18 October 2026

**Goal.** Understand exactly where, when and why each model fails to do correct, accurate, complete and truthful
work, including failures of autonomous self-verification, and how each error shaped everything that followed. Find
general-purpose harness improvements that unlock more of every model's capability.
North star: *a harness that unlocks more of every model's capabilities, that does correct, accurate, truthful,
complete work.*

**Authority.** User, 2026-10-18 (night): run Phases 0–4 to completion, then stop. No GPT-6-Astra, Codex or external
reviewers; reviews only by an Opus medium-effort subagent. Offline: no model API calls, no VM, $0 spend, Core
defaults unchanged. Supersedes the 10-17 self-audit's plan section and folds in the 10-18 external reviews (errata
5dcf444c2).

## Phase 0 — defaults (the principal did not answer before sleeping; recorded here, revisable)

1. **"Elite" metric:** per-task macro-averaged correct completion at a declared budget. Reported separately:
   - truthfulness: unsupported completion or testing claims;
   - completeness: requirements met per task;
   - unnecessary abandonment;
   - cost, steps and wall time.

   Baselines are the strongest same-model alternatives available (Terminus-2 + GLM; Codex + GPT-6-Astra where the tasks
   overlap). Results are always reported per model.
2. **Held-out set:** the TB 2.1 tasks never run by Core stay unread and untouched by this study. No trace of a sealed
   task is opened. The 9 dev tasks and the P1 boards are diagnostic only.
3. **Staffing:** I build every mechanical step. Deep dossiers are written by me and by Opus subagents (≤ 3
   concurrent), all to one schema. Haiku is used only for mechanical extraction. One Opus medium-effort subagent
   reviews the calibration batch and the final Phase 4 output.

## Phase 1 — recover and index everything (mechanical)

- **Inventory** every run in every local source:
  - Core traces in the main checkout, the working branch and the other worktrees;
  - Terminus/Harbor trajectories;
  - G4 Codex+GPT-6-Astra and GPT-6-Luna trials;
  - older Aether-2 and Aether-Next evidence;
  - local tarballs.

  Content-hash every run to collapse duplicate copies. Record per run: source, model (from response_model /
  model_name), harness, board, task, arm, outcome, grader assertions, cost, steps, wall time, validity and lineage.
  Blob-only and VM-only runs are listed as *known, not local*.
- **Timelines** for every run (no judgement): a numbered step list. Each step has:
  - the full reasoning text, with empty-reasoning turns marked;
  - content, tool name and arguments;
  - the tool result (long ones kept whole in a side file);
  - every artifact write, with path, content hash and content (or a diff to the previous version);
  - check-like commands and their outputs;
  - finish claims;
  - context edits and trims;
  - per-turn request size and context tokens.
- **What the model saw:** project-mode context is rebuilt deterministically from the history. CLM context is rebuilt
  from the recorded edits and checked against the recorded request size. Turns that cannot be rebuilt within 5% of
  the logged request characters are flagged *input unverified*.

## Phase 2 — grader audit and our own verdicts

- Per task family: read the grader and the reference solution. Where runnable offline, test the grader against the
  oracle, mutated wrong outputs and legitimate alternatives. Mark the grader trusted, flawed (with the defect) or
  unknown.
- **Own verdict** per run, beyond the grader: judge the final artifact from task text, expected results, reference
  solution and domain facts, recording basis and confidence. Disagreements with the grader are findings. Runs with an
  invalid grader or infrastructure stay in the process analysis and are excluded only from score comparisons.

## Phase 3 — deep dossiers for every eligible run (the core deliverable)

**Requirement.** Every eligible run gets an evidence-linked dossier, step by step. It is **not a label and not only
the first error**:

1. **Error chain.** Every error, not just the first. For each: the exact step; the artifact or belief that became
   wrong; what the model saw just before (rebuilt input); what its reasoning said (or that none was logged); and how
   it propagated. Which later steps, checks, beliefs and artifacts did it shape? Did it compound, get masked, partly
   repair or cause new errors?
2. **Root-cause hypotheses.** Model, harness, tool or evaluation cause. Competing explanations, with the
   observation that would disconfirm each. No assumed explanation.
3. **Self-verification.** What could have been checked, what was checked, and whether each check was valid (would it
   fail on the wrong artifact, and pass the right one?). Why the error escaped. Whether checks were derived from the
   same belief that produced the error.
4. **Evidence → action.** Was the correct information available, delivered, compared, visibly understood and acted
   upon? Name the first broken link.
5. **Recovery.** Mistakes recognised and fixed; contradictory evidence ignored; correct work damaged (correct →
   wrong transitions).
6. **Truthfulness and completeness.** Every task requirement against the final artifact (our verdict and the
   grader's). Every completion or testing claim against the evidence for it.
7. **Reasoning analysis.** Beliefs stated and when they became wrong; doubts raised and dropped; decisions taken with
   zero reasoning; the link from reasoning to action (reasoning right, artifact wrong?).
8. **Impact overall.** How the run's outcome follows from its error chain; steps, time and tokens spent downstream of
   each error.
9. **Success contrast.** For passing runs: what they did at the same decision points where failing runs went wrong.
10. **Uncertainty.** Every causal claim cites steps, tool outputs or artifact versions, or is marked *cannot be
    established*.

**Acceptance criteria.**
- (a) Every eligible run has a dossier, or a recorded reason it cannot (no trace, unreadable, sealed).
- (b) Every causal claim cites evidence or is marked uncertain.
- (c) Every failed run is paired with a passing run on the same task where one exists.
- (d) A calibration batch (~40, stratified across task families, models, outcomes, harmful repairs and invalid runs)
  is independently re-derived by an Opus medium-effort reviewer. Disagreements are adjudicated, and the schema is
  fixed before scaling.
- (e) The output is a **mechanism report**: recurring mechanisms across tasks and models, especially of autonomous
  self-verification. Each has its dossiers, counterexamples, prevalence with denominators, and candidate
  general-purpose harness improvements checked against the two north-star tests (helps every model; improves the work
  itself).

**Eligibility and order.** All solver runs with a trace are eligible, except sealed held-out tasks. Fixed-state
benches (A1, R1, Q1, J1, S1–S3, T1 Stage 1) are analysed as probes, not runs. Order:
1. Core TB 2.1 boards;
2. P1 boards;
3. Terminus;
4. G4 Codex+GPT-6-Astra and GPT-6-Luna;
5. older Aether-2 and Aether-Next.

Coverage is reported at each stage. If usage stops, work resumes from `audit_output/corpus_study_20261018/PROGRESS.md`.

## Phase 4 — rank and design (then stop)

- **Error budget and opportunity budget**, with overlap. Which interventions could prevent or recover which failures.
- **Hypothesis register** with disconfirming predictions.
- **Ranking** by prevalence × recoverability × breadth across models and tasks × the north-star tests.
- **One discriminating experiment**, designed and drafted as a pre-registration with predictions and stopping rules.
  **Not run**; it awaits the principal's OK.
- Opus medium-effort review of the Phase 4 output; then stop and report.

## Amendment 1 (2026-10-18, after the principal's staffing change and the ChatGPT review of 65459814c)

**Staffing.** Context gathering (greps, evidence extraction, per-run evidence packets) is done by **Haiku** subagents,
not Opus (user). Analysis that Haiku cannot do is done by me, or by an Opus writer working **only from the Haiku
packet**, with narrow look-ups. Reviews go to the **Codex thread** `codex://threads/01a14c16-bf09-7550-8361-12757d6e2838`,
replacing the Opus medium-effort reviewer. Max 3 concurrent subagents.

**Corrections accepted.**
1. **Grader classification.** Each grader file gets an effect table using these classes: false rejection
   demonstrated / false acceptance demonstrated / incomplete coverage / ambiguous specification / version mismatch /
   unverified. Each class lists the **historical outcomes it affects**. "6 of 9 flawed" is withdrawn as a headline;
   what counts is how many recorded outcomes each defect changes.
2. **Input reconstruction.** A character-count match within 5% is supporting evidence, not byte-identity. The 450 GLM
   turns, the 55 runs without call logs and all ATIF/G4 runs (input = trajectory prefix) stay labelled
   *unverified / inferred*.
3. **Reasoning telemetry.** "59% of Core+GLM turns logged no reasoning text, vs 1/246 under Terminus" is a
   logging/format observation. It is not evidence of no reasoning, and not a behavioural conclusion. Comparing it with
   outcomes needs provider format, requested effort and turn format held equal.
4. **Calibration quality gate (before scaling).** A calibration dossier counts only if:
   - its first error is supported by an observation or an artifact version;
   - what the model saw matches the recorded request (or is marked inferred);
   - each check is judged for both false acceptance and false rejection;
   - demonstrated and plausible links are kept separate;
   - a matched success is studied, or the missing control is named;
   - an adversarial challenge cannot overturn its core claim.

   The gate has three parts:
   - (a) **adversarial challenge**: a reviewer gets the conclusion and hunts for the strongest contradicting trace
     evidence;
   - (b) **blind re-derivation** of at least 5 dossiers by a writer who has not seen the original;
   - (c) the share of causal conclusions that survive is reported.

   Two same-model agents agreeing is not called independent validation.
5. **Harness integrity triaged separately.** The *fabricated-observation* finding (several JSON objects in one reply
   accepted, so invented tool results entered history) gets a bounded deterministic reproducer and a source-level
   audit before it is used as a mechanism.
6. **Contamination.** Runs with a benchmark leak stay in the process corpus, labelled, and out of clean score
   comparisons. The leak scan reports which access routes it inspected and which it could not ("no further leak found
   by the scan", not "no leak occurred").
7. **No single-story conclusions.** "Every failure had a self-confirming check" describes the inspected subset only.
   Allowed failure types include valid checks ignored or rewritten, harmful checks, and no verification. The research
   question stays: *under what conditions does verification independently establish that the deliverable meets the
   requirements, and when does that improve final work rather than harm it?*
8. **Cost attribution.** Steps after an error are not automatically "wasted". Attributing cost needs a justified
   counterfactual.
9. **Dossiers may say "cannot establish a mechanism from this trace".** The output is a set of reproducible mechanism
   findings: observed failure, trace evidence, alternatives, discriminating evidence, applicability, counterexamples,
   intervention opportunity, uncertainty. It is not page count. The research's own effort (subagent tokens, time) is
   recorded.
