# Wave 05 Model And Launch Recommendations

## Recommended models per main lane

- trajectory/failure analyst:
  - `GPT-5.4 xhigh`
- codebase/source reconstruction analyst:
  - `GPT-5.3 Codex xhigh`
- literature/papers/docs analyst:
  - `GPT-5.4 xhigh`
- informal/issues/postmortems analyst:
  - `GPT-5.4 xhigh`

## Recommended model for contradiction

- contradiction analyst:
  - `GPT-5.4 xhigh`

## Recommended model for checklist

- checklist adjudicator:
  - `GPT-5.4 xhigh`

## Recommended use of Gemini gate review

- model:
  - `Gemini 3.1 Pro`
- use:
  - breadth or long-context gate pressure
- best timing:
  - contradiction stage by default
  - checklist stage when breadth still looks thin

## Recommended use of Claude gate review

- model:
  - `Claude Opus 4.6`
- use:
  - adversarial contradiction or acceptance pressure
- best timing:
  - contradiction stage by default
  - checklist stage if acceptance remains close-call

## Eval lane policy for Wave 05

Wave 05 should keep eval inactive by default.

Only recommend activation if preflight shows evaluator-side tool/environment/permission logic is load-bearing.

If needed, write a recommendation note first:

- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/eval_reactivation_recommendation.md`

Do not silently launch eval.

## Very short launch order

1. trajectory lane
2. codebase lane
3. literature lane
4. informal lane
5. contradiction review
6. optional Gemini or Claude contradiction gate review
7. principal synthesis
8. checklist adjudication
9. optional Gemini or Claude checklist gate review

## Canonical Wave 05 output paths

Main lanes:

- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/trajectory_failure_analyst.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/codebase_source_reconstruction_analyst.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/literature_papers_docs_analyst.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/informal_issues_postmortems_analyst.md`

Primary gates:

- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/contradiction_analyst.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/adjudication/checklist_adjudicator.md`

External gate siblings:

- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/contradiction_analyst__gemini.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/outputs/contradiction_analyst__claude.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/adjudication/checklist_adjudicator__gemini.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/adjudication/checklist_adjudicator__claude.md`

Principal synthesis:

- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_05_tools_environment_permissions/synthesis/principal_synthesis.md`

Carry-forward control surfaces:

- `tracking/collab/stage_02_synthesis/mechanism_map/synthesis/cumulative_synthesis.md`
- `tracking/collab/stage_02_synthesis/coverage_register/current_status.md`
