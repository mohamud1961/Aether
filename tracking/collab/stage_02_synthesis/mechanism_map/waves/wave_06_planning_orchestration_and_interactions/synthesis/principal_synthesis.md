# Mechanism Map Wave 06 Principal Synthesis

Status date: 2026-04-10

Wave

- `wave_06_planning_orchestration_and_interactions`

Overall judgment

- Wave 06 materially strengthens `mechanism_map`.
- The strongest supported Wave 06 conclusion is that `planning`, `replanning`, `delegation`, `role contracts`, and `interaction governance` should not be flattened into generic “agentic workflow” language.
- The wave supports real mechanism separation inside this domain.
- All three contradiction passes converge on `pass_with_warnings`, not on a structural block to synthesis (`tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_06_planning_orchestration_and_interactions/outputs/contradiction_analyst.md`, `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_06_planning_orchestration_and_interactions/outputs/contradiction_analyst__claude.md`, `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_06_planning_orchestration_and_interactions/outputs/contradiction_analyst__gemini.md`).
- BigAI remains `behavioral reconstruction`.
- The wave does not support a strong positive claim that role-separated orchestration is already universally superior across families.
- The wave does not support a strong claim that delegation quality is already robust.
- The wave is now principal-complete and checklist-ready.
- Wave 06 is not yet accepted at the wave level, is not artifact completion, and no family is `decision_ready`.

What this wave resolved

- `planner-first orchestration with conditional verifier gate` is a real visible interaction family in the required BigAI Wave 06 slices.
  - Required BigAI runs consistently show early `save_plan`, executor handoff, and dominant verifier-gated closure, with one explicit no-verifier pass variant and one explicit verifier-failure-to-replan recovery path (`research/analysis/bigai_trace_layer/output/runs/prove-plus-comm/*.json`, `research/analysis/bigai_trace_layer/output/runs/cobol-modernization/*.json`, `research/analysis/bigai_trace_layer/output/runs/openssl-selfsigned-cert/*.json`, `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_06_planning_orchestration_and_interactions/outputs/trajectory_support_planning_timeline.md`).
  - The strongest honest formulation is narrower than “universal orchestration family”:
    - planner-first plus conditional verifier-gated interaction contracts are real in the required BigAI slices,
    - but this remains behavior-rich and source-opaque.
- `delegation and role-boundary contracts` are source-backed in deepagents, KIRA, and a-evolve.
  - DeepAgents exposes explicit subagent middleware and async delegation surfaces (`research/sources/codebases/deepagents/libs/deepagents/deepagents/middleware/subagents.py`, `research/sources/codebases/deepagents/libs/deepagents/deepagents/middleware/async_subagents.py`).
  - KIRA shows explicit planning schema, queue/scheduler runtime, and multi-role orchestration paths across TerminusKira, KiraClaw, and KIRA-Slack (`research/sources/codebases/KIRA/terminus_kira/terminus_kira.py`, `research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/scheduler_runtime.py`, `research/sources/codebases/KIRA/KIRA-Slack/app/cc_slack_handlers.py`).
  - A-Evolve shows explicit loop orchestration and evolution-cycle control, with terminal and MCP paths separated rather than collapsed (`research/sources/codebases/a-evolve/agent_evolve/engine/loop.py`, `research/sources/codebases/a-evolve/agent_evolve/algorithms/guided_synth/engine.py`, `research/sources/codebases/a-evolve/agent_evolve/agents/mcp/conversation_manager.py`).
  - The strongest current limitation is also clear:
    - source-visible orchestration capacity exceeds required-task trajectory exercise for deepagents and a-evolve.
