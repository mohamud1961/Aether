# Task: Patch the correct file in a decoy-heavy repo

You must fix one logic bug in the active reconcile pipeline.

The workspace includes stale docs and generated snapshots that look patchable.
Patch only the true target and provide `candidate/patch_manifest.json`.

Target clarification:
- authoritative code path is under `apps/ledger/src/`;
- do not patch `reconcile_old.py` or generated snapshot files.

Required manifest fields:
- `target_file`
- `changed_files`
- `verification_command`
- `verification_passed`

Do not submit if verification is not run against the active target path.
