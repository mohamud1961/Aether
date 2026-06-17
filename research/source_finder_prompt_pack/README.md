# Source-Finder Prompt Pack

This folder contains the production prompt pack for source-discovery agents used in harness research intake.

Zero-access assumption

- The research agent does not have repo access.
- Any file path in this folder is for the human operator, not for the agent.
- When running a source-finder, paste the full contents of `prompts/canonical_source_finder_template.md` followed by exactly one file from `prompts/buckets/` into a single prompt.
- Do not assume the agent can inspect `shared_json_schema.json` or any other repo file unless you paste the needed content into the prompt.

Layout

- `prompts/dispatcher.md`: master dispatcher prompt
- `prompts/canonical_source_finder_template.md`: shared source-finder template
- `prompts/quality_control.md`: QC agent prompt
- `prompts/dedup_normalization.md`: dedup-and-normalization prompt
- `prompts/dedup_normalization_repo_access.md`: dedup-and-normalization prompt for Codex or any agent with repo read/write access
- `prompts/buckets/`: one bucket-specific prompt per research bucket
- `prompts/supplemental/`: optional cross-cutting sweeps that still map back into the 14 buckets
- `prompts/fresh_readiness_run/`: fresh repair-run prompts for the remaining weak and high-risk gaps, including repo-access capture backfill, synthesis, and exit-gate review
- `shared_json_schema.json`: shared `SourceFinderBatch` schema
- `repo_output_plan.md`: intake storage and file-location plan
- `global_quality_gate_checklist.md`: QC gates
- `merge_protocol.md`: normalization, dedup, and merge procedure
- `operator_runbook.md`: exact human-run execution order for zero-repo-access web agents

Usage

1. Run `prompts/dispatcher.md` to assign a bucket job.
2. For each bucket run, paste `prompts/canonical_source_finder_template.md` plus exactly one file from `prompts/buckets/` into one prompt.
3. Save each bucket prompt's raw output to its own clearly named file in `research/intake/inbox/bucket_runs/`.
   Example: `research/intake/inbox/bucket_runs/<run_date>__tooling_tool_gateway.json`
4. Run `prompts/dedup_normalization.md` and save its raw output too.
5. Run `prompts/quality_control.md` and save its raw output too.
6. Publish the merged manifest only after QC pass.

Fresh readiness run

Use `prompts/fresh_readiness_run/` when the goal is not broad intake, but closing the specific gaps that currently block leaving research intake:

1. Run the bucket-repair prompts there for the still-weak buckets.
2. Normalize and QC those outputs before treating them as corpus coverage.
3. Run the repo-access prompts there to audit and backfill capture gaps, mine local trajectory/codebase evidence, and promote findings into top-level synthesis.
4. Run the exit-gate review only after the fresh repair pass is complete.

Default output location for this run

- `research/intake/inbox/fresh_readiness_run/`
- The folder contains one manifest file for the run and one placeholder output file per fresh-readiness prompt.
- If you later want to promote the raw bucket repair outputs into the standard intake flow, copy or move them into the conventional inbox locations after review.

Recommended supplemental sweeps

- `adversarial_robustness_anti_cheat_sweep.md`: false completion, verifier gaming, test tampering, benchmark exploits, and anti-tamper harness design
- `context_compaction_handoff_sweep.md`: compaction triggers, rolling versus milestone summaries, reset handoffs, and summary-loss recovery
- `llm_native_harness_alignment_sweep.md`: model-native harness patterns, harness-model fit, and model-specific scaffolding effects
- `problem_localization_exploration_strategy_sweep.md`: repo/environment exploration, target narrowing, dependency diagnosis, and wrong-target avoidance
- `prompt_program_token_budget_sweep.md`: prompt layering, token-budget allocation, prompt caching, and model-specific prompt sensitivity
- `workflow_control_policy_sweep.md`: plan-led, deficit-led, verifier-led, milestone-led, queue-led, and hybrid next-action control policies
- `working_context_compiler_retrieval_sweep.md`: retrieval policy, context selection, invalidation, and working-set compilation
- `dynamic_tool_discovery_prefetch_sweep.md`: just-in-time tool loading, deterministic prefetch, and tool-surface bloat control
- `tool_calling_methodologies_sweep.md`: core invocation methods such as structured function calling, parsing, ReAct-style inline calls, code-generation-based tool use, constrained decoding, multi-call, and streaming invocation
- `scheduler_coordination_conflict_sweep.md`: planner-worker coordination, ownership, conflict policies, and bounded parallelism
- `approval_control_gates_sweep.md`: approval gates, escalation, kill switches, scope limiters, and controlled autonomy
- `experiment_methodology_online_offline_alignment_sweep.md`: internal eval design, online-offline alignment, contamination control, and reproducibility
- `frontier_official_docs_sweep.md`: targeted official-doc coverage across current frontier platforms