- `terminal-first single-agent baseline versus prestige orchestration` is now a first-class mechanism judgment.
  - The codebase lane keeps terminal-first single-agent loops as an active baseline comparator rather than treating more roles as automatic improvement (`tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_06_planning_orchestration_and_interactions/outputs/codebase_source_reconstruction_analyst.md`).
  - The literature lane explicitly frames planning/replanning and delegation as real formal mechanism families, while still cautioning that formal role contracts do not prove behavioral superiority (`tracking/collab/stage_02_synthesis/literature_dossiers/themes/planning_and_replanning.md`, `tracking/collab/stage_02_synthesis/literature_dossiers/themes/delegation_and_role_separation.md`).
  - The informal lane independently reinforces the same anti-prestige rule through coordination-stall, delegation mismatch, and false-confidence pressure clusters (`tracking/collab/stage_02_synthesis/informal_cluster_dossiers/planning_orchestration_and_interactions.md`).
- `interaction contract fragility` is a real failure-bearing mechanism surface, not just implementation mess.
  - Delegation mismatch, context inheritance conflicts, compaction/resume coupling, and permission-hook bypass all show that orchestration quality depends on contract discipline, not just role count (`tracking/collab/stage_02_synthesis/informal_cluster_dossiers/planning_orchestration_and_interactions.md`, `research/sources/codebases/KIRA/KIRA-Slack/app/cc_agents/bot_call_detector/agent.py`).
  - The current synthesis should therefore keep `more orchestration` subordinate to `better interaction contracts and bounded degradation`.

What changed because of contradiction review

- I am scoping the strongest trajectory workflow claims as BigAI-behavioral rather than cross-family universal.
  - The contradiction passes are right that explicit planner/executor/verifier packetization is richest in BigAI required slices, while the sampled deepagents/KIRA required-task trajectories remain closer to single-agent loops (`tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_06_planning_orchestration_and_interactions/outputs/contradiction_analyst.md`, `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_06_planning_orchestration_and_interactions/outputs/contradiction_analyst__claude.md`).
- I am not treating verifier optionality as causally explained.
  - The supported claim is only:
    - verifier-gated closure is dominant in the required BigAI slices,
    - no-verifier completion is also directly present,
    - the controller rule behind that variation remains unresolved.
- I am not blending deepagents delegation source capacity into trajectory-backed behavior proof.
  - The strongest current statement is:
    - deepagents has source-backed delegation APIs and orchestration middleware,
    - but this wave does not yet show equally strong delegation-heavy required-task trajectories for that family.
- I am explicitly naming the `planner-completion` versus `verifier-acceptance` split as a hidden coupling risk.
  - Required runs often show planner `task_finished=true` before verifier closure; that means completion signaling and acceptance are split layers, and the coupling between them is not fully explained (`tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_06_planning_orchestration_and_interactions/outputs/trajectory_support_planning_timeline.md`).
- I am keeping role-handoff fragility at `medium` behavioral confidence rather than letting formal and informal evidence over-inflate it.
  - The literature and informal slices sharpen the pressure, but the direct cross-family behavioral closure is still partial.

Promoted mechanism cards

