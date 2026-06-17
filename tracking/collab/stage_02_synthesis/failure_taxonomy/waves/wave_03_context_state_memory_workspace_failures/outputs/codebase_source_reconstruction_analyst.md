CODEBASE_SOURCE_RECON_OUTPUT
- artifact: `failure_taxonomy`
- role: `codebase/source-reconstruction analyst`
- preflight_scope_confirmed:
  - This pass is explicitly scoped to Wave 03 failure attribution for `context loss`, `stale/misleading memory`, `workspace/branch/path drift`, `session persistence/resume-state drift`, and `runtime-memory vs agent-memory boundary discipline`.
  - This is not a generic mechanism recap; attribution is framed as failure families with source-backed boundaries.
  - Optional eval fifth lane is treated as inactive by default in this lane because current read scope is source/trajectory state-control surfaces, not benchmark grader contract internals.
- preflight_planned_read_order:
  - Wave/control surfaces first: Wave 03 brief, support-subagent rules, output manifest, artifact decision/cumulative synthesis, coverage register, operating plan, lane-closure criteria, Wave 02 checklist adjudication, Mechanism Map Wave 04 principal synthesis.
  - Source families second: `deepagents`, `KIRA`, `a-evolve`, `quarantine/claw-code`.
  - Local harness surfaces third: `blocks/`, `runner/`, `evals/`.
  - Behavioral reconstruction pressure for no-source family and source/behavior tension last: BigAI trajectories and prior case-study synthesis paths.
- preflight_critical_sources_selected:
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/brief.md`
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/inputs/support_subagent_rules.md`
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/README.md`
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/decision.md`
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/synthesis/cumulative_synthesis.md`
  - `tracking/collab/stage_02_synthesis/coverage_register/current_status.md`
  - `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_PHASE_AND_WAVE_OPERATING_PLAN.md`
  - `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_LANE_CLOSURE_CRITERIA.md`
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/adjudication/checklist_adjudicator.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/synthesis/principal_synthesis.md`
  - `research/sources/codebases/deepagents/libs/deepagents/deepagents/middleware/{memory.py,summarization.py}`
  - `research/sources/codebases/deepagents/libs/deepagents/deepagents/backends/{state.py,store.py}`
  - `research/sources/codebases/deepagents/libs/cli/tests/integration_tests/test_compact_resume.py`
  - `research/sources/codebases/KIRA/terminus_kira/terminus_kira.py`
  - `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/{session_manager.py,memory_runtime.py,memory_store.py,memory_retriever.py,memory_tools.py,run_log_store.py}`
  - `research/sources/codebases/KIRA/KIRA-Slack/app/cc_agents/state_prompt.py`
  - `research/sources/codebases/a-evolve/agent_evolve/{contract/workspace.py,engine/versioning.py,engine/history.py,agents/terminal/agent.py}`
  - `research/sources/codebases/quarantine/claw-code/src/{context.py,session_store.py,state/__init__.py,reference_data/subsystems/state.json}`
  - `blocks/context/{full_history.py,sliding_window.py,summarize_on_overflow.py,structured_sections.py}`
  - `runner/{agent.py,logger.py,evaluator.py,docker_sandbox.py}`
  - `evals/{context_eval.py,verification_eval.py}`
  - `research/sources/trajectories/BigAI/{git-multibranch/62d2bdf3-6678-44a2-bb90-efd397b7937d-traj.txt,break-filter-js-from-html/4389d2e9-7d17-4dc1-b0bd-5d1bde2716b6-traj.txt,custom-memory-heap-crash/11834f22-09ea-4bc7-9a11-68f574976a10-traj.txt}`
  - `research/sources/trajectories/deepagents/git-multibranch/e6e6d3a5-ee75-489a-a4a0-c3a751ea3421-traj.txt`
  - `research/sources/trajectories/terminus-kira/{git-multibranch/80b5619c-2b60-45e3-b209-ffbf02d27aa9-traj.txt,break-filter-js-from-html/eaf5da17-d140-4652-bd00-3e6a83bf66cf-traj.txt,custom-memory-heap-crash/3c178f63-b5da-4ffa-b4c3-225d919b72ec-traj.txt,db-wal-recovery/3481ab1c-d322-4bda-bd10-49c0708403d2-traj.txt}`
  - `tracking/collab/stage_02_synthesis/trajectory_case_studies/{git_multibranch.md,break_filter_js_from_html.md,custom_memory_heap_crash.md,db_wal_recovery.md}`
