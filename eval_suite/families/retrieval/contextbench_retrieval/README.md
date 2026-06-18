# ContextBench Retrieval Pack

**Family:** retrieval / contextbench_retrieval
**Sub-family:** contextbench_retrieval

## What this tests

Long-context retrieval under the ContextBench benchmark protocol.
Tests the harness's ability to locate and extract specific code/text segments
from large context windows, measured against gold context-length metadata.

## Provenance

Benchmark-derived from the ContextBench leaderboard format. This pack contains
ONLY small synthetic/representative fixtures (not the upstream licensed corpus).
The adapter logic lives at `eval_suite/adapters/contextbench.py` and
`eval_suite/adapters/contextbench_native.py`.
Fixture data lives in `eval_suite/fixtures/contextbench/` (shared with adapter fallback).

**Offline status:** The adapter-driven grading requires runner infrastructure.
Mark as "requires runner integration; not run in the offline suite."

## Offline / Network requirements

- Offline: fixture data is local (no network).
- Requires runner integration to run end-to-end (adapter-driven, not standalone).
- Run via: `python3.11 -m runner run-eval` is not yet wired for this pack type.
