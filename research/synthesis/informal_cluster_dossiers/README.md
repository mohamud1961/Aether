# Informal Cluster Dossiers

This directory holds structured dossiers for important informal, issue, and postmortem clusters.

The purpose is to stop Deep Synthesis from treating sampled blogs or issues as if they covered the whole informal lane.

## What belongs here

High-priority clusters such as:

- interrupt and stuck-process recovery
- context flooding and compaction failure
- resume and persistence fragility
- approval and permission friction
- cleanup and repo-state hygiene
- monitoring, safety, and oversight
- tool misuse and post-tool handling

## Default structure

```text
INFORMAL_CLUSTER_DOSSIER
- cluster:
- source_families:
- primary_items:
- coverage_used:
- coverage_not_yet_used:
- operator_claims:
- issue_or_postmortem_evidence:
- contradictions:
- likely_mechanism_pressure:
- likely_failure_pressure:
- confidence_notes:
- downstream_relevance:
```

## Operating rules

1. Separate operator philosophy from direct issue evidence.
2. Preserve contradictions instead of smoothing them away.
3. Low-credibility or weakly captured material should stay visibly caveated.
