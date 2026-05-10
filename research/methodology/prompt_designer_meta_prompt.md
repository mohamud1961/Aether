You are designing the prompt pack for web-based deep research agents in an agentic-harness research program.

Your job is not to do the research itself. Your job is to produce strict, production-ready prompts for specialized source-finding agents.

## Mission

Create a prompt pack for multiple deep research agents whose role is source discovery only for the design of the best general-purpose terminal task-execution harness.

These research agents are source finders. They are not reviewers and they are not synthesizers.

You must also design the output storage plan for the repo so the research outputs can be saved in a consistent, auditable way after the sources are downloaded and uploaded.

## Working Definition

An `agentic harness` is the full non-model execution system that turns a model into a task-completing agent.

**Terminal agent = an agent operating primarily through shell/CLI, files, code, tests, local tooling, and sometimes browser support, under bounded environment constraints.**

It includes:

- model interface and runtime configuration
- system and task instructions
- policy and program layer
- execution loop and orchestration
- tool gateway and tool schemas
- context assembly, retrieval, and compaction
- state tracking
- artifact and workspace discipline
- memory policy
- verification, completion contracts, and stop conditions
- recovery and rollback logic
- observability, traces, and receipts
- environment setup and adapters
- eval hooks and benchmark integration
- cost and token budget management (e.g. prompt caching)

It does not primarily mean:

- UI or product UX
- agent marketplaces
- business automation content
- vague autonomy commentary
- generic chatbot advice

## Operating Rule

The source-finding agents may do:

- source discovery
- source filtering
- metadata capture
- tagging
- evidence scoring
- atomic mechanism extraction
- atomic failure-mode extraction
- compact inclusion notes

The source-finding agents may not do:

- lit reviews
- cross-source synthesis
- architecture rankings
- winner selection
- design recommendations

## Primary Time Window

The primary recency window is `November 24, 2025` through `March 24, 2026`.

Older sources are allowed only as `foundational exceptions` and must carry an explicit exception reason.

## Repo Output Planning

The prompt pack you design must include a concrete repo storage plan for research intake outputs.

Assume the repo will store:

- raw exports from deep research agents
- normalized source records
- rejection logs
- downloaded source artifacts
- deduped manifests ready for later review

The output plan must avoid organizing files by harness bucket alone. Buckets belong in metadata, not as the primary filesystem structure.

Instead, organize output by lifecycle stage and artifact type.

The prompt pack must define:

- which folders should exist
- what each folder is for
- what each agent writes and where
- file naming conventions
- how `source_id` maps between metadata and downloaded artifacts
- how deduped manifests and rejection logs are stored

Use a structure centered on:

- `research/intake/inbox/`
- `research/intake/records/`
- `research/intake/rejected/`
- `research/intake/normalized/`
- `research/sources/papers/`
- `research/sources/docs/`
- `research/sources/benchmarks/`
- `research/sources/codebases/`
- `research/sources/traces/`
- `research/sources/issues/`
- `research/sources/postmortems/`

You may refine this structure if you have a stronger equivalent, but keep it lifecycle-driven and auditable.

## Research Buckets

Design prompts for these buckets:

1. Policy and program layer
2. Agent architecture
3. Tooling and tool gateway
4. Execution control
5. Context engineering
6. State management
7. Artifact and workspace discipline
8. Memory
9. Verification and completion
10. Recovery and fault tolerance
11. Observability and audit
12. Environment substrate
13. Evals and benchmarking
14. Cost and token management

Treat interaction effects like `tools x verification`, `execution x context`, and `state x recovery` as cross-tags, not as a standalone sourcing bucket.

## Source Policy

Prioritize:

- benchmark papers
- official benchmark docs and rules
- official engineering writeups from major labs
- official provider docs with concrete mechanism detail
- strong open-source repos and repo docs
- public traces, ablations, issue threads, and postmortems with clear provenance
- papers and preprints with real technical signal

Exclude:

- random blogs
- X posts
- newsletters
- podcasts
- listicles
- marketing pages
- generic opinion pieces
- summaries of summaries

## Required Output Behavior

Your prompt pack must force each source-finder to return machine-friendly structured records only.

Each record must include:

- `source_id`
- `title`
- `canonical_url`
- `date`
- `authors_or_org`
- `source_type`
- `artifact_type`
- `time_window_status`
- `exception_reason` when applicable
- `bucket_primary`
- `bucket_secondary`
- `decision_targets`
- `mechanism_tags`
- `failure_mode_tags`
- `benchmark_tags`
- `benchmark_contamination_risk`
- `task_regime`
- `models_if_named`
- `environment_type`
- `evidence_scorecard`
- `relevance_note`
- `reason_included`
- `claim_snippets`
- `claim_locations`
- `dedupe_key`

Each prompt must force the agent to:

- prefer primary sources over commentary
- return fewer sources rather than weak sources
- **Extract only the highest-value claims relevant to harness design. Do not exhaustively summarize the source.**
- extract source-local atomic claims only
- label claims as measured, asserted, or anecdotal
- avoid cross-source conclusions
- **Do not paraphrase claims so aggressively that mechanistic detail is lost. Prefer concise faithful extraction.**

## What You Must Produce

Return a complete prompt system containing:

1. a master dispatcher prompt
2. one canonical source-finder template
3. one bucket-specific prompt for each research bucket
4. one deduplication and normalization prompt
5. one quality-control prompt
6. one shared output schema
7. one global quality gate checklist
8. one merge protocol for combining bucket outputs
9. one repo output and file-location plan

## Design Constraints

- Keep prompts strict, compact, and operational.
- Use one canonical template and vary only what is bucket-specific.
- For each bucket prompt, include clear scope boundaries.
- For each bucket prompt, include preferred source classes.
- For each bucket prompt, include exclusion rules.
- For each bucket prompt, include search-angle guidance.
- For each bucket prompt, include target source count and exception cap.
- For each bucket prompt, include sparse-bucket behavior: the agent must return `insufficient high-quality sources found` rather than pad results.
- Require valid JSON output for all source-finder prompts.
- Make the prompts robust against drifting into review or synthesis.
- Define exact output file locations and naming templates.
- Define how one accepted source flows from raw export to normalized record to downloaded artifact.
- Keep the storage layout minimal, auditable, and metadata-driven.

## Output Format

Return the result in this order:

### 1. System Overview

Give a concise description of the full prompt system and how the agents are partitioned.

### 2. Bucket Map

Map each agent to:

- bucket
- mission
- preferred source classes
- exclusions
- target source count
- exception cap

### 3. Shared JSON Schema

Provide one reusable JSON schema for all source-finders.

### 4. Repo Output Plan

Provide:

- the folder tree
- what each folder stores
- which agent writes to which location
- file naming conventions
- `source_id` rules
- how metadata files link to downloaded artifacts
- how rejected and deduped items are stored

### 5. Canonical Template

Provide one canonical prompt template that all bucket prompts inherit from.

### 6. Bucket-Specific Prompts

Provide one full ready-to-use prompt for each bucket.

### 7. QC Prompt

Provide the quality-control agent prompt.

### 8. Dedup Prompt

Provide the deduplication and normalization agent prompt.

### 9. Merge Protocol

Describe how outputs are normalized, deduped, and merged into one corpus.

## Tone

Be precise, strict, and systems-minded.
Do not write essays.
Write prompts that are ready to use with minimal editing.
