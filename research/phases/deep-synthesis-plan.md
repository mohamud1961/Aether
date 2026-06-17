# Deep Synthesis Plan

Date: 2026-04-07

Artifact

- `deep_synthesis_plan`

Stage boundary

- Deep Synthesis is active.
- The stage should now run under the compressed 14-wave model defined in:
  - `tracking/collab/stage_02_synthesis/deep_synthesis_wave_plan/synthesis/principal_synthesis.md`

Corpus scope and evidence policy

- Integrity anchor:
  - `research/intake/normalized/manifests/corpus__captured_for_synthetic_prep.json`
- In-scope evidence classes:
  - `research/sources/trajectories/`
  - `research/sources/papers/`
  - `research/sources/docs/`
  - `research/sources/informal/`
  - `research/sources/issues/`
  - `research/sources/postmortems/`
  - mirrored repos under `research/sources/codebases/`
  - benchmark and eval surfaces under `research/sources/benchmarks/` and `evals/`
  - relevant local analysis under `research/analysis/`
  - relevant local harness code under `blocks/`, `runner/`, and `evals/`

Evidence precedence

- Direct behavior evidence outranks retrospective discussion when both address the same claim.
- Visible source code outranks conceptual description when the question is about actual implementation.
- Official papers and docs outrank informal notes for definitions and stated benchmark contracts.
- Papers and docs do not override stronger on-disk behavior or source evidence.
- Derived analyses and organizers are routing aids until claims are checked against underlying evidence paths.

Operating model

- Deep Synthesis now uses:
  - `14` core waves
  - `7` continuous support tracks
- Wave acceptance is not artifact completion.
- Coverage should be made explicit through:
  - support tracks
  - dossiers
  - case studies
  - the coverage register

Required support tracks

- `coverage_access`
- `coverage_register`
- `source_system_dossiers`
- `trajectory_case_studies`
- `literature_dossiers`
- `informal_cluster_dossiers`
- `eval_benchmark_dossiers`

Multi-agent setup

- principal steward:
  - one stable principal model
- serious-wave main lanes:
  - `trajectory/failure analyst`
  - `codebase/source-reconstruction analyst`
  - `literature/papers/docs analyst`
  - `informal/issues/postmortems analyst`
- optional fifth main lane:
  - `eval/benchmark analyst`
- bounded support sub-agents:
  - standard for large serious waves
  - gather context, inventories, matrices, and route maps
  - do not replace the main analyst’s synthesis

External gate reviewers

- Gemini is no longer a default blind-parallel main lane.
- Gemini and Claude are now gate-time reviewers for:
  - breadth checks
  - contradiction pressure
  - checklist or acceptance gates

Recommended artifact order

1. `mechanism_map`
2. `failure_taxonomy`
3. `eval_implications`
4. `variant_family_seeds`

Current completed state

- `mechanism_map` Wave 01 `exploratory_anchor`:
  - complete
  - legacy anchor only
- `mechanism_map` Wave 02 `execution_control_and_terminal_grounding`:
  - accepted with carry-forward warnings
- paper-text surface:
  - usable and no longer the main blocker

Wave-closure principle

- A strong wave file is not enough.
- A wave counts only when:
  - cross-lane synthesis exists
  - contradictions are explicit
  - coverage gaps are explicit
  - required support artifacts are updated
  - the principal states what the wave resolved and what remains open

Success criteria

- accepted `mechanism_map`
- accepted `failure_taxonomy`
- accepted `eval_implications`
- accepted `variant_family_seeds`
- reusable dossiers and case studies
- explicit coverage register
- honest carry-forward warnings and contradictions
- downstream handoffs strong enough for eval-suite design and variant-family design without guesswork
