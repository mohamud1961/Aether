# Harness Full Plan Progress Audit

Date: 2026-07-01

## Scope

This slice focused on harness development only. Local work was limited to implementation, deterministic tests, architect-only model calls, and audit artifacts. No local full task attempt was used as benchmark evidence.

## What Changed

### Architect Memory Policy Is Now Realized

The Workbench Architect can now emit:

```json
"memory_policy": {
  "automatic_repeat_mode": "advisory",
  "require_query_before_repeat": true,
  "require_query_before_overwrite": true,
  "index_by": ["path", "action_kind", "check_id", "failure_kind"]
}
```

`automatic_repeat_mode` is validated against runtime-supported modes:

- `off`
- `advisory`
- `require_justification`
- `soft_block_exact_repeat`

The compiler now realizes that field into `RuntimeConfigIR.automatic_memory_policy`, and the compiled runtime/config-realization receipt records the selected mode.

Files changed:

- `aether_next/workbench_config.py`
- `aether_next/workbench_compile.py`
- `aether_next/workbench_hooks.py`
- `aether_next/runtime_manual.py`
- `tests/test_vnext_workbench_ir.py`
- `tests/test_vnext_configurability.py`

## Architect-Only Evaluation

Primary 15-task architect-only eval:

- `architect_only_eval_harness_goal_20260701_023005/architect_only_eval.json`
- `architect_only_eval_harness_goal_20260701_023005/ARCHITECT_EVAL_REPORT.md`

Repair evals for provider/token-ceiling failures:

- `architect_only_eval_harness_goal_20260701_023005_repair3/architect_only_eval.json`
- `architect_only_eval_harness_goal_20260701_023005_sparql_retry/architect_only_eval.json`

Merged result after targeted repair:

- records: 15
- parseable HarnessConfigIR: 15/15
- average overall score: 9.96/10
- minimum overall score: 9.67/10
- average solver prompt score: 9.93/10
- average verifier prompt score: 9.93/10
- config contract score: 10/10 for every task

Per-task merged scores:

| task | overall | solver | verifier | config | solver words | verifier words | memory mode | note |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| filter-js-from-html | 9.67 | 9 | 10 | 10 | 439 | 339 | advisory | solver prompt just below length rubric |
| sparql-university | 10.00 | 10 | 10 | 10 | 759 | 636 | advisory | passed isolated retry |
| openssl-selfsigned-cert | 10.00 | 10 | 10 | 10 | 570 | 404 | advisory | passed repair rerun |
| video-processing | 9.67 | 10 | 9 | 10 | 450 | 296 | advisory | verifier prompt just below length rubric |
| install-windows-3.11 | 10.00 | 10 | 10 | 10 | 739 | 560 | advisory | pass |
| fix-git | 10.00 | 10 | 10 | 10 | 554 | 489 | advisory | pass |
| gpt2-codegolf | 10.00 | 10 | 10 | 10 | 765 | 545 | advisory | pass |
| extract-moves-from-video | 10.00 | 10 | 10 | 10 | 579 | 391 | advisory | pass |
| git-multibranch | 10.00 | 10 | 10 | 10 | 758 | 476 | advisory | pass |
| configure-git-webserver | 10.00 | 10 | 10 | 10 | 601 | 498 | advisory | pass |
| qemu-alpine-ssh | 10.00 | 10 | 10 | 10 | 698 | 410 | require_justification | pass; chose stricter repeat policy |
| financial-document-processor | 10.00 | 10 | 10 | 10 | 648 | 460 | advisory | pass |
| vulnerable-secret | 10.00 | 10 | 10 | 10 | 508 | 362 | advisory | pass |
| query-optimize | 10.00 | 10 | 10 | 10 | 642 | 460 | advisory | pass |
| hf-model-inference | 10.00 | 10 | 10 | 10 | 677 | 448 | advisory | passed repair rerun |

## What We Learned

