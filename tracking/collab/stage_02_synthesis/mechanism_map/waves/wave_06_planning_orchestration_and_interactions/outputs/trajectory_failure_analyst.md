TRAJECTORY_FAILURE_OUTPUT
- artifact: mechanism_map / wave_06_planning_orchestration_and_interactions
- role: trajectory/failure analyst
- preflight_scope_confirmed:
  - Wave 06 is treated as a vertical mechanism wave on planning, replanning, delegation, role separation, and interaction contracts.
  - This lane is trajectory-first and keeps implementation assertions separate from source-backed claims.
  - The optional eval lane was kept inactive because required slices did not make benchmark-contract internals load-bearing.
  - BigAI is kept explicitly as `behavioral reconstruction`.
- preflight_planned_read_order:
  - 1. Wave control surfaces and carry-forward constraints.
  - 2. Required BigAI run slices: `prove-plus-comm`, `cobol-modernization`, `openssl-selfsigned-cert`.
  - 3. Required BigAI trajectory tree for direct path checks.
  - 4. Optional long-tail pressure: `protein-assembly`, `large-scale-text-editing` (BigAI plus one DeepAgents and one Terminus-KIRA run each).
  - 5. Build support artifacts for planning timeline and delegation interaction map.
- preflight_critical_sources_selected:
  - `research/analysis/bigai_trace_layer/output/runs/prove-plus-comm/*.json`
  - `research/analysis/bigai_trace_layer/output/runs/cobol-modernization/*.json`
  - `research/analysis/bigai_trace_layer/output/runs/openssl-selfsigned-cert/*.json`
  - `research/sources/trajectories/BigAI/prove-plus-comm/*`
  - `research/sources/trajectories/BigAI/cobol-modernization/*`
  - `research/sources/trajectories/BigAI/openssl-selfsigned-cert/*`
  - optional pressure:
    - `research/analysis/bigai_trace_layer/output/runs/protein-assembly/*.json`
    - `research/analysis/bigai_trace_layer/output/runs/large-scale-text-editing/*.json`
    - `research/sources/trajectories/deepagents/protein-assembly/88b6b4f5-9493-4f00-9e4c-7550283e3d6d-traj.txt`
    - `research/sources/trajectories/deepagents/large-scale-text-editing/cb0057f1-c601-4072-9a38-8fa425da2b36-traj.txt`
    - `research/sources/trajectories/terminus-kira/protein-assembly/e8d52c49-8861-414f-9675-966c4e3c6398-traj.txt`
    - `research/sources/trajectories/terminus-kira/large-scale-text-editing/8d411246-71ae-4a44-8f8b-af985026bd5a-traj.txt`
- preflight_coverage_risks:
  - One required run (`cd0d69dd...`) lacks normalized `*-traj.txt`; this lane relied on normalized run JSON.
  - BigAI remains behavior-only with hidden scheduler/control internals.
  - Optional long-tail was sampled, not exhausted.
  - No direct literature/issues/postmortem read occurred in this lane pass.
- preflight_likely_blind_spots:
  - hidden branch scheduling and branch-pruning policy
  - verifier rubric internals beyond visible finish statuses
  - cross-family generalization outside sampled tasks
  - formal/informal contradiction pressure not yet integrated in-lane
- preflight_blockers:
  - none
