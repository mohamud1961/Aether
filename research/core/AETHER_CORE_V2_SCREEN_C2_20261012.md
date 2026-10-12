# Aether Core v2: pre-registered screen C2 (12 October 2026)

- **Code:** commit `5897a3a4a`.
- **Design and decisions:** `tracking/ledger/inbox/20261012_aether_core_v2_raw.md`.
- **Contamination:** any later game-port-build row is **post-failure** and labelled that way.

## Arm
- `v2`: `--agent-mode aether-core --core-context clm --core-repl on --core-review reviewer_progress`.
- **Baseline:** C1 rows (Core v1, `project` context, no REPL), recorded in the ledger entry.
- **Scheduling:** one row at a time.

## Rows
1. **Smoke:** repo-secret-recovery. This container has no `python3`, so it exercises the "REPL unavailable" path.
2. interpreter-build × 2.
3. verified-compiler-build × 1. Regression check: C1 core_off solved it.

## Predictions (written before any v2 row)

| # | Prediction | Measured by |
|---|---|---|
| P1 | No request exceeds the 32k budget | Max provider `input` tokens per call ≤ 34k, allowing for the estimate |
| P2 | Mean input per call on interpreter-build is ≤ 20k tokens (C1: ~25k on core_off) | Run record |
| P3 | ≤ 5 provider 429s per row when rows run serially (C1: 31 and 95 failed attempts) | `provider_failures_by_status` |
| P4 | Every interpreter-build row gets progress@0.35, progress@0.7 and final reviews, with 0 review errors | `review_kinds` |
| P5 | GLM uses `python` for ≥ 3 cells on each interpreter-build row | `python_cells` |
| P6 | GLM **does not** edit its own context (0 accepted edits); the automatic checkpoint fires ≥ 1 time per interpreter-build row. Based on the earlier context-file arm, where GLM wrote zero notes | `clm` stats |
| P7 | interpreter-build: ≥ 1 of 2 solved (C1: 0/2, with core_off at 2/3 grader tests) | Grader |
| P8 | verified-compiler-build stays solved | Grader |

## Falsifiers and what follows
- **Any review error, any silent mechanism failure, or a request over budget:** a defect, fixed before any further row.
- **P5 fails** (python unused): the REPL is not adopted by GLM; report that, and consider removing the tool.
- **P7 fails and no row gets further than C1's 2/3 grader tests:** v2 shows no measured lift on interpreter-build. Make-doom is still run once as the post-failure comparison, labelled as such, not as a win.

## Budget
- **Spent so far:** about £0.6.
- **This screen:** 4 rows ≈ £0.6–1.0, plus VM time.
- **Stop line:** £4.50 cumulative.

## Amendment, 12 Oct ~01:25 UTC (during C2 row 1, before its result)

### New finding: the GLM deployment accepts images
- **Probe:** GLM answered three discriminating image probes correctly:
  - a teal fill;
  - left/right halves;
  - a square's position.
- **Control:** with no image sent, it said it saw none.
- **Why it matters:** the C1 interpreter-build failure was a wrong frame (similarity 0.81), which GLM never looked at.

### Change
- **v2.1** = v2 + the `view_image` tool (`--core-images on`), commit recorded below.
- **Row 1** (v2, already running) is kept and reported as v2.
- **Remaining rows:** interpreter-build ×2 and verified-compiler-build ×1, all run with v2.1 instead of v2.

### Predictions P1–P8 still apply, plus:
- **P9:** on each v2.1 interpreter-build row that produces a frame, GLM calls `view_image` on it at least once.
- **P10:** a v2.1 interpreter-build row whose frame is wrong is either fixed or reported as wrong; it is not finished as correct without the image being looked at.

### Mid-run observation (row 1)
- **P5 is at risk:** GLM ran Python only as one-shot terminal heredocs (2 of 53 terminal calls) and never used the REPL tool.

## Amendment 2, 12 Oct ~02:00 UTC (during C2b row 1, before its result)

### Row 1 (v2) result
- **Not solved:** 2/3 grader tests, timeout.
- **Frame similarity now passes** (C1 failed it at 0.81).
- **Failed check:** the grader wants the line `I_InitGraphics: DOOM screen size: w x h: 320 x 200` in stdout. Doom's startup text was garbled, which points to a printf/varargs bug in the interpreter.

### Predictions
- **Pass:** P1 (max 29.9k), P2 (mean 16.0k), P3 (0 failures), P4 (3 reviews, 0 errors), P5 (9 REPL cells).
- **P6 failed in the good direction:** GLM made 3 accepted context edits, plus 2 checkpoints.

