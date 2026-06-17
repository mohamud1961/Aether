INFORMAL_ISSUES_POSTMORTEMS_OUTPUT
- artifact: failure_taxonomy / wave_01_execution_control_and_terminal_failures
- role: informal/issues/postmortems analyst

- preflight_scope_confirmed:
  - wave is a vertical failure-domain pass for execution-control and terminal failures, not a generic mechanism recap
  - lane objective is contradiction-pressure attribution across timeout/stall, false success, cancellation drift, repo-state/control corruption, and blame assignment boundaries
  - trajectory/source precedence retained; informal evidence is used to pressure and challenge attribution, not to override direct behavior/source evidence
  - optional eval/benchmark fifth lane remains inactive in this lane pass because selected evidence centers runtime control failures; benchmark-contract logic is only secondary pressure

- preflight_planned_read_order:
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/brief.md`
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/inputs/support_subagent_rules.md`
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/brief.md`
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/decision.md`
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/synthesis/cumulative_synthesis.md`
  - `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_EXECUTION_PROTOCOL.md`
  - `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_MULTI_AGENT_WORKFLOW_GUIDE.md`
  - `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_LANE_CLOSURE_CRITERIA.md`
  - `tracking/collab/stage_02_synthesis/coverage_register/current_status.md`
  - required mechanism carry-forward syntheses and `tracking/collab/stage_02_synthesis/informal_cluster_dossiers/README.md`
  - targeted read of selected files under `research/sources/informal/`, `research/sources/issues/`, `research/sources/postmortems/`

- preflight_critical_sources_selected:
  - `research/sources/informal/anthropic_long_running_harness.md`
  - `research/sources/informal/cursor_self_driving_codebases.md`
  - `research/sources/informal/cursor_long_running_agents.md`
  - `research/sources/informal/cursor_agent_sandboxing.md`
  - `research/sources/informal/openai_monitor_misalignment.md`
  - `research/sources/postmortems/src_pmt_cddfa4a4dcc6/artifact.txt`
  - `research/sources/postmortems/src_pmt_95c4bda555e0/artifact.txt`
  - `research/sources/issues/src_iss_f736e544a5b9/artifact.txt`
  - `research/sources/issues/src_iss_da41417f5655/artifact.txt`
  - `research/sources/issues/src_iss_677a876a6ea9/artifact.txt`
  - `research/sources/issues/src_iss_6ba217fff208/artifact.txt`
  - `research/sources/issues/src_iss_4c8fe1b50b87/artifact.txt`
  - `research/sources/issues/src_iss_7ea08b4fb93c/artifact.txt`
  - `research/sources/issues/src_iss_5d861db09829/artifact.txt`
  - `research/sources/issues/src_iss_f07284ab370e/artifact.txt`
  - `research/sources/issues/src_iss_d3818cf54a20/artifact.txt`
  - `research/sources/issues/src_iss_836cb2fc3bdb/artifact.txt`
  - `research/sources/issues/src_iss_c07dfa2bcbb3/artifact.txt`
  - `research/sources/issues/src_iss_613424e145e5/artifact.txt`
  - `research/sources/issues/src_iss_222a58240294/artifact.txt`
  - `research/sources/issues/src_iss_edac72dd9b31/artifact.txt`

- preflight_coverage_risks:
  - issue captures are mostly flattened one-line artifacts, so thread-level nuance and maintainer resolution quality are partially hidden
  - evidence concentration in a few ecosystems may over-weight their failure shapes
  - some claims in issue reports are user assertions without independently validated reproduction inside this lane

- preflight_likely_blind_spots:
  - limited private/internal postmortem evidence for non-public systems
  - weak longitudinal evidence for whether fixes persisted after issue closure
  - missing direct trajectory reconciliation for `headless_terminal` (case-study file still absent)

- preflight_blockers:
  - none

- coverage_used:
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/brief.md`
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/inputs/support_subagent_rules.md`
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/brief.md`
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/decision.md`
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/synthesis/cumulative_synthesis.md`
  - `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_EXECUTION_PROTOCOL.md`
  - `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_MULTI_AGENT_WORKFLOW_GUIDE.md`
  - `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_LANE_CLOSURE_CRITERIA.md`
  - `tracking/collab/stage_02_synthesis/coverage_register/current_status.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/synthesis/cumulative_synthesis.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/synthesis/principal_synthesis.md` (read; currently empty)
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/synthesis/principal_synthesis.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/synthesis/principal_synthesis.md`
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_06_planning_orchestration_and_interactions/synthesis/principal_synthesis.md`
  - `tracking/collab/stage_02_synthesis/informal_cluster_dossiers/README.md`
  - `research/sources/informal/anthropic_long_running_harness.md`
  - `research/sources/informal/cursor_self_driving_codebases.md`
  - `research/sources/informal/cursor_long_running_agents.md`
  - `research/sources/informal/cursor_agent_sandboxing.md`
  - `research/sources/informal/openai_monitor_misalignment.md`
  - `research/sources/postmortems/src_pmt_cddfa4a4dcc6/artifact.txt`
  - `research/sources/postmortems/src_pmt_95c4bda555e0/artifact.txt`
  - `research/sources/postmortems/src_pmt_ca79e818d699/artifact.txt`
  - `research/sources/postmortems/src_pmt_afc13590bd50/artifact.txt`
  - `research/sources/issues/src_iss_f736e544a5b9/artifact.txt`
  - `research/sources/issues/src_iss_da41417f5655/artifact.txt`
  - `research/sources/issues/src_iss_677a876a6ea9/artifact.txt`
  - `research/sources/issues/src_iss_6ba217fff208/artifact.txt`
  - `research/sources/issues/src_iss_4c8fe1b50b87/artifact.txt`
  - `research/sources/issues/src_iss_7ea08b4fb93c/artifact.txt`
  - `research/sources/issues/src_iss_5d861db09829/artifact.txt`
  - `research/sources/issues/src_iss_f07284ab370e/artifact.txt`
  - `research/sources/issues/src_iss_d3818cf54a20/artifact.txt`
  - `research/sources/issues/src_iss_836cb2fc3bdb/artifact.txt`
  - `research/sources/issues/src_iss_c07dfa2bcbb3/artifact.txt`
  - `research/sources/issues/src_iss_613424e145e5/artifact.txt`
  - `research/sources/issues/src_iss_222a58240294/artifact.txt`
  - `research/sources/issues/src_iss_edac72dd9b31/artifact.txt`
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/outputs/informal_support_timeout_false_success_cluster.md`

- coverage_not_yet_used:
  - `research/sources/issues/src_iss_2f7fef40c4cf/artifact.txt`
  - `research/sources/issues/src_iss_bfc82053a70d/artifact.txt`
  - `research/sources/issues/src_iss_594e5f13600f/artifact.txt`
  - `research/sources/issues/src_iss_c684343ec3ff/artifact.txt`
  - `research/sources/issues/src_iss_84bccb83da69/artifact.txt`
  - `research/sources/issues/src_iss_51e11ab8bc0e/artifact.txt`
  - `research/sources/issues/src_iss_72d11ef0f608/artifact.txt`
  - most social short-form captures under `research/sources/informal/x_*.md`

- evidence_classes_touched:
  - informal sources
  - issues
  - postmortems
  - carry-forward synthesis/control surfaces
  - support artifact

- priority_sources_not_yet_read:
  - `research/sources/issues/src_iss_594e5f13600f/artifact.txt`
  - `research/sources/issues/src_iss_c684343ec3ff/artifact.txt`
  - `research/sources/issues/src_iss_84bccb83da69/artifact.txt`
  - `research/sources/issues/src_iss_51e11ab8bc0e/artifact.txt`
  - `research/sources/issues/src_iss_72d11ef0f608/artifact.txt`

- support_artifacts_used:
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/outputs/informal_support_timeout_false_success_cluster.md`