```text
MECHANISM_CARD
- mechanism_id: planner_first_orchestration_with_conditional_verifier_gate
- name: Planner-First Orchestration With Conditional Verifier Gate
- short_definition: Planning is an explicit early orchestration act, executor work is delegated against that plan, and closure is often but not always gated by a verifier-like adjudication step.
- mechanism_family: orchestration_and_gate_control
- harness_area: planning_and_interaction_governance
- location_in_harness: planner role, executor handoff packet, verifier gate, and replan trigger logic
- operational_shape: The harness emits an explicit plan, delegates work to one or more executors, and may reopen or reroute work after a verifier-style failure. Completion signaling and final acceptance are separate layers.
- problem_it_addresses: hidden coupling between early planning, delegated execution, and final acceptance
- direct_observations:
  - Required BigAI runs show stable planner-first ordering.
  - Verifier-mediated closure is dominant but not universal.
  - A required run shows explicit verifier failure followed by planner replan and second-pass success.
- inferred_behavior:
  - This is a real orchestration family in the BigAI behavioral slice, but it should not yet be promoted as universal across all families.
- evidence_paths:
  - research/analysis/bigai_trace_layer/output/runs/prove-plus-comm/*.json
  - research/analysis/bigai_trace_layer/output/runs/cobol-modernization/*.json
  - research/analysis/bigai_trace_layer/output/runs/openssl-selfsigned-cert/*.json
  - tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_06_planning_orchestration_and_interactions/outputs/trajectory_support_planning_timeline.md
  - tracking/collab/stage_02_synthesis/literature_dossiers/themes/planning_and_replanning.md
- evidence_types:
  - trajectory
  - literature_dossier
- source_families:
  - BigAI
- task_regimes_observed:
  - prove plus comm
  - cobol modernization
  - openssl selfsigned cert
- likely_failure_modes_addressed:
  - unplanned execution drift
  - verifier-detected false completion
  - incomplete recovery after failed first attempt
- failure_role:
  - mixed
- contradictory_or_complicating_evidence:
  - One required in-scope run passes without a visible verifier gate.
  - The causal rule for verifier optionality remains unresolved.
- interaction_notes:
  - Interacts strongly with role handoff packets, replanning triggers, and completion-layer doctrine from Wave 03.
- likely_tradeoffs:
  - More explicit gate structure can improve accountability but may increase latency and coordination overhead.
- simplicity_note:
  - Real family, but not the default baseline.
- likely_eval_implications:
  - Evaluate planner-finished versus verifier-accepted outcomes separately.
- likely_variant_axes:
  - planner plus single executor
  - planner plus executor plus verifier
  - planner plus multi-executor fanout
  - verifier-optional regime
- confidence:
  - high within BigAI behavioral scope; medium for broader family generalization
- open_questions:
  - What controller rule makes verifier optional in some runs?
```

```text
MECHANISM_CARD
- mechanism_id: source_backed_delegation_and_role_boundary_governance
- name: Source-Backed Delegation And Role-Boundary Governance
- short_definition: Delegation and role separation are explicit source-visible mechanism surfaces in several families, but source-visible capability should not be confused with trajectory-proven behavioral dominance.
- mechanism_family: delegation_and_role_contracts
- harness_area: orchestration_runtime
- location_in_harness: subagent APIs, scheduler/runtime queues, role-specific handlers, and loop orchestration modules
- operational_shape: The harness exposes explicit delegation entrypoints, role-specific payload contracts, and runtime coordination surfaces for planner, executor, operator, or specialized-agent work.
- problem_it_addresses: overclaiming orchestration depth from prompt rhetoric without concrete runtime surfaces
- direct_observations:
  - DeepAgents has explicit sync and async subagent middleware.
  - KIRA has queue-backed and multi-role orchestration surfaces.
  - A-Evolve has explicit evolution-cycle and MCP conversation orchestration.
- inferred_behavior:
  - Role-boundary governance is real in source, but deep behavioral saturation is uneven across families in the current wave.
- evidence_paths:
  - research/sources/codebases/deepagents/libs/deepagents/deepagents/middleware/subagents.py
  - research/sources/codebases/deepagents/libs/deepagents/deepagents/middleware/async_subagents.py
  - research/sources/codebases/KIRA/KiraClaw/apps/agentd/src/kiraclaw_agentd/scheduler_runtime.py
  - research/sources/codebases/KIRA/KIRA-Slack/app/cc_slack_handlers.py
  - research/sources/codebases/a-evolve/agent_evolve/engine/loop.py
  - research/sources/codebases/a-evolve/agent_evolve/algorithms/guided_synth/engine.py
  - tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_06_planning_orchestration_and_interactions/outputs/codebase_support_subagent_delegation_map.md
- evidence_types:
  - source_code
  - support_artifact
- source_families:
  - deepagents
  - KIRA
  - a-evolve
- task_regimes_observed:
  - source-visible orchestration runtime
  - delegation APIs
  - role handoff
- likely_failure_modes_addressed:
  - hidden delegation coupling
  - lost ownership between specialist roles
  - orchestration collapse into one opaque loop
- failure_role:
  - preventive
- contradictory_or_complicating_evidence:
  - Required trajectory slices for deepagents and a-evolve do not yet exercise delegation-heavy orchestration at the same depth as the source suggests.
- interaction_notes:
  - Interacts strongly with permission policy, context inheritance, and verifier/completion gates.
- likely_tradeoffs:
  - Richer role separation can improve modularity but can also create coordination drift, approval mismatch, and handoff loss.
- simplicity_note:
  - Real and important, but should stay bounded by trajectory evidence.
- likely_eval_implications:
  - Evaluate role-boundary quality and delegation recovery, not just number of roles.
- likely_variant_axes:
  - single-agent explicit plan loop
  - delegated specialist tools
  - queue-backed role scheduler
  - evolution-cycle orchestration
- confidence:
  - high for source-backed existence; medium for cross-family behavioral saturation
- open_questions:
  - Which deepagents and a-evolve trajectory slices best pressure-test these role contracts directly?
```

