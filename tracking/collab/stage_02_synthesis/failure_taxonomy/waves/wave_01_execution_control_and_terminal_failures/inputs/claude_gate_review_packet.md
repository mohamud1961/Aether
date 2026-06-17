# Failure Taxonomy Wave 01 Claude Gate Review Packet

Use this packet only for external Claude gate review.

Claude is not a primary Wave 01 main lane.

## Recommended timing

Default:

- contradiction gate stage

Optional:

- checklist stage if acceptance still looks fragile

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

- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/outputs/contradiction_analyst__claude.md`

For checklist-stage gate review:

- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/adjudication/checklist_adjudicator__claude.md`

## Exact Wave 01 gate task

Provide adversarial contradiction and acceptance pressure on:

- unsupported failure attribution
- over-attribution to one cause family
- weak execution-control evidence
- weak false-success/verifier-blindness evidence
- warning suppression during acceptance

## Blocker vs carry-forward warning

Use blocker when acceptance would create a materially misleading state.

Use `pass_with_warnings` when useful attribution exists but mixed-cause uncertainty remains.

## Explicit distinction to enforce

- Wave acceptance is not artifact completion.
- Claude output is a gate opinion, not the canonical contradiction/checklist file.
- Do not collapse model, harness, environment, and benchmark-blindness into one cause when evidence is mixed.

