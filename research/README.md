# Research

Five generations of agent harness, a synthesis of 312 external runs, and the findings that survived. The
short version: verification is where a harness adds most and fails most quietly, and trajectory cost,
not per-call cost, is what to optimise.

The working agent these findings shaped is [Core](../core/): real runs, a quickstart and how it is built.

## The question

What should the code around a frontier model, the harness, add to make an agent reliable, and how would we
know it helped? Each answer was tested as a mechanism, measured against written predictions, and kept or retired
on the evidence.

## Why it matters

- **Reliability.** Agents often finish confidently with wrong work. Knowing who should check a finish, and what
  that checker must not see, decides whether an agent can be trusted without a human reading every step.
- **Cost.** Agent cost is set by the whole run, not the single call. Cheaper calls made runs more expensive here;
  stable context halved cost per run.
- **Measurement.** Many measured wins were artefacts of rate limits, leaks or small samples. A method that catches
  this is worth as much as any single result.

## Read it in five minutes

1. [findings.md](findings.md): the five findings that survived, with numbers and limits.
2. [cemetery.md](cemetery.md): what was retired, and why.
3. [../core/EXPERIMENTS.md](../core/EXPERIMENTS.md): how the findings became decisions in the working agent.

## Open questions

1. Do harness gains shrink as models get stronger? The programme's principle predicts they should for anything
   that is a crutch, but it has not yet been measured across model tiers.
2. How far does review without the agent's claims generalise beyond the 18 cases tested?
3. Can process faithfulness (did the agent really run the check it reports) be graded automatically from traces
   at scale?

## Everything here

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
