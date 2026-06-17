CODEBASE_SOURCE_RECON_OUTPUT
- artifact: mechanism_map / wave_04_context_state_memory_workspace
- role: codebase/source-reconstruction analyst
- preflight_scope_confirmed:
  - This is a vertical mechanism-domain wave centered on context, state, memory, and workspace discipline, not a verification-only or generic execution-control pass.
  - Trajectory/failure remains the primary empirical anchor; this lane is the primary implementation anchor and uses trajectories only to check alignment or mismatch.
  - The optional eval/benchmark fifth lane stays inactive in this pass because none of the source-backed mechanism judgments here depend on grader-side state comparison or benchmark contract logic.
  - Minimal-sufficient baseline kept visible: explicit workspace artifacts, short-horizon history, and replay scripts can explain a large share of observed state continuity without assuming rich long-term memory.
  - Strong coverage for this lane uses two bounded support artifacts:
    - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/outputs/codebase_support_workspace_artifact_map.md`
    - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/outputs/codebase_support_context_state_map.md`
- preflight_planned_read_order:
  - 1. Wave control surfaces and prior accepted synthesis:
    - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/brief.md`
    - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/inputs/support_subagent_rules.md`
    - `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_EXECUTION_PROTOCOL.md`
    - `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_MULTI_AGENT_WORKFLOW_GUIDE.md`
    - `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_LANE_CLOSURE_CRITERIA.md`
    - `tracking/collab/stage_02_synthesis/mechanism_map/synthesis/cumulative_synthesis.md`
    - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/synthesis/principal_synthesis.md`
    - `tracking/collab/stage_02_synthesis/coverage_register/current_status.md`
    - `research/intake/normalized/manifests/corpus__captured_for_synthetic_prep.json`
    - `tracking/collab/stage_02_synthesis/evidence_inventory/outputs/organizer.md`
  - 2. First-class mirrored source families and relevant local harness surfaces:
    - `research/sources/codebases/deepagents/**`
    - `research/sources/codebases/KIRA/**`
    - `research/sources/codebases/a-evolve/**`
    - `research/sources/codebases/quarantine/claw-code/**`
    - `blocks/**`
    - `runner/**`
    - `evals/**`
  - 3. Required trajectory slices for behavior reconciliation:
    - `research/sources/trajectories/BigAI/git-multibranch/*.txt`
    - `research/sources/trajectories/deepagents/git-multibranch/*.txt`
    - `research/sources/trajectories/terminus-kira/git-multibranch/*.txt`
    - `research/sources/trajectories/BigAI/break-filter-js-from-html/*.txt`
    - `research/sources/trajectories/deepagents/break-filter-js-from-html/*.txt`
    - `research/sources/trajectories/terminus-kira/break-filter-js-from-html/*.txt`
    - `research/sources/trajectories/BigAI/custom-memory-heap-crash/*.txt`
    - `research/sources/trajectories/deepagents/custom-memory-heap-crash/*.txt`
    - `research/sources/trajectories/terminus-kira/custom-memory-heap-crash/*.txt`
  - 4. BigAI behavior-reconstruction helpers and already-landed cross-lane aids:
    - `research/analysis/bigai_trace_layer/output/final_harness_reconstruction.md`
    - `research/analysis/bigai_trace_layer/output/question_answers.json`
    - `research/sources/docs/bigai/raw/sdk_documentation_memory.txt`
    - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/outputs/trajectory_failure_analyst.md`
    - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/outputs/codebase_support_workspace_artifact_map.md`
    - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/outputs/codebase_support_context_state_map.md`
- preflight_critical_sources_selected:
  - DeepAgents:
    - `research/sources/codebases/deepagents/libs/deepagents/deepagents/middleware/memory.py`
    - `research/sources/codebases/deepagents/libs/deepagents/deepagents/middleware/summarization.py`
    - `research/sources/codebases/deepagents/libs/deepagents/deepagents/backends/state.py`
    - `research/sources/codebases/deepagents/libs/deepagents/deepagents/backends/store.py`
    - `research/sources/codebases/deepagents/libs/cli/deepagents_cli/sessions.py`
    - `research/sources/codebases/deepagents/action.yml`
  - KIRA:
    - `research/sources/codebases/KIRA/terminus_kira/terminus_kira.py`
    - `research/sources/codebases/KIRA/prompt-templates/terminus-kira.txt`
    - `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/session_manager.py`
    - `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/memory_store.py`
    - `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/memory_runtime.py`
    - `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/memory_retriever.py`
    - `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/memory_saver.py`
    - `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/memory_models.py`
  - A-Evolve:
    - `research/sources/codebases/a-evolve/DESIGN.md`
    - `research/sources/codebases/a-evolve/agent_evolve/protocol/base_agent.py`
    - `research/sources/codebases/a-evolve/agent_evolve/agents/terminal/agent.py`
    - `research/sources/codebases/a-evolve/agent_evolve/contract/workspace.py`
    - `research/sources/codebases/a-evolve/agent_evolve/contract/manifest.py`
    - `research/sources/codebases/a-evolve/agent_evolve/engine/versioning.py`
    - `research/sources/codebases/a-evolve/agent_evolve/engine/history.py`
    - `research/sources/codebases/a-evolve/agent_evolve/engine/trial.py`
    - `research/sources/codebases/a-evolve/agent_evolve/engine/observer.py`
    - `research/sources/codebases/a-evolve/seed_workspaces/terminal/manifest.yaml`
    - `research/sources/codebases/a-evolve/examples/configs/terminal.yaml`
  - Quarantine / archive-pressure:
    - `research/sources/codebases/quarantine/claw-code/README.md`
    - `research/sources/codebases/quarantine/claw-code/src/session_store.py`
    - `research/sources/codebases/quarantine/claw-code/src/transcript.py`
    - `research/sources/codebases/quarantine/claw-code/src/history.py`
    - `research/sources/codebases/quarantine/claw-code/src/context.py`
    - `research/sources/codebases/quarantine/claw-code/src/runtime.py`
    - `research/sources/codebases/quarantine/claw-code/src/remote_runtime.py`
    - `research/sources/codebases/quarantine/claw-code/src/query_engine.py`
    - `research/sources/codebases/quarantine/claw-code/src/bootstrap_graph.py`
    - `research/sources/codebases/quarantine/claw-code/src/main.py`
  - Local harness baseline:
    - `blocks/context/full_history.py`
    - `blocks/context/sliding_window.py`
    - `blocks/context/summarize_on_overflow.py`
    - `blocks/context/structured_sections.py`
    - `blocks/verification/checkpoint_verify.py`
    - `blocks/recovery/rollback.py`
    - `blocks/README.md`
    - `runner/agent.py`
    - `runner/docker_sandbox.py`
    - `runner/logger.py`
    - `evals/context_eval.py`
- preflight_coverage_risks:
  - `tracking/collab/stage_02_synthesis/evidence_inventory/outputs/organizer.md` remains empty, so direct path accounting still outranks organizer routing.
  - BigAI remains source-invisible and can only contribute behavioral reconstruction plus docs pressure.
  - `research/sources/codebases/quarantine/claw-code/**` is explicitly quarantine material and much of the visible runtime/state surface is scaffold or placeholder, not equal-status implementation evidence.
  - Local harness files under `blocks/` and `runner/` are still mostly interface or responsibility stubs, so local implications stay architectural rather than implementation-complete.
- preflight_likely_blind_spots:
  - Harbor `TmuxSession` internals imported by Terminus-KIRA but not present under the required mirrored path family
  - deeper KIRA-Slack memory-manager paths outside the selected first-pass scope
  - cross-thread or multi-run DeepAgents memory retrieval behavior not exercised by the required Wave 04 trajectory slices
  - any claim that claw-code placeholder remote/resume branches correspond to a real stable runtime substrate
- preflight_blockers:
  - none; visible source is sufficient to distinguish context compaction, memory persistence, and workspace artifact discipline honestly if archive-only and behavior-only families are labeled conservatively
- coverage_used:
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/brief.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/inputs/support_subagent_rules.md`
  - `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_EXECUTION_PROTOCOL.md`
  - `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_MULTI_AGENT_WORKFLOW_GUIDE.md`
  - `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_LANE_CLOSURE_CRITERIA.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/synthesis/cumulative_synthesis.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/synthesis/principal_synthesis.md`
  - `tracking/collab/stage_02_synthesis/coverage_register/current_status.md`
  - `tracking/collab/stage_02_synthesis/evidence_inventory/outputs/organizer.md`
  - `research/intake/normalized/manifests/corpus__captured_for_synthetic_prep.json`
  - `research/sources/codebases/deepagents/action.yml`
  - `research/sources/codebases/deepagents/libs/deepagents/deepagents/middleware/memory.py`
  - `research/sources/codebases/deepagents/libs/deepagents/deepagents/middleware/summarization.py`
  - `research/sources/codebases/deepagents/libs/deepagents/deepagents/backends/state.py`
  - `research/sources/codebases/deepagents/libs/deepagents/deepagents/backends/store.py`
  - `research/sources/codebases/deepagents/libs/cli/deepagents_cli/sessions.py`
  - `research/sources/codebases/deepagents/libs/evals/tests/evals/memory_agent_bench/configs.py`
  - `research/sources/codebases/deepagents/libs/evals/tests/evals/memory_agent_bench/eval_utils.py`
  - `research/sources/codebases/KIRA/README.md`
  - `research/sources/codebases/KIRA/prompt-templates/terminus-kira.txt`
  - `research/sources/codebases/KIRA/terminus_kira/terminus_kira.py`
  - `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/session_manager.py`
  - `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/memory_store.py`
  - `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/memory_runtime.py`
  - `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/memory_retriever.py`
  - `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/memory_saver.py`
  - `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/memory_models.py`
  - `research/sources/codebases/a-evolve/DESIGN.md`
  - `research/sources/codebases/a-evolve/agent_evolve/protocol/base_agent.py`
  - `research/sources/codebases/a-evolve/agent_evolve/agents/terminal/agent.py`
  - `research/sources/codebases/a-evolve/agent_evolve/agents/terminal/react_solver.py`
  - `research/sources/codebases/a-evolve/agent_evolve/contract/workspace.py`
  - `research/sources/codebases/a-evolve/agent_evolve/contract/manifest.py`
  - `research/sources/codebases/a-evolve/agent_evolve/engine/versioning.py`
  - `research/sources/codebases/a-evolve/agent_evolve/engine/history.py`
  - `research/sources/codebases/a-evolve/agent_evolve/engine/trial.py`
  - `research/sources/codebases/a-evolve/agent_evolve/engine/observer.py`
  - `research/sources/codebases/a-evolve/seed_workspaces/terminal/manifest.yaml`
  - `research/sources/codebases/a-evolve/seed_workspaces/terminal/memory/memories.jsonl`
  - `research/sources/codebases/a-evolve/examples/configs/terminal.yaml`
  - `research/sources/codebases/quarantine/claw-code/README.md`
  - `research/sources/codebases/quarantine/claw-code/src/session_store.py`
  - `research/sources/codebases/quarantine/claw-code/src/transcript.py`
  - `research/sources/codebases/quarantine/claw-code/src/history.py`
  - `research/sources/codebases/quarantine/claw-code/src/context.py`
  - `research/sources/codebases/quarantine/claw-code/src/runtime.py`
  - `research/sources/codebases/quarantine/claw-code/src/remote_runtime.py`
  - `research/sources/codebases/quarantine/claw-code/src/query_engine.py`
  - `research/sources/codebases/quarantine/claw-code/src/bootstrap_graph.py`
  - `research/sources/codebases/quarantine/claw-code/src/main.py`
  - `blocks/context/full_history.py`
  - `blocks/context/sliding_window.py`
  - `blocks/context/summarize_on_overflow.py`
  - `blocks/context/structured_sections.py`
  - `blocks/verification/checkpoint_verify.py`
  - `blocks/recovery/rollback.py`
  - `blocks/README.md`
  - `runner/agent.py`
  - `runner/docker_sandbox.py`
  - `runner/logger.py`
  - `evals/context_eval.py`
  - `research/sources/trajectories/BigAI/git-multibranch/62d2bdf3-6678-44a2-bb90-efd397b7937d-traj.txt`
  - `research/sources/trajectories/BigAI/git-multibranch/baabd142-9b5e-457d-8c39-2cdf5bd4f462-traj.txt`
  - `research/sources/trajectories/deepagents/git-multibranch/e6e6d3a5-ee75-489a-a4a0-c3a751ea3421-traj.txt`
  - `research/sources/trajectories/terminus-kira/git-multibranch/80b5619c-2b60-45e3-b209-ffbf02d27aa9-traj.txt`
  - `research/sources/trajectories/BigAI/break-filter-js-from-html/4e6a3070-4a78-4c1a-ac1c-c0651045db08-traj.txt`
  - `research/sources/trajectories/deepagents/break-filter-js-from-html/802e3807-8f1a-4c15-991c-9cdb03d16cef-traj.txt`
  - `research/sources/trajectories/terminus-kira/break-filter-js-from-html/eaf5da17-d140-4652-bd00-3e6a83bf66cf-traj.txt`
  - `research/sources/trajectories/BigAI/custom-memory-heap-crash/11834f22-09ea-4bc7-9a11-68f574976a10-traj.txt`
  - `research/sources/trajectories/deepagents/custom-memory-heap-crash/aa903d02-9999-4aa2-8d70-3a73a4eb6d8c-traj.txt`
  - `research/sources/trajectories/terminus-kira/custom-memory-heap-crash/3c178f63-b5da-4ffa-b4c3-225d919b72ec-traj.txt`
  - `research/analysis/bigai_trace_layer/output/final_harness_reconstruction.md`
  - `research/analysis/bigai_trace_layer/output/question_answers.json`
  - `research/sources/docs/bigai/raw/sdk_documentation_memory.txt`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/outputs/trajectory_failure_analyst.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/outputs/codebase_support_workspace_artifact_map.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/outputs/codebase_support_context_state_map.md`
- coverage_not_yet_used:
  - `research/sources/codebases/KIRA/KIRA-Slack/app/cc_agents/memory_manager/**`
  - `research/sources/codebases/KIRA/KIRA-Slack/app/cc_agents/memory_retriever/**`
  - `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/memory_tools.py`
  - `research/sources/codebases/deepagents/examples/**`
  - `research/sources/codebases/deepagents/libs/evals/tests/evals/memory_agent_bench/test_memory_agent_bench.py`
  - `research/sources/codebases/quarantine/claw-code/src/reference_data/subsystems/state.json`
  - `tracking/collab/stage_02_synthesis/source_system_dossiers/deepagents.md`
  - `tracking/collab/stage_02_synthesis/source_system_dossiers/KIRA.md`
  - `tracking/collab/stage_02_synthesis/source_system_dossiers/a-evolve.md`
  - `tracking/collab/stage_02_synthesis/source_system_dossiers/BigAI_behavioral.md`
  - `tracking/collab/stage_02_synthesis/source_system_dossiers/claw-code.md`
  - `tracking/collab/stage_02_synthesis/trajectory_case_studies/git_multibranch.md`
  - `tracking/collab/stage_02_synthesis/trajectory_case_studies/break_filter_js_from_html.md`
  - `tracking/collab/stage_02_synthesis/trajectory_case_studies/custom_memory_heap_crash.md`
- evidence_classes_touched:
  - mirrored codebases
  - local harness code
  - trajectories
  - behavior-reconstruction analysis
  - docs
  - support artifacts
- priority_sources_not_yet_read:
  - `research/sources/codebases/KIRA/KIRA-Slack/app/cc_agents/memory_manager/agent.py`
  - `research/sources/codebases/KIRA/KIRA-Slack/app/cc_agents/memory_retriever/agent.py`
  - `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/memory_tools.py`
  - `research/sources/codebases/deepagents/libs/evals/tests/evals/memory_agent_bench/test_memory_agent_bench.py`
- support_artifacts_used:
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/outputs/codebase_support_workspace_artifact_map.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/outputs/codebase_support_context_state_map.md`
- support_artifacts_requested_or_deferred:
  - deferred:
    - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/outputs/codebase_support_compaction_handoff_map.md`
    - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/outputs/codebase_support_claw_code_runtime_state_map.md`
- coverage_register_updates_needed:
  - after principal synthesis, update `tracking/collab/stage_02_synthesis/coverage_register/current_status.md` to show Wave 04 codebase/source first pass exists with direct source reads across DeepAgents, KIRA, A-Evolve, local harness, and quarantine claw-code
  - keep explicit warnings that BigAI remains behavioral reconstruction, organizer routing remains weaker than direct path accounting, and restart/resumability still lacks strong behavior-layer closure
  - note that both first-pass codebase support artifacts have landed, while deeper compaction-handoff and claw-code runtime follow-ups remain deferred if contradiction review needs tighter path saturation
- required_dossier_updates:
  - `tracking/collab/stage_02_synthesis/source_system_dossiers/deepagents.md`
  - `tracking/collab/stage_02_synthesis/source_system_dossiers/KIRA.md`
  - `tracking/collab/stage_02_synthesis/source_system_dossiers/a-evolve.md`
  - `tracking/collab/stage_02_synthesis/source_system_dossiers/BigAI_behavioral.md`
  - `tracking/collab/stage_02_synthesis/source_system_dossiers/claw-code.md`
- source_backed_mechanisms:
  - mechanism_id: S1
    observation: DeepAgents source separates at least four state substrates instead of one generic memory layer: prompt-injected AGENTS.md memory, summarization offload, ephemeral thread-local files in agent state, and persistent cross-thread files in a store. `MemoryMiddleware` loads configured AGENTS.md sources into private state and appends them into the system prompt; `_DeepAgentsSummarizationMiddleware` offloads evicted history to `/conversation_history/{thread_id}.md`; `StateBackend` persists files only within LangGraph state/checkpoint scope; `StoreBackend` persists files in a namespaced BaseStore across threads; CLI sessions additionally persist checkpoint metadata in `~/.deepagents/sessions.db`.
    inference: DeepAgents is source-backed evidence that context compaction, prompt memory, and durable persistence are separate mechanisms that can be composed but should not be collapsed.
    confidence: high
    evidence_paths:
      - `research/sources/codebases/deepagents/libs/deepagents/deepagents/middleware/memory.py`
      - `research/sources/codebases/deepagents/libs/deepagents/deepagents/middleware/summarization.py`
      - `research/sources/codebases/deepagents/libs/deepagents/deepagents/backends/state.py`
      - `research/sources/codebases/deepagents/libs/deepagents/deepagents/backends/store.py`
      - `research/sources/codebases/deepagents/libs/cli/deepagents_cli/sessions.py`
  - mechanism_id: S2
    observation: Terminus-KIRA source makes live terminal state the primary context substrate and treats summarization as a handoff operation rather than durable memory retrieval. On context overflow it unwinds messages, generates a summary prompt, stores `_pending_handoff_prompt`, and retries with the summarized prompt; proactive summarization can happen before overflow as well. The completion confirmation prompt also embeds the current terminal state and a workspace-minimality checklist.
    inference: Classic KIRA is a source-backed context-compaction and checklist-discipline family whose retained state is mainly terminal-state summary plus explicit completion doctrine, not a rich long-term memory store.
    confidence: high
    evidence_paths:
      - `research/sources/codebases/KIRA/terminus_kira/terminus_kira.py`
      - `research/sources/codebases/KIRA/prompt-templates/terminus-kira.txt`
      - `research/sources/codebases/KIRA/README.md`
  - mechanism_id: S3
    observation: KiraClaw adds a distinct file-backed session-and-memory runtime on top of KIRA-style conversation handling. `SessionManager` keeps bounded recent turn history, clips conversation text, injects optional `context_prefix`, and calls a separate memory-context provider. Completed runs can be auto-classified into semantic or episodic memory and enqueued as `MemoryWriteRequest`s. `MemoryStore` persists markdown memory files plus a JSON index keyed by session/user/channel metadata, and `MemoryRuntime` runs retrieval and async save workers around that store.
    inference: KIRA's broader source family already distinguishes short-horizon session history from durable retrieval memory; the codebase does not support flattening both into one undifferentiated "memory" family.
    confidence: high
    evidence_paths:
      - `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/session_manager.py`
      - `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/memory_store.py`
      - `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/memory_runtime.py`
      - `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/memory_retriever.py`
      - `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/memory_saver.py`
      - `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/memory_models.py`
  - mechanism_id: S4
    observation: A-Evolve makes the filesystem workspace the first-class state substrate. `AgentWorkspace` exposes typed read/write access to prompts, prompt fragments, skills, tools, memory JSONL files, and `evolution/` artifacts. `BaseAgent.reload_from_fs()` reloads prompt/skills/memory from disk after each cycle, `Observer` persists JSONL observation batches under `evolution/observations`, and `VersionControl` creates git commits/tags and rollback/worktree copies for workspace state recovery.
    inference: A-Evolve is the clearest source-backed workspace-artifact family in Wave 04: state is explicitly externalized into files and version history, not hidden inside agent threads.
    confidence: high
    evidence_paths:
      - `research/sources/codebases/a-evolve/DESIGN.md`
      - `research/sources/codebases/a-evolve/agent_evolve/protocol/base_agent.py`
      - `research/sources/codebases/a-evolve/agent_evolve/contract/workspace.py`
      - `research/sources/codebases/a-evolve/agent_evolve/engine/observer.py`
      - `research/sources/codebases/a-evolve/agent_evolve/engine/versioning.py`
      - `research/sources/codebases/a-evolve/agent_evolve/engine/history.py`
  - mechanism_id: S5
    observation: A-Evolve's reference terminal agent deliberately does not inject workspace memories into the user prompt for Terminal-Bench tasks. `_build_user_prompt()` notes that memories dilute attention on time-sensitive tasks, while `_build_system_prompt()` only exposes the base prompt plus skill metadata and lazy skill loading.
    inference: Even inside a workspace-persistent family, long-term memory can be present in the contract yet intentionally excluded from the active solver path. This is strong source pressure against vague "more memory is always the mechanism" narratives.
    confidence: high
    evidence_paths:
      - `research/sources/codebases/a-evolve/agent_evolve/agents/terminal/agent.py`
      - `research/sources/codebases/a-evolve/examples/configs/terminal.yaml`
      - `research/sources/codebases/a-evolve/seed_workspaces/terminal/manifest.yaml`
  - mechanism_id: S6
    observation: The local harness under `blocks/` and `runner/` currently expresses context/state/workspace mechanisms as swap-friendly interfaces and responsibilities, not as implemented policy. Context variants are named (`full_history`, `sliding_window`, `summarize_on_overflow`, `structured_sections`), logging is required, and Docker isolation is called out, but the files are still docstring-level stubs.
    inference: The local harness is presently a mechanism-design scaffold, not yet a source-backed peer implementation family for context/state behavior. It functions as a baseline target architecture rather than direct evidence of working state discipline.
    confidence: high
    evidence_paths:
      - `blocks/context/full_history.py`
      - `blocks/context/sliding_window.py`
      - `blocks/context/summarize_on_overflow.py`
      - `blocks/context/structured_sections.py`
      - `blocks/README.md`
      - `runner/agent.py`
      - `runner/docker_sandbox.py`
      - `runner/logger.py`
      - `evals/context_eval.py`
- behavioral_reconstructions:
  - reconstruction_id: B1
    observation: BigAI trajectories and reconstruction helpers show planner-first role separation, executor fanout, explicit `.work/space` directories, artifact restoration, and verifier-centered cleanup, while the BigAI SDK memory docs describe a message/chunk memory module with `session_id`-style metadata and optional persistence.
    inference: BigAI likely has a multi-layer context/state design with role handoff plus a separate memory module, but the Wave 04 corpus does not expose the actual implementation path where those layers meet. This remains behavioral reconstruction, not source-backed fact.
    confidence: medium
    weakness: hidden scheduler, prompt assembly, workspace-state internals, and real memory retrieval code remain unavailable
    evidence_paths:
      - `research/analysis/bigai_trace_layer/output/final_harness_reconstruction.md`
      - `research/analysis/bigai_trace_layer/output/question_answers.json`
      - `research/sources/docs/bigai/raw/sdk_documentation_memory.txt`
      - `research/sources/trajectories/BigAI/git-multibranch/62d2bdf3-6678-44a2-bb90-efd397b7937d-traj.txt`
      - `research/sources/trajectories/BigAI/break-filter-js-from-html/4e6a3070-4a78-4c1a-ac1c-c0651045db08-traj.txt`
  - reconstruction_id: B2
    observation: BigAI `git-multibranch` repeatedly reasons about shared worktrees, deploy directories, and cleanup state; `break-filter-js-from-html` uses multi-executor workspace coordination and explicit restoration of `test_outputs.py`.
    inference: BigAI behaves like a workspace-discipline and handoff-heavy family, but the current corpus cannot show whether that substrate is backed by durable memory retrieval, controller state, or only task-local artifacts.
    confidence: medium
    weakness: no mirrored source; trajectory-only plus docs pressure
    evidence_paths:
      - `research/sources/trajectories/BigAI/git-multibranch/baabd142-9b5e-457d-8c39-2cdf5bd4f462-traj.txt`
      - `research/sources/trajectories/BigAI/break-filter-js-from-html/4e6a3070-4a78-4c1a-ac1c-c0651045db08-traj.txt`
- subsystem_findings:
  - DeepAgents subsystem split:
    - context assembly: AGENTS.md memory sources appended into the system prompt by `MemoryMiddleware`
    - compaction/handoff: summarization middleware trims old messages, writes them to `/conversation_history/{thread_id}.md`, and injects a summary message that points back to the stored history path
    - state persistence: `StateBackend` is thread-local and checkpoint-backed; `StoreBackend` is namespaced and cross-thread persistent; CLI thread metadata is stored in `~/.deepagents/sessions.db`
    - workspace/artifact discipline: current visible state is more file/store oriented than repo-worktree oriented
  - KIRA subsystem split:
    - classic Terminus-KIRA: live terminal capture, terminal-state injection, proactive/fallback summarization, and checklist-driven completion gating
    - KiraClaw: bounded session history, session lanes, auto-saved semantic/episodic memory classification, markdown memory files plus JSON index, async retrieval/save runtime
    - key distinction: session continuation and durable memory are separate codepaths
  - A-Evolve subsystem split:
    - workspace contract: prompt, skills, tools, memory, and evolution artifacts all live on disk under a typed FS schema
    - reload/reset path: `reload_from_fs()` rehydrates prompt/skills/memories from workspace after each evolution cycle
    - recovery path: git commit/tag/worktree operations preserve workspace state and rollback history
    - active solver doctrine: the reference terminal solver currently privileges skills and prompt over memory injection
  - Quarantine claw-code findings:
    - visible session persistence exists, but mainly as local JSON session snapshots and in-memory transcript compaction
    - remote/resume branches are placeholders in the inspected scope
    - this family should remain archive/quarantine pressure, not promoted peer evidence
  - Local harness findings:
    - architecture is already converging on the right separations for Wave 04: context, verification, recovery, execution, and logging are explicitly decoupled
    - actual mechanism implementations for compaction, resume, checkpoint verification, rollback, and artifact discipline still need to be built
- source_behavior_matches:
  - match_id: M1
    observation: DeepAgents trajectories show short-horizon todo state, replay scripts, and artifact-backed reruns rather than visible durable memory retrieval.
    inference: That behavior matches the source split where prompt memory, summarization offload, ephemeral thread state, and persistent store are optional composable layers rather than one always-on long-term memory mechanism.
    confidence: high
    evidence_paths:
      - `research/sources/codebases/deepagents/libs/deepagents/deepagents/middleware/memory.py`
      - `research/sources/codebases/deepagents/libs/deepagents/deepagents/middleware/summarization.py`
      - `research/sources/codebases/deepagents/libs/deepagents/deepagents/backends/state.py`
      - `research/sources/trajectories/deepagents/git-multibranch/e6e6d3a5-ee75-489a-a4a0-c3a751ea3421-traj.txt`
      - `research/sources/trajectories/deepagents/custom-memory-heap-crash/aa903d02-9999-4aa2-8d70-3a73a4eb6d8c-traj.txt`
      - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/outputs/trajectory_failure_analyst.md`
  - match_id: M2
    observation: Terminus-KIRA trajectories are dominated by checklist-bearing analyses, terminal-state review, and script-backed verification in `git-multibranch`.
    inference: That matches the source-visible KIRA mechanism where the current terminal state is injected into prompts and summarization creates handoff prompts, while completion doctrine explicitly audits minimal workspace state change.
    confidence: high
    evidence_paths:
      - `research/sources/codebases/KIRA/terminus_kira/terminus_kira.py`
      - `research/sources/codebases/KIRA/prompt-templates/terminus-kira.txt`
      - `research/sources/trajectories/terminus-kira/git-multibranch/80b5619c-2b60-45e3-b209-ffbf02d27aa9-traj.txt`
      - `research/sources/trajectories/terminus-kira/break-filter-js-from-html/eaf5da17-d140-4652-bd00-3e6a83bf66cf-traj.txt`
  - match_id: M3
    observation: Wave 04 trajectory synthesis keeps a minimal baseline visible in which artifact continuity and clean workspace state matter more than rich memory rhetoric.
    inference: A-Evolve source strongly supports that baseline because its durable substrate is the workspace plus git-tagged history, not necessarily memory injection into the active solve loop.
    confidence: medium
    weakness: A-Evolve is source-backed here but not one of the required trajectory families in this wave
    evidence_paths:
      - `research/sources/codebases/a-evolve/DESIGN.md`
      - `research/sources/codebases/a-evolve/agent_evolve/agents/terminal/agent.py`
      - `research/sources/codebases/a-evolve/agent_evolve/contract/workspace.py`
      - `research/sources/codebases/a-evolve/agent_evolve/engine/versioning.py`
      - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/outputs/trajectory_failure_analyst.md`
- source_behavior_mismatches:
  - mismatch_id: X1
    observation: A-Evolve's framework persists memories on disk and exposes them through `BaseAgent`, but the reference terminal agent explicitly suppresses memory injection for Terminal-Bench solves.
    inference: Any cross-system claim that A-Evolve's Wave 04 behavior is memory-led would overstate the source; the active solver path is skill- and prompt-led despite a durable workspace memory layer.
    confidence: high
    evidence_paths:
      - `research/sources/codebases/a-evolve/agent_evolve/protocol/base_agent.py`
      - `research/sources/codebases/a-evolve/agent_evolve/agents/terminal/agent.py`
      - `research/sources/codebases/a-evolve/agent_evolve/contract/workspace.py`
  - mismatch_id: X2
    observation: KiraClaw source exposes a richer durable memory runtime than the required KIRA trajectory slices show; the sampled trajectories mostly surface classic Terminus-KIRA checklist and terminal-state behavior, not memory-file retrieval.
    inference: The KIRA family is source-richer than the current Wave 04 trajectory slice reveals, so strong claims about visible durable memory use in sampled KIRA behavior should stay modest.
    confidence: medium
    weakness: the richer runtime belongs to adjacent KiraClaw paths, not the exact Terminus-KIRA agent used in the required trajectories
    evidence_paths:
      - `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/session_manager.py`
      - `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/memory_store.py`
      - `research/sources/trajectories/terminus-kira/git-multibranch/80b5619c-2b60-45e3-b209-ffbf02d27aa9-traj.txt`
      - `research/sources/trajectories/terminus-kira/custom-memory-heap-crash/3c178f63-b5da-4ffa-b4c3-225d919b72ec-traj.txt`
  - mismatch_id: X3
    observation: DeepAgents source exposes durable store namespaces, GitHub Action cache scopes, and memory middleware, but the required trajectory slices mostly show local todo state, scripts, and reruns.
    inference: DeepAgents source supports more durable memory/persistence capacity than the required Wave 04 run slice demonstrates, so the behavioral story remains narrower than the implementation menu.
    confidence: medium
    weakness: required trajectories are single-task windows rather than multi-run memory tests
    evidence_paths:
      - `research/sources/codebases/deepagents/action.yml`
      - `research/sources/codebases/deepagents/libs/deepagents/deepagents/backends/store.py`
      - `research/sources/codebases/deepagents/libs/deepagents/deepagents/middleware/memory.py`
      - `research/sources/trajectories/deepagents/break-filter-js-from-html/802e3807-8f1a-4c15-991c-9cdb03d16cef-traj.txt`
      - `research/sources/trajectories/deepagents/custom-memory-heap-crash/aa903d02-9999-4aa2-8d70-3a73a4eb6d8c-traj.txt`
  - mismatch_id: X4
    observation: Quarantine claw-code includes session persistence and transcript compaction, but the same inspected scope also marks remote/resume surfaces as placeholders and frames the whole tree as a Python porting workspace rather than a finished runtime peer.
    inference: Claw-code should remain archive/quarantine pressure, not promoted first-class source proof for Wave 04 mechanism families.
    confidence: high
    evidence_paths:
      - `research/sources/codebases/quarantine/claw-code/README.md`
      - `research/sources/codebases/quarantine/claw-code/src/session_store.py`
      - `research/sources/codebases/quarantine/claw-code/src/query_engine.py`
      - `research/sources/codebases/quarantine/claw-code/src/remote_runtime.py`
- archive_or_visibility_limits:
  - BigAI has no visible source; all BigAI mechanism judgments remain behavioral reconstruction plus docs pressure.
  - `research/sources/codebases/quarantine/claw-code/**` is visibly a porting/quarantine workspace with placeholder state branches, so its runtime/state findings are inherently lower-status than DeepAgents, KIRA, or A-Evolve.
  - Harbor `TmuxSession` internals that underlie Terminus-KIRA session behavior are imported but not available in the required mirrored source surface.
  - Local harness files under `blocks/` and `runner/` are not yet implemented deeply enough to support strong behavior claims.
  - Cross-family compaction/handoff and claw-code runtime path mapping are improved by the landed support artifacts, but deeper follow-up support would still be needed before making stronger resumability claims.
- confidence_notes:
  - High-confidence:
    - DeepAgents visibly separates prompt memory, summarization offload, ephemeral state, and durable store mechanisms
    - KIRA visibly separates terminal-state summarization from KiraClaw durable memory runtime
    - A-Evolve makes the workspace and git history the durable state substrate
    - local harness is still architectural scaffold, not implemented state doctrine
  - Medium-confidence:
    - KIRA family source richness exceeds what the required trajectory slices presently expose
    - DeepAgents durable-memory capacity is broader than the required Wave 04 run windows demonstrate
    - A-Evolve source aligns with the artifact-first baseline, but direct trajectory reconciliation for A-Evolve is absent in this wave
  - Low-confidence:
    - any claim about BigAI's actual implementation path for memory/workspace state
    - any claim that claw-code placeholders already represent a stable runtime family
- open_questions:
  - Does the unread KIRA-Slack memory-manager surface materially change the KIRA family split between checklist/session state and durable memory retrieval?
  - Which DeepAgents trajectories, if any, actually exercise cross-thread or cross-run memory retrieval rather than only in-run artifact continuity?
  - Can Harbor `TmuxSession` internals materially change the current interpretation of KIRA's context compaction and restore surfaces?
  - Should Wave 04 principal synthesis treat A-Evolve's terminal-agent memory suppression as the main anti-memory baseline, or keep the stronger baseline at direct trajectory-visible artifact continuity only?
  - Is there any first-class non-quarantine source family besides A-Evolve that treats git-versioned workspace rollback as the primary state substrate?
- next_hand_off_target:
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/outputs/contradiction_analyst.md`
