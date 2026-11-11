# Aether

**A research programme on agent harnesses: what should a harness add to a frontier model, and how would we know?**

By [Mohamud Mohamud](https://github.com/mohamud1961)

Aether is not a coding-agent product. It is a year-long empirical investigation into the layer between a model and
the world: the loop, tools, context, verification and evaluation that turn a language model into an agent. Across
five harness generations, the project catalogues 151 evaluation records. The research includes exploratory and
invalid outcomes as well as pre-registered comparisons, held-out tasks and row-level trace audits; many proposed
mechanisms did not survive selection, and the reasons are documented.

## Empirical work at a glance

- **Evaluation programme:** 151 evaluation records across five generations; the current public suite has 28 tasks
  across nine target areas. Start with the [evaluation catalogue](evals/catalogue.md) and
  [current task suite](evals/README.md).
- **External-agent analysis:** a Deep Synthesis across five source systems and 12+ failure families, including a
  trace study of **312 parseable runs from one external system**, called Harness B. Read the
  [synthesis guide](research/synthesis/README.md) and its
  [18 trace-question families](research/synthesis/harness_b_answered_questions.md).
- **Evaluation method:** pre-registered predictions and sentinels, known-bad and careless-agent controls, held-out
  comparisons, and row-level audits. The methods and their limits are documented in
  [evaluation methods](evals/README.md).

The public repository contains analysis summaries, not the raw 312-run trace bundles or all source captures.
Citations marked `[private-source: ...]` refer to evidence that readers cannot open from this repository. The
published synthesis is behavioral analysis of that corpus, not source-level proof of Harness B's internal design.
No clean, frozen, official benchmark win is claimed in the public record; see the
[generation status](research/generations/README.md).

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

**Retrospective reference-agent comparisons are mixed.**

| Aether against | Model (Aether / other) | Tasks × runs | Aether | Other | Cost per run (Aether / other) |
|---|---|---|---|---|---|
| Meta CLM agent | GLM-5.3-Flash / same | 13 × 2 | **25 of 26** | 20 of 26 | $0.041 / **$0.026** |
| Terminus 2 | GLM-5.3-Flash / same | 18 runs | 12 of 18 | 12 of 18 | $0.054 / **$0.047** |
| Claude Code | GLM-5.3-Flash / GLM-5.1 | 25 tasks, mean pass rate | 0.64 | 0.64 | **$0.031** / $0.250 |
| Codex | GLM-5.3-Flash / GPT-5.6-Luna | 25 tasks, mean pass rate | 0.64 | 0.77 | **$0.031** / $0.316 |
| Codex | GLM-5.3-Flash / GPT-6-Astra | 25 tasks, mean pass rate | 0.64 | 0.82 | **$0.031** / $1.302 |

These comparisons were chosen after the runs. The table shows lower Aether costs in the listed Claude/Codex
comparisons, but higher costs against Meta CLM and Terminus; pass results also vary by comparison. Model versions,
task versions and cost accounting differ. The [comparison record](research/head-to-head.md) lists losses, run counts
and caveats; these rows do not establish a general performance or cost advantage.

Evidence and limits for each finding: [research/findings.md](research/findings.md) and
[research/core/](research/core/).

## Contributions

- **Aether Core** ([aether/core/](aether/core/)): a lean agent runtime in which every turn, tool call, result and
  timing is recorded. It has persistent named terminals, model-managed context, deadline visibility and disposable
  container clones for running checks without touching the graded state.
- **A public evaluation suite** ([evals/](evals/), [harness_evals/](harness_evals/)): 28 task definitions with
  graders, references, known-bad states and careless-agent controls. The validation methods and their current
  evidence boundary are documented in [the measurement-validity record](evals/methods/measurement-validity.md).
  `python -m harness_evals validate-graders <task-directory>` runs the grader check for one task. Pointing it at
  `evals/` also discovers archived task manifests, so that command is not a check of just the current 28 tasks.
- **Cross-system synthesis** ([research/synthesis/](research/synthesis/)): 312 parseable runs from Harness B plus
  mechanism and failure-family analysis across other harnesses.
- **An open research record:** every Gen 5 pre-registration with its results ([research/core/](research/core/)), the
  retired mechanisms ([research/cemetery.md](research/cemetery.md)), and how each finding sits against published work
  ([research/related-work.md](research/related-work.md)).

## Method

- **Pre-registration.** Selected comparison studies state their question, predictions and falsifier before they run.
  Results are appended without editing those predictions, and failed predictions are recorded as failed.
- **Row-level audits.** Audits of scored boards have overturned published-looking wins and exposed invalid rows
  ([case studies](workflows/case-studies/)). The historical catalogue includes evidence at different levels.
- **Graders are testable too.** The current task packages include known-bad and careless-agent controls. The
  available `validate-graders` command checks reference pass, untouched-state rejection, known-bad rejection,
  determinism and Python-level grader file access; the repository records that a fresh suite-wide run was not
  evidenced in its measurement-validity snapshot ([evals/](evals/)).
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
| [evals/](evals/) | 28 current task definitions across nine targets, eight documented evaluation methods, and a catalogue of 151 historical evaluation records |
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
