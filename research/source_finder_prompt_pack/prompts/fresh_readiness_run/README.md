# Fresh Readiness Run

This folder is for a targeted second-pass repair run, not broad intake.

Important execution model

- `01` through `05` are for web-based source-finder agents with no repo context.
- `06` through `10` are not web-research prompts. They are local follow-up tasks for a repo-context agent that can inspect this repository.
- Do not send repo-local mining or synthesis prompts to a web-only research agent.

Use it when the corpus has obvious weak spots, empty manifests, malformed artifacts, missing local captures, or stranded synthesis.

What this run is meant to fix

- empty or weak bucket coverage for artifact workspace, observability, environment substrate, evals, and cost/token management
- missing local-capture linkage for accepted sources
- unprocessed local trajectory/codebase evidence outside BigAI
- failure and design synthesis that is still stranded below `research/analysis/`

Run order

1. For `01` through `05`, paste `prompts/canonical_source_finder_template.md` followed by exactly one fresh bucket-repair prompt into a web-based source-finder agent.
2. Save raw outputs under `research/intake/inbox/bucket_runs/` or `research/intake/inbox/supplemental_runs/` with a fresh date prefix.
3. Run normalization and QC before treating those outputs as real coverage.
4. Run `06` through `10` only with a repo-access agent that can inspect local files and write local outputs.
5. Re-run the exit-gate review only after the repaired artifacts exist.

Non-negotiable quality rules

- Never invent titles, URLs, org names, metrics, or source claims.
- `canonical_url` must be a raw absolute URL string, never markdown like `[label](url)`.
- Placeholder domains such as `example.com` are invalid evidence and must be rejected.
- If a source cannot be given a reproducible locator, reject it instead of padding the corpus.
- Prefer fewer strong sources over filler.

Prompt map

- Web-only source-finder prompts:
- `01_artifact_workspace_repair.md`
- `02_observability_audit_repair.md`
- `03_environment_substrate_repair.md`
- `04_evals_benchmarking_repair.md`
- `05_cost_token_management_repair.md`
- Repo-context follow-up prompts:
- `06_local_capture_backfill_audit.md`
- `10_local_capture_backfill_execution.md`
- `07_cross_system_trajectory_gap_fill.md`
- `08_top_level_synthesis_promotion.md`
- `09_exit_gate_recheck.md`
