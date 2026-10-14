# Governance: the rules, the incidents behind them, and what they did

Each rule below has four parts: what it says, the incident that prompted it, the evidence that it worked or failed, and its status. Rules are listed in the order they mattered most to the reported results. Where a rule failed, the failure is recorded next to it.

## 1. No Fake Work

**Rule.** A change is done only when real work is proven by evidence that does not depend on the implementer's own claim. A check turning green is not the goal. The underlying thing being true is the goal. Stub files, no-op shims, and synthetic data that exist only to pass an existence or import check are never complete.

**Incident.** A dependency was handed off as fixed. Its preflight was green and its tests passed, but the files were empty stubs and no-op import shims. The rule text was added to the operating doctrine on 8 Jul.

**Evidence it worked.** On 10 Oct, placeholder evaluation entry points were changed to fail closed after a 3 Oct finding that they could create false "certified" rows.

**Evidence it failed.** On 14 Jul a batch scorer accepted no-op commands (a `chmod`, a `pytest --co`, a `grep`) as passing routes. The rule did not stop this. An adversarial review of the scorer did. No hook enforces the rule, so it depends on review.

**Status.** Active. Enforced by review, not by tooling.

## 2. Propose, never blind-build

**Rule.** Before any non-trivial change, write a current-state map: what exists, what matches the target, what violates it, what is missing, and the smallest next step. Skipping the map is grounds for rejecting the work. New mechanisms need approval.

**Incident.** Architecture drift. Harness pieces had been built to compensate for weak models, and the target architecture was unclear.

**Evidence it worked.** The vision document (2 Jul) gave a one-question test: if a stronger model would make a piece redundant or want to override it, it is a crutch and is removed. Compiler fallbacks were removed on 4 Jul. Solver-requested reconfiguration was deleted on 5 Jul, touching 2,305 files.

**Evidence it failed.** The canonical-line decision was reversed within one day. A carve-down plan (2 Jul) was superseded by a canonical-line decision (3 Jul), because governance documents routed new work to the wrong line. The map-first rule was not yet applied to the line choice.

**Status.** Active.

## 3. Separate verifier, review gate chosen by risk

**Rule.** Completion is judged by a verifier that reads task-visible state, not the solver's story. Review depth is chosen by risk: none, adversarial only, a review skill, or the review skill plus an adversarial pass. One broad review and one finding-focused re-review is the normal limit. Repeated structural findings trigger a redesign or a block.

**Incident.** On 9 Jul a 15-task batch reported 11 of 14 passes. Most passes were not confirmed by the verifier. The verifier itself had been starved by rate limits.

**Evidence it worked.** An adversarial audit of the working tree (8 Jul) proved by tree hash that the uncommitted code produced the reported result, and it found three false-cleans. The verdict was to keep the codebase, not rewrite it. A 28 Sep dual-review gate for a repair was blocked, and the reviewer was changed.

**Evidence it failed.** Same-model review was weak. In a 13 Oct false-completion study, a fresh-context reviewer held 1 of 16 good states and caught 3 of 12 bad ones. The verifier also gave 5.4% verdicts in the 9 Jul storm (see case study 1). The independence-kind gate added on 9 Jul does not prove the verifier judges correctly.

**Status.** Active. The verifier's judgement quality is still open.

## 4. Evidence tiers before promotion

**Rule.** A claim gets promoted only on scored evidence. A single run is a lead, not a result. Scoreboards and result rows are the source of truth for promotion. A win that does not reproduce is recorded as a downgrade.

**Incident.** On 21 Jun an adaptive variant was reported as a deterministic win on one task.

**Evidence it worked.** Reproduction gave 3 of 4 for the variant against 1 of 4 for the baseline. The claim was downgraded to a measured difference, not promoted. An 8-task A/B then gave 0 wins, 0 regressions, and 8 unchanged, with six failures classed as environment or infrastructure. A separate variant with a real regression against the baseline (22 Jun) was not promoted.

**Status.** Active.

## 5. Pre-registration and a sealed falsifier

**Rule.** Before a held-out run, record the prediction, the baseline, the ceiling, the known-bad case, and the falsifier. Seal the pre-registration in version control before any result exists. A campaign with an invalid slot does not qualify.

