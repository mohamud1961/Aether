# Deep Synthesis Multi-Agent Workflow Guide

Use this guide with:

- `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_EXECUTION_PROTOCOL.md`
- `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_PHASE_AND_WAVE_OPERATING_PLAN.md`
- the active artifact and wave packet
- the role prompts under `prompts/`

This guide locks the practical operating rules for fresh-agent execution, support-sub-agent use, follow-ups, wave closeout, and stage-exit readiness.

## 1. Canonical agent model

For serious `mechanism_map` and `failure_taxonomy` waves:

- use one stable principal agent
- use fresh separate main agents for:
  - `trajectory/failure`
  - `codebase/source reconstruction`
  - `literature/papers/docs`
  - `informal/issues/postmortems`
- add `eval/benchmark` only when the wave really needs it
- use fresh contradiction and checklist agents after the main outputs exist

Do not use hidden principal-launched sub-agents as canonical first-pass evidence producers.

## 2. Bounded support-sub-agent rule

Support sub-agents are standard infrastructure for heavy waves.

Use them for:

- inventories
- matrices
- archive triage
- subsystem mapping
- paper grouping
- issue clustering
- source-link gathering

Rules:

- the main analyst owns the lane
- support sub-agents do bounded tasks only
- support outputs must be saved explicitly
- the main analyst must cite those support outputs
- support outputs do not count as final claims by themselves

## 3. What every fresh main agent receives

Every main agent should receive:

- `prompts/deep_synthesis_shared_policy_prompt.md`
- its role-specific prompt
- the active artifact `brief.md`
- the active wave `brief.md`
- `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_EXECUTION_PROTOCOL.md`
- `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_PHASE_AND_WAVE_OPERATING_PLAN.md`
- the exact output path

When relevant, also pass:

- support-artifact paths the wave depends on
- prior accepted wave synthesis
- `cumulative_synthesis.md`
- `coverage_register/current_status.md`

## 4. First-pass immutability

First-pass outputs are immutable historical records.

If follow-up is needed:

- do not overwrite the first-pass file
- write:
  - `__followup_01`
  - `__followup_02`
  - `__revision_01`

Use `followup` for extra depth.
Use `revision` only for a true correction or materially changed view.

## 5. Lane completion rule

No lane is complete just because:

- a file exists
- a file is long
- some cross-source reasoning appears

A lane is only wave-sufficient when:

- the principal says so explicitly
- the lane meets the relevant closure criteria
- required support artifacts for that lane exist for the active domain

Use:

- `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_LANE_CLOSURE_CRITERIA.md`

## 6. Serious-wave launch checklist

Before launching a serious wave:

1. confirm the wave is a vertical domain wave
2. confirm the 4 main lanes
3. confirm whether `eval/benchmark` is activated
4. confirm the output paths
5. confirm the contradiction path
6. confirm the wave synthesis path
7. confirm `cumulative_synthesis.md`
8. confirm `coverage_register/current_status.md`
9. confirm which support tracks and dossier artifacts the wave depends on
10. confirm what the wave is allowed to leave unfinished

## 7. Standard support-task patterns

Trajectory lane:

- run inventory
- shared-task matrices
- pass/fail matrices
- failure-point extraction
- source-link gathering

Source lane:

- subsystem maps
- file discovery
- archive triage
- family clustering

Formal lane:

- paper grouping
- theme grouping
- quality triage

Informal lane:

- issue clustering
- postmortem grouping
- contradiction clustering

Eval lane:

- benchmark routing
- verifier or grader extraction
- replay surface extraction

## 8. Support-track dependency rule

Every serious wave packet should say:

- which support tracks it depends on
- which dossiers it must update
- which coverage-register entries it is expected to change

Waves must not treat support tracks as side junk.

## 9. Long-tail rule

Every serious wave should include:

- at least one shared or anchor slice
- at least one long-tail, failure-heavy, or regime-stressing slice

## 10. Local harness implications rule

Every wave-level principal synthesis should include:

- `local_harness_implications`

That section should say what the wave implies for:

- `blocks/`
- `runner/`
- `evals/`

## 11. External gate-review rule

Gemini and Claude are now gate-time reviewers, not default parallel main lanes.

Use them for:

- breadth checks
- contradiction pressure
- acceptance pressure

Do not silently replace the primary GPT wave outputs with them.

## 12. Wave close rule

A wave may close only if:

- cross-lane synthesis is real
- contradictions are explicit
- `coverage_not_yet_used` is honest
- required support artifacts were updated or explicitly deferred
- the principal can say what the wave resolved
- the principal can say what remains open

## 13. Stage-exit package

Deep Synthesis should not exit with just prose.

It should exit with:

- accepted `mechanism_map`
- accepted `failure_taxonomy`
- accepted `eval_implications`
- accepted `variant_family_seeds`
- `coverage_register/current_status.md`
- reusable dossiers and case studies
- explicit carry-forward warnings
- explicit contradictions
