# Historical state-service replay contract

Use 24 preselected, previously admitted development runs: the four smallest
run IDs from each of y12, y13, y14, y15, y17 and y18 in the frozen 128-run
manifest, SHA-256 `9759c8eac285fd5582206ed8d0852b38d4a0c24c00e87f7c85d1a40b64c2b025`.
The 44 previously excluded sensitive-family runs remain excluded. Source
paths must match the frozen manifest, permitted agent-log names and hashes;
no hidden tests, solutions, grader data, rewards or task artifacts are used.

The archive files have two hard links. Metadata inspection established that
the second link is the corresponding `step0_data/runs_mission` copy. The
reader must use read-only, no-follow opens, verify the expected same-inode
mirror, check size and modification metadata before and after reading, and
match the frozen digest. Any failure is an invalid row, not a retry or an
invitation to weaken the check. No archive data is written or copied into
the result; no recorded command is executed.

For each ordered historical tool event, call the actual Core facts service
with the captured action and result, but make all fresh environment and
process observations unknown: the original machines are not available.
Check that action receipts retain their correct step and output digest and
that unknown state is not reported as observed. Separately measure the
captured successful worker request-input character lengths and illustrate the
effect of fixed-size hypothetical notes. Those hypothetical ratios are a
context-size sensitivity analysis, not measured state-enabled overhead,
provider tokens, model behavior or task-success evidence.

After the initial 24-run sample contained no Python calls, the coverage
expansion was declared as every run in the same frozen 128-run manifest,
without selecting on outcome. The existing analysis reports Python activity
in ten of those runs. The same source checks and unknown-state limitations
apply; historical Python variables and interpreter state are not recreated.
