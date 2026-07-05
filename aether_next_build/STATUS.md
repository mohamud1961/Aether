# Aether-Next build — status (2026-06-26)

## Phase 1: COMPLETE (built, reviewed, tested)

A fully runnable, behaviour-tested Aether-Next harness. Sonnet wrote the code;
every round was audited + independently test-run by the reviewer (Opus).

**60 tests pass. Every module <= 500 LOC. No dead code. No broad bare-except.**

Modules (`aether_next/`):
- `kernel.py` — the complete `run()` loop (was truncated/returned None in Pro's
  output): architect -> validate -> compile -> ledger -> [monitors -> context
  packet -> solve -> dispatch actions -> on submit: run real checks + completion
  gate -> reconfigure] -> KernelResult. Never returns None.
- `runtime_ir.py` — typed IR + `WorkflowPolicy` (8 bounded modes) + model-routing
  tiers (the audit's requested additions).
- `compiler.py` + `analysis.py` — env analysis, eval indexing, objective extraction,
  IR validation/compilation (decomposed to honour the 500-LOC cap).
- `completion.py` — authority-aware completion gate (deterministic; real checks).
- `ledger.py` — structured receipt/world-model memory + bounded context compiler.
- `monitors.py` — cheap per-step monitors + safety/integrity guards.
- `execution.py` — engine abstractions + `MemoryExecutor`.
- `classifier.py` — `HarnessLimiterClassifier` (the empirical "harness vs model"
  labeller; ambiguous endings lean harness-ward, never default to model_limit).
- `model_hooks.py` — `ModelHooks` (Architect/Solver/Reconfigure backed by any
  `ModelCallable`) + strict-JSON parsers + safe fallbacks (kernel never crashes on
  bad model output).
- `real_executor.py` — `SubprocessExecutor` (real workspace ops + artifact diffing).
- `envmap_builder.py`, `run_adapter.py` — build EnvMap from a task; run + classify.
- `providers/azure_model.py` — Azure Responses-API `ModelCallable` (background mode).
  VALIDATED: real call reaches Azure (only the Pro deployment is live; see below).
- `runners/docker_runner.py` — `DockerExecExecutor` + `run_tbench_task` (seed
  workspace from image, run container, drive kernel via `docker exec`, score with
  the official `test.sh`, classify, teardown).
- `run_pilot.py` — pilot CLI over N official tasks.

## Phase 2: BLOCKED on environment (no runs executed; nothing faked)

Three independent blockers, none fixable without the user/admin:
1. **VM unreachable** — `ssh azureuser@20.106.35.151` times out (VM stopped or SSH blocked).
2. **Local Docker daemon won't start** — Docker Desktop is installed but the daemon
   never came up (likely needs GUI interaction on launch).
3. **No 5.4-mini deployment on Azure** — `MINI deploy + working key -> 404
   DeploymentNotFound`. Only the **Pro** deployment is live.

## To unblock Phase 2
Need (A) a container runtime — bring the VM back, or start Docker Desktop fully —
AND (B) a solver deployment — deploy gpt-5.4-mini, or run with **Pro** as the solver
(works now, slower/pricier; effort must be medium/high/xhigh, not low).

Ready-to-run command (set the solver envs to the deployment you have):
```
cd aether_next_build && set -a; . ../.pro_azure_env.local; set +a
PYTHONPATH=. python3.11 run_pilot.py \
  --tasks openssl-selfsigned-cert,log-summary-date-ranges,filter-js-from-html,fix-git,gcode-to-text,extract-elf,raman-fitting,train-fasttext,configure-git-webserver,sparql-university \
  --out pilot_results.json
```
(Defaults to the mini envs; pass `--solver-deploy-env AZURE_OPENAI_GPT54_PRO_DEPLOYMENT
--solver-key-env AZURE_OPENAI_GPT54_PRO_KEY` to use Pro as solver.)
