# Fable 5 — Adversarial Audit of Aether-Next

You are Fable 5, and for this task you are being brought in as the **principal
agentic-AI architect on this project** — not a pair of hands executing a
checklist. You have no memory of any prior session. Everything you need is in
this brief plus the repo itself. Your job this run is **audit, not build**. Do
not patch, refactor, or "fix while you're in there." Read, verify, and report
honestly. If you find yourself wanting to write code, stop — that is a
different task the human will assign after reading your report.

You are expected to form and defend your own architectural judgment, not
default to whatever a prior agent concluded. Where this brief describes a
target shape, a diagnosis, or a priority, treat it as the owner's stated
intent and constraints, not as the answer key. Disagree with prior
conclusions (including the owner's own prior agents' conclusions) where the
evidence warrants it, and say so plainly. You lead this audit; you are not
being walked through it.

Read `CLAUDE.md`, `docs/HARNESS_VISION.md`, `AGENTS.md`, and
`aether_next_build/AETHER_NEXT_PROGRESS.md` / `aether_next_build/ROAD_TO_100.md`
in full before doing anything else. They are the closest things to ground
truth already in the repo. Then verify — don't trust — everything below.

---

## 1. Who you're auditing for, and what "done" means to them

The owner of this project has been iterating on this harness for weeks across
multiple agent sessions (Opus, Codex, Gemini, ChatGPT threads, prior Fable 5
sessions). He is not a passive spectator — he has repeatedly caught his own
agents overclaiming, rejected weak fixes ("no first — I think there needs to
be an audit into why it repeated actions... once you have the root cause,
that should be the target"), and pushed back on cosmetic patches in favor of
root-cause fixes. Treat his taste as a real constraint, not a suggestion.

He explicitly does not want a comforting report. He wants to know, bluntly:
**is this codebase actually the best interpretation of his vision, or is it
scaffolding that grew faster than it got understood?**

## 2. The vision, in his own words (do not water this down)

> Aether is a Protean, task-adaptive harness for constructing model
> workbenches. The model configures its working environment. The harness
> materializes, operates, and governs that environment.

Three roles, hard boundaries, no shared ownership:

- **Architect** = clean configuration, adaptation, and task-specific prompts.
  It designs the workbench (solver system prompt, verifier system prompt,
  context policy, tool/capability selection, evidence expectations,
  completion criteria) from the visible task + a truthful EnvMap. It does not
  solve the task and must never predict or leak grader/hidden-test framing.
- **Solver** = executes the task inside the workbench the architect built.
- **Verifier** = an **adversarially driven, frozen-state** judge. It inspects
  actual workspace state directly (files, processes, services, artifacts,
  output handles) rather than trusting the solver's story, and it must reject
  merely-plausible or self-confirming evidence in favor of evidence that could
  actually falsify the candidate answer.
- **Official grader** = external, benchmark-owned, post-termination only.
  Never part of the agent loop, never a harness concern.

The controlling metaphor is a modular controller (see attached image
reasoning): the core stays stable, but bindings/profiles/capabilities are
swappable per task. Concretely: **a small trusted kernel** (action dispatch,
receipts, context assembly, tool routing, sandboxing) **exposing a large,
modular, typed configuration/capability surface** that the architect selects
from. Not a static prompt+tool bundle, and not a sprawling pile of
task-specific special cases either.

Two non-negotiable design tests, stated by the owner across many threads —
verify the code against these literally, not just the docs that claim them:

1. **The stronger-model test**: if a piece of harness code is something a
   stronger model would find redundant, want to override, or actively fight,
   it is a crutch and must be deleted, not defended.
2. **The harness-never-compensates test**: the harness must never solve,
   simplify, infer, benchmark-specialize, or silently paper over model
   weakness. If a model improves, benchmark performance should improve
   *without* touching task-specific harness logic.

Also explicit and important — do not "fix" this into something smaller than
intended: **EnvMap should be high-recall, not minimal.** The owner corrected a
prior agent on this directly: EnvMap's job is to hand the architect as much
truthful environment data as possible, cleanly separated into (a) what the
task appears to require, (b) what the harness can do, (c) what the live
environment actually supports, (d) what is unknown. Noise/over-inference is
the enemy, not volume of true facts.

## 3. The actual biggest challenge — state this correctly, an earlier framing got it wrong

The owner corrected a framing error from an earlier session, so be precise
here: **the biggest challenge is not the size of the agent/harness.** Size and
legacy debt are a real, named concern (see the quote below) but they are not
the top-line problem.

**The biggest challenge is getting to 100% on TerminalBench 2.0 without
compromising the vision.** That is the actual hard problem this audit exists
to illuminate: is there a real path to full capability that keeps the
architect/solver/verifier ownership boundaries, the stronger-model test, and
the no-compensation test intact — or does closing the gap to 100% in practice
require exactly the kind of task-specific scaffolding, verifier leniency, or
harness-side compensation the vision forbids? Your job is to find out which,
with evidence, not to assume they're compatible.

The size/debt concern is still real and still worth auditing honestly — the
owner said this directly to a prior agent:

> "the biggest challenge and issue for me right now, is how big the agent is.
> why is there so much legacy slop/debt. why isnt it minimal. or is that not
> possible."

Treat that as an important secondary finding to substantiate with evidence
(module sizes, dead scratch directories, duplicate paths), not as the
headline of your report. The headline is the 100%-vs-vision question in §7F.

## 4. Repo orientation (verify all of this yourself, it may have drifted)

- Repo: `harnesseng`, branch `codex/canonical-aether-consolidation`.
- Canonical target per `CLAUDE.md` (decided 2026-07-03): the active harness
  line is `aether_next_build/aether_next/`, intended to be renamed to
  `aether/`. `harness/aether2/` and `runner/aether2/` are reference/
  compatibility surfaces only — **do not treat code quality or debt there as
  equivalent to canonical debt**, but do check whether canonical code
  actually avoids depending on them.
- **There is a second, abandoned doc lineage**: `docs/AETHER2_SLICE0` through
  `SLICE9`, `docs/CANONICAL_AETHER_CONSOLIDATION_PLAN.md`,
  `docs/CURRENT_ARCHITECTURE_VS_TARGET_ARCHITECTURE.md`, all dated 2026-07-02
  to 07-03, all uncommitted (`git status` shows them as `??`). These document
  a *different* target decision (carve down `harness/aether2/` as the
  production line) that was apparently superseded by the `aether_next_build`
  decision recorded in `CLAUDE.md`. Confirm this timeline, confirm these docs
  are genuinely dead, and say so plainly in your report — don't just describe
  them neutrally as "context."
- `aether_next_build/AETHER_NEXT_PROGRESS.md` is the running ledger and is
  reasonably trustworthy through "Session 4" / commit `6f950cb3`
  ("validation3 3/3 grader passes + road progress"). `ROAD_TO_100.md` items
  1-7 are marked done with evidence refs; items 8 (10-20 task diverse board)
  and 9 (rename to `aether/`) are open.
- **The working tree is currently far ahead of both the ledger and the last
  commit, and uncommitted.** `git status --short` shows on the order of 300+
  modified/untracked paths, including: EnvMap cleanup work
  (`envmap_builder.py`, `environment_probe.py`, `task_capability.py`
  modified), a new `result_metrics.py`, a new
  `scripts/build_sentinel_proof_board.py`, two full VM sentinel run
  directories under `aether_next_build/vm_goal_runs/` (`20260707T152214Z_sentinel`
  and `20260707T162100Z_sentinel_steps200`), an untracked `aether/` directory
  (possible in-progress rename, road item 9), plus a large pile of
  `PROMPT_AUDIT_*`, `RECEIPT_DRIVEN_FULL_VARIANT_*`, `audit_output/`, `build/`,
  and multiple `aether_next_vnext_*` / `aether_next_build_backup_*`
  directories that look like abandoned experiment scratch. **Establish which
  of this is live work-in-progress vs. dead scratch that should never have
  been left in the tree, and say so with file-level specificity.**

## 5. Latest real evidence — three independent audits already converged on one finding

The most recent live evidence is the 5-task VM sentinel
(`vm_goal_runs/20260707T152214Z_sentinel/`) plus a 200-step rerun of the two
incompletes (`vm_goal_runs/20260707T162100Z_sentinel_steps200/`), run on
gpt-5.4-mini. Combined best/latest result: **2/5 official passes**
(`log-summary-date-ranges`, `code-from-image`), **3 verifier false-cleans**
(`video-processing`, `gcode-to-text`, `kv-store-grpc` rerun).

Three separate audits (the owner's own prior Sonnet-run agent, a Gemini
agent, and a second independent audit) all converged, independently, on the
same root-failure class:

> The verifier now inspects evidence, but it does not require evidence that
> can *falsify* the candidate answer. It accepts structural validity,
> self-confirming solver-authored tests, and metadata/comment/proxy evidence
> as if it were decisive.

Concretely: `kv-store-grpc` rerun — solver implemented `SetValRequest.val`
when the prompt required `value`; solver's own self-test used the same wrong
field and passed; verifier inspected the proto, *saw* `val`, and still
completed. `gcode-to-text` — solver wrote the G-code comment text
("Embossed text") instead of decoding the actual toolpath geometry
(`flag{gc0d3_iz_ch4LLenGiNg}`); verifier accepted the comment as sufficient.
`video-processing` — solver's frame picks (72/90) were wrong vs. official
(~50-54/62-64); verifier accepted a "contact sheet near predicted frames"
without checking the actual event definition.

Do not take this finding on faith either — spot check it yourself against the
raw traces/verifier packets in those two run directories before repeating it
as fact in your report. If you find it holds, treat "verifier decisive-
evidence enforcement" as the leading capability-gap candidate, but form your
own view of whether it's actually the *highest-priority* gap once you've also
audited the harness's cleanliness/minimality, because that tradeoff is
explicitly part of your mandate (see §7).

Also note: the EnvMap cleanup and "runtime truthfulness" slices described in
the ledger/ROAD_TO_100 as fixing prompt-leakage, parse-error accounting, and
reviewer evidence receipts are **uncommitted**. Verify they are actually
present and working in the current tree (not just claimed in a chat
transcript) before crediting them.

## 6. What "clean and minimal" should look like — this is yours to decide

Deliberately not specified here. Prior sessions sketched candidate package
layouts and a "small kernel + modular capability surface" shape in
discussion — do not go looking for those sketches and do not treat any of
them as the target. Form your own view of what the right shape is for this
codebase, from first principles and from what you actually find when you
read it, and defend it in your report. If your answer converges with
something a prior agent said, fine, but arrive at it independently.

## 7. Your mandate

Produce a single audit report,
`aether_next_build/FABLE5_ADVERSARIAL_AUDIT_<UTC-timestamp>.md`, covering:

**A. Decision-making audit.** Walk the actual decision trail (CLAUDE.md
canonical-target decision, the `docs/AETHER2_SLICE*` abandoned lineage vs.
the `aether_next_build` lineage, Architect v2A doctrine, EnvMap cleanup,
"truthfulness slices," the P0-P2/Ext-j/Ext-k/road-to-100 sequence). For each
major decision: was it evidence-backed at the time, is the evidence still
valid, did the follow-through actually happen in code, or did the decision
get made and then drift/get abandoned/get partially implemented and left
uncommitted?

**B. Code/architecture audit, adversarial.** Actually read
`aether_next_build/aether_next/`. For each of: architect (prompt generation,
config schema, EnvMap consumption), solver (prompt, action loop, context
compilation), verifier (inspection tools, verdict taxonomy, evidence
receipts, decisive-evidence enforcement or lack thereof), kernel/runtime
(dispatch, receipts, stalemate/loop handling), EnvMap (capability inference,
metadata cleanliness, layering) — answer: does the code actually implement
the doctrine in `docs/HARNESS_VISION.md` and `CLAUDE.md`, or does it only
look like it does? Where is ownership shared/blurred (the specific smell the
owner named as the root of most past bugs)? Where is there dead code,
advisory-only mechanisms nothing enforces, duplicate paths, or
benchmark/task-specific logic that shouldn't be in canonical Aether? Cite
file paths and line numbers.

**C. Bloat/minimality audit.** Directly answer the owner's question: why is
the agent this big, is it necessary, and what should be deleted vs. what is
genuine modular capability surface that looks big but is actually the right
kind of big. Inventory the scratch/experiment/backup directories in the repo
root and say plainly what should never have been committed or left in the
working tree. Give LOC/module-count evidence, not vibes. Check the 500-LOC
module cap CLAUDE.md mandates — list every module currently over cap.

**D. Latest-run root-cause audit.** Independently verify (don't just trust
the three prior audits) the sentinel run failures. For each of the 5 tasks:
what did the architect configure, what did the solver do, what did the
verifier inspect and decide, what did the official grader say, and what is
the true root cause (architect/solver/verifier/EnvMap/runner/model-capability
— pick one, with evidence, per the classification discipline already
established in this codebase). Confirm or correct the "verifier accepts
non-decisive evidence" finding.

**E. Vision-fidelity verdict.** Score, with specific evidence per line:
generic (no task-specific logic in canonical path), minimal (smallest
workbench whose ceiling is the model's ceiling), capable (verifier can truly
judge state, context is lossless, tools cover real capability classes), elite
(clean substrate, explicit failures, full traceability). Then give one
overall honest percentage-fit-to-vision judgment, and defend it — don't
default to a comforting number.

**F. Path to 100% on TBench 2.0 — and the priority question.** The owner
asked explicitly: *does getting to his vision (Protean, minimal) clash with
getting to 100% on TerminalBench 2.0, and if so, which wins?* Answer this
directly, don't dodge it. Where you believe they align (e.g., decisive-
evidence verification helps both correctness and is squarely in-vision, not
a benchmark hack), say so. Where you believe a shortcut would raise pass rate
but violate the stronger-model test or the no-compensation test, name it
explicitly and say it should be rejected even though it costs score. Give a
concrete ordered plan to close the gap to 100% — grounded in the actual
capability gaps you found in §D, not a generic checklist — and say which
items are vision-neutral, vision-positive, or vision-risk.

**G. Verdict and recommendation.** One clear paragraph: is this the right
codebase to keep building on as-is, or does it need a deliberate carve-down
pass before more feature work? What's the single next slice you'd do first,
and why that one over the alternatives you considered?

## 8. Rules while you work

- Verify claims against code/tests/traces before repeating them. Treat prior
  agent reports (including everything summarized in this brief) as
  hypotheses to check, not facts.
- Do not write or fix code this run. Read-only investigation + report.
- Do not relitigate settled architecture questions for fun — but if you find
  the canonical-target decision itself was wrong or is being undermined by
  dead parallel lineages still sitting in the tree, say so; that's in scope.
- Be blunt. Separate "looks done" from "is done." If something is genuinely
  good, say that plainly too — this isn't a mandate to manufacture criticism,
  it's a mandate to be accurate.
- Cite file paths, line numbers, commit SHAs, and run directory paths for
  every non-trivial claim.
