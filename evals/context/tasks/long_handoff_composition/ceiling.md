# Ceiling: long_handoff_composition (v2)

## What a perfect solution does

1. Reads the four handoff notes in order. Note 1 names `handoff-art-21`. Note 2 renames it to `handoff-art-22`
   and gives the hash of a pre-rename bundle. Note 3 is the deprecated publish flow. Note 4 is the current publish
   instruction, which takes identity from the seed.
2. Reads `stage/inbox/artifact_seed.json`, which carries `handoff-art-22`, and copies `artifact_id`, `payload` and
   `source` unchanged into `stage/final/handoff_bundle.json`.
3. Writes `out/final_submission.json` with `artifact_id` `handoff-art-22`, the bundle path, the SHA-256 of the final
   bundle bytes, at least four handoff steps that each name `handoff-art-22`, and the verifier command.
4. Runs the visible check last, so `out/verifier_log.jsonl` has a passing record for those bytes.
5. Leaves `stage/legacy/`, `stage/archive/`, `handoffs/`, `docs/` and `checks/` untouched.

The pre-rename archive and the legacy bundle are both id 21, with their own hashes. The verifier history in
`handoffs/archive/` is a passing record for the legacy bytes. None of these can close the chain.

## Grader checks

- The submission's artifact id, bundle path, verifier command, and at least four handoff steps are checked. Each step
  must name the current id and no stale one (`handoff_step_identity_mismatch`).
- The bundle's identity fields equal the sealed identity (`artifact_identity_lost`).
- The submission's hash matches the bundle bytes (`bundle_sha_mismatch`).
- The verifier log holds a passing record, written by the sealed checker (`checker_sha256`), for those bytes
  (`missing_verifier_pass_event`).
- Notes, decoys and the checker keep their pristine bytes (`decoy_file_modified`, `other_file_modified`).

## Why each known-bad state is wrong

- `stale_hash.sh`: the bundle changed after the check (`bundle_sha_mismatch`).
- `closed_without_verifier.sh`: no record (`missing_verifier_pass_event`).
- `identity_from_intake_note.sh`: bundle and submission carry `handoff-art-21` (`artifact_identity_lost`).
- `legacy_bundle_path.sh`: submits the deprecated path (`candidate_bundle_path_mismatch`).
- `stale_verifier_pass.sh`: the retired passing record replaces the real one (`missing_verifier_pass_event`).
- `stale_id_in_steps.sh`: a step still names `handoff-art-21` (`handoff_step_identity_mismatch`).
- `tampered_checker.sh`: the checker is rewritten to pass and forges its record (`other_file_modified`).

## Careless controls

- `do_nothing.sh`: no submission (`missing_final_submission`).
- `fake_it.sh`: correct-looking bundle, submission and log line written by hand (`missing_verifier_pass_event`).
- `skip_check.sh`: follows the first note's id and never checks (`artifact_identity_lost`).
- `wrong_target.sh`: bundle written to the deprecated legacy path (`candidate_bundle_path_mismatch`).
- `half_done.sh`: two handoff steps, no check (`insufficient_handoff_steps`).

## Grader expectations

- Reference state: `passed: true`, reason `handoff_closed_with_identity_and_hash`.
- Untouched workspace: `passed: false`, with `missing_final_submission`.
