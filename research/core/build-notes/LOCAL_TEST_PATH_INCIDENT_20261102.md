# Shared local history path used by a test

During the local CLM checkpoint test, the test configuration supplied a
private context-mirror path but inherited Core's default history path,
/tmp/.aether/ctx/HISTORY.txt. The synthetic test trace at 01:52 on 2 November
shows two checkpoint events, names that shared history path, and records no
history-save error. The history file's inode was created at 01:52:09. The
containing directory existed since 1 November at 23:44. This supports that
the test wrote the shared history file.

Whether a file existed at that path immediately before the write, and what it
contained, are unknown. Core's transfer code atomically replaces the target,
so a pre-existing file could have been overwritten. The existing shared file
has been left in place; its contents were not inspected for this incident.
The companion LIVE_CTX.txt was also present from an earlier local test period;
its prior state and ownership are unknown.

The new facts tests and the local overhead driver now set both the context
mirror and history path inside their private test directories. A rerun of
three CLM tests passed, and metadata for both shared files was unchanged
before versus after that rerun. This does not recover or establish any older
contents.

A metadata-only search found no adjacent history-named backup, and the local
snapshot listing for the root volume returned no entries. Other backups were
not checked; this does not prove recovery is impossible.

The broader Core suite contains other CLM configurations. Do not run the full
suite against the host's shared default paths. Use a separately qualified
isolated test tree/runtime with private paths, and report the isolation.

A macOS sandbox control blocked a write in an owned temporary directory and
allowed a separate owned write. However, the same sandbox refused to execute
/bin/ps even with an allow-default profile. Core's process-cleanup test fixture
requires ps, so a subsequent 32-test attempt failed during setup; no test body
ran. Shared context-file metadata remained unchanged. This is an isolation
environment failure, not a Core test pass or a Core regression.
