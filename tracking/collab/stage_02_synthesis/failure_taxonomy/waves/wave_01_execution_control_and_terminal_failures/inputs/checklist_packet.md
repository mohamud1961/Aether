# Failure Taxonomy Wave 01 Checklist Packet

Use this packet for the primary GPT checklist adjudication in Wave 01.

Paste together:

1. `prompts/deep_synthesis_shared_policy_prompt.md`
2. `prompts/deep_synthesis_checklist_adjudicator_prompt.md`
3. this file

## Exact files to read

Read first:

1. `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/brief.md`
2. `tracking/collab/stage_02_synthesis/failure_taxonomy/brief.md`
3. `tracking/collab/stage_02_synthesis/failure_taxonomy/decision.md`
4. `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_EXECUTION_PROTOCOL.md`
5. `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_LANE_CLOSURE_CRITERIA.md`
6. `tracking/collab/stage_02_synthesis/adjudication/DEEP_SYNTHESIS_V1_AUDIT_CHECKLIST.md`
7. `tracking/collab/stage_02_synthesis/adjudication/DEEP_SYNTHESIS_WAVE_AUDIT_CHECKLIST.md`
8. `tracking/collab/stage_02_synthesis/adjudication/FAILURE_TAXONOMY_AUDIT_CHECKLIST.md`
9. `tracking/collab/stage_02_synthesis/coverage_register/current_status.md`

Then read:

- all primary Wave 01 lane outputs
- primary contradiction output
- Wave 01 principal synthesis
- support artifacts materially cited by the principal synthesis

## Exact output path

- `tracking/collab/stage_02_synthesis/failure_taxonomy/waves/wave_01_execution_control_and_terminal_failures/adjudication/checklist_adjudicator.md`

## Exact Wave 01 attack surface

Audit whether the wave:

- solved the execution-control and terminal-failure attribution question
- kept symptom-vs-cause distinction explicit
- avoided cause collapse across model/harness/environment/benchmark-blindness
- stayed honest about BigAI and mechanism-map carry-forward warnings
- kept eval inactive unless explicitly justified

## What is a blocker vs carry-forward warning

Return `blocked` if:

- acceptance would materially mislead downstream work
- attribution is weakly grounded or collapsed
- checklist compliance is mostly schema theater

Return `pass_with_warnings` if:

- wave is useful and governed
- explicit uncertainty and support-track debt remain

Return `pass` only if:

- attribution quality is strong enough for governed carry-forward

## Explicit distinction to enforce

- wave acceptance is not artifact completion
- passing checklist does not imply `failure_taxonomy` completion
- warnings may remain mandatory after pass

## First-pass immutability reminder

Do not overwrite first-pass files.

If repair is needed, require:

- `__followup_01`
- `__followup_02`
- `__revision_01`

## Explicit mixed-cause anti-collapse warning

Do not collapse model, harness, environment, and benchmark-blindness into one cause when evidence is mixed.

