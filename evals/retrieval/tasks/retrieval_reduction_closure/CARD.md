# Task card: retrieval reduction closure (v2)

Admission: **capability**. Reference, known-bad and careless controls test this v2 design. They do not establish
parity with the original trace contract.

## Design (v2)

- Index hop: `data/index.json` lists the shards for one batch. Evidence order is shard order, then file order.
- Revision supersession: the current row per line is the highest revision. Rows marked `active` can still be stale.
- Noise: a lagging mirror, an archive export, a log, a draft note with a stale total, and a row from another batch.
- Shape-only visible check. The grader seals the expected IDs, scalar, and hashes of all inputs under data/, docs/, checks/.

## Controls

- Known-bad: 7 scripts (`known_bad/`).
- Careless: 5 scripts (`careless/`), one per standard behaviour.

## Check disposition

| Grader reason | Known-bad / careless controls |
|---|---|
| missing_candidate | careless do_nothing, wrong_target |
| final_value_mismatch | known_bad stale_scalar, active_status_only, mirror_copy_value; careless fake_it, skip_check |
| evidence_ids_mismatch | known_bad active_status_only, drop_active_evidence_id |
| stale_ids_mismatch | known_bad omit_stale_rejections |
| justification_missing | known_bad missing_stale_justification |
| justification_trace_invalid | careless half_done |
| input_file_modified | known_bad edited_input_row |

Trace-dependent process checks are not established by this final-state grader. 