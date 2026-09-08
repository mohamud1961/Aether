# Aether: make the model the limit

## The idea

Aether is a next-generation AI agent architecture designed so better models become better agents.

The model remains the source of intelligence. Aether is designed to provide capability, memory, recovery and bounded computer access without putting another intelligence above it. These execution boundaries are research and engineering properties to test, not a demonstrated general safety guarantee.

> The next generation of models needs a next generation of agent.

## The research question

Can we build an agent where improvements in model intelligence translate directly into improvements in real-world capability, without adding more hand-built intelligence around the model?

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

On the same named Terminal-Bench 2.x challenge, `configure-git-webserver`:

- **GPT-5.6 Terra + Codex**: reward **0.00** in the [verified public Harbor trial receipt](https://hub.harborframework.com/jobs/77fc16b9-8db9-4d61-a172-dba037aba20b/trials/34c57d03-071d-449d-8a77-3add87915162); the exposed trial status is **completed**
- **GPT-5.6 Luna + Aether**: reward **1.00**, **PASSED**

The challenge requires an autonomous agent to configure Git over SSH, automatically deploy pushed code, and serve the result from a live web server.

The public Aether case note preserves the Luna records and their limitations: the H10 held-out row is marked `VALID_PASS`, while the older 25 August row records an official pass alongside an internal `verifier_blocked_stalemate` after three verifier path-escape failures. See the [case README](https://github.com/mohamud1961/Aether/blob/master/evidence/terminal-bench/configure-git-webserver/README.md), [structured result](https://github.com/mohamud1961/Aether/blob/master/evidence/terminal-bench/configure-git-webserver/aether-luna-result.json) and [trace summary](https://github.com/mohamud1961/Aether/blob/master/evidence/terminal-bench/configure-git-webserver/trace-summary.md).

The exact Terra trial receipt establishes the named task, model, agent version, reasoning effort, completed status and official reward exposed by Harbor. It does not expose a causal failure explanation. The two configurations differ in model, agent, versions, environment and exact run conditions, so this brief does not establish a causal comparison. [Terminal-Bench submission 115](https://github.com/harbor-framework/terminal-bench-2-1/pull/115) remains separate aggregate context and is not used as the source of this task-level reward.

This selected example is not a representative benchmark score or a causal comparison. The research case remains valid without assuming this comparison establishes any advantage. The next phase tests the hypothesis under controlled conditions.

## The 3-month research programme

### 1. Harden Aether
Establish a reproducible baseline and freeze the comparison protocol. Measure and classify failures caused by the model, provider, environment and harness. Make targeted repairs without excluding those failures from the record.

### 2. Compare fairly
Run repeated matched challenges using the same model, task versions, computer environment and comparable time and spending budgets. Allow capable baselines to create tools as well. Include all tool-building, review and recovery costs. Fix selection rules before evaluation; use separate development and held-out tasks.

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

Nine months of independent, self-funded work precede this request. Funding enables a focused investigation; no positive benchmark result is promised or required before the work is supported.

Support should include paid research time as well as the experiments and infrastructure required to run the programme. I am seeking non-equity support with independence over experimental choices. The initial proposed commitment is three months, with any continuation agreed separately. A smaller award can fund a bounded first study; a larger award can fund a broader comparison or independent replication. The final amount, permitted spending and deliverables will be agreed with the funder. No itemised budget is asserted until actual costs are established.

## Why now

Model intelligence is moving faster than the software around it. If the agent becomes the bottleneck, improvements in the model will not translate cleanly into improvements in what the system can do.

Aether is an attempt to build an agent architecture that compounds with model progress instead of being replaced by it.

## Researcher

**Mohamud Mohamud**  
Independent researcher  
**mohamud1961@gmail.com**
