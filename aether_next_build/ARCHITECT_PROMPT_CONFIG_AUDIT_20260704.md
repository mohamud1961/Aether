# Architect Prompt and Config Audit

Date: 2026-07-04

Purpose:
- Audit generated architect outputs across real task surfaces.
- Separate:
  1. architect prompt/config quality in isolation
  2. whether that quality was actually realized in live runs

This distinction matters because a strong architect prompt is not the same thing
as a live harness run that truly benefited from it.

## Executive Conclusion

- The **workbench architect prompt itself is strong**.
- The **architect-only outputs are strong** on the sampled official tasks.
- But the **live runtime realization has been uneven**:
  - `sparql-university` received a rich proof/evidence contract.
  - `filter-js-from-html` and `openssl-selfsigned-cert` reached live runs where
    the proof/evidence contract was effectively empty and the runtime behaved
    more like a default-bounded configuration than a fully task-shaped
    workbench.

So the honest answer is:

```text
Architect prompt quality: strong
Architect config quality in isolated evals: strong
Architect realization quality in live runs: uneven / not yet fully trustworthy
```

## Sources Inspected

Isolated architect evidence:
- [ARCHITECT_AS_SKILL_15_TASK_AUDIT.md](/Users/mohamud/Downloads/harnesseng/aether_next_build/ARCHITECT_AS_SKILL_15_TASK_AUDIT.md)
- [architect_only_eval_20260704_slice6_prompt_upgrade_final/ARCHITECT_EVAL_REPORT.md](/Users/mohamud/Downloads/harnesseng/aether_next_build/architect_only_eval_20260704_slice6_prompt_upgrade_final/ARCHITECT_EVAL_REPORT.md)
- [workbench_hooks.py](/Users/mohamud/Downloads/harnesseng/aether_next_build/aether_next/workbench_hooks.py)

Live-run evidence:
- [STAGE1_TERMINAL_RUN_FULL_AUDIT.md](/Users/mohamud/Downloads/harnesseng/aether_next_build/STAGE1_TERMINAL_RUN_FULL_AUDIT.md)
- verifier packet artifacts under
  [vm_goal_runs](/Users/mohamud/Downloads/harnesseng/aether_next_build/vm_goal_runs)
- historical traces under
  [expanded_real_task_traces_20260630_architect_skill_loop_v1](/Users/mohamud/Downloads/harnesseng/aether_next_build/expanded_real_task_traces_20260630_architect_skill_loop_v1)

## 1. Architect System Prompt Quality

Current workbench architect system prompt lives in:
- [workbench_hooks.py](/Users/mohamud/Downloads/harnesseng/aether_next_build/aether_next/workbench_hooks.py)

Observed characteristics:
- It is no longer a tiny loose planner prompt.
- It is a large compiler-backed skill prompt.
- It explicitly requires:
  - task-specific solver system prompt
  - task-specific verifier system prompt
  - evidence requirements
  - false-positive risks
  - minimum completion evidence
  - typed visible smoke tests when possible
  - local verification limits
  - automatic-memory guidance
  - explicit stop and do-not-submit gates

Judgment:
- **Strong**

Confidence:
- **High**

## 2. Architect-Only Output Quality

The final three-task prompt-upgrade report shows:

| task | overall | solver | verifier | config |
|---|---:|---:|---:|---:|
| filter-js-from-html | 9.67/10 | 10/10 | 9/10 | 10/10 |
| sparql-university | 10/10 | 10/10 | 10/10 | 10/10 |
| openssl-selfsigned-cert | 10/10 | 10/10 | 10/10 | 10/10 |

Evidence:
- [architect_only_eval_20260704_slice6_prompt_upgrade_final/ARCHITECT_EVAL_REPORT.md](/Users/mohamud/Downloads/harnesseng/aether_next_build/architect_only_eval_20260704_slice6_prompt_upgrade_final/ARCHITECT_EVAL_REPORT.md)

