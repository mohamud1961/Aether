# Context Recipe Audit

## Scope

This slice adds an optional structured-memory-first context recipe over existing `ExecutionLedger` receipts. It does not add model-authored semantic memory, new storage, or benchmark/task-specific selectors.

## Realized Recipe Shape

Supported declared fields:

- `always_include`
- `include_recent`
- `include_last_failure`
- `preserve_exact`
- `make_queryable_not_inline`

Unsupported top-level recipe fields are carried into `unsupported_fields` and surfaced in `context_recipe_realization.rejected`.

## Supported Selectors

Exact selectors:

- `open_obligations`
- `obligation_status`
- `monitor_alerts`
- `live_processes`
- `recent_progress`
- `failure_clusters`
- `artifacts_present`
- `candidate_leaderboard`
- `installed_capabilities`
- `planned_checks`
- `pending_checks`
- `active_verifier_findings`
- `repeated_actions`
- `files_already_read`
- `stuck`

Recent receipt selectors:

- `recent_progress`
- `tool_results`
- `file_reads`
- `file_writes`
- `command_results`
- `check_results`
- `query_memory_results`
- `verifier_results`

Failure selector:

- `last_failures` via `include_last_failure`

## Deterministic Realization Metadata

When a recipe is present, the context packet carries `context_recipe_realization` with:

- `declared`
- `selected`
- `omitted`
- `rejected`
- `queryable_not_inline`
- `counts`
- `rendered_section_counts`
- `byte_count_v1`
- `token_estimate_v1`

The packet keeps `memory_query_available=true` and uses `query_memory` as the only access path for queryable-not-inline material.

## Authority Boundaries

- Recipe realization is derived only from deterministic ledger state and receipt payloads.
- Unsupported selectors are quarantined in metadata and do not create authoritative sections.
- Queryable-not-inline content is represented as metadata only; old or large outputs remain retrievable through existing receipt queries rather than being copied inline.
- `preserve_exact` selectors are protected from the generic compression pass for `recent_progress`, `failure_clusters`, and `candidate_leaderboard`.
