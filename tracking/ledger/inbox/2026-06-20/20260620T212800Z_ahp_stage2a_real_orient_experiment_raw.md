# RAW_LEDGER_UPDATE: AHP Stage 2A Real-Orient Experiment

**Date:** 2026-06-20T21:28:00Z
**Type:** experiment_evidence
**Stage:** AHP Stage 2A — startup configurator task-understanding measurement

## Experiment Summary

Ran the AHP startup configurator (gpt-5.4-mini via azure_gpt54_mini_env) on
21 tasks (14 custom board rows + 7 TerminalBench rows) using REAL orient()
for tbench tasks (Docker workspace seeding + ContainerExecutor + orient())
and synthetic orientation for custom tasks.

**Purpose:** Measure whether the configurator truly understands tasks by
comparing its success_definition + verification_focus against each task's
REAL grader as an oracle. NO task solving, NO loop integration.

## Results

### Profile Generation

| Category | Total | Valid | Fallback | Lint-clean |
|----------|-------|-------|----------|------------|
| Custom   |  14   |  14   |    2     |    14      |
| TBench   |   7   |   7   |    0     |     7      |
| **Total**|  21   |  21   |    2     |    21      |

### Grader-Oracle Capability Test

| Metric               | Value |
|----------------------|-------|
| Total grader criteria |  190  |
| Covered              |   92  |
| Missed               |   66  |
| Invented             |   29  |
| Avg coverage ratio   |  0.52 |

Best coverage: regex-log (0.88), service_lifecycle_readiness_flagship (0.86),
noisy_open_workflow (0.75), fsent_04 (0.71), prove-plus-comm (0.71).

Worst coverage: original_repo_recovery_flagship (0.00),
filesystem_decoy_target_selection (0.00), kv-store-grpc (0.29).

### Pattern Analysis

**Common missed criteria:**
- Trace-level verifier event requirement (visible_verifier status=passed) —
  configurator says "run the check" but doesn't capture the trace audit
- Exact values vs. behavioral descriptions — grader checks specific numbers,
  hashes, file paths; configurator describes behaviors
- Internal grader mechanics (byte-exact file matching, exit code checks)

**Invented criteria (false positives):**
- Process methodology checks not enforced by graders
- Cross-field consistency requirements not in grader logic
- Structural format requirements when graders only check string presence

### Leak Detection

- Full orientation has 7 grader-leak keys per tbench task (env_contract
  paths: model_visible_test_paths, grader_only_test_paths, grader_boundary
  section, hidden_tests_available_to_model)
- ALL leaks stripped by solver_visible_orientation() — configurator received
  zero grader/hidden information (confirmed by orientation_used.json)

### Code Changes Made

1. `harness/aether2/runtime/adaptive_profile.py` (485 LOC):
   - Meta-prompt: added COMPACTNESS RULE and TOOL SELECTION instructions
   - Lint: made negation-aware (handles "do not skip verification",
     comma-separated lists "do not disable, bypass, or skip verification")
   - Validation: unknown tools in primary_tools produce warnings (move to
     reserve_capabilities), not errors
   - Orientation: delegates to helper module for grader-leak stripping

2. `harness/aether2/runtime/adaptive_profile_helpers.py` (99 LOC, NEW):
   - GRADER_LEAK_KEYS constant (13 fields to strip)
   - solver_visible_orientation() — allowlist + recursive denylist filter
   - strip_grader_keys() — recursive key removal
   - build_fallback_profile() — extracted from main module

3. `tools/run_ahp_real_orient_experiment.py` (NEW, experiment script):
   - Custom row profiling with synthetic orientation
   - TBench row profiling with real orient() via Docker workspace seeding
   - Leak detection and incremental artifact saving

### Diff vs Prior Synthetic Profiles

Custom rows (same tasks, different orientation mode + meta-prompt):
- 8/14 tool selections differ, 6/14 match
- Success definition counts vary moderately (same range)
- No new fallbacks compared to prior run baseline
- Model stochasticity + meta-prompt changes account for differences

### Token Cost

- Total input tokens: ~39K
- Total output tokens: ~22K
- Total estimated cost: $0.055

### Validation Gates

- pytest: 143 passed (unchanged count)
- genericity check: EXIT 0 (clean)
- No lingering Docker containers

## Artifact Paths

- Experiment output: tracking/local_runs/ahp_real_orient_experiment/20260620_212757/
- Grader oracle comparison: tracking/local_runs/ahp_real_orient_experiment/20260620_212757/grader_oracle_comparison.json
- Per-task artifacts: {custom|tbench}/{task_id}/{profile.json, success_definition.json, orientation_used.json, ...}
- Prior synthetic run (for diffing): tracking/local_runs/ahp_profile_experiment/20260620_192424/

## TBench Task Selection (7 tasks, why chosen)

1. git-leak-recovery — recovery/forensics: git history + secret extraction (cached)
2. regex-log — data/regex: precise pattern matching (cached)
3. financial-document-processor — OCR/classification: document processing (cached)
4. kv-store-grpc — service/protocol: gRPC server (cached)
5. gcode-to-text — exact-output: decode format to text (cached)
6. prove-plus-comm — formal/semantic: Coq proof completion (built in 90s)
7. db-wal-recovery — data-recovery: SQLite WAL (cached)

## Skipped Tasks

- prove-plus-comm initially failed (workspace at /workspace not /app), fixed
  by adding fallback cp path. Final run succeeded.
- No other tasks skipped.
- qemu*, install-windows*, make-doom*, build-linux-kernel* excluded per
  instructions (monster builds).
