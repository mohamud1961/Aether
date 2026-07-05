# Claude Tasks 1, 3, 4 Adversarial Closeout

Date: 2026-07-04

Scope:
- Audit the takeover slices attributed to Claude Tasks 1, 3, and 4 against the
  current tree and existing evidence.
- This is a current-state audit, not a trust-the-handoff summary.

Task mapping used here:
- Task 1: solver command-output visibility
- Task 3: workbench reconfigure routing / failure surfacing
- Task 4: canonical default-path governance on public run surfaces

Method:
- inspect live code
- inspect live tests
- inspect existing VM/run evidence where relevant
- classify each item as proved, contradicted, incomplete, or only partially proved

## Executive Conclusion

- **Task 1:** proved, and now proved at the real kernel-loop level, not just in
  lower-level context assembly.
- **Task 3:** substantially proved. The canonical workbench reconfigure path now
  routes back through the workbench architect and failed reconfigure surfaces as
  explicit config invalidity rather than fake-generic recovery.
- **Task 4:** partially proved. The certified/default public surfaces now fence
  off reference architect modes, but non-canonical internals still exist in the
  repo as explicit reference/debug machinery.

Overall:
- The Claude work was not accepted on trust.
- The important parts were independently re-proved in current code.
- The remaining gap is not the three target fixes themselves; it is the amount
  of legacy/reference machinery still present around the canonical line.

## Requirement-by-Requirement Audit

### Task 1 — Solver command outputs are visible in practice

Requirement:
- The solver should see its own recent command outputs by default in the real
  loop, not only in a unit helper or idealized path.

Evidence:
- [context_compiler.py](/Users/mohamud/Downloads/harnesseng/aether_next_build/aether_next/context_compiler.py)
  force-includes `command_results` through safety-section enforcement.
- [test_vnext_memory_context_verifier.py](/Users/mohamud/Downloads/harnesseng/aether_next_build/tests/test_vnext_memory_context_verifier.py)
  contains the earlier mode-coverage regression.
- Added live-loop regression:
  [test_vnext_configurability.py](/Users/mohamud/Downloads/harnesseng/aether_next_build/tests/test_vnext_configurability.py)
  `test_solver_sees_recent_command_stdout_in_live_kernel_loop`
  proves second-turn solver context contains `command_results` and the command
  output token `PROOF_TOKEN=visible-now`.

Status:
- **Proved**

Confidence:
- **High**

Why this counts:
- This is no longer only a compiler/context invariant.
- It is verified at the actual kernel message boundary seen by the solver.

### Task 3 — Workbench reconfigure routing and failure surfacing

Requirements:
1. In canonical workbench mode, reconfigure must re-invoke the workbench
   architect rather than collapsing into the legacy thin reconfigure path.
2. If workbench reconfigure fails, the run must surface an explicit
   architect/config failure rather than silently recovering to a generic safe
   default.

Evidence for routing:
- [kernel.py](/Users/mohamud/Downloads/harnesseng/aether_next_build/aether_next/kernel.py)
  `_do_reconfigure()` branches to `_do_reconfigure_workbench()` when
  `self.workbench_architect is not None`.
- [kernel_config.py](/Users/mohamud/Downloads/harnesseng/aether_next_build/aether_next/kernel_config.py)
  `_workbench_resolve(..., reconfigure_context=...)` feeds the workbench
  architect the richer reconfigure context instead of the legacy separate prompt.
- Regression:
  [test_vnext_configurability.py](/Users/mohamud/Downloads/harnesseng/aether_next_build/tests/test_vnext_configurability.py)
  `test_reconfigure_routes_through_workbench_architect_not_legacy_default`

Evidence for failure surfacing:
- [kernel.py](/Users/mohamud/Downloads/harnesseng/aether_next_build/aether_next/kernel.py)
  failed reconfigure receipts now include explicit payload fields such as
  `architect_path`, `blockers`, and `fallback_codes`.
- Regression:
  [test_vnext_configurability.py](/Users/mohamud/Downloads/harnesseng/aether_next_build/tests/test_vnext_configurability.py)
  `test_failed_workbench_reconfigure_surfaces_config_invalid_without_generic_recovery`
  proves:
  - `reconfigure_validation` fails with `failure_class="config_invalid"`
  - payload names `architect_path == "workbench"`
  - blockers include `workbench_architect_configure_failed`
  - no `config_fallback` receipt is emitted
  - prior good workbench prompt remains in effect

