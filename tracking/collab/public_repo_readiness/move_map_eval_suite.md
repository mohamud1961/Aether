# Eval Suite Public Move Map

Generated: 2026-06-16  
Scope: Discovery-only. No files were moved, edited, or deleted.

---

## 1. Executive Summary

### Where the real eval material actually lives

The real, executable eval artifacts are split across **three locations**:

1. **`runner/`** — the grader and adapter code that drives all evals lives entirely in `runner/`. The key files are `eval_adapter_tool_call_composite.py`, `eval_adapter_tool_call_atom.py`, `eval_adapter_terminal_workflow.py`, `eval_adapter_retrieval_context.py`, `eval_adapter_filesystem_agent.py`, `tool_call_composite_assets.py`, `filesystem_agent_context_bench.py`, `terminal_workflow_paths.py`, `packet03_eval_graders.py`, `packet03_eval_fixtures.py`, `phase65_measurement_contracts.py`, `phase65_measurement_grading.py`, `eval_substrate_contracts.py`, `eval_substrate_execution.py`, `eval_substrate_scoreboard.py`, `certified_sandbox.py`, `final_harness_eval_suite_adapter.py`, and `schemas.py`. These are REAL, substantive Python files (50–1330 lines each) that form the complete grading runtime.

2. **`tracking/collab/final_harness_eval_suite/`** — the authoritative private task-pack tree. All 13 task packs (8 hard + 5 sentinel/composition rows) exist here **with their full `reviewer_pack/hidden_verifier.py` + `reviewer_pack/hidden_truth.json`**. The solver-visible side (`solver_pack/`, `grader/grade.py`, `task_pack.yaml`, `fixture_manifest.json`) from this location is already mirrored verbatim into `eval_suite/pressure_family_families/task_packs/` and `eval_suite/harness_core/final_harness_v1/task_packs/`. The adapter fixtures (tool-call composite samples JSON, retrieval-context suite Verified.csv, filesystem-agent suite dataset) also live here as fallbacks.

3. **`eval_suite/`** — the current public skeleton. It contains a mix of REAL artifacts and thin stubs (see section below).

### What is REAL vs STUB in the current `eval_suite/`

**REAL (substantive, can be published as-is or with minor stripping):**
- `eval_suite/custom/families/*/grader.py` — 63–116 line deterministic graders, fully functional Python
- `eval_suite/custom/families/*/task_pack.json` — complete task pack definitions (39–63 lines)
- `eval_suite/custom/families/*/fixture/` — fixture workspaces with reference and candidate directories
- `eval_suite/custom/*/` (flat copies) — exact duplicates of the above; represent a redundant copy from an earlier pass
- `eval_suite/pressure_family_families/task_packs/` — all 13 task packs with real grader code, visible prompts, solver workspace fixtures, and task_pack.yaml; the grader stubs for fhard_01–05 (28 lines each) call `reviewer_pack/hidden_verifier` which is intentionally absent from the public tree
- `eval_suite/harness_core/final_harness_v1/` — real YAML registries (86–233 lines) that are verbatim copies of `tracking/collab/final_harness_eval_suite/*.yaml`
- `eval_suite/boards/` — 9 real JSON board files with actual routing and family references (10–55 lines each)
- `eval_suite/scoreboards/` — 8 example scoreboard JSON files
- `eval_suite/attempts/final_harness_v1/` — 2 real run timestamp dirs with real `result_rows.jsonl`, `scoreboard.json`, `run_summary.json`; the `result_rows.jsonl` contain host paths (`/home/azureuser/...`) that need scrubbing before publication

**STUBS (thin placeholder — README or empty content only):**
- `eval_suite/adapters/README.md` — 8-line placeholder only
- `eval_suite/graders/README.md` — 8-line placeholder only
- `eval_suite/fixtures/README.md` — placeholder only
- `eval_suite/sentinels/README.md` — 7-line placeholder only
- `eval_suite/whole_harness/README.md` — 16-line summary only (no executable content)
- `eval_suite/schemas/public_eval_map_contract.md` — documentation prose only (no JSON Schema)
- `eval_suite/schemas/README.md` — 1-paragraph placeholder
- `evals/context_eval.py`, `evals/step_efficiency_eval.py`, `evals/verification_eval.py` — 7-line docstring-only stubs, no code body

---

## 2. Move-Map Table

Notes on columns:
- **import-risk**: whether moving/copying this file could break `runner.aether2.*` imports or any test import chain
- The `runner/` adapter files import from `runner.*` modules only (no `aether2`), so adapter moves carry import risk if moved outside `runner/`

