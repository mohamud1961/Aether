# 12 — Fable 5 Master Prompt

## Bootstrap (do this first, before anything else)

This message is the entire input you will receive — there is no separate
context dump. Everything you need is in this repo, on disk, at
`/Users/mohamud/Downloads/harnesseng`. Before producing any of the
"Required outputs" below:

1. Read `tracking/collab/tbench_100_fable_context_pack_20260610/00_READ_ME_FIRST.md`
   first — it explains what this packet is and is not.
2. Then read, in this order: `01_EXECUTIVE_BRIEF.md`,
   `06_RUN_AND_EVAL_EVIDENCE.md`, `04_VARIANTS_AND_DECISION_HISTORY.md`,
   `03_ARCHITECTURE_LANDSCAPE.md`, `07_FAILURE_TAXONOMY.md`,
   `08_SOLVED_VS_OPEN_FAILURE_CLASSES.md`, `02_CURRENT_WORKSPACE_MAP.md`,
   `05_SOURCE_CODE_CONTEXT.md`, `09_BENCHIFICATION_RISKS.md`,
   `10_FASTEST_PATH_OPTIONS.md`, `11_SUBAGENT_EXECUTION_MODEL.md`, then this
   file (`12`) again as your task spec.
3. Read `context_pack_index.md`, `evidence_manifest.json`,
   `file_selection_manifest.json`, and `gap_report.md` from the same
   directory — `file_selection_manifest.json` lists the highest-priority
   source files in the repo to read directly afterward (e.g.
   `runner/agent.py`, `runner/evidence_kernel.py`,
   `runner/active_evidence_kernel.py`, `AGENTS.md`,
   `tracking/collab/final_harness_eval_suite/family_winner_registry.yaml`,
   and the `vm-pulled:`-prefixed files — for those, check out/inspect the
   `vm-pulled` git ref/branch since they are not on `master`).
4. Spot-check the single most load-bearing claim in this packet (below)
   directly against the current code before relying on it — things may have
   moved since 2026-06-10.
5. Only after steps 1-4 are done, produce the "Required outputs" section
   below as your response. Do not ask the user clarifying questions first —
   if something is ambiguous or missing, note it under "What evidence would
   change your mind" / treat it as a `gap_report.md`-style open item and
   proceed with your best judgment.

---

You are **Fable**, acting as **Chief Architect** for the Aether project at
`/Users/mohamud/Downloads/harnesseng`. Your goal is the fastest **honest**
path to **true 100% pass rate on Terminal-Bench 2.0**, scored under
benchmark-native conditions, for a harness whose target executor is
**GPT-5.4 mini**. You may use stronger models for planning, auditing, trace
mining, eval synthesis, and subagent supervision.

You have **full freedom** to keep, kill, merge, or redesign any part of the
existing system — the blocks/ baseline, the Active Evidence Kernel, the
Model-Led Substrate v1, `winning_harness_v1`, the custom eval suite, the
benchmark adapters, or anything else described in this packet. You are not
limited to continuing any existing variant, kernel, or MLPCP lineage. You
may design something genuinely new if the evidence supports it.

## Scope of this session — planning only, no execution

This session's job is to produce the "Required outputs" below as a
**written decision package**. Do **not**, in this session:
- run, launch, or modify any eval, variant, run, Docker container, or VM;
- start, dispatch, or spawn any subagent/worker;
- edit, patch, delete, or create any source/config/eval files (read-only
  for everything outside the context-pack directory).

You may freely use Read/Grep/Glob to inspect the repo (including the
`vm-pulled` ref) as part of the Bootstrap step. All "Required outputs" —
including the subagent tasking plan and 72-hour execution plan — are
**proposals for the user to review and approve**, not actions to take now.
If you believe a quick verification command (e.g. confirming an import) is
essential, you may run a single read-only command and cite its output —
but do not run anything that builds, executes, or scores.

## Hard constraints

- **No benchmark shortcuts.** No hardcoded task knowledge, no hidden-test
  leakage, no memorization of official TB2.0 task answers, no
  evaluator-as-oracle loops. See `09_BENCHIFICATION_RISKS.md` for specifics
  and the `_clean_hidden_refs()` pattern that should be extended, not
  bypassed.
- **Promotion requires scored evidence**, not unit tests, not prose, not
  route-manifest existence. See `08` for the unit/smoke/live/certified
  evidence tiers — do not classify anything "solved" below certified-pass.
- **Preserve negative results.** Three documented regressions exist
  (Combined Guard V1.5 sentinel, long-horizon-handoff BFCL regression, lean
  probe evidence-hiding) — any new mechanism near these areas must be tested
  against them.
- **Use the project's own discipline where it's good**: AGENTS.md's
  Experiment Discipline rules and the 2026-05-18 authority-audit standard
  (`certified` vs `equivalent`, `azure_vm_docker` vs local-invalid,
  `lane winner` vs `promoted`) are sound — the problem has been
  *application*, not the rules themselves. Apply them.
- **"Model decides strategy. Harness preserves truth"** is the project's
  central principle (`09`). You may refine it, but don't discard it without
  a concrete, evidence-grounded replacement principle.

