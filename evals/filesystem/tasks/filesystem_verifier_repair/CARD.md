# Task card: filesystem_verifier_repair (v2)

Admission: **capability**. Reference, known-bad and careless controls test this v2 design. They do not establish
parity with the original trace contract.

## Design (v2)

- Two-hop resolution: `app/bin/start.sh` default and `app/build.json` name the loaded config.
- Decoys: a docs snippet with the same file name, a `.orig` copy already at the target value, an archived layout.
- Stale docs: the README names `app/service.yaml`, which does not exist.
- Verifier evidence: the saved log must record a passing run.
- The visible check still checks shape only.

## Controls

- Known-bad: 6 scripts (`known_bad/`).
- Careless: 5 scripts (`careless/`), one per standard behaviour.

## Check disposition

| Grader reason | Controls |
|---|---|
| candidate_target_mismatch | known_bad patch_decoy_not_target, patch_orig_copy; careless skip_check, wrong_target |
| decoy_file_modified | known_bad decoy_edited_claimed_clean |
| missing_verifier_log | known_bad no_verifier_log |
| target_collateral_edit | known_bad collateral_edit_in_target |
| other_file_modified | known_bad tampered_visible_check |
| effective_retries_mismatch | careless fake_it; known_bad patch_orig_copy |
| missing_final_submission | careless do_nothing, half_done |

Trace-dependent process checks are not established by this final-state grader.
