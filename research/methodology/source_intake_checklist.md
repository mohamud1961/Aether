# Source Intake Checklist

Use this as the Phase 1 intake spec. This is for source discovery, metadata capture, and atomic extraction, not synthesis.

## 1. Research Boundary

- Define the target clearly: the research is about the `agentic harness`, meaning the full non-model system that turns a model into a task-completing terminal agent.
- **Terminal agent = an agent operating primarily through shell/CLI, files, code, tests, local tooling, and sometimes browser support, under bounded environment constraints.**
- Treat the harness as including: model interface, runtime settings, system/task instructions, policy/program layer, execution loop, tool gateway, context assembly, state management, memory policy, artifact/workspace discipline, verification, stop rules, recovery, observability, environment adapters, and eval integration.
- Explicitly exclude: UI/product packaging, agent marketplaces, generic business automation, vague autonomy discourse, and future-of-agents commentary with no mechanism.
- Keep the end goal fixed: best general-purpose terminal task-execution harness for strong performance on TerminalBench-like tasks without benchmark chasing.

## 2. Source-Finder Role

- Source-finding agents are allowed to do: discovery, filtering, dedup hints, metadata capture, bucket tagging, evidence scoring, atomic claim extraction, failure-mode extraction, and short inclusion notes.
- Source-finding agents are not allowed to do: lit reviews, cross-source synthesis, ranking overall architectures, declaring winners, or writing design recommendations.
- Limit interpretation to source-local statements only.
- Require every returned source to have a concrete reason it belongs in the corpus.

## 3. Time Window Policy

- Use a primary recency window of `November 24, 2025` through `March 24, 2026`.
- Allow older sources only as `foundational exceptions`.
- Require an explicit exception reason for every older source.
- Cap foundational exceptions per bucket so the corpus does not drift backward.

## 4. Evidence Priority

- Prioritize benchmark papers and official benchmark docs.
- Prioritize official engineering writeups from frontier labs.
- Prioritize official provider docs where they describe concrete agent mechanisms.
- Prioritize strong open-source repos with real implementation detail.
- Prioritize public traces, postmortems, ablations, and issue threads with clear provenance.
- Include papers and preprints when they contain mechanism, eval design, or failure analysis.
- Exclude random blogs, X posts, newsletters, listicles, podcasts, and summary content from source-finder scope.

## 5. Evidence Scoring

- Score each source on provenance.
- Score each source on mechanistic detail.
- Score each source on reproducibility.
- Score each source on ecological validity for terminal agents.
- Score each source on direct relevance to your harness decisions.
- Score each source on recency.
- Assess `benchmark_contamination_risk` (values: `low`, `medium`, `high`) and flag reasons such as:
  - benchmark-specific heuristics
  - explicit benchmark optimization
  - suspicious task-shaped tactics
  - overfit eval behavior with unclear generalization

## 6. Core Decision Targets

- Collect sources that inform `policy/program layer` decisions.
- Collect sources that inform `tool gateway` decisions.
- Collect sources that inform `execution loop` decisions.
- Collect sources that inform `context assembly/compaction/retrieval` decisions.
- Collect sources that inform `state and artifact management` decisions.
- Collect sources that inform `memory policy` decisions.
- Collect sources that inform `verification/completion contract` decisions.
- Collect sources that inform `recovery/fault tolerance` decisions.
- Collect sources that inform `observability/replay` decisions.
- Collect sources that inform `single-agent vs multi-agent topology` decisions.
- Collect sources that inform `eval and holdout design` decisions.
- Collect sources that inform `cost and token budget management` decisions.

## 7. Research Buckets