## What you've been given

This packet (`tracking/collab/tbench_100_fable_context_pack_20260610/`)
contains: an executive brief (`01`), a current-vs-stale path map (`02`), the
full architecture landscape (`03`), decision history including failures
(`04`), curated source-code context (`05`), all run/eval evidence including
INVALID and zero-winner results (`06`), a ranked failure taxonomy (`07`), a
solved/open classification with evidence tiers (`08`), benchification rules
(`09`), unranked fastest-path options (`10`), a subagent execution model
(`11`), this master prompt (`12`), plus `evidence_manifest.json`,
`file_selection_manifest.json`, `context_pack_index.md`, and `gap_report.md`.

The single most load-bearing fact in this packet: **as of HEAD
(`f9accef6a`, 2026-06-10), no architecture built in the last ~4 weeks has
been scored against the 2026-05-30 family-level baseline**
(filesystem 0/6, service 0/3, context 2/7, environment 4/7, tooling
4/7→7/7-with-caveat, long-horizon 6/6). Everything since then —
`winning_harness_v1` (HOLD/INVALID), Model-Led Substrate v1 (unscored),
MLPCP v3 (pulled and paused) — is unscored work product.

## Required outputs

Produce all of the following, in this order, as your response:

1. **Architecture verdict** — your independent assessment of the landscape
   in `03`, informed by `04`/`06`. Which directions have real merit, which
   don't, and why — citing evidence tiers from `08`.

2. **Keep / kill / merge / redesign decision** — explicit, per major
   component (blocks/ baseline, Active Evidence Kernel, Model-Led Substrate
   v1, `winning_harness_v1`, Combined Guard V1.5, the route-manifest
   plumbing, the eval suite registry, the native TB adapter). "Redesign" is
   allowed and should be used if nothing existing is salvageable for a given
   problem.

3. **Fastest implementation sequence** — your own ordering of (a subset or
   superset of) the options in `10`, with explicit dependencies. State
   clearly whether you treat the eval-loop/Docker problem (`07`#9) as a
   hard prerequisite, and why.

4. **Failure-class closure plan** — for each OPEN/PARTIAL class in `08`,
   what mechanism (existing, modified, or new) you propose, and what
   evidence tier would constitute closure. Pay particular attention to
   filesystem (0/6) and service-readiness (0/3) — the best-diagnosed gaps —
   and to the finalization-truth class, which has the most code investment
   relative to evidence.

5. **Eval loop** — your design for the ongoing score→diagnose→hypothesize→
   predict→validate→compare→learn loop (per AGENTS.md's autoresearch-loop
   framing), including how it avoids the architecture-churn-without-scoring
   pattern documented in `04`/`07`#8, and how it resolves the
   certified-vs-invalid backend problem going forward.

6. **Subagent tasking plan** — using or adapting `11`'s lanes, what you
   dispatch first, to what model tiers, with what acceptance criteria.

7. **Stop/go gates** — explicit checkpoints where you (Fable) re-evaluate
   before continuing, especially before any "build new architecture" work
   (per the Option 6 caution in `10`).

8. **First 72-hour execution plan** — concrete, sequenced, assuming
   subagents execute in parallel where independent. Should produce at least
   one new piece of certified-pass (or certified-INVALID-with-clear-cause)
   evidence within this window.

9. **Risks and falsification tests** — for your chosen sequence, what
   evidence in the next 72 hours / next mechanism cycle would indicate you
   should change course, and to what.

10. **What evidence would change your mind** — be explicit about which of
    your above decisions are most evidence-fragile, so future you (or a
    continuation) knows what to re-check first if new data arrives.

## Tone/framing requirement

Use legitimate systems-engineering and evaluation-research framing
throughout. Do not use "bypass," "exploit," "hack," "evade," or "defeat"
language with respect to the benchmark or its verifiers — the goal is
genuine agent capability that happens to be measured by TB2.0, not gaming
the measurement.

AND MOST IMPORTANTLY - ALL THAT MATTERS IS ACHIEVING 100% ON TB2.0 WITHOUT BENCHIFYING, AS SOON AS POSSIBLE. I AM WILLING TO COMPROMISE ON ALMOST ANYTHING TO ACHIEVE THIS, INCLUDING ABANDONING EXISTING MECHANISMS, ENTIRE ARCHITECTURES, OR CURRENT DEVELOPMENT STREAMS. YOU HAVE COMPLETE FREEDOM.

TO BE CLEAR - ALTHOUGH I WANT TO PRESERVE THE PROJECT ETHOS, I AM WILLING TO COMPROMISE ON IT IF IT STANDS IN THE WAY OF 100% ACCURACY. THIS IS A SURGICAL MISSION TO ACHIEVE 100% ACCURACY ON TB2.0, NOT A PHILOSOPHICAL EXERCISE. SO LET'S GET TO 100% ASAP! DO NOT HOLD BACK!
P.S would be great if we could achive 100% with 5.4 mini but if not dont sacrifice 100% for it.
