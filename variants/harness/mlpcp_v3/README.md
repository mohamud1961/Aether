# MLPCP v3 — Whole-Harness Variant Line

**HISTORICAL CODE SNAPSHOT** — not standalone-runnable.

These files are verbatim copies from the MLPCP v3 VM run pulled to
`tracking/variants/mlpcp_v3/` on 2026-06-11. They are preserved here
as a readable historical record, not as executable code.

**Import note**: `mlpcp_v2_harbor_host.py`, `mlpcp_v2_harbor_agent.py`, and
`mlpcp_v2_harbor_task_runner.py` all import from `runner.mlpcp_v2.*`
(capability_mapping, execute_plan, finalization, etc.). That sub-package was
purged from the working tree and is not recoverable from the local repo.
Running these files directly would fail with ImportError.

**The live, runnable harness is `harness/aether2`**, which supersedes this line.

---

## Architecture hypothesis

MLPCP v3 tested a cockpit/capability-graph/receipt "execute-plan" architecture:

- The **harbor host** (`mlpcp_v2_harbor_host.py`, 4369 lines) manages a
  continuous-conversation session with typed tools, a Harbor bridge for
  background services, and a receipt-memory system for task state.
- The **lean cockpit** (`lean_cockpit.py`, 735 lines, self-contained) is a
  compact operating dashboard that shows the model its known state — tasks,
  receipts, tool results — without coercive forcing language. This file has
  zero internal imports and is the most readable piece of this line.
- The **harbor agent** (`mlpcp_v2_harbor_agent.py`, 146 lines) is the
  agent-side shim that dispatches typed tool calls to the host.
- The **task runner** (`mlpcp_v2_harbor_task_runner.py`, 207 lines) handles
  single-task execution flow including receipts and grader callbacks.

## What was tested

Phase 7 (2026-06-08→11): the `receipt-memory-cockpit` patch was applied on the
Azure VM, and `qemu-startup` passed. Background/service tools were added
(`background_job`, `monitor_job`, `service_probe_loop`). However, the model
ignored the new tools on `hard2` tasks (`extract-moves-from-video`,
`install-windows-3.11`) and kept looping on search/inspection instead.

A generic progress escalation patch was attempted but failed because the source
anchor `_execute_single_action` was not found in the current VM code.

## Outcome

- qemu-startup: PASS (after receipt-memory-cockpit patch)
- hard2 reruns: 0.0 (model did not engage background tools)
- Status: PAUSED pending VM reconnect and source anchor inspection

See `pause_state.md` for the full session status and next-session plan.

## Files

| File | Lines | Import risk | Notes |
|---|---|---|---|
| `code/lean_cockpit.py` | 735 | NONE (self-contained) | Best readable artifact in this line |
| `code/mlpcp_v2_harbor_host.py` | 4369 | HIGH (runner.mlpcp_v2.*) | Core v3 host; sub-package purged |
| `code/mlpcp_v2_harbor_agent.py` | 146 | HIGH (runner.mlpcp_v2.*) | Agent shim |
| `code/mlpcp_v2_harbor_task_runner.py` | 207 | HIGH (runner.mlpcp_v2.*) | Task runner |