Historical motivation evidence:
- old traces under
  [expanded_real_task_traces_20260630_architect_skill_loop_v1](/Users/mohamud/Downloads/harnesseng/aether_next_build/expanded_real_task_traces_20260630_architect_skill_loop_v1)
  show real earlier collapses to:
  `"[safe default — reconfigure parse failed]"`

Status:
- **Proved**

Confidence:
- **High**

Important caveat:
- This proves the canonical workbench reconfigure path is now honest about
  failure. It does **not** mean all legacy fallback code has been deleted from
  the repo.

### Task 4 — Canonical default-path governance

Requirements:
1. Public/default Aether-Next run surfaces should default to workbench mode.
2. Reference architect modes should not quietly compete with certified/default
   execution.
3. The VM/public runner path should follow the same governance.

Evidence:
- [run_pilot.py](/Users/mohamud/Downloads/harnesseng/aether_next_build/run_pilot.py)
  defaults to `architect_mode="workbench"` and now rejects reference architect
  modes unless explicitly opted into.
- [run_adapter.py](/Users/mohamud/Downloads/harnesseng/aether_next_build/aether_next/run_adapter.py)
  added `ensure_certified_architect_mode(...)` and requires explicit opt-in for
  `ir` / `contract`.
- [docker_runner.py](/Users/mohamud/Downloads/harnesseng/aether_next_build/aether_next/runners/docker_runner.py)
  now applies the same certified/default-mode quarantine before task execution.
- Tests:
  - [test_run_adapter.py](/Users/mohamud/Downloads/harnesseng/aether_next_build/tests/test_run_adapter.py)
  - [test_docker_runner.py](/Users/mohamud/Downloads/harnesseng/aether_next_build/tests/test_docker_runner.py)
- Focused validation passed:
  - `82 passed` across the focused quarantine/config/context/kernel suite.
- CLI behavior check:
  `run_pilot.py --architect-mode ir` now exits with an explicit quarantine error
  unless reference mode is intentionally enabled.

Status:
- **Partially proved**

Why partial:
- The certified/default entry points are now governed correctly.
- But the repo still contains explicit reference/debug machinery:
  - `architect_overrides_for_mode("ir"|"contract"|...)`
  - legacy `ModelHooks` safe-default fallbacks
  - `compiler.guaranteed_default_ir()` paths for baseline/reference flows
  - replay/debug utilities that still exercise legacy paths

So:
- the public/certified default is fixed
- the legacy/reference surfaces are **quarantined**
- they are **not yet fully removed**

Confidence:
- **High** on the governance fix itself
- **Medium-high** on the broader “legacy interference is fully gone” claim, which
  would be false if claimed today

## Remaining Legacy Surface After Tasks 1/3/4

Still present, but no longer the default certified path:
- [model_hooks.py](/Users/mohamud/Downloads/harnesseng/aether_next_build/aether_next/model_hooks.py)
  - `DEFAULT_VERIFIER_IDENTITY_PROMPT`
  - `_safe_default_ir()`
  - `_safe_default_ir_from_compiled()`
  - `_safe_fallback_turn()`
- [kernel_config.py](/Users/mohamud/Downloads/harnesseng/aether_next_build/aether_next/kernel_config.py)
  baseline/reference uses of `compiler.guaranteed_default_ir()`
- replay/reference utilities such as:
  - `replay_resume.py`
  - `replay_architect.py`
  - older trace-replay utilities

Interpretation:
- These are now better described as **reference/debug surfaces** than active
  canonical runtime authority.
- They still contribute to repo bloat and conceptual drag.

## Bottom Line

The three audited Claude tasks are in much better shape than “trust the handoff”
would have justified:

- Task 1: **good and re-proved**
- Task 3: **good and re-proved**
- Task 4: **good governance fix, but only partial repo cleanup**

So the honest closeout is:

```text
Task 1: ACCEPT
Task 3: ACCEPT
Task 4: ACCEPT WITH REMAINING LEGACY-QUARANTINE WORK
```

That is strong enough to continue the reset plan, but not strong enough to say
the canonical repo is already fully minimal or fully free of legacy slop.
