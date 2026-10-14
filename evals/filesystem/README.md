# Filesystem

Filesystem covers edits to a real directory tree: finding the right file among decoys, reading the true source of truth, and leaving every other file as it was.

The key lesson is about the base path. In a simplified-runtime screen, the first file read failed in every control trial and succeeded in every treatment trial. Path resolution set the result before any editing started.

Filesystem failures are silent. A patch to the nearest copy or the newest backup looks like progress and can pass a shape check. The tasks here check the file that the loader or contract names, and check that decoys are unchanged.

## Failure modes probed

- Following a pointer chain (manifest, profile, overlay) and taking the first match, not the effective value.
- Patching a decoy, a `.bak` copy or an archived layout that matches the search term.
- Editing files outside the scope, including decoys, to make a check pass.
- Claiming a verifier pass without a saved log that matches the final bytes.
- Rebuilding a repo from fragments that contradict each other.
- Writing a manifest or checksum from draft fields or an outdated contract.

## What the history taught

1. **Working directory is a capability, not a detail.** The filesystem and working-directory family scored 0/6 in the May 2026 diagnostic, the worst family measured.
2. **A path-base change can look like a capability gain.** In a later screen the first file read failed in every control and succeeded in every treatment. The difference was the default path, not the model.
3. **Decoys need scope checks.** Early decoy tasks checked only the target edit. The current tasks hash every other file, so an agent that also touches the decoy fails.

Every evaluation behind these lessons is listed in the catalogue.

## Current tasks

Validation key: known-bad files, each rejected with its expected reason; careless controls, each rejected; reference solvable from the workspace. All rows pass the grader gate.

| Task | Failure mode | What makes it hard | Validation | Admission |
|---|---|---|---|---|
| `decoy_target_selection` | Choosing the effective config value | Manifest, then profile, then overlay over a base file; the first `timeout:` line is wrong; stale README names another service; staging overlay already holds the target value | 7 known-bad; 5 careless; solvable | capability |
| `filesystem_verifier_repair` | Patching the file the loader reads | Start script and build file name the config; same-name docs snippet; `.orig` copy already has the target value; README names a missing file; verifier log must record a pass | 6 known-bad; 5 careless; solvable | capability |
| `manifest_repair` | Writing a manifest and summary from the output contract | Draft manifest with extra keys; stale tracked-file entry; superseded v1 doc describes a file-bytes checksum; handoff note agrees with the stale draft | 5 known-bad; 5 careless; solvable | capability |
| `repo_recovery` | Rebuilding a degraded repo from split evidence | Three checkpoints, a handoff manifest and a chat log each hold part of the answer; postmortem draft with the wrong ticket; `.bak` env with the old host; receipt must match final bytes | 5 known-bad; 5 careless; solvable | capability |

## Limits

The grader reads final bytes and checks that pristine inputs are unchanged. It does not see the order of edits. It confirms a visible check ran only where a log is required. The decoys are hand-built and few in number. The tasks do not measure how a solver explores a large, unfamiliar tree. The record holds no model result for these tasks.
