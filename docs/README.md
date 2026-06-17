# Docs

Public documentation hub for the harness, research, eval surfaces, variant
surfaces, publication boundaries, and AI-native engineering workflow.

## Sections

- `architecture/` — live tree map, compatibility boundaries, and navigation
- `research/` — public research summaries and methodology notes
- `case-studies/` — redacted public case studies (harness engineering + variant design)
- `provenance/` — source and publication boundary guidance
- `publication/` — release and publication checks
- `schemas/` — public schema references and templates

## Public Repo Structure

- [Public reviewer guide](../PUBLIC_REVIEWER_GUIDE.md) — concise narrative for
  what shipped, how agents were used, and how they were kept honest.
- [Eval suite](../eval_suite/README.md) — custom evals by capability family and
  whole-harness surface, with boards and scoreboards.
- [Variants](../variants/README.md) — mechanism-family and whole-harness
  variants, with tournament records and scorecards where scored data exists.
- [Research index](../research/README.md) — deep synthesis, planning, reviews,
  analyses, mechanism maps, failure taxonomies, and run studies.
- [Workflow layer](../workflows/README.md) — loop engineering, skills,
  orchestration, reviews, run operations, hooks, and handoffs.

## Research and Synthesis

- [Research index](../research/README.md) — synthesis, case studies, phases, methodology
- [Failure taxonomy](../research/synthesis/failure-taxonomy.md) — 12+ failure families, 4 waves
- [Mechanism map](../research/synthesis/mechanism-map.md) — 6 mechanism families
- [Source system dossiers](../research/synthesis/source_system_dossiers/README.md) — BigAI, KIRA, deepagents, a-evolve, claw-code
- [Case studies index](../research/case_studies/README.md) — 10 trajectory case studies + 3 run analyses
- [Research docs](research/README.md)

## Architecture and Engineering

- [Public architecture](architecture/public-architecture.md)
- [AI-native engineering operating system](../workflows/ai-native-engineering-operating-system.md)
- [Workflow phases](../workflows/phases/README.md)
- [Workflow use cases](../workflows/use-cases/README.md)
- [Public evidence index](publication/public_evidence_index.md)
- [Publication gap list](publication/publication_gap_list.md)
- [Public readiness](publication/public_readiness.md)

## Aether Runtime Slices

The public evidence index also links Python-native Aether capability slices:
skills, MCP-style registry contracts, subagent handoffs, hooks, and permission
surfaces. They are presented as HarnessEng-native runtime interfaces with eval
coverage and explicit provenance boundaries.

## Case Studies

- [Aether runtime capability migration](case-studies/aether-runtime-capability-migration.md)
- [Public manifest repair smoke](case-studies/public-manifest-repair-smoke.md)
- [Attribution-guard tournament](case-studies/attribution-guard-tournament.md)

## Status

This is the public documentation hub, not the source of implementation logic.
