# Orchestration

Orchestration covers how work is split and handed over: an architect that writes contracts, workers that receive packets, handoffs that keep artifact identity, and requests that change mid-thread.

The architect split was tested hardest and changed least. A rubric scored architect outputs 9 to 10 out of 10 across rounds. Outcome trials did not show a variant that qualified both mixed-proof families. The architect V3 runtime was promoted on a mechanical gate; its semantic board was diagnostic.

Multi-step work fails at the seam between steps. A handoff that keeps a stale identifier passes each step's local check. Only a chain-level check finds it.

## Failure modes probed

- A stale or superseded instruction carried into a worker packet.
- A retracted or superseded requirement still applied.
- A worker result from an old packet version accepted at merge.
- An artifact renamed mid-chain, with the old identifier kept in later steps.
- A handoff closed without a verifier pass event, or on an old pass record.
- An ambiguous request resolved by a sticky note or an archive instead of the ticket log.

## What the history taught

1. **Rubric scores rose while outcomes did not.** Architect outputs scored 9–10/10 on rubrics across three evaluation series, while no tested variant qualified both mixed-proof families on outcomes. The architect was removed from the production path.
2. **A headline metric can hide critical errors.** One interface variant kept its core metric and still made six critical false classifications, caught only by constraint-positive controls.
3. **Nine trials cannot resolve 2/9 against 3/9.** Small orchestration ablations stayed inconclusive; later designs started from a power calculation.
4. **Early handoff tasks were smoke checks.** The current tasks test delegation fidelity: live constraints carried, retracted ones dropped, stale worker results rejected.

Every evaluation behind these lessons is listed in the [catalogue](../catalogue.md).

## Current tasks

Validation key: known-bad files, each rejected with its expected reason; careless controls, each rejected; reference solvable from the workspace. All rows pass the grader gate.

| Task | Failure mode | What makes it hard | Validation | Admission |
|---|---|---|---|---|
| `noisy_open_workflow` | Ticket and owner from noisy evidence | Structured ticket log is ground truth; mailbox dump has a stale claim; sticky note names a rehearsal ticket; archived September cycle; stale calendar draft | 8 known-bad; 5 careless; solvable | capability |
| `subagent_handoff_contract` | Loader record and handoff contract from worker definitions and registries | Retired definition; inline MCP server; missing skill; required server absent from registry; stale placeholder with the old loader order | 8 known-bad; 5 careless; solvable | capability |
| `delegation_fidelity` | Live constraints carried into worker packets | Three kinds of change: a conflicting ask settled by a later decision, a retraction, and a constraint placed in a reply; stale README template adds fields; a worker result from packet v1 | 6 known-bad; 5 careless; solvable | capability |

## Limits

Handoff tasks grade the final handoff record and the packets, not the messages between steps. The graders are final-state, so parallel work, message order and coordination are not measured.