| real artifact | current path | proposed destination | public/private | eval name to strip (orig → neutral) | import-risk (Y/N + why) | replaces which placeholder | notes |
|---|---|---|---|---|---|---|---|
| **Custom grader: public_manifest_repair_smoke** | `eval_suite/custom/families/public_manifest_repair_smoke/grader.py` | `eval_suite/custom/public_manifest_repair_smoke/grader.py` (already exists as identical copy) | PUBLIC | none | N | `eval_suite/graders/README.md` (partial) | Exact duplicate already at flat `custom/public_manifest_repair_smoke/grader.py`. Flatten — pick one home. |
| **Custom grader: mcp_registry_contract_smoke** | `eval_suite/custom/families/mcp_registry_contract_smoke/grader.py` | `eval_suite/custom/mcp_registry_contract_smoke/grader.py` (already exists as identical copy) | PUBLIC | none | N | placeholder | Duplicate; pick one canonical location. |
| **Custom grader: runtime_policy_hook_smoke** | `eval_suite/custom/families/runtime_policy_hook_smoke/grader.py` | `eval_suite/custom/runtime_policy_hook_smoke/grader.py` | PUBLIC | none | N | placeholder | Duplicate. |
| **Custom grader: skill_loader_contract_smoke** | `eval_suite/custom/families/skill_loader_contract_smoke/grader.py` | `eval_suite/custom/skill_loader_contract_smoke/grader.py` | PUBLIC | none | N | placeholder | Duplicate. |
| **Custom grader: subagent_handoff_contract_smoke** | `eval_suite/custom/families/subagent_handoff_contract_smoke/grader.py` | `eval_suite/custom/subagent_handoff_contract_smoke/grader.py` | PUBLIC | none | N | placeholder | Duplicate. |
| **Custom task packs (6 families)** | `eval_suite/custom/families/*/task_pack.json` | `eval_suite/custom/<family>/task_pack.json` (already at flat `eval_suite/custom/*/task_pack.json`) | PUBLIC | none | N | placeholder | All duplicated. Canonical home should be `eval_suite/custom/<family>/`. |
| **Custom fixtures (5 families)** | `eval_suite/custom/families/*/fixture/` | `eval_suite/custom/<family>/fixture/` (already at `eval_suite/custom/*/fixture/`) | PUBLIC | none | N | `eval_suite/fixtures/README.md` | Real fixture workspaces. Already in flat form. |
| **Eval adapter: tool-call composite** | `runner/eval_adapter_tool_call_composite.py` | `eval_suite/adapters/eval_adapter_tool_call_composite.py` | PUBLIC | tool_call_composite → tool_call_composite | Y — imports `runner.tool_call_composite_assets`, `runner.eval_adapter_contracts`, `runner.eval_substrate_contracts` | `eval_suite/adapters/README.md` | Must copy, not move. Original stays in `runner/` for import chain. Strip `tool_call_composite`/`tool-call composite` from public-facing names and docstrings. |
| **Eval adapter: tool-call atom suite** | `runner/eval_adapter_tool_call_atom.py` | `eval_suite/adapters/eval_adapter_tool_call_atom.py` | PUBLIC | tool_call_atom/tool-call atom suite → tool_call_atom | Y — same runner.* imports | `eval_suite/adapters/README.md` | Copy only. Strip `tool_call_atom`/`tool-call atom suite`. |
| **Eval adapter: retrieval-context suite** | `runner/eval_adapter_retrieval_context.py` | `eval_suite/adapters/eval_adapter_retrieval_reduction.py` | PUBLIC | retrieval_context/retrieval-context suite → retrieval_reduction | Y — imports `runner.phase65_measurement_grading` | `eval_suite/adapters/README.md` | Copy only. Strip name. |
| **Eval adapter: filesystem-agent suite** | `runner/eval_adapter_filesystem_agent.py` | `eval_suite/adapters/eval_adapter_filesystem_agent.py` | PUBLIC | filesystem_agent/filesystem-agent suite → filesystem_agent | Y — same runner.* imports | `eval_suite/adapters/README.md` | Copy only. Strip `filesystem_agent`/`filesystem-agent suite`. |
| **Eval adapter: terminal-workflow** | `runner/eval_adapter_terminal_workflow.py` | `eval_suite/adapters/eval_adapter_terminal_workflow.py` | PUBLIC | terminal_workflow/terminal-workflow → terminal_workflow | Y — imports `runner.terminal_workflow_paths`, `runner.phase65_measurement_contracts`, `runner.phase65_measurement_grading` | `eval_suite/adapters/README.md` | Copy only. Strip `terminal_workflow`/`terminal_workflow`/`terminal-workflow`. |
| **Eval adapter contracts** | `runner/eval_adapter_contracts.py` | `eval_suite/adapters/eval_adapter_contracts.py` | PUBLIC | none | Y — imported by all adapter files above | `eval_suite/adapters/README.md` | Copy only. No eval names. |
| **tool-call composite assets** | `runner/tool_call_composite_assets.py` | `eval_suite/adapters/tool_call_composite_assets.py` | PUBLIC | tool_call_composite → tool_call_composite | Y — imported by eval_adapter_tool_call_composite | `eval_suite/adapters/README.md` | Copy only. Strip names. |
| **filesystem-agent suite context bench** | `runner/filesystem_agent_context_bench.py` | `eval_suite/adapters/filesystem_agent_context_bench.py` | PUBLIC | filesystem_agent → filesystem_agent | Y — imported by eval_adapter_filesystem_agent | `eval_suite/adapters/README.md` | Copy only. Strip names. |
| **terminal-workflow paths** | `runner/terminal_workflow_paths.py` | `eval_suite/adapters/terminal_workflow_paths.py` | PUBLIC | terminal_workflow/terminal_workflow → terminal_workflow | Y — imported by eval_adapter_terminal_workflow | `eval_suite/adapters/README.md` | Copy only. Strip names. |
| **Phase65 measurement grading** | `runner/phase65_measurement_grading.py` | `eval_suite/graders/measurement_grading.py` | PUBLIC | terminal_workflow names used internally; strip for public | Y — imported by terminal_workflow and retrieval_context adapters | `eval_suite/graders/README.md` | Copy only. Review for internal eval name refs before publishing. |
| **Phase65 measurement contracts** | `runner/phase65_measurement_contracts.py` | `eval_suite/graders/measurement_contracts.py` | PUBLIC | none visible | Y — imported by terminal_workflow adapter | `eval_suite/graders/README.md` | Copy only. |
| **Eval substrate contracts** | `runner/eval_substrate_contracts.py` | `eval_suite/schemas/eval_substrate_contracts.py` | PUBLIC | none | Y — imported by all adapters | `eval_suite/schemas/README.md` | Copy only. |
| **Schemas** | `runner/schemas.py` | `eval_suite/schemas/core_schemas.py` | PUBLIC | none | Y — imported by graders, adapters, and runner itself | `eval_suite/schemas/README.md` | Copy only. |
| **Eval-derived task packs (fhard_01–08)** | `eval_suite/pressure_family_families/task_packs/hard/fhard_0*/` (8 packs) and mirrored in `tracking/collab/final_harness_eval_suite/task_packs/hard/` | `eval_suite/pressure_family/<family>/` (rename per cluster) | PUBLIC (solver_pack/, grader/grade.py for fhard_06–08, fixture_manifest.json, task_pack.yaml, ceiling/, known_bad/) | fhard_01: environment_bootstrap_runner_repair; fhard_02: service_lifecycle_readiness; fhard_03: filesystem_decoy_target_selection; fhard_04: hidden_verifier_repair; fhard_05: structured_retrieval_reduction; fhard_06: original_repo_recovery; fhard_07: tool_schema_workspace_mix; fhard_08: noisy_open_workflow | N (task pack YAMLs and grader scripts are standalone) | `eval_suite/pressure_family_families/` subtree already is the placeholder — promote in-place | **CRITICAL: grader/grade.py for fhard_01–05 calls `reviewer_pack/hidden_verifier` — do NOT move reviewer_pack/hidden_truth.json or hidden_verifier.py to public tree; they stay in `tracking/collab/final_harness_eval_suite/task_packs/`**. fhard_06–08 graders are self-contained (158–195 lines each) and safe. |
| **Eval-derived task packs (sentinel/composition)** | `eval_suite/pressure_family_families/task_packs/sentinel/` and `eval_suite/pressure_family_families/task_packs/composition/` | `eval_suite/pressure_family/<sentinel or composition>/` | PUBLIC (same carve-out: no reviewer_pack) | fsent_01: tool_call_composite→tool_call_composite in task_pack_id (rename); fsent_02–04: no strip needed | N | existing path is already the public home | **fsent_01 task_pack_id and row_id contains literal "tool_call_composite" — rename to `fsent_01_tool_call_composite` before publishing.** task_brief also mentions "tool-call composite-shaped" — reword. |
| **Harness-core registry files** | `eval_suite/harness_core/final_harness_v1/*.yaml` | stay in `eval_suite/harness_core/final_harness_v1/` | PUBLIC (except official_eval_family_board.yaml) | official_eval_family_board.yaml names tool-call composite, tool-call atom suite, retrieval-context suite, filesystem-agent suite, terminal-workflow explicitly | N | already public-targeted; `family_winner_registry.yaml` is stub-data (empty winners list) | `official_eval_family_board.yaml` is a REAL artifact but exposes all eval names verbatim. Recommend either (a) stripping names or (b) marking as internal-only. `pressure_family_provenance.yaml` also names source families but not eval brands — safe. |
| **Board files (9)** | `eval_suite/boards/*.json` | stay in `eval_suite/boards/` | PUBLIC | none visible in board JSON | N | already in place | All 9 boards are real routing configs. The `public_pressure_family_families_v1.json` uses neutral names already. |
| **Example scoreboards (8)** | `eval_suite/scoreboards/*.json` | stay in `eval_suite/scoreboards/` | PUBLIC | none | N | already in place | Real stub examples. Scrub any host path remnants. |
| **Real run attempts** | `eval_suite/attempts/final_harness_v1/20260530T1541*/` | stay (or sanitize) in `eval_suite/attempts/final_harness_v1/` | PUBLIC (after scrubbing) | none in board fields; result_rows.jsonl contain `/home/azureuser/...` host paths | N | already in place | `result_rows.jsonl` contain host paths that MUST be scrubbed before publishing. `run_summary.json` also lists host paths. `scoreboard.json`, `scoreboard.md` are clean. |
| **Harness-core sentinel_composition_board.yaml** | `eval_suite/harness_core/final_harness_v1/sentinel_composition_board.yaml` | stay in place | PUBLIC (after renaming fsent_01 refs) | fsent_01_tool_call_tool_call_composite_composite → fsent_01_tool_call_composite; task_pack_ref points to tracking path | N | already in place | References `tracking/collab/final_harness_eval_suite/task_packs/...` — these are internal paths that need an update if adapter migrates. |
| **tool-call composite adapter fixtures (fallback)** | `tracking/collab/final_harness_eval_suite/adapter_fixtures/tool_call_composite/` | `eval_suite/fixtures/tool_call_composite/` | PUBLIC | tool_call_composite → tool_call_composite | N | `eval_suite/fixtures/README.md` | Small set (22-line JSON + 5 API Python files). These are the fallback copies used when `research/sources/codebases/deepagents` is absent. |
| **retrieval-context suite Verified.csv (fallback)** | `tracking/collab/final_harness_eval_suite/adapter_fixtures/retrieval_context/Verified.csv` | `eval_suite/fixtures/retrieval_reduction/` | PUBLIC | retrieval_context → retrieval_reduction | N | `eval_suite/fixtures/README.md` | 9-line fallback fixture. |
| **filesystem-agent suite dataset fixtures (fallback)** | `tracking/collab/final_harness_eval_suite/adapter_fixtures/filesystem_agent/filesystem-agent/` | `eval_suite/fixtures/filesystem_agent/` | PUBLIC | filesystem_agent → filesystem_agent | N | `eval_suite/fixtures/README.md` | Small dataset + rubric. |
| **Schema YAML files** | `tracking/collab/final_harness_eval_suite/current_stack_manifest.schema.yaml`, `family_winner_registry.schema.yaml`, `recipe_candidates.schema.yaml` | `eval_suite/schemas/` | PUBLIC | none | N | `eval_suite/schemas/README.md` | 55–179 lines each. Real schema contracts. Safe to publish. |
| **Aether2 G2 homolog task defs** | `tracking/collab/aether2_g2_homologs/g2_01_file_artifact/`, `g2_02_service_survives_exit/`, `g2_03_interactive_session/`, `g2_04_package_install/`, `g2_05_long_running_job/` | `eval_suite/custom/<family>/` (new) | PUBLIC | none | N | `eval_suite/sentinels/README.md` | Each has `task.json`, `instruction.md`, `verifier.sh`. These are the live aether2 homolog test cases. Consider as sentinel candidates. |