Bucket Map

| Bucket | Mission | Preferred Source Classes | Exclusions | Target Source Count | Exception Cap |
| --- | --- | --- | --- | ---: | ---: |
| `policy_program` | Find operating doctrine for terminal agents: instruction layering, invariants, stop rules, escalation rules, completion doctrine. | Official engineering writeups, provider docs with agent operating rules, repos exposing prompt/program files, traces/postmortems with policy failures. | Generic prompt tips, alignment essays without mechanism, UI guidance. | 10 | 2 |
| `agent_architecture` | Find topology evidence: single-agent, planner-executor, manager-worker, verifier loops, specialization and coordination overhead. | Benchmark papers, engineering writeups, repos with multi-agent layouts, ablations, traces. | Team-process advice, speculative autonomy commentary, orchestration marketing pages. | 10 | 2 |
| `tooling_tool_gateway` | Find tool schema, permissions, retries, idempotency, error-surface, and path-semantics mechanisms. | Provider docs, repos with tool gateways, issue threads, engineering writeups, benchmark docs with tool rules. | Function-calling tutorials without operational detail, generic SDK intros. | 12 | 2 |
| `execution_control` | Find loop-control mechanisms: phased loops, replanning, interruption, budget control, stopping, loop breakers. | Engineering writeups, benchmark papers, ablations, repos with execution loops, traces showing loop failure or recovery. | Generic agent workflow diagrams, planning essays without measured behavior. | 12 | 2 |
| `context_engineering` | Find working-set construction, retrieval, compaction, stale-context defense, context compilation. | Papers, repos, engineering writeups, issue threads on context failure, benchmark docs with context constraints. | Generic RAG content not tied to tool-using agents, chatbot memory explainers. | 12 | 2 |
| `state_management` | Find manifests, event logs, checkpoints, resumability, replayability, drift detection, authoritative state design. | Repos, engineering writeups, traces, issue threads, postmortems with state corruption or resume failures. | Pure database papers without agent relevance, generic workflow state tools. | 8 | 2 |
| `artifact_workspace` | Find workspace discipline: receipts, scratch files, progress docs, handoff artifacts, cleanliness rules. | Repos, traces, postmortems, issue threads, engineering docs with file/workspace contracts. | General developer productivity advice, IDE workflow tips. | 8 | 2 |
| `memory` | Find write-gated and retrieval-gated memory policy for agentic execution, plus invalidation and contamination controls. | Papers, provider docs, repos, engineering writeups, issue threads with memory regressions. | Consumer memory features, chat personalization, generic knowledge-base marketing. | 8 | 2 |
| `verification_completion` | Find tests, external oracles, completion contracts, false-completion prevention, browser/E2E verification. | Benchmark docs, repos, engineering writeups, issue threads, postmortems, ablations with verification changes. | Pure evaluator leaderboards without methodology, generic QA content. | 12 | 2 |
| `recovery_fault_tolerance` | Find rollback, retry, re-anchoring, environment reset, state repair, degraded-mode mechanisms. | Repos, traces, postmortems, issue threads, engineering docs with recovery logic. | Generic resilience commentary, infra SRE posts not tied to agent execution. | 10 | 2 |
| `observability_audit` | Find traces, replay support, structured logs, command receipts, model I/O capture, audit surfaces. | Repos, benchmark docs, engineering writeups, traces, observability docs with concrete schema. | Generic dashboards, product analytics, unstructured demo videos. | 10 | 2 |
| `environment_substrate` | Find sandbox, Docker, browser, filesystem, and constrained-environment substrate design. | Benchmark docs, repos, environment adapters, task harness docs, engineering writeups. | Generic container intros, unrelated infra setup docs. | 8 | 2 |
| `evals_benchmarking` | Find benchmark rules, grading, holdouts, robustness metrics, failure injection, anti-overfitting measures. | Benchmark papers, official benchmark docs, eval repos, ablations, issue threads on evaluation failure. | Leaderboard brag posts, benchmark summaries without methodology. | 12 | 3 |
| `cost_token_management` | Find budget caps, prompt caching, long-horizon cost tracking, context reuse, and token working-set control. | Provider docs, repos, engineering writeups, cost-ablation papers, issue threads on token blowups. | Pricing pages without mechanism, generic "optimize tokens" advice. | 8 | 2 |
