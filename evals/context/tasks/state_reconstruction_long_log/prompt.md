# Rebuild the fleet config as it stands now

The ingest fleet's config has been changed for several weeks through its operations log, and the
log has been rotated more than once. On-call needs the exact configuration the fleet is running
right now, plus the settings that differ from checkpoint `C3`, the last snapshot before the
incident.

The operations log is in `ops/`. Every file there is part of the log, and their names do not
reflect the order of events. The handoff note in `ops/handoff/`, the dashboard export in
`dashboard/` and the runbook in `docs/` were written at other times and may not match the log.

How the log works:

- Each line is a set of `key=value` tokens. `seq` orders events across all files, and `ts` is
  wall-clock time for reading only.
- Only lines with `kind=cfg` change configuration. Other kinds are monitoring noise.
- `op=set` changes `key` to `value`, but only when `status=applied` and the line is not marked
  `dry_run=true`.
- `op=checkpoint name=Cn` records a snapshot of every key's effective value at that point.
- `op=rollback to=Cn` restores every key to its value in snapshot `Cn`. Changes applied between
  `Cn` and the rollback are discarded. Changes after the rollback apply as usual.
- Values are plain strings. Record them exactly as logged.

Write these two files (create `out/` if needed):

1. `out/final_state.json`: a JSON object with one entry for every fleet config key that the log
   sets, mapping each key to its effective value at the end of the log, as a string.
2. `out/changed_since_c3.json`: a JSON object `{"changed_keys": [...]}` listing, sorted ascending,
   the keys whose final value differs from their value in snapshot `C3`.

Rules:

- Write only inside `out/`. Do not edit the log, the handoff note, the dashboard export, the
  runbook or anything else in the workspace.
- `python3 checks/shape_check.py` run from the workspace root confirms that the two files parse
  and have the right top-level types. It does not check values.
