# Gen 5: Aether Core

**What this is:** The current lean core, in `aether/core/`. The model runs a loop of turns, tool calls and results until it finishes or time runs out. Observable model exchanges and tool results are recorded. The model owns the finish; reviews inform it.
**Key result:** No lift over a stock harness. On the 18-row development board, Aether Core with GLM-5.3-Flash solved 12 of 18 and a stock reference agent with the same model also solved 12 of 18. About 20 mechanism tests against false completion, 11 to 17 October, promoted none.
**Why it matters:** The failures were studied row by row. Outcomes turned out to be close to deterministic per model and task, so most of the remaining error belongs to the model's reading of specific tasks, and a harness lever that only corrects one model's reading of one task is a crutch by this project's own test.

The development sweep of 12 October (below) changed code between rows, so it is a development record, not a frozen comparison.

## Code

| Path | What it is |
|---|---|
| `aether/core/` | The runtime: loop, provider adapters (Chat Completions and Responses), terminals, file tools, context, deadlines, clone, contracts, reviews, Harbor agent |
| `tests/core/` | Its tests. They use scripted provider responses with real shell and file effects; Linux PTY and Docker tests skip elsewhere |
| `docs/core/` | Architecture, lessons, self-audit and validation notes |
| `research/core/` | Pre-registrations and results for every Core experiment, 12 to 18 October |

The commit history of `aether/core/` keeps the original development order and dates.

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
| Loop | Model turn, tools, results, until finish or time. Trace of calls, results, timings, reported token use and provider-exposed reasoning where available. |
| Terminals | Up to eight named, persistent shells. Output goes to a log; the model sees new output and can grep the log. One call waits at most 300 seconds, so reviews can run during long jobs. |
| File tools | Line-numbered reads, whole-file writes, exact-match edits. |
| Context | The four most recent turns verbatim; older turns as pointers to saved full results, trimmed in blocks so the request prefix stays stable. |
| Model-managed context (optional) | The model condenses its own context under a token budget, with nudges at 25, 50 and 75 percent. |
| Structured checkpoint | A fallback summary used only after the model-managed budget is spent. |
| Reviews | A claim-free finish review (it could hold the finish at most twice), progress reviews at fixed points in the time limit, and one final review near the deadline. The review protocol is in `review.py`; the review transport, an external evaluator service, is not included here, so the shipped Harbor agent runs with review `off` or `contract`. |
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

## 13 to 20 October: can false completion be caught?

After the sweep, the question became why runs finish with wrong work. Each experiment was pre-registered with predictions and a falsifier in `research/core/`; failed predictions are recorded as failed.

| Experiment | Result | Verdict |
|---|---|---|
| Hardened board B1 (GLM, 9 tasks x 2) | 9 of 17 graded rows; 6 of 15 voluntary finishes wrong | Baseline |
| Stock reference agent on the same board (T1) | 12 of 18; 2 of 13 finishes wrong | Looked like a harness gap |
| Re-run of the Aether board (S4 b1) | 12 of 18 | The T1 gap was noise (p = 0.50) |
| Finish-time levers: reasoning effort, analysis turn, JSON turns, finish receipt (S3 to S6) | 25 to 39% wrong finishes in every arm | Failed; JSON turns did fix protocol stops |
| Prewritten acceptance checks (A1) | Held 42% of good states | Harmful; removed as a hold |
| Same-model finish review (R1) | Caught 3 of 12 bad states; held 1 of 16 good | Safe but weak |
| GPT-6-Luna on the same board (L1, L2) | 11 of 16 both times; first pass ever on the seq-assembly task | No outcome change from reasoning continuity (replayed 287 of 287) |
| Cache-stable context (N1) | 10 of 16 in both arms; mean cost per row $0.031 to $0.014 | Cost halved at equal passes |
| Requirement ledger (N2) | 6 of 15 against 8 of 15 without it | Failed |
| Reading judge on finished runs (J1) | AUROC 0.475 on 80 runs by another agent; 0.692 on 30 same-model runs | Failed: chance on the larger set; the smaller is too small to use |
| Decision probes on one failing task (P1) | Shown its output file in a field-aware view and asked whether it was right, the model caught the reversed file 18 of 18 times, against 1 of 18 with the file shown raw. The same view inside real runs led to 1 repair in 9 | Understood; nothing fixed it in-run |

The self-audit of 17 October (`research/core/CORE_SELF_AUDIT_RESEARCH_QUESTIONS_20261017.md`) reads these together: about 20 mechanism tests, none promoted, effort concentrated on one failure of one task, and small boards on which only large effects are visible. Its conclusion was to stop tuning on the development board and to measure ceilings before building more levers.

## Limits

- No frozen comparison favours Aether Core. The development sweep changed code between rows, and the matched board is a tie.
- Boards are small: 9 tasks, and 4 of them hold most wrong finishes. Differences under about 5 rows are not visible.
- The interpreter-class prediction failed, and the design has shown no lift on that class.
- The review transport (an external evaluator service) and the research tooling used to score some experiments are not included, so those experiments cannot be re-run from this repository alone. Their pre-registrations, results and audits are.
