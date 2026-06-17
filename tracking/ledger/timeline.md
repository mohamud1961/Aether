# Timeline

Chronological record of material project events.

## 2026-03-12 15:38:08 +0000 | Seed research scaffold
- Actor: repo author(s); exact identity is not recoverable from inspected artifacts.
- Event type: implementation
- Summary: Initial research-analysis files established a working harness decomposition and placeholder synthesis docs.
- Observations: `research/analysis/lego_dimensions.md` enumerates six dimensions: Orientation, Tool Surface, Execution Loop, Context Strategy, Verification, and Error Recovery. `research/analysis/patterns.md` contains seed patterns. `research/analysis/failure_modes.md` is still a TODO stub.
- Inferences: By March 12 the project had an explicit research scaffold, but evidence synthesis and failure taxonomy were still incomplete.
- Evidence paths: `research/analysis/lego_dimensions.md`, `research/analysis/patterns.md`, `research/analysis/failure_modes.md`
- Affected components: `research/analysis`
- Decision/status change: Working research scaffold established.
- Confidence: high
- Follow-up needed: Replace seed notes with evidence-linked findings and populate the failure taxonomy.

## 2026-03-24 17:46:35-21:14:37 +0000 | BigAI post-hoc trace layer generated
- Actor: analysis pipeline; script author is not attributable from the generated artifacts alone.
- Event type: source_analysis
- Summary: A corpus-only derived trace layer was produced over the BigAI TerminalBench corpus.
- Observations: `research/analysis/bigai_trace_layer/output/corpus_summary.json` reports 314 runs, 86 indexed tasks, 312 parseable runs, and 2 provenance-only runs. `research/analysis/bigai_trace_layer/output/coverage_report.json` reports 87 answered questions, 7 partial, and 6 irrecoverable. `research/analysis/bigai_trace_layer/output/question_answers.json` records stable planner/executor/verifier observations, early `save_plan` usage, and verifier/recovery counts.
- Inferences: The repo gained a reusable evidence layer for doctrine extraction, but some questions remain irrecoverable from public trajectories alone.
- Evidence paths: `research/analysis/bigai_trace_layer/README.md`, `research/analysis/bigai_trace_layer/output/corpus_summary.json`, `research/analysis/bigai_trace_layer/output/coverage_report.json`, `research/analysis/bigai_trace_layer/output/question_answers.json`
- Affected components: `research/analysis/bigai_trace_layer`, `research/sources/trajectories/BigAI`
- Decision/status change: BigAI research corpus moved from raw bundles to normalized trace artifacts.
- Confidence: high
- Follow-up needed: Resolve why 89 BigAI task directories reduce to 86 indexed tasks in the derived summary.

## 2026-03-25 17:23:22-18:21:27 +0000 | Source intake, normalization, and dedupe completed
- Actor: intake/normalization pipeline; individual operators are not attributable from the artifacts alone.
- Event type: source_analysis
- Summary: User-supplied research sources were harvested, normalized, deduped, and bucketed into accepted manifests.
- Observations: `research/intake/inbox/2026-03-25__user_supplied_agentic_harness_manifest.json` contains 87 entries, and the paired harvest report contains 87 captured artifacts. `research/intake/normalized/manifests/corpus__deduped.json` lists 105 accepted source IDs. `research/intake/normalized/dedupe/2026-03-25__dedupe_decisions.json` records 33 actions: 22 invalid source ID remaps and 11 merged duplicate candidates. `research/intake/rejected/2026-03-25__dedup__needs_manual_review.json` is empty. Highest accepted-source counts are in `state_management` (23), `agent_architecture` (19), `tooling_tool_gateway` (19), `verification_completion` (17), and `context_engineering` (14); six buckets have zero accepted sources.
- Inferences: Research collection is being handled as a reproducible pipeline rather than an ad hoc reading list, but coverage remains uneven across planned dimensions.
- Evidence paths: `research/intake/inbox/2026-03-25__user_supplied_agentic_harness_manifest.json`, `research/intake/inbox/2026-03-25__user_supplied_agentic_harness_harvest_report.json`, `research/intake/normalized/2026-03-25__response_object.json`, `research/intake/normalized/dedupe/2026-03-25__dedupe_decisions.json`, `research/intake/rejected/2026-03-25__dedup__needs_manual_review.json`, `research/intake/normalized/manifests/`
- Affected components: `research/intake`, `research/source_finder_prompt_pack`
- Decision/status change: Intake pipeline populated the initial research corpus.
- Confidence: high
- Follow-up needed: Targeted acquisition is still needed for buckets with zero accepted sources.

