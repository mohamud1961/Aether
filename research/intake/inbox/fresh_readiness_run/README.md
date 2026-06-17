# Fresh Readiness Run Outputs

This folder is the dedicated landing zone for the fresh-readiness repair run.

Why this exists

- The prompts under `research/source_finder_prompt_pack/prompts/fresh_readiness_run/` now have explicit output files.
- This avoids the situation where prompts exist but no obvious output destination exists.
- It also gives one place to review the entire repair cycle.

Recommended usage

1. Run `01` through `05` with web-based research agents and save their outputs here.
2. Run `06` through `09` only with a repo-context agent and save those outputs here too.
3. Update `2026-03-30__fresh_readiness_run_manifest.json` as each prompt is completed.
4. After the run is complete, promote bucket-like raw JSON outputs into the standard intake flow if needed:
   - `research/intake/inbox/bucket_runs/`
   - `research/intake/inbox/system_runs/`
   - `research/intake/normalized/`
5. Keep repo-access audit/synthesis outputs here until they are either promoted into `research/analysis/` or explicitly rejected.

Files

- `2026-03-30__fresh_readiness_run_manifest.json`: run-level tracker for the whole repair cycle
- `2026-03-30__fresh_readiness_run_combined.md`: optional single-file destination for the full run
- Web-agent outputs:
- `2026-03-30__artifact_workspace_repair.json`
- `2026-03-30__observability_audit_repair.json`
- `2026-03-30__environment_substrate_repair.json`
- `2026-03-30__evals_benchmarking_repair.json`
- `2026-03-30__cost_token_management_repair.json`
- Repo-context outputs:
- `2026-03-30__local_capture_backfill_audit.md`
- `2026-03-30__cross_system_trajectory_gap_fill.md`
- `2026-03-30__top_level_synthesis_promotion.md`
- `2026-03-30__exit_gate_recheck.md`

If you prefer one single file

- Use `2026-03-30__fresh_readiness_run_manifest.json` as the top-level tracker.
- Use `2026-03-30__fresh_readiness_run_combined.md` as the single place to paste the actual outputs.
- Keeping each prompt's real output in its own file is still cleaner and easier to audit.
