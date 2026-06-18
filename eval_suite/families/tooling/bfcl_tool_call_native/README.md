# BFCL Tool-Call Native Pack

**Family:** tooling / tool-call
**Sub-family:** bfcl_tool_call_native

## What this tests

Tool-call capability under the Berkeley Function Calling Leaderboard (BFCL) protocol.
Tests multi-turn function-call composition, parameter handling, and API class dispatch
using small synthetic representative fixtures derived from the BFCL format.

## Provenance

Benchmark-derived from the BFCL v3 multi-turn benchmark format. This pack contains
ONLY small synthetic/representative fixtures (not the upstream licensed corpus).
The adapter logic lives at `eval_suite/adapters/bfcl.py` and `eval_suite/adapters/bfcl_native.py`.
Fixture data lives in `eval_suite/fixtures/bfcl/` (shared with the adapter fallback path).

**Offline status:** The adapter-driven grading requires runner infrastructure.
Mark as "requires runner integration; not run in the offline suite."

## Offline / Network requirements

- Offline: fixture data is local (no network).
- Requires runner integration to run end-to-end (adapter-driven, not standalone).
- Run via: `python3.11 -m runner run-eval` is not yet wired for this pack type.