### DO NOT MOVE (private / never-publish)

| artifact | current path | reason |
|---|---|---|
| Hidden verifiers + truth | `tracking/collab/final_harness_eval_suite/task_packs/*/reviewer_pack/hidden_verifier.py` and `hidden_truth.json` (26 files total) | Private answer keys — moving to public tree would contaminate the eval |
| Raw run dirs | `tracking/collab/final_harness_eval_suite/runs/20260528T*/`, `20260529T*/`, `20260530T*/` | Raw run dirs with model exchanges, host paths, bytecode |
| Eval-suite v1 build (source gone) | `tracking/collab/eval_suite_v1_build/families/` | Source .py deleted; only `__pycache__` .pyc bytecode remains — nothing publishable |
| Eval-suite v1 baseline certified runs | `tracking/collab/eval_suite_v1_baseline/certified_runs/runs/*/` | Certified workspace dirs with reviewer_pack bytecode; empty of source |
| Eval-suite v1 tournament / repair runs | `tracking/collab/eval_suite_v1_tournament_runs/`, `eval_suite_v1_repair_runs/` | Raw run dirs with potential host paths |
| terminal-workflow challenge lane | `tracking/collab/final_harness_eval_suite/terminal_workflow_challenge_lane.yaml` | Contains terminal-workflow challenge task IDs by name; private harness config |
| Eval native certification runs | `tracking/collab/eval_native_certification/` | Raw workspace runs with virtual environment artifacts |
| Result_rows.jsonl with host paths | `eval_suite/attempts/final_harness_v1/*/result_rows.jsonl` | Contains `/home/azureuser/...` paths — scrub before publishing |
| G2 homolog run receipts | `tracking/collab/aether2_g2_homologs/runs/`, `.aether2/host_receipts/` | Raw model exchanges and host receipts |
| aether2_g2_homologs tarballs | `tracking/collab/aether2_g2_homologs/*.tar.gz`, `*_evidence.tar.gz` | Opaque binary blobs with unknown contents |
| Aether2 fake progress run dirs | `tracking/collab/aether2_fake_progress_homologs/`, `aether2_fake_progress_analysis_20260614/` | Internal analysis runs |
| Certify first eval core runs | `tracking/collab/certify_first_eval_core/certified_runs/` | Certified workspace with reviewer_pack bytecode |