Notable details:
- `filter-js-from-html`
  - solver prompt explicitly demands before/after fixture proof
  - verifier prompt rejects source-only claims and demands fixture evidence
  - config contract includes evidence requirements, false-positive risks, and
    minimum completion evidence
- `sparql-university`
  - solver prompt explicitly requires grounding predicates in the TTL
  - verifier prompt is adversarial and evidence-bound
  - config contract is fully populated
- `openssl-selfsigned-cert`
  - solver prompt explicitly requires runtime certificate inspection and
    checker execution
  - verifier prompt demands real artifact/runtime evidence
  - config contract is fully populated

Judgment:
- **Strong**

Confidence:
- **High**

## 3. Did the Live Runs Actually Get That Quality?

This is where the answer changes.

### 3.1 `sparql-university`

Live evidence from Stage 1 audit:
- rich populated `success_definition`
- populated `evidence_requirements`
- populated `false_positive_risks`
- populated proof-contract analysis that correctly identified invented /
  ungrounded predicates and the need to execute against the graph

Judgment:
- **Yes, live run benefited materially from architect quality**

But:
- the solver still failed to recover
- the verifier/no-progress interaction contradicted that good contract

So the architect did its part better than the rest of the loop.

### 3.2 `filter-js-from-html`

Live evidence from Stage 1 audit:
- `architect_path` effectively empty in the canonical failing run audit
- `success_definition` empty
- `evidence_requirements` empty
- proof-contract analysis vacuously passed because there was no task-specific
  contract to enforce

Judgment:
- **No, the live runtime did not realize the isolated architect quality here**

Important distinction:
- The architect-only eval for this task looks good.
- The live run evidence shows that quality did not fully land in the runtime.

### 3.3 `openssl-selfsigned-cert`

Live evidence from Stage 1 audit:
- the row passed end to end
- but the proof/evidence contract was still effectively empty/default-like
  rather than visibly rich in the live runtime audit

Judgment:
- **The task succeeded, but not with strong evidence that architect richness was
  truly realized**

This is a good example of:
- a genuine pass
- but not a clean proof that the architect contract pipeline is uniformly strong

## 4. Root Cause Interpretation

The current evidence suggests:

1. **Prompt quality is not the main weakness anymore.**
2. **Config realization / propagation is a bigger issue than prompt wording.**
3. **A strong architect output can still fail to materially shape the run if the
   runtime path falls back, thins, or records an effectively empty task contract.**

That is why the right statement is not:

> “the architect is weak”

It is closer to:

> “the architect can be strong, but the live harness does not yet realize that
> strength consistently across tasks.”

## 5. Answers to the User’s Core Questions

### Are the architect-created prompts good?

- **Yes, in isolated evaluation they are good to very good.**
- For the sampled three-task prompt-upgrade report: essentially 10/10 quality.

### Do they become the actual solver/verifier prompts?

- In the canonical workbench path, that is the intended design.
- The runtime now enforces architect-authored verifier prompts more strongly than
  before.
- But live-run evidence shows that the overall contract realization has still
  been uneven, so the answer is:
  - **intended: yes**
  - **uniformly realized in practice: not yet fully proved**

### If the model had perfectly followed those isolated prompts, would the tasks likely pass?

- `sparql-university`: **probably much closer, yes**
- `filter-js-from-html`: **likely stronger than the observed live run, yes**
- `openssl-selfsigned-cert`: **yes, and the task did pass anyway**

But:
- the live harness behavior is the real authority
- isolated prompt quality is not the same as runtime success proof

## 6. Bottom Line

The architect prompt/config story is encouraging but not complete:

- **Good news:** the architect prompt itself is no longer the obvious weak link.
- **Bad news:** the runtime still does not realize that quality consistently.

So the current best summary is:

```text
Prompt generation quality: materially improved
Config contract quality: materially improved
Runtime realization consistency: still a live problem
```

That means future fixes should prioritize:
- consistent workbench-config realization
- evidence-contract propagation
- verifier / no-progress / completion alignment

before spending effort trying to make the architect prompt much longer again.
