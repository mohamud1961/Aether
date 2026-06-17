# Operator Runbook

This runbook is for a human operator running web-based deep research agents that have no repo access.

## Core Rule

Never send a bucket prompt by itself.

For each source-finder run, send one combined prompt made from:

1. `prompts/canonical_source_finder_template.md`
2. exactly one file from `prompts/buckets/`

The agent only knows what you paste into the prompt.

## Files You Use

Read these once before starting:

- `README.md`
- `repo_output_plan.md`
- `shared_json_schema.json`
- `global_quality_gate_checklist.md`
- `merge_protocol.md`

Use these during execution:

- `prompts/dispatcher.md`
- `prompts/canonical_source_finder_template.md`
- one file from `prompts/buckets/`
- optional file from `prompts/supplemental/`
- `prompts/dedup_normalization.md`
- `prompts/dedup_normalization_repo_access.md`
- `prompts/quality_control.md`

## Bucket Order

Run buckets in this order:

1. `policy_program`
2. `tooling_tool_gateway`
3. `execution_control`
4. `context_engineering`
5. `state_management`
6. `verification_completion`
7. `recovery_fault_tolerance`
8. `observability_audit`
9. `agent_architecture`
10. `artifact_workspace`
11. `environment_substrate`
12. `evals_benchmarking`
13. `cost_token_management`
14. `memory`

This order front-loads the harness decisions that most strongly shape later intake.

## Step-by-Step Procedure

### Phase 0: One-Time Setup

1. Read `README.md` to confirm the folder layout.
2. Read `repo_output_plan.md` to understand where outputs go.
3. Read `shared_json_schema.json` so you can spot malformed outputs quickly.
4. Read `global_quality_gate_checklist.md` so you know what will fail QC.
5. Keep the bucket order list visible while running the process.

### Phase 1: Run the First 6 Buckets

For each bucket in steps 1 through 6 of the bucket order:

1. Open `prompts/canonical_source_finder_template.md`.
2. Open the matching bucket file in `prompts/buckets/`.
3. Copy the full canonical template.
4. Paste the full bucket prompt directly under it.
5. Submit that combined prompt to the web research agent.
6. Save the raw JSON output to:
   `research/intake/inbox/bucket_runs/<run_date>__<bucket_slug>.json`
7. If the agent returns non-JSON, malformed JSON, or padded weak sources, rerun immediately.

### Phase 2: First Dedup Pass

After the first 6 bucket runs are saved:

1. Open `prompts/dedup_normalization.md`.
2. Paste the full prompt into the dedup agent.
3. Paste the raw outputs from the first 6 buckets below it.
4. Run dedup and normalization.
5. Save the raw dedup agent output to:
   `research/intake/inbox/system_runs/<run_date>__dedup__pass_01.json`
6. Save the normalized results to:
   - `research/intake/records/<source_id>.json`
   - `research/intake/normalized/dedupe/<run_date>__dedupe_decisions.json`
   - `research/intake/rejected/<run_date>__dedup__needs_manual_review.json` if the dedup output contains unresolved cases
   - `research/intake/normalized/manifests/<bucket_slug>__accepted.json`

Do this early so `source_id` drift is controlled before the full corpus grows.

Important:

- The external agent will usually return one large JSON object in chat.
- That is expected.
- The operator must save that JSON object into the raw dedup file and then split its fields into the downstream files.

### Phase 3: Run the Remaining 8 Buckets

For buckets 7 through 14:

1. Repeat the same combined-prompt process:
   canonical template first, bucket prompt second.
2. Save each raw JSON output to:
   `research/intake/inbox/bucket_runs/<run_date>__<bucket_slug>.json`
3. Reject and rerun immediately if the agent pads weak sources instead of returning `insufficient_high_quality_sources_found`.

### Phase 4: Full Dedup Pass

After all bucket runs are complete:

1. Run `prompts/dedup_normalization.md` again.
2. Paste all raw bucket outputs plus any already-normalized records.
3. Save updated normalized records, dedupe decisions, and manifests.
   Save `research/intake/rejected/<run_date>__dedup__needs_manual_review.json` too if the dedup output contains unresolved cases.
4. Save the raw dedup agent output to:
   `research/intake/inbox/system_runs/<run_date>__dedup__pass_02.json`
5. Treat `research/intake/normalized/manifests/corpus__deduped.json` as the candidate merged corpus, not the final corpus yet.

### Optional Phase 4.5: Frontier Official Docs Sweep

Run this only after the first full 14-bucket sweep and first full dedup pass.

1. Open `prompts/canonical_source_finder_template.md`.
2. Open `prompts/supplemental/frontier_official_docs_sweep.md`.
3. Paste the canonical template first and the supplemental prompt second into one prompt.
4. Run the sweep.
5. Save the raw JSON output to:
   `research/intake/inbox/supplemental_runs/<run_date>__frontier_official_docs_sweep.json`
