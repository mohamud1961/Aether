# 03 — Architecture Landscape

This file describes every serious architecture direction found in the repo,
without ranking them. Fable should form its own verdict using `04` (history)
and `06` (evidence).

---

## A. Baseline: Composable Block Architecture (`blocks/`)

**What**: The original Phase-1 architecture from `README.md`. A
`flat_loop` (`blocks/execution/flat_loop.py`) repeatedly dispatches tool
calls — primarily a single `raw_bash` tool (`blocks/tools/raw_bash.py`) —
until the model emits no tool calls or the step budget is exhausted. Other
blocks: `blocks/context/`, `blocks/orientation/`, `blocks/recovery/`,
`blocks/verification/`.

**Why**: Mirrors Terminus/Terminus-2's architecture (single interactive
terminal tool) — confirmed by inbox A4 as an "acceptable base architecture."

**Problem solved**: Gives a minimal, generalizable execution substrate that
matches the benchmark's own reference harness shape, reducing risk of
benchification baked into tool design.

**Key files**: `blocks/execution/flat_loop.py`, `blocks/tools/raw_bash.py`,
`blocks/orientation/phase6_doctrine.py` (used by `winning_harness_v1`),
`blocks/tools/result_attribution_guard_common.py` (Combined Guard V1.5),
`blocks/tools/app_path_normalizer.py`.

**Evidence**: Inbox A4/A5 family-level diagnostics ran against this base
(plus guard variants). Tooling family went 4/7 → 7/7 with combined guard
(but combined guard has the sentinel-regression caveat — `07`).

**Strengths**: Simple, generalizable, closely matches reference harness
shape, easy to reason about and to layer guards onto.

**Weaknesses**: By itself, scores poorly on filesystem (0/6), service
readiness (0/3), and context (2/7) families — raw bash alone doesn't give
the model enough structure for these.

**Status**: current / foundational. Almost every other architecture in this
list is "blocks + something on top," not a replacement for blocks.

**What Fable should decide**: Whether `blocks/` + targeted guards/wrappers
(filesystem cwd normalization, service-readiness receipts) is sufficient, or
whether a deeper structural change (kernel, programmable tool layer) is
needed on top.

---

## B. Active Evidence Kernel (`runner/active_evidence_kernel.py` + `kernel_*.py`)

**What**: A 16-module "kernel" composing: receipts (`kernel_receipts.py`),
context packs (`kernel_context_pack.py`), control plane
(`kernel_control_plane.py`), gates (`kernel_gates.py`), recovery
(`kernel_recovery.py`), success contracts (`kernel_success_contract.py`),
evidence trails (`kernel_evidence_trail.py`), Layer-2 audit
(`kernel_layer2_audit.py`), native tools (`kernel_native_tools.py`),
compaction (`kernel_compaction.py`), working window
(`kernel_working_window.py`), services (`kernel_services.py`), TPM pacing
(`kernel_tpm_pacer.py`), artifacts (`kernel_artifacts.py`), state
(`kernel_state.py`), interrupts (`kernel_interrupts.py`).

**Why**: Designed to give the harness durable, structured "evidence" about
what has actually happened (tool outputs, file states, service readiness)
so that finalization/verification decisions are grounded rather than
model-claimed.

**Problem solved**: The "model claims done but nothing verifies it" failure
class (`ungoverned_model_claim` in `GOVERNED_STATUSES`), context loss across
long runs, recovery from broken states.

**Key files**: all `runner/kernel_*.py`, `runner/active_evidence_kernel.py`,
`runner/evidence_kernel.py` (older/predecessor — needs comparison).

**Tests**: `tests/test_kernel_layer2_audit.py` (7/7 pass, per inbox A9),
`tests/test_model_led_substrates.py`, plus broad kernel test coverage
contributing to the 194→220+ passing-test growth (`06`).

**Evidence**: Unit-test pass only. **No eval-suite run has ever scored this
kernel end-to-end.** This is the single largest evidence gap in the repo.

