# Repo Output Plan

Folder tree

```text
research/
  intake/
    inbox/
      bucket_runs/
        <run_date>__policy_program.json
        <run_date>__agent_architecture.json
        <run_date>__tooling_tool_gateway.json
        <run_date>__execution_control.json
        <run_date>__context_engineering.json
        <run_date>__state_management.json
        <run_date>__artifact_workspace.json
        <run_date>__memory.json
        <run_date>__verification_completion.json
        <run_date>__recovery_fault_tolerance.json
        <run_date>__observability_audit.json
        <run_date>__environment_substrate.json
        <run_date>__evals_benchmarking.json
        <run_date>__cost_token_management.json
      supplemental_runs/
        <run_date>__adversarial_robustness_anti_cheat_sweep.json
        <run_date>__context_compaction_handoff_sweep.json
        <run_date>__llm_native_harness_alignment_sweep.json
        <run_date>__problem_localization_exploration_strategy_sweep.json
        <run_date>__prompt_program_token_budget_sweep.json
        <run_date>__workflow_control_policy_sweep.json
        <run_date>__frontier_official_docs_sweep.json
      system_runs/
        <run_date>__dispatcher__dispatch_plan.json
        <run_date>__dedup__pass_<nn>.json
        <run_date>__qc__pass_<nn>.json
    records/
      <source_id>.json
    rejected/
      <run_date>__policy_program__rejections.json
      <run_date>__agent_architecture__rejections.json
      <run_date>__tooling_tool_gateway__rejections.json
      <run_date>__execution_control__rejections.json
      <run_date>__context_engineering__rejections.json
      <run_date>__state_management__rejections.json
      <run_date>__artifact_workspace__rejections.json
      <run_date>__memory__rejections.json
      <run_date>__verification_completion__rejections.json
      <run_date>__recovery_fault_tolerance__rejections.json
      <run_date>__observability_audit__rejections.json
      <run_date>__environment_substrate__rejections.json
      <run_date>__evals_benchmarking__rejections.json
      <run_date>__cost_token_management__rejections.json
      <run_date>__adversarial_robustness_anti_cheat_sweep__rejections.json
      <run_date>__context_compaction_handoff_sweep__rejections.json
      <run_date>__llm_native_harness_alignment_sweep__rejections.json
      <run_date>__problem_localization_exploration_strategy_sweep__rejections.json
      <run_date>__prompt_program_token_budget_sweep__rejections.json
      <run_date>__frontier_official_docs_sweep__rejections.json
      <run_date>__workflow_control_policy_sweep__rejections.json
      <run_date>__dedup__needs_manual_review.json
      <run_date>__qc__blocked.json
    normalized/
      manifests/
        <bucket_slug>__accepted.json
        corpus__deduped.json
      dedupe/
        <run_date>__dedupe_decisions.json
      capture/
        <run_date>__capture_backfill_report.json
      qc/
        <run_date>__qc_report.json
  sources/
    papers/
      <source_id>/
        artifact.pdf
        capture.json
    docs/
      <source_id>/
        artifact.html
        capture.json
    benchmarks/
      <source_id>/
        artifact.html
        capture.json
    codebases/
      <source_id>/
        artifact.bundle
        capture.json
    traces/
      <source_id>/
        artifact.tar.gz
        capture.json
    issues/
      <source_id>/
        artifact.html
        capture.json
    postmortems/
      <source_id>/
        artifact.html
        capture.json
```

Folder purpose

- `research/intake/inbox/bucket_runs/`: raw outputs from the 14 deep-research bucket prompts, one file per bucket prompt
- `research/intake/inbox/supplemental_runs/`: raw outputs from optional supplemental sweeps
- `research/intake/inbox/system_runs/`: raw outputs from dispatcher, dedup, and QC prompts
- `research/intake/records/`: one normalized metadata record per accepted `source_id`
- `research/intake/rejected/`: auditable near-miss, blocked, and manual-review outputs, never mixed with accepted records
- `research/intake/normalized/manifests/`: deduped accepted-source manifests for each bucket and one merged corpus manifest
- `research/intake/normalized/dedupe/`: duplicate resolution logs and canonicalization decisions
- `research/intake/normalized/qc/`: QC pass/fail reports and gate outcomes
- `research/intake/normalized/capture/`: artifact-capture backfill reports, replacement notes, and coverage counts
- `research/sources/*/<source_id>/`: downloaded or captured source artifacts grouped by artifact class, not by bucket

Write ownership

- Dispatcher: writes one raw dispatch file to `research/intake/inbox/system_runs/`
- Bucket source-finder: produces one raw JSON file saved to `research/intake/inbox/bucket_runs/`
- Supplemental source-finder: produces one raw JSON file saved to `research/intake/inbox/supplemental_runs/`
- Downloader or artifact capture worker: writes captured source files to `research/sources/<artifact_class>/<source_id>/`
- Dedup-and-normalization agent: writes one normalized record per accepted source to `research/intake/records/` and writes dedupe and manifests into `research/intake/normalized/`
- QC agent: writes QC report to `research/intake/normalized/qc/` and blocked items to `research/intake/rejected/`

