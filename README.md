# Aether

> **Make the model the limit.**

Aether is an open research agent runtime built around one question:

> **As models get better, can their agents get better too—without adding more hand-built intelligence around the model?**

The model owns the thinking and strategy. Aether gives it dependable access to tools, files, computers, memory, recovery and evidence inside a bounded execution environment.

**Research & funding site:** https://aether-worldclass-preview.vercel.app/funding-cards  
**Five-minute diligence path:** [`PUBLIC_REVIEWER_GUIDE.md`](PUBLIC_REVIEWER_GUIDE.md)

## Why this matters

A capable model can still become a weak agent because the software around it loses state, hides an important observation, executes something differently than expected, mishandles recovery, or declares completion for the wrong reason.

Aether is testing whether that surrounding layer can become quieter and more dependable.

The design target is simple:

> **better model → better agent**

and to make that relationship dependable rather than accidental.

## The architectural bet

Aether separates three jobs:

- **The model decides.** It chooses the approach, changes course and decides what capability it needs next.
- **Aether executes and preserves reality.** It exposes current state, carries out actions, keeps durable evidence and makes failures observable.
- **Completion review is independent but not sovereign.** A read-only verifier can challenge a completion claim and surface missing evidence, but it does not own the task strategy.

Official benchmark evaluation stays outside Aether and outside the model's context.

## Early evidence

The clearest current signal is Terminal-Bench 2.1 `configure-git-webserver`.

| Configuration | Model | Result |
|---|---|---:|
| Aether | **GPT-5.6 Luna** (**smaller model**) | **1.00 · PASS** |
| Codex | GPT-5.6 Terra | **0.00 · reported FAIL** on the same named challenge |

Aether's Luna pass is preserved in the public evidence and was reproduced again in the sealed September held-out campaign. Terminal-Bench independently verifies Codex + GPT-5.6 Terra as an official 2.1 leaderboard configuration.

**This is an early signal, not a causal A/B.** The model-and-agent configurations differ, and the exact public Terra per-task receipt has not yet been attached to this repository. The funded experiment is the matched comparison: same underlying model, same task/environment, comparable budgets, repeated trials and independent evaluation.

See [`evidence/terminal-bench/configure-git-webserver/`](evidence/terminal-bench/configure-git-webserver/) for the exact evidence boundary.

## Current qualification status

Aether is a working research system, not a claimed benchmark winner.

The latest sealed held-out campaign produced:

- **10** raw held-out tasks;
- **8** validly evaluated rows;
- **3 / 8** valid passes;
- **0** demonstrated generic Aether production defects in the audited rows;
- intact model continuation on every started valid row;
- **0** model-response parse errors;
- runtime mechanical integrity **accepted**;
- benchmark competitiveness **not demonstrated**.

That mixed result is intentionally public. The research question is whether the runtime can preserve model capability reliably—not whether one current configuration already dominates a leaderboard.

The curated public production suite currently passes:

```text
701 passed, 1 skipped
```

and the fail-closed production-surface guard reports:

```text
VALID
```

See [`docs/QUALIFICATION.md`](docs/QUALIFICATION.md) and [`evidence/qualification/`](evidence/qualification/).

## More autonomy, more control

Aether's safety-relevant bet is that giving the model more freedom over *thinking* does not require giving it unrestricted authority over *acting*.

The production boundary is designed around:

- isolated execution environments;
- explicit capability and permission surfaces;
- one observed action frontier at a time;
- durable action/result receipts;
- evidence provenance and freshness;
- controlled recovery rather than silent retries;
- independent read-only completion review;
- no access to hidden evaluation state;
- complete run traces suitable for post-hoc audit.

The held-out case in [`evidence/safety/workspace-boundary-rejection/`](evidence/safety/workspace-boundary-rejection/) shows Aether rejecting an out-of-workspace action even though the run ultimately failed. That is evidence of an enforced boundary, **not** a claim of general AI safety.

See [`docs/SAFETY_BOUNDARY.md`](docs/SAFETY_BOUNDARY.md).

## Nine months of independent development

Aether has been built independently for **nine months** through implementation, live runs, failure analysis, architecture changes and repeated removal of mechanisms that did not earn their complexity.

The public repository preserves more than **1,300 genuine commits** from the earlier research phase. The current internal research lineage is much larger, but historical run archives, held-out material and private operational data are not being dumped into the public repository without publication review.

See [`docs/DEVELOPMENT_HISTORY.md`](docs/DEVELOPMENT_HISTORY.md).

## Three-month funded experiment

Funding buys the decisive experiment, not the first prototype.

**Programme:** 3 months  
**Full budget:** **£30,000**

**Month 1 — Establish + harden.** Freeze a reproducible baseline and comparison protocol, measure failure modes, and repair only observed Aether-side problems.

**Month 2 — Compare.** Run controlled comparisons using the same underlying model, task/environment and comparable budgets against strong existing agent configurations.

**Month 3 — Simplify + publish.** Remove mechanisms that do not create repeatable value; publish methods, traces, costs, successes, failures and limitations.

See [`docs/RESEARCH_PROGRAMME.md`](docs/RESEARCH_PROGRAMME.md) and the [funding/research site](https://aether-worldclass-preview.vercel.app/funding-cards).

## Production architecture

At a high level:

```text
task
  ↓
controlled task environment
  ↓
Aether runtime
  ↕
model ↔ observed world
  ↓
read-only completion review
  ↓
independent official evaluation
```

Aether does **not** use a production Architect, strategy swarm, benchmark-specific solve packs, hidden evaluation access or a second benchmark runner.

For the implementation-level version, see [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Repository map

The public review surface is deliberately small:

- `aether/` — current production runtime;
- `tests/` — curated deterministic production qualification suite;
- `evidence/` — selected public-safe evidence packets, including negative evidence;
- `docs/` — architecture, safety boundary, qualification, history and research programme;
- `tools/` — release/publication checks;
- `website/` — the funding/research site and brief.

Historical architectures remain in Git history. They are not presented as the current system.

## Quick checks

```bash
python tools/check_public_release.py
python tools/check_production_surface.py
python -m pytest -q tests
```

For a tracked-files-only simulation that excludes untracked workspace state:

```bash
python tools/cold_verify_public_release.py
```

## Researcher

**Mohamud Mohamud** — independent researcher  
[mohamud1961@gmail.com](mailto:mohamud1961@gmail.com)

Aether was built before the funding pitch. The next phase is to turn the strongest signals from nine months of engineering into controlled, inspectable research evidence.