---

## 3. Custom vs Eval-Derived Classification

### Custom (purely original behavioral evals)

These test agent behaviors against the harness itself, not any external eval corpus:

| family | mechanism cluster | current path |
|---|---|---|
| `public_manifest_repair_smoke` | filesystem/artifact repair | `eval_suite/custom/public_manifest_repair_smoke/` |
| `homolog_contract_smoke` | contract/homolog verification | `eval_suite/custom/homolog_contract_smoke/` |
| `runtime_policy_hook_smoke` | runtime policy hooks | `eval_suite/custom/runtime_policy_hook_smoke/` |
| `mcp_registry_contract_smoke` | MCP registry discovery | `eval_suite/custom/mcp_registry_contract_smoke/` |
| `skill_loader_contract_smoke` | skill loader contracts | `eval_suite/custom/skill_loader_contract_smoke/` |
| `subagent_handoff_contract_smoke` | subagent handoff discipline | `eval_suite/custom/subagent_handoff_contract_smoke/` |
| `g2_01_file_artifact` (candidate) | file artifact creation | `tracking/collab/aether2_g2_homologs/g2_01_file_artifact/` |
| `g2_02_service_survives_exit` (candidate) | service lifecycle persistence | `tracking/collab/aether2_g2_homologs/g2_02_service_survives_exit/` |
| `g2_03_interactive_session` (candidate) | interactive session isolation | `tracking/collab/aether2_g2_homologs/g2_03_interactive_session/` |
| `g2_04_package_install` (candidate) | package install verification | `tracking/collab/aether2_g2_homologs/g2_04_package_install/` |
| `g2_05_long_running_job` (candidate) | long-running job oversight | `tracking/collab/aether2_g2_homologs/g2_05_long_running_job/` |

