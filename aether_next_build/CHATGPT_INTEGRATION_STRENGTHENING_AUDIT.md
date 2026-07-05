# ChatGPT Deterministic Integration Strengthening Audit

Date: 2026-06-29

## Purpose

Codex was unavailable for model runs, so this slice strengthens the deterministic harness surfaces that do not require model calls, Docker, VM, Azure, benchmark tasks, or the official grader.

The goal is to test more of the agreed harness together:

- Runtime Workbench Architect config path
- compiler-realized tool policy
- safe visible smoke checks
- solver actions
- structured memory / artifact history tools
- context recipe realization
- model-verifier packet construction
- active verifier findings
- verifier-gated completion

## Implemented

### Deterministic integration scenarios

Added `aether_next/integration_scenarios.py` with model-free scenario helpers that run through the real `AetherNextKernel` using:

- a static `WorkbenchArchitect`
- scripted solver turns
- scripted verifier outputs
- real `resolve_runtime()` / compiler path
- real context compiler
- real memory/artifact tools
- real kernel verifier gate

Scenarios:

1. `workbench_verifier_repair_loop`
   - Workbench config enables filesystem + memory tools.
   - Visible smoke check is intentionally weak: `out.txt` contains `PASS`.
   - Solver first writes `PASS-124`.
   - Smoke check passes, but model-verifier hook rejects because success definition requires exact `PASS-123`.
   - Active finding reaches next solver context.
   - Solver uses `query_artifact_history`, `inspect_diff`, `record_observation`, then writes `PASS-123`.
   - Verifier completes and kernel returns completed.

2. `disabled_tool_guard`
   - Workbench config does not enable shell.
   - Solver attempts `run_command`.
   - Kernel rejects the turn before dispatch.
   - No mixed same-turn write is allowed after the invalid action.

### Deterministic integration runner

Added `run_deterministic_integration_eval.py`.

It writes an auditable bundle:

- per-scenario `scenario_result.json`
- `summary.json`
- `DETERMINISTIC_INTEGRATION_REPORT.md`

### Verifier packet strengthening

Updated `aether_next/verifier_packets.py` so verifier packets now include:

- `artifact_history`
- `memory_events`
- `observations`

This gives verifier-only model experiments richer evidence without requiring the verifier to infer history from only recent receipt summaries.

### Verifier-only model mode wiring

Updated `run_verifier_only_eval.py` so `--mode model` is wired to the Azure Responses provider using:

- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_GPT54_MINI_DEPLOYMENT`
- `AZURE_OPENAI_GPT54_MINI_KEY`

The model prompt explicitly states:

- official grader remains external
- judge only packet evidence
- output strict JSON only
- do not invent file contents, command output, or grader results

This mode was not executed in this sandbox.

## Tests Added

Added `tests/test_chatgpt_integration_scenarios.py` covering:

- Workbench verifier repair loop through the real kernel stack
- active finding entering subsequent context
- artifact changed after verifier finding
- artifact history and memory events in verifier packets
- disabled tool guard blocking mixed dispatch
- verifier-only model prompt guardrails
- deterministic integration runner bundle creation

## Validation

```text
python3 -m pytest -q tests/test_chatgpt_integration_scenarios.py
4 passed in 2.31s
```

```text
python3 -m pytest -q tests/test_chatgpt_broad_slice.py tests/test_chatgpt_integration_scenarios.py tests/test_vnext_memory_context_verifier.py
41 passed in 4.10s
```

```text
python3 -m pytest -q --ignore=tests/test_docker_runner.py
186 passed in 6.12s
```

```text
python3 -m compileall -q aether_next
passed
```

Runner output:

```text
./run_deterministic_integration_eval.py

workbench_verifier_repair_loop: completed
  completed=true
  verifier_blocked_first_submit=true
  active_finding_reached_context=true
  artifact_changed_after_finding=true
  final_content_exact=true

disabled_tool_guard: incomplete
  disabled_shell_rejected=true
  invalid_turn_prevented_mixed_dispatch=true
  status_incomplete_without_allowed_repair_turn=true
```

## Caveats

- No model calls were made.
- No Docker tests were run.
- No VM/Azure jobs were run.
- No benchmark or official grader was invoked.
- `--mode model` in `run_verifier_only_eval.py` is wired for Codex/VM, but not executed here.
- These are still synthetic integration scenarios, not real benchmark task attempts.

## Next Model-Gated Step

When Codex usage returns:

1. Use this slice as baseline.
2. Run `run_verifier_only_eval.py --mode model` with 5.4-mini.
3. Save raw verifier outputs, parsed results, active findings, and evidence-bound/actionable judgements.
4. Do not run solver task attempts yet.
