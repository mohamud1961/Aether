# TerminalBench Terminal Pack

**Family:** environment / terminalbench_terminal
**Sub-family:** terminalbench_terminal

## What this tests

Terminal-task capability under the TerminalBench benchmark protocol.
Tests the harness's ability to execute shell tasks, navigate terminal environments,
and handle file/process management under realistic terminal workflows.

## Provenance

Benchmark-derived from the TerminalBench benchmark format. This pack contains
ONLY provenance documentation (no upstream licensed corpus).
The adapter logic lives at `eval_suite/adapters/terminalbench.py` and
`eval_suite/adapters/terminalbench_native.py`.

See also `eval_suite/calibration_lanes/terminal/reference/final_harness_task.md`
for the public calibration reference describing the pressure shape without
including official task material.

**Offline status:** Requires runner infrastructure and certified sandbox.
Mark as "requires docker/sandbox; not run in the offline suite."

## Offline / Network requirements

- Requires docker/certified sandbox backend for execution.
- Requires runner integration to run end-to-end (adapter-driven, not standalone).
- NOT part of the offline suite. Marked deferred per §7 engineering standards.
