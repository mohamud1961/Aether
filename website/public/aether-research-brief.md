# Aether — Make the model the limit

## The idea

Aether is a public research AI agent runtime designed around one question: can better models become better agents without adding more hand-built intelligence around the model?

The model remains the source of intelligence. Aether gives it capability, memory, recovery and bounded computer access without putting another intelligence above it.

> The next generation of models needs a next generation of agent.

## Nine months before the ask

Aether has already been built independently for **nine months**, through implementation, live evaluation, failure analysis and repeated redesign. This funding request is for the next experiment, not the first prototype.

## The research question

Can we build an agent where improvements in model intelligence translate directly into improvements in real-world capability—without adding more hand-built intelligence around the model?

Aether is testing a simple design target:

> Better model → better agent.

The goal is to make that relationship dependable rather than accidental.

## What Aether changes

Aether is designed around four principles:

- **Model-led:** the model decides what to do.
- **Extensible:** the model can create or adapt capability when fixed tools are not enough.
- **Persistent:** useful state survives long-running work and recovery.
- **Sandboxed:** powerful actions run inside controlled, isolated environments with explicit permissions and durable internal traces.

The safety boundary is part of the architecture: more useful autonomy inside a controlled computer environment.

## What exists now

The current public release is a working runtime, not a slide deck or proposed architecture.

The live GitHub qualification runs from a depth-1 tracked checkout on a clean Ubuntu runner with no model-provider credentials. Current checks include:

- publication hygiene: **VALID**;
- production-surface guard: **VALID**;
- public evidence manifest bound back to machine-readable receipts;
- **100** production Python modules, with **97 / 100** statically connected to the canonical entrypoints and the three exceptions explicitly accounted for;
- a built `aether-runtime==0.3.0` wheel checked against tracked source and required Harbor/runtime files;
- **701 passed, 1 skipped** deterministic tests;
- clean source import and isolated built-wheel import.

The current tracked release tree is roughly **4.6 MiB**. The much larger Git repository size comes from preserved historical development lineage rather than the current agent runtime.

Inspect the proof directly:

- **Live qualification:** https://github.com/mohamud1961/Aether/actions/workflows/public-qualification.yml
- **Machine-readable evidence index:** https://github.com/mohamud1961/Aether/blob/master/evidence/MANIFEST.json
- **Held-out H10 results, including failures:** https://github.com/mohamud1961/Aether/tree/master/evidence/qualification
- **Current runtime surface:** https://github.com/mohamud1961/Aether/blob/master/docs/RUNTIME_SURFACE.md
- **Evidence pipeline:** https://github.com/mohamud1961/Aether/blob/master/docs/EVIDENCE_PIPELINE.md
- **Known limitations:** https://github.com/mohamud1961/Aether/blob/master/docs/KNOWN_LIMITATIONS.md

## Early evidence

On the same named Terminal-Bench 2.1 challenge, `configure-git-webserver`:

- **GPT-5.6 Terra + Codex** — reported reward **0.00** — **FAILED**
- **GPT-5.6 Luna + Aether** — reward **1.00** — **PASSED**

The challenge requires an autonomous agent to configure Git over SSH, automatically deploy pushed code, and serve the result from a live web server.

Aether's Luna pass is preserved in the public evidence. Terminal-Bench independently verifies the Terra + Codex submission configuration and aggregate leaderboard result; the exact public Terra per-task receipt for this named challenge is still pending.

This is an important signal, not yet a causal head-to-head result. The model-and-agent configurations differ. The next research phase will repeat comparisons under matched conditions.

The public repository also preserves the less flattering aggregate result: the sealed H10 held-out campaign produced **3 passes across 8 validly evaluated rows** and concluded that runtime mechanical integrity was accepted while benchmark competitiveness was **not demonstrated**. Those misses are part of the evidence, not omitted from the funding story.

## The 3-month research programme

### 1. Harden Aether
Remove failures caused by Aether itself so the comparison measures agent capability rather than broken infrastructure.

### 2. Compare fairly
Run matched hard autonomous challenges with the same model, computer environment and time limit across Aether and strong existing agents.

### 3. Simplify aggressively
Test Aether's major mechanisms separately. Keep complexity only when it produces repeatable value.

### 4. Publish the result
Release methods, costs, successes, failures and public-safe traces so the conclusions can be inspected and built on.

## What funding enables

The full three-month research programme is budgeted at **£30,000**:

- **£12,000** — three months of full-time researcher support
- **£8,000** — frontier-model API and experimental compute
- **£3,000** — cloud, VM and evaluation infrastructure
- **£2,000** — reproduction, audit and evidence preparation
- **£1,000** — public research infrastructure and publication tooling
- **£4,000** — additional experimental compute / contingency

The budget is concentrated on researcher time and experiments. No headcount expansion, office costs or marketing are required.

Funding buys the decisive experiments, not the first prototype. Aether already exists.

## Evidence boundary

Complete internal traces are not automatically safe to publish. Historical traces can contain provider details, host identifiers, held-out benchmark material or other content that needs publication review.

The public repository therefore distinguishes raw trajectories, sealed machine-readable receipts, selected trace summaries and derived projections. If a raw trace is not public, the repository says so and preserves provenance hashes/run identifiers where available. A reconstructed narrative is not labelled as a raw trace.

## Why now

Model intelligence is moving faster than the software around it. If the agent becomes the bottleneck, improvements in the model will not translate cleanly into improvements in what the system can do.

Aether is an attempt to build an agent architecture that compounds with model progress instead of being replaced by it.

## Researcher

**Mohamud Mohamud**  
Independent researcher  
**mohamud1961@gmail.com**  
**Code + evidence:** https://github.com/mohamud1961/Aether
