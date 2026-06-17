# Second Independent Analysis ("5.5 attempt" — read-only Codex thread review)

This is an independent read-only review produced by a separate analysis thread. It is provided as a cross-check against proposal_v1.md. Treat its claims as ALSO subject to adversarial verification — it is not ground truth, it is a second opinion.

**Executive Conclusion**
Aether-2 is the documented active harness line, but the repo does not prove it is a certified scored winner. The best evidence-backed path is to evolve Aether-2 into a smaller certified model-led evidence kernel, harvest MLPCP/Harbor receipt assets, and stop treating implemented harness lines as leaders until scored rows prove it.

Read-only constraints were honored. No files changed. Handoff was sent back to source thread `019ed2e8-f931-7122-b86d-5e513018f1d3`.

**Latest Leader / Runs Truth Table**
| Sense | Truth |
|---|---|
| Latest documented active/current line | Aether-2: AGENTS.md:287, README.md:9, variants/harness/README.md:48. But docs mention `runner/aether2` or `harness/aether2`; actual code is under aether/. |
| Latest scored leader | No fully promoted benchmark leader. Aether-2 is strongest active carrier, but unpromoted. MLPCP v3 has the strongest official Harbor single-task GPT-5.4-mini evidence, `qemu-startup` reward 1.000, but hard2 stayed 0 and the line is paused: variants/harness/mlpcp_v3/README.md:1. |
| Latest polished analysis | research/case_studies/aether2_run_analysis_20260615_l1_targeted.md (mtime 2026-06-16T22:40:19+0100); source bundle tracking/collab/aether2_run_analysis_20260615/l1_targeted_20260615T142411Z_full_analysis.md (mtime 2026-06-15T16:33:20+0100). |
| Latest raw/fresh artifacts | tracking/collab/aether2_g2_homologs/runs/20260616T143518Z and 20260616T141129Z. Not scoreable: each has 2 phase rows and 0 result rows. |
| Latest meaningful present score rows | G2 homolog run 20260612T185102Z/scoreboard.md, 5/5 pass. L1 targeted 2026-06-15: 6/10 scoreable pass, 4 fail, 4 invalid. |

**Repo-Evidence Chronology**
Older blocks/kernel and Active Evidence Kernel lines are useful history, not current proof. Combined Guard V1.5 hit targets but failed sentinel and included hardcoded task knowledge, so not promotable: variants/harness/decision_history.md:1.

`winning_harness_v1` is not a leader. The FABLE package says it was VM-scored and failed badly, and the raw ledger confirms family/private/benchmark/TB rows at 0 pass: tracking/collab/tbench_100_fable_context_pack_20260610/13_FABLE_5_DECISION_PACKAGE.md:1.

Aether-2 then becomes the right carrier by design fit, not by certified promotion. Its prompt is model-led and goal-shaped: aether/runtime/prompts.py:1. Its loop, verifier, Harbor bridge, env orientation, and traces are real assets: aether/control/loop.py:1, aether/runtime/verify.py:1, aether/runtime/bridge_harbor.py:1, aether/runtime/orientation.py:1, aether/traces/decision_trace.py:1.

**Architecture Comparison**
Keep Aether-2 as carrier: minimal, model-led, instrumented, and close to the desired principle: "model pilots, harness instruments, verifier reflects, ledger remembers, grader decides." But current namespace drift is severe: tools still import `runner.aether2` while current code imports `harness.aether2`; read-only import smoke showed those fail.

Harvest MLPCP v3, do not revive it wholesale. The Harbor runner, lean cockpit, receipt memory, and background/service lessons are valuable: variants/harness/mlpcp_v3/code/lean_cockpit.py:1, mlpcp_v2_harbor_task_runner.py:1. Its full lineage is paused/historical.

Treat scoreboards carefully. variants/scoreboards/README.md:1 says several files are structured summaries, not scored eval winners.

**Run And Failure Analysis**
Aether-2 G2 `20260612T185102Z` proves the basic loop can solve narrow custom homologs: 5/5 pass. But this is not TB2.0 proof.

