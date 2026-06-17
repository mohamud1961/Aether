# 04 — Variants and Decision History

This file reconstructs the project's story chronologically, phase by phase,
with hypothesis/work/tests/runs/failures/lessons/verdict/open-questions for
each. The goal is **transfer of learning, not flattering past work** —
failures and reversals are first-class.

---

## Phase 0 — Baseline harness + composable blocks (pre-2026-05)

- **Hypothesis**: A composable block architecture (`blocks/{context,
  execution, orientation, recovery, tools, verification}/`) with a flat
  tool-call loop (`flat_loop`) over a single `raw_bash` tool can serve as a
  generalizable harness for TB2.0-style tasks.
- **Work**: Implemented `blocks/execution/flat_loop.py`,
  `blocks/tools/raw_bash.py`, plus the `runner/packet07_*.py` and
  `runner/successor_*.py` lineages — many cycles of "packet" experiments
  (cycle0/cycle1 variants: anchor continuation, context continuation, linked
  query continuation, parser continuation, reduce-and-select evals, etc.)
- **Tests/runs**: Numerous `packet07_*` eval runners exist
  (`packet07_golden_diagnostic.py`, `packet07_hard_row_robustness_probe.py`,
  `packet07_closeout_scoreboard.py`, etc.) representing dozens of small
  experiments.
- **Verdict (per `runner/README.md`)**: All `packet07_*` and `successor_*`
  files are now **historical reference only** — superseded by the kernel +
  eval-suite approach. The one durable finding that survived: **long-horizon
  artifact handoff is solved (6/6)** — this lineage's main lasting
  contribution.
- **Lessons**: Many small, narrowly-scoped variant experiments accumulate
  into a large historical surface that is hard to mine later. The project
  has repeatedly re-learned the value of "fewer, eval-gated variants."

---

## Phase 1 — Active Evidence Kernel emerges

- **Hypothesis**: Replace ad hoc packet-level state tracking with a
  structured "kernel" providing receipts, evidence trails, gates, recovery,
  and context packs as first-class, composable modules
  (`runner/kernel_*.py`, `runner/active_evidence_kernel.py`).
- **Why**: The recurring failure class across Phase 0 packets was
  `ungoverned_model_claim` — the model says "done" but nothing in the
  harness verified it. `GOVERNED_STATUSES` was introduced to make this
  explicit (`governed_pass`, `ungoverned_model_claim`, `verifier_failed`,
  `artifact_gate_failed`, `provenance_gate_failed`,
  `native_tool_contract_failed`, `service_not_ready`, `invalid_environment`,
  `budget_exhausted_open_obligations`).
- **Work**: 16 kernel modules built incrementally; `runner/evidence_kernel.py`
  appears to be an earlier, narrower predecessor to
  `active_evidence_kernel.py` (needs direct comparison — see `gap_report.md`).
- **Tests**: Substantial unit test growth attributed partly to this phase
  (part of the 194→220+ test count growth, `06`).
- **Status as of this phase**: marked "active but not full-board-ready" —
  i.e. the project itself has, for some time, considered this kernel
  promising-but-unproven.
- **Open questions carried forward**: Does the kernel's complexity pay for
  itself vs. blocks/ + targeted guards? Never answered with eval evidence.

---

## Phase 2 — Eval-First Harness Reset declared (AGENTS.md)

- **Decision**: The project formally declared the current stage,
  "Eval-First Harness Reset" — promotion authority moves from
  packets/route-manifests/trace-prose to scored eval evidence ("the
  scoreboard is the source of truth"). Cites a "5.4 Pro ordered-roadmap
  direction" as strategic source of truth (not itself present in repo as a
  readable doc — likely an external/ephemeral planning artifact).
- **First Reset Goals declared** (dependency order):
  1. `certified_sandbox_contract` — benchmark-native Linux/container
     workspace contract.
  2. `eval_substrate` — task-pack schema, fixtures, verifier/grader,
     result rows, scoreboard.
  3. `first_eval_core` — runtime/tool-contract evals, TB-style verifier
     repair eval, filesystem/open-workflow eval, BFCL sentinel, structured
     retrieval/reduction eval.
  4. `first_bounded_autoresearch_loop` — pick one failing certified eval,
     predict, implement one mechanism, score target+sentinels,
     promote/kill/pause.
