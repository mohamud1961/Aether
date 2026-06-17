# Deep Synthesis Phase And Wave Operating Plan

Use this file when deciding how to staff and run a specific Deep Synthesis wave.

## Current compressed stage structure

- `14` core waves
- `7` continuous support tracks

Support tracks:

- `coverage_access`
- `coverage_register`
- `source_system_dossiers`
- `trajectory_case_studies`
- `literature_dossiers`
- `informal_cluster_dossiers`
- `eval_benchmark_dossiers`

## Current completed state

- `mechanism_map` Wave 01 `exploratory_anchor`
  - complete
- `mechanism_map` Wave 02 `execution_control_and_terminal_grounding`
  - accepted with carry-forward warnings
- `mechanism_map` Wave 03 `verification_completion_and_recovery`
  - accepted with carry-forward warnings
- `mechanism_map` Wave 04 `context_state_memory_workspace`
  - accepted with carry-forward warnings
- `mechanism_map` Wave 05 `tools_environment_permissions`
  - accepted with carry-forward warnings
- `mechanism_map` Wave 06 `planning_orchestration_and_interactions`
  - accepted with carry-forward warnings
- `failure_taxonomy` Wave 01 `execution_control_and_terminal_failures`
  - accepted with carry-forward warnings
- `failure_taxonomy` Wave 02 `verification_completion_and_recovery_failures`
  - accepted with carry-forward warnings
- `failure_taxonomy` Wave 03 `context_state_memory_workspace_failures`
  - accepted with carry-forward warnings

## Core-wave map

### Mechanism Map

1. `exploratory_anchor`
2. `execution_control_and_terminal_grounding`
3. `verification_completion_and_recovery`
4. `context_state_memory_workspace`
5. `tools_environment_permissions`
6. `planning_orchestration_and_interactions`

### Failure Taxonomy

1. `execution_control_and_terminal_failures`
2. `verification_completion_and_recovery_failures`
3. `context_state_memory_workspace_failures`
4. `tools_environment_coordination_and_long_horizon_failures`

### Eval Implications

1. `benchmark_contracts_and_risks`
2. `project_eval_architecture`

### Variant Family Seeds

1. `candidate_families_and_pruning`
2. `block_mapping_and_seed_closeout`

## Serious mechanism and failure waves

Default main-lane roster:

1. `trajectory/failure analyst`
2. `codebase/source-reconstruction analyst`
3. `literature/papers/docs analyst`
4. `informal/issues/postmortems analyst`

Optional fifth lane:

5. `eval/benchmark analyst`

Recommended models:

- trajectory:
  - `GPT-5.4 xhigh`
- source:
  - `GPT-5.3 Codex xhigh`
- literature:
  - `GPT-5.4 xhigh`
- informal:
  - `GPT-5.4 xhigh`
- eval:
  - `GPT-5.4 xhigh`

When to activate eval as a fifth lane:

- verifier logic is central
- grader logic is central
- replay logic is central
- benchmark contract logic is central

## Support-sub-agent model

Use bounded support sub-agents under the main lanes for:

- inventories
- route maps
- file discovery
- subsystem maps
- matrices
- archive triage
- source-link gathering
- paper or issue grouping

Recommended support models:

- code-heavy support:
  - `GPT-5.3 Codex high`
- clustering, matrices, inventories:
  - `GPT-5.4-mini high`

## Eval-implication waves

Use role-sequenced critique:

1. proposer
2. critic
3. falsifier
4. breadth checker
5. principal synthesis

Recommended models:

- proposer:
  - `GPT-5.4 xhigh`
- critic:
  - `GPT-5.3 Codex xhigh`
- falsifier:
  - `GPT-5.4 xhigh`
- breadth checker:
  - `GPT-5.4 xhigh`

## Variant-family waves

Use hybrid execution:

1. seed proposer A
2. seed proposer B
3. pruning critic
4. contradiction review
5. principal synthesis

## Gate-time external review

Gemini and Claude are used at gates, not as routine parallel main lanes.

Use:

- `Gemini 3.1 Pro`
  - breadth or long-context gate review
- `Claude Opus 4.6`
  - contradiction or acceptance gate review

Best gate moments:

- contradiction review
- checklist adjudication
- high-risk breadth check before closing an artifact

## Wave packet minimums

Every wave packet should say:

- `new_resolution_goal`
- `why_prior_waves_were_not_enough`
- required support tracks
- required dossier updates
- what can be left unfinished without blocking contradiction review
- whether eval is a fifth main lane

## Current next planned wave

- `failure_taxonomy` Wave 04 `tools_environment_coordination_and_long_horizon_failures`
  - overall core wave: Wave 10
  - eval fifth lane: inactive by default
  - current stage: packet-prepared
