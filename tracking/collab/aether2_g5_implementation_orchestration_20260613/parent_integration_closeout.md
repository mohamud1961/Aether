# Aether-2 G5 Parent Integration Closeout

Status: `READY_FOR_G3_PREP_NO_BOARD_STARTED`

Created: 2026-06-13

## Summary

Team R and Team H both handed back `READY_FOR_PARENT_*` statuses. The parent
orchestrator inspected the final handoff files, checked the live schema join
points, normalized the official-runner EnvContract version field, applied the
post-implementation system prompt redesign, and reran the local gates.

No real targeted board or benchmark task was started.

## Inputs Accepted

- Team R handoff:
  `tracking/collab/aether2_g5_implementation_orchestration_20260613/runner_team_handoff.md`
- Team H handoff:
  `tracking/collab/aether2_g5_implementation_orchestration_20260613/harness_team_handoff.md`
- Prompt redesign artifact:
  `tracking/collab/aether2_g5_implementation_orchestration_20260613/system_prompt_redesign_pending.md`

## Parent Integration Actions

1. Verified both worker threads were idle and had handed back:
   - Team R: `READY_FOR_PARENT_RUNNER_INTEGRATION`
   - Team H: `READY_FOR_PARENT_HARNESS_INTEGRATION`
2. Checked cross-team schema fields:
   - Team H emits `env_contract_version`, `env_contract_digest`, `env_contract`
   - Team H emits blocker state under the ledger root as `blockers`
   - Team H exposes verifier-visible `action_digest.service_monitoring`
   - Team R preserves blocker/suppression/environment metadata in G2 rows and
     trace bundles
   - Team R official runner writes environment-contract, grader-isolation, and
     service-evidence artifacts
3. Normalized the official runner's EnvContract version to the shared string:
   `aether2_env_contract_v1`.
4. Applied the full post-implementation prompt redesign to
   `runner/aether2/prompts.py`.
5. Updated prompt and official-runner tests for the final prompt/schema contract.

## Files Changed By Parent Integration

- `runner/aether2/prompts.py`
- `tests/test_aether2_prompts.py`
- `tools/run_aether2_g3_official.py`
- `tests/test_run_aether2_g3_official.py`
- `tracking/collab/aether2_g5_implementation_orchestration_20260613/system_prompt_redesign_pending.md`
- `tracking/collab/aether2_g5_implementation_orchestration_20260613/parent_integration_closeout.md`

## Validation

Passed:

- `python3 -m pytest tests/test_aether2_prompts.py -q`
  - `4 passed`
- `python3 -m pytest tests/test_run_aether2_g3_official.py tests/test_aether2_prompts.py -q -p no:cacheprovider`
  - `9 passed`
- `python3 -m py_compile runner/aether2/*.py tools/run_aether2_g2.py tools/run_aether2_g3_official.py tools/aether2_decision_trace.py tools/aether2_grader_isolation.py tools/aether2_targeted_board.py tools/run_phase_journal.py`
- `python3 tools/aether2_genericity_check.py`
- `python3 -m pytest tests/test_aether2_*.py tests/test_run_aether2_g2.py tests/test_run_aether2_g3_official.py tests/test_run_aether2_tournament.py -q -p no:cacheprovider`
  - `193 passed in 96.72s`

Environment flakes observed and resolved:

- One focused join-point run hit `fork: Resource temporarily unavailable` inside
  the G2 interactive-session shell verifier. The exact test passed on rerun.
- One broad run hit `BlockingIOError: [Errno 35] Resource temporarily unavailable`
  while spawning the official runner `--help` import-hygiene check. The exact
  entrypoint import-hygiene test passed on rerun.

## Review

Requested review gate remained `codex_review_skill_plus_adversarial`.

Codex review helper attempt:

```bash
~/.codex/skills/codex-review/scripts/codex-review --mode auto
```

Result: blocked before review by local config/process setup:

```text
review command: codex review --uncommitted
/etc/profile: fork: Resource temporarily unavailable
WARNING: proceeding, even though we could not update PATH: Operation not permitted (os error 1)
Error loading config.toml: unknown variant `default`, expected `fast` or `flex`
in `service_tier`
```

Fallback review performed:

- source-level parent review of the runner/harness schema join points;
- prompt genericity review against `tools/aether2_genericity_check.py`;
- rerun of targeted and broad tests after accepted fixes.

Accepted parent finding:

- Team R official runner exposed `environment_contract_version` as integer `1`
  while Team H uses `aether2_env_contract_v1`. Fixed by normalizing the official
  runner to the shared string and adding a regression assertion.

Rejected/deferred:

- No additional runner/harness schema rewrite was needed after the version
  normalization.
- No real targeted board was started.
- No VM-side official run was started from this local parent closeout.

## Remaining Work

The implementation is locally ready for G3 preparation. Remaining work is
operational/eval-side, not known local harness code:

1. Run VM-side official-runner integration checks in the benchmark-native
   environment.
2. If VM-side checks pass, prepare the preregistered targeted board without
   broadening beyond the approved cap.
3. Keep the prompt redesign as the applied default unless targeted-board evidence
   shows a regression; if so, compare against the lean prompt variant in the same
   artifact.

