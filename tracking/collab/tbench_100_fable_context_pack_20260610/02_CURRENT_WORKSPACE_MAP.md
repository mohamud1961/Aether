# 02 — Current Workspace Map

Snapshot at HEAD `f9accef6a` (master, 2026-06-10). "Old path(s) mentioned"
captures paths referenced in docs/ledger that point elsewhere or no longer
exist. Status vocabulary: `current`, `historical`, `stale`, `duplicate`,
`unknown`, `external benchmark source`, `archived evidence`.

| Area | Current path | Old path(s) mentioned | Exists? | Status | Importance | Notes |
|---|---|---|---|---|---|---|
| Mission/governance | `AGENTS.md`, `README.md` | `/home/azureuser/mlpcp_v2_official_run` (VM-only, never local) | yes | current | high | AGENTS.md is the live constitution; "5.4 Pro ordered roadmap" cited as strategic source but not itself in repo |
| Runner — agent core | `runner/agent.py` | — | yes | current | high | Main agent loop, 75KB |
| Runner — kernel modules | `runner/kernel_*.py` (16 files: services, context_pack, receipts, interrupts, working_window, layer2_audit, tpm_pacer, recovery, success_contract, compaction, evidence_trail, gates, artifacts, native_tools, control_plane, state) | — | yes | current (active-not-board-ready per `runner/README.md`) | high | "model-led substrate v1" = layer2_audit + gates + recovery + context_pack + state, last touched 2026-06-05/06 |
| Runner — active evidence kernel | `runner/active_evidence_kernel.py` | — | yes | current/active-not-ready | high | Composes the kernel_*.py modules; never run against eval suite |
| Runner — evidence kernel (older) | `runner/evidence_kernel.py` | — | yes | unclear — likely historical predecessor of active_evidence_kernel | medium | compare with active version before reading both |
| Runner — route manifest | `runner/packet04_route_manifest.py` | — | yes | current | high | Used by `winning_harness_v1`; route-manifest plumbing |
| Runner — measurement contracts/grading | `runner/phase65_measurement_contracts.py`, `runner/phase65_measurement_grading.py` | `runner/phase15_measurement_repair.py` (historical) | yes | current | medium | per `runner/README.md` |
| Runner — benchmark adapters | `runner/benchmark_adapter_{bfcl,bfcl_native,contextbench,contextbench_native,letta,letta_native,terminalbench,terminalbench_native,acebench,contracts}.py` | — | yes | current | high | TB-native adapter is `benchmark_adapter_terminalbench_native.py` |
| Runner — packet07_*/successor_*/phase15 | `runner/packet07_*.py` (~18 files), `runner/successor_*.py` (~17 files), `runner/phase15_measurement_repair.py` | — | yes | historical (per `runner/README.md`) | low for new work, medium for decision-history mining | Source of "long-horizon artifact handoff 6/6 already solved" lineage |
| Runner — sandbox/docker | `runner/certified_sandbox.py`, `runner/certified_sandbox_backend_probe.py`, `runner/docker_sandbox.py` | — | yes | current | high | Core of the "is Docker available" problem (`06`) |
| Runner — eval substrate | `runner/eval_substrate_contracts.py`, `eval_substrate_execution.py`, `eval_substrate_scoreboard.py`, `eval_batch_runner.py`, `eval_runner_router.py` | — | yes | current | high | Generic eval-substrate plumbing referenced by AGENTS.md Goal 2 |
| Runner — MLPCP v2 stub | `runner/mlpcp_v2/` | — | only `__pycache__/` | **stale/orphaned** | low | Source `.py` purged; only bytecode remains — confirms MLPCP v2/v3 was removed without commit |
| MLPCP v3 variant context | `tracking/variants/mlpcp_v3/` | — | yes | current (paused) | high | Pulled from VM on 2026-06-11; contains runs, audits, patches, and pause state |
| Doc pointers (BROKEN) | `runner/README.md` references `../docs/current_surface_map.md`, `../docs/deprecation_map.md` | same | **NO** — `docs/` does not exist anywhere, including git history | **broken pointer** | high (process risk) | Anyone following runner/README.md hits a dead link; Fable should not search for these |
| Blocks (modular harness) | `blocks/{context,execution,orientation,recovery,tools,verification}/` | — | yes | current | high | `blocks/tools/raw_bash.py`, `blocks/execution/flat_loop.py` confirmed as the Terminus-equivalent baseline (inbox A4); `blocks/orientation/phase6_doctrine.py` used by `winning_harness_v1` |
| Blocks — result attribution guard | `blocks/tools/result_attribution_guard_common.py` (from `076ba7694`) | — | yes | current but unvalidated/risky | medium | "Combined Guard V1.5" — sentinel-regressed, hardcoded `lookup_customer_order` repair; do not re-promote as-is (`07`) |
| Custom eval suite (live registry) | `tracking/collab/final_harness_eval_suite/` (`final_suite_registry.yaml`, `task_packs/{hard,sentinel,composition}/`, `family_winner_registry.yaml`, `recipe_candidates.yaml`, `runs/2026052{8,9,30}T*` — 16 run dirs, `vm_pulled_runs/`, `adapter_fixtures/`, `fixtures/recipe_ingestion_governance/`) | — | yes | current | very high | The live eval registry; `family_winner_registry.yaml` winners list is empty — nothing promoted |
| Eval suite baseline/build/repair/tournament | `tracking/collab/eval_suite_v1_baseline/`, `eval_suite_v1_build/`, `eval_suite_v1_repair_runs/`, `eval_suite_v1_tournament_runs/` | — | yes | current/archived evidence | high | Source of family-level scoreboards cited in `06` (filesystem 0/6, service 0/3, etc.) |
| Tooling tournament (Combined Guard V1.5) | `tracking/collab/first_result_attribution_mechanism_tournament/`, `tracking/collab/tooling_tool_contract_certified_tournament_clean/` | — | yes (first one has content; `_clean` is mostly `.pyc`/`.DS_Store`) | first = archived evidence; `_clean` = stale/empty | medium | `comparison_summary.json` here shows the sentinel regression discussed in `07` |
| Winning harness v1 work | `tracking/collab/final_harness_eval_suite/reviews/winning_harness_synthesis_trace_analysis_2026-05-30.md`, `winning_harness_v1_goal_closeout_2026-05-30.md` | — | yes | current (HOLD) | very high | The 11-step build spec + closeout showing all 4 run surfaces INVALID due to local Docker |
| Model-led substrate v1 | `tracking/collab/model_led_substrate_v1/{workers/*.md, reviews/adversarial_review_01.md, reviews/accepted_findings_resolution.md}` | — | yes | current | very high | Most recent active work (2026-06-05/06); zero eval results yet |
| Local iteration loop 2026-04-06 | `tracking/collab/local_iteration_loop_2026-04-06/` | — | yes | historical | low | Predates the final_harness_eval_suite consolidation |
| Local iteration loop 2026-06-04 | `tracking/collab/local_iteration_loop_2026-06-04/{baseline_runs,full_board_rerun,next_bounded_vm_slice}/.../rows/{fhard_01..08,fsent_01..05}/grading_pack/.../*.pyc` | — | **directory structure exists, but only `__pycache__/*.pyc` remain — all result_rows.jsonl/scoreboard.json/answer.json deleted or gitignored** | **stale/evidence-stripped** | medium | Confirms a real local run happened against the `fhard_01-08`/`fsent_01-05` final-suite tasks on 2026-06-04, but no scored output survives in the repo — see `gap_report.md` |
| Autonomous loop (Goal 1, single-family winner discovery) | `tracking/collab/autonomous_loop/single_family_winner_discovery_gate/` (master copy near-empty) vs. `vm-pulled:tracking/collab/autonomous_loop/single_family_winner_discovery_gate/` (full content) | — | **master: stub only; vm-pulled: full** | **duplicate, divergent** | very high | Read via `git show vm-pulled:<path>` — `closeout.md` says `winner_found = 0` across 7 families (`04`, `06`) |
| Variant hypothesis backlog | referenced as `tracking/collab/variant_hypothesis_backlog.md` / `.yaml` | — | **NOT on master; exists on `f7730830b` / `vm-pulled` / `remotes/vm/push-master`** | **stale path on master / current on vm-pulled** | very high | Read via `git show vm-pulled:tracking/collab/variant_hypothesis_backlog.md` — see `04` |
| GPT-5.5 Pro synthesis context | `tracking/collab/gpt55pro_best_harness_synthesis/INPUT_CONTEXT_AND_PROMPT*.md` | — | unconfirmed on master (built per inbox 2026-05-30, large 1.5–3MB files) | unknown — likely vm-pulled only | low (too large to read; informational) | Do not read directly — multi-MB |
| Stage 02 deep synthesis | `tracking/collab/stage_02_synthesis/{mechanism_map,failure_taxonomy,eval_implications,variant_family_seeds,...}/` | — | yes (mechanism_map, failure_taxonomy populated; `eval_implications` and `variant_family_seeds/synthesis` largely NOT STARTED) | current but incomplete | high | Broken provenance: stage_03 cites `variant_family_seeds/synthesis/principal_synthesis.md` which does not exist |
| Stage 03 execution planning | `tracking/collab/stage_03_execution_planning/packets/{packet_04_first_atomic_variants,packet_06_paired_combo_variants}/` | — | yes | historical/partially current | medium | Predecessor planning to the eval-suite-driven work |
| Research — BigAI trace layer | `research/analysis/bigai_trace_layer/` | — | yes | external benchmark source / archived evidence | high | 314 BigAI TB2.0 runs, ~82% pass — strongest empirical reference |
| Research — Claude Code source | `research/sources/codebases/quarantine/claude-code_ts_release/` | — | yes | external benchmark source (quarantined leaked source) | medium | autoDream, Stop Hooks, ULTRAPLAN, KAIROS — relevant to continuous-session option (`03`, `10`) |
| Research ledger (canonical) | `tracking/ledger/{decisions.md,timeline.md,claims.md}` (symlinked from `research/ledger`) | — | yes | **stale** (last entry 2026-03-29) | high | 27 unprocessed raw handoffs in inbox postdate this |
| Research ledger inbox | `tracking/ledger/inbox/2026-05-30/` (19 files), `2026-06-05/` (2 files), `2026-06-06/` (1 file) | — | yes | current, unprocessed | very high | THE most current strategic record (`04`, `06`) |
| Official TB tasks | `official_tasks/{extract-moves-from-video,headless-terminal,install-windows-3.11,mailman}/` | — | yes | external benchmark source | medium | Local copies of official TB2.0 task fixtures referenced in family diagnostics |
| MLPCP v2 docs package | `mlpcp_v2_complete_variant_package_expanded_docs/runner/` | — | only `.DS_Store`, effectively empty | stale/orphaned | low | Doc shell for purged MLPCP v2 |
| p4r1 / p4r2 | `p4r1/`, `p4r2/` (root) | — | only `.DS_Store` | stale/empty | low | No content; safe to ignore |
| prompts/variants | `prompts/variants/` | — | only `.gitkeep` | stale/empty | low | No content despite the name suggesting variant prompts |
| Scripts — Azure VM lifecycle (MISSING) | referenced: `scripts/deallocate_harnesseng_vm.sh`, `scripts/configure_harnesseng_vm_autoshutdown.sh` | — | **NO — `scripts/` only has `build_harnesseng_runtime_bundle.sh`, `deploy_harnesseng_worker_runtime.sh`** | **missing** | high | AGENTS.md mandates these for Azure VM lifecycle; they don't exist — see `gap_report.md` |
| Tools — eval suite orchestrator | `tools/eval_suite_orchestrator/`, `tools/run_final_harness_eval_suite_baseline.py`, `tools/render_final_harness_scoreboard.py` | — | yes | current | high | `run_final_harness_eval_suite_baseline.py` hardcoded to `recipe_control` (per inbox A7) — route-manifest variants don't actually flow through |
| Tests | `tests/` (120 files) | — | yes | current | high | Includes `tests/test_kernel_layer2_audit.py`, `tests/test_model_led_substrates.py` (per `04`/`06`) |
| Branches | `master` (HEAD `f9accef6a`), `codex/recovery-command-path-serialization`, `codex/structured-evidence-trail`, `vm-pulled`, `remotes/vm/{master,push-master}`, `remotes/origin/master` | — | yes | `vm-pulled`/`push-master` contain content not on master (variant backlog, autonomous_loop full content) | very high | Use `git show <branch>:<path>` to read vm-pulled-only files without checking out |

## Practical guidance for Fable

- **Do not start by reading `runner/packet07_*` or `runner/successor_*`** —
  those are historical lineage useful for `04`'s decision history, not for
  understanding the current runner.
- **The single most load-bearing "current state" directories** are:
  `runner/kernel_*.py` + `runner/active_evidence_kernel.py` (code),
  `tracking/collab/final_harness_eval_suite/` (eval registry + runs),
  `tracking/collab/model_led_substrate_v1/` (latest work),
  `tracking/ledger/inbox/2026-0{5-30,6-05,6-06}/` (latest strategic record),
  and `vm-pulled:tracking/collab/variant_hypothesis_backlog.md` +
  `vm-pulled:tracking/collab/autonomous_loop/single_family_winner_discovery_gate/closeout.md`.
- Several directory names suggest content that **is not actually there**
  (`local_iteration_loop_2026-06-04`, `tooling_tool_contract_certified_tournament_clean`,
  `prompts/variants`, `p4r1`/`p4r2`, `mlpcp_v2_complete_variant_package_expanded_docs`,
  `runner/mlpcp_v2/`) — these are listed for completeness/gap-tracking only.