**Known bugs (recently fixed)**: Layer-2 auditor was dead code (never wired
into `active_evidence_kernel.py`) until 2026-06-05; success-contract-missing
prompt injection was missing; finalization gates didn't block
`governed_pass` on missing success contracts; `render_context_pack` did
naive `[:6000]` character slicing instead of adaptive compaction (all fixed
2026-06-05, `tracking/collab/model_led_substrate_v1/reviews/`). A
recovery-command path-serialization bug (`Errno 36`, raw heredoc commands
polluting artifact/recovery fingerprints) was fixed 2026-06-06
(`runner/kernel_artifacts.py`, `runner/kernel_recovery.py`).

**Strengths**: Most architecturally ambitious current code; directly targets
the `ungoverned_model_claim`/finalization-truth failure classes that have
recurred throughout the project's history (`04`); has GOVERNED_STATUSES
vocabulary that maps cleanly onto a TB2.0-style pass/fail/invalid taxonomy.

**Weaknesses**: Unscored; large surface area (16 modules) makes "is this
actually better than blocks/ baseline" hard to answer cheaply; risk of
over-engineering relative to GPT-5.4 mini's actual needs.

**Status**: "active but not full-board-ready" (per `runner/README.md`); most
recently touched code in the repo (HEAD and its 3 immediate ancestors).

**What Fable should decide**: Is this worth running through the
`final_harness_eval_suite` next (it's implementation-complete and
adversarially reviewed), or does its complexity represent exactly the kind
of "build before scoring" pattern that has repeatedly wasted weeks (`04`)?

---

## C. `winning_harness_v1` (2026-05-30 synthesis)

**What**: An 11-step build implementing a synthesis of the 2026-05-30
family-level diagnostic findings — "programmable terminal-first with
persistent session, native function-call mode, structured receipts/evidence
memory, deterministic verifier/artifact checks, service readiness, and
evidence-preserving compression" (inbox A5 verdict). Built via
`runner/packet04_route_manifest.py` route manifests and
`blocks/orientation/phase6_doctrine.py`.

**Why**: Directly targets the worst-measured families from the same day's
diagnostics (filesystem 0/6, service 0/3, context 2/7) using a synthesized
design rather than ad hoc patches.

**Problem solved (intended)**: All of the above families simultaneously, via
one coherent architecture, instead of one-off guards.

**Key files**: `tracking/collab/final_harness_eval_suite/reviews/winning_harness_synthesis_trace_analysis_2026-05-30.md`
(the 11-step spec + promotion standard),
`tracking/collab/final_harness_eval_suite/reviews/winning_harness_v1_goal_closeout_2026-05-30.md`
(closeout), `runner/packet04_route_manifest.py`,
`blocks/orientation/phase6_doctrine.py`,
`tools/run_final_harness_eval_suite_baseline.py` (needs route-manifest
plumbing fix — currently hardcoded to `recipe_control`).

**Tests**: targeted runner/adapter unit tests pass; route manifest builds
and loads correctly.

**Evidence**: **All 4 scored run surfaces (family-level 35/35, final-suite
private 13/13, benchmark 12/12, TB challenge 2/2) came back INVALID** —
100% invalid, not failed — due to local Docker daemon unavailability. Never
rerun on the Azure VM Docker backend.

**Strengths**: Synthesized directly from the best diagnostic data available
at the time; addresses the actual measured worst gaps; implementation
complete.

**Weaknesses**: Completely unvalidated; built the same week the project
pivoted to "model-led substrate v1" instead of resolving the Docker blocker
and rerunning.

**Status**: HOLD. Commit message literally: "HOLD - rerun winning_harness_v1
eval surfaces on certified Docker backend before promotion."

**What Fable should decide**: Cheapest possible action — rerun on Azure VM
Docker — could resolve a major unknown in hours. Should this be step 1 of
the execution plan regardless of which architecture direction is ultimately
chosen, simply because it's "evidence sitting on the table"?

---