1. The architect prompt/config architecture can now produce high-quality solver and verifier prompts consistently across a broad 15-task architect-only set.
2. The main non-quality failure mode was provider/token ceiling behavior, not schema brittleness. Targeted reruns with a higher output ceiling repaired OpenSSL and HF; isolated lower-concurrency retry repaired SPARQL.
3. The architect mostly selected `advisory` automatic memory, which is a sensible default for first live VM runs. It selected `require_justification` for `qemu-alpine-ssh`, where repeated expensive/runtime actions are riskier.
4. Config quality is now ahead of live-run evidence. The correct next proof surface is VM-only task execution with full trace audit, not more local full attempts.

## Validation

Commands run:

```bash
python3 -m pytest -q tests/test_vnext_workbench_ir.py tests/test_vnext_configurability.py tests/test_memory_loop_fixes.py tests/test_automatic_memory_diagnostic_eval.py
python3 -m pytest -q tests/test_vnext_memory_context_verifier.py tests/test_trace_verifier_replay_ab.py tests/test_chatgpt_integration_scenarios.py
python3 run_architect_only_eval.py --out-dir architect_only_eval_harness_goal_20260701_023005 --effort high --max-output-tokens 24000 --concurrency 3
python3 run_architect_only_eval.py --tasks sparql-university,openssl-selfsigned-cert,hf-model-inference --out-dir architect_only_eval_harness_goal_20260701_023005_repair3 --effort high --max-output-tokens 48000 --concurrency 3
python3 run_architect_only_eval.py --tasks sparql-university --out-dir architect_only_eval_harness_goal_20260701_023005_sparql_retry --effort medium --max-output-tokens 48000 --concurrency 1
python3 -m compileall -q aether_next run_architect_only_eval.py run_trace_verifier_replay_ab.py run_automatic_memory_diagnostic_eval.py
python3 -m pytest -q --ignore=tests/test_docker_runner.py
```

Final local gate:

```text
221 passed in 37.62s
```

## Current Status

Completed locally:

- architect-as-skill prompt/config quality upgraded and measured;
- architect-authored automatic memory mode realized into runtime;
- tests updated and passing;
- architect-only 15-task evidence produced.

Still pending, VM-only:

- real task reruns;
- solver trajectory quality audit;
- verifier live feedback audit;
- grader-backed pass/fail rows.

No benchmark improvement claim is made from this slice.

## VM Plan Expansion

Update on 2026-07-01: the VM-only run packet was expanded from 7 tasks to exactly 10 tasks.

The staged 10-task set is:

1. `filter-js-from-html`
2. `sparql-university`
3. `openssl-selfsigned-cert`
4. `video-processing`
5. `install-windows-3.11`
6. `fix-git`
7. `gpt2-codegolf`
8. `extract-moves-from-video`
9. `git-multibranch`
10. `qemu-alpine-ssh`

The added tasks were selected from the architect-only eval set because they already have parseable, high-scoring Workbench configs and broaden the live evidence surface:

- `extract-moves-from-video`: media acquisition/transcription/extraction workflow;
- `git-multibranch`: service/deployment/Git-over-SSH workflow;
- `qemu-alpine-ssh`: VM/runtime/process-control workflow with stricter `require_justification` automatic memory mode.

The expansion does not authorize local full attempts. Local remains limited to tests, replay, architect-only generation, diagnostics, and audit. Full attempts and grader-backed rows remain VM-only.

Parallel execution update:

- Stage 1 remains the VM infrastructure/calibration gate.
- After Stage 1 is valid and audited, Stage 2 and Stage 3 may use controlled parallel execution within each stage.
- 5.4-mini agents should be used as VM run managers/monitors from this point forward.
- Default concurrency target is `max_parallel=2` until VM/provider stability is proven.
- Heavy VM/QEMU tasks, especially `install-windows-3.11` and `qemu-alpine-ssh`, should run alone or only with a light companion after the lighter lanes prove stable.
- Parallel lanes must use isolated result, trace, snapshot, and log directories.
