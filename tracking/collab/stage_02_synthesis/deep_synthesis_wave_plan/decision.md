# Deep Synthesis Wave Plan Decision

Status: accepted and upgraded; compressed 14-wave model is now the binding Deep Synthesis stage governance

Opened: 2026-04-03

Updated: 2026-04-07

Artifact

- `deep_synthesis_wave_plan`

Goal

- Define the concrete Deep Synthesis operating model so the stage is deep enough, fast enough, and honest enough for downstream eval and variant work.

Why this decision changed

- The earlier 24-wave model solved the honesty problem but created too much governance weight.
- Wave 02 execution provided real evidence about what was missing:
  - depth support artifacts
  - trajectory-to-source case studies
  - explicit lane-closure criteria
  - a mandatory coverage register
  - stronger separation between formal and informal evidence lanes
- The owner requested a plan upgrade that preserves depth while improving speed and reducing unnecessary serial overhead.

Judgment

- Deep Synthesis now runs as:
  - `14` core waves
  - `7` continuous support tracks
- `coverage_access` is no longer counted as 5 heavy core waves.
  - it is now a continuous support track with:
    - `Gate A baseline_access_ready`
    - `Gate B final_coverage_closure`
- Serious `mechanism_map` and `failure_taxonomy` waves now default to:
  - `trajectory/failure`
  - `codebase/source reconstruction`
  - `literature/papers/docs`
  - `informal/issues/postmortems`
  - optional `eval/benchmark` as a fifth main lane only when needed
- Gemini is no longer a default blind-parallel main lane.
- Gemini and Claude are now gate-time external reviewers for:
  - contradiction pressure
  - breadth checks
  - checklist or acceptance gates
- The coverage register is mandatory and load-bearing.

Completed state now recorded

- `mechanism_map` Wave 01 `exploratory_anchor`:
  - complete
  - preserved as legacy anchor only
- `mechanism_map` Wave 02 `execution_control_and_terminal_grounding`:
  - accepted as a wave
  - verdict:
    - `pass_with_warnings`
    - `wave accepted with carry-forward warnings`
- paper-text baseline:
  - available under `research/sources/papers/papers_text/`
  - `200` readable papers on the current pass

Current active and queued work

- active core artifact:
  - `mechanism_map`
- next planned core wave:
  - Wave 03 `verification_completion_and_recovery`
- continuous support work:
  - `coverage_access`
  - `coverage_register`
  - dossier and case-study maintenance

Approval boundary

- This upgraded model reflects owner-approved direction as of 2026-04-07.
- It supersedes the earlier 24-wave maximal layout as the active working plan.
