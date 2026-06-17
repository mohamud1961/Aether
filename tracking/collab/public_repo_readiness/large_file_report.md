# Large File Report

- Generated: `2026-06-15T16:09:56Z`

## Largest Top-Level Footprints

| Path | Size | Notes |
|---|---:|---|
| `.venv` | 490M | excluded from backup as reproducible cache/output |
| `experiments/runs` | 4.0K | excluded from backup as reproducible cache/output |
| `official_tasks` | 47M | private payload |
| `output` | 1.1M | excluded from backup as reproducible cache/output |
| `research/sources` | 2.1G | private payload |
| `runner` | 8.2M | kept in backup if present |
| `scratch` | 96K | excluded from backup as reproducible cache/output |
| `tests` | 5.4M | kept in backup if present |
| `tools` | 1.7M | kept in backup if present |
| `tracking` | 313M | kept in backup if present |
| `tracking/collab/aether2_g2_homologs` | 1.7M | kept in backup if present |
| `tracking/collab/aether2_run_analysis_20260615` | 7.6M | kept in backup if present |
| `tracking/collab/public_repo_readiness` | 180K | kept in backup if present |
| `tracking/ledger` | 552K | private payload |
| `venv` | 42M | excluded from backup as reproducible cache/output |

## Largest Current Changed/Untracked Files

| Size | Path | Classification |
|---:|---|---|
| 106419 | `runner/aether2/loop.py` | public-stageable |
| 81869 | `runner/aether2/delta.py` | public-stageable |
| 58227 | `tools/aether2_decision_trace.py` | public-stageable |
| 51412 | `tests/test_aether2_loop.py` | public-stageable |
| 45539 | `runner/aether2/verify.py` | public-stageable |
| 34794 | `tools/run_aether2_g3_official.py` | public-stageable |
| 34296 | `tools/run_aether2_g2.py` | public-stageable |
| 29325 | `tracking/collab/public_repo_readiness/thread_ledger_skill_mining_report.md` | public-stageable |
| 25603 | `tests/test_aether2_verify.py` | public-stageable |
| 23455 | `tracking/collab/public_repo_readiness/repo_inventory_publication_plan.md` | public-stageable |
| 22610 | `tests/test_run_aether2_g2.py` | public-stageable |
| 22534 | `tests/test_aether2_decision_trace.py` | public-stageable |
| 22283 | `tools/aether2_fake_progress_homologs.py` | public-stageable |
| 21676 | `tests/test_aether2_delta.py` | public-stageable |
| 21015 | `AGENTS.md` | private/hold |
| 20284 | `runner/aether2/orientation.py` | public-stageable |
| 19494 | `tracking/collab/public_repo_readiness/publication_master_plan.md` | public-stageable |
| 19449 | `tools/aether2_targeted_board.py` | public-stageable |
| 18814 | `runner/aether2/envelope.py` | public-stageable |
| 18602 | `runner/aether2/receipts.py` | public-stageable |

## Summary

- The dominant space consumers are the private source mirror (`research/sources`) and the local environment/cache layers that were intentionally excluded from the backup.
- No single modified/public-stageable file is large enough to be a publication risk on its own; the risk is concentrated in whole directories and raw evidence bundles.