- **Variant hypothesis backlog created** (2026-05-13,
  `tracking/collab/variant_hypothesis_backlog.md` — only on `vm-pulled`):
  an admission-gated queue with statuses `control`, `paused_hypothesis`,
  `blocked_pending_eval_substrate`, `blocked_pending_target_eval`,
  `never_evaluated_backlog`, `future_hypothesis`,
  `historically_evaluated_killed`, `retest_required`.
- **Killed hypotheses recorded** (with evidence):
  - `parser_linked_anchor_successors` — killed: no Letta uplift, BFCL
    regression.
  - `reduction_discipline_guard` — killed: hard-row uplift didn't replicate
    across reruns; BFCL/easy/medium sentinels unstable.
  - `work_pocket_answer_projection_01` — killed: 0 context passes, high
    certified-fail rate, no recovery on follow-on boards.
- **Lesson**: The backlog discipline (target eval + predicted delta + named
  sentinels before any new variant) is exactly the discipline that the next
  three phases (below) repeatedly **failed to follow**.

---

## Phase 3 — "Combined Guard V1.5 with Contract-Aware Sentinel Repair" (2026-05-17)

- **Hypothesis**: A small post-hoc guard wrapping tool-call execution
  (`blocks/tools/result_attribution_guard_common.py`, commit `076ba7694`)
  combining: a "no-call guard" (block tool calls before identity
  verification), an "ignored-IDs guard" (flush stale result-attribution
  IDs), and a "sentinel contract guard" (programmatically inject a missing
  `include_history: True` argument for `lookup_customer_order` calls) would
  fix `clean_tool_contract_semantics` failures.
- **Run**: 2026-05-17 tournament on Azure VM Docker (`harnesseng-dev`,
  Ubuntu 24.04, Docker 29.1.3 — confirmed working backend), commit
  `0678492e2` "Record V1.5 perfect tournament run summaries."
- **Result**: `comparison_summary.json` — `combined_guard` variant scored
  `target_pass: 2/2` on the 2 target tasks, but **`sentinel_pass: 0/1`** —
  the regression sentinel `ctc_semantics_001_multi_required_order` FAILED
  under the combined guard (it had passed under control and other variants).
  Overall `scoreboard.json`: 6/12 pass (50%), not "perfect."
  `prediction.json` had predicted "no_material_regression" on the
  sentinel — **this prediction failed**.
- **Verdict**: Per AGENTS.md's own rules ("test the interaction explicitly...
  Promote only the board result that is net-positive on... sentinels"), this
  should NOT have been called a "perfect tournament run" or promoted as a
  general win. It is also a **hardcoded, task-specific repair**
  (`lookup_customer_order` is a specific tool name from one eval task) —
  not a generalizable mechanism.
- **Lesson**: This is a concrete instance of the project's recurring
  "declare victory before checking sentinels" pattern. Any future tooling
  guard work should explicitly re-resolve this sentinel regression before
  reuse, or be redesigned generically (not hardcoded to one tool name).
- **Status**: code exists (`blocks/tools/result_attribution_guard_common.py`),
  unresolved sentinel regression, not currently wired into any "current"
  route per `runner/README.md`.

---

## Phase 4 — Goal 1: Single-Family Winner Discovery (2026-05-18, vm-pulled)

- **Hypothesis**: Run a rigorous, authority-bookkept tournament across 7
  candidate mechanism families to find at least one promotable "winner."
- **Families tested**: `tool_result_attribution`, `long_horizon_artifact_handoff`,
  `dependency_config_environment`, `filesystem_open_workflow`,
  `verifier_repair` (admissible for next round); parked:
  `pressure_tool_call_sentinel`, `structured_retrieval_reduction`.
- **Results** (`vm-pulled:tracking/collab/autonomous_loop/single_family_winner_discovery_gate/closeout.md`):
  - `tool_result_attribution`: all 4 variants 0/2 target, 0/1 sentinel.
  - `long_horizon_artifact_handoff`: both candidates pass target+pressure rows but
    **fail the tool-call sentinel** (cross-benchmark regression).
  - `dependency_config_environment`: target uplift existed but didn't carry
    to sentinels/global board.
  - `filesystem_open_workflow`: both routes failed target rows entirely.
  - `verifier_repair`: both routes passed all rows — but the
    eval itself was **non-discriminating** (too easy to be useful as a
    diagnostic).
