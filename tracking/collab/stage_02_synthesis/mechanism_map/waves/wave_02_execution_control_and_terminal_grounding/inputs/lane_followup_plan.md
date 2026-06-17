# Wave 02 Lane Follow-Up Plan

Status: active governance addendum for `wave_02_execution_control_and_terminal_grounding`

Purpose

- Prevent the Wave 02 first-pass lane outputs from being misread as lane-complete analysis.
- Define the governed follow-up path when a lane does not yet satisfy the packet-required depth for this wave.

Current interpretation of the existing lane files

- The current unsuffixed role outputs under `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_02_execution_control_and_terminal_grounding/outputs/` are first-pass lane outputs only.
- No lane should be treated as complete yet.
- The wave has not earned lane-sufficient status until contradiction review and wave principal synthesis explicitly say so.

Why this addendum exists

- The Wave 02 packet is deliberately deep for the trajectory lane and still substantial for source, formal, and informal lanes.
- Fast first-pass completion is useful for opening contradiction pressure, but it is not evidence that every lane has reached real coverage.
- The trajectory lane in particular must not be flattened into "read a few trajectories and call it done."

Trajectory lane minimum depth for this wave

The trajectory/failure lane is only wave-sufficient for this domain if it either completes or explicitly schedules follow-up for:

- per-run analysis across the selected readable runs in the wave-targeted task families
- shared-task cross-system comparison across the wave-selected families
- pass/fail divergence analysis where the same task family shows meaningful spread
- failure-point comparison for the strongest divergence cases
- mechanism hypotheses anchored in observed trajectory behavior
- source reconciliation where source exists
- explicit `behavioral reconstruction` caveats where source does not exist
- honest inventory of archive-only or unread runs that could still change the judgment

Expected lane-specific follow-up pressure

- `trajectory_failure_analyst`
  - deepen run-by-run analysis where the first pass stayed at family summary level
  - unpack or inspect priority archive variants when the current behavior claim depends too heavily on the readable text subset
  - add explicit pass/fail and failure-point comparison tables for the strongest shared-task contrasts
  - add source-reconciliation notes for DeepAgents, KIRA, claw-code, and other visible-source families where execution-control claims are promoted
- `codebase_source_reconstruction_analyst`
  - close remaining low-level execution-control questions in KIRA session handling, DeepAgents shell control, claw-code runtime control, and top-tier `src_cod_*` captures
  - strengthen behavior-to-source mapping for the trajectory claims promoted by this wave
- `literature_papers_docs_analyst`
  - read priority unread formal sources that could materially change the execution-control judgment
  - keep formal-vs-behavior tensions explicit instead of smoothing them away
- `informal_issues_postmortems_analyst`
  - extend the operating-pressure corpus where current omissions affect execution control, interruption recovery, cleanup discipline, or long-horizon control claims
- `eval_benchmark_analyst`
  - activate only if verifier, replay, grader, or completion-contract logic becomes load-bearing for execution-control interpretation during contradiction review or wave synthesis

Governed follow-up path

If a lane remains under-covered after contradiction review, the principal should do one of:

1. Open a same-wave governed follow-up output such as:
   - `trajectory_failure_analyst__followup_01.md`
   - `codebase_source_reconstruction_analyst__followup_01.md`
   - `literature_papers_docs_analyst__followup_01.md`
   - `informal_issues_postmortems_analyst__followup_01.md`
2. Mark the missing depth explicitly in wave principal synthesis under:
   - `what_still_requires_another_wave`
   - `coverage_not_yet_used`
   - `priority_sources_not_yet_read`
3. Carry the unresolved domain pressure into the next vertical mechanism wave only if the missing work is truly outside the current wave focus rather than neglected current-wave scope.

Closure rule

- A first-pass file does not imply lane completion.
- A lane only becomes wave-sufficient when the principal says so explicitly after contradiction review.
- If the trajectory lane still lacks the minimum depth above, the wave should be treated as incomplete for decision-heavy execution-control claims even if some useful mechanism cards can already be carried forward as exploratory or emerging.
