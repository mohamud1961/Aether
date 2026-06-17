# Variant Move Map

Generated: 2026-06-16  
Scope: READ-ONLY discovery. No files were moved, edited, or deleted.

---

## 1. Executive Summary

### Where the real variant code and configs actually live

Real variant artifacts are split across **five locations** in the current working tree:

1. **`blocks/tools/` and `blocks/context/` and `blocks/execution/`** — the live, promoted winning or
   candidate mechanism implementations. These are the canonical source-of-truth Python files that are
   already in production in the active kernel routes. Every file in `variants/families/*/code/` is a
   verbatim copy of the corresponding `blocks/` file (zero diff confirmed). The real source is `blocks/`.

2. **`runner/`** — the whole-harness variant lines live here. The key files are:
   - `runner/active_evidence_kernel.py` (1844 lines, Phase 1 kernel line — REAL)
   - `runner/evidence_kernel.py` (660 lines, earlier narrower predecessor — REAL)
   - `runner/packet04_route_manifest.py` (2122 lines, route-manifest driving all variant selection — REAL)
   - `runner/kernel_control_plane.py` (679 lines, control-plane for model-led substrate — REAL)
   - `runner/kernel_layer2_audit.py` (Phase 6 Layer-2 audit addition — REAL)
   - `runner/kernel_*.py` (16 modular kernel support files — all REAL)

3. **`harness/aether2/`** — the current winning whole-harness line (Aether-2), with 16,603 lines
   across control, runtime, tools, traces, skills. This is the LIVE harness, not a variant candidate.
   The `runner/aether2/` sub-package is a thin compatibility re-exporter pointing to `harness/aether2/`.

4. **`tracking/collab/first_result_attribution_mechanism_tournament/`** — the raw scoreboard, prediction,
   and comparison_summary JSON for the Phase 3 attribution guard tournament (the real evidence base).
   These three JSON files are bit-for-bit identical to the files in both `variants/families/attribution_guard_tournament/`
   and `variants/families/tooling_tool_contract_tournament/` (same tournament data, two family names).

5. **`tracking/variants/mlpcp_v3/mlpcp_v3_from_official_run/`** — the MLPCP v2/v3 whole-harness variant
   line as pulled from the Azure VM. The canonical code exists in:
   - `harbor_bridge_patch_targets_20260611T012730Z/runner/mlpcp_v2_harbor_host.py` (4369 lines, REAL)
   - `harbor_bridge_patch_targets_20260611T012730Z/runner/mlpcp_v2_harbor_agent.py` (146 lines, REAL)
   - `harbor_bridge_patch_targets_20260611T012730Z/runner/mlpcp_v2_harbor_task_runner.py` (207 lines, REAL)
   - `harbor_memory_cockpit_patch_targets_20260611T013921Z/runner/mlpcp_v2/lean_cockpit.py` (735 lines, REAL)
   The full `runner/mlpcp_v2/` sub-package (capability_mapping, execute_plan, finalization, etc.) was
   purged from the working tree and exists only as imports referenced by `mlpcp_v2_harbor_host.py`.
   `runner/mlpcp_v2/` directory is currently EMPTY (confirmed). The `mlpcp_v2_complete_variant_package_expanded_docs/runner/`
   directory is also empty (only .DS_Store).

### What is REAL vs PLACEHOLDER in current `variants/`

**REAL (substantive code or scored data, can be published):**

- `variants/families/attribution_guard_tournament/code/*.py` — 5 Python files (11–232 lines each),
  all verbatim copies of `blocks/tools/*`; REAL code, but source is `blocks/`
- `variants/families/attribution_guard_tournament/decision_table.json` — 65-line sanitized decision
  table; REAL (sanitized from `tracking/collab/first_result_attribution_mechanism_tournament/`)
- `variants/families/attribution_guard_tournament/README.md` — REAL summary (29 lines)
- `variants/families/tooling_tool_contract_tournament/code/*.py` — 7 Python files; same 5 as above
  plus `contract_classifier.py` (154 lines) and `service_contract_first_receipt_closure.py` (195 lines);
  REAL code, sources are `blocks/tools/*`
- `variants/families/tooling_tool_contract_tournament/{comparison_summary,prediction,scoreboard}.json` —
  bit-for-bit identical to `tracking/collab/first_result_attribution_mechanism_tournament/`; REAL data
  but duplicated (same tournament, two family names)
- `variants/families/tooling_tool_contract_tournament/README.md` — REAL summary (20 lines)
- `variants/families/filesystem_target_selection_family/code/*.py` — 5 Python files, verbatim copies
  of `blocks/context/` and `blocks/execution/` files; REAL code
- `variants/families/finalization_truth_family/code/*.py` — 3 Python files: copies of
  `runner/kernel_layer2_audit.py` and `blocks/verification/{layered_acceptance_guard,trust_model}.py`; REAL code
- `variants/harness/code/active_evidence_kernel.py` — 1844 lines, verbatim copy of
  `runner/active_evidence_kernel.py`; REAL code
- `variants/harness/code/packet04_route_manifest.py` — verbatim copy of `runner/packet04_route_manifest.py`; REAL
- `variants/harness/code/kernel_control_plane.py` — verbatim copy of `runner/kernel_control_plane.py`; REAL
- `variants/harness/decision_history.md` — 350+ line chronological Phase 0–7 history; REAL and VERY
  valuable (the most complete narrative of variant decisions in the repo)
- `variants/harness/variant_hypothesis_backlog.md` — 200+ line living backlog with H1–H8; REAL
- `variants/harness/README.md` — REAL summary (32 lines)
- `variants/kernel/code/kernel_layer2_audit.py` — verbatim copy of `runner/kernel_layer2_audit.py`; REAL
- `variants/kernel/README.md` — REAL summary (25 lines)
- `variants/scoreboards/attribution_guard_tournament_v1.json` — 78-line real scoreboard with
  per-variant counts; REAL sanitized scoreboard