## 2026-03-28 15:35:05 +0000 | Ledger scaffold added
- Actor: historian setup author; exact identity is not recoverable from inspected artifacts.
- Event type: implementation
- Summary: Historian prompt and ledger files were added under `research/ledger/`.
- Observations: `research/ledger/README.md`, `research/ledger/historian_agent_prompt.md`, and the five ledger files were created at the same timestamp. Before this backfill pass, the ledger files contained headers only.
- Inferences: Auditability infrastructure was established after earlier research work, so retrospective reconstruction was required.
- Evidence paths: `research/ledger/README.md`, `research/ledger/historian_agent_prompt.md`, `research/ledger/timeline.md`, `research/ledger/decisions.md`, `research/ledger/failures.md`, `research/ledger/claims.md`, `research/ledger/open_questions.md`
- Affected components: `research/ledger`
- Decision/status change: Single-writer ledger mechanism established.
- Confidence: high
- Follow-up needed: Prefer forward logging via `LEDGER_UPDATE` blocks instead of future backfills.

## 2026-03-28 | Initial ledger backfill
- Actor: historian
- Event type: implementation
- Summary: Existing repo artifacts were converted into an initial evidence-linked ledger, and unsupported assumptions were left explicitly unresolved.
- Observations: The historian-owned files were empty before this pass. The reconstructed record is based on existing docs, manifests, generated analysis outputs, and trajectory artifacts already present in the repo.
- Inferences: The project now has an auditable baseline history, but future fidelity depends on agents emitting `LEDGER_UPDATE` blocks when material work occurs.
- Evidence paths: `research/ledger/timeline.md`, `research/ledger/decisions.md`, `research/ledger/failures.md`, `research/ledger/claims.md`, `research/ledger/open_questions.md`
- Affected components: `research/ledger`
- Decision/status change: Ledger is now usable for ongoing project history.
- Confidence: high
- Follow-up needed: Keep the ledger additive and append supersessions instead of rewriting older conclusions.

## 2026-03-29 18:11:38 +0100 | Supplemental sweeps added, but audited integration did not complete
- Actor: supplemental intake pipeline
- Event type: source_analysis
- Summary: New supplemental sweep outputs were added for approval controls, dynamic tool discovery, and experiment methodology, but the normalization/QC/dedupe path did not produce populated 2026-03-29 audited artifacts.
- Observations: `research/intake/inbox/supplemental_runs/2026-03-29__approval_control_gates_sweep.json` contains 17 records, `2026-03-29__dynamic_tool_discovery_prefetch_sweep.json` contains 22 records, and `2026-03-29__experiment_methodology_online_offline_alignment_sweep.json` contains 19 records. `2026-03-29__frontier_official_docs_sweep.json`, `2026-03-29__scheduler_coordination_conflict_sweep.json`, and `2026-03-29__working_context_compiler_retrieval_sweep.json` are empty JSON objects, while `2026-03-29__tool_calling_methodologies_sweep.json` is a blank file. The paired system-run files for dispatcher, QC, and dedupe are also empty JSON objects. The newest normalized artifacts remain `research/intake/normalized/2026-03-25__response_object.json` and `research/intake/normalized/dedupe/2026-03-25__dedupe_decisions.json`.
- Inferences: New evidence acquisition happened, but it has not yet crossed the threshold into the audited normalized corpus.
- Evidence paths: `research/intake/inbox/supplemental_runs/2026-03-29__approval_control_gates_sweep.json`, `research/intake/inbox/supplemental_runs/2026-03-29__dynamic_tool_discovery_prefetch_sweep.json`, `research/intake/inbox/supplemental_runs/2026-03-29__experiment_methodology_online_offline_alignment_sweep.json`, `research/intake/inbox/supplemental_runs/2026-03-29__frontier_official_docs_sweep.json`, `research/intake/inbox/supplemental_runs/2026-03-29__scheduler_coordination_conflict_sweep.json`, `research/intake/inbox/supplemental_runs/2026-03-29__working_context_compiler_retrieval_sweep.json`, `research/intake/inbox/supplemental_runs/2026-03-29__tool_calling_methodologies_sweep.json`, `research/intake/inbox/system_runs/2026-03-29__dispatcher__dispatch_plan.json`, `research/intake/inbox/system_runs/2026-03-29__qc__pass_01.json`, `research/intake/inbox/system_runs/2026-03-29__dedup__pass_01.json`, `research/intake/normalized/2026-03-25__response_object.json`, `research/intake/normalized/dedupe/2026-03-25__dedupe_decisions.json`
- Affected components: `research/intake/inbox`, normalization workflow, under-covered research buckets
- Decision/status change: Raw supplemental evidence acquired; audited integration still pending.
- Confidence: high
- Follow-up needed: Complete normalization/dedupe/QC for the 2026-03-29 supplemental pass or explicitly mark it aborted.