### Eval-Derived (derived from external eval pressure, names stripped)

| original name | neutral public name | mechanism cluster | current path | original eval |
|---|---|---|---|---|
| `fhard_01_toolchain_runner_repair` | `environment_bootstrap_runner_repair` | environment/toolchain | `eval_suite/pressure_family_families/task_packs/hard/fhard_01_toolchain_runner_repair/` | eval_suite_v1 toolchain seeds |
| `fhard_02_service_orchestration_flagship` | `service_lifecycle_readiness_flagship` | long-horizon orchestration, service | `eval_suite/pressure_family_families/task_packs/hard/fhard_02_service_orchestration_flagship/` | eval_suite_v1 service readiness seeds |
| `fhard_03_filesystem_decoy_patch` | `filesystem_decoy_target_selection` | filesystem/path | `eval_suite/pressure_family_families/task_packs/hard/fhard_03_filesystem_decoy_patch/` | filesystem target selection seeds |
| `fhard_04_hidden_verifier_repair` | `hidden_verifier_repair` | verification/completion | `eval_suite/pressure_family_families/task_packs/hard/fhard_04_hidden_verifier_repair/` | verification_completion_recovery seeds |
| `fhard_05_structured_retrieval_reduction` | `structured_retrieval_reduction` | retrieval/reduction | `eval_suite/pressure_family_families/task_packs/hard/fhard_05_structured_retrieval_reduction/` | context_retrieval_reduction seeds |
| `fhard_06_original_repo_recovery_flagship` | `original_repo_recovery_flagship` | filesystem/path, long-horizon | `eval_suite/pressure_family_families/task_packs/hard/fhard_06_original_repo_recovery_flagship/` | original (no eval) |
| `fhard_07_original_tool_schema_workspace_mix` | `tool_schema_workspace_mix` | tooling/tool-call, filesystem | `eval_suite/pressure_family_families/task_packs/hard/fhard_07_original_tool_schema_workspace_mix/` | original (no eval) |
| `fhard_08_original_noisy_open_workflow` | `noisy_open_workflow` | long-horizon orchestration | `eval_suite/pressure_family_families/task_packs/hard/fhard_08_original_noisy_open_workflow/` | original (no eval) |
| `fsent_01_tool_call_tool_call_composite_composite` | `fsent_01_tool_call_composite` | tooling/tool-call | `eval_suite/pressure_family_families/task_packs/sentinel/fsent_01_tool_call_tool_call_composite_composite/` | tool-call composite-shaped (derived) |
| `fsent_02_runtime_workspace_contract` | same (no eval name) | environment/toolchain | `eval_suite/pressure_family_families/task_packs/sentinel/fsent_02_runtime_workspace_contract/` | original |
| `fsent_03_filesystem_verifier_repair` | same | filesystem/path, verification | `eval_suite/pressure_family_families/task_packs/composition/fsent_03_filesystem_verifier_repair/` | original |
| `fsent_04_retrieval_reduction_closure` | same | retrieval/reduction | `eval_suite/pressure_family_families/task_packs/sentinel/fsent_04_retrieval_reduction_closure/` | original |
| `fsent_05_long_handoff_composition_smoke` | same | long-horizon, filesystem | `eval_suite/pressure_family_families/task_packs/composition/fsent_05_long_handoff_composition_smoke/` | original |

