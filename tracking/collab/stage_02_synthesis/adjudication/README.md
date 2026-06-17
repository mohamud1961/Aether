# Deep Synthesis Adjudication

This directory holds independent audit materials for Deep Synthesis.

Audit layers:

- master stage or stage-exit checklist:
  - `tracking/collab/stage_02_synthesis/adjudication/DEEP_SYNTHESIS_V1_AUDIT_CHECKLIST.md`
- per-wave checklist:
  - `tracking/collab/stage_02_synthesis/adjudication/DEEP_SYNTHESIS_WAVE_AUDIT_CHECKLIST.md`
- artifact-level checklists:
  - `tracking/collab/stage_02_synthesis/adjudication/MECHANISM_MAP_AUDIT_CHECKLIST.md`
  - `tracking/collab/stage_02_synthesis/adjudication/FAILURE_TAXONOMY_AUDIT_CHECKLIST.md`

Use these checklists as:

- independent post-synthesis adjudication gates
- pressure tests against fake coverage
- downstream-readiness reviews for completed artifacts
- compounding checks after accepted waves

Do not use them as:

- producer prompts for first-pass extraction
- a reason to invent certainty just to fill every field

Default adjudication output path per artifact:

- stage or artifact-level adjudication:
  - `tracking/collab/stage_02_synthesis/<artifact>/outputs/checklist_adjudicator.md`
- wave-level adjudication:
  - `tracking/collab/stage_02_synthesis/<artifact>/waves/wave_<nn>_<slug>/adjudication/checklist_adjudicator.md`
