# 10 — Fastest Path Options

This file presents route options. **No final pick is made here.** Each
option is evaluated on: meaning, shortest path, what to reuse/kill/ignore,
speed, success probability, complexity, benchification risk,
overengineering risk, fit for GPT-5.4 mini, first 5 steps, falsification
tests, and supporting/weakening evidence.

---

## Option 1: Eval-Loop-First (infrastructure before architecture)

**Meaning**: Before touching any architecture, fix the certified-eval-loop
problem (`07`#9) — restore/recreate the Azure VM Docker lifecycle scripts,
establish a default "score on Azure VM Docker" workflow, and **rerun
`winning_harness_v1`** (Architecture C, `03`) on it since it's
implementation-complete and just needs scoring.

- **Shortest path**: recreate `scripts/deallocate_harnesseng_vm.sh` /
  `scripts/configure_harnesseng_vm_autoshutdown.sh` (or equivalent),
  validate Azure VM Docker access, rerun the 4 `winning_harness_v1` surfaces
  (62 rows) that were 100% INVALID.
- **Reuse**: `winning_harness_v1` code (Architecture C), the 2026-05-17
  tournament's proof that Azure VM Docker works.
- **Kill**: nothing yet — this is diagnostic.
- **Ignore**: model-led substrate v1, MLPCP for now.
- **Speed**: Fast — could produce real scored evidence within hours of VM
  access being restored.
- **Success probability** (of producing *useful evidence*, not
  necessarily 100%): Very high — this is "evidence sitting on the table."
- **Complexity**: Low (infrastructure + rerun, no new mechanism code).
- **Benchification risk**: None — pure measurement.
- **Overengineering risk**: None.
- **Fit for GPT-5.4 mini**: N/A (infra step), but unblocks all future
  GPT-5.4-mini-targeted scoring.
- **First 5 steps**: (1) confirm Azure VM `harnesseng-dev` still exists/
  accessible; (2) recreate or locate the 2 missing lifecycle scripts;
  (3) rerun `winning_harness_v1`'s family-level (35 rows) surface first
  (cheapest, most diagnostic); (4) compare against the 2026-05-30 baseline
  scoreboard family-by-family; (5) deallocate VM, record results in ledger.
- **Falsification test**: if `winning_harness_v1` scores *worse* than the
  2026-05-30 blocks/+guards baseline on filesystem/service/context, that's
  strong evidence Architecture C's synthesis was flawed despite looking
  good on paper.
- **Supporting evidence**: Azure VM Docker proven working (2026-05-17);
  `winning_harness_v1` implementation-complete; this is the cheapest
  possible source of new, decisive evidence.
- **Weakening evidence**: none identified — the only "cost" is VM time and
  the scripts effort.

---

## Option 2: Filesystem + Service-Readiness Fix-First (close the worst gaps)

**Meaning**: Implement and score the two backlog mechanisms with the
strongest evidence-backed predicted uplift:
`filesystem_cwd_path_normalization_wrapper_01` (targets 0/6 → ?/6) and
`service_contract_first_receipt_closure_01` (predicted 0/3 → 3/3), as
generic wrappers on top of the **current blocks/+guards baseline**
(Architecture A), independent of the kernel/winning-harness/MLPCP debate.

- **Shortest path**: implement both wrappers per their backlog
  specifications (`vm-pulled:tracking/collab/variant_hypothesis_backlog.md`),
  test individually and combined (per AGENTS.md's "fix A alone, fix B
  alone, A+B together" rule), score against family-level eval + BFCL +
  TB-style sentinel.
- **Reuse**: blocks/ baseline, `final_harness_eval_suite` registry,
  `runner/kernel_services.py` (for the service receipt).
- **Kill**: nothing — additive on top of current baseline.
- **Ignore**: kernel/winning-harness/MLPCP architecture debate entirely for
  this slice.
- **Speed**: Fast — both mechanisms are narrowly scoped (per their backlog
  descriptions, "small wrapper" scale, not architecture rewrites).
- **Success probability**: High for service-readiness (explicit predicted
  delta 0/3→3/3 from evidence-backed analysis); moderate-high for filesystem
  (well-diagnosed root cause: cwd/path/decoy confusion).
- **Complexity**: Low-medium.
- **Benchification risk**: Low if implemented generically (`09`).
- **Overengineering risk**: Low.
- **Fit for GPT-5.4 mini**: Excellent — these are exactly the kind of
  "give the harness more structure so a cheaper model doesn't need to be as
  clever" fixes that compensate for a smaller executor.
- **First 5 steps**: (1) implement `filesystem_cwd_path_normalization_wrapper_01`;
  (2) score alone vs. 2026-05-30 filesystem baseline (0/6) + BFCL sentinel;
  (3) implement `service_contract_first_receipt_closure_01`; (4) score alone
  vs. service baseline (0/3) + BFCL sentinel; (5) score both together,
  promote/kill/iterate per AGENTS.md interaction-testing rule.
- **Falsification test**: if either fails to move its target family or
  regresses BFCL/long-horizon sentinels, kill per AGENTS.md (don't
  reinterpret as success).
- **Supporting evidence**: these are the two best-diagnosed, most
  evidence-backed unimplemented fixes in the entire repo (`07`#1, #2).
- **Weakening evidence**: requires the eval loop (Option 1's blocker) to be
  resolved to score — so Option 1 is likely a co-requisite, not an
  alternative.

---

## Option 3: Model-Led Substrate v1 First-Score (score the newest code)

**Meaning**: Run the existing, adversarially-reviewed "model-led substrate
v1" (Architecture D) through the `final_harness_eval_suite` for the first
time, including verifying it's actually wired into the runner entrypoint
that gets executed (per `05`'s finding that `agent.py` currently imports
`evidence_kernel.py`, not `active_evidence_kernel.py`).

- **Shortest path**: (1) confirm/fix wiring so `agent.py` (or a new
  entrypoint) actually exercises `active_evidence_kernel.py` +
  `kernel_layer2_audit.py`; (2) run family-level eval suite; (3) compare to
  2026-05-30 baseline.
- **Reuse**: all of Architecture B/D's code and tests.
- **Kill**: legacy `evidence_kernel.py` path, IF the kernel wiring proves
  net-positive (not before).
- **Ignore**: winning_harness_v1, MLPCP for this slice.
- **Speed**: Medium — wiring verification/fix is an unknown-sized task
  (could be trivial or could reveal deeper integration gaps, per the
  "two finalization code paths" decision in Phase 6).
- **Success probability**: Unknown — this is literally the open question;
  that's the point of running it.
- **Complexity**: Medium-high (16-module kernel, two finalization paths).
- **Benchification risk**: Low (general architecture), but
  `_clean_hidden_refs()` and Layer-2 audit design need the `09` checks.
- **Overengineering risk**: **Highest of all options** — this is the
  largest unscored surface area in the repo; if it doesn't beat baseline,
  a lot of code may need to be reconsidered.
- **Fit for GPT-5.4 mini**: Plausible — the explicit success-contract +
  Layer-2 audit design is meant to compensate for a weaker executor's
  tendency to over-claim completion, which is directly relevant to
  GPT-5.4 mini.
- **First 5 steps**: (1) `git diff`/grep to confirm exactly what `agent.py`
  vs `active_evidence_kernel.py` wiring looks like; (2) if not wired, do the
  minimal wiring to run an eval through the active kernel; (3) run the
  cheapest family (e.g. tooling, already at 4/7→7/7 baseline) as a smoke
  test; (4) run filesystem + service families (0/6, 0/3) — does the kernel
  alone help, even without Option 2's targeted fixes?; (5) run BFCL/
  long-horizon sentinels to check for regressions.
- **Falsification test**: if the kernel makes filesystem/service/context
  *worse* or no different than blocks/ baseline, that's evidence the
  kernel's value is primarily about finalization-truth (a different axis)
  and shouldn't be conflated with the families Option 2 targets.
- **Supporting evidence**: most recent, most reviewed code; directly
  targets `ungoverned_model_claim` (`07`#7), a high-impact class.
- **Weakening evidence**: zero eval evidence so far; "newest ≠ best"
  caution from `01`/`00`; large surface area = expensive to debug if it
  underperforms.

---

## Option 4: Kernel + Targeted-Fixes Hybrid

**Meaning**: Combine Options 2 and 3 — implement the filesystem/
service-readiness wrappers (Option 2) **as kernel-native mechanisms** (e.g.,
extending `kernel_services.py` for service readiness, adding a path-
normalization layer to `kernel_state.py`/`kernel_artifacts.py`), scored
against the kernel-wired runner (Option 3's prerequisite).

- **Shortest path**: requires Option 3's wiring step first, then Option 2's
  mechanisms built kernel-native rather than blocks-native.
- **Reuse**: everything from 2 and 3.
- **Kill**: whichever of blocks-native vs. kernel-native versions of the
  fixes underperforms, once both are scored.
- **Speed**: Slower than 2 alone (kernel wiring dependency) but avoids
  potentially redoing the fixes twice (once for blocks, once for kernel) if
  the kernel direction is eventually chosen anyway.
- **Success probability**: Depends on Option 3's wiring risk being low.
- **Complexity**: Medium-high (sum of 2 and 3's complexity, but not
  strictly additive if done in one slice).
- **Benchification risk**: Low, same as 2/3 individually.
- **Overengineering risk**: Medium-high — risk of building kernel-native
  fixes before knowing if the kernel itself is net-positive (Option 3's
  open question).
- **Fit for GPT-5.4 mini**: Good, same reasoning as 2/3.
- **First 5 steps**: same as Option 3's steps 1-2, then Option 2's steps but
  implemented against kernel modules.
- **Falsification test**: same as both 2 and 3.
- **Supporting evidence**: avoids potential double-work if kernel is chosen.
- **Weakening evidence**: couples two independent unknowns (does kernel
  wiring work? do the fixes work?) into one slice — harder to attribute a
  bad result to the right cause. AGENTS.md's "test A alone, B alone, A+B"
  rule argues AGAINST combining untested things prematurely.

---

## Option 5: Native-Runner-First (harden the TB2.0 scoring path itself)

**Meaning**: Before any mechanism work, harden
`runner/benchmark_adapter_terminalbench_native.py` +
`runner/certified_sandbox.py` to get a confirmed "native" (not
"equivalent") TB2.0 score for the current baseline (blocks/ + whatever
guards are currently considered safe), establishing a true baseline %
on real TB2.0 tasks.

- **Shortest path**: audit `EXPECTED_REMOTE_FRAGMENT` provenance check and
  the certified-sandbox contract against the 4 `official_tasks/`; run a
  small batch of real TB2.0 tasks (beyond the 4 local ones if accessible)
  through the native adapter; record a true baseline %.
- **Reuse**: existing native adapter code.
- **Kill**: the non-native `benchmark_adapter_terminalbench.py` path, IF the
  native path is confirmed working (per the 05-18 audit, this wasn't true
  yet as of that date).
- **Speed**: Medium — depends on how much "native" work was already done
  vs. how much remains.
- **Success probability**: Unknown — directly addresses `01`'s "immediate
  decision" framing (what does 'true 100%' even measure right now?).
- **Complexity**: Medium.
- **Benchification risk**: Must avoid tuning to the 4 local official tasks
  specifically (`09`).
- **Overengineering risk**: Low — this is foundational, not additive
  complexity.
- **Fit for GPT-5.4 mini**: N/A (infra), but establishes the actual metric
  GPT-5.4 mini will be measured against.
- **First 5 steps**: (1) re-run the 2026-05-18 authority audit's "is TB
  native or equivalent" check against current code; (2) if still
  "equivalent only," scope what's missing for "native"; (3) run the 4
  `official_tasks/` through the native adapter as a calibration check;
  (4) record the baseline % for the current architecture; (5) document this
  as the reference number all future architecture comparisons use.
- **Falsification test**: if the native adapter still can't be confirmed
  "native" after this work, that itself is critical information — it means
  no architecture choice can be evaluated against true TB2.0 yet, only
  custom-suite proxies.
- **Supporting evidence**: AGENTS.md explicitly prioritizes this
  (`certified_sandbox_contract` is First Reset Goal #1, still apparently
  incomplete per the 05-18 audit's "not native authority" finding).
- **Weakening evidence**: this has been a stated priority since at least
  2026-05-13 and doesn't appear to have progressed — may indicate it's
  harder than it looks (access to real TB2.0 task corpus, Harbor
  integration depth, etc.) — see `gap_report.md`.

---

## Option 6: Continuous-Session Redesign (new architecture from evidence)

**Meaning**: Design a fresh continuous-session, phase-gated agent loop
(EXPLORE→PLAN→EXECUTE→VERIFY→FINALIZE, informed by option H/I in `03` —
Claude Code's Stop Hooks/autoDream/ULTRAPLAN/KAIROS and BigAI's
planner/executor/verifier ~82%) — effectively redoing what MLPCP v3
attempted, but designed from this packet's evidence rather than purged
without trace.

- **Shortest path**: N/A — this is the "build something new" option and has
  no shortest path; would need its own design doc, eval-gated incremental
  build.
- **Reuse**: BigAI trace-layer findings, Claude Code research docs,
  `blocks/orientation/phase6_doctrine.py`'s `orient_codex_style_handoff_compaction`
  (already Codex-handoff-shaped), Layer-2 audit's `_clean_hidden_refs`
  pattern (Option 3) as a Stop-Hook-like veto component.
- **Kill**: potentially everything in B/C/D if this proves superior — but
  that's a 100%-overengineering-risk claim until proven.
- **Speed**: Slowest — full redesign.
- **Success probability**: Unknown — no Aether-specific evidence either way;
  BigAI's 82% is the best *external* evidence such architectures can work
  well on TB2.0.
- **Complexity**: High.
- **Benchification risk**: Low if designed from abstracted patterns (per
  `09`).
- **Overengineering risk**: **Very high** — this is exactly the pattern
  (build new architecture before scoring existing ones) that produced
  Phases 5-7's churn (`07`#8). Should only be pursued AFTER Options 1-5 have
  produced a clear "none of the existing lines can reach X%" verdict.
- **Fit for GPT-5.4 mini**: Stop-Hook-style completion vetoes are
  specifically good for weaker executors that over-claim — relevant.
- **First 5 steps**: N/A unless chosen — would start with a structured diff
  between BigAI's 82%-passing architecture and Aether's current best-scored
  candidate (Option 1/2/3's winner), focused on the worst families.
- **Falsification test**: N/A — this option doesn't have one until it's
  built, which is itself the argument against choosing it first.
- **Supporting evidence**: BigAI 82%, Claude Code patterns, and MLPCP v3's qemu-startup pass.
- **Weakening evidence**: MLPCP v3 already attempted this and was paused after VM disconnect due to model failing to use the background tools on hard2 tasks and progress-escalation patch failing to apply due to missing anchors. Repeating that pattern without first resolving Options 1-3 would repeat Phase 7's mistake.

---

## Cross-cutting recommendation pattern (not a final pick)

Options 1, 2, and 5 are **cheap, evidence-producing, and largely
independent of the architecture debate** — they could plausibly run in
parallel lanes immediately. Options 3 and 4 require resolving Option 1's
infrastructure blocker and carry real "is the kernel worth it" risk that
should be tested cheaply (small smoke run) before heavy investment. Option
6 should be treated as a last resort, gated on Options 1-5 producing a clear
"ceiling" finding that none of the existing lines can close.
