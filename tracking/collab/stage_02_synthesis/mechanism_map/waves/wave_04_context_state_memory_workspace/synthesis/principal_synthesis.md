# Mechanism Map Wave 04 Principal Synthesis

Status date: 2026-04-08

Wave

- `wave_04_context_state_memory_workspace`

Overall judgment

- Wave 04 materially strengthens `mechanism_map`.
- The strongest supported Wave 04 conclusion is that `context`, `state`, `memory`, and `workspace` should not be treated as one merged mechanism family.
- The dominant visible baseline in the required Wave 04 evidence is explicit artifact continuity and workspace-state discipline, not demonstrated durable long-term memory retrieval.
- Source evidence shows richer state-substrate separation than the sampled trajectory windows exercise, especially in DeepAgents, KIRA/KiraClaw, and A-Evolve.
- All three contradiction reviews converge on `pass_with_warnings`, not on a block to synthesis.
- BigAI remains `behavioral reconstruction`.
- Restart-safe resumability remains `exploratory`.
- The Wave 04 repair pass landed the previously missing packet-required support artifacts.
- Those repairs reinforce the current mechanism picture rather than materially changing it.
- Checklist adjudication accepted Wave 04 with carry-forward warnings.

What this wave resolved

- `artifact continuity and workspace state` are the strongest directly observed state-carrying mechanisms in the required Wave 04 slices.
  - DeepAgents keeps state visible through todo updates, replay scripts, and rerunnable artifact paths rather than visible durable retrieval (`research/sources/trajectories/deepagents/git-multibranch/e6e6d3a5-ee75-489a-a4a0-c3a751ea3421-traj.txt`, `research/sources/trajectories/deepagents/custom-memory-heap-crash/aa903d02-9999-4aa2-8d70-3a73a4eb6d8c-traj.txt`).
  - Terminus-KIRA keeps state visible through checklist-bearing analysis, terminal-state review, and script-backed verification (`research/sources/trajectories/terminus-kira/git-multibranch/80b5619c-2b60-45e3-b209-ffbf02d27aa9-traj.txt`).
  - BigAI's required slices show cleanup-heavy handoff and artifact restoration, but still only as `behavioral reconstruction` (`research/sources/trajectories/BigAI/git-multibranch/baabd142-9b5e-457d-8c39-2cdf5bd4f462-traj.txt`, `research/analysis/bigai_trace_layer/output/final_harness_reconstruction.md`).
  - Cross-lane pressure from literature and informal evidence supports the same baseline: explicit files, summaries, manifests, and reloadable artifacts often carry the real state burden better than vague memory rhetoric (`tracking/collab/stage_02_synthesis/literature_dossiers/themes/workspace_and_artifact_discipline.md`, `tracking/collab/stage_02_synthesis/informal_cluster_dossiers/context_state_memory_workspace.md`).
- `context compaction`, `session history`, `durable memory persistence`, and `workspace artifact state` are separate mechanism surfaces.
  - DeepAgents source separates prompt memory, summarization offload, checkpoint-backed thread state, and cross-thread durable store (`research/sources/codebases/deepagents/libs/deepagents/deepagents/middleware/memory.py`, `research/sources/codebases/deepagents/libs/deepagents/deepagents/middleware/summarization.py`, `research/sources/codebases/deepagents/libs/deepagents/deepagents/backends/state.py`, `research/sources/codebases/deepagents/libs/deepagents/deepagents/backends/store.py`).
  - Terminus-KIRA source shows terminal-state injection and handoff summarization, while KiraClaw source adds separate durable memory runtime and retrieval/store paths (`research/sources/codebases/KIRA/terminus_kira/terminus_kira.py`, `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/memory_store.py`, `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/memory_runtime.py`, `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/memory_retriever.py`).
  - A-Evolve makes the filesystem workspace and versioned history the durable substrate, while the active terminal agent intentionally suppresses memory injection into the solve loop (`research/sources/codebases/a-evolve/agent_evolve/contract/workspace.py`, `research/sources/codebases/a-evolve/agent_evolve/engine/versioning.py`, `research/sources/codebases/a-evolve/agent_evolve/agents/terminal/agent.py`).
  - Formal literature sharpens the same split between working memory, persistent memory, context engineering, and file-native workspace scaffolds (`research/sources/papers/papers_text/2512.13564.txt`, `research/sources/papers/papers_text/src_pap_b191e17f02bb.txt`, `research/sources/papers/papers_text/2512.05470.txt`, `research/sources/papers/papers_text/2602.05447.txt`).