## D. Model-Led Substrate v1 (2026-06-05/06, current HEAD)

**What**: Layers a Layer-2 "success auditor" (model-graded completion check)
and explicit success-contract gating onto the Active Evidence Kernel (B).
Adds: `kernel_layer2_audit.py` (prompt builder/parser/fallback/should-run
logic), success-contract injection into prompts, finalization-gate blocking
on `success_contract_missing`, and a fix to context-pack compaction
(adaptive instead of naive truncation).

**Why**: Targets the specific failure mode where the kernel's finalization
gates exist but a model can still claim `governed_pass` without satisfying
its own declared success contract — i.e., closing the loop between
"evidence exists" (Kernel B) and "evidence was actually checked against the
stated goal" (Layer-2 audit).

**Problem solved**: `ungoverned_model_claim`, `success_contract_missing`,
malformed/truncated context packs.

**Key files**: `runner/kernel_layer2_audit.py`, `runner/kernel_gates.py`,
`runner/kernel_context_pack.py`, `runner/kernel_state.py`,
`runner/active_evidence_kernel.py`,
`tracking/collab/model_led_substrate_v1/workers/{worker_f_layer2_audit.md,worker_eval_contract_dirt_audit.md,worker_recovery_command_path_serialization.md}`,
`tracking/collab/model_led_substrate_v1/reviews/{adversarial_review_01.md,accepted_findings_resolution.md}`.

**Tests**: `tests/test_kernel_layer2_audit.py` (7/7), `tests/test_model_led_substrates.py`,
adversarial code review completed with 4 findings fixed.

**Evidence**: None against eval suite. Most recently touched code in the
entire repo (HEAD `f9accef6a`, parents `551d5fedf`, `7df1dc929`,
`232fef973`).

**Strengths**: Closes a specific, well-understood, recurring gap
(finalization-truth bug, `07`); built on top of B rather than replacing it;
adversarially reviewed already.

**Weaknesses**: Same "unscored" problem as B, compounded — it's B plus more
untested surface area; "bypass finalization loop in legacy routes" decision
(from the adversarial review) means there are now two finalization code
paths to maintain.

**Status**: most recent / actively worked, zero eval evidence.

**What Fable should decide**: This is the natural "next thing to score" if
Fable decides Kernel B/D is the direction — but Fable should not assume that
just because it's newest.

---

## E. MLPCP v2 / v3 (PULLED & PAUSED, 2026-06-08→11)

