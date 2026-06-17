# Mechanism Map Wave 01 Exploratory Anchor Operator Guide

Date: 2026-04-04

This guide applies to the legacy exploratory-anchor closeout for:

- `tracking/collab/stage_02_synthesis/mechanism_map/`

It is not a completion guide for the full `mechanism_map` artifact.

## What this run is

- Wave label:
  - `wave_01_exploratory_anchor`
- Status:
  - first-pass outputs completed
  - Gemini blind-parallel outputs completed
  - contradiction review, principal synthesis, checklist adjudication, and historical preservation required
- Governance rule:
  - do not treat this wave as `mechanism_map` completion
  - do not open new `mechanism_map` waves yet
  - open `coverage_access` next after this wave is closed cleanly

## Governing files

- Active artifact packet:
  - `tracking/collab/stage_02_synthesis/mechanism_map/brief.md`
- Active artifact decision:
  - `tracking/collab/stage_02_synthesis/mechanism_map/decision.md`
- Legacy launch note:
  - `tracking/collab/stage_02_synthesis/mechanism_map/inputs/wave_01_launch.md`
- Execution protocol:
  - `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_EXECUTION_PROTOCOL.md`
- Binding wave plan:
  - `tracking/collab/stage_02_synthesis/deep_synthesis_wave_plan/synthesis/principal_synthesis.md`
- Wave audit checklist:
  - `tracking/collab/stage_02_synthesis/adjudication/DEEP_SYNTHESIS_WAVE_AUDIT_CHECKLIST.md`

## First-pass role outputs already present

Unsuffixed primary outputs:

- `tracking/collab/stage_02_synthesis/mechanism_map/outputs/trajectory_failure_analyst.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/outputs/codebase_source_reconstruction_analyst.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/outputs/literature_papers_docs_analyst.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/outputs/informal_issues_postmortems_analyst.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/outputs/eval_benchmark_analyst.md`

Gemini blind-parallel outputs:

- `tracking/collab/stage_02_synthesis/mechanism_map/outputs/trajectory_failure_analyst__gemini.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/outputs/codebase_source_reconstruction_analyst__gemini.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/outputs/literature_papers_docs_analyst__gemini.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/outputs/informal_issues_postmortems_analyst__gemini.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/outputs/eval_benchmark_analyst__gemini.md`

Status note:

- Gemini is a first-class blind-parallel repo agent under the same packet and review rules as GPT.
- The `__gemini.md` suffix is for lineage and conflict-free storage, not lower status.

## Required closeout order

1. Confirm the ten first-pass files above exist.
2. Run or review contradiction closeout at:
   - `tracking/collab/stage_02_synthesis/mechanism_map/outputs/contradiction_analyst.md`
3. Produce principal synthesis and cumulative artifact state:
   - `tracking/collab/stage_02_synthesis/mechanism_map/synthesis/principal_synthesis.md`
   - `tracking/collab/stage_02_synthesis/mechanism_map/synthesis/accepted_claims.md`
   - `tracking/collab/stage_02_synthesis/mechanism_map/synthesis/contradiction_register.md`
   - `tracking/collab/stage_02_synthesis/mechanism_map/synthesis/coverage_frontier.md`
   - `tracking/collab/stage_02_synthesis/mechanism_map/synthesis/open_questions.md`
4. Run wave audit / checklist adjudication at:
   - `tracking/collab/stage_02_synthesis/mechanism_map/outputs/checklist_adjudicator.md`
5. Preserve the wave under:
   - `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_01_exploratory_anchor/`
6. Open `coverage_access`.

## Non-negotiable rules

1. Do not overwrite unsuffixed GPT outputs with model-suffixed outputs.
2. Do not flatten contradictions away just because multiple lanes converge on the same story.
3. Keep BigAI implementation claims labeled as `behavioral reconstruction` unless there is actual source.
4. Keep paper-content coverage explicitly weak until the paper-text access surface exists.
5. Do not emit `handoff_to_failure_taxonomy.md` from this wave. The artifact is not complete yet.
6. Do not treat this wave as `mechanism_map` completion under any operator summary.

## Expected verdict shape

The clean-closeout target for this wave is:

- contradiction review:
  - `pass_with_warnings`
- wave audit:
  - `pass_with_warnings`

That verdict means:

- preserve the wave as legacy exploratory anchor history
- keep cumulative claims and contradictions visible
- move to `coverage_access`
- do not reopen `mechanism_map` yet