### Diagnosis
- **GLM** saw the garbled bytes in 4 tool results and never reasoned about them.
- **the reviewer** saw none of them. Its evidence was the solver's last 8 actions, and all 3 review requests lacked the program output.

### v2.2 changes
- The reviewer reads the tail of every terminal log and the newest REPL output itself, with non-printing bytes made visible.
- the reviewer gets a new malfunction question:
  - choices: garbled / errors / suspicious values;
  - findings are reported in progress and final reviews;
  - at confidence ≥ 0.8 it also holds a finish (still at most 2 holds).
- One generic solver-prompt line: unexplained output is a bug until explained.

### Schedule
- **C2b row 1** stays v2.1 (it measures `view_image`).
- **The rest runs on v2.2:** interpreter-build ×1, then verified-compiler-build ×1.

### New predictions
- **P11:** on each v2.2 review, output_logs are present in the reviewer request.
- **P12:** if the program output is garbled, at least one v2.2 review reports a malfunction.

## Post-run audit protocol (from 12 Oct ~01:55 UTC)
- **Every row** is audited with `tools/aether_program/core_audit.py` before the next change. It covers outcome, time split, steps, context, caching, tooling, verification, provider and cost.
- **Findings** are recorded here.

### Audit of C1 core_off vs C2 row 1 (v2), interpreter-build
| Dimension | C1 core_off | C2 row 1 (v2) |
|---|---|---|
| First file written | 525 s | 236 s |
| Mean / max input tokens | 25.7k / 55.7k | 16.0k / 29.9k |
| Cache ratio | 85% | 82% |
| Model / tool time | 832 / 667 s | 763 / 977 s |

- **Garbled output** was first visible at 311 s on v2; unnoticed for 25 min.
- **Urgent nudges** fired 10 times.
- **the reviewer verdicts** were all "incomplete" at 0.44–0.69, with only 2 coarse criteria.
- **C1 verified-compiler-build:** 660 s of `sleep` inside commands; finished with 3 min to spare.

### Added to v2.2 before its rows
- The urgent nudge fires at most once every 3 turns.
- The terminal description says to run long commands in the foreground with `wait_s`: the call returns at completion, unlike `sleep N`.
- The audit reports "not traced" for rows that predate retry tracing.

### Audit of C2b row 1 (v2.1, `784b7f558`), interpreter-build
- **Outcome:** 0/3 grader tests, timeout at 1785 s. **P7 not met on this row.**
  - No frame was produced: the interpreter failed while loading the WAD (`Wad file doom2.wad doesn't have IWAD or PWAD id`) from 810 s until the end.
  - Rows 1 and 2 (v2 at 2/3, v2.1 at 0/3) differ by more than the arm changed. At n=1 this is run-to-run variance, not a v2.1 effect.
- **P9 and P10 were not tested:** no frame existed, so `view_image` was never called (0 calls).
- **Spend and provider:** 0 provider failures, $0.175.
- **Context:**
  - mean 16.2k, max 29.6k input tokens;
  - 83% of input tokens cached;
  - 2 edits and 3 checkpoints;
  - 17 urgent nudges (this build predates the throttle).
- **Tooling:** 52 REPL cells, so GLM adopted the REPL. Many were `subprocess.run("sed ...")`, i.e. the REPL used as a shell. It used only 1 terminal.
- **New metric: time lost to hung runs.**
  - This row had 11 commands that ran until their own `timeout N` killed them, totalling **675 s (38% of wall time)**.
  - The C2 v2 row had 4 such commands, totalling 465 s.
  - The guest program printed its fatal error and then hung, apparently because its exit was never handled. GLM kept raising the timeout from 20 to 150 s instead of asking why the run never ended.
- **Verification defect (found and fixed):**
  - The progress review at 740 s, and again at 1267 s, told the solver *"done with unverified parts (0.84)"* with **nothing listed**. At 740 s the interpreter had never been run.
  - Cause: the reviewer rated every criterion "indirect", but `judge` only listed criteria rated "none" or "contradicted".
  - Fix: every criterion not shown directly now goes in the list with its evidence class (indirect / only your own check / none / contradicted). Finish holds are unchanged.
- **Re-exploration after context edits:**
  - 2 calls exactly repeated a call made before the edit or checkpoint.
  - Qualitatively, GLM re-ran `ls /app` and re-read files after its edit at 119 s. That is a modest cost of the context loss.

