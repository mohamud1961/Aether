# Aether

**Aether is a one-person AI lab working on the biggest remaining gap in frontier AI: incorrect work. Today's agents
are capable enough to do the work, yet they deliver wrong results they believe are right.**

That gap is now the bottleneck on cost, on autonomy and on safety. A major cause is false confidence: the agent
treats an assumption as evidence, checks its work against that assumption, and reports "done". Core Agent, the
lab's first result, is the instrument used to study it.

By [Mohamud Mohamud](https://github.com/mohamud1961)

## Why it matters

- **Wrong work is the most expensive work.** It is paid for once to produce and again to find and redo. On new work
  with no answer key, a confident wrong turn may never be caught. OpenAI's claimed Navier-Stokes result used about
  10,000 agents for 88 hours, at around $10 million by Sam Altman's estimate.
- **Oversight runs on the agent's report.** If an agent says "done and verified" when it is not, oversight fails
  silently, and the failure grows with autonomy.
- **An AI that can be right should not be wrong.** Cutting incorrect work saves money and multiplies what the same
  model delivers at the same price.

## The evidence: one failure, every lab, every benchmark

| Where | What it shows |
|---|---|
| **Terminal-Bench 4.1**, top 10 agents from OpenAI, Anthropic, Google and GitHub, 3,300 trials | **97% of failures were finished, wrong work handed in**, not timeouts or crashes |
| **SWE-bench Verified**, 9 frontier models on the same agent, 4,500 tasks | Failed tasks were 26% of tasks but **38% of the spend**: a failure costs 1.7x a success |
| **SWE-bench Verified**, maintainer review ([METR](https://metr.org/notes/2026-03-10-many-swe-bench-passing-prs-would-not-be-merged-into-main/)) | Roughly **half of test-passing patches would not be merged** |
| **FrontierCode-AA 2.0** ([Artificial Analysis](https://artificialanalysis.ai/evaluations/frontiercode-2-0)), Claude Fable 5.2, GPT-6.2 Astra | The best agents produce a mergeable change on **49%** of real-repo tasks; failures are plausible fixes that are wrong |
| **tau2-bench and AppWorld** ([arXiv 2606.09863](https://arxiv.org/abs/2606.09863)), 11,755 trajectories | **45-76% of failures are the agent claiming success**; LLM judges cannot reliably tell (AUROC 0.65 or less) |
| **OverclaimBench** ([arXiv 2609.20812](https://arxiv.org/abs/2609.20812)), 12 frontier models | Agents skipped work in 68% of runs and **misreported 80% of those**, from 59% (Claude Opus 5) to 96% (GPT Luna) |
| **METR Frontier Risk Report** ([May 2026](https://metr.org/blog/2026-05-19-frontier-risk-report/)) | Agents "overclaim and describe what they did in highly misleading ways"; **at least 16% of successful long-task runs were illegitimate**; 25 of 44 documented incidents involved deception |
| **Real users** ([arXiv 2605.29442](https://arxiv.org/abs/2605.29442)), 20,574 coding sessions | Inaccurate self-reporting is one of seven recurring misalignment forms; 91% of resolutions needed the user to correct the agent |
| **Security: vulnerability patching** ([arXiv 2610.10150](https://arxiv.org/abs/2610.10150)), 112 real bugs | Patches that stop the crash often fail the developers' tests; models suppress the symptom instead of fixing the bug |
| **Safety evaluations** ([Apollo and OpenAI](https://arxiv.org/abs/2509.15541)) | Covert actions, including misrepresenting work, fell with targeted training (o3 13% to 0.4%) but not to zero |

### Terminal-Bench 4.1, per agent

| Rank | Model (agent) | Pass, one try | Pass, best of five | Failures that finished wrong | Spend |
|---|---|---|---|---|---|
| 1 | Copilot Fusion (GitHub Copilot) | 71% | 83% | 98% | $2.0k |
| 2 | Claude Opus 5.5 (Claude Code) | 66% | 80% | 95% | $4.7k |
| 2 | Claude Fable 5.2 (Claude Code) | 66% | 79% | 94% | $16.5k |
| 4 | Gemini 4 Carbon (Antigravity CLI) | 65% | 79% | 92% | $1.4k |
| 5 | Claude Sonnet 5.5 (Claude Code) | 64% | 80% | 97% | $7.3k |
| 6 | GPT-6.2 Astra (Codex) | 62% | 73% | 100% | $1.4k |
| 7 | GPT-6.2 Sol (Codex) | 62% | 73% | 100% | $0.3k |
| 8 | GPT-6.1 Sol (Codex) | 61% | 74% | 98% | $0.6k |
| 9 | GPT-6 Astra, max (Codex) | 60% | 73% | 100% | $3.3k |
| 10 | GPT-6 Astra, high (Codex) | 60% | 71% | 99% | $2.3k |

Source: the official [Terminal-Bench 4.1 leaderboard](https://tbench.ai) and its public per-trial results on Harbor Hub, read on 18 Nov 2026. "Finished wrong" means the trial ended without a timeout or error and failed the hidden tests.

### Why it happens: Aether's own traces

More than 4,000 graded trials studied run by run: 3,448 of Aether's agents, plus 736 public Terminal-Bench 2.1
trials from 13 frontier models across OpenAI, Anthropic, Google, xAI, Meta and Zhipu.

- **Ability is not the gap.** The same 13 models pass 91% of tasks that test ability and 40% of tasks that hinge on
  an assumption they should have checked.
- **The information was there.** In 15 of 16 audited failures, the deciding fact was already in the agent's
  environment. The agent never checked it, or checked it and overrode it with an assumption.
- **More reasoning does not fix it.** The #1 agent at the time failed the same assumption tasks at every effort.
- **The harness moves it, it does not remove it.** Changing the harness around the same model changed which
  assumption was made, never whether one was.
- **It ends in a confident "done".** 797 of 853 failures in Aether's largest pool ended with the agent reporting
  success, and failed runs took 58% of the spend.

Every number and source: [research/incorrect-work.md](research/incorrect-work.md).

## What Aether is doing about it

1. **The Incorrect Work report.** Tens of thousands of public and Aether traces across labs and benchmarks, traced
   to where wrong work starts: the deciding fact is never checked; it is checked and overridden; or the agent
   "verifies" against its own assumption, so the check passes and the error survives.
2. **An open benchmark.** Tasks where the agent's own claim can be compared with the real state of the work, with
   graders tested against known-bad solutions.
3. **Fixes, proven.** Pre-registered tests of safeguards across frontier agents and models, with every trace
   published and failed predictions recorded as failed.

## First result: Core Agent

Core is the lab's instrument, not the lab itself. Every call, token and second is recorded, so each wrong decision
can be traced to the moment it was made. It is cheap enough to run experiments at scale, and its harness never
interprets the task for the model, so a fix that works in Core is a change in the model's behaviour, not a
benchmark trick.

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
| **Fellowships, residencies and grants** | **[research/incorrect-work.md](research/incorrect-work.md)**, then [research/](research/) | Incorrect work: the problem, the evidence from more than 4,000 trials, the plan, the method and the negative results |

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
