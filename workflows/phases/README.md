# Workflow Phases

This is the compact phase reference. For the reviewer-facing project lifecycle
with subfolders by stage, start at [../stages/](../stages/).

The point is to make the system understandable as an operating loop, not as a
pile of skills.

## Phase Map

| Phase | Question | Primary artifacts |
|---|---|---|
| 0. Frame | What are we trying to achieve, and what is out of scope? | `task-briefing-and-planning`, `codex-goal-governance` |
| 1. Plan | What is the control map and evidence contract? | `loop-orchestrator`, `context-memory-token-economy`, `task-packet` |
| 2. Launch | Who does the work, where, and with what isolation? | `run-vm-operations`, `hooks-and-automations`, `bounded-implementation-slice` |
| 3. Analyze | What happened, and what evidence is trustworthy? | `analyze-agent-runs`, `deep-synthesis-loop`, `synthesis-adjudication` |
| 4. Eval | What check decides whether the work is real? | `agentic-tdd-and-verification`, `eval-first-implementation-slice`, `eval-design-and-variant-governance` |
| 5. Implement | What is the smallest bounded change? | `implementation-loop`, `bounded-implementation-slice` |
| 6. Review | What did the maker miss? | `code-review-closeout`, `review-repair-loop`, `adversarial-code-review-closeout` |
| 7. Decide | Promote, kill, rerun, or publish? | `tournament-runner`, `provenance-publication-review`, scoreboards |

## Stage Narrative

The loop starts with intent and ends with a decision. A phase can be skipped
only when the artifact is small enough that the exit condition remains obvious.
For serious work, each phase leaves a durable object: a plan, handoff, eval,
result row, review disposition, or publication note.

## Skill Routing

- Framing and planning: `../skills/task-briefing-and-planning.md`,
  `../skills/loop-orchestrator.md`
- Context and memory: `../skills/context-memory-token-economy.md`,
  `../templates/context-memory-handoff-checklist.md`
- Run operations: `../skills/run-vm-operations.md`,
  `../skills/hooks-and-automations.md`
- Evidence analysis: `../skills/analyze-agent-runs.md`,
  `../skills/deep-synthesis-loop.md`
- Eval and TDD: `../skills/agentic-tdd-and-verification.md`,
  `../skills/eval-first-implementation-slice.md`
- Implementation: `../skills/implementation-loop.md`,
  `../skills/bounded-implementation-slice.md`
- Review and repair: `../skills/review-repair-loop.md`,
  `../skills/code-review-closeout.md`
- Decision and publication: `../skills/tournament-runner.md`,
  `../skills/provenance-publication-review.md`

## Output Rule

Every non-trivial phase should leave an artifact another agent can inspect
without reopening the original conversation.
