EVAL_INVENTORY_OUTPUT
- scope:
  - Synthesis-prep inventory of eval-related local evidence across `research/sources/papers/`, `research/sources/docs/`, `research/sources/informal/`, `research/sources/benchmarks/`, `research/sources/codebases/`, `research/sources/trajectories/`, `research/intake/records/`, and local synthesis/governance docs.
  - External repo-status checks were performed only to verify key missing families called out in the prompt: ContextBench, tau2-bench, BFCL, FRAMES, Nexus, MemoryAgentBench, WebArena family, and SWE-bench / Verified.
- corpus_reviewed:
  - 146 paper capture dirs, 100 doc capture dirs, 5 benchmark capture dirs, 8 code capture dirs, 5 top-level local codebase mirrors, 102 informal markdown captures, 280 intake records, and 3 trajectory corpora.
  - The trajectory corpus is unusually strong for eval prep: `BigAI`, `deepagents`, and `terminus-kira` each cover 89 shared task folders, for 267 task-corpus directories total.
  - Key local coordination docs reviewed: `AGENTS.md`, `GOVERNED_MULTI_AGENT_OPERATING_MODEL.md`, `tracking/collab/stage_02_synthesis/README.md`, `tracking/collab/stage_02_synthesis/evidence_inventory/brief.md`, and the two April 1 ledger inbox eval-inventory handoffs.
- highest_value_first_wave_sources:
  - `research/sources/papers/src_pap_f6aa42bfdc1a`: Terminal-Bench paper. This remains the most directly relevant benchmark-spec source for the project mission.
  - `research/sources/trajectories/`: the 89-task `BigAI`, `deepagents`, and `terminus-kira` trajectory triad. This is the strongest local behavioral evidence base for eval-sensitive harness comparison.
  - `research/sources/papers/src_pap_70b31c72af76`: Efficient Benchmarking of AI Agents. Strong cross-benchmark harness methodology source.
  - `research/sources/papers/src_pap_c5f42ff16ea3`: rigorous benchmark construction checklist. High leverage for anti-cheat, contamination, and benchmark validity decisions.
  - `research/sources/docs/src_doc_f93fa0aea2d6` and `research/sources/benchmarks/src_bnm_8c3b5dc456f5`: MALT plus ImpossibleBench. This is the most actionable local anti-cheat / eval-integrity cluster.
  - `research/sources/codebases/deepagents/libs/evals`: strongest local eval code mirror. It already contains runnable or curated coverage for MemoryAgentBench, tau2 airline, BFCL v3, FRAMES, and Nexus.
  - `research/sources/codebases/langchain/agentevals` and `research/sources/codebases/langchain/openevals`: reusable evaluator/judge logic, trajectory scoring, and prompt scaffolding.
  - `research/sources/benchmarks/src_bnm_e5f985948a0e`, `research/sources/papers/src_pap_b4d59442a63d`, and `research/sources/codebases/src_cod_e231561a3d69`: strongest local SWE eval cluster.
  - `research/sources/papers/src_pap_d4370863a7e0`: MCPAgentBench paper capture. Directly relevant, and currently underrepresented in the inventory because it is not backfilled into intake records.
  - `research/sources/papers/src_pap_4c58a9fc09b8`, `research/sources/papers/2601.18137.pdf`, and `research/sources/papers/2601.20730.pdf`: MemoryArena, DeepPlanning, and AgentLongBench exist locally but are not represented in intake metadata, so they should be promoted into first-wave synthesis inputs.
- missing_or_underweighted_eval_families:
  - Context retrieval process evals are underweighted. The repo has only a postmortem-style Context-Bench mention, not the actual `ContextBench` paper or repo mirror.
  - tau-bench / tau2 is only partially represented. DeepAgents vendors or reimplements the airline subset, but the official benchmark family is not mirrored.
  - Tool-calling evals are materially underweighted in official form. BFCL, FRAMES, and Nexus appear only as curated DeepAgents hard-case subsets rather than full benchmark mirrors.
  - Memory evals are stronger than the shortlist suggests but structurally underweighted in metadata. MemoryArena, Evaluating Memory in LLM Agents via Incremental Multi-Turn Interactions, AMA-Bench, LongMemEval, and related captures exist locally, but many are absent from intake records.
  - Browser / GUI evals are underrepresented as runnable code mirrors. There is a WebArena-Infinity capture and papers like OS-HARM and DigiData, but no local mirror of canonical `WebArena`, `VisualWebArena`, `OSWorld`, or `AndroidWorld`.
  - MCP evals are underweighted. MCPAgentBench exists as a local paper capture but has no record backfill and no mirrored code repo.
  - Production / online eval methodology is present only informally. CursorBench, CIRCLE, and Measuring Agents in Production are useful for synthesis, but not yet treated as a coherent family.
