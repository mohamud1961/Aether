# Aether — reviewer guide

If you have five minutes, this is the shortest path through the project.

## 1. Start with the thesis

Read [`README.md`](README.md).

Aether asks whether improvements in model intelligence can translate more directly into improvements in agent capability.

The design split is deliberate:

- **the model owns cognition and strategy**;
- **Aether owns execution reality**: tools, observations, persistence, recovery, permissions, custody and evidence;
- **the benchmark grader remains external**.

The target is:

> **better model → better agent**

without growing a second hidden intelligence around the model.

## 2. Inspect the current architecture

Read [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

The current production package is [`aether/`](aether/), not the historical `harness/aether2` line that exists in earlier Git history.

Useful current modules include:

- `aether/kernel.py` — runtime control loop;
- `aether/model_interface.py` — model boundary;
- `aether/real_executor.py` — execution;
- `aether/context_views.py` / `aether/history_query.py` — context and queryable history;
- `aether/harbor_agent.py` / `aether/harbor_runtime.py` — benchmark integration;
- `aether/inspection_registry.py` / `aether/verifier.py` — evidence and review;
- `aether/redaction.py` / workspace and permission surfaces — execution boundary.

## 3. Check the safety boundary

Read [`docs/SAFETY_BOUNDARY.md`](docs/SAFETY_BOUNDARY.md).

Aether does not equate model autonomy with unrestricted machine authority. The research direction is to give the model greater freedom over **thinking** while keeping **actions** bounded, permissioned, isolated and inspectable.

Then inspect the negative safety-relevant case:

[`evidence/safety/workspace-boundary-rejection/`](evidence/safety/workspace-boundary-rejection/)

The runtime rejected an out-of-workspace read during a held-out task. The task still failed. That case is published because the boundary held even when doing so did not produce a benchmark win.

## 4. Inspect the strongest selected case

Read:

[`evidence/terminal-bench/configure-git-webserver/`](evidence/terminal-bench/configure-git-webserver/)

A GPT-5.6 Luna + Aether run received official reward **1.0**, while Aether's own review path still ended `verifier_blocked_stalemate` after three verifier path-escape failures.

This is useful because it exposes the attribution problem directly:

> the task-visible artifact can be correct while the harness still mishandles completion.

The case is explicitly labelled selected. It is not presented as representative benchmark performance or as proof that Aether is generally better than another agent.

## 5. Read the negative aggregate evidence

Read:

[`evidence/qualification/`](evidence/qualification/)

The sealed H10 held-out campaign produced:

- 10 raw tasks;
- 8 validly graded rows;
- 3 valid passes;
- 5 valid grader misses;
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

## 6. Verify the implementation baseline

The curated public production suite currently reports:

```text
701 passed, 1 skipped
```

The fail-closed production-surface guard reports `VALID` and checks the installed production package against frozen benchmark-neutrality authorities.

See [`docs/QUALIFICATION.md`](docs/QUALIFICATION.md).

Re-run locally with:

```bash
python tools/check_production_surface.py
pytest -q tests
```

## 7. Understand the nine-month development path

Read [`docs/DEVELOPMENT_HISTORY.md`](docs/DEVELOPMENT_HISTORY.md).

Aether has been built independently for nine months. The public Git history already contains more than 1,300 genuine commits; the internal research lineage is much larger. Commit volume is not treated as proof of quality. The value of the history is that it records repeated architecture changes, failed hypotheses, qualification work and evidence-driven simplification before fundraising began.

## 8. See what funding is meant to answer

Read [`docs/RESEARCH_PROGRAMME.md`](docs/RESEARCH_PROGRAMME.md).

The proposed three-month programme is not “build the first prototype.” Aether already exists.

The programme is designed to answer whether the central relationship can become dependable under matched evaluation:

- same underlying model;
- same task and environment;
- comparable budgets;
- repeated trials;
- independent grading;
- selection rules fixed before evaluation;
- negative results published.

## Evidence standard

The public evidence directory is intentionally small.

Aether does not use:

- selected traces as representative aggregate performance;
- invalid infrastructure rows as model failures;
- different model-agent pairs as causal proof of a harness effect;
- hidden benchmark grader state as agent input;
- commit count as a performance metric.

The best place to inspect those rules is [`evidence/README.md`](evidence/README.md).

## Researcher

**Mohamud Mohamud**  
Independent researcher  
**mohamud1961@gmail.com**