File naming conventions

- Dispatcher raw output: `research/intake/inbox/system_runs/<run_date>__dispatcher__dispatch_plan.json`
- Raw bucket export: `research/intake/inbox/bucket_runs/<run_date>__<bucket_slug>.json`
- Raw supplemental sweep export: `research/intake/inbox/supplemental_runs/<run_date>__<sweep_slug>.json`
- Raw dedup output: `research/intake/inbox/system_runs/<run_date>__dedup__pass_<nn>.json`
- Raw QC output: `research/intake/inbox/system_runs/<run_date>__qc__pass_<nn>.json`
- Rejection log: `research/intake/rejected/<run_date>__<prompt_slug>__rejections.json`
- Dedupe manual-review log: `research/intake/rejected/<run_date>__dedup__needs_manual_review.json`
- Normalized record: `<source_id>.json`
- Bucket manifest: `<bucket_slug>__accepted.json`
- Corpus manifest: `corpus__deduped.json`
- Dedupe log: `<run_date>__dedupe_decisions.json`
- QC report: `<run_date>__qc_report.json`
- Capture backfill report: `<run_date>__capture_backfill_report.json`
- Artifact capture metadata: `capture.json`

`source_id` rules

- Format: `src_<class>_<hash12>`
- Allowed class codes:
  - `pap` paper
  - `doc` doc or engineering page
  - `bnm` benchmark source
  - `cod` repo or codebase
  - `trc` trace or run artifact
  - `iss` issue thread
  - `pmt` postmortem
- `hash12` is the first 12 lowercase hex chars of SHA-256 over the finalized canonical locator
- Canonical locator precedence:
  - DOI or arXiv ID plus version for papers if present
  - normalized canonical URL for docs and benchmark pages
  - `repo:<host>/<org>/<repo>` for repos
  - `issue:<host>/<org>/<repo>#<number>` for issue threads
  - `trace:<provider>/<benchmark>/<trial_or_run_id>` for traces
- Bucket names must never appear in `source_id`

Metadata to artifact linkage

- `research/intake/records/<source_id>.json` is the authoritative metadata record
- Each normalized metadata record adds `artifact_relpath`, for example `research/sources/docs/src_doc_a13f09b2c7de/`
- `research/sources/*/<source_id>/capture.json` stores:
  - `source_id`
  - `canonical_url`
  - `captured_at`
  - `fetch_method`
  - `artifact_files`
  - `content_hashes`

Rejected and deduped items

- Near-miss candidates stay in batch-local rejection files under `research/intake/rejected/`
- Ambiguous duplicate cases from dedup are stored in `research/intake/rejected/<run_date>__dedup__needs_manual_review.json`
- QC-blocked records append to `research/intake/rejected/<run_date>__qc__blocked.json`
- Duplicate resolution decisions are stored in `research/intake/normalized/dedupe/<run_date>__dedupe_decisions.json`
- Bucket manifests list only accepted canonical `source_id` values
- `corpus__deduped.json` is the only merged manifest used for later review and synthesis

Accepted source flow

1. Dispatcher output, if used, is saved first to `research/intake/inbox/system_runs/<run_date>__dispatcher__dispatch_plan.json`.
2. Each bucket source-finder emits raw JSON to `research/intake/inbox/bucket_runs/<run_date>__<bucket_slug>.json`.
3. Any supplemental sweep emits raw JSON to `research/intake/inbox/supplemental_runs/<run_date>__<sweep_slug>.json`.
4. Source-finder computes a best-effort provisional `source_id` from the best canonical locator visible at discovery time.
5. Dedup-and-normalization agent raw output is saved to `research/intake/inbox/system_runs/<run_date>__dedup__pass_<nn>.json`.
6. Dedup-and-normalization agent canonicalizes URL or locator, preserves that `source_id` when canonical identity is unchanged, or remaps it when canonical identity changes materially; then it writes `research/intake/records/<source_id>.json`, updates bucket manifests, and logs dedupe decisions.
7. Artifact capture worker downloads or snapshots the source into `research/sources/<artifact_class>/<source_id>/` and writes `capture.json`.
8. QC agent raw output is saved to `research/intake/inbox/system_runs/<run_date>__qc__pass_<nn>.json`.
9. QC agent validates schema, provenance, claim traceability, and bucket fit.
10. Merge step includes the `source_id` in `research/intake/normalized/manifests/corpus__deduped.json`.

Output files by prompt

- `prompts/dispatcher.md`
  - raw output: `research/intake/inbox/system_runs/<run_date>__dispatcher__dispatch_plan.json`
