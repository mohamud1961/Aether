# Failure Taxonomy Wave 04 Model And Launch Recommendations

## Recommended models

- trajectory/failure analyst: `GPT-5.4 xhigh`
- codebase/source reconstruction analyst: `GPT-5.3 Codex xhigh`
- literature/papers/docs analyst: `GPT-5.4 xhigh`
- informal/issues/postmortems analyst: `GPT-5.4 xhigh`
- optional eval/benchmark analyst if reactivated: `GPT-5.4 xhigh`
- bounded code-heavy support: `GPT-5.3 Codex high`
- bounded inventory/matrix/cluster support: `GPT-5.4-mini high`
- contradiction analyst: `GPT-5.4 xhigh`
- checklist adjudicator: `GPT-5.4 xhigh`
- Gemini gate: `Gemini 3.1 Pro`
- Claude gate: `Claude Opus 4.6`

## Eval policy

Eval is inactive by default in Wave 04.
Use [eval_reactivation_packet.md](/Users/mohamud/Downloads/harnesseng/tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_04_tools_environment_coordination_and_long_horizon_failures/inputs/eval_reactivation_packet.md) only when reactivation conditions are met.

## Canonical output paths (from outputs/README)

- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_04_tools_environment_coordination_and_long_horizon_failures/outputs/trajectory_failure_analyst.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_04_tools_environment_coordination_and_long_horizon_failures/outputs/codebase_source_reconstruction_analyst.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_04_tools_environment_coordination_and_long_horizon_failures/outputs/literature_papers_docs_analyst.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_04_tools_environment_coordination_and_long_horizon_failures/outputs/informal_issues_postmortems_analyst.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_04_tools_environment_coordination_and_long_horizon_failures/outputs/eval_benchmark_analyst.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_04_tools_environment_coordination_and_long_horizon_failures/outputs/trajectory_support_tool_coordination_failure_matrix.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_04_tools_environment_coordination_and_long_horizon_failures/outputs/trajectory_support_long_horizon_failure_timeline.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_04_tools_environment_coordination_and_long_horizon_failures/outputs/codebase_support_tool_environment_failure_map.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_04_tools_environment_coordination_and_long_horizon_failures/outputs/codebase_support_orchestration_failure_map.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_04_tools_environment_coordination_and_long_horizon_failures/outputs/literature_support_tools_orchestration_failure_cluster.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_04_tools_environment_coordination_and_long_horizon_failures/outputs/informal_support_long_horizon_tooling_failure_cluster.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_04_tools_environment_coordination_and_long_horizon_failures/outputs/eval_support_benchmark_time_contract_map.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_04_tools_environment_coordination_and_long_horizon_failures/outputs/contradiction_analyst.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_04_tools_environment_coordination_and_long_horizon_failures/outputs/contradiction_analyst__gemini.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_04_tools_environment_coordination_and_long_horizon_failures/outputs/contradiction_analyst__claude.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_04_tools_environment_coordination_and_long_horizon_failures/adjudication/checklist_adjudicator.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_04_tools_environment_coordination_and_long_horizon_failures/adjudication/checklist_adjudicator__gemini.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_04_tools_environment_coordination_and_long_horizon_failures/adjudication/checklist_adjudicator__claude.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_04_tools_environment_coordination_and_long_horizon_failures/synthesis/principal_synthesis.md`

## Recommended launch order

1. trajectory lane
2. codebase/source lane
3. literature lane
4. informal lane
5. primary contradiction
6. optional Gemini/Claude contradiction gates
7. principal synthesis
8. primary checklist
9. optional Gemini/Claude checklist gates
10. optional eval lane only if reactivated

## Dirty-worktree rule

- Expect unrelated dirty files and concurrent Deep Synthesis outputs.
- Do not stop for a dirty worktree alone.
- Edit only assigned Wave 04 files and explicitly assigned support dossier files.
- Do not revert, clean, stage, delete, or overwrite unrelated files.
- Stop only if an unrelated dirty file directly conflicts with assigned write scope.