- corrected_or_expanded_prior_shortlist:
  - Add these local-but-missed sources immediately: MemoryArena, DeepPlanning, AgentLongBench, MCPAgentBench, VeRO, SkillsBench, Evaluating Memory in LLM Agents via Incremental Multi-Turn Interactions, and CUBE.
  - The current accepted eval shortlist is incomplete if it is derived from `research/intake/records` alone. There are 31 relevant eval-oriented paper captures under `research/sources/papers/` that do not currently have intake record coverage.
  - `src_pap_8ffcaa41e955` is misindexed in intake metadata. The record title says LiveCodeBench, but the local capture title is `LOCA-bench: Benchmarking Language Agents Under Controllable and Extreme Context Growth`.
  - `Terminal-Bench` is duplicated locally as both `src_pap_f6aa42bfdc1a` and `src_pap_dd4ca3841fb4`; the principal synthesis pass should pick one canonical path and ignore the duplicate.
  - 7 of the 29 accepted `evals_benchmarking` sources have no `artifact_relpath`, so the accepted manifest currently overstates how much directly openable local evidence exists.
  - Required-family check:
  - `ContextBench`: important and missing as a real local source; only a postmortem/blog-style mention exists.
  - `tau2-bench`: important and only partially represented through DeepAgents' airline subset.
  - `BFCL`: partially represented through DeepAgents curated BFCL v3 cases and local API stubs, but not mirrored as a full official benchmark.
  - `FRAMES`: partially represented through curated DeepAgents cases only.
  - `Nexus`: partially represented through curated DeepAgents cases only.
  - `MemoryAgentBench`: partially represented through a DeepAgents runner, but the official repo is not mirrored.
  - `WebArena family`: only WebArena-Infinity is locally captured; canonical WebArena and VisualWebArena are absent.
  - `SWE-bench / Verified`: strongly represented by papers, site capture, SWE-agent adjacent code, and A-Evolve adapters, but the official SWE-bench repo is not mirrored.
- local_eval_codebases:
  - `research/sources/codebases/deepagents/libs/evals`: full local eval suite with category taxonomy, Harbor integration, LangSmith reporting, external benchmark adapters, and judge logic.
  - `research/sources/codebases/langchain/agentevals`: trajectory matching and trajectory LLM-as-judge evaluators.
  - `research/sources/codebases/langchain/openevals`: general LLM-as-judge, code, safety, RAG, and trajectory evaluators.
  - `research/sources/codebases/a-evolve/agent_evolve/benchmarks`: benchmark adapters for Terminal-Bench, SWE Verified mini, MCP-Atlas, and SkillBench.
  - `research/sources/codebases/src_cod_e231561a3d69`: SWE-agent standardized trajectories and deterministic replay capture.
  - `evals/` plus `runner/evaluator.py`: local project eval stubs exist, but they are still lightweight placeholders compared with the mirrored research code.
- benchmark_captures:
  - `research/sources/benchmarks/src_bnm_8c3b5dc456f5`: ImpossibleBench.
  - `research/sources/benchmarks/src_bnm_e5f985948a0e`: SWE-bench Verified and Scale-SWE Automation.
  - `research/sources/benchmarks/src_bnm_e1cfa2bf78c9`: WebArena-Infinity.
  - `research/sources/benchmarks/src_bnm_f6e5d4c3b2a1`: SlopCodeBench.
  - `research/sources/benchmarks/src_bnm_facefeed2020`: NIKA Network Arena.
- trajectory_assets_relevant_to_evals:
  - `research/sources/trajectories/BigAI`: 89 shared task folders with paired `*-traj.txt` and `*.tar.gz` assets.
  - `research/sources/trajectories/deepagents`: 89 shared task folders.
  - `research/sources/trajectories/terminus-kira`: 89 shared task folders.
  - Together these give a practical basis for scorer design, step-efficiency analysis, failure-mode clustering, and benchmark-sensitive harness comparisons without new data collection.
