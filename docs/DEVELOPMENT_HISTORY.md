# Development history

## Nine months before the funding ask

Aether has been under independent development for **nine months**.

The project did not begin as a grant proposal. It began as repeated engineering work on a practical question: why do capable models still fail when they are wrapped in increasingly complicated agent systems?

The current public Git history does **not** cover every month of that work. Earlier exploration predates the current repository lineage. This page separates the project timeline from what Git can independently prove.

## What the public history proves today

Before the September 2026 public refresh, the existing public `master` branch already contained:

- **1,342 genuine commits**;
- public development through **17 June 2026**;
- the earlier HarnessEng runtime/eval/research phase.

The refresh is being built **on top of that public history**, rather than replacing it with a fake new repository or backdated activity.

## What the internal research history contains

The current internal production/research line contains **25,000+ commits** through 7 September 2026.

That number is not presented as a quality metric. Much of the project used fine-grained, agent-assisted engineering checkpoints, run receipts, audits and experimental branches, so commit volume is unusually high.

The quality claims in this repository should be judged from:

- runnable code;
- deterministic tests;
- sealed run evidence;
- external grading;
- falsifiable experiment design;
- explicit negative results and limitations.

The internal line is not being pushed wholesale into the public repository merely to create a larger activity graph. It contains historical run archives, operational artifacts and held-out evaluation material that require publication review.

## Why the public repo went stale

For several months the public repository and the active research system diverged.

The public tree continued to describe **HarnessEng / Aether-2 / orchestration workflows**, while active engineering moved through several rounds of Aether runtime redesign and eventually converged on a much narrower production package.

That created a credibility problem: someone clicking GitHub from a funding page would see a technically substantial repository, but not the project being funded today.

This refresh fixes that mismatch by preserving the existing public history while promoting only the current, public-safe Aether surface.

## Development arc

### Phase 1 — broad harness exploration

Early work explored a large agent-harness design space: context management, tools, memory, evaluation, orchestration, verification, recovery and workflow infrastructure.

The useful outcome was not "more features." It was a growing list of mechanisms that could interfere with the model or make failure attribution ambiguous.

### Phase 2 — evaluation and failure attribution

The project increasingly moved from architecture-by-intuition toward architecture-by-evidence.

Repeated task runs exposed distinctions that became central to Aether:

- model failure versus harness failure;
- task/environment failure versus agent failure;
- internal verifier judgement versus external grader reality;
- useful context versus runtime detail that competes for model attention;
- recovery that restores execution versus recovery that silently takes over strategy.

### Phase 3 — remove hidden cognition

Aether was progressively carved down around a stronger ownership rule:

> **The model owns intelligence. The runtime owns execution reality.**

Architect/planner-style production authority, benchmark-specific strategy and duplicate judgement paths were removed or quarantined from the production line.

### Phase 4 — reality, evidence and bounded execution

Engineering shifted toward the substrate the model genuinely needs:

- observed action/result boundaries;
- durable receipts;
- workspace and capability enforcement;
- provider continuity;
- process/service/file reality;
- evidence provenance and freshness;
- read-only falsification;
- benchmark lifecycle isolation;
- public traceability.

### Phase 5 — production convergence

The active runtime converged to a single top-level `aether/` production package with Harbor as external benchmark lifecycle authority.

The production design intentionally excludes a semantic Architect, planner swarm, task-specific solve packs, hidden-grader integration and a second benchmark runner.

### Phase 6 — controlled qualification

The current line was frozen and tested under preregistered/held-out execution rules.

The latest sealed H10 campaign is deliberately not marketed as a win:

- 10 raw held-out tasks;
- 8 valid rows;
- 3 valid passes;
- 5 valid model/task misses;
- 2 invalid infrastructure/provider rows;
- no mid-campaign tuning;
- no reruns;
- no task substitution;
- zero Solver parse errors;
- no demonstrated generic Aether production defect in the audited rows;
- runtime mechanical integrity accepted;
- benchmark competitiveness not demonstrated.

That is useful evidence because it gives the next research phase a trustworthy baseline rather than a cherry-picked success board.

## A representative positive signal

`configure-git-webserver` has now produced an externally graded **1.00 pass** with Aether and GPT-5.6 Luna in sealed evidence.

The funding story pairs that with a public Terminal-Bench result where Codex + GPT-5.6 Terra failed the same named challenge.

The project treats that as an **anomaly worth testing**, not proof of Aether superiority. The next experiment holds model/task/environment/time fixed so the runtime effect can be measured directly.

## The public refresh itself

The September public refresh is intentionally being committed as small, coherent changes:

- funding-thesis README;
- current architecture;
- bounded/auditable safety boundary;
- three-month research programme;
- development history;
- promoted evidence packets;
- current production runtime;
- deterministic public checks;
- cold-start reviewer path;
- retirement of stale public surfaces.

That makes current progress visible without manufacturing fake historical commits.

## Researcher

**Mohamud Mohamud**  
Independent researcher  
[mohamud1961@gmail.com](mailto:mohamud1961@gmail.com)

The strongest evidence for the nine-month claim is intended to be the accumulated work itself: code, experiments, failure records, architecture changes and the public trail of what survived.
