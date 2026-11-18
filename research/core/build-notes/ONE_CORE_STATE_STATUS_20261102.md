# One Core-managed state service: current status

The implementation is the single `Facts` service in Core's run session,
with helper modules for observation, workspace state, session rendering and
receipt comparison. The helpers are not separate models or agents. The
current runtime source is commit `f00307d5`; it remains isolated and is
selected with `AETHER_CORE_MANAGED_FACTS=on`, not enabled by default.

## What the service does

- Measures a bounded initial environment and workspace observation and
  refreshes its supported fields after tool actions, before the next model
  request. It labels the source, observation step and unknown cases.
- Records separate receipt-derived named-terminal and Python-session state,
  including a last observed working directory and an unknown current
  directory when a later command or cell is still running.
- Tracks bounded metadata of eligible workspace files, detects observed
  differences from the starting sample, and maintains a bounded record of
  tool-output and post-action workspace metadata digests. Recent records can
  be compared by call ID plus Core step, including in long runs.
- Preserves the initial workspace observation in supported in-process or
  trusted-pickle continuations when the observed workspace identity matches.
  It does not inspect Python variables or read task file contents to create
  default fingerprints.

## Limits that remain explicit

Observations are sampled, bounded and not atomic with background activity.
Hidden, protected, linked or external state, package behavior, Python
variables and unobserved processes are not fully visible. A metadata match is
not proof of unchanged contents, a correct test or task success. Symlinked
workspace roots and unavailable probes are reported as unmeasured. A change
first observed after Luna has already requested finish cannot reach that
decision without another model decision; this service does not veto finish.

## Qualification

The `f00307d5` runtime passed 52 provider-free host checks; the following
test-only parametrization independently passed both a symlink and a regular
directory replacement. A synthetic end-to-end pack passed all five artifact
and five state-sensor controls. A deliberately staged workspace-root swap
showed that the prior scanner incorrectly returned an observation for both
replacement types, while this version returns unknown for both. This check
reopens the path without following symlinks and verifies directory identity;
it does not make the observation atomic or monitor later changes. A further
direct REPL control verified that variables survive a removed working
directory even with the state service disabled.
The permitted 128-run trace replay completed, but the original machines and
file states were not restored. The prior Linux source passed 48 checks, but
the next Linux run exposed a directory-rename portability defect; that
failure is preserved. The corrected source's isolated Linux recheck did not
run: its guest was unresponsive, so the owned VM was stopped and removed.
The latest
completed Linux synthetic overhead screen on the prior source showed a 1.354
median request-character ratio on versus off; it does not measure actual
provider tokens, billing, Luna behavior or task success.

The candidate has not been independently reviewed or evaluated in matched
full Luna tasks. It is not yet qualified for shared default promotion, and
the separately recorded £5 all-in admission/accounting gate is not yet
qualified for paid runs. No external-state visibility should be inferred
from a local synthetic pass.

Exact Linux resumption point: after an owned, isolated Linux runtime can start
reliably, reseal the current `f00307d5` source and include both the previous
shell directory-identity controls and the new Python root-replacement
controls in the local Linux gate. The old `af548e05` archive is not the
current source. Preserve the failed and aborted attempts; do not treat the
macOS pass or an earlier Linux source as that result.