- repo_mirror_now:
  - `safety-research/impossiblebench`: direct anti-cheat benchmark logic; high first-wave value and only captured as a benchmark page today.
  - `EuniAI/ContextBench`: process-oriented context retrieval metrics are a genuine gap in the current local mirror set.
  - `HUST-AI-HYZ/MemoryAgentBench`: core memory family, with current local coverage limited to a paper capture plus a DeepAgents runner that still depends on external data.
  - `sierra-research/tau-bench`: direct relevance to multi-turn tool-agent-user evaluation; current local coverage is only the airline-derived subset in DeepAgents.
  - `SWE-bench/SWE-bench`: central SWE task schemas, harness logic, and verified benchmark structure remain unmirrored despite strong adjacent local evidence.
- repo_mirror_later:
  - official BFCL repo: high value, but DeepAgents already preserves enough curated BFCL v3 cases for first-wave synthesis.
  - official FRAMES source or dataset wrapper: useful, but local curated FRAMES cases are sufficient for first-wave synthesis.
  - official Nexus source: same rationale as FRAMES.
  - `web-arena-x/webarena`: important browser family, but likely second-wave for this project unless browser/GUI moves into the first planned eval slice.
  - `web-arena-x/visualwebarena`: useful extension of the browser family, but clearly later than terminal/SWE/MCP/integrity mirroring.
  - MCPAgentBench official repo if public code is confirmed: direct relevance is high, but repo provenance/location was not confirmed in this pass.
  - AgentLongBench / DeepPlanning repos or datasets if public code is confirmed: both matter, but the current first-wave need is triage and metadata normalization, not broad mirror expansion.
- docs_only_sources:
  - Terminal-Bench paper and trajectory corpus cluster.
  - Efficient Benchmarking of AI Agents.
  - Establishing Best Practices in Building Rigorous Agentic Benchmarks.
  - Bloom.
  - MALT.
  - Claude Sonnet 4.6, Deep Research, and GPT-5.3-Codex system cards.
  - WebArena-Infinity capture for environment-generation/verifier design signal.
  - CursorBench, CIRCLE, and EVMbench informal captures.
  - SWE-rebench paper.
- quarantine_sources:
  - `research/sources/codebases/quarantine/claw-code`: keep quarantined. The path is already explicitly quarantined locally, and it should not be promoted into first-wave eval synthesis.
- open_questions:
  - What is the canonical public repo for BFCL that should be mirrored, if the project wants the full evaluator rather than DeepAgents' curated subset?
  - Is there a public MCPAgentBench repo with runnable code, or only paper/dataset artifacts at this stage?
  - Which Terminal-Bench capture should be treated as canonical: `src_pap_f6aa42bfdc1a` or `src_pap_dd4ca3841fb4`?
  - Should browser / GUI evaluation stay second-wave for synthesis, or should canonical WebArena-family mirroring be pulled forward now?
  - Should the project backfill missing intake records before deep synthesis, or accept that first-wave synthesis must read directly from `research/sources/*` as well as intake metadata?
- recommended_next_step:
  - Run one cleanup-and-triage slice before deep synthesis:
  - backfill missing intake records for the high-value local captures currently absent from `research/intake/records`;
  - fix the `src_pap_8ffcaa41e955` title mismatch;
  - mark one canonical Terminal-Bench capture;
  - mirror the five `mirror now` repos;
  - then hand the normalized first-wave source set to the deep synthesis pass.

EVAL_INVENTORY_TABLE
- eval_name: Terminal-Bench
  source_type: paper
  target_layer: end-to-end, integrity / anti-cheat
  target_domain: terminal, software engineering, verification
  local_path: research/sources/papers/src_pap_f6aa42bfdc1a
  repo_status: unknown
  mirror_recommendation: docs-only
  why_it_matters: The most directly relevant benchmark-spec source for the project mission, including verifier, audit, and anti-cheat design.
  confidence: high
- eval_name: Terminal-Bench Comparative Trajectory Corpora
  source_type: trajectory corpus
  target_layer: interaction, end-to-end, robustness
  target_domain: terminal, planning, verification, software engineering
  local_path: research/sources/trajectories
  repo_status: mirrored
  mirror_recommendation: docs-only
  why_it_matters: Three harness families over the same 89-task set give unusually strong local evidence for scorer design and failure analysis.
  confidence: high