- preflight_coverage_risks:
  - BigAI still has no mirrored source tree; all BigAI mechanism claims remain `behavioral reconstruction`.
  - KIRA and deepagents trajectory files are long and heavily prompt-prefixed; extracted claims are based on command/verification segments, not exhaustive full-run semantic parsing.
  - Local harness (`blocks/runner/evals`) remains largely scaffold-level, limiting direct local failure-attribution depth.
  - `claw-code` is quarantine/port-pressure only and should not be treated as first-class parity evidence.
- preflight_likely_blind_spots:
  - Hidden BigAI internal persistence/scheduler mechanisms behind visible planner/executor/verifier behavior.
  - Full KIRA-Slack memory/runtime behavior under long-horizon pressure beyond read files.
  - A-Evolve behavior prevalence in Wave 03 required task families (source is strong; direct task-family trajectory evidence here is thinner).
  - Benchmark grader/state-contract internals that might reactivate eval fifth lane.
- preflight_blockers:
  - none.
- coverage_used:
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/{brief.md,inputs/support_subagent_rules.md,outputs/README.md}`
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/{decision.md,synthesis/cumulative_synthesis.md}`
  - `tracking/collab/stage_02_synthesis/{coverage_register/current_status.md,DEEP_SYNTHESIS_PHASE_AND_WAVE_OPERATING_PLAN.md,DEEP_SYNTHESIS_LANE_CLOSURE_CRITERIA.md}`
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_02_verification_completion_and_recovery_failures/adjudication/checklist_adjudicator.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/synthesis/principal_synthesis.md`
  - `research/sources/codebases/deepagents/libs/deepagents/deepagents/middleware/{memory.py,summarization.py}`
  - `research/sources/codebases/deepagents/libs/deepagents/deepagents/backends/{state.py,store.py}`
  - `research/sources/codebases/deepagents/libs/cli/tests/integration_tests/test_compact_resume.py`
  - `research/sources/codebases/KIRA/terminus_kira/terminus_kira.py`
  - `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/{session_manager.py,memory_runtime.py,memory_store.py,memory_retriever.py,memory_tools.py,run_log_store.py}`
  - `research/sources/codebases/KIRA/KIRA-Slack/app/cc_agents/state_prompt.py`
  - `research/sources/codebases/a-evolve/agent_evolve/{contract/workspace.py,engine/versioning.py,engine/history.py,agents/terminal/agent.py}`
  - `research/sources/codebases/quarantine/claw-code/src/{context.py,session_store.py,state/__init__.py,reference_data/subsystems/state.json}`
  - `blocks/context/{full_history.py,sliding_window.py,summarize_on_overflow.py,structured_sections.py}`
  - `runner/{agent.py,logger.py,evaluator.py,docker_sandbox.py}`
  - `evals/{context_eval.py,verification_eval.py}`
  - `research/sources/trajectories/BigAI/{git-multibranch/62d2bdf3-6678-44a2-bb90-efd397b7937d-traj.txt,break-filter-js-from-html/4389d2e9-7d17-4dc1-b0bd-5d1bde2716b6-traj.txt,custom-memory-heap-crash/11834f22-09ea-4bc7-9a11-68f574976a10-traj.txt}`
  - `research/sources/trajectories/deepagents/git-multibranch/e6e6d3a5-ee75-489a-a4a0-c3a751ea3421-traj.txt`
  - `research/sources/trajectories/terminus-kira/{git-multibranch/80b5619c-2b60-45e3-b209-ffbf02d27aa9-traj.txt,break-filter-js-from-html/eaf5da17-d140-4652-bd00-3e6a83bf66cf-traj.txt,custom-memory-heap-crash/3c178f63-b5da-4ffa-b4c3-225d919b72ec-traj.txt,db-wal-recovery/3481ab1c-d322-4bda-bd10-49c0708403d2-traj.txt}`
  - `tracking/collab/stage_02_synthesis/trajectory_case_studies/{git_multibranch.md,break_filter_js_from_html.md,custom_memory_heap_crash.md,db_wal_recovery.md}`
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/{codebase_support_context_state_failure_map.md,codebase_support_workspace_persistence_map.md}`
- coverage_not_yet_used:
  - `research/sources/trajectories/BigAI/git-multibranch/baabd142-9b5e-457d-8c39-2cdf5bd4f462-traj.txt`
  - `research/analysis/bigai_trace_layer/output/answered_questions.md`
  - `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/schedule_store.py`
  - `research/sources/codebases/a-evolve/agent_evolve/engine/loop.py`
  - `research/sources/benchmarks/**` grader internals (deferred unless eval lane reactivated)
