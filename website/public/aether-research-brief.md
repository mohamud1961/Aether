# Aether — Make the model the limit

## The idea

Aether is a next-generation AI agent architecture designed so better models become better agents.

The model remains the source of intelligence. Aether gives it capability, memory, recovery and safe computer access without putting another intelligence above it.

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
- **Sandboxed:** powerful actions run inside controlled, isolated environments with explicit permissions and complete traces.

The safety boundary is part of the architecture: more useful autonomy inside a controlled computer environment.

## Early evidence

On the same named Terminal-Bench 2.1 challenge, `configure-git-webserver`:

- **GPT-5.6 Terra + Codex** — reward **0.00** — **FAILED**
- **GPT-5.6 Luna + Aether** — reward **1.00** — **PASSED**

The challenge requires an autonomous agent to configure Git over SSH, automatically deploy pushed code, and serve the result from a live web server.

The Terra + Codex result is publicly reported by Terminal-Bench. The Luna + Aether result is preserved in Aether's run evidence.

This is an important signal, not yet a causal head-to-head result. The model-and-agent configurations differ. The next research phase will repeat comparisons under matched conditions.

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

Funding supports a focused **3-month research programme**:

- dedicated researcher runway
- frontier-model API and compute costs
- matched Terminal-Bench and agent comparisons
- evaluation infrastructure
- trace preparation and public evidence
- publication and replication work

Funding buys the decisive experiments, not the first prototype. Aether already exists.

## Why now

Model intelligence is moving faster than the software around it. If the agent becomes the bottleneck, improvements in the model will not translate cleanly into improvements in what the system can do.

Aether is an attempt to build an agent architecture that compounds with model progress instead of being replaced by it.

## Researcher

**Mohamud Mohamud**  
Independent researcher  
**mohamud1961@gmail.com**
