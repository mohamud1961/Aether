# AETHER_NEXT_PROGRESS — Running Ledger

Lead: Fable 5 (autonomous session, started 2026-07-05).
Canonical root: `aether_next_build/aether_next/`. Branch: `codex/canonical-aether-consolidation` (never master).

## Goal

(1) Verify the codebase builds the intended design — generic, minimal, capable, elite — and correct drift.
(2) Finish remaining work and prove it, until failures are the model's, not the harness's.

North star, invariants, and Definition of Done are as stated in the mission brief (2026-07-05); not restated here.

## Phase list

- **Phase 0** — vision-fidelity gate (6 questions, KEEP/FIX/DELETE, invariant confirmation, regression sentinel) → **IN PROGRESS**
- **P1a** quarantine legacy modules; **P1b** delete solver reconfiguration; **P1c** cache-stable prompt prefix split
- **P2d** verifier overlay execution; **P2e** generic probes; **P2f** full-output capture; **P2g** verifier-triggered reconfig; **P2h** stalemate protocol; **P2i** per-task capability closure (~90 tasks)
- **Ext-j** Docker isolation + golden-grader smoke; **Ext-k** ONE model-backed sentinel batch, then STOP

## Session log

### 2026-07-05 — Session init
- **Baseline adoption:** user-provided `aether_next_build_local_vision_delta.zip` verified as strict superset of the repo working tree (repo `aether_next_build/` was entirely untracked; only repo-side extra file was `.DS_Store`). Zip contains newer versions of ~20 modules (head/tail output preservation, budget-bounded timeouts, lenient-but-fail-closed verifier JSON parse, task.toml metadata, advisory-only memory/no-progress) plus new `task_capability.py`, `test_local_vision_delta.py`, `test_goal_harness_execution.py`. Synced zip → working tree via rsync; post-sync diff = 0 files.
- **Baseline suite:** `python3.11 -m pytest tests -q` → **300 passed, 0 failed, 0 errors** (~25s). NOTE: system python3 is 3.9 and fails collection (`tomllib`); python3.11 required.
- **Environment:** Docker available (`docker info` OK). Official corpus at `official_tasks/` (~90 task dirs + tasks_index.json). Audit script at `scripts/audit_official_task_capabilities.py`; existing outputs `OFFICIAL_TASK_CAPABILITY_AUDIT_LOCAL.{csv,md}`.

## Phase 0 — Vision-fidelity gate (2026-07-05)

### Q1 — Genuine matches to the north star (evidence)

- **Verifier judges state, not story:** `build_verifier_packet` is state-only with a runtime assertion that solver-journey fields never leak (verifier_packets.py:344-427). Verifier has read-only inspection (read_file / rerun_check / artifact history / recent receipts) with executor access (verifier_inspector.py; kernel_verifier.py:190-223).
- **Completion authority:** canonical workbench completion requires a verifier `completed` verdict; solver submit alone never completes (kernel.py:333-343, 358-370 records `verifier_required_for_completion` when verdict missing). Active blocking findings require intervening evidence before re-verify (kernel.py:306-322, 394-421).
- **Fail-closed config:** workbench architect failure → `config_invalid`, no default config (kernel_config.py:229-242, `_invalid_runtime_ir` docstring 189-201). Verifier prompt missing → raise, no fallback prompt (model_hooks.py:329-334).
- **Solver-signal receipts:** parse error → raw(20k) capture + one retry + receipt (kernel.py:225-271); invalid turn → receipt (272-281); solver reconfigure request → neutralizing receipt, config untouched (372-384); report_blocker action exists (761-775).
- **No unprobed env facts:** network_scope defaults `unknown`, upgraded only by live probe (envmap_builder.py:315-321); capability needs marked `inferred_not_fact` (task_capability.py:26).
- **Evidence-bar classifier:** model_limit requires real-action diversity, no harness blocks, no disqualifying failure classes (classifier.py:207-229); grader reconciliation is post-run-record-only (classifier.py:232-283).
- **Provenance:** docker runner threads `run_provenance` into results (docker_runner.py:316,583).
- **Prefix/volatile split exists structurally:** `CompiledRuntime.stable_prefix_sections` + `prefix_messages()` (runtime_ir.py:439,467-471); volatile `[context_packet]` appended per step (kernel_messages.py:69-87). No stability test yet (P1c).
- **Advisory-only memory/no-progress:** completion gate explicitly does not block on them (completion.py:216-219); soft-block is advisory receipt only (kernel.py:474-489; test_memory_loop_fixes).

