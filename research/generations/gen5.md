# Gen 5: Aether (in development)

**What this is:** The current lean core. The model runs a loop of turns, tool calls and results until it finishes or time runs out. Everything is recorded in full, and a claim-free review runs when the model finishes.
**Key result:** A development sweep over 29 Terminal-Bench 2.1 tasks solved 18 at best attempt and 17 on the first valid attempt. The sweep changed code between rows, so it is not a frozen comparison.
**Why it matters:** The sweep's most useful output is the defect audit: 11 harness defects were found by reading every row and fixed with tests.

This page describes the design and the development sweep only. It makes no product claim.

## Core idea

The model pilots, and the harness only instruments. Keep the loop shape simple, record everything, and move judgment to a reviewer that sees the task and real outputs but not the solver's claims.

## Design

```
          ┌──────────────── model turn ◄──────────────────┐
          ▼                                               │
  tool call: terminal | read_file | write_file |          │
             edit_file | finish                           │
          │                                               │
          ▼                                               │
  result: head and tail shown, full log kept on disk ─────┘
          │
          │ finish requested
          ▼
  claim-free review: task, latest actions with real outputs,
                     fresh workspace snapshot (never the claims)
          │ hold (at most 2) or pass
          ▼
  end. Every turn is traced to the run record.
```

| Component | Role |
|---|---|
| Loop | Model turn, tools, results, until finish or time. Full trace of reasoning, calls, results, timings and token use. |
| Terminals | Up to eight named, persistent shells. Output goes to a log; the model sees new output and can grep the log. One call waits at most 300 seconds, so reviews can run during long jobs. |
| File tools | Line-numbered reads, whole-file writes, exact-match edits. |
| Context | The four most recent turns verbatim; older turns as pointers to saved full results, trimmed in blocks so the request prefix stays stable. |
| Model-managed context (optional) | The model condenses its own context under a token budget, with nudges at 25, 50 and 75 percent. |
| Structured checkpoint | A fallback summary used only after the model-managed budget is spent. |
| Reviews | A claim-free finish review (it can hold the finish at most twice), progress reviews at fixed points in the time limit, and one final review near the deadline. Reviews inform; only the finish review can hold. |
| Clone | A disposable, no-network copy of the task container, used to run acceptance checks without touching the graded state. |
| Acceptance checks | Written from the task before the work, offered to the worker as information. They no longer hold a finish. |

Two choices came from measurement. The local token limiter was removed after it cost 112 to 179 seconds per row and no provider rate-limit errors occurred. Acceptance checks stopped holding finishes after two cases in which the worker changed a correct answer or added a fallback to satisfy a wrong check.

## Evaluations

| Eval | Result | Note |
|---|---|---|
| Lean loop baseline, 4 tasks by 2 arms | 0 of 2 on the interpreter-class task; context grew to 222,000 characters with no cap. | Led to the second screen. |
| Second screen, pre-registered predictions 1 to 8 | Prediction 7 (interpreter-class tasks) failed: 0 of 3 solved across three versions. Prediction 8 solved in version 2.2. | Recorded as failed. |
| Claim-free review, offline bench | Caught 15 of 18 wrong finishes; 10 of 18 when the reviewer saw the solver's claims. | Offline bench, not a live run. |
| Structured file tools, one task | Built the artifact in 3 of 3 runs against 0 of 2 for a stock reference agent. | One task; small sample. |
| Development sweep, 29 tasks, one night | 18 solved at best attempt; 17 on first valid attempt. | Code changed per row, so this is a development sweep, not a frozen arm. |

## Development sweep: what it found

Every row was audited. Eleven harness defects were found, fixed and covered by tests. They included a completion marker swallowed by programs that read standard input, a Ctrl-C ignored inside containers, a checkpoint that returned no text because reasoning used the whole output cap, and a single long wait that starved the reviews.

## Limits

- The sweep is not a frozen comparison, and it is not comparable to the held-out campaign of October.
- The interpreter-class prediction failed, and the design has shown no lift on that class.
- Verification in a disposable clone, described in an earlier design note, is not in the branch this page was read from; the page describes only what the branch contains.

