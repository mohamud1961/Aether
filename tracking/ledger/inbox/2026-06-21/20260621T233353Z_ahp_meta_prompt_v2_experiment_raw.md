# RAW_LEDGER_UPDATE: AHP Meta-Prompt V2 Experiment

**Date:** 2026-06-21
**Type:** experiment
**Area:** harness/aether2/runtime/adaptive_profile
**Status:** complete

## Summary

One AHP meta-prompt iteration: added category coverage instructions, authority-level
schema split, and JSON repair. Reran the real-orient + grader-oracle profile experiment
on 14 custom + 7 tbench rows with the updated configurator.

## Changes Made (local, no commit)

- `harness/aether2/runtime/adaptive_profile.py` (500 LOC):
  - Meta-prompt: added CATEGORY COVERAGE (7 categories), DEPENDENCY AWARENESS,
    AUTHORITY SEPARATION instructions to system prompt
  - Schema: added hard_visible_requirements, inferred_success_requirements,
    verification_watchpoints, uncertain_or_exploratory_risks, do_not_assume fields
  - JSON repair: one retry on parse failure before fallback
  - Moved parse_profile_response and compact_tool_catalogue to helpers to stay at cap

- `harness/aether2/runtime/adaptive_profile_helpers.py` (190 LOC):
  - Added parse_profile_response, compact_tool_catalogue, attempt_json_repair
  - Added authority-level fields to fallback profile

- `tools/run_ahp_real_orient_experiment.py`: saves new authority-level fields

## Experiment Results

| Metric                          | Before (V1) | After (V2) | Delta    |
|--------------------------------|-------------|------------|----------|
| Avg raw coverage               | 0.52        | 0.62       | +0.10    |
| Avg anticipatable-only coverage| N/A         | 0.84       | (new)    |
| Total invented criteria        | 29          | 2          | -27      |
| Invented in hard_visible       | N/A         | 1          | (new)    |
| JSON parse fallbacks           | 2           | 0          | -2       |
| Validation fallbacks           | 0           | 1          | +1       |
| Total fallbacks                | 2           | 1          | -1       |
| Tasks at 0.0 coverage          | 2           | 0          | -2       |
| Profiles valid                 | 21/21       | 21/21      | same     |
| Lint clean                     | 21/21       | 21/21      | same     |
| Total cost                     | $0.0547     | $0.0773    | +$0.023  |
| pytest count                   | 143         | 143        | same     |

## Key Per-Task Improvements

- original_repo_recovery_flagship: 0.00 -> 0.67 raw, 1.00 anticipatable
- filesystem_decoy_target_selection: 0.00 -> 0.67 raw, 0.86 anticipatable
- kv-store-grpc: 0.29 -> 0.64 raw, 0.82 anticipatable
- git-leak-recovery: 0.43 -> 0.57 raw, 1.00 anticipatable
- db-wal-recovery: 0.37 -> 0.42 raw, 1.00 anticipatable
- fsent_04_retrieval_reduction_closure: 0.71 -> 0.86 raw

## Remaining Anticipatable Misses

1. **Trace-level visible_verifier event** (12/21 tasks): configurator mentions running
   the check but doesn't assert the trace event requirement. Systematic pattern.
2. **File existence checks** (3 tasks): configurator says "set X" but doesn't
   independently check the file exists after edit.
3. **Specific script content** (env_bootstrap): doesn't check scripts/run_tests.sh
   contains the exact runner_command string.
4. **Row count derivation** (financial-document): doesn't explicitly state "11 rows"
   even though it follows from "one per invoice + total".

## Evidence

- Experiment artifacts: tracking/local_runs/ahp_real_orient_experiment/20260620_233353/
- Grader-oracle comparison: grader_oracle_comparison.json in same directory
- Genericity check: clean (exit 0)
- pytest: 143 passed

## Decision Recommendation

Anticipatable-only coverage rose from unmeasured to 0.84 average. Raw coverage rose
from 0.52 to 0.62. Invented criteria dropped from 29 to 2. JSON fallbacks dropped
from 2 to 0. The meta-prompt improvements are net-positive.

**Recommend narrow Stage 2B** -- the configurator now reliably identifies anticipatable
success criteria and correctly separates visible requirements from inferred guidance.
The remaining systematic miss (trace-level verifier event) could be addressed by a
single generic instruction ("the harness trace must record the visible verifier outcome").
The 1 validation fallback (fsent_02) is a model response quality issue, not a prompt issue.
