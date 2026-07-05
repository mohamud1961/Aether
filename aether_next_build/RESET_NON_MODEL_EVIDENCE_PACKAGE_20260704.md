# Aether-Next Reset Non-Model Evidence Package

Date: 2026-07-04

Purpose:
- Consolidate the non-model evidence completed before the single planned
  real VM task attempt.
- Make clear what has actually been proved versus what still depends on a
  model-backed run.

This package covers:
- Claude Tasks 1, 3, 4 closeout
- solver command-output visibility
- reconfigure failure surfacing
- verifier-only evals
- deterministic EnvMap audit
- EnvMap row-confidence spot checks
- architect prompt/config audit
- certified-path governance quarantine

## Executive Summary

Before any new real task attempt, the reset plan has already proved:

1. Solver command outputs are visible in the real kernel loop.
2. Failed workbench reconfigure surfaces as explicit config invalidity rather
   than fake generic recovery.
3. Verifier-only post-correction behavior is stronger and more evidence-bound
   in deterministic/fake evals.
4. The deterministic EnvMap audit is useful and row-mechanically trustworthy for
   the checked sample, with an interpretation caveat for output-mismatch rows.
5. Architect prompt/config generation is now strong in isolated evaluation.
6. Certified/default public run surfaces now quarantine reference architect
   modes instead of silently treating them as normal canonical execution.

What is **not** yet proved:

1. That a real model-backed task attempt now converts these improvements into a
   better official task outcome.
2. That the remaining legacy/reference internals are fully removed rather than
   merely fenced off from certified/default execution.
3. That architect quality is realized consistently across live tasks, rather
   than strongly in isolation and unevenly in runtime.

## Evidence Board

### A. Claude Tasks 1, 3, 4 closeout

Artifact:
- [CLAUDE_TASKS_1_3_4_ADVERSARIAL_CLOSEOUT_20260704.md](/Users/mohamud/Downloads/harnesseng/aether_next_build/CLAUDE_TASKS_1_3_4_ADVERSARIAL_CLOSEOUT_20260704.md)

Bottom line:
- Task 1: accepted
- Task 3: accepted
- Task 4: accepted with remaining legacy-quarantine work

### B. Solver command-output visibility

Evidence:
- [test_vnext_memory_context_verifier.py](/Users/mohamud/Downloads/harnesseng/aether_next_build/tests/test_vnext_memory_context_verifier.py)
- [test_vnext_configurability.py](/Users/mohamud/Downloads/harnesseng/aether_next_build/tests/test_vnext_configurability.py)

Key proof:
- Live-kernel regression shows second-turn solver context contains
  `command_results` and the observed token `PROOF_TOKEN=visible-now`.

Status:
- **Proved**

### C. Reconfigure failure surfacing

Evidence:
- [kernel.py](/Users/mohamud/Downloads/harnesseng/aether_next_build/aether_next/kernel.py)
- [kernel_config.py](/Users/mohamud/Downloads/harnesseng/aether_next_build/aether_next/kernel_config.py)
- [test_vnext_configurability.py](/Users/mohamud/Downloads/harnesseng/aether_next_build/tests/test_vnext_configurability.py)

Key proof:
- failed workbench reconfigure emits explicit `config_invalid`
- no fake generic fallback receipt is emitted
- prior good workbench prompt remains active

Status:
- **Proved**

### D. Verifier-only evals

Artifacts:
- `aether_next_build/verifier_only_eval_20260704_postfix_fake/`
- `aether_next_build/verifier_prompt_replay_eval_postfix/`

Observed:
- deterministic fake verifier-only eval parses and classifies cases cleanly
- architect prompt replay improves evidence-bound/actionable verifier behavior

Status:
- **Proved in deterministic/fake mode**

Not yet proved:
- full model-backed verifier behavior on a fresh post-closeout VM run

### E. EnvMap audit across official task index

Artifacts:
- [ENVMAP_AUDIT_REPORT.md](/Users/mohamud/Downloads/harnesseng/aether_next_build/envmap_audit_20260704_goal_v1/ENVMAP_AUDIT_REPORT.md)
- `aether_next_build/envmap_audit_20260704_goal_v1/envmap_audit_summary.json`
- `aether_next_build/envmap_audit_20260704_goal_v1/envmap_audit_rows.json`

Headline findings:
- indexed tasks in this checkout: **90**
- sparse visible workspace: **59**
- deliverable pressure with few input hints: **55**
- prompt-declared output not visible: **2**
- heavy visible test surface: **1**

Status:
- **Strong aggregate planning evidence**

### F. EnvMap row-confidence spot checks

Artifact:
- [ENVMAP_SPOTCHECK_20260704.md](/Users/mohamud/Downloads/harnesseng/aether_next_build/ENVMAP_SPOTCHECK_20260704.md)

Spot-checked tasks:
- `adaptive-rejection-sampler`
- `constraints-scheduling`
- `schemelike-metacircular-eval`
- `fix-git`

Result:
- row mechanics hold up
- main interpretation caveat:
  `prompt_declared_output_not_visible` is often a task-shape signal, not by
  itself a harness surfacing defect

Status:
- **Row-level confidence materially improved**

### G. Architect prompt/config audit

Artifact:
- [ARCHITECT_PROMPT_CONFIG_AUDIT_20260704.md](/Users/mohamud/Downloads/harnesseng/aether_next_build/ARCHITECT_PROMPT_CONFIG_AUDIT_20260704.md)

Result:
- prompt generation quality: strong
- isolated config contract quality: strong
- live runtime realization: uneven

Status:
- **Prompt quality proved stronger than runtime realization**

### H. Certified/default governance quarantine

Evidence:
- [run_adapter.py](/Users/mohamud/Downloads/harnesseng/aether_next_build/aether_next/run_adapter.py)
- [run_pilot.py](/Users/mohamud/Downloads/harnesseng/aether_next_build/run_pilot.py)
- [docker_runner.py](/Users/mohamud/Downloads/harnesseng/aether_next_build/aether_next/runners/docker_runner.py)
- [test_run_adapter.py](/Users/mohamud/Downloads/harnesseng/aether_next_build/tests/test_run_adapter.py)
- [test_docker_runner.py](/Users/mohamud/Downloads/harnesseng/aether_next_build/tests/test_docker_runner.py)

Observed:
- certified/default surfaces fail closed on `ir` / `contract`
- reference modes require explicit opt-in

Focused validation:
- focused suite passed: `82 passed`

Status:
- **Proved on certified/default public run surfaces**

## What Remains Before the One VM Run

Still open on the non-model side:

1. Decide whether to do one more carve-down pass on remaining legacy/reference
   internals, or treat the current quarantine as sufficient for the planned
   single VM validation run.
2. Ensure the single VM run is judged against the right standard:
   - not “did unit tests pass”
   - but “did the real task outcome improve, and why”

## Gate Judgment

Current gate status:

```text
Non-model reset evidence:
SUBSTANTIALLY READY

Real model-backed validation:
NOT YET EXECUTED IN THE FINAL CORRECT ORDER
```

That means the plan is now close to the intended handoff point for the one
real VM task attempt, but the final truth still depends on that run.
