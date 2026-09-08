# Public evidence

Aether's public evidence is deliberately small.

The purpose of this directory is not to make the project look successful by selecting only winning traces. It is to make a few consequential claims inspectable and to publish negative evidence when it materially changes the interpretation.

## Start here

### 1. `configure-git-webserver` — capability + attribution

[`terminal-bench/configure-git-webserver/`](terminal-bench/configure-git-webserver/)

A GPT-5.6 Luna + Aether run received official reward **1.0** and CTRF **1/1 passed**, while Aether's own review path still ended `verifier_blocked_stalemate` after three verifier path-escape failures.

Why it matters:

- the external grader says the task-visible outcome passed;
- the internal harness still failed to close cleanly;
- that makes it useful evidence for the research question: model capability and harness behaviour need to be attributed separately.

This is a selected case, not a representative benchmark score.

### 2. H10 held-out qualification — negative and positive results together

[`qualification/H10_FINAL_AUDIT_AND_READINESS_VERDICT_20260907.json`](qualification/H10_FINAL_AUDIT_AND_READINESS_VERDICT_20260907.json)

This sealed held-out campaign records **10 raw tasks**, **8 valid rows**, **3 valid passes**, **5 valid grader misses**, and **2 invalid infrastructure/provider rows**. It used one attempt per task, zero benchmark retries, zero reruns, zero substitutions, and no mid-campaign tuning or repair.

The final verdict is intentionally unflattering where the evidence is unflattering:

- Aether runtime mechanical integrity: **ACCEPTED**
- benchmark competitiveness: **NOT DEMONSTRATED**
- performance verdict: **NOT COMPETITIVE ON H10 SAMPLE**

Why publish it: a funding case should survive negative evidence. The next three-month programme is meant to learn what actually improves agent capability, not to defend a predetermined benchmark claim.

### 3. Boundary-held failure — safety-relevant behaviour

[`safety/workspace-boundary-rejection/`](safety/workspace-boundary-rejection/)

A held-out task includes an attempted read outside the declared `/app` workspace. Aether rejected the action. The run still failed its official grader.

Why it matters: the boundary held even though relaxing it might have made the run easier. This is evidence of an enforced execution boundary, **not** proof of general AI safety.

## Evidence rules

Public Aether evidence follows four rules:

1. **External graders stay external.** Their outputs may be used after a run for evaluation, but hidden grader state is not model input.
2. **Invalid runs stay invalid.** Provider, environment and infrastructure failures are not silently converted into model failures or removed from aggregate records.
3. **Selected traces are labelled selected.** A compelling trace is not presented as representative performance.
4. **Causal claims require matched comparisons.** Different model-and-agent configurations can motivate a hypothesis; they do not isolate a harness effect.

The proposed research programme is designed around that last rule: same model, same task and environment, comparable budgets, repeated trials, independent grading, and selection rules fixed before evaluation.