- `workspace and branch hygiene` are real state-safety mechanisms, but currently strongest in the `git-multibranch` regime rather than universally across all Wave 04 slices.
  - BigAI repeatedly resets repo and deploy directories, KIRA abandons checkout-based deployment in favor of archive extraction, and DeepAgents uses separate temporary clones and verification paths (`research/sources/trajectories/BigAI/git-multibranch/62d2bdf3-6678-44a2-bb90-efd397b7937d-traj.txt`, `research/sources/trajectories/deepagents/git-multibranch/e6e6d3a5-ee75-489a-a4a0-c3a751ea3421-traj.txt`, `research/sources/trajectories/terminus-kira/git-multibranch/80b5619c-2b60-45e3-b209-ffbf02d27aa9-traj.txt`).
  - Informal evidence strengthens workspace/path/session-state corruption as a live failure surface, while broad repo-branch hygiene remains more task-local and less saturated (`research/sources/issues/src_iss_c07dfa2bcbb3/artifact.txt`, `research/sources/issues/src_iss_836cb2fc3bdb/artifact.txt`, `research/sources/postmortems/src_pmt_95c4bda555e0/artifact.txt`).
- The term `memory` is overloaded and must stay split between at least two materially different surfaces.
  - In the required `custom-memory-heap-crash` slices, the core state problem is allocator/facet cleanup order and runtime heap state, not agent long-term memory (`research/sources/trajectories/BigAI/custom-memory-heap-crash/11834f22-09ea-4bc7-9a11-68f574976a10-traj.txt`, `research/sources/trajectories/deepagents/custom-memory-heap-crash/aa903d02-9999-4aa2-8d70-3a73a4eb6d8c-traj.txt`, `research/sources/trajectories/terminus-kira/custom-memory-heap-crash/3c178f63-b5da-4ffa-b4c3-225d919b72ec-traj.txt`).
  - This wave therefore resolves an important anti-collapse rule: runtime memory-management failures must not be misclassified as coding-agent memory mechanisms.
- Informal pressure makes `compaction failure`, `stale resume`, and `instruction loss after compaction` real operational surfaces.
  - Multiple issue clusters independently show context flooding, bad compaction, stale resume indexes, transcript corruption, and post-compaction rule loss (`research/sources/issues/src_iss_15bd3d2d6a1d/artifact.txt`, `research/sources/issues/src_iss_f736e544a5b9/artifact.txt`, `research/sources/issues/src_iss_613424e145e5/artifact.txt`, `research/sources/issues/src_iss_ed4eb57a9d2b/artifact.txt`, `research/sources/issues/src_iss_d227a621da26/artifact.txt`, `research/sources/issues/src_iss_b8d7092a954f/artifact.txt`).
  - This strengthens the case that compaction, rule re-injection, and state-accounting need to stay explicit mechanism concerns instead of being hidden inside “more memory”.

What changed because of contradiction review

- I am not promoting BigAI as the strongest workspace-discipline family.
  - The stronger current statement is narrower:
    - A-Evolve is the clearest source-backed workspace-artifact family in Wave 04 source.
    - BigAI shows the most elaborate visible handoff and cleanup discipline in the required trajectories, but only as `behavioral reconstruction`.
- I am not promoting the trajectory lane's `procedural state-management` label as the DeepAgents family name.
  - The stronger synthesis is:
    - the required DeepAgents trajectories show a procedural artifact-first window,
    - while source shows a broader layered state architecture with prompt memory, summarization offload, checkpoint-backed state, and durable store.
- I am not promoting KIRA as conclusively thinner on persistent workspace discipline.
  - The current evidence shows:
    - sampled Terminus-KIRA trajectories are thinner on durable memory use,
    - but KiraClaw source is richer than the sampled behavior window reveals.
  - This remains a source/trajectory mismatch, not a settled family ranking.