```text
MECHANISM_CARD
- mechanism_id: anti_prestige_terminal_first_baseline
- name: Anti-Prestige Terminal-First Baseline
- short_definition: More roles, more agents, or more orchestration scaffolding are not inherently better than a simpler terminal-first single-agent loop with explicit replanning and verification pressure.
- mechanism_family: baseline_selection_and_complexity_control
- harness_area: orchestration_choice
- location_in_harness: execution-block selection, orchestration policy, and experiment comparison doctrine
- operational_shape: The harness keeps a minimal-sufficient baseline visible and refuses to treat orchestration complexity as default improvement without direct evidence.
- problem_it_addresses: false confidence from prestige orchestration rhetoric and role multiplication
- direct_observations:
  - Sampled deepagents and Terminus-KIRA required-task trajectories remain mostly single-agent loops.
  - Literature and informal evidence both warn that role contracts and degradation quality matter more than role count alone.
  - Issue pressure shows orchestration-heavy systems can fail through coordination stalls, delegation mismatch, and context poisoning.
- inferred_behavior:
  - Complexity control is itself a mechanism choice and should remain visible in local harness design.
- evidence_paths:
  - research/sources/trajectories/deepagents/cobol-modernization/cabb8c07-4d6f-415d-9553-82cd2ca1cc13-traj.txt
  - research/sources/trajectories/terminus-kira/cobol-modernization/8da60a45-3657-4a7c-99d3-d9f0cf7de3dd-traj.txt
  - tracking/collab/stage_02_synthesis/literature_dossiers/themes/delegation_and_role_separation.md
  - tracking/collab/stage_02_synthesis/informal_cluster_dossiers/planning_orchestration_and_interactions.md
  - tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_06_planning_orchestration_and_interactions/outputs/contradiction_analyst.md
- evidence_types:
  - trajectory
  - literature_dossier
  - informal_cluster
  - contradiction_review
- source_families:
  - deepagents
  - KIRA
  - public operator failure clusters
- task_regimes_observed:
  - prove plus comm
  - cobol modernization
  - openssl selfsigned cert
  - browser and long-output issue clusters
- likely_failure_modes_addressed:
  - prestige-driven overgrowth
  - needless coordination overhead
  - false confidence from role multiplication
- failure_role:
  - preventive
- contradictory_or_complicating_evidence:
  - BigAI required slices do show a real role-separated family; the point is not that orchestration is fake, but that it is not automatically dominant.
- interaction_notes:
  - Interacts with Wave 05 terminal-first tooling baseline and with Wave 03 verifier-layer separation.
- likely_tradeoffs:
  - Over-preserving the simple baseline can underexplore tasks that genuinely need richer orchestration.
- simplicity_note:
  - Core anti-prestige card for the next phase.
- likely_eval_implications:
  - Future evals should compare orchestration-heavy variants directly against simpler baselines, not only against other complex systems.
- likely_variant_axes:
  - flat single-agent loop
  - planner plus executor
  - planner plus executor plus verifier
  - multi-executor orchestration
- confidence:
  - high
- open_questions:
  - What is the minimum information-gain threshold that justifies leaving the simple baseline?
```

