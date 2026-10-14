# Ceiling: manifest_repair (v2)

## What a perfect solution does

1. Reads the draft `release/manifest.json`. Keeps `project`, `release` and `maintainer`. Sets `status` to `ready`.
2. Keeps only the `release/` entries of the draft `files` list. The draft also names `notes/obsolete.md`, which is
   outside the release and must go. The result is three files in the contract order.
3. Drops `editor_notes` and `generated_by`. The manifest has exactly five keys.
4. Writes the summary line with the tracked count (3), and the checksum as the SHA-256 of the canonical JSON form,
   not of the file bytes.
5. Leaves `notes/` and `tmp/` exactly as they are.

`notes/RELEASE_CONTRACT_v1.md` is superseded. Its checksum rule (file bytes) and its "keep the draft's list" rule are
wrong for the 1.4 release. `notes/handoff.txt` describes the trim as wanted, which is consistent with the contract.

## Grader checks

- The manifest equals the contract object (`manifest_mismatch`, `manifest_not_json_object`, `missing_release_manifest`).
- The summary line matches (`summary_mismatch`, `missing_release_summary`).
- The checksum equals the canonical hash of the contract object, and of the repaired manifest (`checksum_file_mismatch`,
  `missing_release_checksum`).
- Every file outside `release/` keeps its pristine bytes. Stale notes are labelled `decoy_file_modified`, everything else
  `other_file_modified`.

## Why each known-bad state is wrong

- `checksum_of_file_bytes.sh`: follows the superseded v1 rule (`checksum_file_mismatch`).
- `draft_fields_kept.sh`: keeps the draft's extra keys (`manifest_mismatch`).
- `decoy_listed_in_manifest.sh`: keeps the stale `notes/obsolete.md` entry, so the count is wrong (`manifest_mismatch`,
  `summary_mismatch`).
- `decoy_file_edited.sh`: edits the stale handoff note (`decoy_file_modified`).
- `stale_summary_kept.sh`: summary keeps the draft's "pending review" line (`summary_mismatch`).

## Careless controls

- `do_nothing.sh`: draft left as is (`manifest_mismatch`).
- `fake_it.sh`: right shape, placeholder checksum (`checksum_file_mismatch`).
- `skip_check.sh`: trusts the v1 "keep the draft's files list" rule (`manifest_mismatch`).
- `wrong_target.sh`: writes to `staging/release/`, leaves `release/` as the draft (`manifest_mismatch`).
- `half_done.sh`: manifest and summary fixed, no checksum (`missing_release_checksum`).

## Grader expectations

- Reference state: `passed: true`, reason `manifest_ok`, `summary_ok`, `checksum_ok`, `out_of_scope_untouched`.
- Untouched workspace: `passed: false`, with `manifest_mismatch`, `summary_mismatch` and `checksum_file_mismatch`.
