# Task card: long_handoff_composition (v2)

Admission: **capability**. Reference, known-bad and careless controls test this v2 design. They do not establish
parity with the original trace contract.

## Design (v2)

- Multi-step chain: four dated handoff notes, read in order.
- Renamed artifact: `handoff-art-21` becomes `handoff-art-22` in note 2. The seed carries the new id.
- Stale note: note 3 is a deprecated publish flow that names the legacy path and its hash.
- Decoy artifact: a pre-rename archive and a legacy bundle, both id 21, each with its own hash. Their hashes are quoted in notes.
  The two are near-duplicates by content. A sha256 cannot be made visually similar without brute force, so the similarity is in content, not in the hash itself.
- Stale verifier record: `handoffs/archive/` holds a passing record for the legacy bytes.
- Continuity check: each handoff step must name the current id and no stale id.
- Checker hash in every record, so a hand-written pass record does not verify.

## Controls

- Known-bad: 7 scripts (`known_bad/`).
- Careless: 5 scripts (`careless/`), one per standard behaviour.

## Check disposition

| Grader reason | Controls |
|---|---|
| bundle_sha_mismatch | known_bad stale_hash |
| missing_verifier_pass_event | known_bad closed_without_verifier, stale_verifier_pass; careless fake_it |
| artifact_identity_lost | known_bad identity_from_intake_note; careless skip_check |
| candidate_bundle_path_mismatch | known_bad legacy_bundle_path; careless wrong_target |
| handoff_step_identity_mismatch | known_bad stale_id_in_steps |
| other_file_modified | known_bad tampered_checker |
| insufficient_handoff_steps | careless half_done |
| missing_final_submission | careless do_nothing |

Trace-dependent process checks are not established by this final-state grader.
