# Public evidence

Aether's public evidence is deliberately small, structured and explicit about selection.

The purpose of this directory is not to make the project look successful by selecting only winning traces. It is to make consequential claims inspectable, preserve negative evidence, and separate **raw traces**, **sealed machine-readable receipts**, **derived public projections**, and **human-readable summaries**.

Machine-readable index: [`MANIFEST.json`](MANIFEST.json)

## Evidence map

| Evidence | Status | Machine-readable | Full raw model/action trace public? | What it is for |
|---|---|---:|---:|---|
| Live public qualification | current repository gate | yes — GitHub workflow | n/a | clean-room software/release proof |
| H10 held-out qualification | complete sealed campaign summary | yes | no | representative mixed held-out evidence |
| `configure-git-webserver` | selected capability/attribution case | yes | **no — trajectory hash preserved** | external pass vs internal review disagreement |
| workspace boundary rejection | selected negative safety-relevant case | yes — sealed-row projection | **no — forensics hash preserved** | one enforced execution boundary |
| Terra + Codex source | external comparator provenance | partial | no | verifies comparator identity/aggregate; exact task row pending |

## 1. `configure-git-webserver` — capability + attribution

[`terminal-bench/configure-git-webserver/`](terminal-bench/configure-git-webserver/)

A GPT-5.6 Luna + Aether run received official reward **1.0** and CTRF **1/1 passed**, while Aether's own review path still ended `verifier_blocked_stalemate` after three verifier path-escape failures.

Why it matters:

- the external evaluator says the task-visible outcome passed;
- the internal harness still failed to close cleanly;
- that makes it useful evidence for the research question: model capability and harness behaviour need to be attributed separately.

The machine-readable result preserves the run ID, source identity and SHA-256 hashes for the trajectory, run record, CTRF and reward. The full 25-file raw bundle is **not** in this public release yet. [`trace-summary.md`](terminal-bench/configure-git-webserver/trace-summary.md) is explicitly a summary, not a substitute for the raw trajectory.

This is a selected case, not a representative benchmark score.

## 2. H10 held-out qualification — negative and positive results together

[`qualification/H10_FINAL_AUDIT_AND_READINESS_VERDICT_20260907.json`](qualification/H10_FINAL_AUDIT_AND_READINESS_VERDICT_20260907.json)

This sealed held-out campaign records **10 raw tasks**, **8 valid rows**, **3 valid passes**, **5 valid grader misses**, and **2 invalid infrastructure/provider rows**. It used one attempt per task, zero benchmark retries, zero reruns, zero substitutions, and no mid-campaign tuning or repair.

The final verdict is intentionally unflattering where the evidence is unflattering:

- Aether runtime mechanical integrity: **ACCEPTED**
- benchmark competitiveness: **NOT DEMONSTRATED**
- performance verdict: **NOT COMPETITIVE ON H10 SAMPLE**

Why publish it: a funding case should survive negative evidence. The next three-month programme is meant to learn what actually improves agent capability, not to defend a predetermined benchmark claim.

## 3. Boundary-held failure — safety-relevant negative evidence

[`safety/workspace-boundary-rejection/`](safety/workspace-boundary-rejection/)

A held-out task includes an attempted read outside the declared `/app` workspace. Aether rejected the action. The run still failed its official evaluator.

The directory now includes [`boundary-rejection-result.json`](safety/workspace-boundary-rejection/boundary-rejection-result.json), a convenience projection of **row 5 from the sealed H10 JSON**. It is labelled as a projection; it is not presented as a raw trajectory.

Why it matters: the boundary held even though relaxing it might have made the run easier. This is evidence of an enforced execution boundary, **not** proof of general AI safety.

## 4. Live software proof

The repository's [Public qualification](https://github.com/mohamud1961/Aether/actions/workflows/public-qualification.yml) workflow reconstructs the public package from tracked files only on a clean GitHub runner, runs publication hygiene, scans the production surface for historical/benchmark contamination, executes the deterministic suite and imports `aether`.

The first current-master cold run reported **701 passed, 1 skipped**, both release guards valid, and a successful cold import.

This is software qualification evidence, not live-agent performance evidence.

## Raw trace publication status

The current public release does **not** pretend that narrative summaries are raw traces.

For the selected Luna/Aether case, the preserved trajectory SHA-256 is:

```text
8a106b0837e042d67384e3bd9366ab0c8b83827d895c7ea46028fe57e8835502
```

The raw bundle remains outside the curated public release pending a separate redaction/publication review. The same principle applies to sealed held-out forensics that may contain provider details, host identifiers or held-out benchmark material.

The rule is simple:

> **If the raw artifact is not public, say so. Never reconstruct prose and label it a raw trace.**

## Evidence rules

Public Aether evidence follows five rules:

1. **External evaluators stay external.** Their outputs may be used after a run for evaluation, but hidden evaluation state is not model input.
2. **Invalid runs stay invalid.** Provider, environment and infrastructure failures are not silently converted into model failures or removed from aggregate records.
3. **Selected cases are labelled selected.** A compelling run is not presented as representative performance.
4. **Causal claims require matched comparisons.** Different model-and-agent configurations can motivate a hypothesis; they do not isolate a harness effect.
5. **Publication form is labelled.** Raw traces, sealed records, derived projections and narrative summaries are not conflated.

The proposed research programme is designed around those rules: same model, same task and environment, comparable budgets, repeated trials, independent evaluation, and selection rules fixed before evaluation.
