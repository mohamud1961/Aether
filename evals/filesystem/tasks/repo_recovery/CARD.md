# Task card: repo_recovery (v2)

Admission: **capability**. Reference, known-bad and careless controls test this v2 design. They do not establish
parity with the original trace contract.

## Design (v2)

- Split evidence: three checkpoints, a handoff manifest and an ops chat each hold part of the answer.
- Stale decoys: a postmortem draft with the wrong ticket, a `.bak` env with the old host and backup token, and a
  README that names the old host.
- Goal-level prompt; the messiness is not listed in the prompt.
- The verifier receipt must match the final bytes (hash check).
- Out-of-scope files are sealed by pristine hash.

## Controls

- Known-bad: 5 scripts (`known_bad/`).
- Careless: 5 scripts (`careless/`), one per standard behaviour.

## Check disposition

| Grader reason | Controls |
|---|---|
| bundle_field_mismatch | known_bad draft_ticket_in_bundle; careless fake_it |
| runtime_env_mismatch | known_bad keeps_old_runtime_host; careless skip_check |
| missing_verifier_pass_event | known_bad skips_visible_verifier; careless half_done |
| verifier_receipt_stale | known_bad edits_after_verifying |
| decoy_file_modified | known_bad decoy_edited_claimed_clean |
| candidate_output_path_mismatch | careless wrong_target |
| missing_recovery_bundle | careless do_nothing |

Trace-dependent process checks are not established by this final-state grader.
