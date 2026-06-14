# Governed Multi-Agent Operating Model

## Status

Working project proposal as of 2026-03-30. This is not a frozen policy. It is the current recommended operating model for using multiple strong agents on this project without losing evidence, control, or scientific clarity.

## Why this exists

This project is too large to rely on one agent or one thread, but it is also too complex to hand to an ungoverned swarm.

The goal is not to maximize agent count. The goal is to maximize:

- research quality
- eval quality
- implementation throughput
- traceability
- decision quality

The recommended answer is a governed system:

- one human project owner
- one principal project steward agent
- bounded specialist agents
- structured collaboration artifacts
- historian and git hygiene kept separate from strategy

## Core reasoning

### 1. Use agents to increase coverage, not to replace governance

Multiple strong agents are useful for:

- independent mechanism extraction
- failure analysis
- eval red teaming
- variant criticism
- synthesis pressure-testing

They are dangerous when used as:

- a shared rolling group chat
- an unbounded idea generator
- a self-governing experiment engine

The project needs a stable spine more than it needs more raw intelligence.

### 2. A principal agent should exist

The project benefits from one reusable principal-agent role that owns continuity and coordination.

The principal agent is not the only smart agent and not the only contributor. Its job is to protect project coherence:

- current stage
- active artifacts
- open questions
- specialist routing
- synthesis
- escalation to the human owner

### 3. Collaboration must be stage-aware

Different stages need different collaboration patterns. One shared all-model room will create contamination, repeated arguments, and hard-to-audit conclusions.

The collaboration unit should be:

- one stage
- one artifact
- one decision question

### 4. The historian remains separate

The historian is not the project strategist. The historian owns the canonical research ledger in `tracking/ledger/`.

Other agents may produce raw handoffs and collaboration artifacts, but they do not rewrite the ledger directly.

### 5. The git agent remains separate

Commit hygiene is operational work, not project strategy. The git agent should stay focused on coherent commit grouping and commit intent, using the ledger inbox and git handoff reports as signals.

## Recommended roles

### Human owner

Owns:

- project goal
- final direction
- final approvals on high-impact changes
- acceptance of major stage transitions

### Principal project steward agent

Owns:

- project spine
- current stage and next-step framing
- active artifact list
- specialist assignment recommendations
- synthesis across agent outputs
- escalation of decisions that need the human owner

Must not:

- silently redefine project goals
- rewrite ledger history
- auto-promote eval claims without evidence
- let evals, variants, and experiments all mutate at once without explicit control

### Specialist agents

Own bounded artifacts such as:

- mechanism extraction
- failure taxonomy passes
- eval family design
- variant family proposals
- trace analysis
- red-team critique
- orchestration logic implementation

Specialists should not own project direction.

### Historian agent

Owns:

- `tracking/ledger/`

Consumes:

- raw `RAW_LEDGER_UPDATE` handoffs

Produces:

- canonical ledger entries

### Git commit agent

Owns:

- commit hygiene
- coherent slicing
- git handoff reports in `tracking/git/`

## Collaboration modes

### 1. Single-agent execution

Use when:

- the task is mechanical
- the task is well-bounded
- the task does not benefit from independent judgment

Examples:

- schema cleanup
- one-file implementation
- straightforward repo refactor

### 2. Blind parallel

Use when:

- independent judgment matters
- you want disagreement before convergence
- the artifact is high stakes

Pattern:

1. Create one task packet.
2. Give the same packet to 2-3 agents independently.
3. Store outputs separately.
4. Run one synthesis pass.

Best for:

- mechanism mapping
- failure taxonomy
- results interpretation
- high-stakes architecture comparison

### 3. Role-sequenced collaboration

Use when:

- the artifact benefits from structured opposition rather than parallel brainstorming

Typical role chain:

- proposer
- critic
- falsifier
- synthesizer

Best for:

- eval architecture
- promotion policy
- governance design
- experimental validity review

### 4. Principal-led implementation

Use when:

- the project already knows what should be built
- the remaining issue is coordination and implementation

Best for:

- orchestration logic
- stage transitions
- codifying already-agreed operating rules

## Stage-by-stage operating model

### Stage 1. Research closeout

Primary mode:

- mostly single-agent
- selective blind parallel for gap audits

Outputs:

- accepted corpus
- weak-record audit
- unresolved research gaps

### Stage 2. Synthesis

Primary mode:

- synthesis prep first
- then multi-agent deep synthesis with adversarial review at important checkpoints

Outputs:

