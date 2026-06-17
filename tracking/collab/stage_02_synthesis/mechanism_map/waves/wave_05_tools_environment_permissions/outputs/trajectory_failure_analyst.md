TRAJECTORY_FAILURE_OUTPUT
- artifact: mechanism_map / wave_05_tools_environment_permissions
- role: trajectory/failure analyst
- preflight_scope_confirmed:
  - This is a vertical mechanism-domain wave centered on tool gateways, environment handling, sandbox or permission boundaries, and cwd/workdir discipline.
  - This lane is trajectory-first. Implementation mechanism reconciliation is delegated to the codebase/source lane.
  - The optional eval/benchmark fifth lane remains inactive in this pass because verifier or benchmark-contract logic did not become load-bearing in the required trajectory slices.
  - The lane keeps tool choice, environment discovery, and permission boundaries separate instead of collapsing them into generic "execution quality."
- preflight_planned_read_order:
  - 1. Wave control and integrity anchors:
    - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/brief.md`
    - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/inputs/support_subagent_rules.md`
    - `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_EXECUTION_PROTOCOL.md`
    - `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_MULTI_AGENT_WORKFLOW_GUIDE.md`
    - `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_LANE_CLOSURE_CRITERIA.md`
    - `tracking/collab/stage_02_synthesis/mechanism_map/synthesis/cumulative_synthesis.md`
    - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/synthesis/principal_synthesis.md`
    - `tracking/collab/stage_02_synthesis/coverage_register/current_status.md`
    - `research/intake/normalized/manifests/corpus__captured_for_synthetic_prep.json`
  - 2. Required trajectory slices across three tasks and three families:
    - `research/sources/trajectories/BigAI/headless-terminal/`
    - `research/sources/trajectories/deepagents/headless-terminal/`
    - `research/sources/trajectories/terminus-kira/headless-terminal/`
    - `research/sources/trajectories/BigAI/extract-moves-from-video/`
    - `research/sources/trajectories/deepagents/extract-moves-from-video/`
    - `research/sources/trajectories/terminus-kira/extract-moves-from-video/`
    - `research/sources/trajectories/BigAI/cancel-async-tasks/`
    - `research/sources/trajectories/deepagents/cancel-async-tasks/`
    - `research/sources/trajectories/terminus-kira/cancel-async-tasks/`
  - 3. BigAI behavioral reconstruction pressure for tool and discovery claims:
    - `research/analysis/bigai_trace_layer/output/final_harness_reconstruction.md`
    - `research/analysis/bigai_trace_layer/output/question_answers.json`
  - 4. Wave support artifacts produced in-lane:
    - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/trajectory_support_tool_environment_matrix.md`
    - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/trajectory_support_permission_boundary_cases.md`
- preflight_critical_sources_selected:
  - trajectory anchors:
    - `research/sources/trajectories/deepagents/headless-terminal/8359bd4b-bdf5-4c33-b511-869e048e9f6f-traj.txt`
    - `research/sources/trajectories/deepagents/extract-moves-from-video/67dc6598-86d3-4439-b6be-de398cd964e8-traj.txt`
    - `research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf-traj.txt`
    - `research/sources/trajectories/terminus-kira/headless-terminal/a2ae3f53-cc59-4049-87ca-9e23781c00e4-traj.txt`
    - `research/sources/trajectories/terminus-kira/extract-moves-from-video/3df89e49-6187-4805-a273-641b4d82c5cd-traj.txt`
    - `research/sources/trajectories/terminus-kira/cancel-async-tasks/8d55545f-8ce2-49b7-9fc1-231635fc6a2d-traj.txt`
    - `research/sources/trajectories/BigAI/headless-terminal/cec71502-c287-4257-9aba-4e33b3668881-traj.txt`
    - `research/sources/trajectories/BigAI/extract-moves-from-video/953d42f6-a999-4f95-bc53-79cc2952688d-traj.txt`
    - `research/sources/trajectories/BigAI/cancel-async-tasks/17f3a357-c55a-4171-af6a-510581362baa-traj.txt`
    - `research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee-traj.txt`
    - `research/sources/trajectories/BigAI/cancel-async-tasks/d7992f9a-d71d-4513-b06d-2d0a38757603-traj.txt`
  - contradiction-pressure sources:
    - `research/analysis/bigai_trace_layer/output/question_answers.json`
    - `research/analysis/bigai_trace_layer/output/final_harness_reconstruction.md`
  - minimal-sufficient baseline held explicit:
    - shell plus file tooling with stable cwd/workdir discipline is sufficient to complete core tasks without browser-prestige assumptions.
  - required support artifacts before strong trajectory coverage claims:
    - `trajectory_support_tool_environment_matrix.md`
    - `trajectory_support_permission_boundary_cases.md`
- preflight_coverage_risks:
  - BigAI remains behavioral reconstruction with no direct source reconciliation in this lane.
  - No required slice exposes a complete explicit approval-policy protocol; permission safety can only be weakly inferred from behavior.
  - DeepAgents extract-moves slice is short and ends early with cancellation, reducing comparative depth for that task.
  - Optional long-tail `git-multibranch` pressure for path/worktree boundaries is not included in this pass.
- preflight_likely_blind_spots:
  - benchmark-side tool/environment contracts (eval lane inactive)
  - unsampled browser-specific trajectories outside this wave's required slices
  - hidden runtime permission controls not logged in trajectory text
  - source-level mechanism for BigAI tool orchestration
- preflight_blockers:
  - none. Required trajectory slices were readable enough for honest first-pass synthesis with explicit uncertainty.
- coverage_used:
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/brief.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/inputs/support_subagent_rules.md`
  - `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_EXECUTION_PROTOCOL.md`
  - `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_MULTI_AGENT_WORKFLOW_GUIDE.md`
  - `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_LANE_CLOSURE_CRITERIA.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/synthesis/cumulative_synthesis.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/synthesis/principal_synthesis.md`
  - `tracking/collab/stage_02_synthesis/coverage_register/current_status.md`
  - `research/intake/normalized/manifests/corpus__captured_for_synthetic_prep.json`
  - `research/sources/trajectories/deepagents/headless-terminal/8359bd4b-bdf5-4c33-b511-869e048e9f6f-traj.txt`
  - `research/sources/trajectories/deepagents/extract-moves-from-video/67dc6598-86d3-4439-b6be-de398cd964e8-traj.txt`
  - `research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf-traj.txt`
  - `research/sources/trajectories/terminus-kira/headless-terminal/a2ae3f53-cc59-4049-87ca-9e23781c00e4-traj.txt`
  - `research/sources/trajectories/terminus-kira/extract-moves-from-video/3df89e49-6187-4805-a273-641b4d82c5cd-traj.txt`
  - `research/sources/trajectories/terminus-kira/cancel-async-tasks/8d55545f-8ce2-49b7-9fc1-231635fc6a2d-traj.txt`
  - `research/sources/trajectories/BigAI/headless-terminal/cec71502-c287-4257-9aba-4e33b3668881-traj.txt`
  - `research/sources/trajectories/BigAI/extract-moves-from-video/953d42f6-a999-4f95-bc53-79cc2952688d-traj.txt`
  - `research/sources/trajectories/BigAI/cancel-async-tasks/17f3a357-c55a-4171-af6a-510581362baa-traj.txt`
  - `research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee-traj.txt`
  - `research/sources/trajectories/BigAI/cancel-async-tasks/d7992f9a-d71d-4513-b06d-2d0a38757603-traj.txt`
  - `research/analysis/bigai_trace_layer/output/final_harness_reconstruction.md`
  - `research/analysis/bigai_trace_layer/output/question_answers.json`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/trajectory_support_tool_environment_matrix.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/trajectory_support_permission_boundary_cases.md`
- coverage_not_yet_used:
  - optional long-tail:
    - `research/sources/trajectories/*/git-multibranch/`
  - non-trajectory classes for this lane pass:
    - `research/sources/codebases/**`
    - `research/sources/papers/**`
    - `research/sources/docs/**`
    - `research/sources/informal/**`
    - `research/sources/issues/**`
    - `research/sources/postmortems/**`
  - support artifacts not produced in this pass:
    - `trajectory_support_browser_terminal_substrate_table.md`
    - `trajectory_support_run_to_source_link_map.md`
- evidence_classes_touched:
  - trajectories
  - relevant local analysis (`bigai_trace_layer`)
  - wave control and coverage artifacts
- priority_sources_not_yet_read:
  - `research/sources/trajectories/*/git-multibranch/` (optional but useful for stronger cwd/worktree pressure)
  - `research/sources/codebases/deepagents/` (for trajectory-source reconciliation)
  - `research/sources/codebases/KIRA/`
  - `research/sources/codebases/a-evolve/`
  - `research/sources/codebases/quarantine/claw-code/`
  - `research/sources/docs/**` and `research/sources/issues/**` clusters named in wave brief
- support_artifacts_used:
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/trajectory_support_tool_environment_matrix.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/trajectory_support_permission_boundary_cases.md`
- support_artifacts_requested_or_deferred:
  - produced:
    - `trajectory_support_tool_environment_matrix.md`
    - `trajectory_support_permission_boundary_cases.md`
  - deferred:
    - `trajectory_support_browser_terminal_substrate_table.md`
    - `trajectory_support_run_to_source_link_map.md`
- coverage_register_updates_needed:
  - after principal synthesis, mark Wave 05 trajectory lane as complete with explicit caveat that permission safety remains under-evidenced without source or informal contradiction lanes.
  - maintain explicit note that BigAI claims in this lane are behavioral reconstruction only.
- required_dossier_updates:
  - required-by-wave (deferred in this lane run due scoped-write constraint to Wave 05 output paths only):
    - `tracking/collab/stage_02_synthesis/source_system_dossiers/deepagents.md`
    - `tracking/collab/stage_02_synthesis/source_system_dossiers/KIRA.md`
    - `tracking/collab/stage_02_synthesis/source_system_dossiers/a-evolve.md`
    - `tracking/collab/stage_02_synthesis/source_system_dossiers/BigAI_behavioral.md`
    - `tracking/collab/stage_02_synthesis/source_system_dossiers/claw-code.md`
    - `tracking/collab/stage_02_synthesis/literature_dossiers/themes/tool_use_and_gateways.md`
    - `tracking/collab/stage_02_synthesis/literature_dossiers/themes/environment_and_permissions.md`
    - `tracking/collab/stage_02_synthesis/informal_cluster_dossiers/tools_environment_permissions.md`
    - `tracking/collab/stage_02_synthesis/trajectory_case_studies/headless_terminal.md`
    - `tracking/collab/stage_02_synthesis/trajectory_case_studies/extract_moves_from_video.md`
    - `tracking/collab/stage_02_synthesis/trajectory_case_studies/cancel_async_tasks.md`
- direct_behavior_observations:
  - claim_id: W05-T1
    observation: The three families use materially different tool gateway surfaces in required slices: DeepAgents (`execute` plus file tools), Terminus-KIRA (`bash_command` with optional `image_read` and completion gate), BigAI (`run_shell_command`/`wait_shell_command`/`kill_shell_command` and occasional `interact_with_shell`).
    inference: tool gateway design is a distinct mechanism family axis and should not be flattened into generic execution control.
    confidence: high
    weakness: BigAI mechanism internals are not source-visible in this lane.
    evidence_paths:
      - `research/sources/trajectories/deepagents/headless-terminal/8359bd4b-bdf5-4c33-b511-869e048e9f6f-traj.txt`
      - `research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf-traj.txt`
      - `research/sources/trajectories/terminus-kira/headless-terminal/a2ae3f53-cc59-4049-87ca-9e23781c00e4-traj.txt`
      - `research/sources/trajectories/terminus-kira/extract-moves-from-video/3df89e49-6187-4805-a273-641b4d82c5cd-traj.txt`
      - `research/sources/trajectories/BigAI/headless-terminal/cec71502-c287-4257-9aba-4e33b3668881-traj.txt`
      - `research/sources/trajectories/BigAI/extract-moves-from-video/953d42f6-a999-4f95-bc53-79cc2952688d-traj.txt`
      - `research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee-traj.txt`
      - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/trajectory_support_tool_environment_matrix.md`

  - claim_id: W05-T2
    observation: Environment discovery appears structurally load-bearing: DeepAgents starts with explicit `Current Directory: /app`; BigAI reconstruction reports discovery-tagged behavior across parseable runs; KIRA prompts repeatedly include strict protocol and terminal-state framing.
    inference: environment discovery is a recurring precondition mechanism, not incidental narrative.
    confidence: medium
    weakness: BigAI evidence is behavioral reconstruction; KIRA evidence in this lane is prompt-shape heavy.
    evidence_paths:
      - `research/sources/trajectories/deepagents/headless-terminal/8359bd4b-bdf5-4c33-b511-869e048e9f6f-traj.txt`
      - `research/sources/trajectories/terminus-kira/headless-terminal/a2ae3f53-cc59-4049-87ca-9e23781c00e4-traj.txt`
      - `research/analysis/bigai_trace_layer/output/question_answers.json`

  - claim_id: W05-T3
    observation: cwd/workdir discipline is a first-order failure boundary: BigAI cancel-async shows `No module named 'run'` under `/tmp` pathing and then succeeds when execution is moved to `/app`.
    inference: path discipline should be treated as a mechanism card on its own (`cwd/workdir/path contract`), not merged into general debugging.
    confidence: high
    weakness: strongest direct example is from one BigAI run family.
    evidence_paths:
      - `research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee-traj.txt`
      - `research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf-traj.txt`
      - `research/sources/trajectories/terminus-kira/cancel-async-tasks/8d55545f-8ce2-49b7-9fc1-231635fc6a2d-traj.txt`

  - claim_id: W05-T4
    observation: Permission and boundary risk is visible behaviorally (root pip warning, process kill lifecycle errors, interpreter mismatch), but explicit approval-policy mechanics are largely absent in required slices.
    inference: this lane can promote permission-friction candidates, but not strong claims of robust permission safety.
    confidence: medium
    weakness: required trajectories do not expose end-to-end policy enforcement internals.
    evidence_paths:
      - `research/sources/trajectories/terminus-kira/headless-terminal/a2ae3f53-cc59-4049-87ca-9e23781c00e4-traj.txt`
      - `research/sources/trajectories/terminus-kira/extract-moves-from-video/3df89e49-6187-4805-a273-641b4d82c5cd-traj.txt`
      - `research/sources/trajectories/BigAI/extract-moves-from-video/953d42f6-a999-4f95-bc53-79cc2952688d-traj.txt`
      - `research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee-traj.txt`
      - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/trajectory_support_permission_boundary_cases.md`

  - claim_id: W05-T5
    observation: Browser-first prestige is not supported by this wave's required trajectories; the strongest completions are terminal-centric, with KIRA showing selective multimodal uplift (`image_read`) rather than substrate replacement.
    inference: baseline mechanism remains shell-plus-file tooling with disciplined cwd/process handling; richer substrate is conditional, not default superiority.
    confidence: high
    weakness: this claim is limited to required slice set, not all corpus tasks.
    evidence_paths:
      - `research/sources/trajectories/deepagents/headless-terminal/8359bd4b-bdf5-4c33-b511-869e048e9f6f-traj.txt`
      - `research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf-traj.txt`
      - `research/sources/trajectories/terminus-kira/extract-moves-from-video/3df89e49-6187-4805-a273-641b4d82c5cd-traj.txt`
      - `research/sources/trajectories/BigAI/headless-terminal/cec71502-c287-4257-9aba-4e33b3668881-traj.txt`
      - `research/sources/trajectories/BigAI/extract-moves-from-video/953d42f6-a999-4f95-bc53-79cc2952688d-traj.txt`

  - claim_id: W05-T6
    observation: Cancellation and interrupt semantics recur as a cross-family failure surface: DeepAgents extract aborts on `CancelledError`; KIRA and BigAI cancel-async runs spend substantial steps untangling cleanup behavior under cancellation and signal modes.
    inference: cancellation boundary handling is a stable mechanism candidate in this domain, not a one-off bug.
    confidence: high
    weakness: concentrated heavily in the `cancel-async-tasks` benchmark family.
    evidence_paths:
      - `research/sources/trajectories/deepagents/extract-moves-from-video/67dc6598-86d3-4439-b6be-de398cd964e8-traj.txt`
      - `research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf-traj.txt`
      - `research/sources/trajectories/terminus-kira/cancel-async-tasks/8d55545f-8ce2-49b7-9fc1-231635fc6a2d-traj.txt`
      - `research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee-traj.txt`
      - `research/sources/trajectories/BigAI/cancel-async-tasks/d7992f9a-d71d-4513-b06d-2d0a38757603-traj.txt`
- workflow_patterns:
  - Pattern A: discovery-then-action envelope
    - trajectories and reconstruction both show explicit or implicit environment discovery before heavy execution.
  - Pattern B: terminal-first control loop as default
    - all three families rely on shell execution as the primary action substrate.
  - Pattern C: async process supervision as a distinct tool family
    - strongest in BigAI via run/wait/kill/interact shell primitives.
  - Pattern D: hybrid multimodal uplift only when needed
    - KIRA adds `image_read` in video extraction; otherwise remains shell-dominant.
- verification_and_recovery_patterns:
  - DeepAgents:
    - recovers by writing focused tests inline and replaying cancellation scenarios with controlled scripts.
  - Terminus-KIRA:
    - recovers via long shell-batch iteration and repeated completion-gate attempts after warnings or test failures.
  - BigAI (behavioral reconstruction):
    - recovers through iterative shell experiments plus explicit process control (`wait`/`kill`) and planner-verifier looping.
  - Cross-family:
    - recovery is mostly operational (path correction, dependency correction, cancel-model correction), not abstract planning rhetoric.
- failure_candidates:
  - candidate: cwd/workdir mismatch causes false implementation failure
    - confidence: high
    - evidence:
      - `research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee-traj.txt`
  - candidate: cancellation propagation interrupts cleanup under repeated cancel semantics
    - confidence: high
    - evidence:
      - `research/sources/trajectories/terminus-kira/cancel-async-tasks/8d55545f-8ce2-49b7-9fc1-231635fc6a2d-traj.txt`
      - `research/sources/trajectories/BigAI/cancel-async-tasks/98b7cac5-17d9-401f-83aa-d65c59f4cdee-traj.txt`
      - `research/sources/trajectories/deepagents/cancel-async-tasks/ca5a6b83-cd19-46da-8a12-1070b4f476bf-traj.txt`
  - candidate: environment/toolchain mismatch burns run budget
    - confidence: high
    - evidence:
      - `research/sources/trajectories/terminus-kira/extract-moves-from-video/3df89e49-6187-4805-a273-641b4d82c5cd-traj.txt`
      - `research/sources/trajectories/BigAI/headless-terminal/cec71502-c287-4257-9aba-4e33b3668881-traj.txt`
  - candidate: permission-risk signals exist without explicit guardrails in behavior logs
    - confidence: medium
    - weakness: explicit approval policy not observed end-to-end.
    - evidence:
      - `research/sources/trajectories/terminus-kira/headless-terminal/a2ae3f53-cc59-4049-87ca-9e23781c00e4-traj.txt`
      - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/trajectory_support_permission_boundary_cases.md`
- cross_family_comparisons:
  - DeepAgents:
    - compact tool gateway; explicit sandbox-context cues; strong minimal baseline fit.
  - Terminus-KIRA:
    - batch shell gateway with explicit completion-contract pressure; hybrid image tooling where task requires visual extraction.
  - BigAI:
    - behavioral reconstruction only; strongest explicit process-orchestration gateway (`run`/`wait`/`kill`/`interact`) and large shell-tool volume.
  - cross-family conclusion:
    - stable mechanism families are visible for tool gateway and process control; permission-boundary doctrine remains partially unresolved at trajectory level.
- contradiction_notes:
  - BigAI tool volume and discovery regularity are strong in reconstruction summaries, but still not direct source evidence.
  - No required trajectory slice provides sufficient evidence to claim robust approval-policy safety across families.
  - Tool richness does not correlate cleanly with fewer failures; failures still cluster around pathing, cancellation, and environment mismatch.
  - Browser/multimodal capability appears selective and task-conditional, not universally superior.
- confidence_notes:
  - high-confidence:
    - distinct tool gateway families
    - cwd/workdir and cancellation as primary failure boundaries
    - terminal-first minimal baseline remains valid
  - medium-confidence:
    - cross-family permission safety judgments
    - BigAI internal mechanism interpretation beyond behavioral reconstruction
  - low-confidence:
    - claims about hidden approval-policy internals or sandbox hardening not logged in trajectories
- open_questions:
  - Which source-visible controllers enforce approval and permission boundaries for each family, and where do trajectories diverge from that doctrine?
  - Do optional `git-multibranch` slices materially strengthen the cwd/workdir mechanism family, or just repeat already observed path drift behavior?
  - Are there trajectory slices where browser substrate clearly outperforms terminal-first baseline after controlling for environment setup overhead?
  - How much of BigAI wait/kill/orchestration behavior is framework policy versus run-specific operator pattern?
- next_hand_off_target:
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/contradiction_analyst.md`
