# Aether

[![Public qualification](https://github.com/mohamud1961/Aether/actions/workflows/public-qualification.yml/badge.svg?branch=master)](https://github.com/mohamud1961/Aether/actions/workflows/public-qualification.yml)

> **Make the model the limit.**

Aether is a public research agent runtime built around one question:

> **As models get better, can their agents get better too—without adding more hand-built intelligence around the model?**

The model owns the thinking and strategy. Aether gives it dependable access to tools, files, computers, memory, recovery and evidence inside a bounded execution environment.

**Five-minute diligence path:** [`PUBLIC_REVIEWER_GUIDE.md`](PUBLIC_REVIEWER_GUIDE.md)  
**Evidence index:** [`evidence/MANIFEST.json`](evidence/MANIFEST.json)  
**Runtime surface:** [`docs/RUNTIME_SURFACE.md`](docs/RUNTIME_SURFACE.md)  
**License:** [`LICENSE`](LICENSE) · [`Third-party notices`](docs/provenance/third_party_notices.md)
**Research & funding site:** https://aether-worldclass-preview.vercel.app/funding-cards

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

### Live clean-room proof

Every push and pull request to `master` is qualified on a clean GitHub runner from a depth-1 tracked checkout. The workflow is provider-free and its third-party Actions are pinned to immutable commit SHAs.

The current release surface is about **4.6 MiB of tracked files**, despite a much larger historical Git lineage. The production Python surface contains **100 modules / 1.83 MB of Python source**; **97 / 100** are statically connected to the canonical entrypoints. The three static exceptions are two task-environment transport bridges that are intentionally uploaded and executed inside Harbor, plus the provider namespace marker—not unexplained alternate runtimes.

The hard gate checks:

```text
publication hygiene: VALID
production surface: VALID
public evidence manifest: internally consistent
benchmark-neutrality identifiers checked: 100
deterministic suite: 701 passed, 1 skipped
clean import: OK
```

Each run also uploads a commit-bound qualification receipt containing the exact Python/package environment, current tracked-tree measurement and complete static import graph.

See [`docs/QUALIFICATION.md`](docs/QUALIFICATION.md), [`docs/RUNTIME_SURFACE.md`](docs/RUNTIME_SURFACE.md), [`evidence/qualification/`](evidence/qualification/) and [`evidence/MANIFEST.json`](evidence/MANIFEST.json).

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
- complete internal run traces suitable for post-hoc audit.

The held-out case in [`evidence/safety/workspace-boundary-rejection/`](evidence/safety/workspace-boundary-rejection/) shows Aether rejecting an out-of-workspace action even though the run ultimately failed. That is evidence of an enforced boundary, **not** a claim of general AI safety.

See [`docs/SAFETY_BOUNDARY.md`](docs/SAFETY_BOUNDARY.md).

## Nine months of independent development

Aether has been built independently for **nine months** through implementation, live runs, failure analysis, architecture changes and repeated removal of mechanisms that did not earn their complexity.

The public repository preserves more than **1,300 genuine commits** from the earlier research phase. The current internal research lineage is much larger, but historical run archives, held-out material and private operational data are not being dumped into the public repository without publication review.

The full Git history is intentionally much larger than the current release tree. Ordinary reviewers can use a depth-1 clone; the historical lineage is there for provenance, not because the current agent needs hundreds of megabytes of code.

See [`docs/DEVELOPMENT_HISTORY.md`](docs/DEVELOPMENT_HISTORY.md) and [`docs/GETTING_STARTED.md`](docs/GETTING_STARTED.md).

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

The current public review surface is deliberately separated by authority:

- `aether/` — current production runtime;
- `tests/` — curated deterministic production qualification suite;
- `evidence/` — selected public-safe evidence packets, sealed aggregate evidence and the machine-readable evidence manifest;
- `docs/` — current architecture, runtime surface, safety boundary, evidence pipeline, limitations, qualification, history and research programme;
- `tools/` — fail-closed release, runtime-surface and evidence checks;
- `.github/workflows/` — live provider-free qualification on current GitHub source;
- `website/` — the funding/research site and brief;
- `research/` — explicitly historical research archive; useful for development context, **not** current production authority;
- `tracking/` — frozen historical provenance/selection authorities retained because changing those files would invalidate their evidence hashes; **not** a current product surface.

Historical architectures remain in Git history. They are not presented as the current system.

## Quick checks

```bash
python tools/check_public_release.py
python tools/check_production_surface.py
python tools/check_public_evidence.py
python tools/release_surface_report.py --text release-surface.txt --json release-surface.json
python tools/runtime_surface_report.py --text runtime-surface.txt --json runtime-surface.json
python -m pytest -q tests
```

For a tracked-files-only simulation that excludes untracked workspace state:

```bash
python tools/cold_verify_public_release.py
```

Or inspect the same cold verification running publicly on GitHub: [Public qualification](https://github.com/mohamud1961/Aether/actions/workflows/public-qualification.yml).

## Evidence publication boundary

Aether keeps complete internal execution evidence, but **complete internal traces are not automatically safe to publish**. The public evidence layer distinguishes:

- sealed machine-readable campaign/result records;
- human-readable case explanations;
- trace summaries;
- raw model/action trajectories.

Where a raw trajectory is not public, the repository says so explicitly and preserves hashes/run identifiers where available. A reconstructed narrative is never presented as a raw trace.

The cold qualification now also fails if the evidence manifest loses referenced files or if key public claims drift from the sealed/result JSON they summarize.

See [`evidence/MANIFEST.json`](evidence/MANIFEST.json) and [`docs/EVIDENCE_PIPELINE.md`](docs/EVIDENCE_PIPELINE.md).

## Researcher

**Mohamud Mohamud** — independent researcher  
[mohamud1961@gmail.com](mailto:mohamud1961@gmail.com)

Aether was built before the funding pitch. The next phase is to turn the strongest signals from nine months of engineering into controlled, inspectable research evidence.
