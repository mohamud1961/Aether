# Task card: decoy target selection (v2)

Admission: **capability**. Reference, known-bad and careless controls test this v2 design. They do not establish
parity with the original trace contract.

## Design (v2)

- Two-hop resolution: `deploy_manifest.json` -> `profiles/*.json` -> `services/<svc>/overrides/<env>.yaml`
  over `base.yaml`. The effective value is the overlay's timeout, not the first `timeout:` line found.
- Decoys: a stale README naming alpha, a superseded manifest naming gamma, a `base.yaml.bak`, a staging overlay
  that already holds 300, and a second production profile (us-east, alpha).
- The visible check still checks shape only.

## Controls

- Known-bad: 7 scripts (`known_bad/`).
- Careless: 5 scripts (`careless/`), one per standard behaviour.

## Check disposition

| Grader reason | Controls |
|---|---|
| candidate_target_mismatch | known_bad patch_old_manifest_service; careless skip_check, wrong_target |
| effective_timeout_mismatch | known_bad patch_base_instead, wrong_timeout_value; careless fake_it, half_done |
| missing_final_submission | careless do_nothing, half_done |
| missing_verifier_pass_event | known_bad omit_verifier_command |
| target_collateral_edit | known_bad collateral_edit_in_target |
| decoy_file_modified | known_bad decoy_changed_claimed_untouched |
| other_file_modified | known_bad tampered_visible_check |
| candidate_effective_timeout_mismatch, candidate_decoy_claim_missing, missing_target_file | guards only, no dedicated control |

Trace-dependent process checks are not established by this final-state grader.