## 2026-03-29 18:21:37 +0100 | A-Evolve codebase snapshot added to research sources
- Actor: source acquisition workflow
- Event type: source_analysis
- Summary: The research corpus expanded to include an `a-evolve` codebase snapshot with an explicit workspace contract and a Terminal-Bench adapter.
- Observations: `research/sources/codebases/a-evolve/` now contains 160 non-git files. `research/sources/codebases/a-evolve/README.md` describes A-Evolve as infrastructure for self-improving agents and presents a solve-observe-evolve-gate-reload loop. `research/sources/codebases/a-evolve/DESIGN.md` states that "the workspace IS the interface." `research/sources/codebases/a-evolve/agent_evolve/benchmarks/tb2/README.md` documents a Terminal-Bench 2.0 adapter that expects 89 challenge directories from a pinned source.
- Inferences: The repo's source base now includes an evolution-centric harness with explicit filesystem-contract design that may be relevant to workspace, memory, and gating research.
- Evidence paths: `research/sources/codebases/a-evolve/README.md`, `research/sources/codebases/a-evolve/DESIGN.md`, `research/sources/codebases/a-evolve/agent_evolve/benchmarks/tb2/README.md`
- Affected components: `research/sources/codebases`
- Decision/status change: External codebase corpus expanded beyond the previously indexed set.
- Confidence: high
- Follow-up needed: Index `a-evolve` in the codebase inventory and extract concrete mechanisms into synthesis docs before using it in claims.

## 2026-03-29 | Cross-session ledger inbox workflow implemented
- Actor: historian
- Event type: implementation
- Summary: The repo gained a durable raw handoff path so `LEDGER_UPDATE` blocks survive across threads/sessions without user copy/paste.
- Observations: `AGENTS.md` now requires non-historian agents to persist raw handoffs under `research/ledger/inbox/` using `python3 research/ledger/tools/record_update.py`. `research/ledger/inbox/README.md` defines the inbox as the raw cross-session handoff layer. `research/ledger/historian_agent_prompt.md` now instructs the historian to inspect `research/ledger/inbox/` before relying on chat history. `research/ledger/tools/record_update.py` validates stdin and writes one unique raw handoff file per update.
- Inferences: The ledger workflow no longer depends on the user manually ferrying updates between sessions; it now has an on-disk inbox contract shared by all agents.
- Evidence paths: `AGENTS.md`, `research/ledger/README.md`, `research/ledger/inbox/README.md`, `research/ledger/historian_agent_prompt.md`, `research/ledger/tools/record_update.py`
- Affected components: collaboration workflow, `research/ledger`
- Decision/status change: Cross-session raw handoff workflow established.
- Confidence: high
- Follow-up needed: Ensure future non-historian sessions actually use the recorder command when they emit material `LEDGER_UPDATE`s.

## 2026-03-29 | Raw handoff terminology clarified
- Actor: historian
- Event type: implementation
- Summary: The workflow now explicitly distinguishes raw agent handoffs from canonical historian ledger entries.
- Observations: `AGENTS.md` now tells other agents to emit `RAW_LEDGER_UPDATE` handoffs for historian review. `research/ledger/README.md` and `research/ledger/inbox/README.md` now describe inbox files as raw handoffs rather than ledger entries. `research/ledger/historian_agent_prompt.md` now treats both `RAW_LEDGER_UPDATE` and legacy `LEDGER_UPDATE` as raw inputs only. `research/ledger/tools/record_update.py` accepts both markers for backward compatibility.
- Inferences: The role boundary is now explicit in repo policy: agents produce raw historian inputs; the historian alone produces ledger entries.
- Evidence paths: `AGENTS.md`, `research/ledger/README.md`, `research/ledger/inbox/README.md`, `research/ledger/historian_agent_prompt.md`, `research/ledger/tools/record_update.py`
- Affected components: collaboration workflow, `research/ledger`
- Decision/status change: Terminology clarified without changing single-writer ownership.
- Confidence: high
- Follow-up needed: Prefer `RAW_LEDGER_UPDATE` in new sessions and let the historian treat legacy `LEDGER_UPDATE` handoffs as transitional input.

## 2026-03-29 | Historian pruning rule clarified
- Actor: historian
- Event type: decision
- Summary: The ledger workflow now explicitly treats raw inbox handoffs as noisy inputs that must be pruned for research relevance.
- Observations: `AGENTS.md` now distinguishes material events from routine cleanup and says JSON cleanup, formatting, and housekeeping are usually not material by themselves. `research/ledger/README.md`, `research/ledger/inbox/README.md`, and `research/ledger/historian_agent_prompt.md` now instruct the historian to omit operational noise unless it affects findings, methodology, corpus integrity, experiment validity, or reproducibility.
- Inferences: The canonical ledger is now explicitly curated for research significance rather than completeness of raw operational activity.
- Evidence paths: `AGENTS.md`, `research/ledger/README.md`, `research/ledger/inbox/README.md`, `research/ledger/historian_agent_prompt.md`
- Affected components: historian process, ledger workflow
- Decision/status change: Materiality filter clarified.
- Confidence: high
- Follow-up needed: Apply this pruning standard consistently when reviewing future inbox handoffs.