- `Policy / Program Layer`: system prompts, AGENTS.md/program.md style doctrine, invariants, escalation rules, completion doctrine, operating contracts.
- `Agent Architecture`: single agent, manager-worker, planner-executor-verifier, DAG/workflow hybrids, parallelism, specialization, coordination overhead.
- `Tooling and Tool Gateway`: tool schema design, permissions, retries, idempotency, path semantics, read/write separation, structured vs loose tools, tool error surfaces.
- `Execution Control`: act-observe loops, phased loops, re-planning, budget control, interruptibility, loop breakers, stopping logic.
- `Context Engineering`: retrieval, summarization, compaction, working set selection, stale context defense, compile-time vs on-demand context.
- `State Management`: authoritative state, manifests, event logs, checkpoints, resumability, replayability, task-state drift detection.
- `Artifact / Workspace Discipline`: scratch files, progress files, receipts, handoff docs, test/result artifacts, session-bridging files, workspace cleanliness rules.
- `Memory`: short-term memory, long term memory, cross-session memory, write gating, retrieval gating, invalidation, contamination risks.
- `Verification and Completion`: tests, checklists, external oracles, browser/E2E verification, completion contracts, false-completion prevention.
- `Recovery and Fault Tolerance`: rollback, retry strategy, re-anchoring, state repair, environment reset, degraded mode.
- `Observability and Audit`: step traces, structured logs, command receipts, model I/O capture, replay support, analysis surfaces.
- `Environment Substrate`: terminal sandboxes, Docker/task isolation, browser coupling, filesystem assumptions, constrained environments.
- `Evals and Benchmarking`: benchmark structure, grading, failure injection, holdouts, robustness metrics, anti-overfitting design.
- `Cost and Token Management`: budget caps, prompt caching architecture, inference cost tracking, context reuse logic.
- `Interaction Tags`: require cross-tags like `tools x verification`, `execution x context`, `state x recovery`, `policy x tools`; do not treat interaction as a separate sourcing silo.

## 8. Per-Bucket Search Questions

- What design families exist in this bucket?
- What concrete mechanisms are actually used?
- What failure modes are reported?
- What evidence supports the mechanism?
- What assumptions or scope limits are stated?
- What metrics were used?
- What task regime does the evidence come from?
- What parts seem benchmark-specific?
- What remains unresolved?

## 9. Terminal-Agent Relevance Filter

- Prefer sources grounded in coding agents, terminal agents, long-horizon software tasks, or real tool-using agents.
- Downrank sources that only study pure chat behavior.
- Downrank sources that only study function-call syntax accuracy.
- Downrank sources that only study memory recall divorced from real task execution.
- Keep API-agent sources only if the mechanism plausibly transfers to terminal harness design.

## 10. Required Per-Source Metadata

- `source_id`
- `title`
- `canonical_url`
- `date`
- `authors_or_org`
- `source_type`: paper / official_doc / engineering_writeup / repo / issue_thread / benchmark_site / trace / postmortem
- `artifact_type`: pdf / webpage / repo / markdown / issue / docs_page / codebase
- `decision_targets` (allowed values: policy_program, tool_gateway, execution_loop, context, state, artifacts_workspace, memory, verification, recovery, observability, topology, eval_design, cost_budget)
- `evidence_scorecard`
- `time_window_status`
- `bucket_primary`
- `bucket_secondary`
- `mechanism_tags`
- `failure_mode_tags`
- `benchmark_tags`
- `benchmark_contamination_risk`
- `task_regime`
- `models_if_named`
- `environment_type`
- `relevance_note`
- `reason_included`
- `exception_reason` if older than the primary window
- `dedupe_key`

## 11. Required Atomic Extraction

- **Extract only the highest-value claims relevant to harness design. Do not exhaustively summarize the source.**
- Extract `1-5` atomic mechanism claims from each source.
- Extract `1-5` atomic failure-mode claims if present.
- Point each extracted claim to a section, heading, file, commit, issue comment, or passage location.
- Mark whether each claim is measured, asserted, or anecdotal.
- Mark whether each claim is source-local or inferred.
- Do not merge claims across sources.

## 12. Inclusion Criteria