- I am not promoting durable long-term memory retrieval as a demonstrated cross-family Wave 04 mechanism.
  - The current evidence supports a weaker claim:
    - no required Wave 04 trajectory slice visibly depends on durable long-term retrieval as the dominant state carrier.
  - That is not the same as proving those mechanisms are absent from the families' deeper source capacity.
- I am not promoting restart-safe resumability beyond `exploratory`.
  - Wave 03's caution remains intact:
    - source and docs expose substrate,
    - informal evidence exposes brittleness,
    - required Wave 04 behavior still does not justify stronger promotion.

Promoted mechanism cards

```text
MECHANISM_CARD
- mechanism_id: explicit_artifact_continuity_and_workspace_state
- name: Explicit Artifact Continuity And Workspace State
- short_definition: The main state carrier is explicit files, scripts, checklists, todo state, and clean workspace condition rather than an opaque long-term memory substrate.
- mechanism_family: externalized_state_carrier
- harness_area: context_and_workspace
- location_in_harness: context block, workspace contract, recovery checks, and run-local artifact surfaces
- operational_shape: Systems preserve working state by writing or restoring files, scripts, manifests, and checklist/todo artifacts, then re-reading or replaying them as needed.
- problem_it_addresses: loss of progress or state continuity when raw transcript memory is insufficient or brittle
- direct_observations:
  - DeepAgents trajectories preserve state through todos, scripts, and rerunnable artifact paths.
  - Terminus-KIRA trajectories preserve state through checklist-bearing summaries and shell-scripted verification.
  - BigAI trajectories repeatedly restore and clean workspace artifacts before closure, but only as behavioral reconstruction.
- inferred_behavior:
  - This is the strongest currently demonstrated Wave 04 baseline and should remain visible against richer memory rhetoric.
- evidence_paths:
  - research/sources/trajectories/deepagents/git-multibranch/e6e6d3a5-ee75-489a-a4a0-c3a751ea3421-traj.txt
  - research/sources/trajectories/deepagents/custom-memory-heap-crash/aa903d02-9999-4aa2-8d70-3a73a4eb6d8c-traj.txt
  - research/sources/trajectories/terminus-kira/git-multibranch/80b5619c-2b60-45e3-b209-ffbf02d27aa9-traj.txt
  - research/sources/trajectories/BigAI/git-multibranch/baabd142-9b5e-457d-8c39-2cdf5bd4f462-traj.txt
  - tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/outputs/trajectory_support_context_workspace_matrix.md
  - tracking/collab/stage_02_synthesis/literature_dossiers/themes/workspace_and_artifact_discipline.md
  - tracking/collab/stage_02_synthesis/informal_cluster_dossiers/context_state_memory_workspace.md
- evidence_types:
  - trajectory
  - literature_dossier
  - informal_cluster
- source_families:
  - deepagents
  - KIRA
  - BigAI
- task_regimes_observed:
  - git multibranch
  - break filter
  - custom memory heap crash
- likely_failure_modes_addressed:
  - context overflow
  - losing rule state after compaction
  - workspace drift
  - artifact restoration failure
- failure_role:
  - preventive
- contradictory_or_complicating_evidence:
  - Source-visible durable memory layers exist in DeepAgents and KiraClaw beyond what the required trajectory windows exercise.
- interaction_notes:
  - Interacts strongly with branch hygiene, compaction policy, and recovery logic.
- likely_tradeoffs:
  - Can become brittle if artifact naming, placement, or reload discipline is weak.
  - May under-cover cases where the needed state is not naturally file-native.
- simplicity_note:
  - Minimal-sufficient and important to preserve.
- likely_eval_implications:
  - Test explicit artifact continuity against memory-heavy designs on long-horizon coding tasks.
- likely_variant_axes:
  - checklist/todo artifacts
  - file-native workspace state
  - replay scripts
  - durable memory layer added on top
- confidence:
  - high
- open_questions:
  - Which tasks require durable retrieval beyond this artifact-first baseline?
```

