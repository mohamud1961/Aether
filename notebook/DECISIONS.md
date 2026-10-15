# Decisions

This table lists 18 decisions from March to October 2026, one row each.
The key result is that most decisions tightened a claim or removed a path after a result failed its test, and several reversed an earlier choice.
This matters because each row names the evidence used and what it changed in code, process, or claims.

| Date | Decision | Reason | Evidence | What it changed |
|---|---|---|---|---|
| 2026-03-30 | Use a governed multi-agent model: one principal, bounded specialists, a separate historian | One agent was too limited; an ungoverned group was too complex | Working proposal dated 2026-03-30 | Set the roles that later rules refined, including one writer per branch|
| 2026-05-13 | Reset to eval-first; promotion authority moves to scored eval | Work packets and route manifests were not proof | Governance text dated 13 May; about 20 worker prompts on 21 May | Promotion needed scored eval evidence|
| 2026-06-17 | A handoff closes only with a delivery receipt; a handoff is a baton, not a stop | 91-session fan-out on 2 June and acknowledgement-only replies | Handoff commits per month: May 8, June 3, August 29, September 49, October 23 (to 12 Oct) | Added the handoff-closure rule|
| 2026-06-21 | Downgrade the adaptive profile "win" from deterministic to a measured advantage; no promotion | The N=1 claim did not hold at full strength | Replication: baseline 1/4, adaptive profile 3/4; then 8-task A/B: 0 wins, 0 regressions, 8 unchanged | Two evidence tiers adopted; the profile kept as a flag-gated variant|
| 2026-07-03 | Gen 3 (architect, solver, verifier) becomes the canonical line; Gen 2 becomes reference | Governance docs routed new work to the wrong line; replaced the 2 July carve-down plan | Decision one day after the carve-down plan | Gen 2 kept as reference only|
| 2026-07-04 | Remove compiler fallback branches that supplied default configurations | Judgement layer must have zero fallbacks | Ledger key entry 8; no score | Missing judgement config now fails visibly|
| 2026-07-09 | Add backoff with jitter and a request-rate limiter; add an independence gate for completion evidence | Rate-limit storm: verifier verdicts blocked by tooling; two false clean completions passed the gate | 13 of 20 parsed verifier verdicts blocked by tooling; 82 rate-limit strings; 3 of 4 reward-1.0 passes were verifier misses; false cleans scored 0.98 and 0.93 | Backoff, limiter, and gate added; no 15-way parallel runs on one deployment|
| 2026-07-14 | Add adversarial review of batch scorers | Batch scoring accepted no-op commands as passing | Count not recorded | Scorers reviewed before their results count|
| 2026-08-10 | Stop promoting stable-context dedup; open a decision-contract A/B | Per-call saving raised whole-trajectory cost | Prompt -29% per call; solver calls 16 to 25 (+56%) in a 3-task live A/B | Dedup kept as a diagnostic only|
| 2026-08-19 | Remove architect model calls from production | Architect-authored proof authority was unsound; the ladder never produced a clean official win | architect_model_calls = 0; 19 July verdict NOT READY with 20 findings; verifier ran 0 real checks in 20 runs | Authority moved to the primary solver plus an independent verifier|
| 2026-08-19 | Merge the persistent-worker and independent-verifier lines | The two lines held overlapping responsibilities | Matched crossover 3/3 vs 3/3 official trials (10 Aug); qualification 301/301 local, 301/301 shared Linux, 16/16 real Docker | Gen 4 became the production line (released 8 Sep)|
| 2026-08-22 | Retract the "destabilization" story | Not supported by the data | One task reclassified as a cost tie (both arms 1.0) | Corrections recorded before a task is locked|
| 2026-08-29 | Critical-path-only execution: stop when two consecutive activities change no decision | Delegation churn delayed behavioural progress | Rule text; no score | Serial pre-gate review loops cut|
| 2026-08-30 | Log an invalid official trial as a consumed invalid measurement; do not replace it | Paid attempt lacked usage telemetry | Official score 0.0 kept; 62 provider attempts reconstructed | Invalid measurements are counted, never replaced|
| 2026-10-11 | Seal the pre-registration before results; state the falsifier in the commit history | Honest verdict design | Pre-registration commit abd6b615c before result commit 1d9bbf07d | The held-out result could be checked against a fixed prediction|
| 2026-10-11 | Record the held-out result as a falsified lift claim; do not soften it | Pre-registered falsifier triggered | Aether 5/9 (56%) vs stock reference agent with the same model 4/6 (67%); held-out task C 0/3 vs 0/2 at a 900 s limit | Lift claim withdrawn; any rerun needs a new pre-registered campaign|
