# 05 — Source Code Context

Curated, file-level context for the highest-value source files. "Read
directly?" tells Fable/subagents whether to open the file or trust this
summary.

## Main runner / agent loop

### `runner/agent.py` (current, ~75KB)
- Purpose: "Core baseline runner that composes fixed Packet 02 blocks into
  one run." This is the actual entrypoint most current eval runs go through.
- Key dependencies: `runner/action_bus.py` (`ActionBus`),
  `runner/docker_sandbox.py` (`DockerSandbox`), **`runner/evidence_kernel.py`**
  (`EvidenceKernel` — the OLDER kernel, not `active_evidence_kernel.py`),
  `runner/evaluator.py` (`apply_packet01_guards`, `build_score_envelope`),
  `runner/logger.py` (`RunLogger`).
- **Critical finding**: `agent.py` imports `EvidenceKernel` from
  `evidence_kernel.py`, NOT the active evidence kernel. This means the
  "active but not full-board-ready" kernel (`active_evidence_kernel.py`,
  Architecture B/D in `03`) is **not currently wired into the main runner
  entrypoint** — it's a parallel/standalone module. Confirm this with a
  grep before assuming any eval run exercised it.
- Read directly?: Yes — this is the actual current execution path for most
  eval runs.

### `runner/evidence_kernel.py` (current, used by `agent.py`)
- Purpose: "Integrated evidence-kernel primitives for terminal-first harness
  runs." Defines `ACTION_TYPES` (command/script/...), uses
  `runner/action_bus.py`'s `infer_action_type`.
- Architecture role: This is the kernel that's actually live in `agent.py`
  today — likely the predecessor to / narrower version of
  `active_evidence_kernel.py`.
- Known issues: unclear how it relates to `active_evidence_kernel.py` —
  feature parity unknown. **A direct diff between `evidence_kernel.py` and
  `active_evidence_kernel.py` would resolve a key open question** (is
  active_evidence_kernel a strict superset, or a parallel rewrite?).
- Status: current/live (via agent.py).
- Read directly?: Yes, alongside `active_evidence_kernel.py`, specifically
  to do the diff above.

### `runner/active_evidence_kernel.py` (active-not-board-ready)
- Purpose: "Active evidence-kernel runtime with modular generic adapters."
- Composes: `kernel_compaction` (`build_compaction_prompt`,
  `create_compaction_boundary`, `extract_compaction_summary`,
  `rehydrate_after_compaction`), plus (per `04`/`03`) the other 14
  kernel_*.py modules.
- Architecture role: the centerpiece of Architecture B/D (`03`).
- Status: implemented, unit-tested, adversarially reviewed (Phase 6,
  `04`), **not invoked by `agent.py`** (per finding above) and not yet run
  against the eval suite.
- Read directly?: Yes — central to any verdict on Architecture B/D.

## Kernel modules (`runner/kernel_*.py`)

### `runner/kernel_gates.py`
- Purpose: "Deterministic verifier, artifact, and finalization gates for the
  active kernel." Defines `GOVERNED_STATUSES` (the 9-value outcome
  vocabulary — see `00`/`01`).
- Imports `kernel_artifacts.build_first_verified_success_record`,
  `kernel_evidence_trail.evaluate_evidence_trail_requirements`,
  `kernel_layer2_audit.normalize_layer2_audit_state`.
- Architecture role: the finalization gate logic that Phase 6's adversarial
  review found was NOT blocking `governed_pass` on
  `success_contract_missing` (now fixed).
- Read directly?: Yes — central to understanding the finalization-truth
  fix.

### `runner/kernel_layer2_audit.py`
- Purpose: "Layer 2 Success Audit implementation for model-led completion
  checking." Includes `_clean_hidden_refs()` — recursively strips keys
  containing `expected`/`hidden`/`secret`/`grader`/`ground_truth` from data
  before it's shown to the model (an **anti-leakage** mechanism worth
  noting for `09`).
- Built by "Subagent Worker F" (Phase 6, 2026-06-05), 7/7 unit tests pass
  (`tests/test_kernel_layer2_audit.py`).
- Status: implemented and (after the 06-05 review) wired into
  `kernel_gates.py`.
- Read directly?: Yes — small, central to Architecture D, and the
  `_clean_hidden_refs` pattern is directly relevant to anti-benchification
  design (`09`).