- evidence_classes_touched:
  - mirrored source code
  - local harness code
  - trajectory traces
  - trajectory case studies
  - wave governance/control surfaces
  - lane-generated support artifacts
- priority_sources_not_yet_read:
  - `research/analysis/bigai_trace_layer/output/answered_questions.md`
  - `research/sources/trajectories/BigAI/git-multibranch/baabd142-9b5e-457d-8c39-2cdf5bd4f462-traj.txt`
  - `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/schedule_store.py`
  - `research/sources/codebases/a-evolve/agent_evolve/engine/loop.py`
- support_artifacts_used:
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/codebase_support_context_state_failure_map.md`
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/codebase_support_workspace_persistence_map.md`
- support_artifacts_requested_or_deferred:
  - No additional support sub-agent was requested; both lane-allowed support artifacts were produced directly in this pass.
- coverage_register_updates_needed:
  - Change Wave 03 status from `packet-prepared, not started` to `in progress` with codebase lane output present.
  - Add Wave 03 codebase support artifacts under support-track coverage for this wave.
  - Preserve warning that BigAI claims remain behavioral-only and eval lane remains inactive unless reactivation condition is met.
- required_dossier_updates:
  - `tracking/collab/stage_02_synthesis/source_system_dossiers/deepagents.md`
  - `tracking/collab/stage_02_synthesis/source_system_dossiers/KIRA.md`
  - `tracking/collab/stage_02_synthesis/source_system_dossiers/BigAI_behavioral.md`
  - `tracking/collab/stage_02_synthesis/source_system_dossiers/a-evolve.md`
  - `tracking/collab/stage_02_synthesis/source_system_dossiers/claw-code.md`
  - `tracking/collab/stage_02_synthesis/literature_dossiers/themes/context_and_memory.md`
  - `tracking/collab/stage_02_synthesis/literature_dossiers/themes/workspace_and_artifact_discipline.md`
  - `tracking/collab/stage_02_synthesis/informal_cluster_dossiers/context_state_memory_workspace_failures.md`