- coverage_used:
  - control surfaces:
    - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_06_planning_orchestration_and_interactions/brief.md`
    - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_06_planning_orchestration_and_interactions/inputs/support_subagent_rules.md`
    - `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_EXECUTION_PROTOCOL.md`
    - `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_MULTI_AGENT_WORKFLOW_GUIDE.md`
    - `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_LANE_CLOSURE_CRITERIA.md`
    - `tracking/collab/stage_02_synthesis/mechanism_map/synthesis/cumulative_synthesis.md`
    - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/synthesis/principal_synthesis.md`
    - `tracking/collab/stage_02_synthesis/coverage_register/current_status.md`
    - `research/intake/normalized/manifests/corpus__captured_for_synthetic_prep.json`
  - required trajectory slices:
    - `research/analysis/bigai_trace_layer/output/runs/prove-plus-comm/*.json`
    - `research/analysis/bigai_trace_layer/output/runs/cobol-modernization/*.json`
    - `research/analysis/bigai_trace_layer/output/runs/openssl-selfsigned-cert/*.json`
    - `research/sources/trajectories/BigAI/prove-plus-comm/9d65fa58-b782-4b19-8cd2-f68bbc5e4604-traj.txt`
    - `research/sources/trajectories/BigAI/prove-plus-comm/a3dd0499-b4fd-47bc-8fde-189e4d7093a9-traj.txt`
    - `research/sources/trajectories/BigAI/prove-plus-comm/e2156559-1778-4aeb-93d5-3d627dc5896a-traj.txt`
    - `research/sources/trajectories/BigAI/cobol-modernization/1478ab91-572c-445e-ba77-807d2cd03d4c-traj.txt`
    - `research/sources/trajectories/BigAI/cobol-modernization/23f367d2-84b1-4834-9cb9-43823ca4a2e0-traj.txt`
    - `research/sources/trajectories/BigAI/cobol-modernization/5bcfcd9d-0551-4227-9e9a-26d104728d76-traj.txt`
    - `research/sources/trajectories/BigAI/cobol-modernization/b131ce4a-2242-4467-ad17-acbcd3b2abd6-traj.txt`
    - `research/sources/trajectories/BigAI/cobol-modernization/d7f5f2b6-aede-4480-9cbe-ce5a89ab0342-traj.txt`
    - `research/sources/trajectories/BigAI/openssl-selfsigned-cert/ede4695e-37a5-4e1b-b1ac-187903ef0e29-traj.txt`
  - optional long-tail pressure:
    - `research/analysis/bigai_trace_layer/output/runs/protein-assembly/*.json`
    - `research/analysis/bigai_trace_layer/output/runs/large-scale-text-editing/*.json`
    - `research/sources/trajectories/deepagents/protein-assembly/88b6b4f5-9493-4f00-9e4c-7550283e3d6d-traj.txt`
    - `research/sources/trajectories/deepagents/large-scale-text-editing/cb0057f1-c601-4072-9a38-8fa425da2b36-traj.txt`
    - `research/sources/trajectories/terminus-kira/protein-assembly/e8d52c49-8861-414f-9675-966c4e3c6398-traj.txt`
    - `research/sources/trajectories/terminus-kira/large-scale-text-editing/8d411246-71ae-4a44-8f8b-af985026bd5a-traj.txt`
  - support artifacts produced in-lane:
    - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_06_planning_orchestration_and_interactions/outputs/trajectory_support_planning_timeline.md`
    - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_06_planning_orchestration_and_interactions/outputs/trajectory_support_delegation_interaction_map.md`
- coverage_not_yet_used:
  - `research/sources/trajectories/*/protein-assembly/*.tar.gz` and other unexpanded bundle internals
  - `research/sources/trajectories/*/large-scale-text-editing/*.tar.gz` beyond sampled runs
  - mirrored codebases for mechanism reconciliation:
    - `research/sources/codebases/deepagents/**`
    - `research/sources/codebases/KIRA/**`
    - `research/sources/codebases/a-evolve/**`
    - `research/sources/codebases/quarantine/claw-code/**`
  - formal and informal classes:
    - `research/sources/papers/**`
    - `research/sources/docs/**`
    - `research/sources/informal/**`
    - `research/sources/issues/**`
    - `research/sources/postmortems/**`
- evidence_classes_touched:
  - trajectories
  - relevant local analysis (`bigai_trace_layer` run summaries)
  - wave control artifacts
- priority_sources_not_yet_read:
  - `research/sources/trajectories/BigAI/prove-plus-comm/cd0d69dd-3cac-47e0-9777-51327561ff6d.tar.gz` (required run, no normalized text path)
  - `research/sources/trajectories/*/protein-assembly/*.tar.gz` not sampled
  - `research/sources/trajectories/*/large-scale-text-editing/*.tar.gz` not sampled
  - `research/analysis/bigai_trace_layer/output/final_harness_reconstruction.md` (not re-read in this lane pass)
  - formal and informal wave-06 dossier source pools (papers/docs/issues/postmortems)
- support_artifacts_used:
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_06_planning_orchestration_and_interactions/outputs/trajectory_support_planning_timeline.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_06_planning_orchestration_and_interactions/outputs/trajectory_support_delegation_interaction_map.md`
- support_artifacts_requested_or_deferred:
  - produced:
    - `trajectory_support_planning_timeline.md`
    - `trajectory_support_delegation_interaction_map.md`
  - deferred:
    - no additional support artifacts requested in this lane pass
- coverage_register_updates_needed:
  - Update Wave 06 from `packet prepared` to `trajectory lane complete (first pass)` once principal validates cross-lane consistency.
  - Keep carry-forward note that this lane is trajectory-heavy and BigAI remains behavioral reconstruction.
- required_dossier_updates:
  - updated in this pass:
    - `tracking/collab/stage_02_synthesis/source_system_dossiers/deepagents.md`
    - `tracking/collab/stage_02_synthesis/source_system_dossiers/KIRA.md`
    - `tracking/collab/stage_02_synthesis/source_system_dossiers/a-evolve.md`
    - `tracking/collab/stage_02_synthesis/source_system_dossiers/BigAI_behavioral.md`
    - `tracking/collab/stage_02_synthesis/source_system_dossiers/claw-code.md`
    - `tracking/collab/stage_02_synthesis/literature_dossiers/themes/planning_and_replanning.md`
    - `tracking/collab/stage_02_synthesis/literature_dossiers/themes/delegation_and_role_separation.md`
    - `tracking/collab/stage_02_synthesis/informal_cluster_dossiers/planning_orchestration_and_interactions.md`
- direct_behavior_observations:
  - claim_id: W06-T1
    observation: In all 10 required runs, planner-first sequencing is stable (`save_plan` at step 3, first executor packet at step 4).
    inference: Planning is an explicit front-loaded orchestration contract, not incidental narration.
    confidence: high
    evidence_paths:
      - `research/analysis/bigai_trace_layer/output/runs/prove-plus-comm/*.json`
      - `research/analysis/bigai_trace_layer/output/runs/cobol-modernization/*.json`
      - `research/analysis/bigai_trace_layer/output/runs/openssl-selfsigned-cert/*.json`
      - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_06_planning_orchestration_and_interactions/outputs/trajectory_support_planning_timeline.md`

  - claim_id: W06-T2
    observation: Verifier-gated closure is common but not universal (`9/10` required runs include verifier packet + `finish_verification`; one required run passes without verifier).
    inference: Interaction contracts include at least two regimes: verifier-mediated and planner-executor-only completion.
    confidence: high
    evidence_paths:
      - `research/analysis/bigai_trace_layer/output/runs/cobol-modernization/23f367d2-84b1-4834-9cb9-43823ca4a2e0.json`
      - `research/analysis/bigai_trace_layer/output/runs/prove-plus-comm/*.json`
      - `research/analysis/bigai_trace_layer/output/runs/openssl-selfsigned-cert/*.json`
      - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_06_planning_orchestration_and_interactions/outputs/trajectory_support_delegation_interaction_map.md`

  - claim_id: W06-T3
    observation: One required run (`a3dd...`) shows explicit verifier failure followed by planner plan-update, reassignment to `executor-1`, and second verifier pass.
    inference: Replanning after verifier rejection is behaviorally real and role-bounded (planner updates plan; executors implement; verifier re-adjudicates).
    confidence: high
    evidence_paths:
      - `research/analysis/bigai_trace_layer/output/runs/prove-plus-comm/a3dd0499-b4fd-47bc-8fde-189e4d7093a9.json`
      - `research/sources/trajectories/BigAI/prove-plus-comm/a3dd0499-b4fd-47bc-8fde-189e4d7093a9-traj.txt`

  - claim_id: W06-T4
    observation: Executor handoff packets always include `task+plan+basic_env_info`, while `task_history` appears only in richer branching runs (`2/10` required runs; all sampled protein-assembly runs).
    inference: Handoff payload complexity is conditional and likely used to stabilize multi-executor coordination.
    confidence: medium
    weakness: packet traces are observational; hidden prompt compaction policy is unknown.
    evidence_paths:
      - `research/analysis/bigai_trace_layer/output/runs/prove-plus-comm/*.json`
      - `research/analysis/bigai_trace_layer/output/runs/cobol-modernization/*.json`
      - `research/analysis/bigai_trace_layer/output/runs/protein-assembly/*.json`

  - claim_id: W06-T5
    observation: Optional long-tail pressure shows delegation fanout does not by itself guarantee outcome (`large-scale-text-editing` includes one 3-executor fail and one 2-executor pass, both without verifier).
    inference: Coordination quality depends on gate structure and recovery flow, not just number of delegated branches.
    confidence: medium
    weakness: sample size is small and task-specific.
    evidence_paths:
      - `research/analysis/bigai_trace_layer/output/runs/large-scale-text-editing/*.json`

  - claim_id: W06-T6
    observation: In required verifier-present runs, planner often marks `task_finished=true` before verifier adjudication.
    inference: Completion signaling and acceptance are split layers; planner completion claim is provisional pending verifier gate.
    confidence: high
    evidence_paths:
      - `research/analysis/bigai_trace_layer/output/runs/prove-plus-comm/*.json`
      - `research/analysis/bigai_trace_layer/output/runs/cobol-modernization/*.json`
      - `research/analysis/bigai_trace_layer/output/runs/openssl-selfsigned-cert/*.json`

- workflow_patterns:
  - Pattern A: plan-first, execute-second, verify-last pipeline with explicit handoff packets.
  - Pattern B: lightweight replanning for most required runs; deeper replanning where verifier rejection occurs.
  - Pattern C: delegation depth scales with harder long-tail tasks (`protein-assembly`) rather than being uniformly high.
  - Pattern D: planner completion signal is not final acceptance; verifier can still fail the run.
- verification_and_recovery_patterns:
  - verifier-mediated recovery is explicit in `a3dd...` and reinforced in optional `protein-assembly` runs with `FAILED -> PASSED` sequences.
  - nonzero tool failures are common inside successful runs, with recovery via environment discovery, rerun, and plan update.
  - no-verifier branches can still pass, but they also include visible fail cases in optional pressure.
- failure_candidates:
  - candidate: verifier bypass or absence creates higher coordination-risk regime.
    - evidence: `23f367...` (required no-verifier pass), `9d272744...` (optional no-verifier fail)
    - confidence: medium
  - candidate: hidden coupling between planner done-signals and verifier gate can create false confidence if verifier is skipped.
    - evidence: planner `task_finished=true` before verifier in 9 required runs
    - confidence: medium
  - candidate: delegation fanout without strong interaction contract can increase drift and step inflation.
    - evidence: `large-scale-text-editing/9d272744...` (195 steps, fail, multi-executor)
    - confidence: medium
- cross_family_comparisons:
  - BigAI required slices show explicit planner/executor/verifier role separation and gated recovery loops (behavioral reconstruction).
  - Sampled DeepAgents and Terminus-KIRA optional runs (`protein-assembly`, `large-scale-text-editing`) are primarily single-agent execution traces with no explicit planner-verifier role split visible in the same format.
  - This suggests a real family split between role-separated orchestration and terminal-first single-agent loops, but the cross-family sample here is thin.
- contradiction_notes:
  - Required packet asks for delegation/role separation depth, but required runs include a no-verifier pass variant; role separation is strong but not universal.
  - Multi-executor behavior can coexist with both pass and fail outcomes; “more orchestration” is not automatically better.
  - BigAI evidence remains behavior-only and cannot be promoted to source-backed scheduler claims.
- confidence_notes:
  - high: planner-first ordering, handoff packet structure, and verifier gate presence patterns in required runs.
  - medium: causal claims about why no-verifier runs pass or fail; hidden-control explanations; broad cross-family generalization.
  - low: any claim about internal scheduler branching policy beyond visible packet order.
- open_questions:
  - What precise controller rule allows no-verifier completion in some runs while verifier is dominant elsewhere?
  - When does planner decide to include `task_history` in executor packets, and what failure classes does this prevent?
  - Is verifier optionality task-conditioned, model-conditioned, or policy-conditioned?
  - Which observable signals best detect coordination drift before failure in multi-executor runs?
- next_hand_off_target:
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_06_planning_orchestration_and_interactions/outputs/contradiction_analyst.md`
