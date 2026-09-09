# History-search slice

This note describes a narrow Aether runtime change originally prepared against
public master at commit `5238707848eff72b8008b2b0df12c8a78cc6400f` and ported
cleanly onto the current public master at commit
`c8d39f0e6b33bf7085ea926654db67b571dc3ff8`.

## What changed

- History queries search captured stdout, stderr, content, chunk and excerpt
  fields using case-insensitive literal matching.
- Complete overflow streams can be searched lazily in bounded chunks when the
  captured stream is stored outside the inline receipt projection.
- Overflow paths must match the executor's spool-directory and filename
  contract; arbitrary receipt metadata is not opened. Overlong queries are
  rejected before scanning.
- Results expose bounded excerpts and exact retrieval handles without placing
  complete streams in the next model context.
- Context projection reports when a query page contains more results than the
  hot view displays, preserving the distinction between query paging and view
  projection.
- The top-level search-completeness flag is false when a referenced spool is
  missing, unreadable or outside the executor path contract; no match is
  presented as a complete search in that case.
- Receipts that already match a cheap indexed field do not trigger a full
  overflow scan across the ledger; their spool references are still validated,
  and bounded content detail is read only for selected result rows.
- History results are explicitly marked as historical observations and are
  visible to the solver as primary action results, but are not completion
  evidence for the current external task state.

## Local deterministic validation

The slice has focused tests for inline matches, newest-first ordering, empty
queries, middle-of-stream retrieval, chunk-boundary retrieval, missing spool
files, bounded context projection and evidence classification. The focused and
adjacent and real output-capture checks passed 35 tests in total.

This is source-and-test validation only. It is not a benchmark result, a live
agent qualification, or evidence of performance uplift.

## Publication boundary

The root MIT notice applies to project-owned Aether source selected for public
release. It does not relicense dependencies, copied or translated
third-party source, benchmark fixtures, generated evidence, private research
material or other files whose provenance has not been checked. See
[`third_party_notices.md`](third_party_notices.md) for the exception boundary.
