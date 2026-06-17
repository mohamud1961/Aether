LITERATURE_DOSSIER
- dossier_type: theme
- topic: context_and_memory
- scope:
  - Formal-source routing for Wave 04 claims about bounded context, working memory, compaction, persistent memory, retrieval, and long-context rhetoric.
  - Focus on papers and official docs that sharpen the difference between within-episode context/state handling and cross-session memory.
- primary_sources:
  - `research/sources/papers/papers_text/2512.13564.txt`
  - `research/sources/papers/papers_text/src_pap_b191e17f02bb.txt`
  - `research/sources/papers/papers_text/2510.11967.txt`
  - `research/sources/papers/papers_text/src_pap_91068d0d956d.txt`
  - `research/sources/papers/papers_text/src_pap_4c58a9fc09b8.txt`
  - `research/sources/docs/src_doc_126e07cf0d68/artifact.txt`
  - `research/sources/docs/src_doc_2e0f17682ffb/artifact.txt`
  - `research/sources/docs/src_doc_07fd01b8b76a/artifact.txt`
  - `research/sources/docs/src_doc_118b78fe9c63/artifact.txt`
  - `research/sources/docs/bigai/raw/sdk_documentation_memory.txt`
  - `research/sources/docs/bigai/translated/sdk_agent_core.md`