- a usable corpus map and evidence inventory
- mechanism map
- failure taxonomy
- reusable claims
- open questions list

Important:

- synthesis prep exists to make the full frozen research corpus usable
- deep synthesis is not a single deterministic pass
- deep synthesis should analyze the full frozen corpus across papers, docs, informal sources, trajectories, codebases, eval repos, and eval captures
- important synthesis artifacts should receive adversarial review by default when practical

See also:

- `SYNTHESIS_TEAM_SPEC.md`

### Stage 3. Eval architecture

Primary mode:

- role-sequenced collaboration

Outputs:

- eval layers
- scorecards
- invariant policy
- grader policy
- holdout policy
- promotion policy

### Stage 4. Variant library design

Primary mode:

- hybrid: blind parallel for breadth, role-sequenced for pruning

Outputs:

- baseline variants
- atomic families
- combo candidates
- system candidates

### Stage 5. Reference harness build

Primary mode:

- principal-led implementation with specialist support as needed

Outputs:

- clean baseline harness
- reference substrates
- logging and experiment surfaces

### Stage 6. First manual experiment cycle

Primary mode:

- mostly single-agent and principal-led
- specialist red-team review on anomalies

Purpose:

- validate that the eval stack and variant library are real before heavy automation

### Stage 7. Governed autoresearch

Primary mode:

- orchestrated specialist execution under fixed governance

This is where the overnight loop belongs, after:

- baseline harness exists
- eval v1 exists
- variant cards exist
- logging and promotion rules exist

## Recommended current sequence

This is the recommended order from the current state of the project:

1. Finish research intake and closeout.
2. Build the mechanism map and failure taxonomy.
3. Define the eval architecture.
4. Define the first variant library.
5. Build one clean baseline harness and one manual experiment loop.
6. Only then build the governed autoresearch loop.

## Collaboration workspace

Canonical location:

- `tracking/collab/`

Recommended layout:

```text
tracking/collab/
  stage_02_synthesis/
    mechanism_map/
      brief.md
      inputs/
      outputs/
        model_a_parallel.md
        model_b_parallel.md
        model_c_parallel.md
      synthesis/
        principal_synthesis.md
      decision.md
```

Principles:

- same task packet
- separate agent outputs
- one synthesis artifact
- one explicit decision artifact

Do not use one shared live multi-agent discussion as the canonical record.

## Storage boundaries

### Canonical strategy and coordination

- this document
- future principal-agent prompt under `prompts/`

### Collaboration artifacts

- `tracking/collab/`

### Canonical ledger

- `tracking/ledger/`

### Git hygiene

- `tracking/git/`

### Research corpus and synthesis

- `research/`

## Relationship to existing project files

### `AGENTS.md`

`AGENTS.md` remains the repo-wide behavioral contract. This operating model should refine how multiple agents collaborate, not replace the existing mission, block composability rules, ledger reporting, or commit discipline.

### Historian prompt and ledger

The historian still owns `tracking/ledger/`. Collaboration outputs are not canonical ledger entries. If collaboration work is material, another agent should emit a raw ledger handoff citing the relevant collaboration artifacts.

### Git commit agent

The git agent should use ledger handoffs and real diffs to keep commits coherent, but should not become the owner of project strategy or experiment promotion.

## HITL guidance

This project is AI-first, but the human owner should remain in the loop for:

- new eval families
- new variant families
- changes to promotion logic
- champion replacement
- major stage transitions
- scope changes

Low-risk bounded work can be delegated without approval on every small step.

## What should be built now

Recommended immediate artifacts:

1. A root-level operating model document.
2. A principal-agent prompt.
3. A collaboration workspace README under `tracking/`.
4. Light alignment updates in live docs so the paths are canonical.

Full automation should wait until after the first real manual baseline and eval cycle.

## Actions taken in this pass

This pass created and/or updated the following governance artifacts:

- root operating model document
- principal-agent prompt
- collaboration workspace README
- tracking and prompt indexes where needed
- repo-wide `AGENTS.md` alignment where needed

## Where things are stored

- operating model: `GOVERNED_MULTI_AGENT_OPERATING_MODEL.md`
- principal prompt: `prompts/principal_project_agent_prompt.md`
- collaboration workspace guidance: `tracking/collab/README.md`
- canonical ledger: `tracking/ledger/`
- git handoff reports: `tracking/git/`

## Deliberate non-decisions

This document does not freeze:

- exact model assignments
- exact HITL approval thresholds
- exact overnight orchestration logic
- exact eval versioning policy

Those should be refined after research closeout and the first manual baseline/eval cycle.
