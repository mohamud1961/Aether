# ROAD TO 100 — Aether-Next execution plan

Written 2026-07-05 by Fable 5 (session 4). Source of truth for finishing the harness.
**2026-07-08: superseded by "Road v2" at the bottom of this file** (post-sentinel audit +
owner design review). Items 1-7 below remain as historical record; items 8-9 are absorbed
into Road v2 with changed ordering and preconditions.
Resume rule: read this + `AETHER_NEXT_PROGRESS.md`, verify claims against code/tests, continue top-down.
Suite gate: `python3.11 -m pytest tests -q` must stay green after every slice. Never commit to master.

## State at time of writing

- HEAD `07c8a5d2`, branch `codex/canonical-aether-consolidation`, suite 345 passed.
- All audit root-causes from 12 runs fixed and committed (see AETHER_NEXT_PROGRESS.md "Batch5 audit execution").
- Docker is UP. Validation batch is being launched via a Haiku monitor agent.

## The ordered road (strike through as completed; record evidence refs)

1. ~~**Validation batch**~~ DONE — **3/3 OFFICIAL GRADER PASSES** (`local_goal_runs/20260705T201305Z_validation3/`):
   - headless-terminal: completed, reward 1.0, **8 steps** (was timeout/ungraded at 34) — prediction HIT
   - kv-store-grpc: reward 1.0, 22 steps (was timeout/ungraded at 49) — prediction HIT; internal solver_submit_stalemate (see below)
   - code-from-image: reward 1.0, **16 steps** (was 0.0 at 120 steps) — the VISION LANE converted an unreachable task — prediction EXCEEDED
   - Residual defect found via auto-persisted evidence bundles and FIXED (`d4367064`): the verifier asked the SOLVER to "provide the contents of /app/output.txt" (unsatisfiable — solver claims never enter the state-only packet); path-bearing prose missing-evidence requests now trigger the verifier's own read_file/perceive_artifact inspection within the same round. The kv/code-from-image internal stalemates should convert to internal `completed` on the next run.
   Original spec:
   `python3.11 run_pilot.py --tasks headless-terminal,kv-store-grpc,code-from-image --vision-deploy-env AZURE_OPENAI_GPT54_MINI_DEPLOYMENT --max-steps 40 --trace-dir local_goal_runs/<stamp>/traces --out local_goal_runs/<stamp>/results.json`
   Prediction (record hit/miss): headless PASS, kv PASS, code-from-image first genuine attempt (pass uncertain).
   Interpretation rules: graded_after_timeout rows are valid; verifier evidence bundles auto-persist under trace_dir.

2. ~~**Verifier economics slice**~~ DONE (`3eceeba6`): unchanged-packet memoization + changed-inputs-only checks, 3 tests. Original spec: (biggest efficiency lever; openssl burned 16 rounds on identical state)
   a. Unchanged-packet memoization: hash the state-only packet minus step/reason (`verifier_packets.packet_state_signature`); if identical to last judged signature and last verdict non-completed → skip the model call, record `model_verifier_skipped:unchanged_state` receipt, reuse verdict, count toward submit-stalemate.
   b. Changed-inputs-only check re-execution: in `kernel_turns.run_submit_turn`, skip re-running a planned check when no state_change receipt has occurred since its last execution; record `check_skipped_unchanged` receipt with the prior outcome (kv ran 117 check executions).
   Tests: memoized round produces no verify call; state change re-enables both; stalemate still fires.