6. Run dedup again so any new official-doc sources merge into the same corpus.
7. Save that raw dedup agent output to:
   `research/intake/inbox/system_runs/<run_date>__dedup__pass_03.json`

Why here:

- By this point you already know what the main bucket sweep found.
- The supplemental sweep can then fill official-doc coverage gaps without distorting the primary bucket search.
- This keeps the 14-bucket workflow primary and uses the docs sweep as targeted supplementation.

### Phase 5: Artifact Capture

For each accepted `source_id` in the deduped manifests:

1. Download or snapshot the source artifact.
2. Store it under the matching lifecycle folder:
   - `research/sources/papers/<source_id>/`
   - `research/sources/docs/<source_id>/`
   - `research/sources/benchmarks/<source_id>/`
   - `research/sources/codebases/<source_id>/`
   - `research/sources/traces/<source_id>/`
   - `research/sources/issues/<source_id>/`
   - `research/sources/postmortems/<source_id>/`
3. Write `capture.json` in that folder.

If you are using a repo-access agent to do this systematically:

1. Run `prompts/fresh_readiness_run/10_local_capture_backfill_execution.md`
2. Have it read `research/intake/records/` and `research/intake/normalized/manifests/corpus__deduped.json`
3. Have it write the run report to:
   `research/intake/normalized/capture/<run_date>__capture_backfill_report.json`
4. Have it write blocked items to:
   `research/intake/rejected/<run_date>__capture_backfill__blocked.json`

### Phase 6: Quality Control

1. Open `prompts/quality_control.md`.
2. Paste the full QC prompt into the QC agent.
3. Paste the normalized records, dedupe decisions, and any raw outputs that need checking.
   Paste the dedup manual-review file too if one exists.
4. Run QC.
5. Save the raw QC agent output to:
   `research/intake/inbox/system_runs/<run_date>__qc__pass_01.json`
6. Save the QC report to:
   `research/intake/normalized/qc/<run_date>__qc_report.json`
7. Save blocked items to:
   `research/intake/rejected/<run_date>__qc__blocked.json`

### Phase 7: Repair Loop

If QC fails:

1. Identify which buckets or records failed.
2. Rerun only those bucket searches or only that dedup pass.
3. Run dedup again.
4. Run QC again.
5. Save each rerun's raw dedup or QC output with the next pass number in `research/intake/inbox/`.
   Save dedup reruns in `research/intake/inbox/system_runs/`.
   Save QC reruns in `research/intake/inbox/system_runs/`.
6. Repeat until QC passes.

Do not rerun all buckets unless the failure is systemic.

## What To Paste Into Each Agent

### Source-Finder Agent

Paste, in this exact order:

1. full contents of `prompts/canonical_source_finder_template.md`
2. full contents of one bucket file

Do not paste file paths only. Paste the actual text.

### Dedup Agent

Paste, in this exact order:

1. full contents of `prompts/dedup_normalization.md`
2. raw bucket JSON outputs
3. any existing normalized records if you are running an incremental pass

If a bucket file contains two different source-finder outputs:

- best option: split them into two valid JSON objects before pasting, or wrap them in a JSON array
- acceptable option: paste both complete batch objects one after the other
- avoid relying on a malformed file that mixes two partial outputs or broken JSON fragments

The dedup prompt is written to flatten multiple batch objects before deduping sources.

If you are using Codex or another agent with repo access:

- use `prompts/dedup_normalization_repo_access.md` instead
- do not paste all raw outputs manually unless you want to constrain the run
- the agent should read the intake files itself and write the repo files directly

### QC Agent

Paste, in this exact order:

1. full contents of `prompts/quality_control.md`
2. normalized records
3. dedupe decisions
4. raw outputs if needed for debugging traceability

## Fast Failure Checks

Reject and rerun immediately if any source-finder output does any of the following:

- returns markdown or prose outside a JSON object
- omits required keys
- gives weak sources instead of returning `insufficient_high_quality_sources_found`
- writes a mini literature review
- makes cross-source conclusions
- loses mechanistic detail in claims
- fails to provide claim locations

## Practical Tip

If you want the lowest-friction manual workflow, make one temporary combined prompt document per bucket by concatenating:

1. `prompts/canonical_source_finder_template.md`
2. one `prompts/buckets/*.md`

Then paste that one combined text into the web agent.

## Raw Output Files To Create

Create one raw output file for every prompt execution:

- one dispatcher raw output if you use the dispatcher prompt
- one raw output per bucket run
- one raw output for the supplemental official-docs sweep if you run it
- one raw output for every dedup pass
- one raw output for every QC pass

Do not overwrite passes. Increment `<nn>` for dedup and QC reruns.

For the 14 main web research agents, the important rule is:

- one bucket prompt
- one clearly named bucket output file

Example:

- tooling prompt -> `research/intake/inbox/bucket_runs/<run_date>__tooling_tool_gateway.json`
- context prompt -> `research/intake/inbox/bucket_runs/<run_date>__context_engineering.json`
