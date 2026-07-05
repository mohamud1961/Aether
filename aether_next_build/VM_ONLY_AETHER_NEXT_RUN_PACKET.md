# VM-Only Aether-Next Run Packet

Date: 2026-07-01

## Rule

Full task attempts must run on the VM only. Local runs are for unit tests, deterministic diagnostics, replay, architect-only config generation, and artifact analysis.

## Entry Criteria

Before starting VM task attempts:

- VM Docker backend is healthy.
- Official task folders are present on the VM.
- Azure/OpenAI model environment variables are present on the VM.
- Current Aether-Next build includes:
  - Workbench Architect boot path;
  - stable core tools;
  - architect-generated solver and verifier prompts;
  - architect-authored `memory_policy.automatic_repeat_mode` compiled into runtime;
  - automatic memory receipts;
  - completion blockers for verifier findings and memory repeat blockers;
  - full local non-Docker tests green.

Local evidence for the last item:

```text
python3 -m pytest -q --ignore=tests/test_docker_runner.py
221 passed in 37.62s
```

## Ten-Task VM Plan

The full VM packet is exactly 10 tasks, staged as:

1. Narrow calibration run: 3 tasks.
2. First expansion run: 4 tasks.
3. Second expansion run: 3 tasks.

Do not merge these into one giant run until the staged rows are audited. The
staging is part of the evidence discipline: each batch should produce rows,
traces, snapshots, and an audit before the next batch is interpreted.

Run-management rule:

- Stage 1 is the infrastructure/calibration gate and may run sequentially or as
  one managed batch.
- After Stage 1 produces valid infrastructure evidence, Stage 2 and Stage 3 may
  use controlled parallelism within the stage.
- 5.4-mini agents should act as VM run managers/monitors for stage execution.
- Keep overall concurrency conservative until VM/provider stability is proven:
  default `max_parallel=2`.
- Heavy runtime tasks should run alone or with only a light companion task.
  Treat `install-windows-3.11` and `qemu-alpine-ssh` as heavy VM/QEMU tasks.
- Every parallel lane must write isolated trace, snapshot, result, and log paths.
  No lane may share an output directory with another task.
- Parallelism changes speed only; it does not change evidence standards. Rows
  still need architect/solver/verification/outcome audit before promotion claims.

Exact 10-task set:

- `filter-js-from-html`
- `sparql-university`
- `openssl-selfsigned-cert`
- `video-processing`
- `install-windows-3.11`
- `fix-git`
- `gpt2-codegolf`
- `extract-moves-from-video`
- `git-multibranch`
- `qemu-alpine-ssh`

## Stage 1: Narrow VM Run

Run exactly these first:

- `filter-js-from-html`
- `sparql-university`
- `openssl-selfsigned-cert`

Suggested command:

```bash
cd /path/to/aether_next_build
ts=$(date +%Y%m%d_%H%M%S)
AETHER_MODEL_POLL_TIMEOUT_S=420 \
AETHER_MODEL_POLL_INTERVAL_S=2 \
AETHER_MODEL_VERIFIER_TIMEOUT_S=120 \
python3 run_pilot.py \
  --tasks filter-js-from-html,sparql-university,openssl-selfsigned-cert \
  --architect-mode workbench \
  --effort medium \
  --max-steps 30 \
  --run-timeout-s 900 \
  --trace-dir narrow_real_task_traces_${ts}_vm_harness_goal \
  --snapshot-dir narrow_real_task_snapshots_${ts}_vm_harness_goal \
  --out narrow_real_task_results_${ts}_vm_harness_goal.json
```

## Stage 2: First Expanded VM Run

Only after the narrow three-task run is audited:

- `video-processing`
- `install-windows-3.11`
- `fix-git`
- `gpt2-codegolf`

Parallel policy after Stage 1:

- Recommended controlled schedule:
  - lane A: `video-processing`
  - lane B: `fix-git`
  - lane C: `gpt2-codegolf`
  - heavy lane: `install-windows-3.11` alone, or paired only after light lanes prove stable
- Use separate run ids/output dirs per lane when launching in parallel.

Suggested command:

```bash
cd /path/to/aether_next_build
ts=$(date +%Y%m%d_%H%M%S)
AETHER_MODEL_POLL_TIMEOUT_S=420 \
AETHER_MODEL_POLL_INTERVAL_S=2 \
AETHER_MODEL_VERIFIER_TIMEOUT_S=120 \
python3 run_pilot.py \
  --tasks video-processing,install-windows-3.11,fix-git,gpt2-codegolf \
  --architect-mode workbench \
  --effort medium \
  --max-steps 30 \
  --run-timeout-s 900 \
  --trace-dir expanded_real_task_traces_${ts}_vm_harness_goal \
  --snapshot-dir expanded_real_task_snapshots_${ts}_vm_harness_goal \
  --out expanded_real_task_results_${ts}_vm_harness_goal.json
```

## Stage 3: Second Expanded VM Run

Only after Stage 2 is audited:

- `extract-moves-from-video`
- `git-multibranch`
- `qemu-alpine-ssh`

Parallel policy after Stage 2:

- Recommended controlled schedule:
  - lane A: `extract-moves-from-video`
  - lane B: `git-multibranch`
  - heavy lane: `qemu-alpine-ssh` alone
- Use separate run ids/output dirs per lane when launching in parallel.

Suggested command:

```bash
cd /path/to/aether_next_build
ts=$(date +%Y%m%d_%H%M%S)
AETHER_MODEL_POLL_TIMEOUT_S=420 \
AETHER_MODEL_POLL_INTERVAL_S=2 \
AETHER_MODEL_VERIFIER_TIMEOUT_S=120 \
python3 run_pilot.py \
  --tasks extract-moves-from-video,git-multibranch,qemu-alpine-ssh \
  --architect-mode workbench \
  --effort medium \
  --max-steps 30 \
  --run-timeout-s 900 \
  --trace-dir expanded2_real_task_traces_${ts}_vm_harness_goal \
  --snapshot-dir expanded2_real_task_snapshots_${ts}_vm_harness_goal \
  --out expanded2_real_task_results_${ts}_vm_harness_goal.json
```

## Required Audit For Each Task

### Architect

Record:

- Was Workbench Architect called?
- Was HarnessConfigIR parseable without repair?
- Solver prompt word count and score.
- Verifier prompt word count and score.
- Config contract score.
- Selected `memory_policy.automatic_repeat_mode`.
- Context policy and recipe.
- Visible smoke tests compiled/rejected.
- Did config match task needs?
- Did it miss any environment-aware requirement?

### Solver

Record:

- Did the solver follow the architect prompt?
- Did it inspect the right files/artifacts first?
- Did it create the expected deliverables?
- Did it run validation scripts or commands when appropriate?
- Did it repeat reads/checks/commands?
- If repeated, did automatic memory surface prior evidence?
- Did the solver change strategy after memory feedback?
- Did it use tools/scripts appropriately?
- Did it stop too early or continue after enough evidence?

### Verification

Record:

- Was deterministic verification called?
- Was model verifier called?
- What reason triggered verifier: submit, deterministic success candidate, deterministic failure, no progress, max steps?
- Did verifier packet include:
  - success definition;
  - architect verifier prompt;
  - evidence requirements;
  - false-positive risks;
  - minimum completion evidence;
  - local verification limits;
  - artifact history;
  - latest file reads;
  - automatic memory findings;
  - active findings?
- Was verifier feedback evidence-bound?
- Was verifier feedback actionable?
- Did active findings enter solver context?
- Did completion obey verifier findings?

### Grader / Outcome

Record:

- reward;
- status;
- failure class if failed;
- whether failure is environment/runtime, provider, architect config, solver behavior, verification, completion, or grader-specific;
- whether row is valid or invalid.

## Keep/Kill Criteria

Keep:

- architect-generated verifier prompt if live feedback is more specific/actionable and does not hallucinate;
- `advisory` automatic memory if it reduces loops without blocking useful work;
- stricter memory modes only where they prevent repeated no-progress without false blocking;
- completion blockers if they prevent false success without causing unresolved deadlock.

Kill or revise:

- any verifier prompt pattern that invents evidence;
- any memory mode that blocks legitimate progress without clear override path;
- any context recipe that hides active findings, pending checks, or latest failure evidence;
- any completion gate that marks success from weak checks alone.

## Claims Discipline

Do not claim benchmark improvement until VM rows with grader-backed evidence support it.

Do not use local full attempts as evidence.
