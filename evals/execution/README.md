# Execution

Execution covers whether the harness runs real commands and processes and reports what they did: environment bootstrap, runtime hooks, build outcomes, service lifecycle, and semantic evaluators.

The main lesson of the history is that the substrate failed more often than the model. One full board counted 216 of 241 first-attempt trials as never launched. A parallel batch had 456 of 482 verifier rounds error, 421 of them rate limits, and its headline 78.5% was retired.

A harness that reports success from a wrapper or a summary line, or counts a launch failure as a model failure, produces a score that says nothing about the model. This target tests the instrument that produces the score.

## Failure modes probed

- Reporting success from a wrapper's exit status or a success line, not the real exit code.
- Counting environment or launch errors as capability failures, or the reverse.
- Bootstrapping with a legacy runner or a missing interpreter, then reporting a pass.
- A service that binds the wrong port, returns the wrong media type, or shuts down unclean.
- Hook order and denials that do not match the event logs.
- Evaluators that pass a few examples and fail on precedence or 32-bit wrap-around.

## What the history taught

1. **Launch integrity comes before any score.** On a 241-task board, 216 first attempts never launched. The valid rate was 5/19; the naive 5/241 meant nothing.
2. **A green run once is not a gate.** Five local homolog tasks passed 5/5 once, then regressed with the verifier unclean on every scoreable row. Gates now need repeated runs.
3. **Substrate failures masquerade as capability failures.** A grader timeout, a rate-limit storm (456 of 482 verifier rounds errored) and a crashed launcher all produced rows that looked like agent failures.
4. **Auditing every row finds the harness.** A 29-task development sweep scored 18/29 at best attempt; auditing all 29 rows found 11 harness defects, each fixed with a test. See [run-loop engineering](../../research/run-loop-engineering.md).

Every evaluation behind these lessons is listed in the catalogue.

## Current tasks

Validation key: known-bad files, each rejected with its expected reason; careless controls, each rejected; reference solvable from the workspace. All rows pass the grader gate.

| Task | Failure mode | What makes it hard | Validation | Admission |
|---|---|---|---|---|
| `environment_bootstrap_runner_repair` | Repairing a runner for a Python 3 laptop and a CI job | Runner is named by a contract, not by notes; stale script calls an absent `python` and an undeclared pytest; CI matrix and pyproject conflict | 6 known-bad; 5 careless; solvable | capability |
| `runtime_policy_hook` | Hook order, denials and argument effects from logs | Prompt names only the session and call; file order is not sequence order; same-timestamp pair; a summary written for an older SDK; another session's rewritten path | 8 known-bad; 5 careless; solvable | capability |
| `runtime_workspace_contract` | Runtime classification from a pinned contract | Python command in the base file; runner in a profile pinned by SHA-256; stale backup profile; notes say `python`; classification rule for a missing tool | 7 known-bad; 5 careless; solvable | capability |
| `build_survival_truth` | True end state of a nightly build | Wrapper exit status is `tail`'s; stdout "ok" lines; crash message on stderr; planned count differs from stdout count; last night's clean log | 9 known-bad; 5 careless; solvable | capability |
| `service_lifecycle_readiness` | Local HTTP service against a 1.1 contract | Superseded 0.9 section; scaffold signal handler deadlocks; notes give the wrong port and media type; probe checks status, body, unknown path and clean shutdown | 8 known-bad; 5 careless; solvable | debug |

## Limits

The debug-admitted service task runs candidate code on the host, so it needs a sandbox to count as capability evidence. The build and hook tasks check logged evidence files, so they test what the logs record, not the process that wrote them. Environment bootstrap assumes a Python 3 interpreter; other platforms are not covered. The record holds no model result for these tasks.