```text
MECHANISM_CARD
- mechanism_id: layered_context_compaction_persistence_and_workspace_substrates
- name: Layered Context, Compaction, Persistence, And Workspace Substrates
- short_definition: Context-window management, session history, durable memory persistence, and workspace artifacts are distinct layers that can be composed but should not be collapsed into one memory mechanism.
- mechanism_family: layered_state_substrates
- harness_area: context_and_state
- location_in_harness: context block, memory store, session runtime, workspace contract, and recovery substrate
- operational_shape: Systems separate active context management from durable persistence and from file-native workspace state, with compaction/handoff logic acting as a distinct state-management layer.
- problem_it_addresses: collapsing all continuity behavior into vague "memory" and hiding important mechanism differences
- direct_observations:
  - DeepAgents source separates prompt memory, summarization, checkpoint-backed state, and durable store.
  - Terminus-KIRA source separates terminal-state summary/handoff from KiraClaw durable memory runtime.
  - A-Evolve source separates workspace files and versioned history from optional memory injection into the active solver.
- inferred_behavior:
  - The corpus supports a layered-state picture, but the required trajectories only exercise a subset of the available source capacity.
- evidence_paths:
  - research/sources/codebases/deepagents/libs/deepagents/deepagents/middleware/memory.py
  - research/sources/codebases/deepagents/libs/deepagents/deepagents/middleware/summarization.py
  - research/sources/codebases/deepagents/libs/deepagents/deepagents/backends/state.py
  - research/sources/codebases/deepagents/libs/deepagents/deepagents/backends/store.py
  - research/sources/codebases/KIRA/terminus_kira/terminus_kira.py
  - research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/memory_store.py
  - research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/memory_runtime.py
  - research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/memory_retriever.py
  - research/sources/codebases/a-evolve/agent_evolve/contract/workspace.py
  - research/sources/codebases/a-evolve/agent_evolve/engine/versioning.py
  - research/sources/codebases/a-evolve/agent_evolve/agents/terminal/agent.py
  - research/sources/papers/papers_text/2512.13564.txt
  - research/sources/papers/papers_text/src_pap_b191e17f02bb.txt
  - research/sources/papers/papers_text/2512.05470.txt
  - research/sources/papers/papers_text/2602.05447.txt
- evidence_types:
  - source_code
  - literature
  - docs
- source_families:
  - deepagents
  - KIRA
  - a-evolve
- task_regimes_observed:
  - context compaction
  - memory persistence
  - workspace state management
- likely_failure_modes_addressed:
  - context flooding
  - stale resume
  - rule loss after compaction
  - hidden state coupling
- failure_role:
  - mixed
- contradictory_or_complicating_evidence:
  - Required Wave 04 trajectories do not directly exercise all of the richer source-visible durable-memory layers.
- interaction_notes:
  - Interacts with compaction, workspace artifacts, restart/resume substrate, and instruction reinjection.
- likely_tradeoffs:
  - More layers can improve control and observability but also create mismatch between capacity and behavior.
- simplicity_note:
  - Important anti-collapse card rather than a single implementation doctrine.
- likely_eval_implications:
  - Evaluate compaction-only, file-native workspace, and durable store variants separately rather than as one "memory" axis.
- likely_variant_axes:
  - compaction only
  - session history plus compaction
  - workspace files plus versioning
  - durable retrieval store
  - hybrid layered stack
- confidence:
  - high
- open_questions:
  - Which layers are actually exercised in long-horizon coding runs rather than just exposed in source?
```

