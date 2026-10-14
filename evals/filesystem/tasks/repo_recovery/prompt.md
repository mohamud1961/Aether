# Close out the catalog repo after the failed migration

The repository in the current directory was migrated twice. Since the last migration, the catalog
runtime config (`services/catalog/config/runtime.env`) no longer matches what is actually running,
and ops wants the repo closed out with evidence.

Your job:

1. Bring `services/catalog/config/runtime.env` in line with the current evidence. Keep keys that are
   not in dispute as they are.
2. Build the recovery bundle at the path the handoff manifest names. It must contain the bundle
   fields that the manifest requires, with values that agree with the current evidence and with the
   repaired config.
3. Write `out/final_submission.json`, a JSON object with these keys:
   - `output_path`: the bundle path, relative to the repo root.
   - `closure_ticket`
   - `runtime_host`
   - `queue_name`
   - `verifier_command`: the exact visible verifier command, which is
     `python3 scripts/verify_recovery.py --bundle artifacts/recovery/final/recovery_bundle.json --config services/catalog/config/runtime.env`
4. Run the visible verifier command. It writes `out/verifier_receipt.json` with SHA-256 hashes of the
   bundle and the config. If you change either file after the last passing run, run the verifier
   again so the receipt matches the final files.

Use only the files in this repository as evidence. Leave other files as they are.

Public dataset identifier: harness-evals-public-5abdf0eb5bb6f23d.
