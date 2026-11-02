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

The same Core facts service keeps the bounded metadata observed at step 0.
When a file from that observation later has different metadata, it records
and may display the first step where that difference was observed. This is
not a claim that file contents changed, that an edit was wrong, or that the
file was supplied by the task. If the initial scan was unavailable, it stays
unknown; a later observation cannot recreate it. An incomplete later scan
cannot establish that an initially observed path disappeared. Root identity
changes are never compared as if they were the same workspace.

Name filtering cannot establish that an innocently named file contains no
secret material. Fingerprinting reads eligible file bytes inside the task
environment, although only a digest is returned. This prototype has exercised
only synthetic files; before any live use the selected task pack and this
access policy require independent qualification against the no-keys rule.

For a safe workspace path literally mentioned in a terminal command or Python
cell, Core may fingerprint that file after the action. If its bytes later
change, Core can state that the command text mentioned that path and that the
post-action fingerprints differ. This is not proof that the command read the
file, that it ran a test, that the fingerprint describes what was read, or
that the task is correct. Unreadable, too large, changing-during-read or
excluded files are unknown. Keep the number and size of watched files bounded.

Only fixed system interpreter paths are candidates for the observer; never
execute an interpreter or utility selected from the task's PATH. The task
environment and its system binaries are still a trust boundary. If an
appropriate interpreter is unavailable, state remains unknown. Observations
are not atomic with arbitrary background activity. A change after Luna has
already decided to finish cannot be presented without another model decision;
this slice records it but does not block or rewrite that finish.

For model-managed context, the latest scoped facts are pinned separately from
the task and refreshed on an observed change. This prevents a checkpoint from
silently dropping the last fact, but does not make observations current after
unobserved changes or establish the model's use of them. Each raw tool result
has a bounded post-action observation receipt; it is not a snapshot of the
state that the tool necessarily read.

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
