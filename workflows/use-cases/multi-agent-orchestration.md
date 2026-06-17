# Multi-Agent Orchestration

## Purpose

Use this workflow when work is too large for one uninterrupted agent session.
An orchestrator owns the objective and delegates bounded slices to specialist
threads or agents.

## Loop

1. Orchestrator frames the goal, scope, stop conditions, and evidence outputs.
2. Work is split into bounded task packets.
3. Specialists execute one slice each.
4. Each specialist hands back status, files changed, validation, risks, and
   next action.
5. The orchestrator integrates, checks claims against the tree, and sends weak
   work back through review or repair.
6. Material results are persisted as public-safe summaries or private ledger
   inputs.

## Public Proof Surfaces

- `../loop-engineering/README.md`
- `../loop-engineering/orchestration-ledger-case-study.md`
- `../skills/loop-orchestrator.md`
- `../skills/handoff-writing.md`
- `../templates/multi-thread-handoff.md`
- `../orchestration/governed-multi-agent-model.md`

## What This Prevents

- silent background work;
- merged transcripts with no ownership;
- lost validation commands;
- unreviewed worker claims;
- context compaction destroying project memory.

## Closeout Rule

A worker summary is not complete until the orchestrator can inspect the changed
files, evidence, review findings, unresolved risks, and next recommended
action.
