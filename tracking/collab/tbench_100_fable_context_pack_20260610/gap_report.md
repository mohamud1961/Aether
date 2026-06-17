# Gap Report

This file lists everything referenced across the project's own docs that
this packet's curator could **not** verify, locate, or fully resolve —
so Fable knows what's missing rather than assuming silence means "fine."

## 1. Missing files referenced by current docs

- **`docs/current_surface_map.md`** — referenced by `runner/README.md` as
  the authoritative current/active/historical surface map. **Does not
  exist anywhere in the repo** (`docs/` itself does not exist). The
  `02_CURRENT_WORKSPACE_MAP.md` in this packet is a best-effort
  reconstruction but is not authoritative in the way the missing file
  would be.
- **`docs/deprecation_map.md`** — same situation, referenced by
  `runner/README.md` for historical/deprecated surfaces. Does not exist.
- **`tracking/collab/variant_hypothesis_backlog.md`** /
  **`.yaml`** — referenced by `AGENTS.md` as the canonical variant queue.
  **Not present on `master`** (HEAD `f9accef6a`). Found only on the
  `vm-pulled` branch and on commit `f7730830b` and its descendants. Fable
  should treat the vm-pulled copy as current content but note it has not
  been merged to master — reconciliation is itself a Lane 7 task.
- **Azure VM lifecycle scripts** — `AGENTS.md` references
  `scripts/deallocate_harnesseng_vm.sh` and
  `scripts/configure_harnesseng_vm_autoshutdown.sh` as part of the standard
  run procedure. **Neither exists** in `scripts/`, which only contains
  `build_harnesseng_runtime_bundle.sh` and
  `deploy_harnesseng_worker_runtime.sh`. This directly blocks
  `10_FASTEST_PATH_OPTIONS.md` Option 1 and Option 5's first steps unless
  recreated or an equivalent workflow exists elsewhere (e.g. on the VM
  itself, not checked into this repo — unconfirmed).

## 2. Runs mentioned but evidence missing/incomplete

- **`tracking/collab/local_iteration_loop_2026-06-04`** — directory
  structure (`baseline_runs/20260604T111218Z/`,
  `baseline_runs/20260604T112901Z/`, `full_board_rerun/20260604T151902Z/`,
  `next_bounded_vm_slice/20260604T145313Z/`) confirms a real run happened
  against `final_harness_eval_suite` task packs (`fhard_01-08`,
  `fsent_01/03/05` confirmed present in directory names; `fsent_02/04`
  likely but not directly confirmed). **Only `__pycache__/*.pyc` for
  `grade.py`/`hidden_verifier.py` survive** — no `result_rows.jsonl`,
  `scoreboard.json`, or `answer.json` recoverable from any of the 4 run
  dirs. We cannot tell Fable what this run actually scored.
- **2026-05-30 "lean probe" regression** — `01`/`08` reference a lean-mode
  run that "regressed" relative to Antigravity's Zero-Abstraction Engine
  predictions and involved "evidence-hiding." The curator located the
  prediction document and the family-level diagnostic but did not locate a
  single consolidated run artifact tying the regression to specific
  `result_rows`/`scoreboard` entries beyond what's summarized in
  `06_RUN_AND_EVAL_EVIDENCE.md` section 3. Treat the regression as
  **documented but not independently re-verified** by this curation pass.
- **"194→220+" test count** — `04`/`06` cite test-suite growth from 194 to
  220+ across Phases 5-6. The curator counted 120 files under `tests/` at
  HEAD but did not run `pytest --collect-only` to get an exact current test
  count, nor verify the historical 194/220 figures against specific commits.
  This is a low-importance gap (test counts are unit-test-tier evidence
  regardless) but flagged for completeness.

## 3. Tests referenced but not executed

