# Ceiling: runtime_workspace_contract (v2)

## What a perfect solution does

1. Resolves the effective contract in layers. `config/base_contract.json` gives `python_command`
   (`python3`). `config/runtime_contract.json` gives `workspace_root` (`/workspace/runtime`) and
   `runner_profile` (`ci-python`).
2. Follows `profiles_file` to `config/runner_profiles.json` and takes the `ci-python` command,
   `python3 -m pytest -q`. It does not take the `uv` command from `runner_profiles.json.bak`, the
   `ci-python` entry in the backup, or the stale notes.
3. Verifies the pin: the SHA-256 of the live profiles file equals `profiles_sha256`. It verifies, so the
   classification rule gives `capability_success`. The missing `uv` on the old CI log is not the rule's test.
4. Writes `out/final_submission.json` with those four values and runs the visible check.
5. Leaves every file under `config/`, `docs/`, `logs/` and `checks/` unchanged.

The reference follows the same layering and the same pin check. It hard-codes the method, not the values.

## Grader checks

- `python_command`, `workspace_root`, `runner_command`, `runtime_classification` each equal the sealed
  effective value (`python_command_mismatch`, `workspace_root_mismatch`, `runner_command_mismatch`,
  `runtime_classification_mismatch`).
- The submission exists and is a JSON object (`missing_final_submission`, `candidate_not_json`,
  `candidate_not_object`).
- Byte identity of every pristine file: `contract_file_modified`, `decoy_file_modified`, `other_file_modified`.

## Why each known-bad state is wrong

- `stale_runner_command.sh`: the old uv command from the backup profile. `runner_command_mismatch`.
- `use_bare_python_command.sh`: the bare `python` from the stale notes. `python_command_mismatch`.
- `wrong_workspace_root.sh`: the parent directory. `workspace_root_mismatch`.
- `invalid_environment_from_stale_note.sh`: classified invalid because `uv` is missing, which the
  contract's rule does not test. `runtime_classification_mismatch`.
- `contract_pin_rewritten.sh`: the pin is re-pointed at the backup so it appears to verify, and the
  contract file is edited. `contract_file_modified`.
- `truncated_submission.sh`: invalid JSON. `candidate_not_json`.
- `skip_submission.sh`: no submission. `missing_final_submission`.

## Careless controls

- `do_nothing.sh`: no submission. `missing_final_submission`.
- `fake_it.sh`: stale-note values. `python_command_mismatch`.
- `skip_check.sh`: the backup profile's command, with the pin never checked. `runner_command_mismatch`.
- `wrong_target.sh`: correct values in a scratch file. `missing_final_submission`.
- `half_done.sh`: no classification. `runtime_classification_mismatch`.

## Grader expectations

- Reference state: `passed: true`, `score: 1.0`.
- Untouched workspace: `passed: false`, with `missing_final_submission`.
