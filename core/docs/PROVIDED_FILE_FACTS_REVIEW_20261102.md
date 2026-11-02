# Review of proposed provided-file observations

Claude's review of `research/core_mission_20261028/never/NEVER.md` raises a
useful hypothesis: when a run changes an input supplied at the beginning, a
later successful check may describe the altered input. The study also reports
completed solutions that invoke a provided executable. Those are possible
targets for a factual observation; neither is automatically a task failure.
The report itself says its 100 rows are 97 distinct runs, including a
fourfold duplicate, so its raw per-task totals are not all independent runs.
The hidden reason for a failed outcome is not established by either pattern.

The existing start-copy mechanism does not guarantee a usable immutable
manifest. It skips workspaces it cannot measure or those above 512 MiB. It
also tells the model that the harness does not use the copy, and the location
is available to the task. Reading it as a baseline would require changing
that statement and verifying its provenance and immutability. Recursively
hashing every file would also risk reading protected task files or keys; a
filename filter alone cannot make that safe.

Periodic process snapshots cannot reliably detect a short-lived child process
or establish its executable's origin. A verified parent/exec event could
support a narrower observation, but an unobserved process must remain
unknown. A green output from an executable is not proof that its input or
expectation is authoritative.

## Offline next step

First construct a small transparent task-facing fixture with explicit
known-good and known-bad artifacts. Include a task where an initially present
file should remain unchanged, one where modifying it is the correct action,
and a missing/incomplete-start-observation control. Check that any proposed
signal reports only its actual source and first observation step, does not
label permitted edits as wrong, and cannot turn an unavailable start state
into a clean baseline. A synthetic pass is only a sensor contract, not a
Luna task-success result. No general manifest or process monitor is promoted
from this case study alone.

A QEMU/process-lifetime check through Harbor is a separate substrate
experiment. A VM is not free merely because no model is called: its actual
runtime and infrastructure charges need to fit a sealed all-in budget, and
its exact runtime, process ownership and clean-up must be specified before
starting it. In-session observations do not by themselves prove what survives
the agent-to-verifier transition or explain a hidden grade.
