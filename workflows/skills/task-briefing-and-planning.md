# Task Briefing and Planning

Use this skill when a new artifact or task needs to be framed, routed, and
packaged before specialist agents begin work.

Briefing is a distinct stage: more structured than "figure it out as we go,"
but less interpretive than deep synthesis. Its output is a task packet that
any qualified specialist can execute without reopening the strategic question.

## Governing Question

> What is the objective, who may act, and what evidence closes the loop?

If those three questions cannot be answered before dispatch, the task is not
ready to brief.

## When To Use

Use this skill when:

- opening a new stage or artifact;
- routing a question to a specialist agent;
- deciding whether a task needs one agent or multiple agents;
- choosing the right collaboration mode;
- framing a task that has previously been stated as vague or open-ended.

Do not use this skill for:

- final synthesis judgment (that is the principal agent's job post-synthesis);
- small mechanical tasks that can be issued directly;
- retrospective post-mortems (use analyze-agent-runs instead).

## Workflow

### 1. Identify the Active Stage

Before framing the task, confirm the current project stage:

- What has already been produced?
- What is the blocking question for the next stage?
- Has the previous stage actually closed, or is it nominally closed?

Do not advance the stage marker until the previous stage has real output, not
just progress activity.

### 2. Frame the Task Packet

Use the [TASK_PACKET template](../schemas/task-packet.md) to capture:

- `stage`: which project stage this belongs to
- `artifact`: the exact output being requested
- `objective`: what the artifact must accomplish
- `exact_question`: the question the artifact answers
- `why_now`: why this artifact is needed before other work
- `inputs`: what evidence or artifacts the specialist needs
- `preflight_requirements`: what must be true before the specialist starts
- `exclusions`: what the specialist must not do
- `output_contract`: what the artifact must contain and in what format
- `collaboration_mode`: single-agent / blind-parallel / role-sequenced / principal-led
- `external_agent_action`: explicit yes/no, which agent, and expected output path
- `assigned_roles`: which specialist roles are needed
- `handoff_requirements`: what the specialist must include in their handoff
- `evidence_expectations`: what evidence will be evaluated and on what standard
- `decision_needed_from_human`: what must be approved before proceeding
- `done_condition`: the falsifiable condition that closes the task

### 3. Choose the Collaboration Mode

**Single-agent:** bounded mechanical work, straightforward implementation,
or tasks where one specialist has clear authority.

**Blind-parallel:** mechanism extraction, failure taxonomy, high-stakes
interpretation, gap analysis, major synthesis conclusions. Run 2-3 independent
agents on the same packet, store outputs separately, then synthesize.

**Role-sequenced:** eval architecture, governance design, promotion policy,
red-team review, high-impact synthesis adjudication. Typical flow: proposer →
critic → falsifier → synthesizer.

**Principal-led implementation:** when the project knows what to build and the
main task is coherent execution across disjoint worker scopes.

### 4. Issue the External-Agent Callout

Every task recommendation must include an explicit callout:

```text
Run external agent now: yes | no
Agent: <role name>
Why now: <bounded reason>
Expected output path: <project>/tracking/collab/<stage>/<artifact>/outputs/<file>.md
```

Never leave the callout implicit. If the answer is "no," say why.

### 5. Confirm Escalation Triggers

Before dispatch, confirm when the specialist should stop and escalate rather
than continue:

- scope boundary reached;
- decisive artifact missing;
- evidence too thin to support a conclusion at the required confidence level;
- material change in direction required.

## Output Contract

The briefing should produce:

1. Active stage and rationale for why this task is next.
2. A completed TASK_PACKET struct (or the key fields if the full struct is
   overkill for a small task).
3. Explicit collaboration mode selection with rationale.
4. The external-agent callout (yes/no with reason).
5. Escalation triggers.

## Guardrails

- Do not brief a task that cannot be falsified. If the done condition is "we
  looked at it," that is not a task; that is a conversation.
- Do not skip the preflight. A specialist who starts without knowing their
  inputs wastes both time and evidence freshness.
- Do not let the task packet sprawl into a full synthesis document. One packet
  = one artifact = one question.
- Require artifacts, not chat. The output of briefing is a written task packet,
  not a verbal summary.

## Sources

- `workflows/prompts/principal-project-agent.md` — principal-agent role spec
  (operating procedure, collaboration mode guidance, escalation rules)
- `workflows/orchestration/principal-agent-workflow.md` — step-by-step
  engagement protocol (steps 1–4: stage activation, task framing, task packet
  creation, specialist routing)
- `workflows/schemas/task-packet.md` — the 25-field TASK_PACKET struct
- `workflows/loop-engineering/hour-zero-contracts-example.md` — real example of
  pre-execution contract discipline (the Hour-0 pattern applied before worker dispatch)