```text
MECHANISM_CARD
- mechanism_id: workspace_and_branch_hygiene_regime
- name: Workspace And Branch Hygiene Regime
- short_definition: Clean workspace state, path-target fidelity, and branch or deploy isolation are explicit state-safety mechanisms in tasks where concurrent or multi-branch artifacts can interfere.
- mechanism_family: workspace_isolation_and_hygiene
- harness_area: workspace
- location_in_harness: runner workspace management, recovery checks, and artifact-validation logic
- operational_shape: The harness or agent isolates or resets directories, avoids shared mutable state, and validates the target path or branch before treating progress as reliable.
- problem_it_addresses: hidden cross-branch contamination, wrong-target edits, and dirty workspace state masquerading as task progress
- direct_observations:
  - BigAI resets repo and deploy directories in `git-multibranch`.
  - KIRA uses `git archive | tar -x` rather than checkout-based deployment.
  - DeepAgents uses temporary clones and fresh verification paths.
  - Informal issue clusters show path-target and session-state corruption as a real operational hazard.
- inferred_behavior:
  - This is a real mechanism family, but current evidence is strongest in `git-multibranch` and should stay regime-scoped.
- evidence_paths:
  - research/sources/trajectories/BigAI/git-multibranch/62d2bdf3-6678-44a2-bb90-efd397b7937d-traj.txt
  - research/sources/trajectories/deepagents/git-multibranch/e6e6d3a5-ee75-489a-a4a0-c3a751ea3421-traj.txt
  - research/sources/trajectories/terminus-kira/git-multibranch/80b5619c-2b60-45e3-b209-ffbf02d27aa9-traj.txt
  - research/sources/issues/src_iss_c07dfa2bcbb3/artifact.txt
  - research/sources/issues/src_iss_836cb2fc3bdb/artifact.txt
  - research/sources/postmortems/src_pmt_95c4bda555e0/artifact.txt
- evidence_types:
  - trajectory
  - issue
  - postmortem
- source_families:
  - BigAI
  - deepagents
  - KIRA
- task_regimes_observed:
  - git multibranch
  - workspace/path targeting
- likely_failure_modes_addressed:
  - cross-branch contamination
  - wrong-target file edits
  - dirty deploy state
  - session-state corruption
- failure_role:
  - preventive
- contradictory_or_complicating_evidence:
  - Direct pressure is stronger for workspace/path corruption than for broad branch-hygiene claims outside `git-multibranch`.
- interaction_notes:
  - Interacts with artifact continuity, cleanup, and recovery.
- likely_tradeoffs:
  - More isolation increases setup cost and state-management overhead.
- simplicity_note:
  - Strongly regime-dependent; do not over-generalize it.
- likely_eval_implications:
  - Add evals that distinguish functional success from wrong-target or dirty-workspace success.
- likely_variant_axes:
  - no isolation
  - branch/worktree isolation
  - deploy-directory reset
  - path-target validation
- confidence:
  - medium_high
- open_questions:
  - How much of this family survives outside `git-multibranch` and session/path corruption issues?
```

Candidate mechanisms not yet promoted

- `durable_long_term_memory_retrieval_as_dominant_state_carrier`
  - Source and docs show substrate in multiple families.
  - Required Wave 04 trajectories do not show it dominating state continuity.
  - Keep this candidate `exploratory`.
- `restart_safe_resumability`
  - Remains source/doc-visible and informally pressured, but not behaviorally established.
  - Keep this candidate `exploratory`.
- `BigAI_hidden_memory_substrate`
  - Docs and reconstruction imply a distinct memory layer, but implementation remains hidden.
  - Keep this candidate `exploratory` and explicitly `behavioral reconstruction`.
- `claw_code_runtime_state_family`
  - Archive pressure exists, but the required dossier is still missing and the visible runtime surfaces remain quarantine-level evidence.
  - Keep this candidate `exploratory`.

Support-track updates

- Landed and usable in this wave:
  - `tracking/collab/stage_02_synthesis/trajectory_case_studies/git_multibranch.md`
  - `tracking/collab/stage_02_synthesis/trajectory_case_studies/break_filter_js_from_html.md`
  - `tracking/collab/stage_02_synthesis/trajectory_case_studies/custom_memory_heap_crash.md`
  - `tracking/collab/stage_02_synthesis/source_system_dossiers/claw-code.md`
  - `tracking/collab/stage_02_synthesis/literature_dossiers/themes/context_and_memory.md`
  - `tracking/collab/stage_02_synthesis/literature_dossiers/themes/workspace_and_artifact_discipline.md`
  - `tracking/collab/stage_02_synthesis/informal_cluster_dossiers/context_state_memory_workspace.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/outputs/trajectory_support_context_workspace_matrix.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/outputs/codebase_support_workspace_artifact_map.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/outputs/codebase_support_context_state_map.md`
