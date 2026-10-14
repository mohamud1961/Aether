# Handoff writing

Use this when you need to hand work to an orchestrator or reviewer who must act on it without reopening the full task.

A handoff is evidence that work is done, or exactly how far it got. It is a structured record the next actor can check, not a progress update.

## Governing question

> Can the receiving orchestrator act on this handoff without reopening the full task?

If not, the handoff is incomplete. Common failures: vague status ("mostly done"), missing evidence paths, no risk list, no next action.

## 1. Set the status honestly

- `complete`: every exit criterion in the packet is met.
- `partial`: some are met; list the exact missing items.
- `blocked`: progress stopped on a named dependency, environment problem, or missing input.
- `invalid_due_to_environment`: the environment prevented execution.

Never use `complete` if a required behaviour is absent. A partial handoff with exact missing items is more useful than a false complete.

## 2. Summarise scope

Name the files created or changed, the files inspected but not changed, and any file on the do-not-touch list you did not touch. State whether the write scope was respected.

## 3. List evidence paths

Give every path the reviewer needs: test commands and outputs, review artifacts, scoreboard rows, lint output. Do not describe work you cannot cite.

## 4. Enumerate risks

Spec items not reached, tests that pass locally but may not elsewhere, integration surfaces not exercised end to end, deferred behaviour. A handoff with no risks usually means none were looked for.

## 5. State the next action

What the orchestrator should do next: review, repair, rerun, promote, kill, or park. Say whether any process, VM, or external service is still running. Say whether a human decision is needed.

## 6. Record the delivery receipt

Name the orchestrator and the mechanism, and whether receipt was confirmed. A file on disk is not a delivered handoff. The orchestrator must receive it.

## Output

Use the [multi-thread handoff template](../templates/multi-thread-handoff.md).

## Guardrails

- Never write `complete` when a required behaviour is absent.
- Never leave evidence paths out.
- Never leave `external_state` blank. If nothing is running, say so.
- A handoff that exists only in the agent's final message, and was never delivered, is not a handoff.
