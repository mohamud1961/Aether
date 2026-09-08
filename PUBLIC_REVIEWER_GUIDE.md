# Aether — five-minute reviewer guide

[![Public qualification](https://github.com/mohamud1961/Aether/actions/workflows/public-qualification.yml/badge.svg?branch=master)](https://github.com/mohamud1961/Aether/actions/workflows/public-qualification.yml)

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

## 2. Verify that the current repo is real and green

Open the live [Public qualification](https://github.com/mohamud1961/Aether/actions/workflows/public-qualification.yml).

The current workflow takes tracked public files only, installs the package on a clean GitHub runner, checks publication hygiene, scans the production package for historical/benchmark contamination, runs the deterministic suite and imports Aether.

The first current-master cold run reported:

```text
329 tracked public files
PUBLIC_RELEASE_VALID
production surface: VALID
100 production Python modules scanned
100 benchmark-neutrality task identifiers checked
701 passed, 1 skipped
AETHER_IMPORT_OK
```

No private development workspace or model-provider credentials are required for this qualification path.

Read [`docs/QUALIFICATION.md`](docs/QUALIFICATION.md) for what that does—and does not—prove.

## 3. Inspect the evidence map before any selected case

Open [`evidence/MANIFEST.json`](evidence/MANIFEST.json), then [`evidence/README.md`](evidence/README.md).

The evidence layer labels whether something is:

- a complete sealed campaign record;
- a selected case;
- a machine-readable projection of a sealed row;
- a narrative trace summary;
- or a raw trajectory.

The public release does **not** label reconstructed prose as a raw trace. Where a full trajectory is not public, that limitation is explicit and hashes/run identifiers are preserved where available.

## 4. Look at the strongest selected case

Read:

[`evidence/terminal-bench/configure-git-webserver/`](evidence/terminal-bench/configure-git-webserver/)

A GPT-5.6 Luna + Aether run received official reward **1.0** on Terminal-Bench 2.1 `configure-git-webserver`.

The important part is not just the pass. Aether's own completion review still ended `verifier_blocked_stalemate` after three path-escape failures even though the task-visible artifact passed externally.

That makes the case useful for the research question:

> the model can produce the right result while the surrounding agent system still mishandles completion.

The machine-readable result preserves the original run ID and hashes for the trajectory, run record, CTRF and reward. The full raw trajectory is not public yet and the repo says so.

The case is explicitly selected. It is not presented as representative benchmark performance or as causal proof that Aether is better than another agent.

## 5. Read the negative aggregate evidence

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

## 6. Check the execution boundary

Read [`docs/SAFETY_BOUNDARY.md`](docs/SAFETY_BOUNDARY.md).

Then inspect:

[`evidence/safety/workspace-boundary-rejection/`](evidence/safety/workspace-boundary-rejection/)

During a held-out task, Aether rejected an attempt to read outside the permitted workspace. The task still failed. The case is published because the boundary held even when doing so did not produce a benchmark win.

The machine-readable JSON beside the case is explicitly a projection of sealed H10 row 5, not a fabricated raw trace.

## 7. Inspect the implementation

Read [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

The current production package is [`aether/`](aether/). The production-surface guard scans **100 current Python modules** and fail-closes on legacy runtime imports, old Architect/Workbench cognition modules, benchmark task IDs, checkout-specific paths, non-loopback hard-coded IPs, Harbor identity drift and launch-schema drift.

Useful current modules include:

- `aether/launch.py` — strict one-task launch/admission and custody boundary;
- `aether/harbor_agent.py` — thin Harbor adapter;
- `aether/harbor_runtime.py` — Harbor-facing runtime wiring;
- `aether/kernel.py` — model/action/review control loop;
- `aether/model_interface.py` — exact model-facing interface capture;
- `aether/execution.py` / `aether/real_executor.py` — external action execution;
- `aether/ledger.py` / `aether/receipts.py` — durable receipts/evidence state;
- `aether/context_views.py` / `aether/history_query.py` — context and queryable history;
- `aether/verifier.py` and verifier modules — independent read-only completion review;
- `aether/redaction.py` — evidence publication boundary.

The canonical package is `aether-runtime==0.3.0`; Harbor integration is pinned to `0.20.0`; the console entrypoint is `aether = aether.launch:main`.

## 8. See what funding is meant to answer

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

## 9. Understand the development path

Read [`docs/DEVELOPMENT_HISTORY.md`](docs/DEVELOPMENT_HISTORY.md).

The public Git history already contains more than 1,300 genuine commits from the earlier research phase; the internal research lineage is much larger.

Commit volume is not treated as proof of quality. The useful part of the history is that it records architecture changes, failed hypotheses, qualification work and evidence-driven simplification before fundraising began.

## Evidence standard

Aether does not use:

- selected traces as representative aggregate performance;
- invalid infrastructure rows as model failures;
- different model-agent pairs as causal proof of a harness effect;
- hidden evaluation state as agent input;
- commit count as a performance metric;
- narrative reconstructions as raw traces.

The machine-readable index is [`evidence/MANIFEST.json`](evidence/MANIFEST.json).

## Researcher

**Mohamud Mohamud**  
Independent researcher  
**mohamud1961@gmail.com**