### Adapter-driven eval lanes (metadata only, not full task packs)

These are rows driven purely by the adapter code in `runner/`; the task definition comes from the live fixture files, not from a task_pack.yaml:

| adapter target | neutral public name | eval identifier to strip | adapter file |
|---|---|---|---|
| tool-call composite multi-turn composite rows | `tool_call_composite_rows` | tool_call_composite, tool-call composite, fbench_tool_call_composite_* | `runner/eval_adapter_tool_call_composite.py` |
| tool-call atom suite atom rows | `tool_call_atom_rows` | tool_call_atom, tool-call atom suite, fbench_tool_call_atom_* | `runner/eval_adapter_tool_call_atom.py` |
| retrieval-context suite verified rows | `retrieval_reduction_rows` | retrieval_context, retrieval-context suite, fbench_retrieval_context_* | `runner/eval_adapter_retrieval_context.py` |
| filesystem-agent suite filesystem-agent rows | `filesystem_agent_rows` | filesystem_agent, filesystem-agent suite, fbench_filesystem_agent_* | `runner/eval_adapter_filesystem_agent.py` |
| terminal-workflow public tasks | `terminal_workflow_rows` | terminal_workflow, terminal_workflow, terminal-workflow | `runner/eval_adapter_terminal_workflow.py` |

---

## 4. Family-Level vs Whole-Harness Lane Classification

### Family-level lane (single mechanism family)

These target one failure mode and should be runnable independently:

| family | mechanism cluster | lane type |
|---|---|---|
| `public_manifest_repair_smoke` | filesystem/artifact repair | custom family lane |
| `homolog_contract_smoke` | contract/homolog verification | custom family lane |
| `runtime_policy_hook_smoke` | runtime policy hooks | custom family lane |
| `mcp_registry_contract_smoke` | MCP registry | custom family lane |
| `skill_loader_contract_smoke` | skill loader | custom family lane |
| `subagent_handoff_contract_smoke` | subagent handoff | custom family lane |
| `environment_bootstrap_runner_repair` | environment/toolchain | pressure-family family lane |
| `service_lifecycle_readiness` | service process readiness | pressure-family family lane |
| `filesystem_decoy_target_selection` | filesystem/path | pressure-family family lane |
| `hidden_verifier_repair` | verification/completion | pressure-family family lane |
| `structured_retrieval_reduction` | retrieval/reduction | pressure-family family lane |
| `tool_call_composite` (adapter) | tooling/tool-call | pressure-family family lane |
| `tool_call_atom` (adapter) | tooling/tool-call | pressure-family family lane |
| `retrieval_reduction` (adapter) | retrieval/reduction | pressure-family family lane |
| `filesystem_agent` (adapter) | filesystem/path | pressure-family family lane |
| `terminal_workflow` (adapter) | filesystem/path + long-horizon | pressure-family family lane |

