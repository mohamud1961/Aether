# 00 — READ ME FIRST

## What this packet is

This is **not a variant continuation packet**. It is a **strategic evidence
packet** assembled for an AI planner ("Fable 5" / "Fable") whose job is to
decide the fastest *honest* path from the current state of the **Aether**
project (`/Users/mohamud/Downloads/harnesseng`) to **true 100% pass rate on
Terminal-Bench 2.0**, evaluated under real benchmark-native conditions, with
no benchmark-specific shortcuts, hidden-test leakage, or evaluator gaming.

Aether is an "automated evaluation engine for high-reliability, long-running
autonomous agents" — eval-first harness engineering for an LLM-driven
terminal agent. The current declared strategic stage (per `AGENTS.md`) is the
**"Eval-First Harness Reset"**: promotion authority is supposed to move from
prose/packets/route-manifests to scored, benchmark-grade eval evidence. In
practice (see `04` and `06`), that reset is itself incomplete and contested —
multiple architecture lines have been built, partially scored, or abandoned
in just the last ~4 weeks (mid-May through 2026-06-06).

## What Fable decides

Fable is the **Chief Architect**. Fable should:

1. Form an independent verdict on the current architecture landscape (`03`),
   decision history (`04`), and source code (`05`) — not just accept any one
   faction's framing.
2. Decide what to **keep, kill, merge, or redesign** — including possibly
   designing something new that isn't any of the existing variant families.
3. Produce a concrete, evidence-gated execution plan targeting **GPT-5.4
   mini** as the executor model, using subagents (`11`) for narrow,
   auditable lanes.
4. Decide how to close the **failure taxonomy** (`07`, `08`) without
   benchification (`09`).

This curator did **not** make that call. Where evidence conflicts, both sides
are presented.

## Token budget

Target 50k–100k tokens across all 16 files + 4 manifests. Files are written
densely — curated summaries and pointers, not raw log dumps. If you need raw
detail (a specific trace, a specific JSON scoreboard), use
`file_selection_manifest.json` to find the exact path and read it directly —
don't expect it pasted here.

## What NOT to do

- Do **not** assume the most recently-touched architecture ("model-led
  substrate v1" / `active_evidence_kernel`) is automatically the right one —
  it has **zero scored eval results** as of HEAD (commit `f9accef6a`,
  2026-06-10). It is simply the most recently *worked-on*.
- Do **not** treat unit-test pass counts (194/205/211/220...) as evidence of
  live or benchmark behavior. See `08` for the unit-vs-smoke-vs-live-vs-
  certified distinction.
- **Do not** re-promote "Combined Guard V1.5" as-is — its target tasks
  passed (2/2) but it caused a **sentinel regression** (0/1), which under the
  project's own promotion rules (`AGENTS.md`) means it should not have been
  called a "perfect tournament run."
- **Do not** assume MLPCP v3 is completely gone or unrecoverable — while MLPCP v2/v3
  was previously purged from master's working tree, we have now pulled the actual
  runs, patches, audits, and pause state from the official VM run into
  `tracking/variants/mlpcp_v3/` (as of 2026-06-11). It is paused but active.
- **Do not** read `docs/current_surface_map.md` or `docs/deprecation_map.md`
  — `runner/README.md` references them but **they do not exist anywhere in
  the repo or git history**. This is a known broken pointer (see `02`, `gap_report.md`).
- **Do not** BENCHIFY, IN ANY SHAPE OR FORM, WHETHER THAT IS TASK SPECIFIC OR TERMINAL BENCH 2.0 TARGETING AS A WHOLE PLEASE. I want a solution that is GENERALIZABLE. DO NOT OPTIMIZE FOR THE BENCHMARK. OPTIMIZE FOR GENERALIZABILITY.

## Most important files (read first)

In order:

1. `01_EXECUTIVE_BRIEF.md` — the one-page truth.
2. `02_CURRENT_WORKSPACE_MAP.md` — so you don't read stale paths.
3. `06_RUN_AND_EVAL_EVIDENCE.md` — what has actually been measured.
4. `04_VARIANTS_AND_DECISION_HISTORY.md` — how we got here, including dead ends.
5. `03_ARCHITECTURE_LANDSCAPE.md` — the live menu of architecture options.
6. `07` / `08` — failure taxonomy and what's actually solved.
7. `10_FASTEST_PATH_OPTIONS.md` — route options (no final pick made for you).
8. `12_FABLE_5_MASTER_PROMPT.md` — your operating prompt and required outputs.

`context_pack_index.md` has the full reading guide and a 16-question
self-check confirming this packet's coverage.

## Glossary (minimal)

- **TB2.0**: Terminal-Bench 2.0, the target benchmark.
- **Aether**: this project's name for the harness.
- **Kernel / Active Evidence Kernel**: `runner/active_evidence_kernel.py` +
  15 `runner/kernel_*.py` modules — current "active but not board-ready" runner.
- **MLPCP v2/v3**: An experimental variant family (cockpit/capability-graph/receipts v2; continuous-conversation typed-tools v3). While v2 remains purged, MLPCP v3 runs, audits, patches, and pause state from 2026-06-11 have been pulled to `tracking/variants/mlpcp_v3/` for analysis (`04`, `06`).
- **Model-led substrate v1**: the most recent (2026-06-05/06) architecture
  push, layering a Layer-2 success auditor and success-contract gating onto
  the active evidence kernel. Implemented, adversarially reviewed, never
  scored.
- **`winning_harness_v1`**: a 2026-05-30 attempt at a synthesized "winning"
  harness from family-level eval data. Code exists, but every scored run was
  environment-INVALID (no local Docker). Status: HOLD.
- **GOVERNED_STATUSES**: the kernel's outcome vocabulary
  (`governed_pass`, `ungoverned_model_claim`, `verifier_failed`,
  `artifact_gate_failed`, `provenance_gate_failed`,
  `native_tool_contract_failed`, `service_not_ready`, `invalid_environment`,
  `budget_exhausted_open_obligations`).
- **Benchification**: building harness behavior that exploits this
  benchmark's specifics rather than generalizable agent capability — see `09`.
- **vm-pulled / push-master**: a parallel branch lineage (commit
  `f7730830b` and descendants) containing files referenced by `AGENTS.md`
  that are **missing from `master`** (notably
  `tracking/collab/variant_hypothesis_backlog.md`).