- `prompts/canonical_source_finder_template.md` + one file from `prompts/buckets/`
  - raw output: `research/intake/inbox/bucket_runs/<run_date>__<bucket_slug>.json`
  - rejection log if split out manually: `research/intake/rejected/<run_date>__<bucket_slug>__rejections.json`
- `prompts/canonical_source_finder_template.md` + `prompts/supplemental/frontier_official_docs_sweep.md`
  - raw output: `research/intake/inbox/supplemental_runs/<run_date>__frontier_official_docs_sweep.json`
  - rejection log if split out manually: `research/intake/rejected/<run_date>__frontier_official_docs_sweep__rejections.json`
- `prompts/canonical_source_finder_template.md` + `prompts/supplemental/workflow_control_policy_sweep.md`
  - raw output: `research/intake/inbox/supplemental_runs/<run_date>__workflow_control_policy_sweep.json`
  - rejection log if split out manually: `research/intake/rejected/<run_date>__workflow_control_policy_sweep__rejections.json`
- `prompts/canonical_source_finder_template.md` + `prompts/supplemental/llm_native_harness_alignment_sweep.md`
  - raw output: `research/intake/inbox/supplemental_runs/<run_date>__llm_native_harness_alignment_sweep.json`
  - rejection log if split out manually: `research/intake/rejected/<run_date>__llm_native_harness_alignment_sweep__rejections.json`
- `prompts/canonical_source_finder_template.md` + `prompts/supplemental/problem_localization_exploration_strategy_sweep.md`
  - raw output: `research/intake/inbox/supplemental_runs/<run_date>__problem_localization_exploration_strategy_sweep.json`
  - rejection log if split out manually: `research/intake/rejected/<run_date>__problem_localization_exploration_strategy_sweep__rejections.json`
- `prompts/canonical_source_finder_template.md` + `prompts/supplemental/prompt_program_token_budget_sweep.md`
  - raw output: `research/intake/inbox/supplemental_runs/<run_date>__prompt_program_token_budget_sweep.json`
  - rejection log if split out manually: `research/intake/rejected/<run_date>__prompt_program_token_budget_sweep__rejections.json`
- `prompts/canonical_source_finder_template.md` + `prompts/supplemental/context_compaction_handoff_sweep.md`
  - raw output: `research/intake/inbox/supplemental_runs/<run_date>__context_compaction_handoff_sweep.json`
  - rejection log if split out manually: `research/intake/rejected/<run_date>__context_compaction_handoff_sweep__rejections.json`
- `prompts/canonical_source_finder_template.md` + `prompts/supplemental/adversarial_robustness_anti_cheat_sweep.md`
  - raw output: `research/intake/inbox/supplemental_runs/<run_date>__adversarial_robustness_anti_cheat_sweep.json`
  - rejection log if split out manually: `research/intake/rejected/<run_date>__adversarial_robustness_anti_cheat_sweep__rejections.json`
- `prompts/dedup_normalization.md`
  - raw output: `research/intake/inbox/system_runs/<run_date>__dedup__pass_<nn>.json`
  - normalized writes: `research/intake/records/<source_id>.json`
  - dedupe log: `research/intake/normalized/dedupe/<run_date>__dedupe_decisions.json`
  - manual-review log: `research/intake/rejected/<run_date>__dedup__needs_manual_review.json`
  - manifests: `research/intake/normalized/manifests/<bucket_slug>__accepted.json`
  - merged corpus: `research/intake/normalized/manifests/corpus__deduped.json`
- `prompts/quality_control.md`
  - raw output: `research/intake/inbox/system_runs/<run_date>__qc__pass_<nn>.json`
  - QC report: `research/intake/normalized/qc/<run_date>__qc_report.json`
  - blocked items: `research/intake/rejected/<run_date>__qc__blocked.json`
- `prompts/fresh_readiness_run/10_local_capture_backfill_execution.md`
  - captured artifacts: `research/sources/<artifact_class>/<source_id>/`
  - capture metadata: `research/sources/<artifact_class>/<source_id>/capture.json`
  - accepted-record linkage updates: `research/intake/records/<source_id>.json`
  - run report: `research/intake/normalized/capture/<run_date>__capture_backfill_report.json`
  - blocked items: `research/intake/rejected/<run_date>__capture_backfill__blocked.json`

Examples for the 14 bucket agents

- Tooling output:
  - `research/intake/inbox/bucket_runs/2026-03-25__tooling_tool_gateway.json`
- Verification output:
  - `research/intake/inbox/bucket_runs/2026-03-25__verification_completion.json`
- Recovery output:
  - `research/intake/inbox/bucket_runs/2026-03-25__recovery_fault_tolerance.json`

Repo notes

- Use `research/sources/traces/` for new trace intake; existing `research/sources/trajectories/` can remain as legacy storage until migrated
- Use `research/sources/issues/` for new issue-thread intake; existing `research/sources/threads/` can remain as legacy storage until migrated
- Do not use bucket names as top-level directories
