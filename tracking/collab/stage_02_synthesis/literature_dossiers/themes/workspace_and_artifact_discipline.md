LITERATURE_DOSSIER
- dossier_type: theme
- topic: workspace_and_artifact_discipline
- scope:
  - Formal-source routing for Wave 04 claims about file-native context, workspace scaffolding, artifact persistence, instruction files, task scratchpads, and governed context repositories.
  - Focus on sources that treat the filesystem, instruction files, and explicit artifacts as first-class agent state surfaces.
- primary_sources:
  - `research/sources/papers/papers_text/2512.05470.txt`
  - `research/sources/papers/papers_text/2602.05447.txt`
  - `research/sources/docs/src_doc_126e07cf0d68/artifact.txt`
  - `research/sources/docs/src_doc_29494193a1c5/artifact.txt`
  - `research/sources/docs/bigai/translated/sdk_workflow.md`
  - `research/sources/docs/bigai/translated/sdk_agent_core.md`
- secondary_sources:
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/outputs/trajectory_support_context_workspace_matrix.md`
  - `tracking/collab/stage_02_synthesis/coverage_register/current_status.md`
- coverage_used:
  - `research/sources/papers/papers_text/2512.05470.txt`
  - `research/sources/papers/papers_text/2602.05447.txt`
  - `research/sources/docs/src_doc_126e07cf0d68/artifact.txt`
  - `research/sources/docs/src_doc_29494193a1c5/artifact.txt`
  - `research/sources/docs/bigai/translated/sdk_workflow.md`
  - `research/sources/docs/bigai/translated/sdk_agent_core.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/outputs/trajectory_support_context_workspace_matrix.md`
- coverage_not_yet_used:
  - `research/sources/docs/src_doc_31348971d5a0/artifact.txt`
  - `research/sources/docs/src_doc_0036f83a1758/artifact.txt`
  - `research/sources/docs/bigai/translated/framework_multi_agent.md`
  - `research/sources/papers/papers_text/src_pap_575afb401440.txt`
- evidence_classes_touched:
  - papers
  - docs
  - support_artifact
- priority_sources_not_yet_read:
  - `research/sources/docs/src_doc_31348971d5a0/artifact.txt`
  - `research/sources/docs/bigai/translated/framework_multi_agent.md`
  - `research/sources/papers/papers_text/src_pap_575afb401440.txt`
- formal_claims:
  - |
    Claim 1
    Observation: `2512.05470` treats context engineering as a persistent, governed file-system abstraction that unifies history, memory, and scratchpad. It explicitly models scratchpads as temporary workspaces and memory/history as external state outside the bounded token window.
    Inference: This is the strongest formal source in the current slice for workspace-as-state-carrier. It supports a Wave 04 mechanism family centered on explicit artifact scaffolding and governed repositories rather than latent internal memory alone.
    Confidence: high
    Evidence: `research/sources/papers/papers_text/2512.05470.txt`
  - |
    Claim 2
    Observation: `2602.05447` empirically studies file-native agent context and explicitly names `CLAUDE.md`, `AGENTS.md`, and similar instruction files as part of the rise of file-based semantic layers. It finds model-dependent benefits for file-native retrieval and warns about the grep tax from dense or unfamiliar formats.
    Inference: Formal evidence supports instruction files and file-native organization as real workspace/context substrates, but it also warns that artifact format and retrieval ergonomics matter operationally. Workspace discipline is therefore not just "store it in files"; it is also "store it in grep- and navigation-friendly files."
    Confidence: high
    Evidence: `research/sources/papers/papers_text/2602.05447.txt`
  - |
    Claim 3
    Observation: Anthropic's official context-engineering guidance recommends just-in-time retrieval over file paths and notes, structured note-taking, and hybrid file-system exploration; the Android AGENTS.md doc defines repo-local instruction files discovered from the current directory upward and shared through version control.
    Inference: Official docs converge on repo-local artifacts as a coordination layer: files are not only passive content, but an addressable instruction and state surface that can be inherited, localized, and versioned.
    Confidence: high
    Evidence: `research/sources/docs/src_doc_126e07cf0d68/artifact.txt`, `research/sources/docs/src_doc_29494193a1c5/artifact.txt`
  - |
    Claim 4
    Observation: BigAI workflow docs describe `WorkFlowEnv` as an environment-level manager for lifecycle, tool calls, MCP dispatch, sandboxing, and workspace capabilities, while the agent core doc places prompt, tools, model, memory, and knowledge base in one agent container.
    Inference: BigAI's formal stack reinforces a distinction between orchestration/workspace environment and memory module. This helps Wave 04 avoid collapsing workflow environment, workspace isolation, and memory storage into one mechanism.
    Confidence: medium
    Evidence: `research/sources/docs/bigai/translated/sdk_workflow.md`, `research/sources/docs/bigai/translated/sdk_agent_core.md`
    Weakener: These are translated docs and still weaker than source-backed implementation.
- benchmark_or_definition_notes:
  - `2602.05447` is the strongest formal artifact-discipline benchmark in this pass because it evaluates file-native context delivery, schema partitioning, and format efficiency rather than only discussing them rhetorically.
  - `2512.05470` is stronger on architectural definition than on benchmark rigor; use it for mechanism intent and repository structure.
- mechanism_relevance:
  - Strong support for a Wave 04 family where workspace artifacts, manifests, todo files, notes, and scoped scratchpads act as operational state carriers.
  - Strong support for making artifact discipline and workspace hygiene visible in mechanism cards, especially where direct trajectories already show todo lists, saved scripts, restored files, and clean repo state.
  - Weak support for promoting any universal shared-workspace protocol beyond these concrete file-native and repository-governed patterns.
- failure_relevance:
  - `2602.05447` gives a formal failure surface for file-native work: dense or unfamiliar formats can increase tool-call churn and token overhead, and weaker models may misread format cues.
  - The docs reinforce the risk of stale or mis-scoped instructions when too many tools/files/rules are injected without disciplined selection.
- eval_relevance:
  - File-native context evaluation should measure navigation cost and retrieval ergonomics, not just final correctness.
  - Workspace/artifact evals should track whether agents preserve task state through files and manifests instead of assuming long-term memory exists.
- contradictions:
  - Formal workspace literature mostly treats governed repositories and instruction files as positive scaffolding; the direct wave support artifact shows that in practice these surfaces often work as minimal-sufficient substitutes for richer memory systems rather than alongside them.
  - The metadata for `src_pap_575afb401440.meta.json` points to "Agent Workspace Collaboration Protocol (AWCP)", but the corresponding extracted text in `src_pap_575afb401440.txt` is a different Cadmus paper. That source is currently unusable for Wave 04 claims until the capture is repaired.
- confidence_notes:
  - High confidence that file-native artifacts and workspace scaffolds are load-bearing in the formal slice.
  - Medium confidence in broader "workspace protocol" generalization because the most on-point named workspace paper is currently mismatched on disk.
- open_questions:
  - Is there another formal source in the unread corpus that directly addresses branch/worktree hygiene or artifact handoff for coding agents?
  - Should the mismatched AWCP capture be repaired in coverage support before contradiction review?
  - How much of the observed direct-evidence workspace discipline is best treated as memory substitute versus a separate workspace-control family?
- downstream_use:
  - Use this dossier to support mechanism cards around workspace/artifact discipline and file-native context scaffolding.
  - Use it to keep branch hygiene and restored-artifact continuity visible as state surfaces even when explicit durable memory is absent.
  - Use it to argue against overclaiming "long-term memory" where the stronger evidence is actually governed external artifacts.
- wave_03_context_state_memory_workspace_failures_update_2026_04_10:
  - source_scope_delta:
    - `research/sources/papers/papers_text/2512.05470.txt`
    - `research/sources/papers/papers_text/2602.05447.txt`
    - `research/sources/docs/src_doc_126e07cf0d68/artifact.txt`
    - `research/sources/docs/src_doc_29494193a1c5/artifact.txt`
    - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/codebase_support_workspace_persistence_map.md`
  - observations:
    - formal workspace literature and docs keep file-native artifacts, instruction routing, and repo-local discipline as explicit operational surfaces.
    - Wave 03 codebase evidence aligns: deepagents/KIRA/a-evolve expose distinct workspace and persistence controls that can fail independently of context-window compaction.
    - quarantine claw-code remains a cautionary case where metadata-like workspace scaffolds do not prove full runtime persistence integrity.
  - inference:
    - failure taxonomy should keep `workspace hygiene/path drift` and `artifact persistence/version drift` separate from memory-compaction classes.
    - artifact discipline can function as continuity substrate, but should not be mislabeled as durable memory by default.
  - confidence:
    - high on workspace/artifact class relevance
    - medium on broad cross-family prevalence outside the current Wave 03 task slice
  - evidence_paths:
    - `research/sources/papers/papers_text/2512.05470.txt`
    - `research/sources/papers/papers_text/2602.05447.txt`
    - `research/sources/docs/src_doc_126e07cf0d68/artifact.txt`
    - `research/sources/docs/src_doc_29494193a1c5/artifact.txt`
    - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/codebase_support_workspace_persistence_map.md`

Wave 03 failure-taxonomy addendum (2026-04-10)

- wave: `failure_taxonomy/wave_03_context_state_memory_workspace_failures`
- focus: formal failure attribution for workspace/artifact-state failure classes
- coverage_used_wave_03:
  - `research/sources/papers/papers_text/2512.05470.txt`
  - `research/sources/papers/papers_text/2602.05447.txt`
  - `research/sources/docs/src_doc_29494193a1c5/artifact.txt`
  - `research/sources/docs/src_doc_126e07cf0d68/artifact.txt`
  - `research/sources/docs/bigai/translated/sdk_workflow.md`
  - `research/sources/docs/bigai/translated/sdk_agent_core.md`
- formal_failure_attribution_claims_wave_03:
  - |
    Claim W03-WS-1
    Observation: formal file-system context architecture treats history/memory/scratchpad as explicit, governed artifact layers with logged state transitions.
    Inference: missing or corrupt artifact lifecycle transitions are a dedicated workspace-state failure family, not merely memory recall failure.
    Confidence: high
    Evidence: `research/sources/papers/papers_text/2512.05470.txt`
  - |
    Claim W03-WS-2
    Observation: file-native benchmark evidence identifies retrieval-format failure pressure ("grep tax", pattern mismatch, partial exploration) under tool-mediated navigation.
    Inference: workspace failures should include artifact-format and retrieval-contract subfamilies separate from context-window overflow.
    Confidence: medium
    Evidence: `research/sources/papers/papers_text/2602.05447.txt`
    Weakener: benchmark task regime is structured-data heavy and not identical to required coding trajectories.
  - |
    Claim W03-WS-3
    Observation: AGENTS.md-style instruction files are discovered through directory hierarchy and can be layered/specialized.
    Inference: stale or mis-scoped workspace instruction artifacts are a formal failure mechanism under workspace-state discipline.
    Confidence: medium
    Evidence: `research/sources/docs/src_doc_29494193a1c5/artifact.txt`
  - |
    Claim W03-WS-4
    Observation: formal workflow docs separate workspace orchestration from memory modules.
    Inference: failure attribution should keep workspace/orchestration-state and memory-store causes separated where possible.
    Confidence: medium
    Evidence: `research/sources/docs/bigai/translated/sdk_workflow.md`, `research/sources/docs/bigai/translated/sdk_agent_core.md`
- direct_evidence_tension_wave_03:
  - Formal workspace governance intent is strong, but direct synthesis still indicates strongest observed continuity comes from minimal artifact discipline rather than fully realized memory-workflow stacks.
  - Evidence: `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/synthesis/principal_synthesis.md`

- wave_03_literature_lane_refresh_2026_04_11:
  - source_scope_delta:
    - `research/sources/papers/papers_text/2512.05470.txt`
    - `research/sources/papers/papers_text/2602.05447.txt`
    - `research/sources/docs/src_doc_29494193a1c5/artifact.txt`
    - `research/sources/docs/src_doc_126e07cf0d68/artifact.txt`
    - `research/sources/docs/bigai/translated/sdk_workflow.md`
    - `research/sources/docs/bigai/translated/sdk_agent_core.md`
    - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/literature_papers_docs_analyst.md`
  - observations:
    - formal file-native evidence supports workspace artifacts as a real state substrate, but also reports retrieval-format failures (token overhead, grep-pattern mismatch).
    - AGENTS.md discovery rules encode directory-scoped instruction inheritance, creating a formal surface for instruction-scope drift.
    - workflow docs continue to separate workspace/orchestration surfaces from memory modules.
  - inference:
    - Wave 03 should keep `workspace retrieval/format failures` and `instruction-scope/path routing failures` distinct from context-overflow and memory-retrieval failures.
    - artifact discipline should be treated as state-carrying infrastructure, not automatically as durable-memory proof.
  - confidence:
    - high on workspace/artifact class relevance
    - medium on cross-task prevalence from SQL-heavy proxy settings
  - evidence_paths:
    - `research/sources/papers/papers_text/2512.05470.txt`
    - `research/sources/papers/papers_text/2602.05447.txt`
    - `research/sources/docs/src_doc_29494193a1c5/artifact.txt`
    - `research/sources/docs/src_doc_126e07cf0d68/artifact.txt`
    - `research/sources/docs/bigai/translated/sdk_workflow.md`
    - `research/sources/docs/bigai/translated/sdk_agent_core.md`
