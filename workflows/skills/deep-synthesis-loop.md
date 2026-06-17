# Deep Synthesis Loop

Use this skill when a synthesis question needs multiple evidence lanes,
specialist threads, contradiction review, and a decision package.

This is the orchestrator skill for deep synthesis. The family member skills do
the lane work; this skill controls the loop.

## Governing Question

What claim can survive evidence inventory, specialist analysis, contradiction
review, and closure without overstating the source material?

## Use Cases

- Derive reusable engineering skills from prior agent threads.
- Turn many run analyses into a failure taxonomy.
- Compare source systems, tools, or workflows without collapsing them into one
  narrative.
- Extract mechanism ideas from traces, code, docs, and informal engineering
  reports.
- Produce a public-safe claim set from private or mixed-source evidence.

## Lane Map

Activate only the lanes needed for the question:

- coverage/access lane: what exists and what can be read;
- trajectory/failure lane: what actually happened in runs;
- codebase/source lane: what the implementation really does;
- formal-docs lane: what papers/docs/specs claim;
- informal lane: what issues, posts, and postmortems suggest;
- eval/verifier lane: what the scoring and checking surfaces actually test;
- contradiction lane: what claims fail under cross-lane pressure;
- closure lane: accepted claims, warnings, and next actions.

## Workflow

1. **Freeze the question**
   - Name the artifact and decision it supports.
   - Define the confidence ladder.
   - Mark private/public boundaries.

2. **Build the evidence inventory**
   - List sources by lane.
   - Mark unread, inaccessible, weak, and strong evidence separately.

3. **Dispatch lanes**
   - Give each specialist a bounded output contract.
   - Allow support subagents for inventory or matrices only.

4. **Synthesize per lane**
   - Require observations before inference.
   - Require evidence paths for strong claims.

5. **Contradiction review**
   - Ask an independent reviewer to disprove the emerging claim set.
   - Preserve unresolved contradictions instead of smoothing them away.

6. **Closure package**
   - Produce accepted claims, rejected claims, warnings, confidence labels, and
     follow-up tasks.

## Output Contract

```text
question:
lanes_activated:
evidence_inventory:
accepted_claims:
rejected_claims:
contradictions:
confidence:
public_safe_summary:
private_evidence_withheld:
next_actions:
```

## Guardrails

- Do not summarize before inventory exists.
- Do not let one strong lane override direct contradictory evidence.
- Do not publish private evidence; publish the claim with a safe reference or
  withhold it.
- Do not treat a polished synthesis as proof if the evidence ladder is weak.

