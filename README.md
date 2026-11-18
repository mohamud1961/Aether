# Aether

**Aether is a one-person AI lab working on false confidence in AI agents: why even frontier agents treat an
assumption as evidence, and report "done" when the work is wrong.**

Core Agent was the first breakthrough: an agent 26% cheaper than Codex on Terminal-Bench 2.1, on the same model.
The bigger challenge is the one Aether is going after: making an agent's "done" something you can trust.

By [Mohamud Mohamud](https://github.com/mohamud1961)

## The problem

Agents now run long jobs with nobody watching, then report back that the work is finished and checked. Oversight
depends on that report being true. Aether's question is when it is, and why it so often is not.

- **Thousands of traces.** 3,448 graded trials of Aether's own agents, plus 736 public trials from frontier agents,
  studied trial by trial, with the decision rule for each experiment fixed before it ran.
- **It is a frontier problem, not a small-model one.** Across 736 public Terminal-Bench 2.1 trials from 22
  submissions and 13 models, the top-ranked agent (Codex on GPT Astra) failed all 25 runs on two tasks, at every
  reasoning effort. Other frontier models failed the same tasks with the same reading.
- **The information was there.** In 15 of 16 audited failures, the fact that decided the task was already in the
  agent's environment. The agent either never checked it, or checked it and overrode it with an assumption, and
  then reported success.
- **Harness patches move it, they do not remove it.** Changing the harness around the same model changed which
  assumption was made, never whether one was. Verifiers, requirement ledgers, prewritten checks and a reading judge
  were all tested against false completion and none was good enough to keep (details below).

Summary and evidence: [research/false-confidence.md](research/false-confidence.md).

## What Aether is doing about it

1. **Measure it.** An open false-confidence benchmark: tasks where the agent's own claim can be compared with the
   real state of the work, using graders that are themselves tested against known-bad solutions.
2. **Explain it.** A trace-level map of where false confidence enters: the deciding fact is never checked; it is
   checked and overridden; or the agent "verifies" with a check built on the same assumption, so the check passes
   and the error survives.
3. **Test fixes honestly.** Pre-registered tests of safeguards across frontier agents and models, with every trace
   published and failed predictions recorded as failed.

## First result: Core Agent

Core is a product of the lab, not the lab itself: a lean, fully recorded agent built to make experiments cheap and
to show the research ships.

Head to head with Codex on Terminal-Bench 2.1, both on GPT Luna: **25/25 tasks passed each, and Core cost 26%
less** ($0.416 against $0.563). [The comparison](https://github.com/mohamud1961/core-agent/tree/main/benchmarks).

Real runs with GPT Luna, graded afterwards by hidden tests, at list prices. Chosen examples; details in
[RUNS.md](https://github.com/mohamud1961/core-agent/blob/main/RUNS.md).

| Job | Time | Cost |
|---|---|---|
| Bank capital calculation under EU banking rules, with an Excel workbook of the workings | 17m 15s | $0.085 |
| A graphic rebuilt as a layout config that renders pixel-identical | 26m 42s | $0.085 |
| A 3D FreeCAD part built from an engineering drawing | 12m 34s | $0.051 |
| 17 scanned documents sorted, with invoice totals and VAT summarised | 5m 44s | $0.021 |
| A COBOL program rewritten in Python, matching byte for byte | 4m 20s | $0.028 |

Code, quickstart and how it is built: **[github.com/mohamud1961/core-agent](https://github.com/mohamud1961/core-agent)**.

## Pick your path

| You are | Start here | What you will find |
|---|---|---|
| **Hiring AI engineers** (startups, product teams) | **[Core Agent](https://github.com/mohamud1961/core-agent)** | The cost comparison with Codex, real runs, a 60-second quickstart, how it is built and tested |
| **Hiring research engineers** (labs, senior roles) | Read on, then [Core Agent](https://github.com/mohamud1961/core-agent) and [research/findings.md](research/findings.md) | How the engineering and the research fit, and the evidence behind each design choice |
| **Fellowships, residencies and grants** | **[research/false-confidence.md](research/false-confidence.md)**, then [research/](research/) | The problem, the evidence from thousands of traces, the plan, the method and the negative results |

## At a glance

| | |
|---|---|
| **The agent** | Core: about 23,000 lines of Python in 120 modules, 174 test files, every call, token and second recorded |
| **Real work** | Hard tasks graded by hidden tests, from EU bank capital rules to CAD from a drawing, for $0.005 to $0.20 a job |
| **The research** | Five harness generations, 151 evaluation records, 32 retired mechanisms with the evidence that retired them |
| **External evidence** | A trace study of 312 runs from another agent system, across 12+ failure families |
| **Method** | Written predictions before each run, held-out checks, known-bad controls, row-level trace audits |
| **Build record** | About 840 commits with their real dates, Core's 373 among them |

## How the two fit together

Core is the working agent. The research is how it got that way. Every change to Core starts as a small,
switchable experiment with a written prediction, runs on real tasks, and is kept only if the numbers hold up on
tasks it was not tuned on. Ideas that do not earn their place are removed quickly and cheaply, and the record of
why is kept. The research is the evidence behind each design choice; Core is the proof that the research ships.

- How Core is built: [BUILDING.md](https://github.com/mohamud1961/core-agent/blob/main/BUILDING.md)
- What was tried, kept and removed: [EXPERIMENTS.md](https://github.com/mohamud1961/core-agent/blob/main/EXPERIMENTS.md)
- The research findings: [research/findings.md](research/findings.md)

# The research

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

- **Core Agent** ([core-agent](https://github.com/mohamud1961/core-agent)): the agent. A lean runtime in which every turn, tool call, result and timing is
  recorded, with persistent named terminals, model-managed context, deadline visibility and disposable container
  clones for running checks without touching the graded state.
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
| [core-agent](https://github.com/mohamud1961/core-agent) | **Core Agent**, in its own repo: package, tests, real runs and build notes |
| [aether/](aether/) | The Gen 4 runtime that Core replaced, kept for reference |
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

Core, the agent (Python 3.12+, [uv](https://docs.astral.sh/uv/)):

```bash
cd core && uv sync --frozen
uv run python examples/offline_smoke.py
uv run pytest -q
```

The research tools and evaluation suite (Python 3.11+):

```bash
pip install -e ".[dev]"
python -m pytest -q
python -m harness_evals validate-graders evals
```