### Queued for v2.3 (not applied to the running v2.2 rows, so C2c stays one clean config)
- The review lists every criterion it cannot directly confirm.
- One generic solver-prompt sentence: an unexplained duration (a run that is killed by its own timeout) is a hang to diagnose.
- The audit gains `runs_killed_by_own_timeout`, `seconds_in_those_runs` and `repeats_right_after_context_events`.

## Overnight D1 dev loop (from 12 Oct ~03:20 UTC)
- **Principal's instruction:** advance Aether as far as possible with £10, auditing after every run. The make-doom frozen run is deferred.
- **Setup:** a queue driver on the VM runs one row at a time and merges `a working branch` before each row. Every row records its exact commit.
- **First sweep:** v2.3 across 12 TB2.1 tasks.

### Audit of C2c (v2.2) interpreter-build
- **Outcome:** 0/3 grader tests, timeout. The interpreter was still debugging WAD lump lookup at the end.
- **P11 met:** all 3 the reviewer requests contained `output_logs`.
- **P12 met:** the malfunction question flagged `errors_or_crashes` at 0.97 and 0.91 in the progress reviews.
- **Context and cost:** mean 16.4k tokens, 85% cached, $0.20.
- **P7 failed:** 0 of 3 interpreter-build rows solved across v2, v2.1 and v2.2.

### Audit of C2c (v2.2) verified-compiler-build: substrate bugs found
- **Outcome:** **P8 met.** The grader passed all 3 tests (reward 1), but the agent was still running at the 2385 s limit.
  - Only 146 s of the run was model time.
  - First file written at 2036 s.
- **Bug 1: lost completion marker.**
  - Each `apt-get install` was reported "still running" for 240–600 s, although the next command in the same terminal ran at once.
  - Cause: the command and its completion marker were queued as separate stdin lines, and apt/dpkg read stdin and swallowed the marker.
  - Fix: the command body runs from a file and the shell reads a single line, `. file; printf marker`.
  - Test: `read -t 1` used to report `read-rc=0`, i.e. it ate the marker. Now it times out and the marker prints.
- **Bug 2: Ctrl-C never worked in containers.**
  - Found while verifying bug 1 on Linux. The existing interrupt test fails there on the old code too; the macOS suite only runs the pipe path.
  - Cause: the terminal was launched with `&` from a non-interactive `sh`, so SIGINT was ignored, and that disposition was inherited by every command.
  - Fix: launch with `setsid -f`, which leaves only SIGHUP ignored, verified via `/proc/<pid>/status`.
  - All 6 terminal tests pass on the Linux pty path.
- **Remaining waste on this row:** 390 s of `sleep N` polling a background `make`, despite the v2.2 guidance to wait in the foreground.

### What the lost marker cost (new audit metric `suspected_lost_markers`)
| Row | Lost markers | Seconds waiting on a finished command |
|---|---|---|
| C2c verified-compiler-build (v2.2) | 5 | **903** (38% of the run) |
| D1 r02 legacy-sim-build (aeaf884f, before the fix) | 1 | **300** (84% of a 358 s row) |
| C2c interpreter-build | 1 | 0 |

- **Prediction:** rows on `a3e580ff` or later show 0 suspected lost markers.

### D1 rows on `aeaf884f` (v2.3, before the terminal fix)
- **r01 dual-language-build:** solved in 138 s, $0.01.
- **r02 legacy-sim-build:** solved in 358 s, $0.008. 300 s of that was the lost marker.
- **r03 vuln-fix** (`a3e580ff`): solved in 47 s.
- **r04 credential-recovery-recovery:** solved in 114 s.
- **r05 db-coverage-build:** solved in 141 s.
- **Lost markers since the terminal fix:** 0 across r03–r05.

### Pool expanded for headroom
- 5 of 5 rows on the original pool were solved, so it can't tell improvements apart.
- Added 17 TB2.1 tasks marked "hard" (`d1/pool_d1.json`). Skipped: GPU/VM-heavy tasks, the exclusion list, and `async-cancel`, whose built-in pin conflicts with the pool and refuses to launch.
- Two lanes now run in parallel, sharing a lock-protected queue.

### r07 cipher-diff-attack: solved, with 2 false holds
- the reviewer read the state as "fully_done" (0.92 and 0.95), but the malfunction rule held both finishes. The cause was AssertionError tracebacks from GLM's early exploratory REPL cells, which were long resolved.
- **Tally for the malfunction-hold rule:** 2 false holds and 0 true holds in D1. Its useful signal was in progress reviews (C2c interpreter-build).
- **Change:** malfunction findings still go into progress, final and finish feedback, but only the failure-mode reading can hold a finish.
