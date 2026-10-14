# Task card: delegation fidelity (v2)

Admission: **capability**. The grader is standalone stdlib code that reads JSON, and it runs no candidate code. The reference, known-bad
and careless controls test this v2 design. This task is new in v2; there is no archived parity claim.

## Design (v2)

- A request thread in time order, with three kinds of change. A conflicting ask (format v1 vs v2; live database vs frozen snapshot) is
  settled by a later decision. A retraction (PII redaction) is withdrawn by its author. A constraint that applies to every worker
  (vendor/ is off limits) is in a reply, not the main message.
- Tags: `[C-xx]` live, `[R-xx]` retracted, `[X-xx]` superseded. Only live tags go into packets.
- An exact packet schema in `specs/packet_schema.json`. A stale README template adds `deadline` and `constraints` fields.
- Worker results: one stale (packet version 1 against a current version 2). The merge rules say to reject it.
- The visible check tests key types only.

## Controls

- Known-bad: 6 scripts (`known_bad/`), run after the reference.
- Careless: 5 scripts (`careless/`), one per standard behaviour. They do not use `$TASK_ROOT`.

## Check disposition

| Grader reason | Controls |
|---|---|
| retracted_constraint_present | known_bad kb_keeps_retracted_redaction, kb_live_db_reconcile; careless skip_check |
| live_constraint_missing | known_bad kb_drops_vendor_rule |
| stale_result_accepted | known_bad kb_accepts_stale |
| packet_schema_mismatch | known_bad kb_extra_packet_key |
| vendor_modified | known_bad kb_vendor_edit |
| constraint_misassigned | careless fake_it |
| missing_packets | careless do_nothing, wrong_target |
| missing_merged | careless half_done |
| packet_version_mismatch, merge_mismatch, duplicate_packet, unexpected_packet, input_modified, *_unparseable | guards, no dedicated control |