- **`winner_found = 0`** — explicit, honest closeout: "This Goal ends as an
  initial/recovery pass, not successful winner discovery. No family is
  promoted as a winner."
- **Authority audit** (`claim_authority_audit.md`, 2026-05-18, "complete"):
  Found that some "shared fresh probe" rows labeled `admission_level=certified`,
  `backend_ref=azure_vm_docker` had **actually run on a failed local Mac
  Docker socket** and were correctly excluded from promotion math for 4
  families. Explicit non-claims: pressure tool-call native full-runtime
  authority NOT claimed; the external benchmark remains
  "eval_gap/equivalent-only anchor, NOT native authority."
- **Lesson**: This is the **most rigorous, most honest** evidence-bookkeeping
  exercise in the repo's history — a model for how Fable's subagents should
  report results (distinguish certified/native vs. equivalent/local-invalid,
  explicitly say "no winner" when true). It directly predates and is more
  disciplined than Phase 5 below, which repeated the same Docker-authority
  mistake two weeks later.
- **Recommended next steps from this closeout** (never executed):
  - `tool_result_attribution`: fix hidden-truth leakage/solver isolation,
    test `tool_call_contract_classifier`, `permission_runtime_attribution_split`.
  - `long_horizon_artifact_handoff`: need a stronger challenger than
    `bounded_episode_01`; backlog refs `stateful_compaction_external_context_01`,
    `verified_work_pocket_redesign`.
  - `dependency_config_environment`: better bounded slate around
    `cwd_workdir_invariant_guard` + `candidate_plus_app_workspace_path_normalizer_01`.
  - `filesystem_open_workflow`: test
    `v04_ex_02_cwd_workdir_invariant_propagation_guard`,
    `v04_cb_01_decoy_resistant_target_selection`,
    `candidate_plus_app_workspace_path_normalizer_01`.
  - `verifier_repair`: expand homolog pressure before retesting
    `verification_repair_loop_01`/`artifact_and_verifier_hard_gate_01`.

---

## Phase 5 — 2026-05-30: Theoretical specs, family diagnostics, and `winning_harness_v1`

This was the single busiest day in the project's recorded history (19 inbox
files).

- **Antigravity's theoretical specs** (tracking/collab, benchmark-100-series theoretical harness specification): proposed a "100% theoretical harness"
  combining persistent tmux/PTY shell, supervised background daemons,
  double-loop recovery hooks, unified CLI tool wrappers, "Stem Agents"
  (static system prompts + session forking + VFS minification, modeled on
  Vix's ~22-step efficiency vs. BigAI's ~75-step chattiness). Then a
  competing **"Zero-Abstraction Engine"** spec proposed a single-file
  (<300-line) persistent-PTY kernel, predicting <12 steps and **$0.19/run**
  (claimed 65-92% cost reduction).
  - **These cost/step numbers are unvalidated predictions.** The one related
    "lean/zero-abstraction" run that was actually tried **regressed** — it
    improved one path-state row but did so by hiding evidence and using
    brittle anchors (per inbox A5).
- **Codex family-level diagnostic run** (inbox A5,
  `tracking/collab/eval_suite_v1_baseline/`,
  `tracking/collab/eval_suite_v1_repair_runs/`,
  `tracking/collab/eval_suite_v1_tournament_runs/`): the **most concrete
  measured data point in the whole repo**:
  - filesystem/cwd: 0/6
  - service readiness: 0/3
  - context/reduction: 2/7
  - environment/toolchain: 4/7
  - tooling baseline: 4/7, combined tooling guard → 7/7 (caveat: Phase 3's
    sentinel regression)
  - long-horizon artifact handoff: 6/6 (already solved)
  - **Root causes identified**: environment baseline failed on stale docs
    source / wrong canonical-runner discovery / wrong python invocation;
    filesystem baseline failed on wrong cwd/root and wrong target-file
    pattern matching; context baseline failed on evidence carry-forward,
    relevant retrieval, wrong field, stale state after mutation; service
    baseline failed on wrong process identity + missing readiness proof.
