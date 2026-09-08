# Aether — five-minute reviewer guide

If you have five minutes, this is the shortest path through the project.

## 1. Start with the thesis

Read [`README.md`](README.md).

Aether asks whether improvements in model intelligence can translate more directly into improvements in agent capability.

The design split is simple:

- **the model owns cognition and strategy**;
- **Aether owns reliable interaction with the computer**: tools, observations, state, recovery, permissions and evidence;
- **official evaluation stays outside the agent**.

The target is:

> **better model → better agent**

without growing a second hidden intelligence around the model.

## 2. Look at the strongest selected case

Read:

[`evidence/terminal-bench/configure-git-webserver/`](evidence/terminal-bench/configure-git-webserver/)

A GPT-5.6 Luna + Aether run received official reward **1.0** on Terminal-Bench 2.1 `configure-git-webserver`.

The important part is not just the pass. Aether's own completion review still ended `verifier_blocked_stalemate` after three path-escape failures even though the task-visible artifact passed externally.

That makes the case useful for the research question:

> the model can produce the right result while the surrounding agent system still mishandles completion.

The case is explicitly labelled selected. It is not presented as representative benchmark performance or as causal proof that Aether is better than another agent.

## 3. Read the negative aggregate evidence

Read:

[`evidence/qualification/`](evidence/qualification/)

The sealed H10 held-out campaign produced:

- 10 raw tasks;
- 8 validly evaluated rows;
- 3 valid passes;
- 5 valid misses;
- 2 invalid infrastructure/provider rows;
- 0 benchmark retries;
- 0 reruns;
- 0 task substitutions;
- no mid-campaign tuning or repair.

Its final verdict says both:

> **Aether runtime mechanical integrity: ACCEPTED**

and:

> **Benchmark competitiveness: NOT DEMONSTRATED**

The project publishes both because the research question is not served by hiding failed rows.

## 4. Check the safety boundary

Read [`docs/SAFETY_BOUNDARY.md`](docs/SAFETY_BOUNDARY.md).

Aether does not equate model autonomy with unrestricted machine authority. The model gets more freedom over **thinking** while **actions** remain permissioned, isolated and inspectable.

Then inspect:

[`evidence/safety/workspace-boundary-rejection/`](evidence/safety/workspace-boundary-rejection/)

During a held-out task, Aether rejected an attempt to read outside the permitted workspace. The task still failed. The case is published because the boundary held even when doing so did not produce a benchmark win.

## 5. See what funding is meant to answer

Read [`docs/RESEARCH_PROGRAMME.md`](docs/RESEARCH_PROGRAMME.md).

Aether has already been built independently for **nine months**. The proposed funded phase is a **three-month, £30,000** research programme—not a request to build the first prototype.

The central experiment uses matched conditions:

- same underlying model;
- same task and environment;
- comparable resource budgets;
- repeated trials fixed in advance;
- independent official evaluation;
- negative results published.

The point is to determine whether the architecture itself helps model capability translate into agent performance.

## 6. Inspect the implementation if you want to go deeper

Read [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

The current production package is [`aether/`](aether/). Historical architectures remain in Git history but are not presented as the current system.

Useful current modules include:

- `aether/kernel.py` — runtime control loop;
- `aether/model_interface.py` — model boundary;
- `aether/real_executor.py` — execution;
- `aether/context_views.py` / `aether/history_query.py` — context and queryable history;
- `aether/inspection_registry.py` / `aether/verifier.py` — evidence and completion review;
- `aether/redaction.py` plus workspace/permission surfaces — execution boundary.

## 7. Verify the implementation baseline

The curated public production suite currently reports:

```text
701 passed, 1 skipped
```

The fail-closed production-surface guard reports `VALID`.

See [`docs/QUALIFICATION.md`](docs/QUALIFICATION.md).

Re-run locally with:

```bash
python tools/check_production_surface.py
pytest -q tests
```

## 8. Understand the development path

Read [`docs/DEVELOPMENT_HISTORY.md`](docs/DEVELOPMENT_HISTORY.md).

Aether has been built independently for nine months. The public Git history already contains more than 1,300 genuine commits; the internal research lineage is much larger.

Commit volume is not treated as proof of quality. The useful part of the history is that it records architecture changes, failed hypotheses, qualification work and evidence-driven simplification before fundraising began.

## Evidence standard

The public evidence directory is intentionally small.

Aether does not use:

- selected traces as representative aggregate performance;
- invalid infrastructure rows as model failures;
- different model-agent pairs as causal proof of a harness effect;
- hidden evaluation state as agent input;
- commit count as a performance metric.

The best place to inspect those rules is [`evidence/README.md`](evidence/README.md).

## Researcher

**Mohamud Mohamud**  
Independent researcher  
**mohamud1961@gmail.com**
