# Task card: manifest_repair (v2)

Admission: **capability**. Reference, known-bad and careless controls test this v2 design. They do not establish
parity with the original trace contract.

## Design (v2)

- A draft manifest with extra keys and a stale tracked-file entry outside the release.
- A superseded v1 contract doc that describes a file-bytes checksum and keeping the draft's list.
- A handoff note that agrees with the 1.4 contract, plus an unrelated tmp file.
- Goal-level ticket prompt, with the output contract stated exactly.
- Out-of-scope files are sealed by pristine hash.

## Controls

- Known-bad: 5 scripts (`known_bad/`).
- Careless: 5 scripts (`careless/`), one per standard behaviour.

## Check disposition

| Grader reason | Controls |
|---|---|
| checksum_file_mismatch | known_bad checksum_of_file_bytes; careless fake_it |
| manifest_mismatch | known_bad draft_fields_kept, decoy_listed_in_manifest; careless do_nothing, skip_check, wrong_target |
| summary_mismatch | known_bad stale_summary_kept, decoy_listed_in_manifest |
| decoy_file_modified | known_bad decoy_file_edited |
| missing_release_checksum | careless half_done |

Trace-dependent process checks are not established by this final-state grader.