**What**:
- **MLPCP v2**: cockpit + capability-graph + receipt "execute-plan" architecture (purged from master's working tree; only `runner/mlpcp_v2/__pycache__/` bytecode remains).
- **MLPCP v3**: "continuous conversation, typed-tools, Claude/Codex-style" continuity runner. Active VM run files, including audits, patches, and pause state, were pulled and preserved under `tracking/variants/mlpcp_v3/` as of 2026-06-11.

**Why**: Apparently an attempt to bring a Claude-Code-like continuous-session
agent loop (see option H below) into Aether, with explicit phase gating as a
structural alternative to the kernel's gate/evidence model.

**Problem solved (intended)**: Long-horizon coherence, explicit phase
discipline, possibly addressing context/compaction issues differently than
Kernel B/D.

**Key files**: `tracking/variants/mlpcp_v3/MLPCP_V3_PAUSE_STATE_20260611.md` (pause state and status), runs/audits/patches located under `tracking/variants/mlpcp_v3/mlpcp_v3_from_official_run/`.

**Tests**: Background/service tools (`background_job`, `monitor_job`, `service_probe_loop`) compiled successfully during the run.

**Evidence**: `qemu-startup` task passed after applying the `receipt-memory-cockpit` patch. Reruns of hard2 tasks stayed at 0.0 because the model ignored the new tools and kept looping. A generic progress patch was unapplied because the `_execute_single_action` anchor was not found.

**Strengths**: Active VM runs and audits provide direct evidence of model interaction with the new tools; `receipt-memory-cockpit` enabled a pass on `qemu-startup`.

**Weaknesses**: The model did not naturally utilize the background/service tools during hard2 tasks, and the generic progress patch could not be applied due to missing source anchors.

**Status**: Paused after VM disconnect during progress-escalation patch design. Currently stored in `tracking/variants/mlpcp_v3/` as a paused experimental state.

**What Fable should decide**: Whether to reconnect to the VM, inspect the true source anchors, apply the generic progress escalation patch, and resume runs on `extract-moves-from-video` and `install-windows-3.11` to verify if the model can utilize the service tools.

---

## F. Final Harness Eval Suite (`tracking/collab/final_harness_eval_suite/`)

**What**: Not a runner architecture per se, but the **live custom eval
registry** — `final_suite_registry.yaml` (board id
`final_harness_eval_suite_v1`, 8 hard task packs + 5 sentinel/composition
rows, 2 "flagship" tasks), `task_packs/{hard,sentinel,composition}/`,
`family_winner_registry.yaml` (winners: `[]` — nothing promoted ever),
`recipe_candidates.yaml` (only `recipe_control`/`sc_b_01` are real recipes).

**Why**: This is the actual scoring surface every architecture direction
above is supposed to be measured against.

**Key files**: `tracking/collab/final_harness_eval_suite/final_suite_registry.yaml`,
`family_winner_registry.yaml`, `recipe_candidates.yaml`,
`tools/run_final_harness_eval_suite_baseline.py`,
`tools/render_final_harness_scoreboard.py`, 16 run dirs under `runs/`
(2026-05-28 through 2026-05-30).

**Status**: current, but `run_final_harness_eval_suite_baseline.py` is
hardcoded to `recipe_control` — variant route manifests don't flow through
it yet (per inbox A7). This is plumbing that needs fixing regardless of
which architecture direction is chosen.

**What Fable should decide**: This plumbing fix (route-manifest support in
the baseline runner) is likely a prerequisite for scoring *any* of B/C/D —
should it be an early, architecture-agnostic step in the execution plan?

---

## G. Native Harbor / TB-native Runner & Benchmark Adapters

**What**: `runner/benchmark_adapter_terminalbench_native.py` (and siblings
for BFCL, ContextBench, Letta, AceBench — both "native" and non-native
variants), `runner/certified_sandbox*.py`, `runner/docker_sandbox.py`.

**Why**: To run real TB2.0 tasks (and calibration benchmarks BFCL/
ContextBench/Letta/AceBench) under benchmark-native conditions, per
AGENTS.md's mandate that "certified TerminalBench-style/file/verifier evals
must run in benchmark-native Linux/container conditions."

**Problem solved**: Provides the actual scoring backend for TB2.0 — without
this, no architecture direction can produce a "true TB2.0 %" number.

**Key files**: `runner/benchmark_adapter_terminalbench_native.py`,
`runner/benchmark_adapter_terminalbench.py` (non-native, likely
calibration/equivalent-only per the 2026-05-18 authority audit),
`runner/certified_sandbox.py`, `runner/certified_sandbox_backend_probe.py`,
`runner/docker_sandbox.py`, `official_tasks/{extract-moves-from-video,
headless-terminal,install-windows-3.11,mailman}/` (local TB task fixtures).

**Evidence**: The 2026-05-18 authority audit (`vm-pulled:
tracking/collab/autonomous_loop/single_family_winner_discovery_gate/claim_authority_audit.md`)
explicitly states "TerminalBench remains `eval_gap`/equivalent-only anchor,
NOT native authority" as of that date — i.e., even the native adapter's
"native" status was not fully claimed.

**Strengths**: This is the ground truth scoring path — everything else is
proxy/calibration until this works reliably.

**Weaknesses**: Entangled with the Docker-availability problem (`01`, `06`);
"native" vs "equivalent" distinction has been a recurring source of
authority-mislabeling (rows labeled `certified`/`azure_vm_docker` that
actually ran on a failed local Mac Docker socket).

**What Fable should decide**: Whether to invest in hardening this adapter +
sandbox path as the FIRST priority (since every other direction's "real"
score depends on it), independent of which harness architecture wins.

---

## H. Continuous-Session / Claude-Code-style Agent (research-only, not implemented in Aether)

**What**: Not an Aether architecture — a reference pattern from
`research/sources/codebases/quarantine/claude-code_ts_release/` (leaked
Claude Code TS source, quarantined). Documents: **autoDream** (memory
consolidation between sessions), **Stop Hooks** (deny premature
task-complete claims), **ULTRAPLAN** (offload planning to a stronger model),
**KAIROS** (always-on watcher/monitor).

**Why relevant**: The purged MLPCP v3 ("continuous conversation, typed-tools,
Claude/Codex-style... EXPLORE→PLAN→EXECUTE→VERIFY→FINALIZE") was apparently
inspired by this pattern. The BigAI trace-layer's planner/executor/verifier
split (~82% pass, option below) is architecturally adjacent.

**Problem solved (potential)**: Stop Hooks directly addresses
`ungoverned_model_claim`/finalization-truth (same problem as Kernel D's
Layer-2 audit, via a different mechanism — a hook that *vetoes* premature
completion rather than auditing after the fact). ULTRAPLAN maps onto "Fable
plans, GPT-5.4 mini executes."

**Key files**: `research/sources/codebases/quarantine/claude-code_ts_release/`
(read selectively — this is a large leaked codebase; do not dump it).

**Status**: research reference only, nothing implemented in Aether.

**What Fable should decide**: Whether Stop-Hook-style completion vetoes are
a simpler/cheaper alternative or complement to Kernel D's Layer-2 audit
mechanism for closing the finalization-truth gap.

---

## I. BigAI Trace-Layer Reference Architecture (research-only, strongest empirical data point)

**What**: `research/analysis/bigai_trace_layer/` — corpus-only post-hoc
analysis of 314 BigAI TB2.0 runs across 86 tasks, ~82% pass rate
(256 pass / 53 fail / 5 unknown), using a planner/executor/verifier
architecture with Gemini 3.1-pro-preview.

**Why relevant**: This is the **highest pass-rate reference point in the
entire repo** (~82% on real TB2.0 tasks, by another team's harness) — a
calibration target and a source of mechanism ideas (what does an
82%-passing planner/executor/verifier loop actually do differently from
Aether's current ~unknown%?).

**Key files**: `research/analysis/bigai_trace_layer/` (read the synthesis
docs, not the raw 314 traces).

**Status**: external, analyzed, not implemented as an Aether architecture.

**What Fable should decide**: Should a subagent do a structured diff between
this 82%-passing architecture and Aether's current best candidate, focused
on the families where Aether scores worst (filesystem, service readiness,
context)?

---

## Summary table

| Direction | Code status | Eval status | Risk if chosen blind |
|---|---|---|---|
| A. blocks/ baseline | exists, current | family-level scored (mixed) | under-powered alone for filesystem/service/context |
| B. Active Evidence Kernel | exists, active-not-ready | unit-tests only | large unscored surface |
| C. winning_harness_v1 | exists, HOLD | 100% INVALID (Docker) | cheap to unblock — rerun first |
| D. Model-led substrate v1 | exists, newest | unit-tests + adversarial review only | newest ≠ best; unscored |
| E. MLPCP v2/v3 | pulled/paused (v3) | partial (qemu-startup pass; hard2 fail) | unapplied generic progress patch |
| F. final_harness_eval_suite | exists, current | IS the scoring surface | route-manifest plumbing gap blocks variant scoring |
| G. Native TB/Harbor adapter | exists, current | "equivalent" not "native" per 05-18 audit | everything else depends on this working |
| H. Continuous-session (Claude Code) | research only | n/a | speculative, but cheap mechanism ideas (Stop Hooks) |
| I. BigAI planner/executor/verifier | research only | 82% on real TB2.0 (other team) | best calibration target available |