- `variants/scoreboards/whole_harness_stack_summary_v1.yaml` — 32-line structured stack summary; REAL
- `variants/scoreboards/model_led_substrate_v1.yaml` — 28-line control-plane review summary; REAL
- `variants/scoreboards/aether2_g5_harness_upgrade_v1.yaml` — 21-line Aether G5 summary; REAL
- `variants/shared/atomic_variant_cards.md` — 360-line YAML-fenced variant cards (v04_vc_01 through
  evidence_report_scaffold); REAL and public-safe
- `variants/shared/decision_rubric.md` — promotion/kill decision rubric; REAL
- `variants/shared/lineage_map.md` — public route/kernel/aether lineage table; REAL

**PLACEHOLDER / STUB (empty dirs, no content yet):**

- `variants/families/dependency_config_environment/` — EMPTY DIR (no files, no code)
- `variants/families/filesystem_open_workflow/` — EMPTY DIR (no files, no code)
- `variants/families/long_horizon_artifact_handoff/` — EMPTY DIR (no files, no code)
- `variants/families/terminal_workflow_verifier_repair/` — EMPTY DIR (no files, no code)
- `variants/families/filesystem_target_selection_family/variant_cards/` — EMPTY SUBDIR
- `variants/families/finalization_truth_family/variant_cards/` — EMPTY SUBDIR
- `variants/aether/` — README only (28 lines), no code or data files
- `variants/scoreboards/README.md` — 16-line placeholder only
- `variants/shared/README.md` — 12-line placeholder only
- `variants/families/README.md` — 14-line placeholder only

### Key structural finding: two tournament families share the same scoreboard

`variants/families/attribution_guard_tournament/` and `variants/families/tooling_tool_contract_tournament/`
both carry the SAME three JSON files (comparison_summary, prediction, scoreboard) with MD5 hash
`b47bd24b990e8deca7596a2b23a44908` for comparison_summary, and the same sentinel/target task IDs
(`ctc_semantics_*`). This is because both were run on the same Phase 3 "clean tool contract semantics"
eval rows. The distinction between the two families is in the mechanism code only: attribution_guard has
the 3 basic guard variants; tooling_tool_contract adds `contract_classifier` and `service_contract_first_receipt_closure`.
The "tooling_tool_contract_tournament" family name in `variants/families/` is the intended _next_ tournament
layer that adds these two additional mechanisms — but its scoreboard data is still from the Phase 3 run
(not the subsequent Goal 1b certified tournament in `tracking/collab/eval_suite_v1_tournament_runs/`).

---

## 2. Move-Map Table

Legend for import-risk column:
- `NONE` — file has no internal imports; safe to copy/move anywhere
- `runner.*` — imports runner sub-modules; keep `runner/` in PYTHONPATH or update import paths
- `blocks.*` — imports blocks sub-modules; same constraint