### Q2 — Appears-to-match only

- **Mount isolation** (solver container without /task,/tests; post-terminal docker cp): code present (docker_runner.py:489-501) but **not Docker-proven** → Ext-j.
- **repair_config on the workbench path** (kernel_config.py:271-283): recorded via receipt + repair_codes, so not silent, but an architect defect is absorbed into a continuing run without an `architect_defect` mark in result rows → fold into P2g.
- **`stdout_full`/`stderr_full` + handles** (kernel.py:823-830) claim losslessness, but the substrate caps output at 20k **before** the kernel sees it (real_executor.py:21-22,150-151), and on timeout partial output is dropped entirely (152-158) → P2f is real work, currently a truthfulness violation of "full output retrievable by handle".

### Q3 — Benchifying sweep (verified by hand against Haiku inventory)

- **proof_contract.py (273 LOC): CONFIRMED task-family semantic analyzers** — `_openssl_cert_findings` (openssl+cert+key shape, lines 193-216), SPARQL/Turtle semantic checks (84-111). **Orphaned**: zero imports from any aether_next module; referenced only by tests (test_runtime_enforcement.py, test_vnext_memory_context_verifier.py) and as a forbidden-string in verifier_packets. → P1a quarantine + delete blessing tests.
- **no_progress.py:16**: `_PATH_RE` extension whitelist includes `.sparql|.ttl` — benchmark residue in a certified-path regex. → fixed this slice (generic extension pattern).
- **Legacy architect modes** (`ir`, `contract`): live code in kernel_config.py (_baseline_resolve/_contract_resolve), contract_compile.py, contract_hooks.py, task_contract.py; flag-gated off certified runs (run_adapter.ensure_certified_architect_mode) but physically co-resident and imported at module top by kernel_config. Auto-submit exists only on non-workbench path (kernel.py:284-299). → P1a physical quarantine.
- **envmap_builder / task_capability keyword tables** (openssl, qemu, sparql, stan, cobol...): generic tool/language/extension vocabulary used as capability classes, marked inferred; no task-name branching; architect can override. KEEP (watch item).
- **docker_runner `run_tbench_task`**: benchmark-format adapter (task.toml, /task layout, grader invocation) at the runner boundary, not model-visible. KEEP.
- **Zero task-name conditionals** in aether_next/ certified path (verified: no `task_name ==`-style branching; startswith uses are path validation).

### Q4 — Minimality sweep

- **Dead cluster in verifier_packets.py**: `_solver_authored_evidence`, `_recent_actions`, `_latest_command_results`, `_latest_file_reads`, `_failed_or_empty_checks`, `_memory_loop_feedback`, `_automatic_memory_findings`, `_artifact_evidence`, `_changes_since_active_findings` — unreachable (only call each other). → deleted this slice.
- **model_hooks.py:333**: dead assignment before raise. → deleted this slice.
- **Orphaned modules**: proof_contract.py (0 prod importers), alignment_board.py (tests only), architect_quality.py (tests only). → P1a quarantine.
- **Module-size violations** (>500 LOC): kernel.py 889, context_compiler.py 858, docker_runner.py 796, model_hooks.py 667, compiler.py 663, runtime_ir.py 544. P1a/P1b shrink kernel; remaining decomposition tracked as standards debt in P1.

### Q5 — Generic sweep

EnvMap and tooling are capability-class shaped (task_capability.CapabilityNeed; capability registry; tool hints as generic names). No task shape special-cased in certified path. Keyword tables are tool-vocabulary, not task IDs (watch item, acceptable).

### Q6 — Capability gaps (what stops true behavioral judgment / lossless context)