- Deferred but not yet checklist-blocking if the required files above land:
  - `trajectory_support_memory_state_drift_cases.md`
  - `trajectory_support_branch_worktree_state_table.md`
  - `trajectory_support_run_to_source_link_map.md`
  - `codebase_support_compaction_handoff_map.md`
  - `codebase_support_claw_code_runtime_state_map.md`

What still requires another same-wave repair

- No additional same-wave repair is required before checklist.
- The repair-pass case studies and `claw-code` dossier formalize already-cited support-track surfaces and do not materially change the promoted mechanism picture.
- No contradiction rerun is required.

What still requires another later wave

- Long-tail pressure on:
  - `research/sources/trajectories/BigAI/adaptive-rejection-sampler/**`
  - `research/sources/trajectories/*/headless-terminal/**`
  - `research/sources/trajectories/*/large-scale-text-editing/**`
- Deeper KIRA durable-memory mapping through:
  - `research/sources/codebases/KIRA/KIRA-Slack/app/cc_agents/memory_manager/**`
  - `research/sources/codebases/KIRA/KIRA-Slack/app/cc_agents/memory_retriever/**`
- Deeper source pressure on:
  - `research/sources/codebases/deepagents/libs/evals/tests/evals/memory_agent_bench/test_memory_agent_bench.py`
- Later waves still need to answer:
  - when durable retrieval memory materially beats artifact continuity,
  - when restart-safe resumability becomes behaviorally real,
  - and how these state families interact with tools, permissions, and orchestration.

Local harness implications

- The local harness should keep `context-window management`, `compaction/handoff`, `workspace artifacts`, and any future `durable memory` as separate swappable blocks or sub-block responsibilities.
- The current evidence does not support building the harness around rich long-term memory as the default baseline.
  - It supports starting from explicit files, checklists, scripts, and workspace hygiene, then adding richer memory only where later evidence proves it matters.
- `runner/` and recovery surfaces should treat path-target validation, isolated workspaces, and artifact continuity as first-class concerns.
- `ContextBlock` design should avoid collapsing:
  - full-history retention
  - compaction
  - structured scratchpads
  - durable retrieval
  into one monolithic memory policy.
- `VerificationBlock` and `RecoveryBlock` should remain aware that state continuity can fail through dirty workspaces, lost rule artifacts, and stale resume indexes even when the model “remembers” the plan.

Coverage not yet used

- `research/sources/trajectories/BigAI/adaptive-rejection-sampler/**`
- `research/sources/trajectories/*/headless-terminal/**`
- `research/sources/trajectories/*/large-scale-text-editing/**`
- `research/sources/codebases/KIRA/KIRA-Slack/app/cc_agents/memory_manager/**`
- `research/sources/codebases/KIRA/KIRA-Slack/app/cc_agents/memory_retriever/**`
- `research/sources/codebases/deepagents/libs/evals/tests/evals/memory_agent_bench/test_memory_agent_bench.py`
- `research/sources/papers/papers_text/2510.04618.txt`
- `research/sources/papers/papers_text/2603.09619.txt`
- `research/sources/papers/papers_text/src_pap_f2bc990ed39f.txt`
- `research/sources/papers/papers_text/src_pap_703731e7c236.txt`

Priority sources not yet read

- `research/sources/trajectories/BigAI/adaptive-rejection-sampler/**`
- `research/sources/codebases/KIRA/KIRA-Slack/app/cc_agents/memory_manager/agent.py`
- `research/sources/codebases/KIRA/KIRA-Slack/app/cc_agents/memory_retriever/agent.py`
- `research/sources/codebases/deepagents/libs/evals/tests/evals/memory_agent_bench/test_memory_agent_bench.py`
- long-tail trajectory pressure from `headless-terminal` and `large-scale-text-editing`

Gate judgment

- Used contradiction outputs:
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/outputs/contradiction_analyst.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/outputs/contradiction_analyst__claude.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/outputs/contradiction_analyst__gemini.md`
- Convergence:
  - all three contradiction reviews support `pass_with_warnings`
  - all three keep BigAI bounded
  - all three preserve restart/resume caution
  - the stricter GPT and Claude reviews required support-track repair before clean acceptance, and that repair pass has now landed
- Principal call:
  - Wave 04 principal synthesis is complete.
  - Wave 04 is now ready for checklist adjudication.