### `runner/kernel_recovery.py`
- Purpose: "Failure signature extraction and bounded recovery policy for the
  active kernel." `handle_error()` classifies exceptions and returns a
  "truthful recovery action"; uses `runner/action_bus.extract_command` and
  `runner/model_client.ModelClientError`.
- Recently fixed (2026-06-06): raw heredoc commands were polluting failure
  signatures via `kernel_artifacts.py`'s path-extraction — fixed to use
  bounded path refs + command digests.
- Read directly?: Yes if working on recovery/failure-classification
  (relevant to `07`'s "bad recovery" and "repeated inspection/repair loops"
  failure classes).

### `runner/kernel_context_pack.py`
- Purpose: "Evidence-preserving context-pack projection and history
  manager." Composes `kernel_evidence_trail.project_evidence_trail_state`,
  `kernel_receipts.{compact_receipt_digest,summarize_receipt}`,
  `kernel_services.project_service_summary`,
  `kernel_artifacts.summarize_artifact_registry`, plus
  `blocks/context/full_history.append_observation`.
- Recently fixed (2026-06-05): `render_context_pack` was doing naive
  `compact[:6000]` character-slicing — replaced with adaptive compaction
  using the above projections.
- Read directly?: Yes — central to context/compaction failure class (`07`).

### `runner/kernel_success_contract.py`
- Purpose: "Pure success-contract substrate helpers for model-led runs."
  Defines `ALLOWED_SUCCESS_CONTRACT_KEYS` (`status`, `contract_id`,
  `source_receipt_id`, `criteria`, `required_artifacts`, `required_checks`,
  ...).
- Architecture role: the schema for what a model must declare as its
  "success contract" — consumed by `kernel_layer2_audit.py` and
  `kernel_gates.py`.
- Read directly?: Only if directly auditing the success-contract
  enforcement chain.

### `runner/kernel_artifacts.py`
- Purpose: "Generic artifact registry helpers for the active kernel."
  Defines `ARTIFACT_TYPE_GUESSES` (text/json/csv/archive/document/image/
  audio/video/binary/unknown), path-ref extraction (`extract_artifact_path_refs`,
  used by `kernel_state.py` and the recovery fix above).
- Read directly?: Only if working on artifact-gate or recovery-fingerprint
  logic.

### `runner/kernel_state.py`
- Purpose: "Run-local state projection for the active evidence kernel."
  Uses `kernel_evidence_trail.extract_evidence_trail_records_from_receipt`,
  `kernel_artifacts.extract_artifact_path_refs`.
- Read directly?: Only if debugging state projection.

### Other kernel modules (lower priority to read directly)
`kernel_receipts.py`, `kernel_interrupts.py`, `kernel_working_window.py`,
`kernel_tpm_pacer.py`, `kernel_compaction.py`, `kernel_evidence_trail.py`,
`kernel_native_tools.py`, `kernel_control_plane.py`, `kernel_services.py` —
each is a focused helper module consumed by the modules above. Read only if
a specific failure class (`07`) implicates one directly (e.g.
`kernel_services.py` for the service-readiness 0/3 family).

## Route manifest / measurement / benchmark adapters

### `runner/packet04_route_manifest.py`
- Purpose: "Packet 04A execution route-manifest helpers." Defines
  `BASELINE_VARIANT_ID = "sc_b_01"`, `DEFAULT_PACKET04_ROUTE_SCOPE =
  "packet04a_first_slice"`, `PACKET04_SLICE2_ROUTE_SCOPE`,
  `PACKET05A_TOOL_CALL_SCOPE`.
- Architecture role: this is the route-manifest plumbing `winning_harness_v1`
  (Architecture C) builds on, and the thing
  `tools/run_final_harness_eval_suite_baseline.py` does NOT yet route
  through (hardcoded to `recipe_control`).
- Read directly?: Yes if pursuing Architecture C or fixing the
  baseline-runner route-manifest plumbing gap.

### `runner/phase65_measurement_contracts.py` / `phase65_measurement_grading.py`
- Purpose: "Task-contract loaders" / "Truthful graders for the bounded Phase
  6.5 measurement repair slice." `load_extract_moves_contract()` parses
  `tests/test_outputs.py` via `ast` to extract a `SOLUTION` constant —
  i.e. grading is done by parsing the official task's own test file, not by
  a hardcoded answer. `phase65_measurement_grading.py` imports
  `runner.letta_context_bench.grade_letta_filesystem_answer`.
