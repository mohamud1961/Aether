# Run-loop engineering: what broke, and what fixed it

An agent's run loop fails in a small number of recurring ways: it cannot see results, it cannot stop, it
cannot recover, or it reports success it did not earn. This page collects every run-loop defect found by
auditing trajectories across four harness generations, grouped by the concern a harness engineer owns.
Almost none of them were visible in pass rates. All were found by reading trajectories row by row.

## 1. Observation: the model must see what its actions did

| Defect | Effect | Fix |
|---|---|---|
| Context rendered only shell-command results; file reads, service probes and process launches never reached the model | The solver acted, saw nothing, and acted again | Render every tool result through one path, and test each result kind |
| A stalled command was visible only as "(no new output)" | One run sat for 1,300 s on a silent process | Report process state (alive, CPU, last output) on every still-running result |
| Programs that read stdin swallowed the completion marker | Runs hung for 903 s and 300 s | Run commands from a file, with the marker on the same line |

## 2. Termination: the loop must always be able to stop

| Defect | Effect | Fix |
|---|---|---|
| A verifier verdict ("blocked by tooling") carried zero findings, and both stalemate detectors required a non-empty finding set | A loop that could never end; one run spun 76 steps without a command | Every verdict is either actionable or terminal; stalemate detection does not depend on findings |
| The wall-clock timeout was raised by a signal, then caught by a broad exception handler and re-labelled as a model error | Runs became unbounded | The deadline is enforced outside model-call error handling, and tested by firing it mid-call |
| Three length cut-offs in a row were classified as "no tool loop" | A working run was stopped with 30 minutes left | Classify cut-offs separately from loops |
| Ctrl-C was ignored inside containers, because background launches inherited an ignored SIGINT | Interrupts did nothing | Launch in a new session (`setsid`) |

## 3. Context: the window must hold what matters, at a sane cost

| Defect | Effect | Fix |
|---|---|---|
| A full state snapshot was rendered as a tool result every turn, and the full history was replayed | By turn 16, 98.8% of a 266 KB request was replayed content | Snapshot once; replay only what changed |
| No cap on context growth | Context reached 222K characters | Hard budget with measured, not estimated, token counts |
| Replayed reasoning was under-counted (38.2k against a 32k budget) | The budget was silently exceeded | Use the provider's exact count |
| The fix for that caused a regression: one long thought triggered a checkpoint that discarded it | About 1,100 s lost on one row | Exclude the newest reasoning from the checkpoint trigger |
| A checkpoint summary returned no text because reasoning consumed the 4k output cap | Three runs killed | 16k cap; low reasoning effort first, then retry |

## 4. Provider and recovery: the loop must survive the provider

| Defect | Effect | Fix |
|---|---|---|
| No backoff or concurrency cap on model calls; 15 parallel tasks shared one deployment | 456 of 482 verifier rounds errored; a "78.5%" batch was a rate-limit storm | Adaptive backoff, a concurrency cap per deployment, and invalid-row accounting |
| Retries ran into a verifier whose own timeout was shorter than the retry budget | Retries could never succeed | Align retry budgets with callee timeouts |
| The open model ran at temperature 0.0 by default | Greedy runaways: one identical malformed call repeated 18 times; one 32k-token loop | Explicit sampling settings; repeated-action detection |
| A single 902 s blocking wait starved the review checks | Reviews never ran | Cap any single wait at 300 s |

## 5. Protocol: the model must be able to follow it

| Defect | Effect | Fix |
|---|---|---|
| A terse JSON turn protocol with no worked example | A small model emitted the wrong turn shape 12+ times and burned steps on parse failures | Give a worked example; accept and repair near-miss shapes instead of failing the turn |
| Multi-decision responses were treated as transport errors | 6 protocol-invalid samples misdiagnosed | Classify protocol errors separately from transport |

## 6. Verification: the check must check

| Defect | Effect | Fix |
|---|---|---|
| The verifier ran 0 real checks across 20 runs | Runs were "verified" by nothing | Count checks executed; a verdict with no evidence is invalid |
| The verifier rooted every path at the workspace, so system paths and subdirectories resolved to missing files | "File not found" was read as task failure; every verifier miss in one batch | Resolve paths against the real filesystem; test with paths outside the workspace |
| A repair hint told the solver to "change the artifact" when a check failed | The solver edited the task's own test file | Never point the solver at the check; point it at the requirement |
| A verifier arm was wired without its callback | An inert arm reported results | The launcher refuses inert configurations |
| A malfunction signal held correct finishes | 2 false holds, 0 true holds in one sweep | Measure false holds before trusting a hold signal |

## 7. Isolation and substrate

| Defect | Effect | Fix |
|---|---|---|
| The task directory was mounted into the solver's container | The solver could see grader material | Mount task files only into trusted grading |
| Commit clones kept container-orchestration labels | The worker ran inside the clones, invalidating three experiment variants | Strip labels on clone; check where work actually ran |
| Candidates ran inside the grader's process | Two rejection controls scored 1.0 | Run candidates in a separate process with no access to the oracle |
| A dead Docker socket produced rows that looked like failures | Invalid rows counted as capability results | Health-check the substrate before each row; count invalid rows separately |

## What generalises

1. **Most failures are the harness, not the model.** In one audited batch the solver did nothing wrong
   after step 5. The miss was an un-passable check, a wrong-root inspection and a dead verifier.
2. **Every timeout, budget and detector needs a test that fires it.** Several defects were safeguards
   that existed and never triggered.
3. **Fixes cause regressions.** The fix for under-counted reasoning (section 3) caused the next defect. Every fix needs its own
   sentinel.
4. **Audit trajectories, not scores.** In one development sweep, auditing all 29 rows found 11 harness
   defects. All were fixed with tests, and none showed up in the pass rate.