G5 full_twice shows launch/eval collapse: attempt 1 had 241 tasks, only 19 valid-scored rows, 5 pass, 14 fail, 216 invalid launches; attempt 2 was contaminated/unusable: aether2_g5_outcome_scoreboard.md:1, aether2_g5_run_failure_taxonomy.md:1.

The 2026-06-14 analysis shows real solving ability but bad finalization: 7/22 scoreable pass, with false-clean verifier failures on hidden/reference/protocol/package boundaries: aether2_run_analysis_20260614.md:1.

The 2026-06-15 L1 targeted run improved launch validity but exposed verifier OVERBLOCKING: 6/10 scoreable pass, false-clean 0, false-blocked 6 due pseudo-requirement pollution and read-only verifier restrictions: aether2_run_analysis_20260615_l1_targeted.md:1.

**Root-Cause Map**
Observation: environment/eval substrate failures dominate first. Namespace/import drift, invalid launches, missing scorer rows, resource killed rows, and absent raw VM artifacts block reliable conclusions.
Observation: verifier/finalization is second. It first accepted self-authored evidence as clean, then overcorrected by treating harness wrapper text as task requirements.
Inference: context engineering is leaking meta-contract into task contract. The verifier sometimes grades the wrapper.
Inference: genuine model-capability ceiling is still UNCLEAR. Current failures are too contaminated by launch, verifier, service, and contract defects to claim GPT-5.4-mini is near its true ceiling.

**Recommended Harness/System Design**
Build a certified Aether-2 evidence kernel:
1. Clean task contract: objective, deliverables, constraints, grader-visible artifacts, forbidden actions.
2. Benchmark-native EnvContract v2: cwd/root, artifact roots, package scope, service lifecycle, ports, resource budget, grader paths.
3. Model-led goal loop: inspect, brief plan, act, collect evidence, repair, finalize.
4. Evidence receipts: independent vs self-authored vs weak evidence, with file hashes/output summaries.
5. Verifier reflection: no invented constraints, no wrapper pollution, repair guidance only.
6. Finalization: tolerant schema, explicit limitations, no completion unless evidence maps to task contract.
7. Harbor outer loop: official/native rows decide promotion.

**Goal-Based Prompt Strategy**
Use a small goal prompt, not a doctrine packet. Name the goal, success contract, environment facts, available tools, current evidence ledger, unresolved requirements, finalization rule. Strip benchmark wrapper text from "requirements." For GPT-5.4-mini, keep context compressed into structured receipts and retrieve only task-relevant files/logs.

**Tooling / Runtime / Verification**
First fix launch integrity: import smoke, canonical cwd, correct namespace, non-vacuous genericity check, explicit `invalid_launch` rows, abort-on-mass-failure. Then broaden safe read-only verifier commands enough to inspect reality without mutating state. Add service/process attribution and grader-visible artifact checks before more prompt mechanisms.

**Eval Plan**
Measure in this order: launch integrity known-bad plus ceiling; verifier contract-pollution homologs; fake-progress homolog board; service/runtime/qemu/video board; then a small official Harbor GPT-5.4-mini slice. Only after that test mechanisms A/B/A+B: evidence-strength verifier, EnvContract v2, escalation ladder, context reducer. Backlog: variant_hypothesis_backlog.md:1.

**Kill / Keep / Harvest**
Keep and repair Aether-2. Harvest MLPCP Harbor bridge, receipt cockpit, service/background-tool lessons. Kill `winning_harness_v1` as a leader narrative. Kill broad unscored variant work. Redesign verifier requirement extraction, namespace checks, task_done schema tolerance.

**Risks And Falsifiers**
If Aether-2 still underperforms after launch and verifier repair on a clean official Harbor mini slice, replace the carrier. If false-clean persists on fake-progress homologs, the verification architecture is wrong. If GPT-5.4-mini still fails validated tasks that stronger models pass, then mini needs task-local micro-tools and more aggressive context reduction, not more prose.

Tool reported 273,313 tokens used, ~7m 23s elapsed. Target model referenced as GPT-5.4-mini / GPT-5.5.