What still requires another wave

- Wave 06 does not complete `mechanism_map`; it closes the final mechanism-domain wave only at principal-synthesis level, pending checklist.
- Cross-family behavioral saturation for delegation-heavy deepagents and a-evolve work remains thinner than source-side capability evidence.
- BigAI remains behavior-rich but source-opaque, so scheduler heuristics, verifier optionality rules, and deeper interaction policy remain unresolved.
- HITL delegation and subagent context-poisoning pressure are now visible but not deeply excavated in this wave (`research/sources/codebases/deepagents/libs/deepagents/deepagents/middleware/hitl.py` remains a relevant deferred source).

Local harness implications

- The local harness should preserve a swappable `execution/orchestration` surface rather than hard-coding one prestige workflow.
  - `blocks/execution/flat_loop.py`, `blocks/execution/guided_loop.py`, and `blocks/execution/dag_loop.py` should stay comparable rather than one absorbing all planning and delegation semantics.
- `VerificationBlock` and orchestration policy should stay separate.
  - Wave 06 reinforces Wave 03’s rule that completion signaling and final acceptance are distinct; local orchestration should not collapse planner “done” into verifier acceptance.
- The local harness needs explicit room for bounded delegation without forcing it.
  - If subagents or specialist roles exist, their contracts should be explicit, narrow, and degradable back to the simpler baseline.
- Permission and context inheritance at handoff boundaries remain high-risk.
  - Wave 05 and Wave 06 together suggest any local subagent or planner-executor handoff must carry explicit policy and context-boundary rules, not hidden shared state.

Coverage not yet used

- `research/sources/trajectories/*/protein-assembly/*.tar.gz` and deeper long-tail delegation-heavy archives
- `research/sources/trajectories/*/large-scale-text-editing/*.tar.gz` beyond sampled runs
- fuller KIRA-Slack subsystem closure
- `research/sources/codebases/deepagents/libs/deepagents/deepagents/middleware/hitl.py`
- deeper postmortem durability checks after issue closure

Priority sources not yet read

- `research/sources/codebases/deepagents/libs/deepagents/deepagents/middleware/hitl.py`
- `research/sources/codebases/KIRA/KIRA-Slack/app/main.py`
- `research/sources/codebases/a-evolve/agent_evolve/benchmarks/tb2/terminal2.py`
- `research/sources/trajectories/BigAI/prove-plus-comm/cd0d69dd-3cac-47e0-9777-51327561ff6d.tar.gz`

Support track updates

- Required Wave 06 dossiers and case studies exist and are substantive enough for synthesis:
  - `tracking/collab/stage_02_synthesis/source_system_dossiers/deepagents.md`
  - `tracking/collab/stage_02_synthesis/source_system_dossiers/KIRA.md`
  - `tracking/collab/stage_02_synthesis/source_system_dossiers/a-evolve.md`
  - `tracking/collab/stage_02_synthesis/source_system_dossiers/BigAI_behavioral.md`
  - `tracking/collab/stage_02_synthesis/source_system_dossiers/claw-code.md`
  - `tracking/collab/stage_02_synthesis/literature_dossiers/themes/planning_and_replanning.md`
  - `tracking/collab/stage_02_synthesis/literature_dossiers/themes/delegation_and_role_separation.md`
  - `tracking/collab/stage_02_synthesis/informal_cluster_dossiers/planning_orchestration_and_interactions.md`
  - `tracking/collab/stage_02_synthesis/trajectory_case_studies/prove_plus_comm.md`
  - `tracking/collab/stage_02_synthesis/trajectory_case_studies/cobol_modernization.md`
  - `tracking/collab/stage_02_synthesis/trajectory_case_studies/openssl_selfsigned_cert.md`
- Coverage-register state was stale going into this pass and is updated here to reflect Wave 06 first-pass completion.
- The missing `headless_terminal.md` path remains a Wave 05 carry-forward warning, not a Wave 06 structural blocker.

Next governed step

- Run Wave 06 checklist adjudication.