### Whole-harness lane (all families together)

`eval_suite/boards/public_eval_harness_v1.json` and `eval_suite/harness_core/final_harness_v1/final_suite_registry.yaml` define the harness-as-a-whole lane: 8 hard rows + 5 sentinel/composition rows + official eval adapter rows. This is the `final_harness_eval_suite_v1` board.

The `eval_suite/custom/harness/runtime_control_custom_harness_v1.json` defines the custom-harness-only sub-lane (6 custom families only).

---

## 5. Strongest Showcases

### Top 3–5 Custom Evals

1. **`public_manifest_repair_smoke`** (`eval_suite/custom/public_manifest_repair_smoke/`) — Complete, self-contained eval with a deterministic 116-line grader, fixture workspace with reference and candidate directories, and a full task_pack.json. Tests manifest normalization, SHA-256 checksum derivation, and summary consistency. Best showcase of the custom eval format.

2. **`mcp_registry_contract_smoke`** (`eval_suite/custom/mcp_registry_contract_smoke/`) — Tests MCP server discovery, schema mapping fidelity, invocation result typing, and hook permission traces. 77-line grader with rich reason codes. Directly tests the harness's MCP contract discipline.

3. **`subagent_handoff_contract_smoke`** (`eval_suite/custom/subagent_handoff_contract_smoke/`) — Tests subagent session handoff discipline. Compact but complete.

4. **`homolog_contract_smoke`** (`eval_suite/custom/homolog_contract_smoke/`) — Tests homolog contract verification behavior. Has the most detailed task_pack.json (63 lines).

5. **`g2_02_service_survives_exit`** (candidate from `tracking/collab/aether2_g2_homologs/g2_02_service_survives_exit/`) — Aether2 homolog with a real `verifier.sh` and workspace fixture (`server_ok.py`). Tests that a background service persists after the agent's shell exits. Excellent primitive.

### Top 2–3 Eval-Derived Families

1. **`fhard_02_service_orchestration_flagship`** (`eval_suite/pressure_family_families/task_packs/hard/fhard_02_service_orchestration_flagship/`) — The single flagship hard row. Complete solver workspace with `launcher.py`, `probe.py`, `cleanup.sh`, `service_config.json`, and `visible_verifier.py`. Tests long-horizon service orchestration with readiness-probe loops and cleanup discipline. Self-contained grader (27-line shell calling hidden verifier) with full fixture.

2. **`fhard_06_original_repo_recovery_flagship`** (`eval_suite/pressure_family_families/task_packs/hard/fhard_06_original_repo_recovery_flagship/`) — Second flagship. 195-line standalone grader with no hidden verifier dependency. Rich solver workspace with checkpoint files, incident postmortem, handoff manifest, and runtime env. Best example of an original (non-pressure-family) hard task.

3. **`fsent_01_tool_call_tool_call_composite_composite`** / renamed `fsent_01_tool_call_composite` (`eval_suite/pressure_family_families/task_packs/sentinel/fsent_01_tool_call_tool_call_composite_composite/`) — 161-line self-contained grader that validates tool call argument semantics, legacy no-op traps, and receipt closure. Best showcase of the sentinel family format. **Requires renaming before publish** (strip "tool_call_composite" from task_pack_id, row_id, and task_brief).

---

## 6. Open Questions / Ambiguities

1. **Duplicate hierarchy in `eval_suite/custom/`**: Both `eval_suite/custom/<family>/` (flat) and `eval_suite/custom/families/<family>/` exist with identical files. A canonical decision is needed: adopt the flat form (matches the board JSON refs) and remove `custom/families/`.

2. **`fsent_01` eval name leak**: The task_pack_id `fsent_01_tool_call_tool_call_composite_composite` and its task_brief text say "tool-call composite-shaped". This must be renamed and reworded before any public release. The `official_eval_family_board.yaml` in `eval_suite/harness_core/` also exposes all eval names explicitly — decision needed on whether this file is public or internal.

3. **grader/grade.py for fhard_01–05 call `reviewer_pack/hidden_verifier`**: The 28-line grade.py stubs in those packs hard-code the `reviewer_pack/hidden_verifier` import. As-is, they are non-runnable without the private reviewer_pack. The public tree needs either a no-op stub verifier interface documented, or the graders need a public-mode path that degrades gracefully.

