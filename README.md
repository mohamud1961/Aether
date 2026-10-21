# Aether

**A research programme on agent harnesses: what should a harness add to a frontier model, and how would we know?**

By [Mohamud Mohamud](https://github.com/mohamud1961)

Aether is not a coding-agent product. It is a year-long empirical investigation into the layer between a model and
the world: the loop, tools, context, verification and evaluation that turn a language model into an agent. Over five
harness generations and 151 evaluations, every claimed gain was put against pre-registered predictions, sealed
held-out tasks and row-level audits of the traces. Most claimed gains did not survive that, and the ways they failed
are the main findings.

## The thesis

> **The better the model, the better the system.**

A harness should measure and release model capability, not supply it. Every mechanism is held to one test: *would a
stronger model make this code redundant, or want to override it?* If so, it is a crutch, and it goes. Build the
workbench, never the crutch.

The programme splits an agent run into four roles with hard boundaries:

| Role | Job | Boundary |
|---|---|---|
| **Solver** | Works the task with real tools | Never sees the grader |
| **Verifier** | Checks the actual task state, not the solver's account of it | Read-only; never sees the grader |
| **Harness** | Executes, records and bounds; holds the invariants | Never decides what the task needs |
| **Grader** | Scores the result after the run ends | External; never part of the loop |

> *The model pilots. The harness instruments. The verifier reflects. The ledger remembers. The grader decides.*

Full statement: [docs/VISION.md](docs/VISION.md).

## Research questions

1. **False completion.** Agents finish confidently with wrong work. Can a harness tell a true finish from a false
   one, and who should do the checking: the agent itself, a second model, or the environment?
2. **Verification independence.** What does a verifier need to see, and what must it *not* see, to catch errors the
   solver cannot?
3. **Context economics.** What does context management cost at the level of a whole trajectory, not a single call?
4. **Measurement validity.** When an agent result improves, how often is the improvement real?
5. **Harness or model.** Which failures belong to the harness, and which to the model, and does a lever that helps
   one model help another?

## What we found

**Verification is where a harness adds most, and where it fails most quietly.**
- A completion verifier reported success across 20 runs while executing 0 real checks.
- A reviewer shown the task and the real outputs, but *not* the agent's claims, caught 15 of 18 wrong finishes.
  Shown the claims, it caught 10.
- A requirement ledger, prewritten acceptance checks, a same-model reviewer and a reading judge were all
  tried against false completion. None separated true finishes from false ones well enough to keep; the judge
  scored at chance (AUROC 0.475).

**Models answer pointed questions well, but do not choose to ask them.**
- Shown its own output in a field-aware view and asked whether it was right, a model caught a reversed file 18 of 18
  times. With the file shown raw, it caught it 1 time in 18.
- Inside real runs, the same evidence led to 1 repair in 9.
- Every lever that relied on the model asking itself failed. The open harness question is *who asks, and when*.

**Outcomes are close to deterministic per model and task.**
- The same harness and text gave one model 22 of 22 passes on a task where another model was wrong in nearly every
  run, and the reverse on a second task.
- A lever that only corrects one model's reading of one task is a crutch by the programme's own test.

**Cheaper calls made trajectories more expensive.** Cutting context bytes by 29% raised model calls by 56%. Making
the request prefix cache-stable instead halved cost per run at equal passes. Optimise the trajectory, not the call.

**Most measured wins were measurement artefacts.**
- A "78.5%" batch was a rate-limit storm: 456 of 482 verifier rounds had errored.
- A pre-registered falsifier fired on our own harness on sealed held-out tasks.
- 32 mechanisms were retired on evidence, and the [cemetery](research/cemetery.md) records why each one died.

**Aether holds its own against production agents, at a fraction of the cost.**

| Aether against | Model (Aether / other) | Tasks × runs | Aether | Other | Cost per run (Aether / other) |
|---|---|---|---|---|---|
| Meta CLM agent | GLM-5.3-Flash / same | 13 × 2 | **25 of 26** | 20 of 26 | $0.041 / **$0.026** |
| Terminus 2 | GLM-5.3-Flash / same | 18 runs | 12 of 18 | 12 of 18 | $0.054 / **$0.047** |
| Claude Code | GLM-5.3-Flash / GLM-5.1 | 25 tasks, mean pass rate | 0.64 | 0.64 | **$0.031** / $0.250 |
| Codex | GLM-5.3-Flash / GPT-5.6-Luna | 25 tasks, mean pass rate | 0.64 | 0.77 | **$0.031** / $0.316 |
| Codex | GLM-5.3-Flash / GPT-6-Astra | 25 tasks, mean pass rate | 0.64 | 0.82 | **$0.031** / $1.302 |

Comparisons chosen after the runs; every loss, run count and caveat is in
[research/head-to-head.md](research/head-to-head.md).

Evidence and limits for each finding: [research/findings.md](research/findings.md) and
[research/core/](research/core/).

## Contributions

- **Aether Core** ([aether/core/](aether/core/)): a lean agent runtime in which every turn, tool call, result and
  timing is recorded. It has persistent named terminals, model-managed context, deadline visibility and disposable
  container clones for running checks without touching the graded state.
- **A validated evaluation suite** ([evals/](evals/), [harness_evals/](harness_evals/)): 28 tasks whose graders are
  themselves tested against known-bad states and careless agents. `python -m harness_evals validate-graders evals`
  re-runs those checks.
- **A synthesis of 312 external agent runs** ([research/synthesis/](research/synthesis/)): a mechanism map, a failure
  taxonomy and dossiers across other harnesses.
- **An open research record:** every Gen 5 pre-registration with its results ([research/core/](research/core/)), the
  retired mechanisms ([research/cemetery.md](research/cemetery.md)), and how each finding sits against published work
  ([research/related-work.md](research/related-work.md)).

## Method

- **Pre-registration.** Every experiment states its question, predictions and falsifier before it runs. Results are
  appended without editing the predictions, and failed predictions are recorded as failed.
- **Row-level audits.** Every result is checked against its traces. An audit overturned a published-looking win more
  than once ([case studies](workflows/case-studies/)).
- **Graders are tested too.** Each of the 28 evaluation tasks is validated against known-bad states and careless
  agents before it scores anything ([evals/](evals/)).
- **No Fake Work.** A check that a known-bad case cannot fail is not a check, and a green produced by stubs, mocks or
  shims does not count ([docs/no-fake-work.md](docs/no-fake-work.md)).
- **Clean context.** No benchmark, grader or hidden-test framing ever reaches the model, and tests enforce it.

## Five generations

Each generation tested a different answer to "what should the harness add?" Each was replaced because a measurement
said so.

| Gen | Hypothesis | What ended it |
|---|---|---|
| 1. Planner memory | A planner as external memory for a stateless coding agent | An oracle mount leaked answers; one idea survived: the oracle-free verifier |
| 2. Receipt kernel | A "done" claim needs a receipt; a task profile is generated before the loop | Fake progress: lock-in, circular self-checks, shape-only success |
| 3. Architect, solver, verifier | A model writes the harness config and the solver and verifier prompts | The architect's proof authority was unsound; the verifier ran no real checks |
| 4. Persistent worker, independent verifier | One persistent model owns the task; an independent verifier checks completion | A sealed held-out test did not support the lift claim |
| 5. Aether Core | The model pilots a lean, fully recorded loop; the harness only instruments | Current: the false-completion programme above |

The full arc: [research/generations/](research/generations/).

## The repository

| Folder | What's inside |
|---|---|
| [aether/](aether/) | The harness: Aether Core ([aether/core/](aether/core/)), the current lean loop, and the Gen 4 runtime it replaced |
| [research/](research/) | Findings, generation pages, postmortems, the cemetery, a synthesis of 312 external agent runs, and every Gen 5 pre-registration ([research/core/](research/core/)) |
| [evals/](evals/) | 28 validated evaluation tasks across nine targets, eight evaluation methods, and a catalogue of all 151 evaluations |
| [harness_evals/](harness_evals/) | The evaluation runner: task format, sandboxed runs, grader validity, trial rows, statistics |
| [docs/](docs/) | The vision, architecture layers, engineering standards and the No Fake Work rule |
| [workflows/](workflows/) | How one person ran the programme with a fleet of coding agents: roles, review gates, handoffs, incidents |
| [notebook/](notebook/) | Decisions, turning points and a timeline |

## How the work was done

One principal directed the programme. Coding agents did most of the implementation, analysis and auditing: Codex
from spring, ChatGPT in late summer, and from 8 October Claude in Claude Code, orchestrating Sonnet and Haiku
subagents. Running research this way is itself a multi-agent system, with work packets, review gates, concurrency
limits and failure modes of its own, and it is documented as one in [workflows/](workflows/).

## Quick start

```bash
pip install -e ".[dev]"
python -m pytest -q
python -m harness_evals validate-graders evals
```