1. Executor 20k output cap + timeout output destruction (P2f).
2. Verifier cannot execute the deliverable against its own fixtures in an isolated overlay — only rerun declared checks (P2d).
3. No generic service/port/media probes for the verifier beyond process probe via solver receipts (P2e).
4. Verifier inspection `read_file` returns only a 4k excerpt (verifier_inspector.py:130-131) — fine for text, but no paging for large artifacts (fold into P2e).
5. No verifier-triggered reconfiguration path (P2g) and no stalemate bound (P2h).

### KEEP / FIX / DELETE

| Verdict | Item |
|---|---|
| KEEP | workbench architect path, verifier packet + inspector, completion gate (verifier-gated), classifier evidence bar, report_blocker, paging handles, envmap probe discipline, task_capability vocab, docker runner adapter |
| FIX | executor output truthfulness (P2f); prompt-cache stability test (P1c); repair_codes → architect_defect surfacing (P2g); no_progress regex (this slice); verifier read_file paging (P2e); module size cap debt |
| DELETE/QUARANTINE | proof_contract.py + blessing tests; contract/ir architect paths (contract_compile, contract_hooks, task_contract, _baseline_resolve/_contract_resolve, auto-submit branch, hooks.reconfigure legacy path); solver `request_reconfigure` turn kind (P1b); dead verifier_packets cluster (this slice); model_hooks dead line (this slice); alignment_board + architect_quality (quarantine) |

### Invariants — one line each

1. No silent fallback — HOLDS on workbench path (fail-closed config, fail-closed verifier prompt); repair_config recorded, defect-surfacing deferred to P2g.
2. No silent loss of solver signal — HOLDS (receipts for parse/validation/reconfigure/blocker).
3. No information destruction — **VIOLATED at substrate** (executor 20k cap; timeout drops output) → P2f.
4. No grader/test leakage into solver phase — HOLDS in code (packet assertion; container isolation code) — Docker proof pending (Ext-j).
5. No solver self-report authority — HOLDS (verifier-gated completion).
6. No task-specific semantic judgment — HOLDS after this slice quarantines are done; violations were orphaned proof_contract + no_progress regex residue.
7. Explicit provenance — HOLDS (run_provenance in run records); SHA stamping enforced at Ext-k.
8. Every non-pass row classified with evidence — HOLDS (classifier + reconcile_grader_alignment).
9. Substrate vs model failures separated — HOLDS (classifier labels).
10. Verifier judges state not story — HOLDS (state-only packet + inspection).
11. No unprobed env facts — HOLDS (network unknown-until-probed; inferred_not_fact).
12. Cache-stable prefix — structurally present; test added in P1c.

### Regression sentinel

Added `tests/test_wording_sentinel.py`: a correct-but-differently-worded solution (summaries/artifact text containing scary words like "failed"/"error" in benign context) must not trip FailureParser on successful commands, must not trip automatic-memory/no-progress blocks, and CompletionGate must stay state-based.

## P1a — Physical legacy quarantine (2026-07-05) — DONE

- Created top-level `reference_legacy/` package; moved `proof_contract.py`, `contract_compile.py`, `contract_hooks.py`, `task_contract.py` (absolute `aether_next.*` imports — reference may depend on certified, never the reverse). Moved `run_stage1_replay_acceptance.py` (legacy-analyzer replay harness) there too.
- Certified surgery: kernel_config lost `_contract_resolve`/contract imports/`contract` field; kernel lost `contract_architect` param, "contract" realization branch, and the **auto-submit branch** (+ dead `cheap_checks_all_passed`); run_adapter and docker_runner are workbench-only (`ensure_certified_architect_mode` fail-closes ir/contract with no bypass flag; `architect_overrides_for_mode` replaced by `workbench_architect_for`); `reference_architect_mode` result field removed everywhere (run_pilot included).
- Correction to Phase 0 notes: `alignment_board.py` is NOT orphaned (used by `run_alignment_board.py` post-run audit); kept. `architect_quality.py` kept (offline architect-eval scorer used by run_architect_only_eval.py; not in the run loop).
- Tests: deleted blessing tests (`test_auto_submit.py`, `test_contract.py`, proof-contract analyzer tests in test_runtime_enforcement, contract-resolve tests in test_kernel_config/test_kernel, `test_stage1_replay_acceptance.py`); rewrote test_live_checks obligation test onto the baseline envmap-hints path; added `tests/test_legacy_quarantine.py` (5 falsifiable exclusion gates: no static import, no module files, subprocess-clean transitive import, adapter rejects legacy modes, reference stays importable).
- Suite: **279 passed, 0 failed**. Note: kernel.py now 838 LOC (auto-submit removal) — still >500, shrink continues in P1b.
- Watch item: `EnvMap.grader_hints` is a model-visible field name fed to the architect (kernel_messages.py:37); populated from public task surfaces (analysis.py builds checks from it). Verify at P2i/Ext-j that nothing grader-derived ever lands there in the docker runner path.

