# Literature Dossiers

This directory holds the structured Deep Synthesis literature layer.

The purpose is not to create one heavyweight dossier for every paper.
The purpose is to keep formal-source analysis deep enough to matter without turning 166 papers into administrative overhead.

## Dossier tiers

### 1. Anchor-paper dossiers

Use for papers or docs that are likely to be cited repeatedly by downstream Deep Synthesis artifacts.

Examples:

- benchmark-rigor anchors
- terminal-agent benchmark anchors
- memory/context eval anchors
- replay / verification anchors
- anti-cheat / integrity anchors

Recommended path:

- `tracking/collab/stage_02_synthesis/literature_dossiers/anchors/<topic>.md`

### 2. Theme dossiers

Use when several papers or docs are better understood as one cluster.

Examples:

- context and memory
- verification and replay
- eval methodology
- topology and orchestration
- tool use and tool contracts

Recommended path:

- `tracking/collab/stage_02_synthesis/literature_dossiers/themes/<topic>.md`

### 3. Corpus-level inventory only

Some papers should stay indexed and citable but do not need a full dossier yet.

That is acceptable when:

- the paper is narrow
- the claim is secondary
- the paper is overlapping with a stronger anchor source
- the paper is unlikely to shape variant or eval design directly

## Selection rules

Give a paper or doc an anchor dossier when it is:

- load-bearing for mechanism, failure, or eval reasoning
- repeatedly referenced by multiple downstream artifacts
- unusually strong or canonical for a research dimension
- likely to shape final writeup claims

Give a theme dossier when:

- multiple papers reinforce or contradict each other around one question
- no single paper should dominate the theme

## Default dossier structure

```text
LITERATURE_DOSSIER
- dossier_type: anchor | theme
- topic:
- scope:
- primary_sources:
- secondary_sources:
- coverage_used:
- coverage_not_yet_used:
- evidence_classes_touched:
- priority_sources_not_yet_read:
- formal_claims:
- benchmark_or_definition_notes:
- mechanism_relevance:
- failure_relevance:
- eval_relevance:
- contradictions:
- confidence_notes:
- open_questions:
- downstream_use:
```

## Operating rules

1. Formal literature does not outrank stronger behavior or source evidence.
2. A dossier should sharpen Deep Synthesis, not replace it.
3. Theme dossiers are preferred over one-paper-one-file sprawl.
4. Anchor dossiers should be created only when a source is truly load-bearing.

## Expected users

- literature/papers/docs analyst
- principal steward
- downstream `eval_implications` and `variant_family_seeds` artifacts
