# AI-Native Project Stages

This folder shows how AI was used to build the project as an engineering
system, not as scattered chat prompts.

The canonical assets still live in:

- `../skills/` for reusable operator skills;
- `../prompts/` for role prompts used by specialist agents;
- `../templates/` for handoff and closeout checklists;
- `../schemas/` for structured evidence objects.

The stage folders below explain when those assets are used and what evidence
each stage should leave behind.

## Stage Map

| Stage | Project use | Main output |
|---|---|---|
| [01 Research Gathering](01-research-gathering/) | Gather sources, traces, code, docs, run artifacts, and open questions | source inventory and access map |
| [02 Deep Synthesis](02-deep-synthesis/) | Convert raw evidence into mechanism maps, failure taxonomies, and claims | synthesis artifacts and contradiction register |
| [03 Evals And Variants](03-evals-and-variants/) | Turn failures into eval contracts, scoreboards, and bounded variant decisions | eval rows, scorecards, keep/kill decisions |
| [04 Implementation And Runtime](04-implementation-and-runtime/) | Build bounded runtime slices with tests, smokes, and handoffs | verified diffs and runtime capability evidence |
| [05 Review Repair And Publication](05-review-repair-and-publication/) | Attack claims and diffs before shipping or publishing | review disposition and public/private clearance |
| [06 Loop Operations And Continuity](06-loop-operations-and-continuity/) | Keep the project continuable through orchestration, memory, and follow-up loops | durable state, handoffs, and next-action map |

## Design Rule

Skills are the public operating layer. Prompts are supporting implementation
examples. If a prompt does not serve a reusable role, it should be collapsed
into a skill or removed.

The intentionally small public skill set is:

1. task briefing and planning;
2. loop orchestration;
3. context, memory, and token economy;
4. run and VM operations;
5. analyze agent runs;
6. deep synthesis loop;
7. synthesis adjudication;
8. agentic TDD and verification;
9. eval-first implementation slice;
10. eval design and variant governance;
11. tournament runner;
12. implementation loop;
13. bounded implementation slice;
14. review repair loop;
15. code review closeout;
16. provenance publication review;
17. handoff writing.

Specialist deep-synthesis files remain available, but they are not the default
entry point. They are activated only when a stage needs that role.
