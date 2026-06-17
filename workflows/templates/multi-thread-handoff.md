# Multi-Thread Orchestration Handoff

Use this when a worker thread hands results back to an orchestrator.

## Required Fields

- final status: `complete`, `partial`, `blocked`, or `invalid due to environment`;
- objective and scope actually completed;
- exact files changed;
- requirement or plan-item disposition;
- validation commands and evidence paths;
- review findings, accepted fixes, and consciously rejected findings;
- unresolved work, blockers, risks, and exact next action;
- external-state confirmation for processes, servers, VMs, or credentials;
- persisted `RAW_LEDGER_UPDATE` status when the work was material;
- explicit handoff delivery receipt: target orchestrator thread ID, delivery
  tool or mechanism, and success/error result.

## Handoff Quality Checks

- The summary matches the live tree.
- Claims are qualified where evidence is incomplete.
- Private artifacts are referenced only when the audience is allowed to see
  them.
- The orchestrator can decide the next slice without reopening the whole task.
- The handoff was explicitly sent to the originating orchestrator, not only
  written to disk or posted as the worker thread's own final answer.
