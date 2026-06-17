# Hooks And Automations

Use this skill when a loop needs repeated enforcement or repeated execution
without relying on a human to remember the next prompt.

Hooks and automations are not the loop's judgment. They are the machinery that
makes the loop observable, repeatable, and safer to leave running.

## Governing Question

Should this behavior live in a skill, a hook, or an automation?

## Decision Rule

- Put judgment in a skill.
- Put always-on enforcement around tool actions in a hook.
- Put scheduled or event-triggered repetition in an automation.
- Put cross-run state in memory files, tickets, ledgers, or scoreboards.

## Use Cases

- Wake a maintainer loop every morning to triage issues, failing checks, or
  stale branches.
- Monitor a long run and report progress or invalid state.
- Refresh scoreboards after new result rows land.
- Enforce permission checks and unsafe-action denial before tool execution.
- Capture tool arguments, receipts, and external-state changes.
- Wake a thread when an external dependency should be checked again.

## Hook Workflow

1. Identify the action boundary: before tool, after tool, before commit, before
   publish, or before external side effect.
2. Define the policy as a deterministic check.
3. Log the decision and input summary.
4. Fail closed for unsafe side effects.
5. Keep hooks small; they should enforce, not reason through the whole task.

## Automation Workflow

1. Name the cadence or event.
2. Name the project, state file, and target skill.
3. Define what counts as "nothing to do."
4. Define what gets escalated to the orchestrator.
5. Define max runtime and retry cap.
6. Write a compact run note when the automation acts.

## Output Contract

```text
mechanism: hook | automation | skill | memory
trigger:
policy_or_prompt:
state_paths:
max_runtime:
retry_cap:
escalation_rule:
logs_or_receipts:
owner:
```

## Guardrails

- Do not put broad reasoning in hooks.
- Do not schedule an automation without a stop condition.
- Do not let an automation modify high-impact surfaces without review.
- Do not hide repeated failures by archiving them as "nothing happened."