- secondary_sources:
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/outputs/trajectory_support_context_workspace_matrix.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/synthesis/cumulative_synthesis.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/synthesis/principal_synthesis.md`
- coverage_used:
  - `research/sources/papers/papers_text/2512.13564.txt`
  - `research/sources/papers/papers_text/src_pap_b191e17f02bb.txt`
  - `research/sources/papers/papers_text/2510.11967.txt`
  - `research/sources/papers/papers_text/src_pap_91068d0d956d.txt`
  - `research/sources/papers/papers_text/src_pap_4c58a9fc09b8.txt`
  - `research/sources/docs/src_doc_126e07cf0d68/artifact.txt`
  - `research/sources/docs/src_doc_2e0f17682ffb/artifact.txt`
  - `research/sources/docs/src_doc_07fd01b8b76a/artifact.txt`
  - `research/sources/docs/src_doc_118b78fe9c63/artifact.txt`
  - `research/sources/docs/bigai/raw/sdk_documentation_memory.txt`
  - `research/sources/docs/bigai/translated/sdk_agent_core.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/outputs/trajectory_support_context_workspace_matrix.md`
- coverage_not_yet_used:
  - `research/sources/papers/papers_text/2510.04618.txt`
  - `research/sources/papers/papers_text/2603.09619.txt`
  - `research/sources/papers/papers_text/src_pap_0655c8a420ca.txt`
  - `research/sources/papers/papers_text/src_pap_ef174e4a1f48.txt`
  - `research/sources/papers/papers_text/src_pap_f2bc990ed39f.txt`
  - `research/sources/papers/papers_text/src_pap_703731e7c236.txt`
  - `research/sources/docs/src_doc_1069e67c4fe5/artifact.txt`
  - `research/sources/docs/bigai/translated/framework_multi_agent.md`
- evidence_classes_touched:
  - papers
  - docs
  - support_artifact
  - prior_wave_synthesis
- priority_sources_not_yet_read:
  - `research/sources/papers/papers_text/2510.04618.txt`
  - `research/sources/papers/papers_text/2603.09619.txt`
  - `research/sources/papers/papers_text/src_pap_f2bc990ed39f.txt`
  - `research/sources/papers/papers_text/src_pap_703731e7c236.txt`
- formal_claims:
  - |
    Claim 1
    Observation: `2512.13564` explicitly separates agent memory from context engineering, and further separates factual, experiential, and working memory. It defines working memory as active, within-episode manipulation of context rather than passive transcript retention.
    Inference: For Wave 04, "context/state/memory" should not be promoted as one mechanism family. The cleanest formal split is: bounded working context; persistent factual/experiential memory; and external engineering scaffolds that schedule what enters the window.
    Confidence: high
    Evidence: `research/sources/papers/papers_text/2512.13564.txt`
  - |
    Claim 2
    Observation: `src_pap_b191e17f02bb` and `2510.11967` both formalize long-horizon context handling as a structured workspace with stable anchors, a condensed long-term summary, and a recent high-fidelity working segment; they make folding/compression an explicit action rather than a hidden afterthought.
    Inference: The strongest formal context-management family in this wave is not generic "memory", but active working-memory control through staged folding, summary write-back, and recent-window preservation.
    Confidence: high
    Evidence: `research/sources/papers/papers_text/src_pap_b191e17f02bb.txt`, `research/sources/papers/papers_text/2510.11967.txt`
  - |
    Claim 3
    Observation: Anthropic's context-engineering doc and OpenAI's compaction/sessions docs all treat context as a finite operating budget and provide explicit machinery for compaction or session-backed continuation. OpenAI's compaction item is intentionally opaque, while session storage persists conversation items outside the active turn.
    Inference: Official docs converge on a substrate distinction: compaction preserves enough state for the next window, while sessions persist conversation history outside the window. This sharpens Wave 04's separation between active context and external state carriers.
    Confidence: high
    Evidence: `research/sources/docs/src_doc_126e07cf0d68/artifact.txt`, `research/sources/docs/src_doc_2e0f17682ffb/artifact.txt`, `research/sources/docs/src_doc_07fd01b8b76a/artifact.txt`
  - |
    Claim 4
    Observation: `src_pap_91068d0d956d` frames persistent-agent design as a choice between replaying full history and retrieving distilled facts from a memory store, with break-even economics favoring fact memory as histories and turn counts grow. `src_pap_4c58a9fc09b8` argues that recall-only long-context benchmarks do not measure whether memory guides later action in multi-session agent loops.
    Inference: Formal benchmark and systems literature now pressures Wave 04 to keep retrieval-based memory and long-context replay separate, and to evaluate them against multi-session action settings rather than recall-only QA.
    Confidence: medium
    Evidence: `research/sources/papers/papers_text/src_pap_91068d0d956d.txt`, `research/sources/papers/papers_text/src_pap_4c58a9fc09b8.txt`
    Weakener: Both sources are benchmark- and conversational-agent-heavy; they are not coding-agent or workspace-first by default.
  - |
    Claim 5
    Observation: BigAI formal docs define memory as message-based storage/recall, with `SimpleMemory` as in-memory runtime storage and `PersistenceMemory` as durable backing storage; the translated agent core says `AgentRunContext` defaults to `SimpleMemory`.
    Inference: BigAI's formal surface supports a conventional memory-subsystem reading, but this remains formal intent rather than source-backed or behaviorally saturated proof of how Wave 04 state was actually carried in observed runs.
    Confidence: medium
    Evidence: `research/sources/docs/bigai/raw/sdk_documentation_memory.txt`, `research/sources/docs/bigai/translated/sdk_agent_core.md`
    Weakener: In Wave 04 carry-forward, BigAI remains behavioral reconstruction on stronger implementation claims.
- benchmark_or_definition_notes:
  - `2512.13564` is the most useful definitional anchor in the current slice because it explicitly distinguishes agent memory, RAG, and context engineering and gives a working-memory definition that matches Wave 04 needs.
  - `src_pap_4c58a9fc09b8` is the best benchmark-definition source in this pass because it defines a multi-session Memory-Agent-Environment loop where later actions depend on retained state from earlier sessions.
  - `src_pap_91068d0d956d` is useful for cost/performance framing, but it operationalizes memory mainly as fact extraction versus long-context replay in persistent conversational settings.
- mechanism_relevance:
  - Strongly supports a Wave 04 family for active working-memory management via compaction/folding.
  - Supports a second family for persistent external memory, but only as a formal category that must not outrank stronger artifact/workspace evidence.
  - Supports keeping restart/resume substrate separate from general memory rhetoric.
- failure_relevance:
  - Formal literature repeatedly warns about context rot, context explosion, and semantic drift under append-only histories.
  - The same literature under-specifies stale memory, incorrect write paths, and durability failures relative to the more concrete direct evidence pressure in trajectories.
- eval_relevance:
  - MemoryArena is a strong formal pointer that recall-only memory benchmarks are insufficient for agentic evaluation.
  - The cost paper is useful for future eval implications around long-context versus memory-store tradeoffs, but not yet enough to bind Wave 04 mechanism ranking.
- contradictions:
  - The formal slice often treats compaction and persistent memory as if they produce stable continuity by construction; the trajectory support artifact shows most current Wave 04 state continuity coming from todo lists, saved scripts, restored files, and clean repo state rather than a visible durable memory subsystem.
  - Sessions/checkpoints/compaction docs provide substrate definitions for persistence and restoration, but accepted prior synthesis still treats restart/resumability as under-evidenced behaviorally rather than established cross-family fact.
  - BigAI formal memory docs imply a configurable memory stack, but current wave-wide stronger evidence still supports only behavioral reconstruction for BigAI mechanism claims.
- confidence_notes:
  - High confidence in the context-versus-memory distinction and in active working-memory as a real formal family.
  - Medium confidence in using memory benchmark papers as direct support for coding-agent Wave 04 conclusions because their evaluation regimes are adjacent rather than identical.
  - Medium confidence in BigAI formal-memory implications because the docs are available but stronger source/behavior reconciliation remains incomplete.
- open_questions:
  - Which unread papers best pressure stale-memory and incorrect-write failure modes rather than just memory usefulness rhetoric?
  - Do any unread formal sources give a stronger treatment of artifact discipline as a memory substitute in coding agents?
  - Should `2512.13564` or `2512.05470` graduate to anchor-dossier status after contradiction review?
- downstream_use:
  - Use this dossier to keep Wave 04 mechanism cards split between working-memory control and persistent external memory.
  - Use it to resist flattening artifact-backed workspace continuity into "long-term memory".
  - Use it as formal pressure for future `eval_implications` on recall-only memory benchmarks versus multi-session action benchmarks.
- wave_03_context_state_memory_workspace_failures_update_2026_04_10:
  - source_scope_delta:
    - `research/sources/papers/papers_text/2512.13564.txt`
    - `research/sources/papers/papers_text/src_pap_b191e17f02bb.txt`
    - `research/sources/papers/papers_text/2510.11967.txt`
    - `research/sources/docs/src_doc_2e0f17682ffb/artifact.txt`
    - `research/sources/docs/src_doc_07fd01b8b76a/artifact.txt`
    - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/codebase_source_reconstruction_analyst.md`
  - observations:
    - formal sources continue to separate bounded working-context control from persistent memory categories.
    - compaction and session docs define substrate patterns but do not guarantee successful state reinjection or recovery in stressed coding-agent runs.
    - Wave 03 codebase lane evidence shows concrete compaction fallback and clipped retrieval pressure, matching literature warnings while preserving mechanism-specific attribution.
  - inference:
    - failure taxonomy should keep `compaction/folding failure`, `stale retrieval`, and `session persistence drift` as distinct classes.
    - do not use formal context-memory literature to override stronger source/trajectory evidence on system-specific failure behavior.
  - confidence:
    - high on conceptual class separation
    - medium on direct transfer from formal literature to coding-agent prevalence
  - evidence_paths:
    - `research/sources/papers/papers_text/2512.13564.txt`
    - `research/sources/papers/papers_text/src_pap_b191e17f02bb.txt`
    - `research/sources/papers/papers_text/2510.11967.txt`
    - `research/sources/docs/src_doc_2e0f17682ffb/artifact.txt`
    - `research/sources/docs/src_doc_07fd01b8b76a/artifact.txt`
    - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/codebase_source_reconstruction_analyst.md`

Wave 03 failure-taxonomy addendum (2026-04-10)

- wave: `failure_taxonomy/wave_03_context_state_memory_workspace_failures`
- focus: formal failure attribution for context-loss, stale-summary, and persistence/resume contract failures
- coverage_used_wave_03:
  - `research/sources/papers/papers_text/2512.13564.txt`
  - `research/sources/papers/papers_text/src_pap_b191e17f02bb.txt`
  - `research/sources/papers/papers_text/2510.11967.txt`
  - `research/sources/papers/papers_text/src_pap_8ffcaa41e955.txt`
  - `research/sources/papers/papers_text/src_pap_9dbf664b6954.txt`
  - `research/sources/papers/papers_text/src_pap_91068d0d956d.txt`
  - `research/sources/docs/src_doc_126e07cf0d68/artifact.txt`
  - `research/sources/docs/src_doc_2e0f17682ffb/artifact.txt`
  - `research/sources/docs/src_doc_07fd01b8b76a/artifact.txt`
  - `research/sources/docs/src_doc_118b78fe9c63/artifact.txt`
- formal_failure_attribution_claims_wave_03:
  - |
    Claim W03-CM-1
    Observation: long-context and agentic-context formal sources describe measurable degradation under context growth and position sensitivity.
    Inference: context-overflow and mid-context retrieval-loss should be tracked as first-class failure families, not blended into generic model weakness.
    Confidence: high
    Evidence: `research/sources/papers/papers_text/src_pap_8ffcaa41e955.txt`, `research/sources/papers/papers_text/src_pap_9dbf664b6954.txt`, `research/sources/docs/src_doc_126e07cf0d68/artifact.txt`
  - |
    Claim W03-CM-2
    Observation: compaction/folding methods are explicitly state-transforming operations and can reduce token pressure while risking summary-loss or trigger-policy errors.
    Inference: compaction failures should be attributed as context-state operator failures (timing/content/merge policy) before assigning model-only blame.
    Confidence: medium
    Evidence: `research/sources/papers/papers_text/2510.11967.txt`, `research/sources/papers/papers_text/src_pap_b191e17f02bb.txt`, `research/sources/docs/src_doc_2e0f17682ffb/artifact.txt`
  - |
    Claim W03-CM-3
    Observation: session/checkpoint docs define explicit resume contracts and state merge boundaries.
    Inference: resume failures can be harness/session contract failures even when model reasoning is nominal.
    Confidence: medium
    Evidence: `research/sources/docs/src_doc_07fd01b8b76a/artifact.txt`, `research/sources/docs/src_doc_118b78fe9c63/artifact.txt`
- direct_evidence_tension_wave_03:
  - Formal memory-layer richness remains stronger than currently demonstrated trajectory-visible use; keep durable-memory dominance unpromoted without direct run evidence.
  - Evidence: `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/synthesis/principal_synthesis.md`

- wave_03_literature_lane_refresh_2026_04_11:
  - source_scope_delta:
    - `research/sources/papers/papers_text/2512.13564.txt`
    - `research/sources/papers/papers_text/src_pap_b191e17f02bb.txt`
    - `research/sources/papers/papers_text/2510.11967.txt`
    - `research/sources/papers/papers_text/src_pap_8ffcaa41e955.txt`
    - `research/sources/papers/papers_text/src_pap_9dbf664b6954.txt`
    - `research/sources/docs/src_doc_126e07cf0d68/artifact.txt`
    - `research/sources/docs/src_doc_2e0f17682ffb/artifact.txt`
    - `research/sources/docs/src_doc_07fd01b8b76a/artifact.txt`
    - `research/sources/docs/src_doc_118b78fe9c63/artifact.txt`
    - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/literature_papers_docs_analyst.md`
  - observations:
    - formal sources continue to split bounded working context from persistent memory and session-state substrates.
    - long-context benchmark evidence keeps context growth and position sensitivity as explicit degradation channels.
    - compaction/folding is treated as a policy surface (trigger, boundary, summary quality), not a guaranteed-safe reduction step.
  - inference:
    - Wave 03 failure taxonomy should keep `context-window/position loss`, `compaction operator failure`, and `session persistence/resume-state drift` separated.
    - formal claims should bound confidence until trajectory and codebase lanes confirm prevalence and cause distribution.
  - confidence:
    - high on class-boundary separation
    - medium on transfer from benchmark behavior to required trajectory frequency
  - evidence_paths:
    - `research/sources/papers/papers_text/2512.13564.txt`
    - `research/sources/papers/papers_text/src_pap_b191e17f02bb.txt`
    - `research/sources/papers/papers_text/2510.11967.txt`
    - `research/sources/papers/papers_text/src_pap_8ffcaa41e955.txt`
    - `research/sources/papers/papers_text/src_pap_9dbf664b6954.txt`
    - `research/sources/docs/src_doc_126e07cf0d68/artifact.txt`
    - `research/sources/docs/src_doc_2e0f17682ffb/artifact.txt`
    - `research/sources/docs/src_doc_07fd01b8b76a/artifact.txt`
    - `research/sources/docs/src_doc_118b78fe9c63/artifact.txt`
