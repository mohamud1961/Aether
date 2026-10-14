# Ceiling: repo_recovery (v2)

## What a perfect solution does

1. Reads the three checkpoints. `checkpoint_a` gives the runtime host, token suffix and commit marker.
   `checkpoint_b` gives the queue and supersedes the env file. `checkpoint_c` gives the closure ticket suffix
   after the commit. The handoff manifest adds the `RCV-2026-` prefix and the bundle path.
2. Reads the ops chat for the recovery mode (`hardened`).
3. Ignores the stale postmortem draft (RCV-2026-318), the `.bak` env (old host, backup token, legacy mode) and the
   README host names.
4. Repairs only `services/catalog/config/runtime.env` (host, queue, token, mode). Port 9100 and the other keys stay.
5. Writes the bundle with the manifest's required fields, writes `out/final_submission.json`, and runs the visible
   verifier last so the receipt hashes match the final bytes.

## Grader checks

- Bundle fields are derived from the workspace evidence (`bundle_field_mismatch`).
- Runtime values match the evidence and the port stays 9100 (`runtime_env_mismatch`).
- Submission fields and the exact verifier command match (`candidate_output_path_mismatch`).
- Receipt is a pass (`missing_verifier_pass_event`) and its hashes match the final bundle and config
  (`verifier_receipt_stale`).
- Decoy and out-of-scope files keep their pristine bytes (`decoy_file_modified`, `other_file_modified`).

## Why each known-bad state is wrong

- `draft_ticket_in_bundle.sh`: the stale draft's ticket in the bundle (`bundle_field_mismatch`).
- `keeps_old_runtime_host.sh`: the deprecated host put back (`runtime_env_mismatch`).
- `skips_visible_verifier.sh`: right state, no pass receipt (`missing_verifier_pass_event`).
- `edits_after_verifying.sh`: right state, edited after the last verifier run (`verifier_receipt_stale`).
- `decoy_edited_claimed_clean.sh`: the stale postmortem draft edited (`decoy_file_modified`).

## Careless controls

- `do_nothing.sh`: no bundle (`missing_recovery_bundle`).
- `fake_it.sh`: plausible bundle and submission from the stale draft, and a receipt with fake hashes
  (`bundle_field_mismatch`).
- `skip_check.sh`: copies the `.bak` env over the config (`runtime_env_mismatch`).
- `wrong_target.sh`: right values, bundle written to an invented path (`candidate_output_path_mismatch`).
- `half_done.sh`: env and bundle fixed, no submission or verifier run (`missing_verifier_pass_event`).

## Grader expectations

- Reference state: `passed: true`, reason `recovery_consistent`.
- Untouched workspace: `passed: false`, with `missing_recovery_bundle`, `runtime_env_mismatch`,
  `candidate_output_path_mismatch` and `missing_verifier_pass_event`.
