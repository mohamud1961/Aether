# Research

Five generations of agent harness, a synthesis of 312 external runs, and the findings that survived. The
short version: verification is where a harness adds most and fails most quietly, and trajectory cost,
not per-call cost, is what to optimise.

| Read | What it is |
|---|---|
| [findings.md](findings.md) | The five findings, with numbers, evidence and limits. **Start here** |
| [run-loop-engineering.md](run-loop-engineering.md) | Every run-loop defect found by trajectory audit: observation, termination, context, provider, protocol, verification, isolation |
| [outer-loop.md](outer-loop.md) | Four turns of the loop: trajectory → named failure → eval → harness change → measured effect |
| [related-work.md](related-work.md) | How each finding sits against published work, and the open questions left |
| [synthesis/](synthesis/) | Deep synthesis of external harnesses and 312 parsed runs: mechanism map, failure taxonomy, answered questions, dossiers |
| [generations/](generations/) | Five harness generations: design, results, and why each was replaced |
| [generations/adaptive-workbench.md](generations/adaptive-workbench.md) | The architect–solver–verifier workbench and Adaptive Harness Profiles |
| [postmortems/](postmortems/) | The rate-limit storm, the grader leak, the held-out falsifier |
| [cemetery.md](cemetery.md) | 32 mechanisms that were killed, and the evidence that killed them |
