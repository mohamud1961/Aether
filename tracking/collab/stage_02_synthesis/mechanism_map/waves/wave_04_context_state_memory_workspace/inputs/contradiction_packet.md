# Wave 04 Contradiction Packet

Use this packet for the Wave 04 primary GPT contradiction review.

Paste together:

1. `prompts/deep_synthesis_shared_policy_prompt.md`
2. `prompts/deep_synthesis_contradiction_analyst_prompt.md`
3. this file

## Exact role

- `contradiction analyst`

## Read these files

Read first:

1. `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/brief.md`
2. `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_EXECUTION_PROTOCOL.md`
3. `tracking/collab/stage_02_synthesis/DEEP_SYNTHESIS_LANE_CLOSURE_CRITERIA.md`
4. `tracking/collab/stage_02_synthesis/mechanism_map/synthesis/cumulative_synthesis.md`
5. `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_03_verification_completion_and_recovery/synthesis/principal_synthesis.md`
6. `tracking/collab/stage_02_synthesis/coverage_register/current_status.md`

Then read all current Wave 04 first-pass outputs:

- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/outputs/trajectory_failure_analyst.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/outputs/codebase_source_reconstruction_analyst.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/outputs/literature_papers_docs_analyst.md`
- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/outputs/informal_issues_postmortems_analyst.md`

Read any material support artifacts actually cited by those lane outputs.

## Exact output path

Write exactly here:

- `tracking/collab/stage_02_synthesis/mechanism_map/waves/wave_04_context_state_memory_workspace/outputs/contradiction_analyst.md`

## Exact Wave 04 attack surface

Attack these failure modes directly:

- fake “memory” families built from vague rhetoric
- unsupported long-term-memory claims
- workspace artifacts being misread as rich memory architecture
- source/trajectory mismatch on state persistence or compaction
- weak separation between context compaction, memory retrieval, state persistence, and workspace discipline
- BigAI being treated as source-backed rather than `behavioral reconstruction`
- restart or resumability being promoted beyond the current evidence
- organizer rhetoric outranking direct path accounting
- support artifacts being treated as if they were final claims
- stealth eval-lane reasoning even though eval is inactive

## Blocker vs carry-forward warning

Return `blocked` if:

- the wave’s promoted claims are structurally unsupported
- the main lanes did not actually synthesize the active domain
- core evidence classes required by the wave are missing
- BigAI, restart/resume, or workspace-memory distinctions are being overclaimed in a way that would mislead downstream synthesis

Return `pass_with_warnings` if:

- the wave resolves meaningful mechanism structure
- but some long-tail evidence, dossier depth, or contradiction pressure remains thin
- and those limits can be carried forward honestly without corrupting the artifact

Return `pass` only if:

- the wave is strong, reconciled, and the remaining uncertainty is minor rather than structural

## Explicit distinction you must preserve

- wave acceptance is not artifact completion
- accepted with warnings is still acceptable if the unresolved limits are explicit
- a strong wave may still leave `mechanism_map` globally incomplete

## Coverage and support checks

You must check:

- whether each lane used direct repo-local paths
- whether coverage reporting is real rather than rhetorical
- whether required support artifacts and required dossier updates were used honestly or explicitly deferred
- whether the coverage register state matches the actual wave state

## Carry-forward cautions you must enforce

- BigAI remains `behavioral reconstruction`
- restart and resumability remain under-evidenced
- organizer remains weaker than direct path accounting
- Wave 03 verification/recovery conclusions should constrain but not predetermine Wave 04