3. ~~**Verifier-side vision parity**~~ DONE (`3eceeba6`): `perceive_artifact` inspection kind + guidance + tests. Original spec:: new inspection kind `perceive_artifact` in `verifier_inspector.py` → uses kernel/hooks `perceive_image` (available via `kernel_verifier._call_verify`'s access to hooks) on an image path; result labeled `model_transcription_not_ground_truth`. Without a vision model → explicit error row. Advertise in `model_prompts.py` inspector kinds. Test with stub vision hooks.

3.5. ~~**Schema-humility guardrail**~~ DONE (post-validation slice): architect prompt + runtime manual now explicitly forbid hardening placeholder notation such as `[integer]` into list/array contracts unless the task says so, and `config_realization_audit.guardrails.schema_humility` reports suspected placeholder-shape hardening as advisory evidence. This targets the video-processing audit root cause without adding task-specific judgment or rewriting the model's workbench.
   Evidence: `python3 -m pytest tests/test_vnext_workbench_ir.py -q` → 27 passed; `python3 -m pytest tests -q` → 331 passed.

3.6. ~~**Verifier output-handle inspection**~~ DONE (post-perceptual retry slice): `read_output` is now a read-only verifier inspection kind, advertised in the verifier prompt protocol and backed by ledger stdout/stderr handles including spooled full streams. This closes the generic state-inspector gap where the verifier could see that command-output handles existed but could not dereference the transcript it needed.
   Evidence: `python3 -m pytest tests/test_verifier_probes.py -q` → 13 passed; `python3 -m pytest tests -q` → 333 passed.

3.7. ~~**Transcript auto-realization**~~ DONE (follow-up verifier slice): prose missing-evidence requests for stdout/stderr/transcripts now auto-realize into `read_output` inspections against the latest relevant packet output handles, just as path-bearing prose requests already auto-realized into `read_file`/`perceive_artifact`. This targets the video-processing stalemate generically without making the harness decide task correctness.
   Evidence: `python3 -m pytest tests/test_verifier_economics.py tests/test_model_hooks.py -q` → 27 passed; `python3 -m pytest tests -q` → 335 passed.

4. **Perceptual-class live proof** (after 1 lands): one run each
   `--tasks video-processing --vision-deploy-env ...` and `--tasks qemu-startup ...` (max-steps 60; budgets honor task.toml). Interpret: solver should sample frames via ffmpeg + inspect_artifact(vision); verifier should perceive frames itself (needs slice 3).

5. ~~**Step-budget expectations**~~ DONE (`e5f5e179`): architect `expected_steps` → config_realization → result-row `step_efficiency`. Original spec:: architect config optional `expected_steps` (int) in HarnessConfigIR (workbench_config parse + prompt mention); thread into result rows as `expected_steps` + `step_efficiency = step/expected`; no runtime enforcement (advisory metric only — never a gate).

6. **Size-cap closure** PARTIAL (`e855e05c` + follow-up): docker_runner 965→693 (DockerExecExecutor extracted), model_hooks 619→446 (model_parse.py), compiler 664→606 (compiler_prefix.py). Remaining over-cap: docker_runner 693 (run_tbench_task orchestration — split record assembly next), compiler 606 (split config_realization builder next). Original spec:: docker_runner 965 → split executor class into `runners/docker_exec_executor.py` (~250 LOC) and grader/reward resolution into `runners/grader_resolve.py`; compiler 664 → extract prefix-section builder into `compiler_prefix.py`; model_hooks 619 → extract solver/architect parse helpers into `model_parse.py`. Suite green after each move.

7. ~~**Repo hygiene**~~ DONE (`e5f5e179`): run/eval artifact dirs gitignored. Original spec:: add `.gitignore` entries under aether_next_build for `local_goal_runs/`, `deterministic_integration_eval_*/`, `component_eval_*/`, `architect_only_eval_*/`, `verifier_only_eval_*/`, `trace_verifier_replay_*/`, `DOCKER_ISOLATION_SMOKE_*.json` (already-tracked files stay tracked; new artifacts stop polluting status). Do NOT untrack existing evidence without an explicit decision.

8. **10–20 task diverse board** at fixed SHA (after 1–4): pick across classes — file/data (log-summary, gcode-to-text), git (fix-git, git-multibranch), query (sparql, regex-log), build (write-compressor, polyglot-c-py), service (nginx-request-logging, pypi-server), security (crack-7z-hash, vulnerable-secret), perception (code-from-image, video-processing), interactive (headless-terminal, qemu-startup), ML (train-fasttext). Record per-class pass rates + step efficiency. This produces the first honest capability %.

9. **Consolidation rename** `aether_next_build/aether_next` → `aether/` per CLAUDE.md target (last, after board is green): move package, update imports, keep `aether_next` shim for one release, update docs.

## Standing invariants (do not regress)
Fail-closed config; state-only verifier packet (forbidden-field assertion); no solver self-report authority; no task-name logic; advisory-only memory/no-progress; full outputs by handle; cache-stable prefix; architect_defect never laundered; grader external post-terminal only; every non-pass row classified with evidence.

## Known debts (tracked, not urgent)
- Wall-clock budget counts verifier model latency against the task budget (consider separate metering).
- fix-git watch item: prominent logging when solver edits deliverable-adjacent test/entry files.
- Old-line surfaces (`harness/aether2`, `pro_workspace_aether_next`) remain as reference; do not build on them.

---

# Road v2 (2026-07-08) — post-sentinel, post-design-review

Basis: `FABLE5_ADVERSARIAL_AUDIT_20260708T165639Z.md` (incl. the dated Addendum adjudicating
the owner's three Phase-1 concerns). Sentinel evidence: 2/5 official passes, 3 verifier
false-cleans, all produced by the working tree itself (code_tree_hash `d559c7dc…` identity).
The measured bottleneck is verifier falsification discipline, not missing inspection mechanism.

Design decisions of record (full reasoning in the audit Addendum):
- D1: completion-evidence record is **content-blind protocol** — presence + non-emptiness +
  inspection_refs resolving to this round's real inspections. The harness NEVER evaluates
  reasoning content, never prescribes methods per evidence class, never coverage-maps
  against config items. Line: acts-that-happened + records-referencing-those-acts, nothing more.
- D2: architect is **primary** (owns what must be proven; doctrine fixed to spec-anchored,
  method-independent minimum evidence). Harness record is a **thin secondary backstop**
  making the architect's own contract undroppable. Prompt-only already failed 3/3 in the
  sentinel against good configs; ship both together.
- D3: video-processing false-clean **is the same self-confirmation class** (reference solution
  is deterministic cv2; frame numbers are machine-re-derivable; verifier perceived a
  solver-authored contact sheet instead of deriving independently via overlay). The
  "perception ceiling / accept the loss" carve-out is retracted; independence norm enters as
  uniform contract + architect doctrine (never harness-enforced classification).

## Phases (strike through as completed; record evidence refs)

- **P0 — commit the world honestly** (precondition for trusting anything downstream):
  governance docs (CLAUDE.md, AGENTS.md, docs/HARNESS_VISION.md, decision briefs,
  AETHER2_SLICE* record) → canonical package + tests + scripts (incl. proof-board test fix —
  it never ran; and un-flattening the 30,757-char single-line architect prompt,
  content-identity proven by hash) → sentinel evidence + ledger notes + audit report →
  `aether/` shim + pyproject → `harness/aether2` reference state. Suite green before each
  commit. RAW_LEDGER_UPDATE per material slice.
- **P1 — verification falsification slice** (one slice, two coupled parts + tests):
  (a) workbench architect doctrine: minimum_completion_evidence must be spec-anchored and
  method-independent; ban solver-anchored phrasing; independence norm for machine-re-derivable
  values; overlay-first when decisive artifacts exceed read spans.
  (b) verifier contract + runtime: `completion_evidence` record required on `completed`
  (schema advertised in VERIFIER_RUNTIME_CONTRACT; parse-layer normalization; content-blind
  model_hooks gate with retry-then-refuse, mirroring existing gates).
  (c) unit tests with stub hooks: record missing → retry → refuse; refs that don't resolve →
  rejected; valid record → accepted; known-good path unaffected.
  (d) context-window de-starvation (owner direction, 2026-07-08): the volatile context view
  is capped by a hidden harness default `model_context_window_tokens=8000` (runtime_ir.py:281,
  compression at 0.60 → ~4.8k tokens) that the workbench architect cannot override — measured
  solver steps ran on ~7k tokens total against 200k-class models. Expose the view budget as an
  architect-configurable workbench ContextPolicySpec field with a modern default (50k, ceiling
  not target); same hidden-constraint class P2i fixed for wall-clocks.
- **P2 — known-bad verifier eval (falsifiability gate for P1)**: verifier-only replay over
  frozen sentinel snapshots (kv wrong-field proto, gcode comment-vs-toolpath, video
  self-confirming frames) + log-summary known-good. Predictions recorded in the audit
  Addendum. Model-backed execution happens under the run protocol below. P1 is not "done"
  until this board runs; a P1 that cannot fail a known-bad is theater.
- **P3 — sentinel rerun + 10–20 task diverse board** at fixed committed SHA, benchmark-native
  budgets (task.toml, NOT max-steps 30 — that manufactured both run-A incompletes),
  `AETHER_VERIFIER_EVIDENCE_DIR` exported, provenance with real SHA. First honest capability %.
- **P4 — hygiene carve** (after boards, unless idle time): delete/archive root scrapheap
  (audit §C table), quarantine legacy ir-architect lineage to reference_legacy, remove
  grader_hints vestiges + dead branches, real size-cap decomposition (6 modules over),
  verdict-taxonomy reconciliation (advertise or cut — contract says 5, code accepts 14),
  then the `aether/` physical rename LAST.

## Run protocol (owner rule, 2026-07-08)
- All model runs are launched and monitored by **haiku subagents**; the principal agent stays
  idle while runs execute. VM is temporarily upsized for parallel runs and downsized after
  boards complete (record original SKU). Deallocate at handoff per AGENTS.md.

## Open blockers / owner inputs
- Model-identity contradiction: ledger notes say gpt-5.4-mini; run provenance records
  `AZURE_OPENAI_GPT54_PRO_DEPLOYMENT` for solver+architect. Owner must confirm the Azure
  deployment mapping; until then the sentinel model identity is unverified. Provenance should
  additionally record the resolved deployment name (small P1-adjacent fix).
