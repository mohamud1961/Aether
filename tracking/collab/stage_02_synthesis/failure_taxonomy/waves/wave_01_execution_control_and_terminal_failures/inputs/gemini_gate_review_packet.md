# Failure Taxonomy Wave 01 Gemini Gate Review Packet

Use this packet only for external Gemini gate review.

Gemini is not a primary Wave 01 main lane.

## Recommended timing

Default:

- contradiction gate stage

Optional:

- checklist stage if breadth still looks thin

## Exact files to read

Read first:

1. `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/brief.md`
2. `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_PHASE_AND_WAVE_OPERATING_PLAN.md`
3. `tracking/collab/stage_02_synthesis/coverage_register/current_status.md`

Then read the active wave outputs at the stage where called:

- main lane outputs
- primary GPT contradiction output if available
- principal synthesis if checklist-stage gate review

## Exact output path

For contradiction-stage gate review:

- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/outputs/contradiction_analyst__gemini.md`

For checklist-stage gate review:

- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/adjudication/checklist_adjudicator__gemini.md`

## Exact Wave 01 gate task

Provide breadth and long-context pressure on:

- missed failure families
- missed mixed-cause confounders
- missed benchmark-blindness pressure
- stale coverage assumptions
- hidden scope drift from Wave 01 attribution question

## Blocker vs carry-forward warning

Use blocker only when breadth gaps are structural and acceptance would mislead.

Otherwise prefer `pass_with_warnings` with explicit missing path families.

## Explicit distinction to enforce

- Wave acceptance is not artifact completion.
- Gemini output is a gate opinion, not the canonical contradiction/checklist file.
- Do not collapse model, harness, environment, and benchmark-blindness into one cause when evidence is mixed.