- Include only if the source contains at least one concrete mechanism.
- Include only if the source contains at least one operational lesson, failure analysis, eval design insight, or implementation detail.
- Include only if the source helps one or more harness decisions.
- Include only if the source has enough provenance to be audited later.

## 13. Exclusion Criteria

- Reject if it is mainly hype, marketing, trend commentary, or abstraction without mechanism.
- Reject if it is a summary of other sources without original technical detail.
- Reject if it is leaderboard boasting without methodology.
- Reject if it is unrelated to general-purpose task execution.
- Reject if it is too weak to justify re-reading during synthesis.

## 14. Source Quotas

- Set a target count for each bucket before searching.
- Require a minimum count of high-quality primary-window sources per bucket.
- Allow only a limited number of foundational exceptions per bucket.
- Stop searching a bucket if additional results are low-signal repeats.
- Return `insufficient high-quality sources found` instead of padding with junk.

## 15. Search Discipline

- Search official benchmark and lab sources first.
- Search repos and implementation artifacts before commentary.
- Search for postmortems, failures, and issue discussions, not just polished success narratives.
- Search specifically for ablations and comparisons where the same model behaves differently under different harnesses.
- Search for long-running agent writeups, resumability, and session handoff behavior.
- Search for premature completion, context drift, bad tool use, state corruption, and recovery mechanisms.

## 16. Bucket-Specific Must-Find Themes

- For `policy/program`: doctrines, invariants, stop rules, instruction layering, structured task rules.
- For `tool gateway`: schema design, tool docs, permission surfaces, explicit analysis fields, path clarity, safe write flows.
- For `execution`: loop families, phased control, re-planning triggers, search vs exploitation behavior, budget-aware control.
- For `context`: working-set construction, compaction failure, retrieval quality, stale-summary failure, context compilation.
- For `state/artifacts`: manifests, progress logs, TODO stores, receipts, checkpoint files, session-transfer artifacts.
- For `verification`: external oracles, test-first vs test-last, completion checklists, false positive/false negative behavior.
- For `recovery`: rollback points, clean-state restart, Git-based safety, environment reinit, recovery after wrong edits.
- For `observability`: trajectory schema, replayability, auditable actions, what to log for later causal analysis.
- For `evals`: holdouts, anti-benchmark-chasing measures, failure-injection evals, stratified task sets.
- For `cost/tokens`: prompt caching implementation, long-horizon cost tracking, cache eviction, token working-set limits.

## 17. Corpus Quality Control

- Check for duplicate URLs and duplicate underlying sources.
- Normalize canonical URLs.
- Remove multiple summaries of the same original source.
- Check that bucket tags are not bloated.
- Check that every source has a concrete mechanism or failure signal.
- Check that foundational exceptions are truly justified.
- Check that relevance notes are short and factual.
- Check that claims are traceable back to the source.
- Check that no source-finder has drifted into synthesis.

## 18. Repo Intake Requirements

- Save each accepted source with stable metadata.
- Save raw source files or snapshots when feasible.
- Save extracted claims separately from source metadata.
- Save dedupe decisions.
- Save rejection logs for near-miss sources so search effort is auditable.
- Keep bucket-level inventories so later review can see coverage gaps.

## 19. Coverage Review Before Analysis

- Verify all buckets have enough high-signal coverage.
- Verify the highest-priority buckets are strongest: policy/program, tool gateway, execution, context/state, verification, recovery.
- Verify terminal-agent relevance remains dominant.
- Verify the corpus contains both success patterns and failure patterns.
- Verify the corpus contains both official polished sources and real-world artifacts like repos, traces, and issues.
- Verify there is enough material to compare single-agent and multi-agent without prematurely biasing toward either.

## 20. Done Criteria For Phase 1 Intake

- Every bucket has a usable corpus.
- Every source has auditable metadata.
- Every source has atomic extraction, not just a link.
- Every foundational exception is justified.
- The corpus is deduped and normalized.
- Coverage gaps are explicitly documented.
- The intake corpus is ready for separate review and synthesis.