- eval_name: Efficient Benchmarking of AI Agents
  source_type: paper
  target_layer: end-to-end, integrity / anti-cheat
  target_domain: terminal, browser, tool-use, software engineering
  local_path: research/sources/papers/src_pap_70b31c72af76
  repo_status: unknown
  mirror_recommendation: docs-only
  why_it_matters: Best local source on cost-aware cross-benchmark harnessing and reproducible large-scale agent evaluation.
  confidence: high
- eval_name: Establishing Best Practices in Building Rigorous Agentic Benchmarks
  source_type: paper
  target_layer: integrity / anti-cheat
  target_domain: verification, safety / security, software engineering
  local_path: research/sources/papers/src_pap_c5f42ff16ea3
  repo_status: unknown
  mirror_recommendation: docs-only
  why_it_matters: High-signal methodology source for contamination, exploit resistance, rubric quality, and benchmark governance.
  confidence: high
- eval_name: Holistic Agent Leaderboard
  source_type: paper
  target_layer: end-to-end, integrity / anti-cheat
  target_domain: browser, tool-use, software engineering, cost, observability
  local_path: research/intake/records/src_pap_1230097168db.json
  repo_status: unknown
  mirror_recommendation: docs-only
  why_it_matters: Strong source on standardized multi-benchmark harnessing, log release, and scaffold-level analysis, but local artifact access is weaker than the record suggests.
  confidence: medium
- eval_name: ImpossibleBench
  source_type: benchmark capture
  target_layer: integrity / anti-cheat
  target_domain: software engineering, verification, safety / security
  local_path: research/sources/benchmarks/src_bnm_8c3b5dc456f5
  repo_status: not mirrored
  mirror_recommendation: mirror now
  why_it_matters: Direct anti-cheat benchmark implementation with impossible-task framing, honesty shifts, and specification-gaming signal.
  confidence: high
- eval_name: PostTrainBench
  source_type: paper
  target_layer: integrity / anti-cheat, end-to-end
  target_domain: software engineering, verification
  local_path: research/sources/papers/src_pap_80760cf676b4
  repo_status: unknown
  mirror_recommendation: docs-only
  why_it_matters: High-value judge-integrity source because it focuses on anti-cheat judges rather than just task outcomes.
  confidence: high
- eval_name: MALT
  source_type: doc
  target_layer: integrity / anti-cheat
  target_domain: safety / security, verification
  local_path: research/sources/docs/src_doc_f93fa0aea2d6
  repo_status: not mirrored
  mirror_recommendation: docs-only
  why_it_matters: Ground-truth eval-integrity transcript dataset for reward hacking, sandbagging, and benign-control comparisons.
  confidence: high
- eval_name: Bloom
  source_type: doc
  target_layer: robustness, integrity / anti-cheat
  target_domain: safety / security, verification
  local_path: research/sources/docs/src_doc_f2f6a3c7bbc6
  repo_status: not mirrored
  mirror_recommendation: docs-only
  why_it_matters: Practical open-source behavioral evaluation tooling from a frontier lab.
  confidence: high
- eval_name: DeepAgents Evals
  source_type: code mirror
  target_layer: dependent-part, interaction, end-to-end
  target_domain: memory, context, tool-use, planning, verification, software engineering
  local_path: research/sources/codebases/deepagents/libs/evals
  repo_status: mirrored
  mirror_recommendation: docs-only
  why_it_matters: Strongest local eval implementation asset, already covering judge logic, reporting, external benchmark subsets, and Harbor/LangSmith integration.
  confidence: high
- eval_name: AgentEvals
  source_type: code mirror
  target_layer: dependent-part, interaction
  target_domain: tool-use, trajectory scoring, verification
  local_path: research/sources/codebases/langchain/agentevals
  repo_status: mirrored
  mirror_recommendation: docs-only
  why_it_matters: Reusable trajectory evaluators and LLM-as-judge scaffolding for agent behavior.
  confidence: high
- eval_name: OpenEvals
  source_type: code mirror
  target_layer: atomic, dependent-part
  target_domain: verification, safety / security, code, trajectory scoring
  local_path: research/sources/codebases/langchain/openevals
  repo_status: mirrored
  mirror_recommendation: docs-only
  why_it_matters: General evaluator library with code, security, RAG, multimodal, and trajectory evaluation components.
  confidence: high