- source_backed_mechanisms:
  - Claim A (`high`): DeepAgents implements explicit context-compaction state with a recoverable pointer (`_summarization_event`) and thread-keyed history files.
    Observation: summarization code computes cutoff indices, carries summary message plus optional history path, and warns when offload fails.
    Inference: Wave 03 should model compaction failure as a first-class state-loss risk, not generic model forgetfulness.
    Evidence: `research/sources/codebases/deepagents/libs/deepagents/deepagents/middleware/summarization.py`.
  - Claim B (`high`): DeepAgents separates thread-scoped state (`StateBackend`) from cross-thread storage (`StoreBackend`), with explicit checkpoint behavior.
    Observation: state backend is conversation-thread scoped; store backend introduces namespaced persistent backing.
    Inference: Wave 03 should separate `session/thread boundary failures` from `durable store failures`.
    Evidence: `research/sources/codebases/deepagents/libs/deepagents/deepagents/backends/{state.py,store.py}`.
  - Claim C (`medium`): DeepAgents resumability path is source-backed beyond single-turn memory via compact/resume integration tests.
    Observation: integration test restarts server and validates resumed-thread compaction with persisted history path.
    Inference: resumability substrate exists, but run-family prevalence remains uncertain for failure taxonomy saturation.
    Evidence: `research/sources/codebases/deepagents/libs/cli/tests/integration_tests/test_compact_resume.py`.
    Weakener: test-level evidence is stronger for capability existence than broad behavioral reliability.
  - Claim D (`high`): KIRA explicitly degrades context handling on overflow through summarize-or-fallback logic.
    Observation: on context length exceed, TerminusKira attempts `_summarize`; if unavailable, it retries with a limited current-screen prompt.
    Inference: this creates a concrete `state compression fallback` failure mode distinct from generic memory failure.
    Evidence: `research/sources/codebases/KIRA/terminus_kira/terminus_kira.py`.
  - Claim E (`high`): KiraClaw memory/session subsystem is explicitly bounded and failure-tolerant rather than fail-stop.
    Observation: memory runtime queue has bounded size; retrieval/save exceptions become warnings/errors with continued lane execution; retrieval clips and file-count limits are explicit.
    Inference: stale/missing memory can surface silently as degraded context quality, not only hard crashes.
    Evidence: `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/{memory_runtime.py,memory_store.py,session_manager.py}`.
  - Claim F (`high`): A-Evolve treats workspace as primary state substrate and deliberately suppresses runtime memory injection in the terminal solve loop.
    Observation: workspace contract exposes prompts/skills/tools/memory files; terminal agent comments state memory injection is disabled for time-sensitive tasks.
    Inference: Wave 03 must keep `workspace-artifact discipline` and `memory retrieval` as separate attribution classes.
    Evidence: `research/sources/codebases/a-evolve/agent_evolve/{contract/workspace.py,agents/terminal/agent.py}`.
  - Claim G (`high`): A-Evolve versioning makes rollback/persistence explicit and history-preserving.
    Observation: rollback restores prior content as a new commit, not destructive reset.
    Inference: state recovery failures can be analyzed as rollback policy failures without conflating with context-window failures.
    Evidence: `research/sources/codebases/a-evolve/agent_evolve/engine/versioning.py`.
  - Claim H (`high`): Local harness code in this repo currently exposes Wave 03 surfaces only as interfaces/stubs.
    Observation: context/recovery/verification/eval files are docstring contracts without implemented logic.
    Inference: current local harness cannot yet support strong source-backed attribution for Wave 03 control families.
    Evidence: `blocks/context/{full_history.py,sliding_window.py,summarize_on_overflow.py,structured_sections.py}`, `runner/{agent.py,evaluator.py,logger.py}`, `evals/{context_eval.py,verification_eval.py}`.
- behavioral_reconstructions:
  - Claim I (`medium`, behavioral reconstruction): BigAI trajectories show explicit planner/executor/verifier role and workspace governance doctrine (`.work/space`, delivery-dir cleanliness) in context-heavy runs.
    Observation: trajectory prompts and run traces explicitly encode team-space structure and verification roles.
    Inference: context/state coordination is behaviorally load-bearing, but implementation internals remain unverified.
    Evidence: `research/sources/trajectories/BigAI/git-multibranch/62d2bdf3-6678-44a2-bb90-efd397b7937d-traj.txt`, `research/sources/trajectories/BigAI/break-filter-js-from-html/4389d2e9-7d17-4dc1-b0bd-5d1bde2716b6-traj.txt`.
    Weakener: no mirrored BigAI source.
  - Claim J (`high`, behavioral reconstruction): In `custom-memory-heap-crash`, BigAI evidence is runtime allocator-memory debugging, not coding-agent long-term memory behavior.
    Observation: trajectory focus is release/debug, gdb/valgrind, and `user.cpp` lifecycle fixes.
    Inference: enforce anti-collapse rule separating runtime-memory failures from context/memory/state failure classes.
    Evidence: `research/sources/trajectories/BigAI/custom-memory-heap-crash/11834f22-09ea-4bc7-9a11-68f574976a10-traj.txt`.
- subsystem_findings:
  - `context compaction`: strongest in DeepAgents (explicit event/cutoff/offload) and KIRA (summarize-or-screen fallback), with different failure modes.
  - `session persistence`: strongest source-backed in DeepAgents and KiraClaw; present as git/versioning substrate in A-Evolve.
  - `workspace discipline`: strongest behaviorally in BigAI and source-backed in A-Evolve’s workspace contract.
  - `runtime-memory boundary`: custom-memory-heap trajectories reinforce keeping allocator-memory bugs out of coding-agent memory taxonomy.
  - `local harness readiness`: planned interfaces exist but implementation depth for Wave 03 families is not yet present.
