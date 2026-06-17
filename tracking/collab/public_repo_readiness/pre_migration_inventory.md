# Pre-Migration Inventory

- Generated: `2026-06-15T16:09:56Z`
- Branch: `master`
- HEAD: `f9accef6a0d2a023557d7232fd502ada259e7f2a`
- Current status snapshot: `5 modified`, `47 untracked`, `52 total status lines including branch header`

## Quiescence Check

- Direct process-list inspection was not available in this sandbox (`ps` and `pgrep` both failed with sandbox/process-listing restrictions).
- The tree was captured twice around backup/report generation and the backup completed without write conflicts, so there is no observed evidence of active project-owned writes during this freeze pass.
- Because the OS process table could not be queried, this is a best-effort quiescence check rather than an absolute claim.

## Ignore Verification

- Added ignore buckets for the raw collaboration execution trees that were still surfacing as untracked: `tracking/collab/aether2_build_orchestration/`, `tracking/collab/aether2_fake_progress_analysis_20260614/`, `tracking/collab/aether2_fake_progress_implementation_plan_20260614/`, `tracking/collab/aether2_g5_implementation_orchestration_20260613/`, `tracking/collab/aether2_g5_run_analysis_20260613/`, `tracking/collab/aether2_run_analysis_20260614/`, `tracking/collab/aether2_run_analysis_20260615/`, and `tracking/collab/**/.aether2/`.
- Added ignore buckets for the clearly internal planning docs that should not stay visible as public-stageable candidates: `tracking/collab/aether2_build_spec/`, `tracking/collab/aether2_g2_homologs/pre_g3_ready_handoff_20260612.md`, `tracking/collab/tbench_100_fable_context_pack_20260610/`, and `tracking/collab/variant_hypothesis_backlog.md`.
- Representative `git check-ignore` evidence: the repo now ignores `tracking/collab/aether2_build_orchestration/README.md`, `tracking/collab/aether2_g5_run_analysis_20260613/README.md`, `tracking/collab/aether2_run_analysis_20260615/l1_targeted_20260615T142411Z/progress.tsv`, `tracking/collab/aether2_fake_progress_analysis_20260614/older_vm_and_trace_rerun_fake_progress_analysis_20260614.md`, and `tracking/collab/aether2_g2_homologs/g2_01_file_artifact/.aether2/host_receipts/receipts/0001_action_run_command.json`.

## Current Dirty Surface

| Top-level path | Non-ignored changed/untracked files | Notes |
|---|---:|---|
| `.gitignore` | 1 | mixed / review needed |
| `AGENTS.md` | 1 | mixed / review needed |
| `runner` | 21 | public-stageable candidate |
| `scripts` | 4 | public-stageable candidate |
| `tests` | 30 | public-stageable candidate |
| `tools` | 9 | public-stageable candidate |
| `tracking` | 41 | mostly private research/collab material; public readiness docs are the exception |

## Public-Stageable Snapshot

- `runner/aether2/` source modules and package init.
- `scripts/configure_harnesseng_vm_autoshutdown.sh`, `scripts/deallocate_harnesseng_vm.sh`, `scripts/run_aether2_tournament.sh`, and the already-modified `scripts/build_harnesseng_runtime_bundle.sh`.
- `tests/test_aether2_*.py`, `tests/test_run_aether2_*.py`, and `tests/test_aether2_vm_lifecycle_scripts.py` plus `tests/conftest.py`.
- `tools/aether2_*.py`, `tools/run_*.py`, and `tools/run_phase_journal.py`.
- `tracking/collab/public_repo_readiness/` planning and mapping docs.
- `tracking/collab/skills/analyze-agent-runs/` skill package files.
- `tracking/collab/aether2_g2_homologs/` task-def files outside ignored `runs/` and `.aether2/` receipts.

## Deferred / Hold Material

- **private research mirrors**: research/sources/, research/intake/, research/external/
- **ledger / variant state**: tracking/ledger/, tracking/variants/
- **raw run bundles**: tracking/collab/**/runs/, tracking/collab/**/.aether2/, tracking/collab/aether2_*_run_analysis_*/, tracking/collab/aether2_*_analysis_*/
- **build/runtime caches**: .venv/, venv/, website/node_modules/, website/.next/, .pytest_cache/, .mypy_cache/, .ruff_cache/, .tox/, .nox/, .playwright-mcp/, .tmp_codex_home/
- **scratch/output/archive**: scratch/, output/, experiments/runs/, repomix-output.xml, *.log, *.jsonl, *.tar.gz, *.zip
- **eval corpora**: official_tasks/
- **private planning docs**: tracking/collab/aether2_build_spec/, tracking/collab/aether2_g2_homologs/pre_g3_ready_handoff_20260612.md, tracking/collab/tbench_100_fable_context_pack_20260610/, tracking/collab/variant_hypothesis_backlog.md

## Notes For Later Commit Slicing

- The code/runtime slice is coherent around `runner/aether2/`, the new `tools/*.py` shims, and the shell lifecycle scripts.
- The eval/documentation slice is coherent around `tests/` plus `tracking/collab/public_repo_readiness/`.
- The private source mirror `research/sources/codebases/quarantine/claude-code_ts_release` remains a hold-out and should not be published or force-added.

## Backup Reference

- Private archive: `<private tmp archive root>`
- Snapshot root: `<private tmp archive root>/snapshot`
- Manifest: `<private tmp archive root>/manifest.sha256`
- Manifest SHA256: `6a93a69326e8e240d03c7d28f07988e077396d4ef8512bfd93dbcb639232e61a`
- Verification log: `<private temp verify log>`
