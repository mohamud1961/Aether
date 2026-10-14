# Task card: environment_bootstrap_runner_repair (v2)

Admission: **capability**. Reference, known-bad and careless controls test this v2 design.

## Design (v2)

- Goal-level ticket: a red CI job and a `python3`-only laptop failure. The contract is named as the source of truth.
- Indirection: the runner is `test_runner` + `test_target` from `config/toolchain_contract.json`, not a value in any note.
- Interpreter portability: the stale script calls `python` (absent) and `pytest` (not a dependency). The tests use
  only the standard library and assert `python3 >= 3.9`, so the repair has to work on any supported `python3`.
- Messiness: a legacy runner, a stale notes file that says `python` and pytest, a CI matrix and `.python-version`
  pinned to 3.11, a CI log showing `python: command not found`, and a stale `pyproject.toml` requirement.
- End-state grader: sealed command and package manager, report from real runner evidence, patch list must equal the
  set of changed files, the runner must pass in a fresh copy (`Ran 3 tests`, `OK`), byte identity of every other file.
- The visible check still checks only the report's shape against the contract.

## Controls

- Known-bad: 6 scripts (`known_bad/`).
- Careless: 5 scripts (`careless/`), one per standard behaviour.

## Check disposition

| Grader reason | Controls |
|---|---|
| missing_toolchain_repair_report | careless do_nothing, half_done |
| runner_command_mismatch | known_bad trusts_legacy_runner_alias; careless skip_check |
| package_manager_mismatch | known_bad wrong_package_manager |
| runner_script_not_patched | known_bad patch_list_names_decoy, report_without_script_patch; careless fake_it, wrong_target |
| runner_run_failed | known_bad report_without_passing_preflight (also in untouched workspace) |
| contract_modified | known_bad contract_rewritten_to_stale |
| decoy_file_modified | known_bad patch_list_names_decoy |
| patches_list_mismatch, preflight_not_successful, runner_test_count_mismatch, other_file_modified | guards only |