## P1b — Solver-requested reconfiguration deleted (2026-07-05) — DONE

- `request_reconfigure` removed from SolverTurn kinds + `reconfigure_reason` field deleted (runtime_ir); a solver emitting it now gets a visible `turn_validation` receipt ("unknown turn kind"), no silent loss.
- `KernelHooks.reconfigure` protocol method, `ModelHooks.reconfigure`, `RECONFIGURE_SYSTEM_PROMPT`, `reconfigure_model` plumbing: deleted.
- Legacy mid-run reconfigure loop (`_do_reconfigure` + completion-gate `recommend_reconfigure` consumption) and unreachable `_do_reconfigure_workbench`: deleted. `CompletionDecision.recommend_reconfigure` and monitors' flags retained — P2g (verifier-triggered single-shot reconfigure) will consume them via the workbench resolve path (`resolve_runtime(..., reconfigure_context=...)` kept).
- report_blocker routing: verifier packet now carries `solver_reported_blockers` (authority `escalation_request_only`, bounded excerpts) — the solver's only config signal, routed to the verifier as designed. Positive test added.
- kernel.py 889 → 730 LOC (still >500; P1c/P2 continue the shrink).
- Suite: **279 passed**.

## P1c — Prompt-cache stability (2026-07-05) — DONE

- Verified the split already exists structurally and carries the required content: stable prefix = protocol card (`kernel_contract`, `tool_semantics`, `solver_turn_contract`), architect solver prompt (`solver_identity`), tool schema (`action_schema`, `selected_capabilities`), task/world facts (`task_prompt`, `envmap`, file tree, `objective_graph`, `eval_index`, `environment_probe`) — compiler.py:532-617; volatile part is the single trailing `[context_packet]` message (kernel_messages.py:69-87) serialized with sorted keys.
- Added `tests/test_prompt_cache_stability.py` (3 tests): byte-identical prefix across all steps of a 4-step mutating run with exactly one trailing volatile message (with a self-guard that the packet actually varies), required-section presence, deterministic packet serialization.
- Suite: **282 passed**. P1 complete.

## P2f — Truthful full-output capture (2026-07-05) — DONE

- Substrate fix in both executors (SubprocessExecutor + DockerExecExecutor): the old silent 20k truncation is gone. Streams ≤1MB are kept verbatim inline; beyond 1MB the COMPLETE stream is spooled to disk (`StreamSpooler`, tempdir per executor) and the inline text is a clearly marked head+tail naming the spool path. `CommandResult` gains `stdout/stderr_overflow_path`, `stdout/stderr_bytes_total`, `timed_out`.
- Timeout no longer destroys output: partial stdout/stderr from `TimeoutExpired` is preserved with an explicit `[harness] ... partial output above is preserved` marker; exit 124 + `timed_out=True`.
- Kernel `read_output`/`grep_output` transparently page/grep over the spool file when present; receipts carry overflow paths and true byte totals.
- **Invariant repair found during testing:** `read_output`/`grep_output`/`read_file_page` were NOT in `ALWAYS_AVAILABLE_ACTION_KINDS` — a config that didn't grant them made handles unretrievable. Now always available (runtime_ir.py:68) with a comment pinning the invariant.
- Tests: `tests/test_truthful_output_capture.py` (4): 100k verbatim (old cap would destroy), >1MB spool completeness + marked inline, timeout partial preservation, kernel page+grep across spooled stream by handle.
- Suite: **286 passed**. Invariant 3 (no information destruction) now HOLDS at the substrate.

