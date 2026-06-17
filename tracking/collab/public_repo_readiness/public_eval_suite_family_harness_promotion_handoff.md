# Public Eval Suite Family / Harness Promotion Handoff

- Status: `COMPLETE`
- Source thread: `019eb760-ea75-7af1-8d62-6e3e8cd7ba2a`
- Target thread: `019eb760-ea75-7af1-8d62-6e3e8cd7ba2a`
- Date: `2026-06-16`

## Objective And Scope

Build a public eval map that is more than a flat smoke-pack list by adding:

- family-level summaries divided by family;
- a whole-harness overview;
- renamed calibration and adapted-pressure surfaces for the private collab
  registry material;
- publication-navigation links and a schema note so the surface reads like a
  coherent system.

Scope:

- promote public-safe summaries and indexes into `eval_suite/`;
- keep the executable smoke packs under `eval_suite/custom/`;
- keep private task packs, private verifier logic, raw runs, and raw collab
  archives out of the public surface;
- update publication/navigation docs so reviewers can find the new map.

Out of scope:

- creating branches, commits, pushes, worktrees, VMs, containers, or
  eval/full task runs;
- publishing raw traces, hidden verifiers, raw evidence ledgers, or private
  local paths;
- making production-readiness or eval-leadership claims.

## Sources Inspected

- `eval_suite/`
- `tracking/collab/final_harness_eval_suite/`
- `tracking/collab/aether2_g2_homologs/`
- `tracking/collab/aether2_fake_progress_homologs/`
- `tracking/collab/public_repo_readiness/collab_promotion_map_handoff.md`
- `docs/publication/collab_promotion_map.md`
- `docs/publication/public_evidence_index.md`
- `docs/publication/publication_gap_list.md`
- `docs/architecture/public-architecture.md`

## Artifacts Promoted

### Family-Level Navigation

- `eval_suite/families/README.md`
- `eval_suite/families/index.json`
- `eval_suite/families/public_manifest_repair_smoke.md`
- `eval_suite/families/homolog_contract_smoke.md`
- `eval_suite/families/runtime_policy_hook_smoke.md`
- `eval_suite/families/mcp_registry_contract_smoke.md`
- `eval_suite/families/skill_loader_contract_smoke.md`
- `eval_suite/families/subagent_handoff_contract_smoke.md`

### Whole Harness Overview

- `eval_suite/whole_harness/README.md`
- `eval_suite/boards/public_eval_harness_v1.json`
- `eval_suite/scoreboards/public_eval_harness_v1.example.scoreboard.json`

### Calibration And Adaptation Surfaces

- `eval_suite/calibration_lanes/README.md`
- `eval_suite/boards/public_calibration_lanes_v1.json`
- `eval_suite/scoreboards/public_calibration_lanes_v1.example.scoreboard.json`
- `eval_suite/adapted_pressure_families/README.md`
- `eval_suite/boards/public_adapted_pressure_families_v1.json`
- `eval_suite/scoreboards/public_adapted_pressure_families_v1.example.scoreboard.json`

### Schema And Navigation

- `eval_suite/schemas/public_eval_map_contract.md`
- `eval_suite/README.md`
- `eval_suite/custom/README.md`
- `eval_suite/boards/README.md`
- `eval_suite/scoreboards/README.md`
- `eval_suite/schemas/README.md`
- `eval_suite/adapters/README.md`
- `docs/architecture/public-architecture.md`
- `docs/publication/public_evidence_index.md`
- `docs/publication/publication_gap_list.md`
- `docs/publication/README.md`

## Rejected Or Kept Private

- raw task packs and hidden verifier material under
  `tracking/collab/final_harness_eval_suite/task_packs/`;
- raw run folders and trace bundles under `tracking/collab/final_harness_eval_suite/runs/`;
- row copies from private eval-style sources or eval-specific
  wording in the public map;
- any private local path, workspace dump, or raw evidence artifact;
- certification or eval-leadership language in the public summary layer.

## Validation

- path/link existence check for the changed public docs and summary files:
  - passed
- JSON/YAML parse checks for the structured new files:
  - passed for the added JSON artifacts
- `rg` sweeps over changed public files for private paths, secrets-looking
  tokens, raw trace / evidence-ledger exposure, private verifier leakage,
  private adaptation claims, stale style-guide drift, and production / status
  claims:
  - passed with no matches
- `git diff --check` over the changed files:
  - passed
- `python3 tools/aether2_genericity_check.py`:
  - passed

## Next Slice

Add one more public-safe executable family with a different failure pressure
than the existing smoke packs, then thread it into the family index, the
whole-harness overview, and the publication evidence index.

## External-State Confirmation

- No branch, commit, push, worktree, VM, container, or eval/full task run
  was created.
- No server or background process was intentionally left active.

## RAW_LEDGER_UPDATE

- Persisted: yes
- File: `tracking/ledger/inbox/2026-06-16/124154_codex_public-eval-suite-family-harness-promotion_0ff70919b9.md`

## Thread Send

- Target thread ID: `019eb760-ea75-7af1-8d62-6e3e8cd7ba2a`
- Tool/mechanism: `handoff artifact`
- Result: ready for orchestrator pickup
