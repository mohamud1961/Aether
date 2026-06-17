# Evidence Inventory Principal Synthesis

Date: 2026-04-02

Artifact

- `evidence_inventory`

Current judgment

- Stage 2A synthesis prep is now complete for the `evidence_inventory` artifact.
- The repaired `outputs/organizer.md` plus the rerun `outputs/red_team.md` are sufficient to open deep synthesis, with warnings carried forward as operating rules rather than as prep blockers.

What the organizer solved

- It made the active first-wave evidence boundary explicit by routing deep synthesis through `research/intake/normalized/manifests/corpus__captured_for_synthetic_prep.json` and treating `research/intake/rejected/2026-04-01__accepted_blocked_exceptions.json` as metadata-only exclusions.
- It kept non-intake evidence classes in scope explicitly instead of leaving trajectories, informal notes, postmortems, mirrored codebases, and benchmark captures as hidden side channels.
- It correctly marked stale prep artifacts and superseded review drafts.

Accepted red-team findings

- The rerun review is right to keep three operating rules visible for deep synthesis:
  - stay on `research/intake/normalized/manifests/corpus__captured_for_synthetic_prep.json`
  - treat the matrices as routing scaffolds rather than as substitutes for underlying trajectory/code/eval reading
  - do not treat placeholder matrix tags such as `inspect`, `comparison-run`, or `unknown` as adjudicated findings
- The remaining warnings are acceptable for opening deep synthesis because they are about downstream discipline, not missing prep structure.

Rejected overreach

- There is no longer a reason to keep Stage 2A blocked on another organizer repair slice.
- The first-wave matrices are selective rather than exhaustive, but that is acceptable so long as later agents do not misread omission from the first-wave matrix as exclusion from the frozen corpus.

Decision

- Mark `evidence_inventory` complete.
- Recommend `mechanism_map` as the first deep-synthesis artifact.
- Do not silently open Deep Synthesis. Human owner approval is required for the stage transition before external deep-synthesis specialists are run.

Why `mechanism_map` first

- The repaired organizer now binds the corpus directly onto `research/analysis/lego_dimensions.md`, which makes mechanism extraction more grounded than it was before the repair.
- The codebase/eval matrix and case-study slate now expose mechanism-bearing evidence across terminal control, process control, stateful recovery, verification, and replay infrastructure.
- Opening `mechanism_map` first keeps the project aligned with the repo mission of swappable harness blocks instead of jumping straight into failure anecdotes without a stable mechanism spine.
- `failure_taxonomy` should open immediately after the first mechanism pass, using the same trajectory matrix and failure-heavy case slate.

Recommended deep-synthesis cell after approval

- Collaboration mode: blind parallel for first-pass extraction, then contradiction review, then principal synthesis.
- First-pass specialists:
  - trajectory/failure analyst
  - codebase/source-reconstruction analyst
  - eval/benchmark analyst
  - literature/papers/docs analyst
  - informal/issues/postmortems analyst
- Follow-on adversarial specialist:
  - contradiction analyst
- Expected artifact order:
  - `mechanism_map`
  - `failure_taxonomy`

Stage implication

- Stage 2A is complete.
- The next decision that matters is whether the human owner approves the formal move into Deep Synthesis.
- If approved, the project should open `mechanism_map` first and route it as a multi-agent blind-parallel artifact with adversarial review.
