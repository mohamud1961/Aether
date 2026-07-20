# Aether-Next Harness Evals v1

Status: deterministic evaluation framework implemented; official model boards remain gated.

## Purpose

These evals answer two different questions without confusing them:

1. Is each trusted harness invariant implemented correctly?
2. Does the complete model-led system solve diverse official tasks reliably?

A task failure is not automatically a kernel defect. Component evals establish whether the harness supplied a truthful, causal and usable runtime. Official-task boards then measure the complete probabilistic system.

## Non-benchmarkifying boundary

The official task taxonomy lives only under `evals/`.

Production code must never import it or receive its labels. The harness sees only the original public task prompt, factual EnvMap and fixed generic tools. Task-family labels are used solely to select a diverse evaluation board and interpret aggregate results.

The taxonomy was derived from public task instructions, public metadata and public environment filenames. Solution content, official tests and grader output were excluded.

## Four evaluation layers

### Layer 1: component invariants

Manifest groups exercise production owners directly:

- provider and strict protocol;
- Solver causal action boundary and result continuity;
- Architect IR and mechanical compiler;
- inspection registry, proof freshness and completion conjunction;
- Verifier findings and failure ownership;
- workspace, process and service generations;
- filesystem, network, secret and timeout isolation;
- context growth and lossless output retention;
- runner, grader and evidence finalisation;
- architectural purity and canonical-path ownership.

Every group maps to frozen scorecard IDs. Missing targets or unknown built-ins fail closed.

### Layer 2: deterministic system scenarios

These use the real kernel, compiler, context compiler, ledger and Verifier protocol with scripted models and a memory executor. They test interactions that unit tests can miss, including repair after a Verifier finding and fixed-core tool availability.

Known-bad replay cases test false-clean resistance against retained failed states.

### Layer 3: official-task corpus coverage

`evals/official_task_board.v1.json` defines:

- all 90 official tasks;
- a 24-task smoke board spanning code, services, data, science, ML, security, media, emulation, concurrency and symbolic work;
- verification surfaces such as exact artefacts, protocols, numeric thresholds, visual semantics and resource constraints;
- harness-risk coverage such as stale evidence, process identity, derived representations, secrets and long outputs.

The board file is selection metadata only. It is never delivered to Architect, Solver or Verifier.

### Layer 4: model roles and official-grader boards

`evals/model_boards.v1.json` defines separate Architect, Solver, Verifier,
perception, smoke-system and full-system boards. The first four isolate model
behaviour while keeping the trusted kernel and evidence protocol fixed. Use
`scripts/run_model_role_eval_plan.py` to generate a finalised plan for one role.

The official task archetype matrix in `evals/archetype_matrix.v1.json` requires
every public task dimension, verification surface and harness risk to have both
deterministic targets and official-task representatives.

The board runners are plan-only by default. Real model execution requires:

- `--allow-model`;
- a deterministic `summary.json` with `passed: true` and no required failures;
- explicit official-task directory;
- production provenance;
- separate output and trace directories for every sample.

Each task is run with the unmodified public prompt and normal production runner. Official reward remains authoritative.

## Commands

Component and meta gates:

```text
python3 scripts/run_harness_certification_evals.py --tier component
```

Cross-component and full current suite:

```text
python3 scripts/run_harness_certification_evals.py --tier system
```

All blocking deterministic gates:

```text
python3 scripts/run_harness_certification_evals.py --tier certification
```

Generate an individual model-role plan without model calls:

```text
python3 scripts/run_model_role_eval_plan.py \
  --board solver
```

Generate the concrete eight-case Solver checkpoint plan:

```text
python3 scripts/run_solver_checkpoint_eval.py
```

Execute it only after deterministic promotion:

```text
python3 scripts/run_solver_checkpoint_eval.py \
  --samples 3 \
  --effort low \
  --deterministic-summary /path/to/harness_eval/summary.json \
  --allow-model
```

Generate an official smoke-board plan without model calls:

```text
python3 scripts/run_official_task_eval_board.py \
  --board smoke \
  --tasks-dir /path/to/official_tasks
```

Execute three samples only after deterministic promotion:

```text
python3 scripts/run_official_task_eval_board.py \
  --board smoke \
  --tasks-dir /path/to/official_tasks \
  --samples 3 \
  --effort low \
  --deterministic-summary /path/to/harness_eval/summary.json \
  --allow-model
```

## Required metrics

Deterministic gates:

- all required cases pass;
- zero rejected provider output dispatches;
- zero multi-action causal leakage;
- zero stale or unregistered proof acceptance;
- zero completion with active deterministic blockers;
- zero unrelated finding clearance;
- bounded context growth;
- lossless queryable large outputs;
- evidence final marker present.

Official boards:

- official reward;
- internal kernel status and Verifier verdict;
- false-clean count: internal completed, official fail;
- false-block count: internal non-completed, official pass;
- provider/protocol failure rate;
- evidence-finalisation rate;
- steps and efficiency;
- task-dimension coverage;
- sample reliability per task.

## Promotion rules

Harness-code certification requires every blocking deterministic case to pass locally and on a manifest-matching fresh VM. Diagnostic migration cases remain visible even when non-blocking.

A model board may begin only after deterministic promotion. It cannot retroactively make a failed trusted invariant acceptable.

A claim of 100 percent Terminal-Bench performance requires every official task to receive official reward in the declared sample policy. A lower model score does not by itself prove a kernel defect; evidence must identify the correct owner before code changes are admitted.

## Ablations

After the deterministic framework is green, compare the same task/sample set under controlled feature switches:

1. strict provider/parser only;
2. causal one-action observation boundary;
3. boundary plus decision commitment and exact result continuity;
4. boundary plus deterministic repeat/no-progress controls;
5. full certified harness.

Only one factor changes per ablation. Source commit, model, effort, task image, public prompt and official grader remain identical.
