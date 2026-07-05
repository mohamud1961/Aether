# SENTINEL_REGRESSION_REPORT

- generated_at: 2026-06-29T22:40:19
- scope: Phase 6 deterministic sentinel/regression gate

## Gate Commands

| command | result |
|---|---|
| `python3 -m pytest -q --ignore=tests/test_docker_runner.py` | PASS: 192 passed |
| `python3 -m compileall -q aether_next` | PASS |
| `python3 run_verifier_only_eval.py --mode fake --out-dir verifier_only_eval_fake_final_gate` | PASS: 5 rows generated |
| `python3 validate_verifier_only_eval.py verifier_only_eval_fake_final_gate --report VERIFIER_ONLY_FAKE_FINAL_VALIDATION.md` | PASS: ok true |

## Sentinel Coverage

- disabled tool rejection: covered by vNext configurability/integration tests in full suite.
- query_memory always available: covered by runtime prompt/model-hooks and query-memory tests.
- query_artifact_history, inspect_diff, record_observation: covered by broad slice and integration scenario tests.
- context recipe cannot drop active findings/pending checks: covered by context recipe tests.
- verifier blocks needs_repair/uncertain and completed resolves findings: covered by verifier lifecycle tests plus fake final gate.
- unsupported/raw smoke quarantined/rejected: covered by Workbench IR and broad-slice smoke tests.
- compiled smoke in verifier packet: added deterministic test in `tests/test_vnext_memory_context_verifier.py`.
- no-progress visible: covered by replay injection and controlled replay tests.
- artifact history write/read distinction: covered by verifier packet change/touch tests.
- solver prompt verifier feedback guidance: strengthened `SOLVER_SYSTEM_PROMPT` and asserted final solver messages include active verifier finding guidance.
- architect prompt no invented contents / parser rejects weak outputs: covered by Workbench prompt/parser tests.
- no secret leakage: added key-based redaction for model-visible memory/verifier packet payload projections and deterministic packet test.

## Phase 6 Code/Test Changes

- Added `aether_next/redaction.py` for deterministic key-based redaction of structured secret-bearing payload fields.
- Applied redaction to memory events and verifier observation payloads.
- Added tests for secret redaction and compiled visible smoke evidence in verifier packets.
- Added active verifier findings blocker guidance to the solver prompt and asserted it appears in final solver messages.
- Reconciled controlled replay harness and added `tests/test_controlled_replay_eval.py`.

## Residual Risk

- Redaction is key-based and deterministic; it prevents obvious structured credential fields from entering model-visible packets, but it is not a general free-text secret scanner.
- Phase 5 real task validation did not pass because Docker image acquisition/credential access blocked workspace creation; no performance claim is made.

## Evidence Paths

- `VERIFIER_ONLY_FAKE_FINAL_VALIDATION.md`
- `verifier_only_eval_fake_final_gate/summary.json`
- `controlled_replay_eval_phase4/summary.json`
- `NARROW_REAL_TASK_REPORT.md`