- eval_name: ContextBench
  source_type: informal plus external repo gap
  target_layer: dependent-part
  target_domain: context, software engineering
  local_path: research/intake/records/src_pmt_e0628ecf9702.json
  repo_status: not mirrored
  mirror_recommendation: mirror now
  why_it_matters: The current local corpus lacks a real process-oriented context retrieval benchmark mirror, and this is the clearest missing family.
  confidence: high
- eval_name: tau-bench / tau2 airline subset
  source_type: code mirror
  target_layer: interaction, end-to-end
  target_domain: tool-use, planning, verification
  local_path: research/sources/codebases/deepagents/libs/evals/tests/evals/tau2_airline
  repo_status: not mirrored
  mirror_recommendation: mirror now
  why_it_matters: DeepAgents only preserves the airline-derived subset; the official tau-bench family is important for multi-turn tool-agent-user evaluation.
  confidence: high
- eval_name: MemoryAgentBench
  source_type: paper plus code mirror
  target_layer: interaction, end-to-end
  target_domain: memory, context
  local_path: research/sources/papers/src_pap_41dd6013eb25; research/sources/codebases/deepagents/libs/evals/tests/evals/memory_agent_bench
  repo_status: not mirrored
  mirror_recommendation: mirror now
  why_it_matters: Core memory eval family; current local runner still depends on external data and does not preserve the full upstream benchmark.
  confidence: high
- eval_name: MemoryArena
  source_type: paper
  target_layer: interaction, end-to-end
  target_domain: memory
  local_path: research/sources/papers/src_pap_4c58a9fc09b8
  repo_status: unknown
  mirror_recommendation: mirror later
  why_it_matters: Strong benchmark for interdependent multi-session memory, currently missing from intake indexing.
  confidence: high
- eval_name: DeepPlanning
  source_type: paper
  target_layer: end-to-end
  target_domain: planning, verification
  local_path: research/sources/papers/2601.18137.pdf
  repo_status: unknown
  mirror_recommendation: mirror later
  why_it_matters: Important long-horizon planning benchmark family that exists locally only as a PDF and is absent from intake records.
  confidence: medium
- eval_name: AgentLongBench
  source_type: paper
  target_layer: end-to-end, robustness
  target_domain: context, planning
  local_path: research/sources/papers/2601.20730.pdf
  repo_status: unknown
  mirror_recommendation: mirror later
  why_it_matters: Important long-context agent benchmark family that is locally present only as a PDF and currently underweighted.
  confidence: medium
- eval_name: SWE-bench Verified
  source_type: benchmark capture
  target_layer: end-to-end, integrity / anti-cheat
  target_domain: software engineering, verification
  local_path: research/sources/benchmarks/src_bnm_e5f985948a0e
  repo_status: not mirrored
  mirror_recommendation: mirror now
  why_it_matters: Central SWE benchmark family for the project, with strong local adjacency but no official benchmark repo mirror.
  confidence: high
- eval_name: SWE-agent Deterministic Replay
  source_type: code mirror
  target_layer: interaction, end-to-end
  target_domain: software engineering, verification, observability
  local_path: research/sources/codebases/src_cod_e231561a3d69
  repo_status: mirrored
  mirror_recommendation: docs-only
  why_it_matters: Preserves standardized trajectories and replay structure, which is directly useful for eval reproducibility analysis.
  confidence: high
- eval_name: SWE-rebench
  source_type: paper
  target_layer: end-to-end, integrity / anti-cheat
  target_domain: software engineering, verification
  local_path: research/sources/papers/src_pap_b4d59442a63d
  repo_status: unknown
  mirror_recommendation: docs-only
  why_it_matters: Direct source on automated task collection and decontaminated SWE evaluation.
  confidence: high
- eval_name: MCPAgentBench
  source_type: paper
  target_layer: end-to-end
  target_domain: MCP, tool-use, verification
  local_path: research/sources/papers/src_pap_d4370863a7e0
  repo_status: unknown
  mirror_recommendation: mirror now
  why_it_matters: Directly relevant benchmark family for MCP tool use, but it is effectively hidden today because the local capture is not backfilled into intake records.
  confidence: medium
- eval_name: WebArena-Infinity
  source_type: benchmark capture
  target_layer: end-to-end
  target_domain: browser, verification
  local_path: research/sources/benchmarks/src_bnm_e1cfa2bf78c9
  repo_status: not mirrored
  mirror_recommendation: docs-only
  why_it_matters: Useful local source on generated browser environments and decoupled verification APIs, even though the broader WebArena family is still missing.
  confidence: high
