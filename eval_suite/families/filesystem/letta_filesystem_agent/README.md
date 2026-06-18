# Letta Filesystem Agent Pack

**Family:** filesystem / letta_filesystem_agent
**Sub-family:** letta_filesystem_agent

## What this tests

Filesystem-agent capability under the Letta leaderboard protocol.
Tests the harness's ability to navigate and query a file tree, answer questions
about file contents, and handle different difficulty levels (easy/medium/hard).

## Provenance

Benchmark-derived from the Letta leaderboard filesystem-agent task format.
This pack contains ONLY small synthetic/representative fixtures (not the upstream
licensed corpus). The adapter logic lives at `eval_suite/adapters/letta.py` and
`eval_suite/adapters/letta_native.py`.
Fixture data lives in `eval_suite/fixtures/letta/letta/filesystem-agent/`
(also the adapter fallback path used by `runner/legacy_packets/letta_context_bench.py`).

**Offline status:** The adapter-driven grading requires runner infrastructure.
Mark as "requires runner integration; not run in the offline suite."

## Offline / Network requirements

- Offline: fixture data is local (no network).
- Requires runner integration to run end-to-end (adapter-driven, not standalone).
- Run via: `python3.11 -m runner run-eval` is not yet wired for this pack type.
