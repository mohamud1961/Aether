# Environment facts: first build slice

Objective: give the worker a bounded, accurately scoped first observation of
its task environment, then report observed changes during the run with one
Core-owned facts interface. The final objective is better completed work, not
a larger environment note. No live experiment or promotion is authorized by
this local implementation slice alone.

The first snapshot is a separate model-facing information item, not a change to
the system prompt or original task. It reports the probe shell's command
resolution, package-manager names,
up to 20 permitted non-hidden working-directory entries, tested host/port
connectivity, and the host-reported available memory when available. A
container's memory limit, a persistent terminal's PATH, installed package
contents, functionality, and later network state are not established by a
shared-probe snapshot. Missing, incomplete, timed-out or failed observations
remain unknown.

Automatic version execution is disabled in this slice: a task-provided
executable may do arbitrary work even when called with --version. Version
values remain unmeasured until an appropriately isolated measurement or an
actual task command provides evidence. If the existing Python REPL is
enabled, its already-executed Python 3 preflight can provide a version,
labelled as that preflight rather than proof of the later server binary.
The network probe uses fixed system
helper paths; if they are absent, the result is unknown.

After task actions, re-observe the inexpensive command-resolution and listing
fields; emit only changed or newly unknown fields. Refresh named-host
observations only at a declared interval or after likely
environment changes, and retain their measurement time rather than claiming
continuous freshness. Terminal-session PATH differs from the shared probe:
use the terminal's real completion receipt where available and explicitly
identify its session. Asynchronous changes after the final observation remain
unobserved; there is no completion hold. This bounded slice does not promise to
detect every external or transient change.

High-signal controls before integration:

1. Real local shell with a synthetic executable added/removed during a run:
   the next observation reports the change, and unchanged probes stay silent.
2. A named terminal with a changed PATH is not confused with the shared probe
   or another terminal. Failed/pending observations do not become facts.
3. Initial files are capped and untrusted names are filtered; protected paths,
   file contents and keys are not read. Symlinks and omissions are explicit.
4. Version/host/memory outputs have actual sources and unknown cases; local
   tests replace public host probes with an empty list or a localhost stub.
5. A real Core loop shows facts in a separate message or tool-result suffix,
   with no additional model call, unchanged task/system text and no hold.
6. Measured overhead and a recorded-request replay are required after
   integration; local synthetic tests cannot establish Luna task success.

Review points: arbitrary shell or Python can change state indirectly, so
lexical command classification is not complete; a fresh probe's PATH is not
automatically a named terminal's PATH. Do not claim a complete snapshot or
dependency graph. Any inherited flag retained for compatibility is listed
for review before removal, rather than silently deleting a supported path.
