# Evidence Inventory Decision

Status: complete, awaiting human approval for Deep Synthesis activation

Opened: 2026-03-31

Artifact

- `evidence_inventory`

Goal

- Build the evidence inventory to a level that is actually usable for deep synthesis, not only good enough to close scope.

Why this is first

- `SYNTHESIS_PREP_CHECKLIST.md` makes evidence inventory the first recommended deliverable.
- The current repo state is broad and rich, but deep synthesis should not begin until one artifact explains how the full frozen corpus is organized and routed.
- `tracking/collab/stage_02_synthesis/red_team_review/outputs/red_team_review_adjudicated.md` identifies the missing organizer as the clearest remaining Stage 2A blocker.
- `tracking/collab/stage_02_synthesis/evidence_inventory/outputs/organizer.md` fixed that scope-routing blocker, and the rerun `tracking/collab/stage_02_synthesis/evidence_inventory/outputs/red_team.md` now returns `pass_with_warnings` instead of `blocked`.

Collaboration mode

- Stage 2A work on this artifact is complete.
- The next recommended artifact uses blind parallel first-pass extraction, then contradiction review, then principal synthesis.

External-agent call

- Run external agent now: no.
- Reason: opening Deep Synthesis is a major stage transition and requires human owner approval first.
- If approved:
  - Agent: mechanism-map synthesis cell
  - Why now: Stage 2A prep is complete and the evidence base is now structured enough for multi-agent deep synthesis.
  - Expected output path: `tracking/collab/stage_02_synthesis/mechanism_map/outputs/`

Specialist decision

- Do not run more synthesis-prep specialists on `evidence_inventory`.
- Recommended next deep-synthesis specialists after approval:
  - trajectory/failure analyst
  - codebase/source-reconstruction analyst
  - eval/benchmark analyst
  - literature/papers/docs analyst
  - informal/issues/postmortems analyst
  - contradiction analyst
- Reason: the prep artifact now supports multi-agent mechanism extraction without reopening corpus scope.

Principal judgment on current outputs

- Accept the organizer’s scope-routing boundary as correct and useful.
- Accept the rerun red-team judgment that the artifact now passes with warnings rather than remaining blocked.
- Carry the warnings forward as operating rules:
  - stay on `corpus__captured_for_synthetic_prep.json`
  - treat first-wave matrices as routing scaffolds, not exhaustive corpus indexes
  - confirm placeholder matrix tags against underlying artifacts during deep synthesis
- The project is now ready for a human-approved move into Deep Synthesis.

Informal-source policy

- Informal sources stay in scope for this artifact.
- They must be inventoried and labeled separately, not filtered out for being informal.
- They can influence prioritization, contradictions, and open-question framing, but they must not be silently upgraded to the same confidence level as stronger evidence classes.

Expected outputs

- `outputs/organizer.md`
- `outputs/red_team.md`
- explicit full-corpus map
- prioritized trajectory list
- prioritized codebase list
- prioritized eval-repo list
- `lego_dimensions` mapping
- run-level trajectory matrix
- subsystem-level codebase/eval matrix
- individually indexed benchmark captures and standalone code captures
- explicit informal-signal notes
- stale or superseded prep artifacts called out explicitly
- explicit malformed-or-missing evidence notes
- recommended first case studies
- first deep-synthesis priorities
- explicit judgment on whether synthesis prep is complete after the repair pass or needs one more prep artifact

Approval boundary

- No human approval is needed to accept this completed Stage 2A artifact.
- Human approval is needed before a formal move from research closeout into full Deep Synthesis.

Prep completion judgment

- The current `organizer.md` plus rerun `red_team.md` complete synthesis prep for the `evidence_inventory` artifact.
- Remaining concerns are warnings and operating rules, not blockers.
- Deep Synthesis should not open automatically; it now awaits human approval.

Stale-or-superseded artifacts to call out in organizer

- `tracking/collab/stage_02_synthesis/eval_inventory/outputs/eval_inventory.md` should be treated as superseded by `eval_metadata_repair.md` plus the repaired manifests for first-wave routing.
- `research/intake/rejected/2026-04-01__current_blocked_accepted_sources.json` should be treated as stale and non-authoritative relative to `accepted_blocked_exceptions.json` plus `corpus__captured_for_synthetic_prep.json`.

Next move

- Review `tracking/collab/stage_02_synthesis/deep_synthesis_plan/synthesis/principal_synthesis.md`.
- Ask the human owner to approve the formal move into Deep Synthesis under that plan.
- If approved, open `mechanism_map` first.
- Keep `failure_taxonomy` queued immediately after the first mechanism pass.

Next artifact after completion

- Recommended first deep-synthesis artifact: `mechanism_map`
- Recommended second artifact: `failure_taxonomy`
