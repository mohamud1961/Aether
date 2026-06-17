# Principal Agent Workflow

## Purpose

This guide explains how the human owner should engage the principal project agent and how the principal should engage specialist agents.

## In simple terms

- You talk to the principal agent.
- The principal agent decides what artifact is active.
- The principal agent decides whether a specialist is needed.
- Specialists do bounded work.
- The principal agent synthesizes and returns the result to you.
- The principal agent should recommend adversarial review at important moments by default.

The principal agent is the manager, not the only worker.

## What you say to the principal agent

Use short, stage-aware requests.

Examples:

- `We are ready for synthesis prep. Start with evidence inventory.`
- `Open the mechanism-map artifact and tell me which specialists you need.`
- `Run a blind-parallel pass for failure taxonomy.`
- `Use the synthesis-prep specialist on the accepted corpus and trajectory assets.`
- `Summarize where the evidence base is still weak before we start mechanism extraction.`

## What the principal agent should return

For each new artifact, the principal agent should give you:

1. the active artifact
2. the goal of the artifact
3. the collaboration mode
4. the specialists to use, if any
5. whether you should run an external agent now
6. the expected outputs
7. what needs your approval

The external-agent callout should be explicit:

- `Run external agent now: yes`
- `Agent: synthesis-prep specialist`
- `Why: evidence inventory is bounded specialist work`
- `Expected output: tracking/collab/<stage>/<artifact>/outputs/<file>.md`

Or:

- `Run external agent now: no`
- `Reason: this is still principal-only coordination or judgment work`

## Recommended workflow

### Step 1. You activate a stage or artifact

Example:

- `Start synthesis prep`
- `Open failure taxonomy`

### Step 2. Principal agent frames the task

It should define:

- the artifact
- the exact question
- the collaboration mode
- the needed inputs
- the needed specialists

### Step 3. Principal agent creates the task packet

The task packet should usually become:

- `tracking/collab/<stage>/<artifact>/brief.md`

### Step 4. Principal agent routes specialist work

Examples:

- synthesis-prep specialist
- trajectory/failure analyst
- codebase/eval analyst
- literature/informal analyst
- contradiction analyst

At this step, the principal agent should tell you plainly whether to task/run an external agent now or to hold.

### Step 5. Specialists write separate outputs

These should go under:

- `tracking/collab/<stage>/<artifact>/outputs/`

### Step 6. Principal agent synthesizes

This should go under:

- `tracking/collab/<stage>/<artifact>/synthesis/principal_synthesis.md`

And the principal should also produce:

- `tracking/collab/<stage>/<artifact>/decision.md`

### Step 7. You approve the next move

You approve:

- stage transitions
- major artifact acceptance
- high-impact changes in direction

### Step 8. Material outcomes go to the historian

If the artifact materially matters, a raw ledger handoff is emitted citing the collaboration files.

## When the principal agent should use a specialist

Use a specialist when:

- the task is bounded
- the task has a clear output
- the task benefits from depth in one evidence class
- the task would otherwise overload the principal agent

Do not use a specialist when:

- the task is a simple coordination question
- the task is a final synthesis judgment
- the task is a small direct repo edit

## When the principal agent should use a red-team / adversarial specialist

Use a red-team or contradiction specialist by default for:

- synthesis-prep completion
- major deep-synthesis artifacts
- eval architecture
- variant-library conclusions
- important methodology or scope changes

You can skip adversarial review only when the artifact is obviously mechanical or low impact.

## The synthesis-prep specialist specifically

Use the synthesis-prep specialist when the task is:

- evidence inventory
- source tagging
- confidence labeling
- trajectory/codebase priority selection
- preparation for mechanism map or failure taxonomy

Do not use it for:

- final mechanism claims
- final failure conclusions
- final eval policy

## Minimal operator loop

If you want the simplest possible way to work:

1. tell the principal which artifact to open
2. let the principal decide whether to use specialists
3. check the explicit `Run external agent now: yes/no` call
4. review the principal synthesis
5. approve the next artifact

That is enough.

## Suggested first commands for synthesis prep

When you are ready, say one of these to the principal agent:

- `Start synthesis prep with evidence inventory.`
- `Use the synthesis-prep specialist and tell me the first trajectory and codebase case studies to prioritize.`
- `Open the mechanism-map artifact and prepare the evidence base first.`
