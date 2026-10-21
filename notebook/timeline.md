# Timeline, late 2025 to October 2026

This page lists the key dated events: generations, evaluation layers, audits, the held-out evaluation, and the development sweep.
The key result is a period of five generations, each ended by a failed test or audit rather than by a win, with one falsified lift claim.
This matters because it shows the order in which claims were tested and withdrawn.

**Generations:** Gen 1 planner memory (late 2025 to Feb 2026), Gen 2 receipt kernel (May to Jul 2026), Gen 3 architect, solver, verifier (Jul to Aug 2026), Gen 4 persistent worker with independent verifier (Aug 2026 onward, production from 8 Sep), Gen 5 Aether (in development from 12 Oct 2026).

## 2025

- **Late 2025:** Gen 1 starts: a planner acts as external memory for a stateless coding agent.

## 2026

- **2026-02-20:** Gen 1 pivots for the third time (earlier pivots on 22 Dec 2025 and 11 Jan 2026) and ends on 25 Feb. Its oracle mount had leaked answers; one idea survived, the oracle-free verifier.
- **2026-03-30:** Governed multi-agent model proposed: one principal, bounded specialists, a separate historian.
- **2026-04-04:** First mechanism map. Its status is "not complete", and it records that verifier status and final task success are not equivalent.
- **2026-04-06:** Deep synthesis waves run as about 120 sessions in one week.
- **2026-05-13:** Eval-first reset. Promotion authority moves from packets to scored evaluation.
- **May to Jul 2026:** Gen 2 (receipt kernel) is built. Its "done" claims need receipts.
- **2026-05-17:** Combined attribution guard: target 2/2, sentinel 0/1. Not promoted.
- **2026-06-12:** Gen 2 full run: 216 of 241 trials never launched validly; 5 of 19 valid trials passed.
- **2026-06-17:** Public release cut. Private directories removed. Unofficial model route removed.
- **2026-06-18:** Offline end-to-end eval becomes the baseline check; the 500-line module cap is enforced.
- **2026-06-21:** Adaptive profile claim downgraded. Replication 1/4 baseline vs 3/4. Eight-task A/B: 0 wins, 0 regressions. Two evidence tiers adopted.
- **2026-07-03:** Gen 3 (architect, solver, verifier) becomes the canonical line. Gen 2 becomes reference.
- **2026-07-08:** Independent audit recommends keeping the codebase; no rewrite.
- **2026-07-09:** Rate-limit storm. 13 of 20 parsed verifier verdicts blocked by tooling. Backoff, rate limiter, and independence gate added.
- **2026-07-16:** Native verifier promoted: Stage A1 14/14, Stage B 41/42; locked at commit 729c8e1.
- **2026-07-19:** Gen 3 forensic audit: NOT READY, 20 numbered findings. Its 9/9 result covers three narrow scenarios only.
- **2026-08-02 to 08-04:** Architect boards score 6/12, 5/12, 4/12; no winner declared. The fixed official board is grader-invalid on 15 of 15 trials.
- **2026-08-05 to 08-08:** Gen 4 prototype (persistent worker with an independent verifier) built.
- **2026-08-10:** Stable-context dedup stopped for promotion: -29% per call, +56% solver calls.
- **2026-08-15:** Discovery board admits 0 of 8 trials and 0 of 4 pairs. No cognition choice made.
- **2026-08-19:** Architect model calls set to zero; Gen 3 removed from production. Gen 4 (persistent worker, independent verifier) merged.
- **2026-08-22:** "Destabilization" story retracted as unsupported.
- **2026-08-30:** An invalid official trial is logged as a consumed invalid measurement and kept.
- **2026-09-08:** Gen 4 released to production. Qualification: 301/301 local, 301/301 shared Linux, 16/16 real Docker.
- **2026-09-12:** Solver root-cause census. Pilot of a semantic completion review: 0 wins, 1 loss, 4 ties across 5 valid pairs.
- **2026-09-15:** All-workstreams audit. Held-out evaluation (September set) 0 of 3 official passes; workstreams C and D not advanced.
- **2026-09-30:** A repair pass closed as an incomplete discovery screen, with 50 valid trials kept.
- **2026-10-01:** Pre-held-out audit: by turn 16, 98.8% of a 266 KB request was non-observed content.
- **2026-10-05:** Grader-validity audit: two known-bad controls scored 1.0. Provider streaming fix ends the hung calls.
- **2026-10-06:** Overnight workstream audit: 0 of 26 trials rewarded.
- **2026-10-08:** Claude takes over orchestration; Codex and ChatGPT workstreams closed. 24 + 8 + 11 branches merged in about 72 hours.
- **2026-10-11:** Held-out evaluation (October set) falsifies the lift claim: Aether 5/9 vs stock reference agent 4/6.
