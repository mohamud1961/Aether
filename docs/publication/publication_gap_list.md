# Publication Gap List

Status: active public curation checklist

This list tracks the biggest remaining publication and privacy gaps for the
reviewer-facing repository surface.

## Resolved

- Runtime-source-study notice questions have been moved out of the reviewer
  path. The public capability story now points to owned Aether interfaces,
  smoke packs, and provenance policy rather than branded source-study handoffs.
- A compact public evidence index now exists at
  `docs/publication/public_evidence_index.md`, so reviewers do not need to
  browse the full tracking tree to find the cleanest public artifacts.
- A second public eval family now exists at
  `eval_suite/custom/homolog_contract_smoke/`, showing a sanitized
  cross-surface contract shape beyond the first manifest-repair smoke slice.
- A public keep/kill tournament summary now exists at
  `variants/families/attribution_guard_tournament/`, showing preregistered
  prediction, observed outcome, and non-promotion of the sentinel-failing
  target winner.
- A broader public variant map now exists across
  `variants/harness/`, `variants/kernel/`, `variants/aether/`, and
  `variants/shared/`, with structured scoreboards for whole-harness,
  control-plane, and Aether / loop summaries.
- A practical collab promotion map now exists at
  `docs/publication/collab_promotion_map.md`, so future public slices can be
  routed by region instead of rediscovering the split from scratch.
- A public eval map now exists across `eval_suite/families/`,
  `eval_suite/whole_harness/`, `eval_suite/calibration_lanes/`, and
  the promoted pressure-family surfaces, so the public eval surface is no
  longer just a pair of smoke-family examples.

## Priority 1

- Keep branded source-study handoff files out of the reviewer-facing path
  unless they are deliberately published as legal/provenance appendix material.
- Apply the collab promotion map when deciding whether a `tracking/collab`
  region should be cloned, linked, redacted, or kept private.
- Complete a direct audit of every public-facing doc and workflow page for
  accidental references to private traces, raw evidence ledgers, private
  verifiers, or private fixture materials.

## Priority 2

- Add more public case-study content that shows concrete engineering outcomes
  without leaking internal run history.
- Add another executable custom family if we want a third runnable family
  shape in addition to the smoke examples.
- Keep growing the public variant map only with sanitized summaries and
  calibrated claims, not with raw run histories or leadership-style claims
  about the public surface.
- Review all public handoff docs for claims that imply stronger usability,
  external-suite status, or implementation breadth than the tree currently
  supports.

## Priority 3

- Decide which internal workflow skills deserve sanitized public counterparts
  and which should remain tracking-only.
- Normalize case-study and workflow language so "draft", "planned", "stub",
  and "implemented" are used consistently.

## Explicitly Still Out Of Scope

- publishing raw traces or raw historian inbox files;
- redistributing private fixtures or private grader logic;
- claiming production-grade completeness, external-suite dominance, or fully
  finished end-user product packaging.
