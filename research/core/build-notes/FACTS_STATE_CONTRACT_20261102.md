# Workspace state and observation linkage: local qualification contract

The purpose is to make a task-relevant change available before Luna's next
decision, while reporting only what Core actually observed. This is an
offline prototype, not a claim that every machine state is visible.

After each tool action, inspect a bounded set of allowed workspace entries in
the task environment. Report observed file additions, removals and metadata
changes with their observation step. A scan may be incomplete because of
coverage limits, permissions, protected names, symlinks, hard links or a
missing observer; incomplete and failed scans must not be called unchanged.
Never open hidden task tests, solutions, verifier or grader paths, key files,
linked files, or paths outside the task workspace. Output names must be safe
for display and capped.

The workspace root is opened one path component at a time with no-follow
directory descriptors, so an ancestor symlink does not redirect the bounded
metadata scan. A root that cannot be verified this way is unmeasured. The
separate shell listing also checks ancestor links, but its checks and listing
are not atomic against a concurrent adversarial filesystem change.

The same Core facts service keeps the bounded metadata observed at step 0.
When a file from that observation later has different metadata, it records
and may display the first step where that difference was observed. This is
not a claim that file contents changed, that an edit was wrong, or that the
file was supplied by the task. If the initial scan was unavailable, it stays
unknown; a later observation cannot recreate it. An incomplete later scan
cannot establish that an initially observed path disappeared. Root identity
changes are never compared as if they were the same workspace.

Workspace probes reject filesystem-root aliases such as `//`, as well as
symlinked root ancestors. A rejected root yields an incomplete observation,
not a listing of the host root or a claim that its contents are absent.
The shell's root-entry listing runs from an opened current directory after
checking its physical name, rather than expanding the original path after a
separate symlink check. If the configured root is replaced by a symlink in
between, or moved while it is being listed, the buffered listing is discarded
and the observation is incomplete. The probe compares directory identities
as well as physical path strings, because some shells cache a moved path.
If the identity comparison is unsupported, the observation is incomplete.
This is a bounded sandbox observation,
not a defense against every possible privileged filesystem or mount change.

Name filtering cannot establish that an innocently named file contains no
secret material. For that reason, the normal Core service does not read file
contents to make fingerprints; it reports only bounded metadata changes. A
lower-level fingerprint prototype remains directly selectable only in
synthetic, explicitly key-free tests and is not exposed through the Harbor
configuration. A content change therefore remains unestablished by normal
state observations, even if metadata differs.

Only fixed system interpreter paths are candidates for the observer; never
execute an interpreter or utility selected from the task's PATH. The task
environment and its system binaries are still a trust boundary. If an
appropriate interpreter is unavailable, state remains unknown. Observations
are not atomic with arbitrary background activity. A change after Luna has
already decided to finish cannot be presented without another model decision;
this slice records it but does not block or rewrite that finish.

A terminal working directory is labeled as the last completion receipt,
not as a live measurement. If another command is still running, Core marks
the current working directory unknown until a later observation.
The Python REPL likewise reports the directory already recorded in its last
cell completion receipt, without inspecting variables. A running or exited
cell leaves the current directory unknown; a restarted REPL begins without
the previous process's directory observation.
If a cell removes or loses access to its current directory, an unavailable
`getcwd` is recorded as unknown without discarding the completed cell or
terminating the REPL; a later cell can restore an accessible directory.

For model-managed context, the latest scoped facts are pinned separately from
the task and refreshed on an observed change. This prevents a checkpoint from
silently dropping the last fact, but does not make observations current after
unobserved changes or establish the model's use of them. Each raw tool result
has a bounded post-action observation receipt; it is not a snapshot of the
state that the tool necessarily read.

Core can compare a retained tool call's post-action workspace metadata sample
with its latest sample. The service returns `sample_matches`, `sample_differs`,
or `unknown` with observation steps and coverage; it also records the most
recent eight comparisons in the run's Core facts record. An unavailable
observation, missing or duplicate call ID, or truncated receipt history is
unknown when queried by call ID alone. After older receipts are evicted,
retained recent calls can still be addressed by both call ID and Core's
strictly increasing observation step; an out-of-order step invalidates that
disambiguation. Evicted calls stay unknown. Matching samples do not establish
that contents or the wider environment were unchanged, and differing samples do not establish whether a
test is valid or a task is wrong. These comparisons are available to Core and
the run record; they are not automatically presented to Luna as warnings.

When Core continues a copied CLM context produced with this prototype, it
refreshes the pinned observation identified by that context's private index
instead of appending a second, conflicting state note. The index is not
inferred from the contents of task text. Older or externally modified
contexts without that provenance have not been qualified for this behavior.
For an in-process project-context fork, a private string type identifies the
Core-owned note across the copy; ordinary user text is not eligible for
replacement. The Core-owned note carries the bounded initial metadata in
private in-process state and in the existing trusted pickle checkpoint, not
in the model-facing text. On continuation Core re-observes the workspace:
only an observed matching root identity permits comparison with the earlier
baseline. A different root gets a new continuation baseline; an unmeasured
root leaves the relationship unknown. New differences are labeled with the
continuation number and observation step. Root identity and metadata are not
proof of file content or semantic correctness.

A JSON-deserialized or externally constructed history loses that private
provenance and has not been qualified for automatic refresh. The service does
not restore live Python variables, shell processes or external services from
the checkpoint. Do not deserialize untrusted pickle files.

Required falsifiers: actual workspace replacement, unchanged-content touch,
unrelated file, two versions of a mentioned file, unsafe symlink and
protected-path canaries, observer outage, an action with no changes, and a
background change before a read-only tool response. Then exercise the actual
Core loop, inspect model-facing requests, measure overhead, and compare on
real tasks before drawing any task-success conclusion.
