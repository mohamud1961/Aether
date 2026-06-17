# Wave 02 Trajectory Follow-Up 01 Packet

Use this packet for a fresh `trajectory/failure analyst` follow-up agent.

Purpose

- Deepen the Wave 02 trajectory lane to the packet-required depth for `execution_control_and_terminal_grounding`.
- Preserve the existing first-pass file as history.
- Write the follow-up to:
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/trajectory_failure_analyst__followup_01.md`

What the agent should receive

- `prompts/deep_synthesis_shared_policy_prompt.md`
- `prompts/deep_synthesis_trajectory_failure_analyst_prompt.md`
- `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_EXECUTION_PROTOCOL.md`
- `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_MULTI_AGENT_WORKFLOW_GUIDE.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/brief.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/brief.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/inputs/lane_followup_plan.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/inputs/support_subagent_rules.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/trajectory_failure_analyst.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/codebase_source_reconstruction_analyst.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/eval_benchmark_analyst.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/contradiction_analyst.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/synthesis/principal_synthesis.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/synthesis/cumulative_synthesis.md`

Required output sections

- `preflight_scope_confirmed`
- `preflight_planned_read_order`
- `preflight_critical_sources_selected`
- `preflight_coverage_risks`
- `preflight_likely_blind_spots`
- `preflight_blockers`
- `coverage_used`
- `coverage_not_yet_used`
- `evidence_classes_touched`
- `priority_sources_not_yet_read`
- `run_inventory_extended`
- `per_run_analysis`
- `shared_task_cross_system_comparison`
- `pass_fail_divergence_analysis`
- `failure_point_comparison`
- `mechanism_hypotheses`
- `source_reconciliation_notes`
- `behavioral_reconstruction_caveats`
- `followup_judgment`

Minimum depth required

- extend per-run analysis where the first pass stayed at family-summary level
- add explicit shared-task cross-system comparison tables
- add explicit pass/fail divergence analysis for the strongest contrasts
- add explicit failure-point comparison for the strongest contrasts
- reconcile promoted trajectory claims against visible source where source exists
- keep BigAI and any no-source family explicitly labeled `behavioral reconstruction`
- inspect priority archive variants only where unread variants could materially change the current judgment

Preferred support-subagent tasks

The main follow-up agent may launch bounded support sub-agents, but only for support artifacts, not final synthesis. Good support tasks:

- `trajectory_support_run_inventory.md`
  - inventory readable runs vs archive-only runs for the selected task families
- `trajectory_support_pass_fail_matrix.md`
  - produce a compact pass/fail matrix across systems and selected tasks
- `trajectory_support_failure_points.md`
  - extract specific failure points, interruptions, cleanup points, and verifier transitions
- `trajectory_support_source_links.md`
  - gather concrete source links for promoted trajectory-backed mechanism claims

Support-subagent rule

- support outputs must be saved as explicit artifacts under the same wave `outputs/` directory
- the main follow-up agent must cite them explicitly
- support outputs are context-gathering support, not final evidence claims by themselves
- the main follow-up agent still owns the actual synthesis

Do not do

- do not overwrite `trajectory_failure_analyst.md`
- do not claim lane completion unless the follow-up genuinely closes the packet-required depth
- do not silently expand beyond the active Wave 02 domain
- do not treat support-subagent notes as final mechanism claims without principal or main-analyst synthesis
