# RAW_LEDGER_UPDATE: AHP Stage 2D Solve-Rate A/B

**Date:** 2026-06-21
**Timestamp:** 20260621T035424
**Type:** experiment_result
**Status:** completed
**trusted_promotion_evidence:** false

## Summary

End-to-end model-backed A/B: baseline Aether-2 vs AHP startup slice on 4 hard
rows, using azure_gpt54_mini_env (gpt-5.4-mini). 1 attempt per row per
condition (8 model-backed attempts total, bounded n=1).

## Bug Fix Discovered

The AHP wiring in `harness/aether2/control/loop.py` line 174 had a latent bug:
`verifier_task_contract` is a string (newline-joined requirements), but the
code did `list(set(verifier_task_contract) | set(...))` which exploded the
string into a set of characters. This caused `_build_completion_contract` to
receive a list instead of a string, producing `AttributeError: 'list' object
has no attribute 'split'` on every AHP run. Fixed by splitting the string into
lines before set-union, then rejoining. All 4 AHP runs succeeded after the fix.

## Per-Row A/B Results

| Row | Condition | Grader | Verifier | Calls | Steps | Fresh Tok | Cached Tok | Wall(s) | Finalize |
|---|---|---|---|---|---|---|---|---|---|
| service_lifecycle_readiness_flagship | baseline | pass | passed | 15 | 9 | 34476 | 149760 | 77.6 | implicit_stop |
| service_lifecycle_readiness_flagship | AHP | pass | passed | 11 | 8 | 30459 | 131712 | 66.3 | implicit_stop |
| fsent_06_exact_serialization_contract | baseline | pass | passed | 13 | 7 | 29696 | 123008 | 66.2 | task_done |
| fsent_06_exact_serialization_contract | AHP | pass | passed | 8 | 5 | 22618 | 66176 | 59.8 | implicit_stop |
| original_repo_recovery_flagship | baseline | pass | passed | 11 | 6 | 29805 | 100736 | 61.6 | task_done |
| original_repo_recovery_flagship | AHP | pass | passed | 11 | 6 | 49828 | 115584 | 69.2 | task_done |
| environment_bootstrap_runner_repair | baseline | pass | passed | 8 | 5 | 20651 | 65280 | 39.7 | implicit_stop |
| environment_bootstrap_runner_repair | AHP | pass | passed | 12 | 10 | 29998 | 156032 | 56.4 | implicit_stop |

## Win/Regression/Unchanged Tally

- service_lifecycle_readiness_flagship: **UNCHANGED** (pass -> pass)
- fsent_06_exact_serialization_contract: **UNCHANGED** (pass -> pass)
- original_repo_recovery_flagship: **UNCHANGED** (pass -> pass)
- environment_bootstrap_runner_repair: **UNCHANGED** (pass -> pass)

**Wins (fail->pass):** 0
**Regressions (pass->fail):** 0
**Unchanged:** 4/4

## Verifier/Grader Agreement

- Baseline: 4/4 agree
- AHP: 4/4 agree

## Cost/Steps Delta (AHP vs Baseline totals across 4 rows)

- Fresh tokens: baseline=114628, AHP=132903, delta=+18275 (+16%)
- Cached tokens: baseline=438784, AHP=469504, delta=+30720 (+7%)
- Model calls: baseline=47, AHP=42, delta=-5 (-11%)
- Wall time: baseline=245.1s, AHP=251.7s, delta=+6.6s (+3%)
- AHP startup overhead: 1 model call per row (4 total, included in AHP totals)

## AHP Contract Wiring Verification

All 4 AHP runs generated valid AdaptationContracts (no fallback):
- `used_fallback: false` on all 4 rows
- `hard_visible_requirements` generated and present in `completion_contract` artifact
- `inferred_success_requirements` generated and tagged `[inferred]` in authority_mapping
- `frozen_success_contract` present in prefix messages (verified from model exchange receipts)
- `[ahp_task_block]`, `[ahp_profile_summary]`, `[initial_plan]` all present in prefix
- `flag_off_baseline_diff.txt` shows DIFFERS for tool_schemas, completion_contract, verifier_stated_requirements, extra_prefix_messages, frozen_success_contract, initial_plan
- System prompt remains IDENTICAL (kernel only, no task-specific content)
- Tool schemas: 4-6 tools hidden per row (session/job tools removed where not needed)

## AHP Verifier/Completion Contract Wiring (from artifacts)

Confirmed from `.aether2/ahp/` artifacts on the service_lifecycle row:
- `hard_visible_requirements -> completion_contract`: 12 items reached completion_contract
- `inferred_success_requirements -> verifier_stated_requirements (tagged)`: 5 items reached verifier
- `do_not_assume -> verifier_do_not_assume`: 6 items reached verifier
- `initial_plan -> solver_checklist`: 5-step plan generated

## Interpretation

All 4 rows passed at both baseline and AHP. The user's premise that these rows
"FAIL at baseline" was not confirmed in this run -- all 4 passed under baseline
Aether-2 with gpt-5.4-mini. This means there was no headroom for AHP to
demonstrate a solve-rate improvement.

On 2/4 rows (service_lifecycle, serialization), AHP used fewer model calls and
less wall time. On 2/4 rows (repo_recovery, bootstrap_repair), AHP used more
calls, steps, and tokens. The per-row efficiency signal is mixed.

The aggregate delta is: AHP used 5 fewer model calls (-11%) but 18k more fresh
tokens (+16%) and 6.6s more wall time (+3%). The fresh-token increase reflects
the AHP startup call (profile generation) and longer context from the frozen
prefix messages. The call-count decrease suggests AHP's structured plan and
requirements helped the model converge more efficiently on some rows.

## Honest Verdict

**AHP showed no clear solve-rate effect on these 4 rows** because baseline
already passes all of them. This is a directional signal (n=1 per cell), not
promotion evidence. The bug fix in loop.py (verifier_task_contract set-union)
was necessary -- without it, every AHP run crashed with a runtime error. The
AHP contract wiring is now confirmed to work end-to-end for real model-backed
runs. To demonstrate solve-rate improvement, the A/B needs to target rows that
actually fail at baseline.

## Infrastructure Checks

- pytest: 151/151 passed
- genericity check: clean (exit 0)
- No commits made
- No processes/containers left running

## Output Roots

- Baseline: `tracking/stage2d_baseline/20260621T035424/`
- AHP: `tracking/stage2d_ahp/20260621T035424/`

## Files Changed (not committed)

- `tools/run_custom_eval_board.py`: added `--adaptive-profile` CLI flag, threaded through `run_attempt` -> `_run_model_worker` -> `run_aether2_loop`
- `harness/aether2/control/loop.py`: fixed `verifier_task_contract` set-union bug (string split before set, rejoin after)
- `tests/test_run_custom_eval_board.py`: updated monkeypatched `_fake_model_worker` signature to accept `adaptive_profile_enabled` kwarg
