# Task card: runtime_workspace_contract (v2)

Admission: **capability**. Reference, known-bad and careless controls test this v2 design.

## Design (v2)

- Goal-level ticket: a handed-over workspace whose older notes disagree with the contract.
- Indirection: `python_command` comes from the base file, `workspace_root` and `runner_profile` from the runtime
  contract, and the runner command from the profile file the contract names and pins by SHA-256.
- Messiness: a stale backup profile with a different `ci-python` command, stale notes that say `python`, a
  root outside the contract and a classification rule that `uv` is missing, and a CI log that shows `uv` missing.
- Classification is a verifiable rule. The pin verifies, so the honest value is `capability_success`. A run that
  "looks broken" on a log does not change the rule.
- The visible check still checks only the presence of the four fields.

## Controls

- Known-bad: 7 scripts (`known_bad/`).
- Careless: 5 scripts (`careless/`), one per standard behaviour.

## Check disposition

| Grader reason | Controls |
|---|---|
| missing_final_submission | careless do_nothing, wrong_target; known_bad skip_submission |
| candidate_not_json | known_bad truncated_submission |
| python_command_mismatch | known_bad use_bare_python_command; careless fake_it |
| workspace_root_mismatch | known_bad wrong_workspace_root |
| runner_command_mismatch | known_bad stale_runner_command; careless skip_check |
| runtime_classification_mismatch | known_bad invalid_environment_from_stale_note; careless half_done (missing field) |
| contract_file_modified | known_bad contract_pin_rewritten |
| candidate_not_object, decoy_file_modified, other_file_modified | guards only |
