TRAJECTORY_FAILURE_OUTPUT
- artifact: mechanism_map / wave_04_context_state_memory_workspace
- role: trajectory/failure analyst
- preflight_scope_confirmed:
  - This is a vertical mechanism-domain wave centered on context, state, memory, and workspace discipline, not a verification-only or generic execution-control pass.
  - Trajectories are the primary empirical anchor for this lane; source remains the separate implementation anchor.
  - The optional eval/benchmark fifth lane stays inactive in this lane pass because none of the required Wave 04 trajectory slices made grader-side state comparison or benchmark contract logic load-bearing for the promoted claims.
- preflight_planned_read_order:
  - 1. Wave control surfaces and coverage anchors:
    - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/brief.md`
    - `tracking/collab/stage_02_synthesis/mechanism_map/synthesis/cumulative_synthesis.md`
    - `tracking/collab/stage_02_synthesis/coverage_register/current_status.md`
    - `research/intake/normalized/manifests/corpus__captured_for_synthetic_prep.json`
    - `tracking/collab/stage_02_synthesis/evidence_inventory/outputs/organizer.md`
  - 2. Required trajectory slices across the three anchor tasks:
    - `research/sources/trajectories/BigAI/git-multibranch/*.txt`
    - `research/sources/trajectories/deepagents/git-multibranch/*.txt`
    - `research/sources/trajectories/terminus-kira/git-multibranch/*.txt`
    - `research/sources/trajectories/BigAI/break-filter-js-from-html/*.txt`
    - `research/sources/trajectories/deepagents/break-filter-js-from-html/*.txt`
    - `research/sources/trajectories/terminus-kira/break-filter-js-from-html/*.txt`
    - `research/sources/trajectories/BigAI/custom-memory-heap-crash/*.txt`
    - `research/sources/trajectories/deepagents/custom-memory-heap-crash/*.txt`
    - `research/sources/trajectories/terminus-kira/custom-memory-heap-crash/*.txt`
  - 3. BigAI behavior-reconstruction helpers used only as secondary pressure:
    - `research/analysis/bigai_trace_layer/output/final_harness_reconstruction.md`
    - `research/analysis/bigai_trace_layer/output/question_answers.json`
    - `research/sources/docs/bigai/raw/sdk_documentation_memory.txt`
  - 4. Saved support artifact for coverage discipline:
    - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/outputs/trajectory_support_context_workspace_matrix.md`
- preflight_critical_sources_selected:
  - Core trajectory slices:
    - `research/sources/trajectories/BigAI/git-multibranch/62d2bdf3-6678-44a2-bb90-efd397b7937d-traj.txt`
    - `research/sources/trajectories/BigAI/git-multibranch/baabd142-9b5e-457d-8c39-2cdf5bd4f462-traj.txt`
    - `research/sources/trajectories/deepagents/git-multibranch/e6e6d3a5-ee75-489a-a4a0-c3a751ea3421-traj.txt`
    - `research/sources/trajectories/terminus-kira/git-multibranch/80b5619c-2b60-45e3-b209-ffbf02d27aa9-traj.txt`
    - `research/sources/trajectories/deepagents/break-filter-js-from-html/802e3807-8f1a-4c15-991c-9cdb03d16cef-traj.txt`
    - `research/sources/trajectories/terminus-kira/break-filter-js-from-html/eaf5da17-d140-4652-bd00-3e6a83bf66cf-traj.txt`
    - `research/sources/trajectories/BigAI/custom-memory-heap-crash/11834f22-09ea-4bc7-9a11-68f574976a10-traj.txt`
    - `research/sources/trajectories/deepagents/custom-memory-heap-crash/aa903d02-9999-4aa2-8d70-3a73a4eb6d8c-traj.txt`
    - `research/sources/trajectories/terminus-kira/custom-memory-heap-crash/3c178f63-b5da-4ffa-b4c3-225d919b72ec-traj.txt`
  - BigAI contradiction-pressure helpers:
    - `research/analysis/bigai_trace_layer/output/question_answers.json`
    - `research/analysis/bigai_trace_layer/output/final_harness_reconstruction.md`
  - Minimal-sufficient baseline kept visible:
    - explicit workspace artifacts and verification scripts with little or no durable memory subsystem, especially in `deepagents/break-filter-js-from-html` and `terminus-kira/git-multibranch`
  - Required support artifact before strong coverage claim:
    - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/outputs/trajectory_support_context_workspace_matrix.md`
- preflight_coverage_risks:
  - `tracking/collab/stage_02_synthesis/evidence_inventory/outputs/organizer.md` is still empty, so direct path accounting remains mandatory.
  - BigAI is still behavior-only; hidden prompt assembly, true memory substrate, and internal scheduler state remain unobserved.
  - `terminus-kira/custom-memory-heap-crash` is thinner as a state-memory slice than the DeepAgents and BigAI crash slices.
  - Optional long-tail pressure from `headless-terminal` and `large-scale-text-editing` remains unread in this pass.
- preflight_likely_blind_spots:
  - restart-safe resumability beyond the sampled run windows
  - tar-bundle internal files that were not expanded in this pass
  - source-backed explanations for BigAI workspace or memory behavior
  - long-term memory retrieval claims that would require more than run-local artifact continuity
- preflight_blockers:
  - none; the required trajectory slices are sufficient for an honest first-pass trajectory synthesis if claims stay at artifact continuity, workspace discipline, and weak durable-memory conclusions
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
  - `research/sources/trajectories/BigAI/git-multibranch/62d2bdf3-6678-44a2-bb90-efd397b7937d-traj.txt`
  - `research/sources/trajectories/BigAI/git-multibranch/baabd142-9b5e-457d-8c39-2cdf5bd4f462-traj.txt`
  - `research/sources/trajectories/deepagents/git-multibranch/e6e6d3a5-ee75-489a-a4a0-c3a751ea3421-traj.txt`
  - `research/sources/trajectories/terminus-kira/git-multibranch/80b5619c-2b60-45e3-b209-ffbf02d27aa9-traj.txt`
  - `research/sources/trajectories/BigAI/break-filter-js-from-html/4389d2e9-7d17-4dc1-b0bd-5d1bde2716b6-traj.txt`
  - `research/sources/trajectories/BigAI/break-filter-js-from-html/4e6a3070-4a78-4c1a-ac1c-c0651045db08-traj.txt`
  - `research/sources/trajectories/deepagents/break-filter-js-from-html/802e3807-8f1a-4c15-991c-9cdb03d16cef-traj.txt`
  - `research/sources/trajectories/terminus-kira/break-filter-js-from-html/eaf5da17-d140-4652-bd00-3e6a83bf66cf-traj.txt`
  - `research/sources/trajectories/BigAI/custom-memory-heap-crash/11834f22-09ea-4bc7-9a11-68f574976a10-traj.txt`
  - `research/sources/trajectories/deepagents/custom-memory-heap-crash/aa903d02-9999-4aa2-8d70-3a73a4eb6d8c-traj.txt`
  - `research/sources/trajectories/terminus-kira/custom-memory-heap-crash/3c178f63-b5da-4ffa-b4c3-225d919b72ec-traj.txt`
  - `research/analysis/bigai_trace_layer/output/final_harness_reconstruction.md`
  - `research/analysis/bigai_trace_layer/output/question_answers.json`
  - `research/sources/docs/bigai/raw/sdk_documentation_memory.txt`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/outputs/trajectory_support_context_workspace_matrix.md`
- coverage_not_yet_used:
  - `research/sources/trajectories/*/headless-terminal/**`
  - `research/sources/trajectories/*/large-scale-text-editing/**`
  - `research/sources/trajectories/BigAI/adaptive-rejection-sampler/**`
  - tar-bundle internals beyond the visible `*-traj.txt` files
  - current wave source-system dossiers and trajectory case studies named in the packet
  - mirrored codebases and local harness paths for reconciliation, which belong primarily to the codebase/source lane
- evidence_classes_touched:
  - trajectories
  - behavior-reconstruction analysis
  - docs
  - local synthesis control surfaces
- priority_sources_not_yet_read:
  - `research/sources/trajectories/BigAI/adaptive-rejection-sampler/**`
  - `research/sources/trajectories/*/headless-terminal/**`
  - `research/sources/trajectories/*/large-scale-text-editing/**`
  - `tracking/collab/stage_02_synthesis/trajectory_case_studies/git_multibranch.md`
  - `tracking/collab/stage_02_synthesis/trajectory_case_studies/break_filter_js_from_html.md`
  - `tracking/collab/stage_02_synthesis/trajectory_case_studies/custom_memory_heap_crash.md`
- support_artifacts_used:
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/outputs/trajectory_support_context_workspace_matrix.md`
- support_artifacts_requested_or_deferred:
  - used:
    - `trajectory_support_context_workspace_matrix.md`
  - deferred:
    - `trajectory_support_memory_state_drift_cases.md`
    - `trajectory_support_branch_worktree_state_table.md`
    - `trajectory_support_run_to_source_link_map.md`
- coverage_register_updates_needed:
  - after principal synthesis, update `tracking/collab/stage_02_synthesis/coverage_register/current_status.md` to show Wave 04 trajectory-first required slices are now substantively read even though long-tail pressure and restart/resume depth remain open
  - keep the carry-forward warning that organizer routing is still weaker than direct path accounting
- required_dossier_updates:
  - `tracking/collab/stage_02_synthesis/source_system_dossiers/deepagents.md`
  - `tracking/collab/stage_02_synthesis/source_system_dossiers/KIRA.md`
  - `tracking/collab/stage_02_synthesis/source_system_dossiers/a-evolve.md`
  - `tracking/collab/stage_02_synthesis/source_system_dossiers/BigAI_behavioral.md`
  - `tracking/collab/stage_02_synthesis/source_system_dossiers/claw-code.md`
  - `tracking/collab/stage_02_synthesis/trajectory_case_studies/git_multibranch.md`
  - `tracking/collab/stage_02_synthesis/trajectory_case_studies/break_filter_js_from_html.md`
  - `tracking/collab/stage_02_synthesis/trajectory_case_studies/custom_memory_heap_crash.md`
- direct_behavior_observations:
  - claim_id: T1
    observation: Across the required slices, the dominant retained state is not a durable memory store but explicit run-local artifacts: planner todo lists, KIRA checklist JSON, saved test scripts, edited deliverable files, and clean repo/workspace state.
    inference: The strongest trajectory-backed baseline family is artifact continuity and explicit state bookkeeping, not general long-term memory.
    confidence: high
    weakness: This is a trajectory-only claim; source lanes still need to test whether any family hides a richer memory subsystem beneath similar behavior.
    evidence_paths:
      - `research/sources/trajectories/deepagents/git-multibranch/e6e6d3a5-ee75-489a-a4a0-c3a751ea3421-traj.txt`
      - `research/sources/trajectories/terminus-kira/git-multibranch/80b5619c-2b60-45e3-b209-ffbf02d27aa9-traj.txt`
      - `research/sources/trajectories/deepagents/custom-memory-heap-crash/aa903d02-9999-4aa2-8d70-3a73a4eb6d8c-traj.txt`
      - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/outputs/trajectory_support_context_workspace_matrix.md`
  - claim_id: T2
    observation: `git-multibranch` makes workspace and branch state load-bearing. BigAI explicitly resets `/git/project` and clears `/var/www/html/main/*` and `/var/www/html/dev/*`; KIRA abandons bare-repo `checkout` in favor of `git archive | tar -x`; DeepAgents keeps branch-specific deploy directories and reruns a full clone/push/curl workflow from temporary repos.
    inference: Workspace and branch hygiene are real trajectory-visible state-safety mechanisms and should not be collapsed into "memory."
    confidence: high
    weakness: This is strongest in `git-multibranch`; the HTML and heap-crash slices do not make branch state central.
    evidence_paths:
      - `research/sources/trajectories/BigAI/git-multibranch/62d2bdf3-6678-44a2-bb90-efd397b7937d-traj.txt`
      - `research/sources/trajectories/BigAI/git-multibranch/baabd142-9b5e-457d-8c39-2cdf5bd4f462-traj.txt`
      - `research/sources/trajectories/deepagents/git-multibranch/e6e6d3a5-ee75-489a-a4a0-c3a751ea3421-traj.txt`
      - `research/sources/trajectories/terminus-kira/git-multibranch/80b5619c-2b60-45e3-b209-ffbf02d27aa9-traj.txt`
  - claim_id: T3
    observation: BigAI shows the richest visible handoff discipline: planner-first role separation, executor fanout, verifier closure, and repeated cleanup reports that explicitly describe restored clean state.
    inference: BigAI currently looks like a context-compaction and handoff-heavy family, but only as behavioral reconstruction.
    confidence: medium
    weakness: No BigAI source is available, and the internal controller / prompt assembly / real memory substrate remain hidden.
    evidence_paths:
      - `research/sources/trajectories/BigAI/git-multibranch/62d2bdf3-6678-44a2-bb90-efd397b7937d-traj.txt`
      - `research/sources/trajectories/BigAI/git-multibranch/baabd142-9b5e-457d-8c39-2cdf5bd4f462-traj.txt`
      - `research/analysis/bigai_trace_layer/output/question_answers.json`
      - `research/analysis/bigai_trace_layer/output/final_harness_reconstruction.md`
  - claim_id: T4
    observation: DeepAgents carries state forward mostly through in-run todos plus reproducible scripts and reruns, not through visible durable memory. In `git-multibranch` it updates todos and creates reusable verification helpers under `/tmp`; in `custom-memory-heap-crash` it keeps the same root cause in view through repeated compile/run/Valgrind loops on `/app/user.cpp`.
    inference: DeepAgents currently supports a procedural state-management family: short-horizon todo state plus artifact-backed replay.
    confidence: high
    weakness: This is still trajectory-visible behavior; the source lane must determine how much of this is framework policy versus agent habit.
    evidence_paths:
      - `research/sources/trajectories/deepagents/git-multibranch/e6e6d3a5-ee75-489a-a4a0-c3a751ea3421-traj.txt`
      - `research/sources/trajectories/deepagents/break-filter-js-from-html/802e3807-8f1a-4c15-991c-9cdb03d16cef-traj.txt`
      - `research/sources/trajectories/deepagents/custom-memory-heap-crash/aa903d02-9999-4aa2-8d70-3a73a4eb6d8c-traj.txt`
  - claim_id: T5
    observation: KIRA keeps state visible as explicit per-turn checklist summaries and shell-scripted verification, but the sampled runs show less reusable workspace structure than BigAI or DeepAgents. In `git-multibranch` it writes `/app/test_deploy.sh`; in `custom-memory-heap-crash` it iterates through compile/run/gdb steps and proposes a minimal `std::ostringstream` pre-initialization fix.
    inference: KIRA currently looks like a checklist-and-batch-command family with thinner persistent workspace discipline in the sampled Wave 04 slices.
    confidence: medium
    weakness: The custom-memory slice is thinner at the end state, so the family comparison should stay modest until more lines or source reconciliation are read.
    evidence_paths:
      - `research/sources/trajectories/terminus-kira/git-multibranch/80b5619c-2b60-45e3-b209-ffbf02d27aa9-traj.txt`
      - `research/sources/trajectories/terminus-kira/break-filter-js-from-html/eaf5da17-d140-4652-bd00-3e6a83bf66cf-traj.txt`
      - `research/sources/trajectories/terminus-kira/custom-memory-heap-crash/3c178f63-b5da-4ffa-b4c3-225d919b72ec-traj.txt`
  - claim_id: T6
    observation: The three `custom-memory-heap-crash` slices are about runtime allocator and cleanup state, not agent long-term memory. DeepAgents explicitly moves facet registration into `user_init()` and releases the exception pool in `user_cleanup()`. KIRA proposes early `ostringstream` use to force facet allocation before the custom heap. BigAI reconstructs the crash around allocator / facet cleanup order and repeated verification.
    inference: Wave 04 needs to separate runtime memory-management state from agent memory narratives; the corpus uses the same word "memory" for materially different mechanisms.
    confidence: high
    weakness: BigAI remains behavior-only, and KIRA's final stabilized fix is less explicit than DeepAgents' in the sampled lines.
    evidence_paths:
      - `research/sources/trajectories/BigAI/custom-memory-heap-crash/11834f22-09ea-4bc7-9a11-68f574976a10-traj.txt`
      - `research/sources/trajectories/deepagents/custom-memory-heap-crash/aa903d02-9999-4aa2-8d70-3a73a4eb6d8c-traj.txt`
      - `research/sources/trajectories/terminus-kira/custom-memory-heap-crash/3c178f63-b5da-4ffa-b4c3-225d919b72ec-traj.txt`
- workflow_patterns:
  - Pattern A: explicit state checklist or todo before and during execution
    - BigAI planner todo and verifier handoff
    - DeepAgents `write_todos`
    - KIRA checklist-bearing JSON analysis blocks
  - Pattern B: save or recreate a runnable artifact, then replay it end-to-end
    - KIRA `/app/test_deploy.sh`
    - DeepAgents `/tmp/verifyrepo` and `/tmp/askpass.sh`
    - DeepAgents repeated compile/run/Valgrind loops on `/app/user.cpp`
  - Pattern C: treat clean workspace state as part of task success
    - BigAI explicitly resets repos and work directories
    - KIRA deletes extra break-filter probes before closing
    - DeepAgents verifies from fresh temporary clones
  - Pattern D: use run-local retrieval rather than durable memory
    - retrieve prior tool outputs, scripts, or file contents instead of querying a visible long-term memory store
- verification_and_recovery_patterns:
  - BigAI:
    - verification is a separate visible role and often reopens the run after initial progress
    - recovery commonly means restoring clean repo or delivery state before final handoff
  - DeepAgents:
    - recovery is narrower and procedural: rerun the workflow or add another verification pass until the same artifact path proves out
  - KIRA:
    - recovery is checklist-driven and shell-script-heavy; the verifier contract in the prompt strongly shapes state discipline
  - Cross-family:
    - the strongest visible recovery mechanism is not "retrieve long-term memory" but "reconstruct the required state from files, scripts, and reruns"
- failure_candidates:
  - candidate: workspace drift or dirty state blocks honest completion
    - support: BigAI `git-multibranch` repeatedly cleans and resets the repo and deploy directories before closing
    - confidence: high
  - candidate: branch/worktree handling is a distinct failure surface, not generic memory loss
    - support: BigAI reasons about shared bare-repo index effects; KIRA discards `checkout`-based deployment for archive extraction
    - confidence: high
  - candidate: stale or missing verification artifacts can force recovery loops even when the core exploit or fix is already known
    - support: break-filter runs rely on intact test files and repeat the verifier after recreating the right artifact state
    - confidence: medium
  - candidate: "memory" rhetoric can misclassify runtime allocator cleanup bugs as agent memory failures
    - support: all three `custom-memory-heap-crash` slices are about allocator/facet lifecycle ordering
    - confidence: high
- cross_family_comparisons:
  - strongest minimal baseline:
    - explicit artifact continuity with little or no durable memory subsystem
    - best supported by `deepagents/break-filter-js-from-html`, `deepagents/git-multibranch`, and `terminus-kira/git-multibranch`
  - strongest workspace-discipline family:
    - BigAI, but only as behavioral reconstruction
    - the family signal is planner/executor/verifier handoff plus cleanup/reset reports
  - strongest procedural replay family:
    - DeepAgents
    - todo updates plus reusable scripts and reruns dominate the visible state story
  - strongest checklist-batch family:
    - KIRA
    - explicit requirements checklist is the primary state surface, but sampled persistent workspace artifacts are thinner
  - strongest anti-collapse point:
    - branch hygiene, workspace cleanup, runtime allocator state, and agent memory should stay separate mechanism candidates
- contradiction_notes:
  - BigAI docs talk about a formal memory module with message persistence fields, but the required Wave 04 trajectories do not directly show that module in use; trajectory evidence is weaker and more artifact-centric than the docs rhetoric suggests.
  - The word "memory" spans at least two different phenomena in this wave:
    - agent conversational or retrieval memory
    - runtime heap / facet / exception-pool memory management
  - Branch hygiene is real in `git-multibranch`, but the HTML and heap-crash slices do not justify treating it as a universal context-state mechanism.
  - Restart and resumability still remain under-evidenced behaviorally in this trajectory pass.
- confidence_notes:
  - High-confidence claims:
    - explicit artifact continuity is real
    - workspace cleanup and branch hygiene are real in `git-multibranch`
    - runtime allocator state should not be collapsed into agent memory
  - Medium-confidence claims:
    - BigAI as a distinct context-compaction / handoff family
    - KIRA as thinner on persistent workspace discipline in this wave's sampled slices
  - Low-confidence areas:
    - any claim about durable long-term memory architecture
    - any promotion of restart-safe resumability
- open_questions:
  - Which trajectories, if any, show durable memory retrieval that cannot be reduced to scripts, files, tool history, or planner/checklist state?
  - Does long-tail pressure from `headless-terminal` or `large-scale-text-editing` change the current baseline that artifact continuity outranks memory rhetoric?
  - Can the source lane reconcile whether DeepAgents' todo state and replay scripts are framework doctrine or repeated agent habit?
  - Does KIRA have stronger persistent workspace discipline in unsampled slices than this wave's required slices reveal?
  - What exact mechanism restores `test_outputs.py` in the stronger BigAI break-filter slice, and is it pure tool-history retrieval or a richer artifact cache?
- next_hand_off_target:
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/outputs/contradiction_analyst.md`