| Real artifact | Current path | Proposed destination | Level | Public/Private | Eval name to strip | Import risk | Replaces placeholder | Notes |
|---|---|---|---|---|---|---|---|---|
| Attribution guard common logic | `blocks/tools/result_attribution_guard_common.py` | `variants/families/attribution_guard_tournament/code/result_attribution_guard_common.py` | family-level | PUBLIC | none | `blocks.*` | already copied | Canonical source is `blocks/`; variant copy is verbatim. No move needed — update reference to point at `blocks/` as source |
| Combined guard module | `blocks/tools/combined_result_attribution_guard.py` | `variants/families/attribution_guard_tournament/code/combined_result_attribution_guard.py` | family-level | PUBLIC | none | `blocks.*` | already copied | Same as above |
| No-call attribution guard | `blocks/tools/no_call_attribution_guard.py` | `variants/families/attribution_guard_tournament/code/no_call_attribution_guard.py` | family-level | PUBLIC | none | `blocks.*` | already copied | Same as above |
| Ignored-IDs attribution guard | `blocks/tools/ignored_result_ids_guard.py` | `variants/families/attribution_guard_tournament/code/ignored_result_ids_guard.py` | family-level | PUBLIC | none | `blocks.*` | already copied | Same as above |
| App path normalizer | `blocks/tools/app_path_normalizer.py` | `variants/families/attribution_guard_tournament/code/app_path_normalizer.py` | family-level | PUBLIC | none | `blocks.*` | already copied | Same as above |
| Attribution tournament scoreboard (raw) | `tracking/collab/first_result_attribution_mechanism_tournament/scoreboard.json` | `variants/scoreboards/attribution_guard_tournament_v1.json` (already sanitized there) | family-level | PUBLIC (sanitized version already promoted) | none | NONE | yes | Raw version stays private; sanitized version already in `variants/scoreboards/attribution_guard_tournament_v1.json` |
| Attribution tournament prediction | `tracking/collab/first_result_attribution_mechanism_tournament/prediction.json` | `variants/families/attribution_guard_tournament/prediction.json` (new) | family-level | PUBLIC | none | NONE | no (new artifact) | Not yet in the public family dir; safe to copy as-is |
| Attribution tournament comparison | `tracking/collab/first_result_attribution_mechanism_tournament/comparison_summary.json` | `variants/families/attribution_guard_tournament/comparison_summary.json` (new) | family-level | PUBLIC | docker version string with `harnesseng-dev` hostname should be stripped | NONE | no (new artifact) | Contains Azure VM Docker preflight output; strip `tail` field or remove `docker_preflight` block before publishing |
| Contract classifier (tooling) | `blocks/tools/contract_classifier.py` | `variants/families/tooling_tool_contract_tournament/code/contract_classifier.py` | family-level | PUBLIC | none | `blocks.*` | already copied | Adds tool-call contract classification on top of attribution guards |
| Service contract first-receipt | `blocks/tools/service_contract_first_receipt_closure.py` | `variants/families/tooling_tool_contract_tournament/code/service_contract_first_receipt_closure.py` | family-level | PUBLIC | none | `blocks.*` | already copied | Service-readiness contract mechanism |
| Tooling tournament scoreboard (real Goal-1b run) | `tracking/collab/eval_suite_v1_tournament_runs/tooling_tool_contract_certified_tournament/` (run dirs only, no top-level scoreboard JSON found) | `variants/families/tooling_tool_contract_tournament/scoreboard_certified_v2.json` (new) | family-level | PRIVATE (raw runs, hidden verifiers) | `esv1_tooling_006_tool_call_atom_tool_call_composite_private_function_mix` → `pressure_family_composite_mix` | NONE | no | The actual certified Goal-1b tournament run dirs are in this path; only `.pyc` hidden verifier files found at top level; no aggregated scoreboard JSON exists at root level — needs to be generated from the per-run dirs |
| CWD invariant loop | `blocks/execution/cwd_invariant_loop.py` | `variants/families/filesystem_target_selection_family/code/cwd_invariant_loop.py` | family-level | PUBLIC | none | `blocks.*` | already copied | |
| Workspace target state | `blocks/context/workspace_target_state.py` | `variants/families/filesystem_target_selection_family/code/workspace_target_state.py` | family-level | PUBLIC | none | `blocks.*` | already copied | |
| Path-normalized exact target projection | `blocks/context/path_normalized_exact_target_projection.py` | `variants/families/filesystem_target_selection_family/code/path_normalized_exact_target_projection.py` | family-level | PUBLIC | none | `blocks.*` | already copied | |
| Path-normalized target resolution guard | `blocks/context/path_normalized_target_resolution_guard.py` | `variants/families/filesystem_target_selection_family/code/path_normalized_target_resolution_guard.py` | family-level | PUBLIC | none | `blocks.*` | already copied | |
| App workspace path normalizer | `blocks/context/app_workspace_path_normalizer.py` | `variants/families/filesystem_target_selection_family/code/app_workspace_path_normalizer.py` | family-level | PUBLIC | none | `blocks.*` | already copied | |
| Variant cards for filesystem_target_selection | `variants/shared/atomic_variant_cards.md` (v04_ex_02, v04_cb_01 sections) | `variants/families/filesystem_target_selection_family/variant_cards/v04_ex_02.yaml` and `v04_cb_01.yaml` | family-level | PUBLIC | `terminal_workflow_development_transfer_*` → `pressure_family_transfer_*` in anticipated_transfer_eval | NONE | yes (empty dir) | Cards already in `atomic_variant_cards.md`; extract and split by family to populate the empty `variant_cards/` subdir |
| Kernel Layer-2 audit | `runner/kernel_layer2_audit.py` | `variants/families/finalization_truth_family/code/kernel_layer2_audit.py` | family-level | PUBLIC | none | NONE | already copied | |
| Layered acceptance guard | `blocks/verification/layered_acceptance_guard.py` | `variants/families/finalization_truth_family/code/layered_acceptance_guard.py` | family-level | PUBLIC | none | `blocks.*` | already copied | |
| Trust model | `blocks/verification/trust_model.py` | `variants/families/finalization_truth_family/code/trust_model.py` | family-level | PUBLIC | none | `blocks.*` | already copied | |
| Variant card for finalization_truth | `variants/shared/atomic_variant_cards.md` (v04_vc_01 section) | `variants/families/finalization_truth_family/variant_cards/v04_vc_01.yaml` | family-level | PUBLIC | `terminal_workflow_development_transfer_*` → `pressure_family_transfer_*` | NONE | yes (empty dir) | Extract from atomic_variant_cards.md |
| Open-workflow answer normalizer | `blocks/tools/open_workflow_answer_candidate_normalizer.py` | `variants/families/filesystem_open_workflow/code/open_workflow_answer_candidate_normalizer.py` | family-level | PUBLIC | none | `blocks.*` | yes (empty dir) | Real code to populate empty family dir |
| Open-workflow path evidence normalizer | `blocks/tools/app_open_workflow_path_evidence_normalizer.py` | `variants/families/filesystem_open_workflow/code/app_open_workflow_path_evidence_normalizer.py` | family-level | PUBLIC | none | `blocks.*` | yes (empty dir) | |
| Open-workflow context dispatch | `blocks/context/open_workflow_answer_candidate_dispatch.py` | `variants/families/filesystem_open_workflow/code/open_workflow_answer_candidate_dispatch.py` | family-level | PUBLIC | none | `blocks.*` | yes (empty dir) | |
| Verifier repair projection | `blocks/context/path_normalized_verifier_repair_projection.py` | `variants/families/terminal_workflow_verifier_repair/code/path_normalized_verifier_repair_projection.py` | family-level | PUBLIC | `terminal_workflow` in name — DO NOT rename the file itself (it's not a eval row name); no strip needed in the code itself | `blocks.*` | yes (empty dir) | Mechanism code; the eval word is in the file name but the code is generic. Consider rename to `verifier_repair_projection.py` in public variant dir |
| Verifier episode parser | `blocks/verification/verifier_episode_parser.py` | `variants/families/terminal_workflow_verifier_repair/code/verifier_episode_parser.py` | family-level | PUBLIC | none | `blocks.*` | yes (empty dir) | |
| Active Evidence Kernel (whole-harness line 1) | `runner/active_evidence_kernel.py` | `variants/harness/code/active_evidence_kernel.py` | whole-harness | PUBLIC | none | `runner.*` (16 kernel sub-modules) | already copied | IMPORT RISK: this file has 16 `from runner.*` imports; must keep `runner/` in path or rewrite all imports if relocated outside repo structure |
| Evidence Kernel (whole-harness line 0/predecessor) | `runner/evidence_kernel.py` | `variants/harness/code/evidence_kernel.py` (new) | whole-harness | PUBLIC | none | `runner.action_bus` | no (new file) | Earlier, narrower predecessor to active_evidence_kernel; only imports `runner.action_bus` |
| Packet 04 Route Manifest | `runner/packet04_route_manifest.py` | `variants/harness/code/packet04_route_manifest.py` | whole-harness | PUBLIC | none | NONE (no internal imports) | already copied | The definitive variant-routing registry; zero import risk |
| Kernel Control Plane | `runner/kernel_control_plane.py` | `variants/harness/code/kernel_control_plane.py` | whole-harness | PUBLIC | none | `runner.kernel_services` | already copied | |
| MLPCP v2/v3 Harbor Host (whole-harness line 2) | `tracking/variants/mlpcp_v3/mlpcp_v3_from_official_run/harbor_bridge_patch_targets_20260611T012730Z/runner/mlpcp_v2_harbor_host.py` | `variants/harness/mlpcp_v3/code/mlpcp_v2_harbor_host.py` | whole-harness | PUBLIC (code only, not run dirs) | none | `runner.mlpcp_v2.*` (purged sub-package; code will not run standalone) | no | 4369-line MLPCP v3 harbor host — the most complete surviving MLPCP code; imports a purged sub-package |
| MLPCP v3 Lean Cockpit | `tracking/variants/mlpcp_v3/mlpcp_v3_from_official_run/harbor_memory_cockpit_patch_targets_20260611T013921Z/runner/mlpcp_v2/lean_cockpit.py` | `variants/harness/mlpcp_v3/code/lean_cockpit.py` | whole-harness | PUBLIC | none | NONE | no | 735-line formatter layer; no internal imports, self-contained |
| MLPCP v3 Pause State | `tracking/variants/mlpcp_v3/MLPCP_V3_PAUSE_STATE_20260611.md` | `variants/harness/mlpcp_v3/decision_history.md` (or `pause_state.md`) | whole-harness | PUBLIC | none | NONE | no | Compact pause/status note; safe to publish as-is |
| MLPCP v3 Harbor Agent | `tracking/variants/mlpcp_v3/mlpcp_v3_from_official_run/harbor_bridge_patch_targets_20260611T012730Z/runner/mlpcp_v2_harbor_agent.py` | `variants/harness/mlpcp_v3/code/mlpcp_v2_harbor_agent.py` | whole-harness | PUBLIC | none | `runner.mlpcp_v2.*` | no | 146-line agent shim |
| MLPCP v3 Harbor Task Runner | `tracking/variants/mlpcp_v3/mlpcp_v3_from_official_run/harbor_bridge_patch_targets_20260611T012730Z/runner/mlpcp_v2_harbor_task_runner.py` | `variants/harness/mlpcp_v3/code/mlpcp_v2_harbor_task_runner.py` | whole-harness | PUBLIC | none | `runner.mlpcp_v2.*` | no | 207-line task runner |
| Harness/Aether-2 (current winning line) | `harness/aether2/` (16,603 lines total) | stays at `harness/aether2/`; add `variants/aether/code/` symlink reference | whole-harness | PUBLIC (already public) | none | `harness.aether2.*` | no | This IS the live harness; do not move. Populate `variants/aether/` with a pointer and scoreboard only |
| MLPCP v2 raw run evidence | `tracking/variants/mlpcp_v2/mlpcp_v2_official_run/` (pytest cache only) | stay private | — | PRIVATE | — | — | no | Only pytest cache remains; the actual run artifacts were purged |
| MLPCP v3 raw run dirs | `tracking/variants/mlpcp_v3/mlpcp_v3_from_official_run/*/jobs/`, `*/logs/` | stay private | — | PRIVATE | — | — | no | Raw job logs, lock.json, run receipts |
| Attribution tournament raw run dirs | `tracking/collab/tooling_tool_contract_certified_tournament_clean/tooling_tool_contract_certified_tournament_clean/*/runs/` | stay private | — | PRIVATE | `esv1_tooling_006_tool_call_atom_tool_call_composite_private_function_mix` | — | no | Contains hidden_verifier.pyc files; entire run dir is private |
| Model-led substrate adversarial review | `tracking/collab/model_led_substrate_v1/reviews/adversarial_review_01.md` | stay private (or adapt to public summary if desired) | — | PRIVATE/borderline | — | — | no | Mentions specific integration gaps that may reveal grader internals |
| Model-led substrate accepted findings | `tracking/collab/model_led_substrate_v1/reviews/accepted_findings_resolution.md` | stay private | — | PRIVATE | — | — | no | |

---

## 3. Variant Families Found (family-level variants)

### 3a. Attribution Guard Tournament family (`attribution_guard_tournament`)

- **What it is**: Competing result-attribution guard mechanisms for tool-call results.
- **Variants**: `control_no_mechanism`, `ignored_result_ids_guard`, `no_call_attribution_guard`, `combined_guard`
- **Real code paths**: `blocks/tools/{result_attribution_guard_common,combined_result_attribution_guard,no_call_attribution_guard,ignored_result_ids_guard,app_path_normalizer}.py`
- **Scoreboard/decision**: `tracking/collab/first_result_attribution_mechanism_tournament/{comparison_summary,prediction,scoreboard}.json` (verbatim copies already in `variants/families/attribution_guard_tournament/`)
- **Keep/kill**: `ignored_result_ids_guard` → killed; `no_call_attribution_guard` → keep for follow-up (target lift, sentinel safe); `combined_guard` → keep for follow-up (full target lift, but sentinel regression); `control_no_mechanism` → retained as baseline
- **Public readiness**: READY — code, decision_table.json, and sanitized scoreboard already in place

### 3b. Tooling / Tool-Contract Tournament family (`tooling_tool_contract_tournament`)

- **What it is**: Extended attribution guard family adding tool-call contract classification and service-readiness receipt closure.
- **Additional variants** (beyond attribution guard): `contract_classifier`, `service_contract_first_receipt_closure`
- **Real code paths**: same as attribution_guard plus `blocks/tools/{contract_classifier,service_contract_first_receipt_closure}.py`
- **Scoreboard**: currently holds Phase 3 attribution_guard tournament data; the Goal-1b certified tournament run dirs are in `tracking/collab/eval_suite_v1_tournament_runs/tooling_tool_contract_certified_tournament/` but no aggregated scoreboard JSON exists at top level there (only per-run dirs with hidden_verifier.pyc)
- **Keep/kill**: no promotion yet from the certified tournament run; scoreboard data is from Phase 3
- **Public readiness**: PARTIAL — code is in place; scoreboard needs the real Goal-1b aggregated data

### 3c. Filesystem Target Selection family (`filesystem_target_selection_family`)

- **What it is**: Context-state and execution mechanisms to preserve target-file identity under path perturbations and decoy files.
- **Variants**: `v04_ex_02_cwd_workdir_invariant_propagation_guard` (cwd_invariant_loop), `v04_cb_01_decoy_resistant_target_selection` (workspace_target_state + path-normalized projections)
- **Real code paths**: `blocks/execution/cwd_invariant_loop.py`, `blocks/context/{workspace_target_state,path_normalized_exact_target_projection,path_normalized_target_resolution_guard,app_workspace_path_normalizer}.py`
- **Evidence**: Phase 5 family-level diagnostic (0/6 on filesystem_cwd rows), plus variant cards in `variants/shared/atomic_variant_cards.md`
- **Keep/kill**: no tournament scoreboard yet; Phase 4 single_family closeout shows target uplift not carrying to sentinels
- **Public readiness**: PARTIAL — code in place; variant_cards/ subdir is empty; no hypothesis.md or scoreboard

### 3d. Finalization Truth family (`finalization_truth_family`)

- **What it is**: Layer-2 success audit and acceptance gating to prevent `ungoverned_model_claim` false completions.
- **Variants**: `kernel_layer2_audit` (model-backed Layer-2 auditor), `layered_acceptance_guard` (non-substitution reason codes), `trust_model` (finalization trust tier)
- **Real code paths**: `runner/kernel_layer2_audit.py`, `blocks/verification/{layered_acceptance_guard,trust_model}.py`
- **Evidence**: Phase 6 adversarial review (`tracking/collab/model_led_substrate_v1/reviews/`); 7/7 unit tests pass in `tests/test_kernel_layer2_audit.py`; scoreboards in `variants/scoreboards/model_led_substrate_v1.yaml`
- **Keep/kill**: integrated and tested; no eval-suite run yet (AGENTS.md §Phase 6 status)
- **Public readiness**: PARTIAL — code in place; variant_cards/ subdir empty; no hypothesis.md

### 3e. Dependency / Config / Environment family (`dependency_config_environment`)

- **What it is**: cwd/workdir invariant guard plus app_workspace_path_normalizer combo for environment bootstrap failures.
- **Variants** (proposed): `cwd_workdir_invariant_guard`, `candidate_plus_app_workspace_path_normalizer_01`
- **Real code**: `blocks/context/app_workspace_path_normalizer.py` (shared with filesystem family); `blocks/execution/cwd_invariant_loop.py` (shared)
- **Evidence**: Phase 4 single_family closeout — target uplift existed, didn't carry to sentinels; Phase 5 family-level diagnostic (4/7 on environment/toolchain rows)
- **Public readiness**: STUB — empty dir; needs code symlinks from shared blocks, hypothesis.md, and scoreboard

### 3f. Filesystem Open Workflow family (`filesystem_open_workflow`)

- **What it is**: Open-workflow path evidence normalization for noisy open-file tasks.
- **Variants** (proposed): `open_workflow_answer_candidate_normalizer`, `app_open_workflow_path_evidence_normalizer`, combined with `v04_cb_01_decoy_resistant_target_selection`
- **Real code**: `blocks/tools/open_workflow_answer_candidate_normalizer.py`, `blocks/tools/app_open_workflow_path_evidence_normalizer.py`, `blocks/context/open_workflow_answer_candidate_dispatch.py`
- **Evidence**: Phase 4 — both routes failed target rows entirely; Phase 5 — no updated run
- **Public readiness**: STUB — empty dir; needs code copies, hypothesis.md

### 3g. Long-Horizon Artifact Handoff family (`long_horizon_artifact_handoff`)

- **What it is**: Multi-step artifact handoff with stateful compaction; historically the repo's ONLY solved family (6/6 pass).
- **Variants** (tested): `bounded_episode_01`, `stateful_compaction_external_context_01` (proposed), `verified_work_pocket_redesign` (proposed)
- **Real code**: primarily in `runner/packet07_cycle1_context_targeted_autoresearch.py` (long_horizon_spec) and `blocks/context/{lean_compact,sliding_window,full_history,closure_evidence_projection}.py` — scattered across historical packet07 files and current blocks
- **Evidence**: Phase 4 — passes target+private-suite eval but tool-call composite regression; Phase 5 — 6/6 on internal long-horizon row
- **Public readiness**: STUB — empty dir; no clear single code unit to promote (mechanism is embedded in packet07 runner files)

### 3h. terminal-workflow Verifier Repair family (`terminal_workflow_verifier_repair`)

- **What it is**: Verifier-episode parser and repair loop for tasks where the grader requires a re-run of verification after agent edits.
- **Variants** (tested): `verification_repair_loop_01`, `artifact_and_verifier_hard_gate_01`
- **Real code**: `blocks/context/path_normalized_verifier_repair_projection.py`, `blocks/verification/verifier_episode_parser.py`
- **Evidence**: Phase 4 — both routes passed all rows BUT the eval was non-discriminating (too easy)
- **Public readiness**: STUB — empty dir; code exists in blocks; needs to be populated
- **Note**: "terminal_workflow" appears in `path_normalized_verifier_repair_projection.py` filename; consider renaming to `verifier_repair_projection.py` in public copy

---

## 4. Harness Lines Found (whole-harness variants)

### 4a. Evidence Kernel / Packet-07 line (Phase 0 — historical)

- **What it is**: The original composable-blocks + flat_loop architecture with packet-07 eval runners.
- **Key files**: `runner/evidence_kernel.py` (660 lines), 25 `runner/packet07_*.py` files, 23 `runner/successor_*.py` files
- **Status**: Marked HISTORICAL REFERENCE ONLY in `runner/README.md`. Superseded by kernel + eval-suite approach.
- **Public candidate**: `runner/evidence_kernel.py` for `variants/harness/code/evidence_kernel.py` as the phase-0 predecessor
- **Keep/kill**: Killed architecturally; the one durable finding (long-horizon 6/6) was migrated to the active eval surface

### 4b. Active Evidence Kernel line (Phase 1 — current runner)

- **What it is**: Modular 16-module kernel providing receipts, gates, recovery, compaction, control-plane.
- **Key files**: `runner/active_evidence_kernel.py` (1844 lines), `runner/packet04_route_manifest.py` (2122 lines), `runner/kernel_control_plane.py` (679 lines), and 14 other `runner/kernel_*.py` files
- **Status**: ACTIVE — used by `runner/agent.py` and all `runner/eval_batch_runner.py` routes
- **Proposed destination**: `variants/harness/` (code already copied there verbatim)
- **Import risk**: `runner/active_evidence_kernel.py` imports 16 `runner.*` sub-modules; moving it outside the `runner/` namespace would require rewriting all imports
- **Keep/kill**: Kept; no eval-suite promotion yet

### 4c. MLPCP v2 / v3 Harbor line (Phase 7 — purged/paused)

- **What it is**: Cockpit/capability-graph/receipt "execute-plan" architecture with typed tools and a host-side Harbor bridge.
- **Key files** (surviving):
  - `mlpcp_v2_harbor_host.py` (4369 lines, in tracking/variants/mlpcp_v3/) — the core v3 host
  - `lean_cockpit.py` (735 lines, in tracking/variants/mlpcp_v3/) — the compact cockpit formatter
  - `mlpcp_v2_harbor_agent.py` (146 lines), `mlpcp_v2_harbor_task_runner.py` (207 lines)
- **Status**: PAUSED. `runner/mlpcp_v2/` is EMPTY (purged). The harbor host references a purged `runner/mlpcp_v2.*` sub-package (capability_mapping, execute_plan, finalization, etc.) that no longer exists in the tree
- **Proposed destination**: `variants/harness/mlpcp_v3/code/`
- **Import risk**: HIGH — `mlpcp_v2_harbor_host.py` imports from `runner.mlpcp_v2.*` which is purged; code cannot be executed standalone
- **Keep/kill**: Kept for reference/resumption; `lean_cockpit.py` is the most self-contained publishable piece

### 4d. Aether-2 line (current winning line)

- **What it is**: The live harness under `harness/aether2/` with control loop, runtime, tools, traces.
- **Key files**: `harness/aether2/control/loop.py` (2634 lines), `harness/aether2/traces/delta.py` (2099 lines), 16,603 total lines across the package
- **Status**: ACTIVE and canonical. `runner/aether2/` is a thin compatibility re-exporter.
- **Proposed destination**: stays at `harness/aether2/`; add reference/summary to `variants/aether/`
- **Import risk**: This IS the live harness; touching it risks `harness.aether2` imports everywhere including tests and `tools/run_aether2_g3_official.py`
- **Keep/kill**: Kept; no eval promotion yet

---

## 5. Showcase Set

### Strongest family-level variants (3–5)

1. **Attribution Guard Tournament** (`variants/families/attribution_guard_tournament/`) — Best public example of preregistered prediction + comparison + keep/kill reasoning with real scored data. Decision table, scoreboard, and code are all in place. Story: combined_guard hit target 2/2 but failed sentinel; no_call_attribution_guard balanced target lift with sentinel safety.

2. **Tooling / Tool-Contract Tournament** (`variants/families/tooling_tool_contract_tournament/`) — Extends the attribution guard story with contract classification and service-readiness receipt closure. Code is more complete (7 files vs 5). Interesting because it shows the mechanical extension path.

3. **Finalization Truth family** (`variants/families/finalization_truth_family/`) — Best example of a harness-control variant (not a model-facing mechanism): Layer-2 audit + layered acceptance guard closes the `ungoverned_model_claim` gap. Supported by adversarial review evidence and 7/7 passing unit tests. The mechanism story (dead-code integration bug found and fixed by review) is instructive.

4. **Filesystem Target Selection family** (`variants/families/filesystem_target_selection_family/`) — Good example of context + execution co-mechanism (cwd invariant + decoy-resistant target projection). Grounded in Phase 5 failure analysis (0/6 on filesystem rows). The variant cards in `atomic_variant_cards.md` are the richest structured specification in the repo.

5. **Long-Horizon Artifact Handoff** (currently empty dir, but the underlying story) — Only family that ever achieved 6/6 on its target eval. The tool-call composite regression finding (Phase 4) is the most concrete cross-eval interaction evidence in the repo. Would require constructing the public artifact from `packet07_cycle1_context_targeted_autoresearch.py` + decision_history Phase 0 narrative.

### Strongest whole-harness lines (1–2)

1. **Active Evidence Kernel line** (`runner/active_evidence_kernel.py` + `runner/packet04_route_manifest.py`) — Best showcase because: (a) the route manifest is a clean self-contained Python file with zero internal imports that shows exactly how variant routing works; (b) the kernel has the richest per-module decomposition in the repo; (c) the Phase 6 adversarial review → integration fix → unit test cycle is the cleanest evidence of responsible harness engineering.

2. **MLPCP v3 / Lean Cockpit** (`lean_cockpit.py` from `tracking/variants/mlpcp_v3/`) — Best showcase of an alternative architecture: a compact operating dashboard (cockpit) that shows the model its known state without coercive forcing language. `lean_cockpit.py` is self-contained (no internal imports), 735 lines, readable. The pause state document describes a clear hypothesis (receipt-memory patch) and honest outcome (service-startup-row passed, hard-2 did not). The incomplete `runner/mlpcp_v2.*` sub-package is a known blocker for any live use.

---

## 6. Eval Name Stripping Map

The following eval identifiers appear in artifact names and must be neutralized before public promotion:

| Original eval identifier | Appears in | Proposed neutral replacement | Notes |
|---|---|---|---|
| `tool_call_composite` | `fsent_01_tool_call_tool_call_composite_composite` (task_pack_id, row_id) | `pressure_family_tool_call_composite` | In `eval_suite/pressure_family_families/task_packs/sentinel/` |
| `tool_call_atom_tool_call_composite_private_function_mix` | `esv1_tooling_006_tool_call_atom_tool_call_composite_private_function_mix` (run dir name in certified tournament) | `pressure_family_private_function_mix` | Run dir in `tracking/collab/tooling_tool_contract_certified_tournament_clean/` (stays private) |
| `retrieval_extraction_hard_row` | `source_eval_family: retrieval_extraction_hard_row` in `fhard_05_structured_retrieval_reduction/task_pack.yaml` | `pressure_family_retrieval_extraction` | The task_pack_id itself (`fhard_05_structured_retrieval_reduction`) is already neutral |
| `terminal_workflow` / `terminal_workflow` prefix | `eval_adapter_terminal_workflow*.py` (runner files), `terminal_workflow_paths.py`, `TERMINAL_WORKFLOW_` constants | Leave runner adapter files as-is (they are backend adapters, not public variant artifacts); strip from public eval family names only | The runner adapters are internal infrastructure |
| `terminal_workflow` in variant family name | `variants/families/terminal_workflow_verifier_repair/` (directory name) | `verifier_repair` | Rename the family dir in the public tree |
| `terminal_workflow_development_transfer_*` | Anticipated-transfer-eval fields in `atomic_variant_cards.md` | `pressure_family_transfer_*` | In `variants/shared/atomic_variant_cards.md`; several `anticipated_transfer_eval` fields |
| `terminal_workflow_100` | `tracking/collab/tbench_100_fable_context_pack_20260610/` | stays private (tracking dir) | Decision history source only |

---

## 7. Import Risk Summary

Files that MUST stay in the `runner/` Python namespace (or have their imports rewritten) to avoid breaking the live harness:

| File | Importers | Risk if moved outside runner/ |
|---|---|---|
| `runner/active_evidence_kernel.py` | `runner/agent.py`, `runner/kernel_native_tools.py`, `tests/test_active_evidence_kernel.py`, `tests/test_model_led_substrates.py`, `tests/test_kernel_artifacts.py` | HIGH: 5 importers; all tests would break |
| `runner/evidence_kernel.py` | `runner/agent.py`, `tests/test_evidence_kernel.py` | MEDIUM: 2 importers |
| `runner/packet04_route_manifest.py` | `runner/agent.py`, `runner/eval_batch_runner.py`, `blocks/execution/trace_learning_loop.py`, 20+ `runner/packet07_*.py` files | HIGH: 20+ importers |
| `runner/kernel_control_plane.py` | `runner/active_evidence_kernel.py`, `runner/agent.py`, `runner/kernel_compaction.py`, `runner/kernel_working_window.py`, tests | HIGH |
| `runner/kernel_layer2_audit.py` | `runner/kernel_gates.py` (indirectly via active_evidence_kernel) | MEDIUM |
| `harness/aether2/` | all of `runner/aether2/`, `tools/run_aether2_g3_official.py`, `tools/aether2_targeted_board.py`, tests | CRITICAL: do not move; this IS the live harness |

The `variants/harness/code/` copies are SNAPSHOTS only — they reference `runner.*` imports. Any reviewer trying to run them directly from `variants/harness/code/` would hit import errors unless running from the repo root with `runner/` on the path.

---

## 8. What Must Stay Private

- `tracking/collab/tooling_tool_contract_certified_tournament_clean/**/runs/` — all per-run dirs (contain `hidden_verifier.pyc` files)
- `tracking/collab/model_led_substrate_v1/evals/`, `full_board/` — raw eval run rows with reviewer packs
- `tracking/collab/model_led_substrate_v1/workers/` — internal worker handoffs
- `tracking/variants/mlpcp_v2/mlpcp_v2_official_run/` — only pytest cache remains; no value in making public
- `tracking/variants/mlpcp_v3/mlpcp_v3_from_official_run/*/jobs/`, `*/logs/` — raw job logs and run receipts
- `tracking/collab/autonomous_loop/*/runs/` — raw run directories with certified workspaces and hidden verifiers
- `tracking/collab/eval_suite_v1_tournament_runs/**/runs/` — all tournament raw run dirs
- `eval_suite/attempts/` — two run timestamp dirs contain result rows with `/home/azureuser/` host paths that need scrubbing
- Any `hidden_truth.json`, `hidden_verifier.py`, or `reviewer_pack/` content anywhere

---

## 9. Open Questions

1. **Where is the Goal-1b certified tooling tournament aggregated scoreboard?** The per-variant run dirs exist in `tracking/collab/eval_suite_v1_tournament_runs/tooling_tool_contract_certified_tournament/` but there is no top-level scoreboard JSON. It may be in a worker's output that was not pulled, or it was generated but not committed. The `variants/families/tooling_tool_contract_tournament/scoreboard.json` is using Phase-3 attribution data as a placeholder.

2. **Where is the complete mlpcp_v2 sub-package?** `mlpcp_v2_harbor_host.py` imports `runner/mlpcp_v2/{capability_mapping,execute_plan,finalization,failure_classes,final_completion,integration,live_model,model_io,model_loop,receipts,references,verifier_critic}.py` — none of these exist in the current tree. The `mlpcp_v2_complete_variant_package_expanded_docs/runner/` is empty. The sub-package was purged from the working tree (confirmed via `runner/mlpcp_v2/` empty dir) and is not in git history (no commits found for those paths). Any future use of MLPCP v3 would require reconstructing this sub-package from the VM.

3. **Tournament runner scripts missing from tools/**: `tests/test_run_first_result_attribution_mechanism_tournament.py` imports `tools.run_first_result_attribution_mechanism_tournament` and `tests/test_clean_tool_contract_diagnostic_family.py` imports `tools.clean_tool_contract_diagnostic_family` — neither script exists in `tools/`. These tests would fail with ImportError. Confirm whether these scripts were deleted or never committed.

4. **Long-horizon artifact handoff family has no single code unit**: The mechanism is embedded in `runner/packet07_cycle1_context_targeted_autoresearch.py` (historical reference file) and in `blocks/context/{lean_compact,sliding_window,closure_evidence_projection}.py`. There is no clean "long_horizon_variant_code.py" to promote. Creating a clean family entry would require extracting the relevant blocks from the packet07 file.

5. **Should `terminal_workflow_verifier_repair/` be renamed?** The word "terminal_workflow" appears only in the directory name, not in the code itself. Renaming to `verifier_repair/` in the public `variants/families/` tree would strip the eval identifier without touching any code.

6. **`eval_suite/attempts/` host-path scrubbing**: Two run dirs in `eval_suite/attempts/final_harness_v1/` contain `result_rows.jsonl` with `/home/azureuser/` paths. If these are to be published, the host-path references need scrubbing to generic `/workspace/` equivalents. Currently unscrubbbed.

7. **Aether-2 variants entry is still empty**: `variants/aether/` has only a README. The Aether G5 run analysis (`tracking/collab/aether2_g5_run_analysis_20260613/`) is the richest data on Aether-2 performance, but it is private (95% invalid-launch run; not suitable for public promotion). The H1–H8 backlog in `variants/harness/variant_hypothesis_backlog.md` is the most public-ready Aether evidence artifact.

---

## 10-Line Summary

1. Real family-level variant code lives in `blocks/{tools,context,execution,verification}/`; all `variants/families/*/code/` dirs are verbatim copies.
2. Real whole-harness variant code lives in `runner/` (active_evidence_kernel, evidence_kernel, packet04_route_manifest, kernel_control_plane, 16 kernel modules) and in `tracking/variants/mlpcp_v3/` (harbor host + lean cockpit).
3. `variants/families/attribution_guard_tournament/` is the only fully populated family (code + decision_table + README + scoreboard); `tooling_tool_contract_tournament/` has code + scoreboards (but scoreboards are Phase-3 data, not the Goal-1b certified run).
4. Four family dirs are EMPTY stubs with no files: `dependency_config_environment/`, `filesystem_open_workflow/`, `long_horizon_artifact_handoff/`, `terminal_workflow_verifier_repair/`; their real code is in `blocks/`.
5. The MLPCP v2/v3 whole-harness line code (harbor host, lean cockpit) survives only in `tracking/variants/mlpcp_v3/`; the full `runner/mlpcp_v2/` sub-package was purged and is unrecoverable from the local tree.
6. `variants/harness/decision_history.md` is the highest-value single document in the repo for understanding variant lineage (Phase 0–7 history, 350+ lines, honest about failures).
7. Eval names to strip: `tool_call_composite` → `pressure_family_tool_call_composite` (fsent_01), `tool_call_atom_tool_call_composite` → `pressure_family` (run dir name, stays private), `retrieval_extraction_hard_row` → `pressure_family_retrieval_extraction` (source_eval_family field in fhard_05), `terminal_workflow_verifier_repair` dir → `verifier_repair`.
8. Import risk is HIGH for `active_evidence_kernel.py` and `packet04_route_manifest.py` (20+ importers each); snapshot copies in `variants/harness/code/` must stay as read-only references — never a relocation target.
9. The strongest showcase set: attribution_guard_tournament (only scored decision table), finalization_truth_family (adversarial review evidence), active_evidence_kernel line (route-manifest self-documentation), lean_cockpit.py from MLPCP v3 (self-contained, zero imports).
10. Three open questions block completion: missing Goal-1b certified tournament aggregated scoreboard, purged mlpcp_v2 sub-package, and missing `tools/run_first_result_attribution_mechanism_tournament.py` + `tools/clean_tool_contract_diagnostic_family.py` scripts.
