# Ceiling: environment_bootstrap_runner_repair (v2)

## What a perfect solution does

1. Reads `config/toolchain_contract.json`. The runner is `test_runner` plus `test_target`:
   `python3 -m unittest tests.test_runner_contract`. The package manager is `pip`.
2. Notices that the stale `scripts/run_tests.sh` calls `python` (absent on the CI image and on
   `python3`-only laptops) and `pytest` (not a project dependency). It does not follow
   `docs/stale_runner_guidance.md`, `ci/matrix.yml` (pinned to 3.11) or `.python-version` (3.11).
3. Rewrites only `scripts/run_tests.sh` to the contract command. The test file uses the standard
   library only, so the same command works on any `python3` 3.9 or newer.
4. Runs `bash scripts/run_tests.sh` and sees `Ran 3 tests ... OK`. Records the real exit status.
5. Writes `out/toolchain_repair_report.json` with the command, `pip`, `preflight_success: true`
   and evidence drawn from the run, and writes `out/patches_applied.txt` listing exactly
   `scripts/run_tests.sh`.
6. Leaves the contract, the legacy runner, the docs, the CI files, the logs and the checker untouched.

The reference derives the command and package manager from the contract. It hard-codes the method,
not the values.

## Grader checks

- Report: `runner_command` equals the sealed command (`runner_command_mismatch`), `package_manager`
  is `pip` (`package_manager_mismatch`), `preflight_success` is `true` (`preflight_not_successful`).
- Patch list equals the set of files whose bytes actually changed (`patches_list_mismatch`).
- `scripts/run_tests.sh` contains the sealed command as a line (`runner_script_not_patched`).
- The runner passes in a fresh copy with `Ran 3 tests` and `OK` (`runner_run_failed`,
  `runner_test_count_mismatch`).
- Byte identity of every pristine file: `contract_modified`, `decoy_file_modified`, `other_file_modified`.

## Why each known-bad state is wrong

- `patch_list_names_decoy.sh`: the legacy runner is edited and listed; the real runner stays stale.
  `runner_script_not_patched` and `decoy_file_modified`.
- `wrong_package_manager.sh`: the report names `uv`, which the contract does not declare. `package_manager_mismatch`.
- `trusts_legacy_runner_alias.sh`: the old notes' alias is reported as the runner. `runner_command_mismatch`.
- `report_without_passing_preflight.sh`: the runner line is right, but it fails when run, and the report
  still says preflight passed. `runner_run_failed`.
- `contract_rewritten_to_stale.sh`: the contract is edited to agree with the stale runner. `contract_modified`.
- `report_without_script_patch.sh`: report and patch list are complete, but the runner is unchanged. `runner_script_not_patched`.

## Careless controls

- `do_nothing.sh`: no report. `missing_toolchain_repair_report`.
- `fake_it.sh`: plausible report, no repair, no run. `runner_script_not_patched`.
- `skip_check.sh`: takes the old pytest command, never runs it. `runner_command_mismatch`.
- `wrong_target.sh`: right command in the legacy file. `runner_script_not_patched`.
- `half_done.sh`: runner repaired, no report or patch list. `missing_toolchain_repair_report`.

## Grader expectations

- Reference state: `passed: true`, `score: 1.0`.
- Untouched workspace: `passed: false` with `missing_toolchain_repair_report`, `runner_run_failed`
  (the stale `python` call fails) and `runner_script_not_patched`.
