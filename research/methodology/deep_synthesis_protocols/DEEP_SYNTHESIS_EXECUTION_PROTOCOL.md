# Deep Synthesis Execution Protocol

This protocol defines the human-run procedure for Deep Synthesis execution.

It is the governed operating procedure for:

- `mechanism_map`
- `failure_taxonomy`
- `eval_implications`
- `variant_family_seeds`

## Core rule

Deep Synthesis is not one shot.

Run it as:

1. packet approval
2. specialist preflight
3. first-pass analysis
4. contradiction review
5. principal synthesis
6. carry-forward handoff
7. checklist adjudication

## Checklist anchors

- master:
  - `tracking/collab/stage_02_synthesis/adjudication/DEEP_SYNTHESIS_V1_AUDIT_CHECKLIST.md`
- wave:
  - `tracking/collab/stage_02_synthesis/adjudication/DEEP_SYNTHESIS_WAVE_AUDIT_CHECKLIST.md`
- artifact:
  - `tracking/collab/stage_02_synthesis/adjudication/MECHANISM_MAP_AUDIT_CHECKLIST.md`
  - `tracking/collab/stage_02_synthesis/adjudication/FAILURE_TAXONOMY_AUDIT_CHECKLIST.md`

Use these as adjudication gates, not producer prompts.

## Wave budget

The minimum execution unit is one governed wave.

The binding stage model now uses:

- `14` core waves
- continuous support tracks underneath them

Core waves should not be multiplied casually.
Depth should come from support artifacts and bounded support sub-agents, not from endless new core waves.

## Model defaults

Stable principal:

- principal steward / final synthesis:
  - `GPT-5.4 xhigh`

Serious-wave main lanes:

- trajectory/failure analyst:
  - `GPT-5.4 xhigh`
- codebase/source-reconstruction analyst:
  - `GPT-5.3 Codex xhigh`
- literature/papers/docs analyst:
  - `GPT-5.4 xhigh`
- informal/issues/postmortems analyst:
  - `GPT-5.4 xhigh`
- eval/benchmark analyst:
  - `GPT-5.4 xhigh`
  - activate only when the packet says verifier, grader, replay, or benchmark logic is load-bearing

Gate roles:

- contradiction analyst:
  - `GPT-5.4 xhigh`
- checklist adjudicator:
  - `GPT-5.4 xhigh`

Support-sub-agent defaults:

- code-heavy bounded support:
  - `GPT-5.3 Codex high`
- inventory, grouping, matrices, and route maps:
  - `GPT-5.4-mini high`

External gate reviewers:

- `Gemini 3.1 Pro`
  - breadth or long-context gate review
- `Claude Opus 4.6`
  - adversarial contradiction or acceptance gate

Gemini rule:

- Gemini is not a default canonical main lane in the upgraded model.
- Use Gemini at gates or as targeted external review, not as routine parallel first-pass execution.

## Output naming for gate reviews

Do not overwrite the primary GPT outputs.

Use suffixed files such as:

- `contradiction_analyst__gemini.md`
- `contradiction_analyst__opus.md`
- `checklist_adjudicator__gemini.md`
- `checklist_adjudicator__opus.md`

These are governed gate artifacts, not replacement primary files.

## Phase 0: Packet review

Before launching specialists:

1. Read the active wave `brief.md`.
2. Read the active artifact `brief.md`.
3. Confirm the output paths.
4. Confirm whether the wave is a serious mechanism/failure wave, eval wave, or variant wave.
5. Confirm which support tracks the wave depends on.
6. Confirm which dossiers or case studies the wave must update.
7. Confirm whether the optional `eval/benchmark` fifth lane is activated.

## Phase 1: Specialist preflight

Every main analyst must start with:

- `preflight_scope_confirmed`
- `preflight_planned_read_order`
- `preflight_critical_sources_selected`
- `preflight_coverage_risks`
- `preflight_likely_blind_spots`
- `preflight_blockers`

If blockers are structural, stop and return control to the principal.

## Phase 2: First-pass analysis

### For serious `mechanism_map` and `failure_taxonomy` waves

Run independently:

- trajectory/failure analyst
- codebase/source-reconstruction analyst
- literature/papers/docs analyst
- informal/issues/postmortems analyst

Run optional fifth main lane:

- eval/benchmark analyst

Serious-wave rule:

- trajectory/failure is the primary empirical anchor
- source is the primary implementation anchor
- formal and informal lanes remain separate
- support artifacts are standard infrastructure, not a special exception

Support-sub-agent rule:

- main analysts may launch bounded support sub-agents for:
  - inventories
  - matrices
  - archive triage
  - subsystem mapping
  - grouping and clustering
  - source-link gathering
- support outputs must be saved explicitly
- support outputs do not count as final promoted claims on their own

### For `eval_implications`

Run role-sequenced:

- proposer
- critic
- falsifier
- breadth checker
- principal synthesis

### For `variant_family_seeds`

Run hybrid:

1. seed proposals
2. pruning critic
3. contradiction review
4. principal synthesis

## Partial failure rule

If fewer than `N-1` of `N` required main lanes complete with non-blocked outputs, stop and return control to the principal.

If exactly one required main lane fails but the packet can still be covered honestly, the principal must justify why before contradiction review.

## Phase 3: Contradiction review

After first-pass outputs exist:

1. give the contradiction analyst:
   - the active packet
   - all main outputs
   - any material follow-up outputs
2. require one explicit verdict:
   - `pass`
   - `pass_with_warnings`
   - `blocked`

If `blocked`, do not move to principal synthesis.

If `pass_with_warnings`, the principal must either:

1. resolve the warning
2. carry it forward explicitly
3. schedule a governed repair

Optional gate-time Gemini or Claude contradiction passes may run here, but they do not replace the primary contradiction file.

## Phase 4: Principal synthesis

The principal should:

1. read all main outputs
2. read any material follow-up outputs
3. read contradiction output
4. preserve disagreement and uncertainty
5. emit wave synthesis
6. update:
   - `cumulative_synthesis.md`
   - `coverage_register/current_status.md`
7. request or emit downstream handoff only when the artifact is actually ready

## Phase 5: Carry-forward handoff

When an artifact is actually ready:

1. create a structured handoff using:
   - `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_HANDOFF_SCHEMA.md`
2. link it from the downstream artifact packet

## Phase 6: Checklist adjudication

After principal synthesis:

1. run a checklist adjudicator
2. provide:
   - the active packet
   - main outputs
   - contradiction output
   - principal synthesis
   - the relevant checklist surfaces
3. require one explicit verdict:
   - `pass`
   - `pass_with_warnings`
   - `blocked`

Optional Gemini or Claude gate checks may run here as external second opinions.

## Support-track rule

`coverage_access` is a continuous support track, not a serial core-wave blocker.

- incomplete support work weakens confidence
- incomplete support work must stay visible in the coverage register
- incomplete support work does not automatically block a serious wave that can proceed honestly

## Coverage-register rule

After every accepted serious wave, update:

- `tracking/collab/stage_02_synthesis/coverage_register/current_status.md`

Do not claim deep coverage without updating the register.