- This curation pass **did not run any test suite** (out of scope for a
  curator role — running tests could itself produce stale or
  environment-dependent results that should be Fable/Lane-5's call). Pass
  rates cited in `06`/`08` (e.g. "7/7" for `kernel_layer2_audit`) are taken
  from ledger inbox claims, not independently re-run. Fable's first 72-hour
  plan should likely include re-running the existing test suite as a sanity
  baseline before any new work.

## 4. Unclear current runner / unclear latest variant

- **`runner/agent.py` vs `runner/active_evidence_kernel.py`**: confirmed via
  direct read that `agent.py` imports `EvidenceKernel` from
  `evidence_kernel.py`. This means Architecture B/D (Active Evidence
  Kernel / Model-Led Substrate v1) is **not reachable from the default
  runner entrypoint** without additional wiring. This is the single most
  load-bearing open question in the packet (propagated to `01`, `03`, `05`,
  `08`, `10`, `12`) — but the curator did not attempt the wiring fix itself
  (out of scope for curation), so the *size* of the wiring gap (trivial vs.
  deep) is unknown.
- **"Latest variant"**: by commit timestamp, `model_led_substrate_v1`
  (2026-06-05/06) is the most recent substantive work, and the recovery
  command path-serialization fix (`551d5fedf`) is HEAD's parent. But by
  *implementation completeness*, `winning_harness_v1` (2026-05-30,
  Architecture C) is more "done" (11-step build complete) yet 100% INVALID
  due to environment, not architecture. Fable should not assume "most
  recent" = "most ready."

## 5. Conflicting docs / stale path conflicts

- **`autonomous_loop/single_family_winner_discovery_gate/`** — diverges
  between `master` (near-empty stub) and `vm-pulled` (full closeout +
  claim_authority_audit). Unclear whether master's stub was a placeholder
  that was never filled, or whether vm-pulled's content was written and
  never merged back. Either way, **master alone is missing this evidence**.
- **`first_result_attribution_mechanism_tournament/`** vs
  **`tooling_tool_contract_certified_tournament_clean/`** — the latter
  appears to be an attempted "clean" re-run/re-framing of the former but is
  mostly empty. Unclear if this represents an abandoned cleanup attempt or
  an in-progress one. Not blocking, but noted as workspace clutter Fable may
  want a Lane-7 pass to resolve.
- **`tracking/ledger/decisions.md`/`timeline.md`/`claims.md`** (canonical,
  last entry 2026-03-29) vs **`tracking/ledger/inbox/2026-05-30` through
  `2026-06-06`** (27 unprocessed raw entries spanning the most eventful
  5 weeks of the project). The canonical ledger is **stale by over 2
  months** relative to actual project activity. Any "what does the project
  currently believe" question should be answered from the inbox + this
  packet, not from `decisions.md`.

## 6. Evidence not inspected (deliberately, for token budget)

- `tracking/collab/gpt55pro_best_harness_synthesis/` — 1.5-3.16MB raw
  context dumps. Confirmed to exist (location: under `tracking/collab/`,
  exact branch/commit not double-checked beyond initial discovery) but not
  read in full. Summarized secondhand via `04`/`09` based on file names and
  partial greps. If Fable needs the "Stem Agents" / Vix trajectory details
  in full, this is the source — but read selectively, not wholesale.
- `research/sources/codebases/quarantine/claude-code_ts_release/` — large
  quarantined source tree. Patterns (autoDream, Stop Hooks, ULTRAPLAN,
  KAIROS) were identified via targeted search/grep, not a full read of the
  codebase.
- `research/analysis/bigai_trace_layer/` — 314 run traces. The ~82%
  (256/53/5) figure and planner/executor/verifier architecture description
  come from summary/index-level files in this directory, not from reading
  individual trace files.
- Full contents of `tracking/ledger/inbox/2026-05-30/` (19 files) — only a
  representative subset was read in detail; the rest were catalogued by
  filename/topic via the research agent's digest.

## 7. Other unresolved items

- **"5.4 Pro ordered-roadmap direction"** — `AGENTS.md` cites this as a
  strategic source of truth for the current Eval-First Harness Reset stage,
  but it is not itself a file in the repo (likely an external
  conversation/decision not captured in writing). Fable should be aware
  this "upstream justification" is not independently auditable from the
  repo alone.
- **Native vs. equivalent TB2.0 adapter status as of HEAD** — the
  "equivalent, not native" finding is dated 2026-05-18
  (`claim_authority_audit.md`). No subsequent audit of
  `runner/benchmark_adapter_terminalbench_native.py` was found between
  2026-05-18 and HEAD (2026-06-10), so its status **could have changed
  (improved or not) without being re-audited**. This is exactly
  Option 5's first step.
- **Exact scope of "two finalization code paths"** (Phase 6 / `07`#7) — the
  adversarial review and resolution docs describe this as fixed at the code
  level, but the curator did not trace both paths end-to-end to confirm
  they're now unified vs. merely both individually patched. Flagged for
  Lane 1 (Architecture Audit).