**Incident.** Earlier claims had outrun their evidence: the June adaptive-variant win (rule 4) and several August boards that were read as stories before they were scored. The rule fixes the verdict before the data arrives.

**Evidence it worked.** On 11 Oct the pre-registration was committed before the results commit. The held-out comparison gave the harness 5 of 9 against 4 of 6 for a stock reference agent on the same model. The falsifier fired and the commit subject says so. See case study 2.

**Evidence it failed.** A pre-registration does not guarantee a valid run. On 4 Aug a locked official board was graded invalid on 15 of 15 rows. The pre-registration was intact, but the rows were not usable.

**Status.** Active. Rule for any rerun: a new pre-registered campaign, compared against the earlier numbers.

## 6. Invalid-row accounting

**Rule.** Invalid rows are kept and counted. They are not replaced by retries and not dropped. Provider, protocol, runtime, environment, grader, and model validity are classified separately. Invalid runs never enter the capability score.

**Incident.** On 30 Aug one task row scored 0.0 on the official grader, but its paid attempt lacked cost telemetry. The row was at risk of being quietly re-run.

**Evidence it worked.** The row was logged as a consumed invalid measurement, and the forensics covered five official trajectories and 62 provider attempts. A later board (23 Jun) with 20 of 20 rows invalid before model work was classed as invalid, not as a model failure. See case study 3.

**Evidence it failed.** Recording is not the same as analysis. Invalid rows still need a root cause. About 83% of recorded notebook entries carry a HOLD or NONE commit field, so the accounting is only as good as the notebook discipline.

**Status.** Active.

## 7. No blind retries; run freeze

**Rule.** During a run, no source, prompt, schema, scorer, provider config, task pack, or verifier changes. Never replace an invalid row with a retry. Preserve every row.

**Incident.** A capacity change silently removed a control at call 86 of an overnight workstream (6 Oct).

**Evidence.** The same 6 Oct audit found the overnight lane had 0 of 26 rows rewarded. The model stated the correct hypothesis at call 8 and dismissed it without testing it.

**Status.** Active.

## 8. Critical-path-only execution

**Rule.** Stop an activity when two consecutive activities change no decision item. Serial review loops before a gate are not free.

**Incident.** On 29 Aug, serial pre-gate review and delegation churn delayed behavioural progress.

**Evidence.** The rule was adopted on 29 Aug. A related rule came later: a duplicate-state breaker stops retries when nothing has changed. It followed the 23 to 24 Aug "keep going" nudges.

**Status.** Active.

## 9. One writer per branch

**Rule.** One writer per branch. Claude works only on its own branch prefix in its own worktree. No push or merge without approval.

**Incident.** On 7 Oct a Claude edit was committed in a Codex worktree that another agent was actively using. It was then undone by a soft reset.

**Evidence.** Worktrees accumulated: 140 were registered on 12 Oct, of which 30 were prunable. The rule is a coordination convention, not a lock, and it depends on agents following it.

**Status.** Active. Not enforced by tooling.

## 10. Lease and reaper for paid compute

**Rule.** No paid compute without approval. Machines are deallocated unless a batch is ready. Idle machines are reaped.

**Incident.** A July month-to-date cost audit (23 Jul).

**Evidence.** Lease-based deallocation was adopted on 23 Jul. An idle reaper was added on 29 Sep. Detached background processes were still reaped at the end of an exec on two occasions (19 Jun, 14 Aug), which led to lease registration.

**Status.** Active.

## 11. Handoff closure with a delivery receipt

**Rule.** A handoff is a baton, not a stop. A file on disk is not a delivered handoff. The originating orchestrator must receive it, and the receipt is recorded. See [the handoff template](templates/multi-thread-handoff.md).

**Incident.** A 91-worker fan-out on 2 Jun, and acknowledgement-only replies.

**Evidence.** Handoff commits per month were May 8, Jun 3, Aug 29, Sep 49, and Oct 23 (to 12 Oct).

**Status.** Active.

## 12. Publication and provenance gate

**Rule.** Public material is checked for private paths, names, hosts, and held-out material before release. The public and private repositories are split.

**Incident.** Public release (17 Jun) and a leakage cleanup the next day.

**Evidence.** The public release candidate removed about 4.56 million lines of private material. Machine paths were removed from public history on 9 Sep.

**Status.** Active.
