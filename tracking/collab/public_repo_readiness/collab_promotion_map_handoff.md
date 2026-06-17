# Collab Promotion Map Handoff

- Status: `COMPLETE`
- Source thread: `019eb760-ea75-7af1-8d62-6e3e8cd7ba2a`
- Target thread: `019eb760-ea75-7af1-8d62-6e3e8cd7ba2a`
- Date: `2026-06-16`

## Objective And Scope

Create a practical public/private promotion map for the `tracking/collab`
corpus so future workers can tell what should be cloned or adapted into public
areas, what should stay linked as curated evidence, what needs redaction first,
and what must remain private.

Scope:

- add a public-safe promotion map under `docs/publication/`;
- wire the map into the publication navigation pages;
- keep the map conservative about raw trajectories, raw ledgers, hidden
  graders, official eval fixtures, and private/local paths;
- keep the handoff short and evidence-oriented.

Out of scope:

- runtime code changes;
- eval/full task runs;
- commits, branches, pushes, worktrees, VMs, or containers.

## Files Changed

- `docs/publication/collab_promotion_map.md`
- `docs/publication/README.md`
- `docs/publication/public_evidence_index.md`
- `docs/publication/publication_gap_list.md`
- `tracking/collab/public_repo_readiness/collab_promotion_map_handoff.md`

## Summary

Added a public-safe `tracking/collab` promotion map with five buckets:

- promote now by cloning/adapting;
- curate as public evidence link only;
- summarize/sanitize first;
- keep private/excluded;
- needs owner/legal/privacy review.

The map routes the clearest public-safe material into the existing public
homes:

- `workflows/skills/analyze-agent-runs.md` for the sanitized skill slice;
- `eval_suite/custom/`, `eval_suite/boards/`, and `eval_suite/scoreboards/`
  for the synthetic homolog family;
- `docs/case-studies/`, `docs/research/`, and `docs/provenance/` for the
  redacted synthesis material;
- `docs/publication/` for the publication-navigation layer.

The map also keeps the raw campaign archives private, especially the run
analysis bundles, execution-planning surfaces, calibration runs, hidden
verifier packs, and adapter fixtures that still need rights review.

## Validation

- Path/link existence check for the touched markdown files
  - result: `path-check-ok`
- `rg` sweeps over the touched docs for private paths, secrets-looking tokens,
  raw trajectory / ledger exposure, hidden grader / official eval leakage,
  stale MIT, and production-ready / eval-leadership overclaim
  - result: only expected negated/exclusionary references remained
- `git diff --check`
  - result: passed
- `python3 tools/aether2_genericity_check.py`
  - result: passed

## Review Findings And Dispositions

### Privacy Reviewer

- Finding: the promotion map could accidentally point at private raw runs or
  hidden grader material.
- Disposition: addressed by keeping the map at the region level and routing
  raw archives into private/excluded buckets.

### Publication Maintainer

- Finding: the public docs needed a single place to look up the `tracking/collab`
  split.
- Disposition: addressed by adding the new map and linking it from the
  publication navigation pages.

### Overclaim Skeptic

- Finding: the new map could have implied public readiness for raw run
  archives.
- Disposition: rejected; the map keeps those surfaces private and only routes
  redacted summaries into public docs.

## Remaining Gaps

- Export the sanitized case-study slice from `tracking/collab/stage_02_synthesis/`
  into `docs/case-studies/`.
- Export the board-level summaries from `tracking/collab/final_harness_eval_suite/`
  into `eval_suite/boards/` and `eval_suite/scoreboards/`.
- Sync the generic `analyze-agent-runs` skill into the public workflow surface.
- Keep adapter fixtures and other rights-sensitive assets private until their
  review gates are closed.

## External-State Confirmation

- No branch, commit, push, worktree, VM, container, or eval/full task run
  was created.
- No process or server was intentionally left active.

## RAW_LEDGER_UPDATE

- Persisted: yes
- Private raw historian input: recorded in the private ledger inbox

## Thread Send

- Target thread ID: `019eb760-ea75-7af1-8d62-6e3e8cd7ba2a`
- Tool/mechanism: `handoff artifact`
- Result: ready for orchestrator pickup
