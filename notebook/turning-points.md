# Turning points

This page lists 25 moments where a claim changed, a result overturned an assumption, or a process rule was added.
The key result is that most turning points were negative or corrective: a failed check, a withdrawn claim, or an invalid run that was kept on the record.
This matters because the same pattern (a claim tested and narrowed) is the reason the later decisions exist.

### 2025-11-22 · A planner acts as the agent's memory
- **What happened:** Gen 1 used a planner as external memory for a stateless coding agent.
- **What changed:** Three pivots followed (22 Dec 2025, 11 Jan 2026, 20 Feb 2026). An oracle mount leaked answers and a phase could be bypassed.
- **Numbers:** Gen 1 ran from 22 Nov 2025 to 25 Feb 2026.

### 2026-04-04 · The first mechanism map separates verifier status from task success
- **What happened:** The first synthesis recorded that internal verifier status and final task success are not equivalent.
- **What changed:** Verifier-versus-grader mismatch stayed in the failure taxonomy as a standing family.
- **Numbers:** Six exploratory-anchor families; status "not complete".

### 2026-04-06 · Deep synthesis waves run as about 120 sessions
- **What happened:** Synthesis was run in waves, one workstream per source family, over one week.
- **What changed:** Wave prompts became standing prompt and skill files.
- **Numbers:** About 120 sessions, 6 to 13 April.

### 2026-05-13 · Eval-first reset moves promotion to scored evidence
- **What happened:** The project was reset so that promotion required scored eval results, not packets or route manifests.
- **What changed:** Governance text was rewritten; work moved to eval-first slices.
- **Numbers:** 267 sessions in May.

### 2026-05-17 · A combined attribution guard fails its sentinel
- **What happened:** The combined guard hit its target but regressed on the sentinel task.
- **What changed:** Marked "kill for promotion"; kept for follow-up.
- **Numbers:** Target 2/2; sentinel 0/1.

### 2026-05-18 · A winner search finds no winner
- **What happened:** A phase that searched for a winning harness across seven task families found none.
- **What changed:** No candidate was carried forward from that search.
- **Numbers:** winner_found = 0 across 7 families.

### 2026-06-12 · Gen 2 full run: most trials never launched validly
- **What happened:** A full board of Gen 2 trials ran, but most trials failed before scoring.
- **What changed:** Launch-integrity checks were added before any board counts; the board was not used as capability evidence.
- **Numbers:** 216 of 241 trials INVALID_LAUNCH; 19 valid trials; 5 passed (valid 5/19 = 26%).

### 2026-06-21 · The adaptive profile "win" shrinks to a smaller effect
- **What happened:** A single-task win (N=1) was replicated on four pairs.
- **What changed:** The claim was downgraded to a measured advantage, and two evidence tiers were adopted.
- **Numbers:** Baseline 1/4; adaptive profile 3/4.

### 2026-07-03 · Gen 3 becomes canonical one day after the carve-down plan
- **What happened:** A plan to carve down Gen 2 was replaced the next day by a decision to make Gen 3 canonical.
- **What changed:** Governance docs were updated; new work targeted Gen 3.
- **Numbers:** One day between the two plans.

### 2026-07-05 · Solver-requested reconfiguration is deleted
- **What happened:** The path that let the solver request a reconfiguration was removed.
- **What changed:** A single-shot verifier-triggered reconfiguration was treated as a defect.
- **Numbers:** 2,305 files in one commit.

### 2026-07-09 · A rate-limit storm leaves most verifier verdicts unreturned
- **What happened:** Parallel verifier runs hit the rate limit on a single deployment. Most verdicts were blocked by tooling, and two false clean completions passed the gate.
- **What changed:** Backoff with jitter, a request-rate limiter, and an independence-kind gate were added. Parallel runs on one deployment were stopped.
- **Numbers:** 13 of 20 parsed verdicts blocked by tooling; 82 rate-limit strings; 3 of 4 reward-1.0 passes were verifier misses; false cleans scored 0.98 and 0.93.

### 2026-07-14 · The batch scorer passes no-op commands
- **What happened:** Batch behavioural scoring counted `chmod`, `pytest --co`, and `grep` as passing routes.
- **What changed:** Scorers were put through adversarial review before their results counted.
- **Numbers:** Not recorded.

### 2026-07 (approx.) · The Gen 3 verifier runs no real checks
- **What happened:** A phase-2 audit found that verifier checks written in free text were never compiled into runnable checks.
- **What changed:** An executable check path was added, with a sandboxed overlay.
- **Numbers:** 0 real checks in 20 runs; every verdict was ready=True by evidence fallback.

### 2026-08-04 · The fixed official architect board is grader-invalid
- **What happened:** The fixed official board was audited and every trial was found grader-invalid.
- **What changed:** No promotion; the failure pattern was logged as layered (weak proof contracts, provider instability, proxy reasoning).
- **Numbers:** 15 of 15 trials grader-invalid.

### 2026-08-10 · Stable-context dedup cuts prompts and raises total cost
- **What happened:** A per-call prompt reduction increased the number of calls needed to finish.
- **What changed:** Dedup stopped for promotion and was kept as a diagnostic; a decision-contract A/B was opened.
- **Numbers:** Prompt -29% per call; solver calls 16 to 25 (+56%) in a 3-task live A/B.

### 2026-08-19 · Architect removed from production; persistent line merged
- **What happened:** Architect model calls were set to zero, and the persistent-worker line was merged with the independent verifier.
- **What changed:** Authority moved to a primary solver plus an independent verifier. The architect was removed from production.
- **Numbers:** architect_model_calls = 0; qualification 301/301 local, 301/301 shared Linux, 16/16 real Docker.

