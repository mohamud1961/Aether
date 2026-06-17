# Failure Taxonomy Wave 01 Support Task Templates

Use these templates when a Wave 01 main lane needs bounded support help.

Always pair with:

- `prompts/deep_synthesis_support_subagent_prompt.md`
- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/inputs/support_subagent_rules.md`

Support artifacts are not final synthesis.

## Trajectory lane template

- task shape:
  - bounded run inventory, failure timeline, or failure matrix for selected slices
- input scope:
  - selected paths under `research/sources/trajectories/` and `research/analysis/bigai_trace_layer/output/`
- stop condition:
  - stop when requested timeline/matrix is complete and path-backed
- output naming pattern:
  - `trajectory_support_<topic>.md`
- reminder:
  - do not promote final failure claims

Typical outputs:

- `trajectory_support_failure_timeline.md`
- `trajectory_support_terminal_failure_matrix.md`

## Source lane template

- task shape:
  - bounded subsystem map for execution failure and interrupt/cancel boundaries
- input scope:
  - selected paths under `research/sources/codebases/`, `blocks/`, `runner/`, and `evals/`
- stop condition:
  - stop when requested subsystem map is complete and path-backed
- output naming pattern:
  - `codebase_support_<topic>.md`
- reminder:
  - support maps do not equal promoted failure attribution

Typical outputs:

- `codebase_support_execution_failure_map.md`
- `codebase_support_interrupt_cancellation_map.md`

## Literature lane template

- task shape:
  - bounded cluster for failure pressure terms and attribution confounders
- input scope:
  - selected paths under `research/sources/papers/papers_text/` and `research/sources/docs/`
- stop condition:
  - stop when requested cluster/route map is complete and path-backed
- output naming pattern:
  - `literature_support_<topic>.md`
- reminder:
  - support clusters aid synthesis; they are not final claims

Typical output:

- `literature_support_failure_pressure_cluster.md`

## Informal lane template

- task shape:
  - bounded issue/postmortem cluster for one failure family
- input scope:
  - selected paths under `research/sources/informal/`, `research/sources/issues/`, and `research/sources/postmortems/`
- stop condition:
  - stop when requested cluster is complete with strong/weak evidence separation
- output naming pattern:
  - `informal_support_<topic>.md`
- reminder:
  - support clustering is not final failure attribution

Typical output:

- `informal_support_timeout_false_success_cluster.md`

## Optional eval lane support if explicitly reactivated

- task shape:
  - bounded map of benchmark contract failure and verifier/grader blind spots
- input scope:
  - selected paths under `research/sources/benchmarks/`, `research/sources/codebases/deepagents/libs/evals/`, and `evals/`
- stop condition:
  - stop when requested map is complete and path-backed
- output naming pattern:
  - `eval_support_<topic>.md`
- reminder:
  - eval remains inactive unless principal explicitly reactivates it

Potential output:

- `eval_support_benchmark_failure_contract_map.md`

