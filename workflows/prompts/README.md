# Prompts

Role prompts for the specialist agents in the loop. All prompts have been sanitized:
private paths replaced with `<project root>`, internal stage paths replaced with
generic forms, model version strings removed.

Prompts are not the main showcase. The main showcase is the skill and stage
system that decides when a specialist should run, what evidence it must leave,
and when the loop should stop.

Keep a prompt only when it is:

- reusable across tasks;
- tied to a real stage or specialist role;
- paired with a skill, schema, or handoff artifact;
- sanitized of private paths, provider branding, private suite details, and
  one-off task answers.

If an instruction does not meet that bar, keep it as a task packet or fold it
into the relevant skill.

## Role Map

### Orchestration / Coordination

| File | Role | Use when |
|---|---|---|
| [principal-project-agent.md](principal-project-agent.md) | Principal Project Agent | Project coherence, stage transitions, artifact routing, specialist dispatch, escalation. The manager, not the sole implementer. |
| [base-system.md](base-system.md) | Base task agent | Clean 14-line base prompt for a task-solving agent in a terminal environment. Two template variables: `{task_instruction}` and `{env_snapshot}`. |

### Git / Code

| File | Role | Use when |
|---|---|---|
| [git-commit-agent.md](git-commit-agent.md) | Git Commit Agent | Turning completed slices into regular, intentional commits. Produces a `GIT_AGENT_REPORT` with commit candidates, split plans, and blockers. |

### Synthesis Preparation

| File | Role | Use when |
|---|---|---|
| [synthesis-prep-agent.md](synthesis-prep-agent.md) | Synthesis Prep Agent | Building or updating the evidence inventory for a synthesis artifact. More structured than broad intake; less interpretive than deep synthesis. |
| [synthesis-prep-red-team-agent.md](synthesis-prep-red-team-agent.md) | Synthesis Prep Red-Team Agent | Adversarial review of synthesis prep outputs — challenging evidence quality, coverage gaps, and inference leaps. |
| [synthesis-prep-eval-inventory-agent.md](synthesis-prep-eval-inventory-agent.md) | Eval Inventory Specialist | Building the eval evidence inventory: which eval sources exist, which are highest value, which important eval families are missing. |

### Deep Synthesis (family)

| File | Role | Purpose |
|---|---|---|
| [deep-synthesis-shared-policy.md](deep-synthesis-shared-policy.md) | Shared policy supplement | Evidence precedence rules, extraction ceiling (L4/L5), coverage reporting contract, gate-review rules. Use together with any role-specific deep synthesis prompt. |
| [deep-synthesis-trajectory-failure-analyst.md](deep-synthesis-trajectory-failure-analyst.md) | Trajectory/failure analyst | Extract how harnesses behave in runs, where they fail, and which workflow patterns recur. |
| [deep-synthesis-codebase-source-analyst.md](deep-synthesis-codebase-source-analyst.md) | Codebase/source analyst | Source-reconstruction: how harness components are actually built from code evidence. |
| [deep-synthesis-eval-contract-analyst.md](deep-synthesis-eval-contract-analyst.md) | Eval contract analyst | Verifier, grader, replay, and eval contract logic when the wave packet makes this load-bearing. |
| [deep-synthesis-literature-analyst.md](deep-synthesis-literature-analyst.md) | Literature/papers/docs analyst | Academic and official documentation evidence. |
| [deep-synthesis-informal-analyst.md](deep-synthesis-informal-analyst.md) | Informal/issues/postmortems analyst | Engineering writeups, issue trackers, postmortems, and informal sources. |
| [deep-synthesis-support-subagent.md](deep-synthesis-support-subagent.md) | Support sub-agent | Bounded support: inventories, matrices, file discovery, subsystem maps. Output is an inventory aid, not promoted synthesis. |
| [deep-synthesis-contradiction-analyst.md](deep-synthesis-contradiction-analyst.md) | Contradiction analyst | Surface and preserve contradictions across wave outputs. Gate-time reviewer. |
| [deep-synthesis-checklist-adjudicator.md](deep-synthesis-checklist-adjudicator.md) | Checklist adjudicator | Adversarial audit gate: independent review of deep synthesis checklist compliance. Produces explicit `PASS` / `PARTIAL_PASS` / `FAIL` verdicts. |
| [deep-synthesis-eval-implications.md](deep-synthesis-eval-implications.md) | Eval implications analyst | Role-sequenced specialist for the `eval_implications` artifact. |
| [deep-synthesis-variant-pruning.md](deep-synthesis-variant-pruning.md) | Variant pruning analyst | Role-sequenced specialist for the `variant_family_seeds` artifact. |

## How to Use the Deep Synthesis Family

Every deep synthesis specialist should receive:
1. `deep-synthesis-shared-policy.md` (policy supplement — always)
2. Their role-specific prompt
3. The active deep synthesis `brief.md` task packet

The operating model is:
- 4 main lanes (trajectory/failure, codebase/source, literature, informal)
- eval contract analyst as an optional 5th lane when verifier/grader logic is load-bearing
- contradiction analyst and checklist adjudicator as gate-time reviewers (not first-pass)
- support sub-agents for bounded inventory/matrix work

## See Also

- [schemas/task-packet.md](../schemas/task-packet.md) — the brief format used for specialist dispatch
- [orchestration/principal-agent-workflow.md](../orchestration/principal-agent-workflow.md) — how to engage the principal agent
- [skills/](../skills/) — the workflow skills that these prompts support
