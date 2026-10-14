# Fleet config ops runbook

- The operations log is rotated by the log shipper. The live file is `ops/opslog.1.log`; older
  rotations are `ops/opslog.2.log` to `ops/opslog.4.log`, and the oldest one is compressed.
  Read them newest first (1 to 4) to rebuild the current state.
- Checkpoints are written on the hour by the on-call bot (C1 to C5 in a normal week).
- A `dry_run=true` set is a preview from the config UI. It does not reach the fleet.
- The dashboard export refreshes nightly at 02:00 UTC.
