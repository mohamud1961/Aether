# Source System Dossiers

This directory holds architectural-depth dossiers for major source-visible systems.

The purpose is to guarantee that Deep Synthesis does not stop at wave summaries when a system is important enough to shape mechanism, failure, eval, or variant reasoning.

## Required first-class dossiers

Create and maintain dossiers for:

- `KIRA`
- `deepagents`
- `a-evolve`
- `claw-code`

## Optional additional dossiers

Create dossiers when a system materially shapes a wave:

- `autoagent`
- grouped `src_cod_*` families
- local harness subsystems when they become comparison-relevant

## BigAI rule

BigAI should not receive a fake source dossier.

Use a behavioral dossier instead when needed:

- observed behavior
- inferred mechanism
- confidence and missing-source caveat

## Default structure

```text
SOURCE_SYSTEM_DOSSIER
- system:
- dossier_status:
- source_scope:
- architectural_core:
- tool_calling_and_execution:
- workflow_and_control_doctrine:
- context_and_state_model:
- memory_or_persistence_model:
- verification_and_completion:
- recovery_and_resumability:
- environment_and_permissions:
- what_the_agent_sees:
- relevant_trajectory_links:
- contradictions_or_unknowns:
- confidence_notes:
- downstream_relevance:
```

## Operating rules

1. A dossier should go to architectural core, not just list files.
2. Source-backed implementation claims must stay source-backed.
3. Archive-only `src_cod_*` material may pressure a dossier, but should not silently become first-class fact.
4. Dossiers support wave synthesis; they do not replace it.
