# Failures

Failed hypotheses, regressions, invalid methods, and rejected directions.

## F-001 | 2026-03-25 | Intake coverage gaps across planned dimensions
- Status: open
- Summary: Six planned research buckets had zero accepted sources after the initial normalization pass.
- Observations: `artifact_workspace__accepted.json`, `cost_token_management__accepted.json`, `environment_substrate__accepted.json`, `evals_benchmarking__accepted.json`, `memory__accepted.json`, and `observability_audit__accepted.json` each contain empty `accepted_source_ids` lists.
- Inference: Any near-term design decisions in those areas would be weakly supported unless the scope is narrowed or more evidence is gathered.
- Evidence paths: `research/intake/normalized/manifests/artifact_workspace__accepted.json`, `research/intake/normalized/manifests/cost_token_management__accepted.json`, `research/intake/normalized/manifests/environment_substrate__accepted.json`, `research/intake/normalized/manifests/evals_benchmarking__accepted.json`, `research/intake/normalized/manifests/memory__accepted.json`, `research/intake/normalized/manifests/observability_audit__accepted.json`
- Affected components: research scope, future block design for under-covered dimensions
- Decision/status change: none; gap recorded
- Confidence: high
- Follow-up needed: Run targeted intake or explicitly mark these dimensions out of scope for the current cycle.

## F-002 | 2026-03-24 to 2026-03-25 | BigAI baseline description does not match derived coverage
- Status: open
- Summary: Repo narrative describes an 89-task BigAI baseline, but the derived trace layer currently indexes only 86 tasks.
- Observations: `research/sources/trajectories/README.md` and the filesystem show 89 task directories under `research/sources/trajectories/BigAI`. `research/analysis/bigai_trace_layer/output/corpus_summary.json` reports `task_count: 86`. The non-indexed directories are `financial-document-processor`, `install-windows-3.11`, and `sparql-university`.
- Inference: Any statement that the current derived trace layer covers the full 89-task BigAI baseline is unsupported until the missing-task discrepancy is explained.
- Evidence paths: `research/sources/trajectories/README.md`, `research/sources/trajectories/BigAI/`, `research/analysis/bigai_trace_layer/output/corpus_summary.json`
- Affected components: baseline framing, corpus-derived claims, reproducibility notes
- Decision/status change: baseline description should be treated as provisional
- Confidence: high
- Follow-up needed: Determine whether the three directories were intentionally excluded or are missing usable run artifacts.

## F-003 | 2026-03-24 | Provenance-only gaps in BigAI corpus
- Status: known limitation
- Summary: Two BigAI bundles could not be fully traced because only provenance-level information was available.
- Observations: `research/analysis/bigai_trace_layer/README.md` notes that two BigAI bundles are provenance-only because `agent/trajectory.json` is a Git LFS pointer. `research/analysis/bigai_trace_layer/output/corpus_summary.json` reports `provenance_only: 2`. `research/analysis/bigai_trace_layer/output/exemplar_runs.json` names `gcode-to-text` and `video-processing` as the affected runs.
- Inference: Corpus-level statistics are based on 312 parseable runs, not the full raw bundle set.
- Evidence paths: `research/analysis/bigai_trace_layer/README.md`, `research/analysis/bigai_trace_layer/output/corpus_summary.json`, `research/analysis/bigai_trace_layer/output/exemplar_runs.json`
- Affected components: BigAI-derived claims and any aggregate counts that imply complete coverage
- Decision/status change: none; limitation recorded
- Confidence: high
- Follow-up needed: Recover missing trajectory content if possible, or keep these exclusions explicit in any write-up.

## F-004 | 2026-03-08 run, recorded in corpus analysis | Functional success invalidated by destructive cleanup
- Status: reusable negative result
- Summary: A BigAI run solved the nominal XSS task but still failed verification because it deleted an original verification file from the task environment.
- Observations: In `research/sources/trajectories/BigAI/break-filter-js-from-html/4e6a3070-4a78-4c1a-ac1c-c0651045db08-traj.txt`, the verifier says the payload in `/app/out.html` correctly bypassed the filter and triggered `alert()`, but verification failed because `/app/test_outputs.py` had been deleted. The planner then reassigned work to restore the file.
- Inference: Destructive cleanup is a concrete failure mode; verification must protect environment integrity, not just output behavior.
- Evidence paths: `research/sources/trajectories/BigAI/break-filter-js-from-html/4e6a3070-4a78-4c1a-ac1c-c0651045db08-traj.txt`, `research/analysis/bigai_trace_layer/output/question_answers.json`
- Affected components: verification policy, recovery design, cleanup heuristics
- Decision/status change: none; negative result preserved
- Confidence: high
- Follow-up needed: Encode environment-integrity checks into future verification/recovery block design.

## F-005 | 2026-03-29 | Supplemental intake pass produced partial raw outputs without audited integration
- Status: open
- Summary: The 2026-03-29 supplemental intake pass gathered new raw records, but the pipeline did not finish with populated dispatcher, QC, dedupe, or normalized artifacts.
- Observations: Three supplemental run files contain 58 total records: 17 in approval-control gates, 22 in dynamic tool discovery/prefetch, and 19 in experiment-methodology alignment. Four paired outputs are empty or blank: `frontier_official_docs_sweep.json`, `scheduler_coordination_conflict_sweep.json`, `working_context_compiler_retrieval_sweep.json`, and `tool_calling_methodologies_sweep.json`. The system-run files `2026-03-29__dispatcher__dispatch_plan.json`, `2026-03-29__qc__pass_01.json`, and `2026-03-29__dedup__pass_01.json` are empty JSON objects. No newer normalized response object or dedupe decisions file exists beyond the 2026-03-25 versions.
- Inference: The repo currently contains new raw evidence that is not yet eligible for stable ledger claims or bucket-count corrections.
- Evidence paths: `research/intake/inbox/supplemental_runs/2026-03-29__approval_control_gates_sweep.json`, `research/intake/inbox/supplemental_runs/2026-03-29__dynamic_tool_discovery_prefetch_sweep.json`, `research/intake/inbox/supplemental_runs/2026-03-29__experiment_methodology_online_offline_alignment_sweep.json`, `research/intake/inbox/supplemental_runs/2026-03-29__frontier_official_docs_sweep.json`, `research/intake/inbox/supplemental_runs/2026-03-29__scheduler_coordination_conflict_sweep.json`, `research/intake/inbox/supplemental_runs/2026-03-29__working_context_compiler_retrieval_sweep.json`, `research/intake/inbox/supplemental_runs/2026-03-29__tool_calling_methodologies_sweep.json`, `research/intake/inbox/system_runs/2026-03-29__dispatcher__dispatch_plan.json`, `research/intake/inbox/system_runs/2026-03-29__qc__pass_01.json`, `research/intake/inbox/system_runs/2026-03-29__dedup__pass_01.json`, `research/intake/normalized/2026-03-25__response_object.json`, `research/intake/normalized/dedupe/2026-03-25__dedupe_decisions.json`
- Affected components: intake workflow, supplemental source integration, bucket coverage accounting
- Decision/status change: none; process failure recorded
- Confidence: high
- Follow-up needed: Finish the 2026-03-29 integration path or document the pass as incomplete/aborted.
