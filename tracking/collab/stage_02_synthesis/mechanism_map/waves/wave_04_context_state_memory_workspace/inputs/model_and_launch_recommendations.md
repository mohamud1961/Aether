# Wave 04 Model And Launch Recommendations

## Recommended models

Main lanes:

- trajectory/failure analyst:
  - `GPT-5.4 xhigh`
- codebase/source reconstruction analyst:
  - `GPT-5.3 Codex xhigh`
- literature/papers/docs analyst:
  - `GPT-5.4 xhigh`
- informal/issues/postmortems analyst:
  - `GPT-5.4 xhigh`

Gate roles:

- contradiction analyst:
  - `GPT-5.4 xhigh`
- checklist adjudicator:
  - `GPT-5.4 xhigh`

Support sub-agents:

- code-heavy support:
  - `GPT-5.3 Codex high`
- matrices, clustering, inventories, route maps:
  - `GPT-5.4-mini high`

External gate review:

- Gemini:
  - `Gemini 3.1 Pro`
  - use for breadth or long-context gate review
- Claude:
  - `Claude Opus 4.6`
  - use for contradiction or acceptance pressure

## Eval lane recommendation

Wave 04 should keep eval inactive by default.

Only recommend reactivation if preflight shows that:

- benchmark state-comparison logic is central
- grader-side state handling is central
- evaluator-side state or replay contracts materially shape the Wave 04 mechanism judgment

If that happens, write a short recommendation note first instead of silently launching the lane.

Suggested note path:

- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/outputs/eval_reactivation_recommendation.md`

## Short launch order

1. trajectory lane
2. codebase lane
3. literature lane
4. informal lane
5. contradiction review
6. optional Gemini or Claude contradiction gate
7. principal synthesis
8. checklist adjudication
9. optional Gemini or Claude checklist gate if needed

## Gate reviewer recommendation

Default recommendation:

- use `Claude` at contradiction review if you want one external adversarial pass

Optional additional breadth pass:

- use `Gemini` at contradiction review or checklist adjudication if coverage still feels thin

## Output paths for the main wave

Main lanes:

- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/outputs/trajectory_failure_analyst.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/outputs/codebase_source_reconstruction_analyst.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/outputs/literature_papers_docs_analyst.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/outputs/informal_issues_postmortems_analyst.md`

Primary gates:

- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/outputs/contradiction_analyst.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/adjudication/checklist_adjudicator.md`

External gate siblings:

- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/outputs/contradiction_analyst__gemini.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/outputs/contradiction_analyst__claude.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/adjudication/checklist_adjudicator__gemini.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/adjudication/checklist_adjudicator__claude.md`

Synthesis:

- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/synthesis/principal_synthesis.md`

Carry-forward surfaces to update after principal synthesis and checklist:

- `tracking/collab/stage_02_synthesis/mechanism_map/synthesis/cumulative_synthesis.md`
- `tracking/collab/stage_02_synthesis/coverage_register/current_status.md`