- support_artifacts_requested_or_deferred:
  - no additional support sub-agent requested in this pass
  - deferred: deeper benchmark-blindness subcluster from unread issue set

- coverage_register_updates_needed:
  - once contradiction review runs, mark Wave 01 informal lane as first-pass complete
  - add carry-forward warning that timeout/stall and false-success failures remain mixed-cause and should not be flattened into model-only attribution
  - add explicit note that `headless_terminal` case-study path remains missing and limits execution-control saturation depth

- required_dossier_updates:
  - needed by packet but not edited in this scoped run:
    - `tracking/collab/stage_02_synthesis/informal_cluster_dossiers/execution_control_and_terminal_failures.md`
    - `tracking/collab/stage_02_synthesis/literature_dossiers/themes/tool_use_and_gateways.md`
    - `tracking/collab/stage_02_synthesis/literature_dossiers/themes/environment_and_permissions.md`
    - `tracking/collab/stage_02_synthesis/literature_dossiers/themes/verification_and_replay.md`
    - `tracking/collab/stage_02_synthesis/source_system_dossiers/deepagents.md`
    - `tracking/collab/stage_02_synthesis/source_system_dossiers/KIRA.md`
    - `tracking/collab/stage_02_synthesis/source_system_dossiers/BigAI_behavioral.md`
    - `tracking/collab/stage_02_synthesis/source_system_dossiers/a-evolve.md`

