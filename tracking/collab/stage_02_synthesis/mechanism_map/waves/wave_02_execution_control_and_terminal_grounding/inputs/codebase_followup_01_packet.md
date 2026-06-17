# Wave 02 Codebase Follow-Up 01 Packet

Use this packet for a fresh `codebase/source-reconstruction analyst` follow-up agent.

Purpose

- Deepen the Wave 02 source lane where the first pass left important execution-control pressure unresolved.
- Preserve the existing first-pass file as history.
- Write the follow-up to:
  - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/codebase_source_reconstruction_analyst__followup_01.md`

What the agent should receive

- `prompts/deep_synthesis_shared_policy_prompt.md`
- `prompts/deep_synthesis_codebase_source_reconstruction_analyst_prompt.md`
- `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_EXECUTION_PROTOCOL.md`
- `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_MULTI_AGENT_WORKFLOW_GUIDE.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/brief.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/brief.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/inputs/lane_followup_plan.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/inputs/support_subagent_rules.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/codebase_source_reconstruction_analyst.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/trajectory_failure_analyst.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/contradiction_analyst.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/synthesis/principal_synthesis.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/synthesis/cumulative_synthesis.md`
- `research/sources/codebases/autoagent/agent.py`
- `research/sources/codebases/autoagent/program.md`

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
- `source_deepening_targets`
- `subfamily_closure_updates`
- `behavior_to_source_reconciliation`
- `autoagent_impact_note`
- `claw_code_and_src_cod_pressure`
- `local_harness_gap_notes`
- `followup_judgment`

Minimum depth required

- close the strongest remaining low-level questions around:
  - KIRA Harbor `TmuxSession` / inherited session internals if visible in-corpus
  - DeepAgents execution-control boundaries and Harbor execution semantics where materially visible
  - `claw-code` runtime control relevant to execution/terminal grounding
  - top-tier `src_cod_*` captures relevant to execution control
- strengthen mapping from trajectory-backed claims to visible source-backed mechanism families
- explicitly state whether `autoagent` changes the current family split or merely reinforces the existing discrete command-executor family
- keep no-source claims separate from source-backed implementation claims

Preferred support-subagent tasks

The main follow-up agent may launch bounded support sub-agents, but only for support artifacts, not final synthesis. Good support tasks:

- `codebase_support_claw_code_map.md`
  - identify execution-control-relevant files and interfaces in `claw-code`
- `codebase_support_src_cod_triage.md`
  - triage top-tier `src_cod_*` captures for execution-control relevance
- `codebase_support_harbor_links.md`
  - gather KIRA / Harbor / DeepAgents inherited execution-control linkage points
- `codebase_support_local_harness_compare.md`
  - compare promoted execution-control families against local `blocks/`, `runner/`, and `evals/` gaps

Support-subagent rule

- support outputs must be saved as explicit artifacts under the same wave `outputs/` directory
- the main follow-up agent must cite them explicitly
- support outputs are context-gathering support, not final evidence claims by themselves
- the main follow-up agent still owns the actual synthesis

Do not do

- do not overwrite `codebase_source_reconstruction_analyst.md`
- do not present `BigAI` as source-backed implementation
- do not inflate `autoagent` into a new execution-control family unless the read source genuinely forces that conclusion
- do not force `mempalace` into this Wave 02 domain; it is primarily later-wave memory/state material