- Architecture role: "current" per `runner/README.md` — the truthful-grading
  layer for at least the `extract-moves-from-video` official task family.
- Read directly?: Yes if auditing grading correctness / anti-benchification
  (`09`) — this is exactly the kind of code that must not special-case
  specific task answers.

### `runner/benchmark_adapter_terminalbench_native.py`
- Purpose: "Native TerminalBench bridge with provenance checks and official
  verifier execution." `EXPECTED_REMOTE_FRAGMENT = "harbor-framework/terminal-bench"`
  — i.e. it checks that the TB harness being used is actually the official
  `harbor-framework/terminal-bench` repo (provenance check against
  swapped/forked benchmarks).
- Architecture role: the "native" TB2.0 scoring path (Architecture G).
- Status caveat: per the 2026-05-18 authority audit, "native" status was
  explicitly NOT fully claimed as of that date — verify current status.
- Read directly?: Yes — this is the file that ultimately produces a "true
  TB2.0" number, if/when it runs successfully.

### `runner/certified_sandbox.py`
- Purpose: "Certified sandbox contract helpers for benchmark-native
  execution." `DEFAULT_CONTAINER_WORKSPACE_ROOT = "/app"`.
- Architecture role: the workspace-contract layer AGENTS.md's
  `certified_sandbox_contract` Goal #1 refers to.
- Read directly?: Yes if working on the Docker/eval-loop blocker (`01`'s
  "immediate decision").

## Blocks (modular harness, Architecture A)

### `blocks/execution/flat_loop.py`
- Purpose: "Simple while-not-done loop — basic agent loop with no phases or
  gates." `run_loop(model, tools, context, max_steps, tool_definitions)`.
- This is literally the Terminus-equivalent loop confirmed in inbox A4.
- Read directly?: Yes — small, foundational, worth understanding before
  judging whether kernel complexity (B/D) is additive or redundant.

### `blocks/tools/raw_bash.py`
- Purpose: defines the single `raw_bash` tool schema (`{"command": string}`)
  — "Execute a bash command in the sandbox working directory."
- Read directly?: Optional — trivial, ~20 lines.

### `blocks/orientation/phase6_doctrine.py`
- Purpose: "Phase 6 context, completion, and tool-call repair doctrines."
  Defines named "doctrines" like `orient_model_led_compaction()` (variant id
  `candidate_plus_model_led_compaction_01`) and
  `orient_codex_style_handoff_compaction()` (variant id
  `candidate_plus_codex_style_handoff_compaction_01`, "done/next/files/
  commands/risk handoff" — note this is explicitly a Codex-style handoff
  format, relevant to option H in `03`).
- Architecture role: used by `winning_harness_v1` (Architecture C); a menu
  of named, swappable orientation/compaction strategies tagged with variant
  IDs that map onto the backlog (`04`).
- Read directly?: Yes if evaluating Architecture C or compaction strategies
  generally — it's a useful menu of named approaches even independent of
  whether C itself is chosen.

## Tests

- `tests/test_kernel_layer2_audit.py` — 7/7 pass; unit-level only.
- `tests/test_model_led_substrates.py` — covers the Phase 6 fixes
  (success-contract injection, finalization gate blocking, context-pack
  compaction). Unit-level only.
- 120 files total under `tests/`. The broad growth from ~194 to 220+
  passing tests (`06`) is spread across kernel modules, benchmark adapters,
  and eval-substrate contracts — **none of this constitutes live or
  benchmark evidence** (`08`).

## What NOT to read directly (large/low-value)

- `runner/packet07_*.py` (~18 files) and `runner/successor_*.py` (~17
  files) — historical; consult `04` instead of reading these.
- `tracking/collab/gpt55pro_best_harness_synthesis/INPUT_CONTEXT_AND_PROMPT*.md`
  — 1.5–3.16MB, do not open.
- `research/sources/codebases/quarantine/claude-code_ts_release/` — large
  leaked codebase; read only the specific autoDream/Stop-Hooks/ULTRAPLAN/
  KAIROS summary docs if they exist, not the raw source tree.