- high_signal_operating_claims:
  - claim_id: FT_W01_INF_C1_timeout_loops_are_harness_lifecycle_failures
    - observation: compaction hangs, browser crash non-recovery, startup bootstrap hangs, and stuck RUNNING/THINKING states recur across issue evidence
    - inference: execution-control failures are heavily shaped by harness lifecycle control (watchdogs, bounded retries, interrupt propagation), not only by model planning quality
    - confidence: high
    - weakener: cross-family prevalence is inferred from a subset of ecosystems
    - evidence_paths:
      - `research/sources/issues/src_iss_f736e544a5b9/artifact.txt`
      - `research/sources/issues/src_iss_da41417f5655/artifact.txt`
      - `research/sources/issues/src_iss_677a876a6ea9/artifact.txt`
      - `research/sources/issues/src_iss_6ba217fff208/artifact.txt`
      - `research/sources/issues/src_iss_4c8fe1b50b87/artifact.txt`
      - `research/sources/informal/anthropic_long_running_harness.md`

  - claim_id: FT_W01_INF_C2_false_success_pressure_is_contract_gap_pressure
    - observation: host-side completion/status signals can report success while target-state verification is absent or downstream action events are missing
    - inference: false success is primarily a completion-contract failure (what gets checked, where, and when), then amplified by benchmark blind spots
    - confidence: medium
    - weakener: strongest hardware-damage report is user-asserted and not independently reproduced in this lane
    - evidence_paths:
      - `research/sources/issues/src_iss_5d861db09829/artifact.txt`
      - `research/sources/issues/src_iss_6ba217fff208/artifact.txt`
      - `research/sources/informal/openai_monitor_misalignment.md`
      - `research/sources/postmortems/src_pmt_cddfa4a4dcc6/artifact.txt`

  - claim_id: FT_W01_INF_C3_interrupt_resume_drift_is_persistent
    - observation: interruption failures (non-responsive ctrl-c, stuck queues) co-occur with stale/missing resume state and index drift
    - inference: cancellation/interrupt reliability depends on shared state consistency and resumability pipeline health; these should be one attributed family, not separate bugs
    - confidence: high
    - weakener: causal ordering between interrupt bug and index drift is inferred
    - evidence_paths:
      - `research/sources/issues/src_iss_f736e544a5b9/artifact.txt`
      - `research/sources/issues/src_iss_4c8fe1b50b87/artifact.txt`
      - `research/sources/issues/src_iss_613424e145e5/artifact.txt`
      - `research/sources/issues/src_iss_222a58240294/artifact.txt`
      - `research/sources/issues/src_iss_edac72dd9b31/artifact.txt`

  - claim_id: FT_W01_INF_C4_repo_state_corruption_is_control_integrity_not_model_intent
    - observation: repeated session-state file corruption and path-target contamination loops show control-plane/write-target integrity loss
    - inference: repo-state/control corruption and cleanup gaps belong to harness concurrency/path-control surfaces; model-only blame is weak without stronger evidence
    - confidence: high
    - weakener: evidence is mostly issue-reported rather than trajectory-replayed
    - evidence_paths:
      - `research/sources/issues/src_iss_836cb2fc3bdb/artifact.txt`
      - `research/sources/issues/src_iss_c07dfa2bcbb3/artifact.txt`
      - `research/sources/issues/src_iss_613424e145e5/artifact.txt`

  - claim_id: FT_W01_INF_C5_model_vs_harness_blame_is_systematically_mixed
    - observation: unstructured tool errors and strict parser failure paths provoke retry loops or hard stops, while postmortems emphasize harness/guardrail design as primary reliability lever
    - inference: attribution should default to mixed-cause (model behavior + harness contract + runtime/environment), unless stronger direct evidence isolates one cause
    - confidence: high
    - weakener: some supporting evidence is design doctrine rather than direct incident data
    - evidence_paths:
      - `research/sources/issues/src_iss_f07284ab370e/artifact.txt`
      - `research/sources/issues/src_iss_d3818cf54a20/artifact.txt`
      - `research/sources/informal/cursor_self_driving_codebases.md`
      - `research/sources/postmortems/src_pmt_cddfa4a4dcc6/artifact.txt`
      - `research/sources/postmortems/src_pmt_95c4bda555e0/artifact.txt`