- source_behavior_matches:
  - DeepAgents artifact-first trajectory behavior (`write_todos`, script replay verification) matches source design where context/state is externalized and checkpointed rather than hidden in monolithic prompt memory.
    Evidence: `research/sources/codebases/deepagents/libs/deepagents/deepagents/backends/state.py`, `research/sources/trajectories/deepagents/git-multibranch/e6e6d3a5-ee75-489a-a4a0-c3a751ea3421-traj.txt`.
  - KIRA checklist/protocol-heavy trajectories in git/break-filter slices match TerminusKira prompt doctrine and completion-control scaffolding.
    Evidence: `research/sources/codebases/KIRA/terminus_kira/terminus_kira.py`, `research/sources/trajectories/terminus-kira/git-multibranch/80b5619c-2b60-45e3-b209-ffbf02d27aa9-traj.txt`, `research/sources/trajectories/terminus-kira/break-filter-js-from-html/eaf5da17-d140-4652-bd00-3e6a83bf66cf-traj.txt`.
- source_behavior_mismatches:
  - KiraClaw source exposes substantial memory/session infrastructure, but required KIRA db-wal trajectory shows collapse into mount/overlay exploration with weak state recovery grounding.
    Confidence: `medium`.
    Evidence: `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/{session_manager.py,memory_runtime.py,memory_store.py}`, `research/sources/trajectories/terminus-kira/db-wal-recovery/3481ab1c-d322-4bda-bd10-49c0708403d2-traj.txt`.
    Weakener: single-run pressure for this exact failure mode.
  - DeepAgents source supports richer layered memory/store capacity than what required Wave 03 trajectories visibly exercise.
    Confidence: `medium`.
    Evidence: `research/sources/codebases/deepagents/libs/deepagents/deepagents/middleware/{memory.py,summarization.py}`, `research/sources/trajectories/deepagents/git-multibranch/e6e6d3a5-ee75-489a-a4a0-c3a751ea3421-traj.txt`.
    Weakener: trajectory sample coverage is task-limited.
  - A-Evolve has strong source-backed workspace/versioning structure but thin direct Wave 03 behavioral trajectory linkage in this pass.
    Confidence: `low` for prevalence; `high` for mechanism existence.
    Evidence: `research/sources/codebases/a-evolve/agent_evolve/{contract/workspace.py,engine/versioning.py}`.
    Weakener: behavior gap in current required run slice.
- archive_or_visibility_limits:
  - BigAI has no source; all BigAI mechanism claims remain behavioral reconstruction.
  - Claw-code is under quarantine and partly archive-referential (`state.json` metadata), limiting subsystem inspection depth.
  - Local harness files in `blocks/`, `runner/`, and `evals/` are largely interface stubs for Wave 03 surfaces.
- confidence_notes:
  - `high`: claims grounded in directly read source files with explicit control flow/constraints.
  - `medium`: source-behavior mismatch claims where trajectory slice depth is limited.
  - `low`: cross-family prevalence claims that rely on thin behavior for a source-rich system (not promoted as binding).
- open_questions:
  - Which KIRA run families (beyond inspected db-wal) reproduce context/session drift versus recover cleanly with memory/session substrate active?
  - In DeepAgents, what proportion of successful long-horizon runs relies on store-backed retrieval versus artifact-first replay scripts?
  - Should eval fifth lane be reactivated if Wave 03 contradiction review finds grader workspace contracts are confounded with workspace drift attribution?
  - What minimum implementation is needed in local `blocks/context/*` to make Wave 03 failure families testable instead of conceptual?
- next_hand_off_target:
  - `trajectory/failure analyst` for per-run attribution density on context/state/workspace failures.
  - `informal/issues/postmortems analyst` for contradiction-pressure clustering on stale memory, compaction loss, and workspace/path drift.
  - `principal synthesis` after contradiction pass.