4. **`result_rows.jsonl` host path scrubbing**: Both attempt files at `eval_suite/attempts/final_harness_v1/*/result_rows.jsonl` and `run_summary.json` contain `/home/azureuser/harnesseng/...` absolute paths in every field. These must be path-stripped or redacted before the public tree goes live.

5. **`sentinel_composition_board.yaml` points to `tracking/` paths**: The `task_pack_ref` values in `eval_suite/harness_core/final_harness_v1/sentinel_composition_board.yaml` point into `tracking/collab/final_harness_eval_suite/task_packs/...`. If the public tree is ever used standalone (without the `tracking/` subtree), these refs need updating to `eval_suite/pressure_family_families/task_packs/...`.

6. **`eval_suite_v1_build` source deleted**: The `tracking/collab/eval_suite_v1_build/families/` tree has only `__pycache__` bytecode; the `.py` source files were deleted. This means the esv1_* family seeds (tooling_tool_contract, service_process_readiness, context_retrieval_reduction, verification_completion_recovery, long_horizon_artifact_handoff) cannot be published from source — the `fhard` task packs in `tracking/collab/final_harness_eval_suite/task_packs/` are their successor equivalents and are the appropriate public artifacts.

7. **`terminal_workflow_challenge_lane.yaml` is unambiguously private**: Contains challenge task IDs (`retrieval-extraction-hard-row`, `service-lifecycle-hard-row`) by name. Do not publish.

8. **`evals/` directory is entirely stubs**: The three Python files in `evals/` are 7-line docstring-only skeletons. They should either be deleted or filled in before publication.

9. **Import chain for adapters**: Copying adapter files to `eval_suite/adapters/` without also copying `runner/*.py` dependencies (eval_adapter_contracts, schemas, eval_substrate_contracts, phase65_measurement_grading, phase65_measurement_contracts, tool_call_composite_assets, filesystem_agent_context_bench, terminal_workflow_paths) would produce broken imports. The public `eval_suite/adapters/` copies must either be self-contained or import from a co-published `eval_suite/graders/` and `eval_suite/schemas/`. Plan the import graph before moving.

10. **`official_eval_family_board.yaml` vs public safety**: This YAML in `eval_suite/harness_core/final_harness_v1/` names all five evals (tool-call composite, tool-call atom suite, retrieval-context suite, filesystem-agent suite, terminal-workflow) with their case IDs. Decision needed on whether to strip these to neutral names or treat the whole file as internal-only.

---

## 10-Line Summary of Most Important Findings

1. The real eval grader and adapter code lives entirely in `runner/` (17+ substantive Python files, 50–1330 lines each); nothing in `eval_suite/graders/`, `eval_suite/adapters/`, or `eval_suite/schemas/` contains real code yet — all are stub READMEs.
2. The 6 custom family eval packs in `eval_suite/custom/` are REAL and publication-ready: each has a working grader.py, complete task_pack.json, and fixture workspace.
3. The 13 pressure-family task packs are mirrored in both `eval_suite/pressure_family_families/` and `tracking/collab/final_harness_eval_suite/task_packs/`; the public mirror is the correct publication source, but graders for fhard_01–05 hard-depend on `reviewer_pack/hidden_verifier.py` which must never be published.
4. The `reviewer_pack/` dirs (hidden_verifier.py + hidden_truth.json) for all 13 task packs exist only in `tracking/collab/final_harness_eval_suite/task_packs/`; they are the primary private-only artifacts.
5. `eval_suite_v1_build/families/` source code is entirely deleted (only .pyc bytecode remains); it cannot be published.
6. The harness_core registry YAMLs in `eval_suite/harness_core/final_harness_v1/` are verbatim copies of the tracking source; `official_eval_family_board.yaml` names all five external evals verbatim and needs stripping or privatization.
7. Both attempt run dirs (`eval_suite/attempts/final_harness_v1/*/result_rows.jsonl`) contain `/home/azureuser/` host paths that must be scrubbed before publication.
8. `fsent_01_tool_call_tool_call_composite_composite` leaks the "tool_call_composite" eval identifier in its task_pack_id, row_id, and task_brief — it must be renamed to `fsent_01_tool_call_composite` before publishing.
9. Moving any adapter from `runner/` to `eval_suite/adapters/` carries an import chain risk; adapters depend on at least 5–6 other `runner.*` modules that must be co-copied.
10. The aether2 G2 homolog task definitions in `tracking/collab/aether2_g2_homologs/g2_0*/` are strong sentinel candidates for the public custom eval suite; they have real verifier.sh files and workspace fixtures but have not yet been promoted to `eval_suite/`.
