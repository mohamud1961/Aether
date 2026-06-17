# Repo Map Worker C: Workflows, Skills, Prompts, and Orchestration

Status: sanitized publication-planning summary

This note keeps the original workflow-mapping conclusions while stripping
machine-local links and direct pointers into private execution surfaces. It is
guidance for publication curation, not itself a public docs index.

## Executive Summary

The repository has strong raw materials for a public workflow layer, but they
still span three different classes of surface:

- human-readable governance and operating-model docs at the repo root;
- model-facing prompt packs and internal operator notes;
- collaboration, run-analysis, and eval artifacts under `tracking/collab/`.

Recommended split:

- publish sanitized workflow docs under `workflows/` and `docs/`;
- publish generic schemas and templates under `docs/schemas/`;
- keep reusable public skill material narrow and explicit;
- keep live collaboration folders, raw run artifacts, raw ledger inputs, and
  hidden/private eval material out of the publication set.

The strongest reviewer and hiring evidence is the eval/task-pack discipline and
the governed handoff structure, not the raw internal planning folders.

## Inventory Summary

| Surface | Current class | Public recommendation | Notes |
|---|---|---|---|
| `tracking/collab/skills/analyze-agent-runs/` | reusable skill candidate | publish a sanitized public counterpart | good public pattern once repo-path assumptions are removed |
| root governance docs such as `AGENTS.md`, `GOVERNED_MULTI_AGENT_OPERATING_MODEL.md`, and `PRINCIPAL_AGENT_WORKFLOW.md` | mixed public/private | publish only sanitized workflow derivatives | keep evidence-first rules; remove current-stage and infrastructure-specific details |
| `prompts/` | internal operator material | selective publication only after sanitization | useful patterns exist, but current copies are repo-specific and path-heavy |
| schema/template docs such as `FAILURE_CARD_SCHEMA.md`, `MECHANISM_CARD_SCHEMA.md`, `TRAJECTORY_SOURCE_CASE_STUDY_TEMPLATE.md`, `VARIANT_FAMILY_SEED_SCHEMA.md`, and `tracking/collab/TASK_PACKET_TEMPLATE.md` | near-public | publish after light cleanup | strong public evidence of process rigor |
| case-study and eval-blueprint inputs such as `tracking/collab/*run_analysis*` and `tracking/collab/final_harness_eval_suite/task*` | source material for public narratives | summarize into curated docs | public value comes from distilled lessons, not raw internal scaffolding |
| live collaboration folders such as `tracking/collab/stage_02_synthesis/` and orchestration/run folders | private working surface | keep private | these encode current campaign state and raw evidence relationships |
| raw run folders and hidden-eval material under `tracking/collab/**/runs/` | private evidence | keep private | not safe as direct publication artifacts |
| ledger inbox and git-handoff state | private historian/ops surface | keep private | publication should reference summaries, not raw intake |

## Public / Private Boundary

Safe to publish after routine wording cleanup:

- curated workflow guides in `workflows/`;
- public architecture, provenance, and publication notes in `docs/`;
- deterministic public eval-smoke packs and example boards/scoreboards in
  `eval_suite/`;
- sanitized handoffs that explain scope, validation, and remaining gaps
  without exposing private raw evidence locations.

Keep private or summarize instead of staging verbatim:

- live collaboration workspaces under `tracking/collab/` that capture active
  run analysis, internal planning, or review state;
- raw run rows, traces, workspaces, hidden truth, and repair artifacts;
- raw historian inbox files and any pointer set that effectively indexes them;
- operator-only prompt packs that still encode repo-local workflow machinery.

## Publication Recommendations

1. Treat `tracking/collab/` as the private execution surface by default.
2. Publish workflow method through the existing `workflows/` and `docs/`
   surfaces, not by promoting raw collaboration folders.
3. Translate the best internal materials into curated case studies, workflow
   guides, and schema references.
4. Keep eval credibility visible through task-pack contracts, boards,
   scoreboards, and bounded handoffs rather than through raw run dumps.
5. Preserve explicit privacy boundaries around ledger intake, private archives,
   hidden graders, and official eval internals.

## Open Questions

1. Should the public repo expose compatibility shims like `CLAUDE.md` or
   `CODEX.md`, or keep a single sanitized workflow entrypoint?
2. How much of the internal run-analysis material should become curated case
   studies versus stay private source material?
3. Should the strongest public eval evidence live mostly in `eval_suite/`,
   mostly in `docs/case-studies/`, or in both with different levels of detail?