## P2d — Sandboxed verifier overlay execution (2026-07-05) — DONE

- New `aether_next/verifier_overlay.py` (~130 LOC): `VerifierOverlay` creates a copy of the solver workspace **through the same executor substrate** (`cp -a` via executor.run_command — works identically for host bash and `docker exec`, so overlay runs see the solver's real toolchain). Lazily created, sibling-of-workspace path (outside solver-visible tree and mtime snapshots), unconditional idempotent `teardown()` (rm -rf).
- Verifier inspection now supports: `overlay_run_command` (bounded execution in overlay cwd), `overlay_write_fixture` (verifier-authored fixture, base64-written INTO OVERLAY ONLY, path-escape rejected), and `rerun_check` now **routes through the overlay** — verifier check execution can never mutate solver state (no-overlay fallback is an explicit error, never a workspace run).
- `kernel_verifier._call_verify` builds the overlay per verification round and tears it down in `finally` (rollback pass or fail), recording a `model_verifier_overlay_teardown` receipt.
- Verifier guidance updated: fixtures + overlay semantics documented; "test the deliverable against YOUR OWN inputs".
- Tests: `tests/test_verifier_overlay.py` (5): overlay mutations invisible to workspace, fixture+run with teardown removing everything, fixture path-escape rejection, rerun_check overlay routing with side-effect containment, no-overlay explicit error.
- Suite: **291 passed**.

## P2e — Generic service/port/process + media/artifact verifier probes (2026-07-05) — DONE

- New `aether_next/verifier_probes.py` (~170 LOC), pure capability classes: `probe_port` (TCP connect via python3 socket through the executor substrate), `probe_http` (GET status+body head), `probe_process` (pgrep with bracket-first-char regex so the probe never matches itself; ps fallback; `tool_missing` reported honestly), `inspect_artifact_probe` (file type, size, sha256, plus type-appropriate metadata: ffprobe for a/v, pdftotext head for PDFs, identify for images, content head for text — missing tools reported as `tool_missing`, never silently skipped).
- All probes run through the executor substrate (container-aware for docker runs), take typed quoted fields (no command injection), observe LIVE state read-only.
- New inspection kinds dispatched in verifier_inspector (`probe_port|probe_http|probe_process|inspect_artifact`) with `target` field; verifier `read_file` inspection now supports `offset` paging (closes Phase 0 Q6 item 4).
- Verifier guidance: "for service tasks, judge live state with probes rather than the solver's captured output."
- Tests: `tests/test_verifier_probes.py` (6): open/closed/invalid port, live+dead HTTP server, live process + absent process, PNG/text/missing artifact, inspector dispatch with no-mutation assertion, read_file offset paging.
- Suite: **297 passed**.

## P2g — Verifier-triggered single-shot reconfiguration (2026-07-05) — DONE

- A verifier `blocked_by_harness_config` verdict (workbench mode only) triggers at most ONE mid-run reconfiguration, re-invoking the real workbench architect via `resolve_runtime(..., reconfigure_context=...)` with the full verifier verdict + failure clusters + open obligations as evidence. A second blocked verdict yields a `verifier_reconfigure_exhausted` receipt, never a second reconfigure.
- **architect_defect is a first-class result field**: `KernelResult.architect_defect` + `architect_defect_reasons`, true when the initial config needed `repair_config` fixes (reasons `initial_config_repaired:<code>`) or when a verifier-triggered reconfigure fired — even when the task then passes. Threaded into run_adapter and docker_runner records (closes the Phase 0 Q2 repair-surfacing item).
- Bug found & fixed while testing: the verifier-skip gate (`active findings require intervening evidence`) compared step numbers, so a same-step reconfigure receipt didn't count and the verifier starved on its own config finding. Now position-based over the ledger; `verifier_triggered_reconfigure` counts as intervening evidence so the verifier re-judges the new workbench.
- Tests: `tests/test_verifier_triggered_reconfigure.py` (3): blocked→reconfigure→completed with architect_defect=True and evidence-bearing reconfigure_context; second blocked verdict exhausted; clean run has no defect.
- Suite: **300 passed**.

## P2h — Bounded verifier-disagreement / stalemate protocol (2026-07-05) — DONE

- `AetherNextKernel.STALEMATE_ROUNDS = 3`: when the identical non-empty active-finding set survives 3 consecutive verification rounds (each round only happens after intervening solver evidence, per the existing skip-gate), the run terminates with new status **`verifier_stalemate`** and a `verifier_stalemate` receipt carrying the full disagreement record (finding ids, per-round history, final verdict, active findings). The harness records the disagreement; it never adjudicates it. Changing finding sets = progress, no stalemate.
- Classifier: `verifier_stalemate` → `verification_failure` (high confidence, receipt evidence) — never `model_limit`.
- Fixed a double trace-step recording in the stalemate return path (caught by the tracing suite).
- Tests: `tests/test_verifier_stalemate.py` (3): identical findings terminate at exactly 3 verifier calls with full record; changing findings never stalemate; classification is verification_failure.
- Suite: **303 passed**.
- Standards debt noted: kernel.py at 923 LOC — decomposition slice next, before P2i.

## Kernel decomposition slice (2026-07-05) — DONE

- kernel.py 923 → **493 LOC**: extracted `kernel_dispatch.py` (action dispatch + `_head_tail` + `_action_timeout_s`, 288 LOC) and `kernel_turns.py` (act/submit turn execution + automatic-memory advisory reason, 174 LOC); dead imports pruned.
- Suite: **303 passed**.
- **Remaining size-cap debt (baseline modules, pre-existing):** context_compiler.py 858, docker_runner.py 794, compiler.py 663, model_hooks.py 637, runtime_ir.py 547. Decomposition deferred behind the mission-critical path (P2i → Ext-j → Ext-k); tracked here so it is not silently dropped.

## P2i — Per-task capability closure (2026-07-05) — DONE

- **Two generic gaps found and closed while building the support matrix:**
  1. Runner wall clock was a fixed 1800s regardless of the task's declared budget (bn-fit-modify declares 3600s → would be killed by a hidden harness constraint). `docker_runner._effective_run_timeout_s`: task `agent.timeout_sec` raises the runner floor up to a 14400s cap; policy recorded in the run record. 3 tests.
  2. Verifier overlay commands were capped at a fixed 300s while tasks declare verifier budgets up to 3600s. `VerifierOverlay(max_command_timeout_s=...)` now bound by task `verifier_timeout_sec` (`kernel_verifier._verifier_command_budget_s`, cap 7200s).
- **Audit script upgraded into a reusable per-class closure artifact:** `HARNESS_SUPPORT` matrix maps every capability class → status + the exact generic solver+verifier mechanism (module refs); per-task CSV gains `capability_support` (class=status per class); readiness = worst class status.
- **Re-run over all 90 tasks. Before → after readiness buckets:**
  - before: `needs_long_command_budget_and_verifier_execution` 59, `needs_p2_verifier_or_service_support` 31
  - after: `supported` 63, `supported_with_environment_gate` 27, **unsupported 0**
  - The environment gate is exclusively `network_download`: generic path exists (bootstrap_acquire + probed network_scope); offline environments are a probed environment fact reported honestly, never a silent harness failure. No capability class lacks a generic path; no BLOCKED entries required.
- **Verification against raw tasks (not script trust):** all 90 rows reviewed for class sanity (0 tasks unclassified; over-inclusion accepted as coverage-safe); deep spot-checks of headless-terminal (solver-authored pty via run_command — deliberate: no bespoke TTY channel, scripting via expect/pexpect is the generic path), install-windows-3.11 (qemu_vm/VNC/nginx → port/process probes + screendump artifacts), sparql-university, mailman, code-from-image. Existing test proves the audit never reads solution/ or tests/ (test_local_vision_delta).
- Suite: **306 passed**. P2 complete.

## Ext-j — Docker isolation + golden-grader smoke (2026-07-05) — DONE

- Latest evidence: `DOCKER_ISOLATION_SMOKE_20260705T032020Z.json`.
- Golden file case: official grader pass, internal completion completed, verifier alignment aligned.
- Golden service case: official grader pass, internal completion completed, verifier alignment aligned; exercises stable process launch + service readiness in Docker.
- Known-bad file case: official grader fail while internal verifier completed; recorded as `verifier_false_clean` rather than a pass. This is the intended alignment artifact: the grader remains external and the result row exposes verifier disagreement instead of hiding it.
- Earlier smoke attempts are retained as evidence of failure progression: `DOCKER_ISOLATION_SMOKE_20260705T031739Z.json` (grader errors) and `DOCKER_ISOLATION_SMOKE_20260705T031827Z.json` (service smoke still failing).

## Deterministic gate closeout (2026-07-05)

- Stable-core tool surface includes every generic workbench capability (`read_file`, `write_file`, `run_command`, `launch_process`, `probe_service`, `stop_process`, `inspect_artifact`, `bootstrap_acquire`, `query_memory`, `run_check`, `inspect_checks`); evidence in `tests/test_vnext_configurability.py`.
- Process probing now preserves truth under host policy denial: when `pgrep`/`ps` cannot enumerate processes, `probe_process` returns `state=unknown` and `tool_unavailable`, not a false `running=false` claim.
- Docker runner tests now mount workspaces under `/tmp`, a Docker-shareable path on local Docker Desktop; the previous `/var/folders/...` tempdir could fail before harness code executed.
- Focused tests:
  - `python3.11 -m pytest tests/test_verifier_probes.py -q` → **7 passed**
  - `python3.11 -m pytest tests/test_vnext_configurability.py tests/test_verifier_probes.py -q` → **34 passed**
  - `python3.11 -m pytest tests/test_docker_runner.py -q` → **12 passed**
- Full deterministic suite: `python3.11 -m pytest tests -q` → **308 passed**.

## BLOCKED

(none)

## Next step

Ext-k: ONE model-backed sentinel batch managed with 5.4 mini, preceded by focused architect/solver/verifier component evals and followed by non-pass classification.

## Ext-k component gates + one real run (2026-07-05) — PARTIAL

- Architect-only 5.4-mini eval across 10 varied official tasks: `architect_only_eval_20260705_goal_10_mini/ARCHITECT_EVAL_REPORT.md`.
  - 8/10 rows scored 10.0/10.
  - `headless-terminal` scored 9.67/10.
  - `fix-git` scored 9.0/10.
  - All configs were valid; no repair warnings or rejected config fields.
  - Every solver prompt included self-verification; every config used `model_verifier_policy.runs_on=["solver_submit"]`.
- Verifier-only model eval found and drove fixes:
  - Initial packet-style verifier eval exposed parse/protocol drift and lack of inspection-loop realism.
  - Production-style verifier-only eval after fixes: `verifier_only_eval_20260705_goal_mini_structured_missing_v1` → 6/6 parse-ok, evidence-bound, actionable `needs_repair` rows.
- Real run: `local_goal_runs/20260705T041231Z_one_real_logsummary`.
  - Task `log-summary-date-ranges`, 5.4 mini, Docker-backed official grader.
  - Result: reward 0.0, status incomplete, final verifier verdict `blocked_by_tooling`, 80 steps.
  - Official grader failed on semantic counts (`today,ERROR` expected 370, got 414).
  - Trace showed one real solver action at step 0, then repeated submit-only turns through step 79.
  - Root cause: verifier structured missing-evidence requests were not realized, glob/raw-state inspection was too weak, and active verifier findings did not stop submit-only looping.
  - Full audit: `ONE_REAL_RUN_AUDIT_20260705.md`.
- Fixes applied after the run:
  - `uncertain_missing_evidence` with structured evidence requests now triggers read-only verifier inspection rounds.
  - verifier JSON/protocol repair retry added for prose drift.
  - verifier output token budget now configurable via `AETHER_VERIFIER_MAX_OUTPUT_TOKENS`.
  - inspection request parser accepts first JSON object from mixed output.
  - `run_check` aliases to `rerun_check`.
  - globbed `read_file` verifier inspection returns bounded matched-file excerpts.
  - repeated submit-only turns under active verifier findings now terminate as `solver_submit_stalemate` after three skipped verifier rounds without intervening evidence.
- Tests after fixes:
  - `python3.11 -m pytest tests/test_verifier_probes.py -q` → **10 passed**.
  - `python3.11 -m pytest tests/test_model_hooks.py tests/test_verifier_probes.py -q` → **31 passed**.
  - `python3.11 -m pytest tests -q` → **311 passed**.

## Post-audit quality slice (2026-07-05, Fable session 2) — DONE

- Committed the codex working tree in two verified slices (Ext-j smoke + stable-core fix `666b09a1`; verifier realization + submit-stalemate `e7b5d17b`).
- Anti-self-confirmation slice (`7b36aba8`):
  - Architect prompt now mandates independent-verification discipline: raw-input inspection before choosing semantics, verification via a genuinely different method, manual raw-sample spot-audit, explicit self-confirmation trap; verifier rules name the same-method trap.
  - Visible smoke checks compile runnable but `authoritative=False`, labeled "shape-only, not semantic proof"; compiler plan membership decoupled from evidential authority.
  - `solver_submit_stalemate` reclassified: `model_limit` when verifier feedback was delivered on a clean workbench, `harness_context_failure` otherwise — never `verification_failure` (the verifier did its job).
  - Verifier feedback legibility confirmed: blocking-first active findings with repair_instruction are an always-include solver context section.
- Decomposition (`6018397c`): context_compiler 858→366 (context_views, context_recipe_apply), kernel 535→473 (kernel_reconfigure), model_hooks 712→601 (model_prompts); run_pilot CLI certified-only. Remaining size debt: docker_runner 820, compiler 666, model_hooks 601, runtime_ir 547.
- Suite: **315 passed**.

## Approved rerun (2026-07-05, in progress)

- Batch: `log-summary-date-ranges` (A/B against the failed run) + `openssl-selfsigned-cert` (known-pass sentinel), 5.4-mini, max_steps=40, SHA-stamped at the committed HEAD.
- **log-summary-date-ranges: completed, reward=1.0, 3 steps, classifier=none, architect_defect=False** (was: reward=0.0, incomplete, 80 steps). The structured-evidence realization + anti-self-confirmation + submit-stalemate fixes converted the exact prior failure into a clean, efficient pass.
- **openssl-selfsigned-cert: reward=1.0 (official grader: PASS), internal status `solver_submit_stalemate` at step 23, classifier `harness_context_failure`, alignment `verifier_completion_miss`.**
  - Interpretation (trace-audited): all 19 rounds of visible shape checks passed; the verifier ran 16 rounds + 42 read-only inspections and refused `completed` for ONE unprovable fact — `/app/ssl/server.key` mode 600. Its inspection surface had file contents/sha256/size/type but **no permission metadata**; it honestly escalated `blocked_by_tooling` ("Provide a read-only metadata receipt ... showing mode 600"). The solver, having genuinely finished, had nothing to repair; the submit-stalemate bound then terminated the run at step 23 instead of burning the remaining budget. The classifier correctly refused to blame the model.
  - This is the system working as designed on every layer except one missing generic capability. **Fix committed:** `inspect_artifact` probe now returns `mode`/`owner`/`mtime_epoch` (GNU+BSD stat), verifier guidance names the surface, regression test with a chmod-600 key file.
  - Launch note: `AETHER_VERIFIER_EVIDENCE_DIR` was not exported for this batch, so per-round verifier bundles were not persisted (findings recovered from the trace); export it for the next run.

## Ext-k verdict

The measured batch is interpreted; per the one-batch constraint, no further model runs launched this session. The next approved run should confirm openssl completes internally with the metadata probe (log-summary already passes clean: reward 1.0, 3 steps, no defect).