- issue_and_postmortem_findings:
  - timeout/stall loops:
    - compaction or substrate failures can trap runs in non-progress states for long periods
    - evidence: `research/sources/issues/src_iss_f736e544a5b9/artifact.txt`, `research/sources/issues/src_iss_da41417f5655/artifact.txt`, `research/sources/issues/src_iss_6ba217fff208/artifact.txt`, `research/sources/issues/src_iss_4c8fe1b50b87/artifact.txt`, `research/sources/issues/src_iss_677a876a6ea9/artifact.txt`
  - false success and benchmark blindness:
    - completion/status surfaces can pass while target-side success is not validated
    - evidence: `research/sources/issues/src_iss_5d861db09829/artifact.txt`, `research/sources/issues/src_iss_6ba217fff208/artifact.txt`, `research/sources/postmortems/src_pmt_cddfa4a4dcc6/artifact.txt`
  - cancellation/interrupt drift:
    - interruption control and resume/index integrity fail together, producing repetitive restart overhead
    - evidence: `research/sources/issues/src_iss_f736e544a5b9/artifact.txt`, `research/sources/issues/src_iss_4c8fe1b50b87/artifact.txt`, `research/sources/issues/src_iss_613424e145e5/artifact.txt`, `research/sources/issues/src_iss_222a58240294/artifact.txt`, `research/sources/issues/src_iss_edac72dd9b31/artifact.txt`
  - repo-state/control corruption and cleanup gaps:
    - control-plane state corruption and wrong-file targeting loops are visible operational pressure
    - evidence: `research/sources/issues/src_iss_836cb2fc3bdb/artifact.txt`, `research/sources/issues/src_iss_c07dfa2bcbb3/artifact.txt`
  - model-vs-harness blame confusion:
    - reports often label model fault where tool/runtime contracts are underspecified or brittle
    - evidence: `research/sources/issues/src_iss_f07284ab370e/artifact.txt`, `research/sources/issues/src_iss_d3818cf54a20/artifact.txt`, `research/sources/informal/cursor_self_driving_codebases.md`, `research/sources/postmortems/src_pmt_cddfa4a4dcc6/artifact.txt`

- contradiction_or_support_notes:
  - supports mechanism_map carry-forward warning that organizer and rhetoric should not outrank direct path evidence
  - supports Wave 03/05 caution that verification/completion and execution-control surfaces are distinct and coupled
  - keeps BigAI at behavioral-reconstruction caution level; informal pressure does not upgrade source certainty
  - contradicts any monocausal framing that execution-control failures are primarily model weakness

- unvalidated_leads:
  - whether benchmark-contract-specific blindness dominates false-success rate compared with lifecycle-control defects
  - whether permission/hook path failures materially worsen timeout loops in this wave domain
  - whether structured tool error metadata reduces retry-loop frequency in long-running terminal tasks

- confidence_notes:
  - high: recurrence of timeout/stall, interrupt drift, and control-corruption pressure clusters
  - medium: false-success severity distribution and benchmark contribution ratios
  - low: ecosystem-wide fix durability for closed/stale issue items

- open_questions:
  - what minimal execution-control contract prevents stall loops: watchdog, bounded retries, and explicit interrupt propagation checks?
  - where should completion truth live for terminal tasks: host-side command completion, verifier layer, or target-state postcondition proof?
  - which cleanup guarantees are mandatory before marking task completion in stateful/physical-target workflows?
  - what evidence threshold is sufficient to assign primary blame to model vs harness vs environment?

- next_hand_off_target:
  - `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/outputs/contradiction_analyst.md`
