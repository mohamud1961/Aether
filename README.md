# Aether

> **Make the model the limit.**

Aether is a model-led execution runtime for autonomous computer work. Its research goal is simple: **as models get better, their agents should get better too—without adding another intelligence above the model.**

The model owns cognition and strategy. Aether supplies the execution substrate: tools, files, computer access, state, recovery, evidence and bounded action.

**Research & funding site:** https://aether-worldclass-preview.vercel.app/funding-cards  
**Five-minute diligence path:** [`PUBLIC_REVIEWER_GUIDE.md`](PUBLIC_REVIEWER_GUIDE.md)

```text
MODEL                    AETHER                         WORLD
intelligence             capability                    real work
understand               observe                       code
choose                   act                           services
adapt          ->         remember          ->          applications
                         recover                       computers
                         trace

                         bounded by
                         sandbox · permissions · isolation · evidence
```

## The research question

Can we build an agent where improvements in model intelligence translate directly into improvements in real-world capability—without growing more hand-built intelligence around the model?

Aether is testing a specific architectural split:

- **The model decides.** It chooses the approach, changes course and decides what capability it needs next.
- **Aether executes and preserves reality.** It exposes current state, carries out actions, keeps durable evidence and makes failures observable.
- **Review is independent but not sovereign.** A read-only verifier can challenge completion claims and surface missing evidence; it does not own the task strategy.
- **The benchmark grader stays outside Aether.** Official grading remains external to model context and agent control.

## Why this matters

A capable model can still fail as an agent because the software around it loses state, hides decisive observations, executes something differently than expected, mishandles recovery, or declares success/failure for the wrong reason.

Aether is an attempt to make that surrounding layer quieter and more dependable.

The long-term design target is:

> **better model → better agent**

and to make that relationship dependable rather than accidental.

## Early evidence

The clearest current signal is Terminal-Bench 2.1 `configure-git-webserver`.

| Configuration | Model | Result |
|---|---|---:|
| Aether | **GPT-5.6 Luna** (**smaller model**) | **1.00 · PASS** |
| Codex | GPT-5.6 Terra | **0.00 · reported FAIL** on the same named challenge |

Aether's Luna pass is preserved in the project evidence and was reproduced again in the sealed September held-out campaign. Terminal-Bench independently verifies Codex + GPT-5.6 Terra as an official 2.1 leaderboard configuration.

**This is an early signal, not a causal A/B.** The model-and-agent configurations differ, and the exact public Terra per-task receipt has not yet been attached to this repository. The funded experiment is the matched comparison: same underlying model, same task/environment, comparable budgets, repeated trials and independent grading.

See [`evidence/terminal-bench/configure-git-webserver/`](evidence/terminal-bench/configure-git-webserver/) for the exact evidence boundary.

## Current qualification status

Aether is a working research system, not a claimed benchmark winner.

The latest sealed held-out campaign produced:

- **10** raw held-out tasks;
- **8** validly graded rows;
- **3 / 8** valid passes;
- **0** demonstrated generic Aether production defects in the audited rows;
- intact Solver continuation on every started valid row;
- **0** Solver parse errors;
- runtime mechanical integrity **accepted**;
- benchmark competitiveness **not demonstrated**.

That result is intentionally public-facing context, not something to hide. The research question is whether the runtime can preserve model capability reliably—not whether one current model configuration already dominates a leaderboard.

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

Aether's safety-relevant bet is that model autonomy over *thinking* does not require unbounded autonomy over *acting*.

The production boundary is designed around:

- isolated execution environments;
- explicit capability and permission surfaces;
- one observed action frontier at a time;
- durable action/result receipts;
- evidence provenance and freshness;
- controlled recovery rather than silent retries;
- independent read-only completion review;
- no hidden grader access in model context;
- complete run traces suitable for post-hoc audit.

The held-out safety-relevant case in [`evidence/safety/workspace-boundary-rejection/`](evidence/safety/workspace-boundary-rejection/) shows Aether rejecting an out-of-workspace action even though the run ultimately failed. That is evidence of an enforced boundary, **not** a claim of general AI safety.

See [`docs/SAFETY_BOUNDARY.md`](docs/SAFETY_BOUNDARY.md).

## Nine months of independent development

Aether has been built independently for **nine months** through implementation, live runs, failure analysis, architecture changes and repeated removal of mechanisms that did not earn their complexity.

The existing public repository already contains more than **1,300 genuine commits** from the earlier HarnessEng research phase. The current internal research lineage is much larger, but it is **not being dumped wholesale into the public repository**: historical run archives, held-out benchmark material and private operational data require publication review first.

This public refresh preserves the real public history and promotes the current Aether runtime and selected evidence on top of it.

See [`docs/DEVELOPMENT_HISTORY.md`](docs/DEVELOPMENT_HISTORY.md).

## Three-month research programme

Funding buys the decisive experiment, not the first prototype.

**Month 1 — Establish + harden.** Freeze a reproducible baseline and comparison protocol, measure failure modes, and repair only observed Aether-side problems.

**Month 2 — Compare.** Run controlled comparisons using the same underlying model, task/environment and comparable budgets against strong existing agent configurations.

**Month 3 — Simplify + publish.** Remove mechanisms that do not create repeatable value; publish methods, traces, costs, successes, failures and limitations.

See [`docs/RESEARCH_PROGRAMME.md`](docs/RESEARCH_PROGRAMME.md).

## Production architecture

The current production line is intentionally narrow:

```text
task
  ↓
Harbor lifecycle
  ↓
Aether runtime
  ↕
model ↔ observed world
  ↓
read-only completion review
  ↓
external official grader
```

Aether does **not** use a production Architect, semantic planner, strategy swarm, benchmark-specific solve packs, hidden-grader integration or a second benchmark runner.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Repository map

The current public review surface is deliberately small:

- `aether/` — current production runtime and Harbor adapter;
- `tests/` — curated deterministic production qualification suite;
- `evidence/` — selected public-safe evidence packets, including negative evidence;
- `docs/` — current architecture, safety boundary, qualification, history and research programme;
- `tools/` — release/publication checks;
- `website/` — the funding/research site and brief.

Historical HarnessEng/Aether-2 research remains in Git history. It is not presented as the current architecture.

## Quick checks

```bash
python tools/check_public_release.py
python tools/check_production_surface.py
python -m pytest -q tests
```

For a tracked-files-only simulation that excludes all untracked workspace state:

```bash
python tools/cold_verify_public_release.py
```

The public package is designed so a reviewer can inspect the runtime without access to private benchmark archives or provider credentials.

## Researcher

**Mohamud Mohamud** — independent researcher  
[mohamud1961@gmail.com](mailto:mohamud1961@gmail.com)

Aether was built before the funding pitch. The next phase is to turn the strongest signals from nine months of engineering into controlled, inspectable research evidence.
