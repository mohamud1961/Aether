# Failure Taxonomy Wave 03 Prompt Engineer Request

Use this request to create launch-ready prompts for overall Deep Synthesis Wave 09 / `failure_taxonomy` Wave 03.

Prompt to use

```text
You are the Deep Synthesis prompt-engineering agent.

Task: create launch-ready prompt packets for overall Deep Synthesis Wave 09, artifact-local `failure_taxonomy` Wave 03 `context_state_memory_workspace_failures`.

Read first:
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

Create these prompt packet files:
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/inputs/trajectory_lane_packet.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/inputs/codebase_lane_packet.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/inputs/literature_lane_packet.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/inputs/informal_lane_packet.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/inputs/eval_reactivation_packet.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/inputs/contradiction_packet.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/inputs/checklist_packet.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/inputs/gemini_gate_review_packet.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/inputs/claude_gate_review_packet.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/inputs/support_task_templates.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/inputs/model_and_launch_recommendations.md`

Main lanes to create:
- trajectory/failure analyst -> output `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/trajectory_failure_analyst.md`
- codebase/source reconstruction analyst -> output `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/codebase_source_reconstruction_analyst.md`
- literature/papers/docs analyst -> output `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/literature_papers_docs_analyst.md`
- informal/issues/postmortems analyst -> output `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/informal_issues_postmortems_analyst.md`

Eval policy:
- Eval/benchmark is inactive by default for this wave.
- Include a short `eval_reactivation_packet.md` that explains when to activate it.
- Reactivate eval only if benchmark state contracts, replay state, grader workspace expectations, or task persistence contracts become load-bearing.
- If reactivated, output path is `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/eval_benchmark_analyst.md`.

Gate outputs to include:
- primary contradiction -> `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/contradiction_analyst.md`
- Gemini contradiction gate -> `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/contradiction_analyst__gemini.md`
- Claude contradiction gate -> `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/outputs/contradiction_analyst__claude.md`
- primary checklist -> `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/adjudication/checklist_adjudicator.md`
- optional Gemini checklist -> `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/adjudication/checklist_adjudicator__gemini.md`
- optional Claude checklist -> `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/adjudication/checklist_adjudicator__claude.md`
- principal synthesis -> `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_03_context_state_memory_workspace_failures/synthesis/principal_synthesis.md`

Support artifacts to include:
- `trajectory_support_context_workspace_failure_matrix.md`
- `trajectory_support_memory_state_drift_cases.md`
- `codebase_support_context_state_failure_map.md`
- `codebase_support_workspace_persistence_map.md`
- `literature_support_context_memory_failure_cluster.md`
- `informal_support_context_workspace_failure_cluster.md`
- optional if eval reactivated: `eval_support_state_contract_map.md`

Key wave rules:
- This is not a generic context/memory mechanism recap. It is a failure-taxonomy wave.
- Do not collapse context loss, stale memory, workspace drift, branch/path corruption, session persistence failure, and runtime memory pressure into one generic memory failure bucket.
- Runtime allocator-memory failures must remain distinct from coding-agent context/memory failures.
- BigAI must stay labeled `behavioral reconstruction`.
- First-pass outputs are not complete coverage by themselves.
- Each lane must name `coverage_used`, `coverage_not_yet_used`, `support_artifacts_used`, `support_artifacts_requested_or_deferred`, and `coverage_register_updates_needed`.
- Support sub-agents are allowed only for bounded support tasks, and support outputs are not final evidence claims by themselves.
- Gemini and Claude are gate-time reviewers, not default parallel main lanes.

Dirty-worktree rule to include in every packet:
- Expect unrelated dirty files and concurrent Deep Synthesis outputs.
- Do not stop for a dirty worktree alone.
- Edit only assigned Wave 03 files and explicitly assigned support dossier files.
- Do not revert, clean, stage, delete, or overwrite unrelated files.
- Stop only if an unrelated dirty file directly conflicts with the assigned write scope.

Recommended models:
- trajectory/failure analyst: GPT-5.4 xhigh
- codebase/source reconstruction analyst: GPT-5.3 Codex xhigh
- literature/papers/docs analyst: GPT-5.4 xhigh
- informal/issues/postmortems analyst: GPT-5.4 xhigh
- optional eval/benchmark analyst if reactivated: GPT-5.4 xhigh
- bounded code-heavy support: GPT-5.3 Codex high
- bounded inventory/matrix/cluster support: GPT-5.4-mini high
- contradiction analyst: GPT-5.4 xhigh
- checklist adjudicator: GPT-5.4 xhigh
- Gemini gate: Gemini 3.1 Pro for breadth/long-context pressure
- Claude gate: Claude Opus 4.6 for adversarial contradiction/acceptance pressure

End by listing the exact prompts you created and the launch order.
```