- eval_name: A-Evolve Benchmark Adapters
  source_type: code mirror
  target_layer: end-to-end
  target_domain: terminal, MCP, software engineering
  local_path: research/sources/codebases/a-evolve/agent_evolve/benchmarks
  repo_status: mirrored
  mirror_recommendation: docs-only
  why_it_matters: Concrete benchmark-runner and adapter logic spanning Terminal-Bench, MCP-Atlas, SWE Verified mini, and SkillBench.
  confidence: high
- eval_name: BFCL, FRAMES, and Nexus Curated Cases
  source_type: code mirror
  target_layer: dependent-part, interaction
  target_domain: tool-use, context, planning
  local_path: research/sources/codebases/deepagents/libs/evals/tests/evals/external_benchmarks.py
  repo_status: mirrored
  mirror_recommendation: mirror later
  why_it_matters: First-wave local coverage already exists, but only as curated hard subsets rather than full benchmark mirrors.
  confidence: high
- eval_name: OS-HARM
  source_type: paper
  target_layer: end-to-end, robustness
  target_domain: GUI, safety / security
  local_path: research/sources/papers/src_pap_b4277c809d70
  repo_status: unknown
  mirror_recommendation: docs-only
  why_it_matters: One of the clearest local GUI/OS-agent safety eval sources, useful for browser/GUI family gap assessment.
  confidence: high
- eval_name: DigiData
  source_type: paper
  target_layer: end-to-end
  target_domain: GUI, tool-use
  local_path: research/sources/papers/src_pap_1e57c6e6d27b
  repo_status: unknown
  mirror_recommendation: docs-only
  why_it_matters: Adds mobile-control eval coverage to an otherwise terminal-heavy local corpus.
  confidence: medium
- eval_name: CursorBench
  source_type: informal
  target_layer: end-to-end
  target_domain: software engineering, context, efficiency
  local_path: research/sources/informal/cursor_cursorbench.md
  repo_status: unknown
  mirror_recommendation: docs-only
  why_it_matters: Strong engineering writeup on online-offline eval alignment, benchmark saturation, and contamination pressures.
  confidence: high
- eval_name: CIRCLE
  source_type: informal
  target_layer: robustness, integrity / anti-cheat
  target_domain: safety / security, evaluation methodology
  local_path: research/sources/informal/cohere_circle_eval.md
  repo_status: unknown
  mirror_recommendation: docs-only
  why_it_matters: Useful real-world evaluation framework that broadens the local corpus beyond static benchmark design.
  confidence: medium
- eval_name: EVMbench
  source_type: informal
  target_layer: end-to-end, integrity / anti-cheat
  target_domain: safety / security, verification, software engineering
  local_path: research/sources/informal/openai_evmbench.md
  repo_status: unknown
  mirror_recommendation: docs-only
  why_it_matters: Strong domain-specific example of harnessed exploit, patch, and detect evaluation with anti-cheat grader hardening.
  confidence: medium
- eval_name: LOCA-bench (misindexed as LiveCodeBench in intake)
  source_type: paper
  target_layer: robustness
  target_domain: context
  local_path: research/sources/papers/src_pap_8ffcaa41e955
  repo_status: unknown
  mirror_recommendation: docs-only
  why_it_matters: Important mainly because it reveals a shortlist integrity problem: the accepted eval manifest currently points to the wrong local capture for LiveCodeBench.
  confidence: high
- eval_name: LiveCodeBench
  source_type: paper
  target_layer: end-to-end, integrity / anti-cheat
  target_domain: software engineering, verification
  local_path: none; only indirect mentions and mislabeled intake metadata are local today
  repo_status: not mirrored
  mirror_recommendation: mirror later
  why_it_matters: Widely referenced contamination-resistant coding benchmark family, but not actually available as a direct local capture in the current corpus.
  confidence: high
- eval_name: claw-code
  source_type: code mirror
  target_layer: end-to-end
  target_domain: software engineering, terminal
  local_path: research/sources/codebases/quarantine/claw-code
  repo_status: quarantined
  mirror_recommendation: quarantine
  why_it_matters: Already locally quarantined; should not be promoted into first-wave eval synthesis without provenance resolution.
  confidence: high
