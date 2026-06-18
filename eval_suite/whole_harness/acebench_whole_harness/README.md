# ACEBench Whole-Harness Pack

**Group:** whole_harness / acebench_whole_harness

## What this tests

Whole-harness capability under the ACEBench benchmark protocol.
ACEBench tests the agent harness as a whole across diverse agentic tasks
including web navigation, coding, and multi-step problem solving — measuring
end-to-end harness performance rather than a single capability family.

## Provenance

Benchmark-derived from the ACEBench benchmark format. This pack contains
ONLY provenance documentation (no upstream licensed corpus).
The adapter logic lives at `eval_suite/adapters/acebench.py`.

## Offline / Network requirements

- Requires access to ACEBench upstream data (set `ACEBENCH_UPSTREAM_ROOT`
  environment variable or place data at `/private/tmp/acebench_upstream`).
- Requires docker/certified sandbox backend for execution.
- NOT part of the offline suite. Marked deferred per §7 engineering standards.
- Mark as "requires <ACEBENCH_UPSTREAM_ROOT> and docker; not run in the offline suite."