- **`winning_harness_v1` synthesized and implemented** (Phase 5 continued,
  inbox A6-A8): an 11-step build order
  (`tracking/collab/final_harness_eval_suite/reviews/winning_harness_synthesis_trace_analysis_2026-05-30.md`)
  targeting exactly the families above. Implementation completed
  (`runner/packet04_route_manifest.py`, `blocks/orientation/phase6_doctrine.py`),
  unit/adapter tests pass, route manifest builds correctly.
- **Scoring attempt — total failure due to environment, not capability**:
  family-level (35/35), final-suite private (13/13), benchmark (12/12), and
  TB challenge (2/2) runs **all came back INVALID** — local Docker daemon
  unavailable. Closeout: HOLD, "rerun on certified Docker backend before
  promotion."
- **GPT-5.5 Pro context curation** (inbox A6): built a 1.5MB then 3.16MB
  context dump (`tracking/collab/gpt55pro_best_harness_synthesis/
  INPUT_CONTEXT_AND_PROMPT*.md`) for an external GPT-5.5 Pro synthesis pass —
  a context-curation artifact, no architecture decision recorded from it in
  the inbox window.
- **Lesson**: Phase 5 produced the project's best diagnostic data AND its
  best-targeted (on paper) fix, but **repeated the exact Docker-authority
  mistake Phase 4 had already documented two weeks earlier** — rather than
  rerunning on the known-working Azure VM Docker backend (used successfully
  in Phase 3's tournament), the project let `winning_harness_v1` sit in HOLD
  and pivoted to a new architecture line (Phase 6) without resolving it.

---

## Phase 6 — Model-Led Substrate v1 (2026-06-05/06, current HEAD)

- **Hypothesis**: Layer a Layer-2 success auditor and explicit success-
  contract gating onto the Active Evidence Kernel (Phase 1) to close the
  `ungoverned_model_claim`/finalization-truth gap.
- **Work** (2026-06-05): `runner/kernel_layer2_audit.py` implemented by
  "Subagent Worker F" — prompt builder, parser, deterministic fallback,
  should-run logic. 7/7 unit tests pass
  (`tests/test_kernel_layer2_audit.py`). **Integration into
  `active_evidence_kernel.py`/`kernel_gates.py` was NOT done in this step.**
- **Adversarial review** (2026-06-05, antigravity,
  `tracking/collab/model_led_substrate_v1/reviews/adversarial_review_01.md`):
  found 4 gaps:
  1. Layer-2 auditor was completely dead code (confirms the integration gap
     above).
  2. "Success Contract missing" prompt instruction never injected.
  3. Finalization gates didn't block `governed_pass` when
     `success_contract_missing` was an open obligation.
  4. `render_context_pack` did naive `compact[:6000]` character-slicing
     instead of adaptive compaction.
  All 4 fixed same day (`accepted_findings_resolution.md`); decision made to
  bypass the finalization loop in legacy routes (preserve old behavior) and
  add the Layer-2 verify-repair loop only for model-led routes.
- **Recovery path-serialization fix** (2026-06-06, codex, from a codex
  worktree — the **latest event in the entire repo**, matching HEAD's
  immediate parent `551d5fedf`): fixed an `Errno 36` ("file name too long")
  bug where raw multiline heredoc shell commands were treated as
  artifact-path candidates by `runner/kernel_artifacts.py`, polluting
  recovery fingerprints in `runner/kernel_recovery.py`. Fixed by extracting
  bounded path refs and using command digests/snippets instead of raw
  command text. Focused pytest passed. Open question: broader path-extraction
  coverage for unusual path syntax (spaces, non-POSIX separators).
- **Status**: implementation-complete, adversarially reviewed, hardened —
  but **zero eval-suite runs**. This is where HEAD currently sits.
- **Lesson**: Phase 6 is methodologically *better* than Phase 5 (adversarial
  review caught real dead-code/gating bugs before any eval was wasted on
  them) — but it inherits the same fundamental gap: no scored evidence yet,
  and the Docker/eval-loop problem from Phases 4-5 was never resolved in
  parallel.

---

## Phase 7 — MLPCP v2/v3 (2026-06-08→11, PULLED & PAUSED)

- **Hypothesis**: A cockpit/capability-graph/receipt "execute-plan" architecture (v2) and/or a continuous-conversation, typed-tools continuity runner (v3), inspired by Claude-Code-style continuous-session agents (option H in `03`).
- **Work**: MLPCP v2 remains purged from the working tree. For MLPCP v3, the active VM run files (runs, audits, patches, and pause state) have been pulled to `tracking/variants/mlpcp_v3/` as of 2026-06-11.
- **Outcome**: The `qemu-startup` task passed after applying the `receipt-memory-cockpit` patch. However, latest `hard2` reruns for `extract-moves-from-video` and `install-windows-3.11` remained at 0.0 because the model ignored the background/service tools and kept looping. A generic progress escalation patch failed to apply because target anchors in `_execute_single_action` were missing.
- **Lesson**: While the `receipt-memory-cockpit` patch succeeded in passing `qemu-startup`, the model's failure to naturally use the background tools on `hard2` tasks indicates that the agent needs explicit progress tracking or escalation. Resuming/repairing this session requires reconnecting to the VM and resolving the source anchors for generic progress escalation.

---

## Cross-cutting lessons for Fable

1. **The "scoreboard is the source of truth" rule has been honored in
   diagnosis (Phase 5's family-level run) but not in promotion** (Phase 3's
   sentinel regression ignored, Phase 5's `winning_harness_v1` never rerun
   after going INVALID, Phase 6 built before Phase 5 was resolved).
2. **The Azure VM Docker backend works** (proven in Phase 3 and referenced
   in Phase 4's audit) but is treated as a one-off rather than the default
   loop — local Mac Docker unavailability has invalidated more "certified"
   claims than any single mechanism failure.
3. **The best diagnostic data (Phase 5's family-level scoreboard) and the
   best bookkeeping discipline (Phase 4's authority audit) are 2 weeks
   apart and were never combined** — Phase 5 repeated Phase 4's documented
   mistake.
4. **Two of the worst-measured families (filesystem 0/6, service readiness
   0/3) have specific, evidence-backed proposed fixes sitting unimplemented
   in the backlog** (`filesystem_cwd_path_normalization_wrapper_01`,
   `service_contract_first_receipt_closure_01`) since at least 2026-05-25 —
   these are the cheapest, most evidence-backed next mechanism bets in the
   entire repo, independent of which architecture direction wins.
5. **Long-horizon artifact handoff (6/6) is solved and should not be
   re-litigated** — but a candidate from Phase 4 that improved this family
   regressed BFCL, so any future change here needs a BFCL sentinel.

---

## Note: Long-Horizon Artifact Handoff (excluded from public family gallery)

The `long_horizon_artifact_handoff` behavioral class is the only family in the
repo that ever achieved 6/6 on its target eval. However, it does not have a
dedicated public family directory in `variants/families/`. This was a deliberate
decision based on the following:

**No clean single code unit**: The long-horizon mechanism is embedded across
`runner/packet07_cycle1_context_targeted_autoresearch.py` (historical reference,
superseded) and `blocks/context/{lean_compact,sliding_window,full_history,
closure_evidence_projection}.py`. There is no single `long_horizon_variant.py`
file to publish. Extracting a clean variant would require non-trivial surgery on
the packet07 file, which is marked as historical-reference-only in `runner/README.md`.

**The 6/6 result has a known shadow**: Phase 4 showed that a candidate which
improved this family regressed BFCL (a cross-benchmark sentinel). The interaction
between long-horizon compaction and tool-call attribution is unresolved.

**Proposed challengers were not built**: the Phase 4 closeout recommended
`stateful_compaction_external_context_01` and `verified_work_pocket_redesign`
as the next challenger variants. Neither was built before Phase 5 pivoted to
a new architecture.

The correct next action for this family, when work resumes, is:
1. Extract the long-horizon compaction logic into a clean `blocks/context/`
   module with no `runner/` dependency.
2. Build the `stateful_compaction_external_context_01` challenger.
3. Include an explicit BFCL sentinel in any future tournament design.

Until then, the 6/6 result is noted here as the strongest empirical finding in
the repo's Phase 0–4 history, carried forward without promotion.
