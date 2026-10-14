# Close the handoff chain for the current artifact

An artifact has moved through several handoffs. The notes are in `handoffs/`, in date order, and
`stage/inbox/artifact_seed.json` is the seed. You are in the workspace root (the current directory).

Close the chain. Build the final bundle for the artifact as it stands now, write a submission that
records it, and run the visible check so there is a verified record for the final bytes.

Rules:

- The artifact's `artifact_id`, `payload` and `source` must survive the handoff unchanged. Use the
  identity the artifact carries now.
- Each entry in `handoff_steps` must name the artifact id you carried forward, and must not name any id
  the artifact no longer uses.
- Do not write to `stage/legacy/`, `stage/archive/`, `handoffs/` or `docs/`.
- If you change the bundle after a check, run the check again.

Outputs:

1. `stage/final/handoff_bundle.json`: a JSON object with `artifact_id`, `payload` and `source`.
2. `out/final_submission.json`: a JSON object with `artifact_id`, `bundle_path`
   (`stage/final/handoff_bundle.json`), `bundle_sha256` (the SHA-256 of the final bundle bytes),
   `handoff_steps` (at least four non-empty strings), and `verifier_command`
   (`python3 checks/visible_check.py --candidate out/final_submission.json`).
3. Run the visible check with that command, so `out/verifier_log.jsonl` records a passing run for the
   bundle bytes as they stand when you finish.

Public dataset identifier: harness-evals-public-77f291c71268a069.
