# Stage 1 Terminal Run — Full Architect / Solver / Verifier Audit

- **Run id:** `20260701T_runtime_enforcement_stage1_timeoutfix_py311_retry`
- **VM:** `harnesseng-regular-01` (HARNESSENG-RG), remote root `/home/azureuser/harnesseng_vm/aether_next_build`
- **Start:** 2026-07-01 16:23:35 UTC · **End:** ~16:55 UTC · **Terminal:** yes (results.json 3/3, process exited)
- **Auditor:** Claude (Opus 4.8). Evidence pulled live from the VM via `az vm run-command invoke` (raw `results.json` receipt summaries, `verifier_evidence/*` packets/parsed results/active findings, workspace snapshots). Not a remote summarizer.
- **Canonical-run note:** 5 Stage-1 directories accumulated on the VM today (13:43, 14:57, 16:07, 16:22, 16:23) from uncoordinated prior agents. **Only the 16:23 `_retry` is canonical.** The other four are superseded diagnostics and must not be mixed into evidence.

## Result rows (all VALID)

| Task | Reward | Status | Classifier | Steps | Reconfig | Grader |
|---|---|---|---|---|---|---|
| filter-js-from-html | 0.0 | incomplete | model_limit (med) | 30 | 2 | exit 0, no passing check |
| sparql-university | 0.0 | incomplete | model_limit (med) | 30 | 0 | exit 0, no passing check |
| openssl-selfsigned-cert | 1.0 | completed | none (high) | 2 | 1 | **6/6 tests passed** |

Validity: every row had a real workspace, Docker up, provider up, official grader executed (exit 0). No environment/provider/harness-crash invalidity. filter & sparql are **valid capability failures**; openssl is a **valid pass**. **Zero false-cleans across the run** (the primary goal of the enforcement slice).

---

## The headline: enforcement is a GOOD GATE, not yet a RECOVERY ENGINE

> Did the new runtime enforcement create actionable recovery loops, or did it only prevent completion?

**It prevented false completion on all three tasks and created recovery on none.** Verifier stayed `uncertain_missing_evidence` on both fails and returned `completed` only where the grader agreed. But neither failing task recovered:

- **sparql** — the loop was detected *perfectly* (13 no-progress fires with the correct directive) and the solver ignored it every time, because the directive was **advisory** and the **verifier's own feedback actively contradicted it** (asked for *more* display).
- **filter** — no loop at all; genuine diverse effort with real validation scripts, good actionable verifier feedback, but no architect proof scaffold and no convergence within 30 steps.

This is exactly the "dead-end gate vs recovery loop" risk called out before the run. The gate works. The teeth and the recovery path do not exist yet.

---

## Cross-cutting harness findings (these undermine future audits — fix first)

**H1 — Trace writing is broken in the timeout-fix build.** Every row carries `trace_write_error: "failed to write trace file"`; `traces/` is empty. The "trace-proven" pillar produced **no traces** for the canonical run. (The pre-timeout-fix 16:07 run *did* write traces, so this is a regression introduced by the timeout-guard patch.) This audit survived only because `receipt_summary` is embedded in `results.json`.

**H2 — `verifier_evidence/` is a single shared directory across sequential tasks with colliding `step_NNNN` keys.** filter→sparql→openssl each wrote `step_0002…`, `step_0030…` etc. into the same folder, so later tasks **overwrote** earlier ones. On disk: steps 0–2 are openssl's, the no_progress steps are sparql's, filter's no_progress evidence is gone. Per-task verifier evidence is only fully recoverable from `receipt_summary`, not from `verifier_evidence/`. Violates the packet rule "no lane may share an output directory."

**H3 — `verifier_prompt.txt` is 0 bytes on the `deterministic_failure` path** (3607 bytes on the `no_progress` path). Prompt persistence is code-path-dependent. Mitigated only because the prompt is also embedded in `verifier_packet.json` as `architect_verifier_prompt`.

**H4 — The architect proof/evidence contract was populated for ONLY 1 of 3 tasks.** `success_definition`, `evidence_requirements`, `false_positive_risks` are fully populated for **sparql** and **empty** for **filter and openssl** (confirmed at multiple steps, pre- and post-reconfigure; `config_realization.architect_path` is empty for filter). Consequently filter's and openssl's `proof_contract_analysis` returned `status: passed, finding_count: 0` **vacuously** — there were no requirements to enforce. **Proof-contract enforcement was actually exercised on sparql alone.** The replay-acceptance "filter false-clean blocked" result is therefore a property of the *replay fixture*, not of this live run.

> Net: several mechanisms that "look implemented" were inert or invisible in the live run. This is the difference between "harness improved" and "harness looks better."

---

## Task 1 — filter-js-from-html  (valid fail, no false-clean)

**ARCHITECT** — *effectively absent.* `architect_path` empty; `success_definition` empty; `evidence_requirements` `[]`; `false_positive_risks` `[]`; proof contract vacuously passed. Ran on the **default** config (9 stable-core tools, `default_bounded` context). Weakness: no task-specific deliverables, no XSS/clean-preservation proof scaffold.

**COMPILER/RUNTIME** — `config_realization` success=True but realized the default contract. Stable-core tools all present (`run_command`, `write_file`, `read_file`, `query_artifact_history`, etc.). 2 reconfigures, one of which was a `solver_output_parse_failure` (malformed model action, recovered).

**SOLVER** — genuine, diverse effort (165 receipts): 20 `run_command` real `python3` validation scripts each step, wrote `verification_fixture.html`, 114 `check_result` (all executed), used `query_artifact_history`. **No `no_progress` fired** — actions were diverse enough not to trip the repeat detector. It just never packaged the before/after evidence the verifier demanded within 30 steps.

**VERIFIER** — *worked well.* Called 9× (on deterministic-failure events + max_steps). Verdict **every time** = `uncertain_missing_evidence` (never false-cleaned). Feedback was **specific and correct**: *"Rerun /app/filter.py on a real HTML fixture and include the full before and after file contents, plus an explicit in-place change indicator, so the evidence shows dangerous JavaScript-bearing substrings were removed and the remaining safe HTML stayed unchanged."* Note: false-clean prevention here came from the **verifier**, since the proof contract was empty.

**OUTCOME** — grader exit 0, reward 0.0, `model_limit` "genuine progress and diverse actions but no passing check."
**Primary failure class:** architect_config (empty contract) + solver_self_verification (couldn't produce accepted before/after proof in budget). **Not** a verifier failure; **not** a false-clean.

---

## Task 2 — sparql-university  (valid fail, no false-clean, the key story)

**ARCHITECT** — *good content, wrong evidence model.* Full contract: precise `success_definition` (three professor filters, 2025-08-16 reference date, exact `GROUP_CONCAT(DISTINCT ?country; separator=", ") AS ?countries` projection); concrete `evidence_requirements` (5); excellent `false_positive_risks` (4: temporal logic missed, not-all-three-conditions, wrong enrollment scope, incomplete EU set). **Gap:** evidence requirements are *text-inspection* based ("a final reread showing…"), they do **not** mandate executing the query against the graph.

**COMPILER/RUNTIME** — `proof_contract_analysis` populated and **correct**: `declared_query_terms_absent_from_graph` (invented predicates `uni:Professor`, `uni:academicRank`, `uni:hasStudentEnrollment`, `uni:worksInDepartment`, …), `next_action: "Repair the query using predicates/classes observed in the Turtle graph, then execute it."`, severity **blocking**. **But** it only ever appeared as *packet data* — no `proof_contract` receipt and no completion block fired, because the solver never attempted `task_done`. Proof contract gates *completion*; it never drove *mid-run* behavior.

**SOLVER** — the loop the enforcement is meant to break (48 receipts): 14 `run_command` = `sed`/`tail`/`nl`/`grep` on the same `solution.sparql`, 4 `read_file`, 2 `write_file`, 4 `automatic_memory` (surfaced prior identical reads). **Never executed the query.** Final artifact hedged schema by OR-ing candidate predicates — `(uni:worksInDepartment|uni:worksInDepart)`, `(uni:isDepartmentOf|uni:partOfUniversity|uni:belongsToUniversity|^uni:hasDepartment)` — i.e. guessing because it never grounded predicates against the Turtle graph.

**NO-PROGRESS CONTROLLER** — fired **13×** (steps 14–26), each `repeated_evidence_display_no_state_change` with the correct directive: *"Next action must repair the artifact, run semantic validation, inspect a new target, or declare a concrete blocker."* **Advisory only — the solver ignored it at every step.** No hard/soft block enforced.

**VERIFIER** — *this is the smoking gun.* Called 5×, verdict every time `uncertain_missing_evidence` (never false-cleaned — good). **But its repair instruction was `solution_sparql_truncated_excerpt`: "Provide a full reread of /app/solution.sparql, or a longer excerpt…"** — it asked the solver to **display more**, directly contradicting the no-progress controller's "stop displaying, execute/repair," and it did **not** surface the proof-contract invented-predicate finding as the primary instruction. The verifier reinforced the exact loop the controller was trying to break.

**OUTCOME** — reward 0.0, `model_limit`, step 30. No false-clean, **no recovery**.
**Primary failure class:** memory_repeat_control (advisory, not enforced) + verifier_judgement (display-seeking feedback) + architect_config (evidence model didn't mandate execution). Secondary: solver_execution (ignored directives, never executed the query).

---

## Task 3 — openssl-selfsigned-cert  (valid PASS — the first clean post-upgrade win)

**ARCHITECT** — empty contract (same as filter: empty `success_definition`, 0 `evidence_requirements`, proof vacuously passed). Default config. The task was simple enough that this didn't matter.

**COMPILER/RUNTIME** — default config, `run_command` exposed. 1 reconfigure (`solver_output_parse_failure`, recovered).

**SOLVER** — efficient (19 receipts): step-0 one shell script — `mkdir -p /app/ssl; openssl genrsa …; openssl req -x509 … -days 365`; 13 `check_result`; submitted at step 2.

**VERIFIER** — called 1× on `solver_submit_success_candidate`, verdict **completed**: *"successful end-to-end OpenSSL workflow that created /app/ssl, generated a 2048-bit RSA key at /app/ssl/server.key with chmod 600, issued a self-signed certificate at /app/ssl/server.crt for 365 days…"*

**OUTCOME** — grader **6/6** (`test_directory_structure`, `test_key_file`, `test_certificate_file`, …), reward 1.0. **Verifier `completed` aligned with grader pass. No false-clean.** The prior "openssl verifier permission failure" from earlier audits is **resolved**.
**Class:** valid pass. Preserve this trace.

---

## Answers to the audit's decision questions

- **What did this run prove?** The enforcement layer prevents false completion (0 false-cleans, verifier/grader aligned on all 3). openssl is a real end-to-end capability win. The no-progress detector and the SPARQL proof analyzer both *detect* the right things.
- **What did it NOT prove?** That enforcement produces recovery. It doesn't yet. It also did not prove proof-contract enforcement broadly — that ran on 1/3 tasks (H4). And "trace-proven" is currently false (H1).
- **Did the harness improve or just look better?** Genuinely improved: no false-cleans, openssl win, complete verifier packets. But partly *looks* better: proof contract inert on 2/3, traces missing, verifier evidence overwritten.
- **Did memory prevent loops?** It *detected* them (13 fires + automatic-memory surfacing) but did **not** prevent them — advisory, ignored.
- **Did verifier catch real defects?** Yes on all 3 (never false-cleaned). But on sparql its repair instruction was counterproductive (display-seeking).

## Smallest next fixes (priority order)

1. **Fix the evidence-hygiene bugs first** (H1 trace-write regression, H2 per-task `verifier_evidence` namespacing, H3 verifier_prompt persistence). Without these, no future audit is trustworthy.
2. **Give no-progress teeth (the sparql fix).** After N `repeated_evidence_display_no_state_change`, hard-block the repeated command class and constrain the next action set to {repair, execute/semantic-validation, new target, declare blocked}. Enforced, not advisory.
3. **Resolve the verifier↔controller contradiction.** When a blocking `proof_contract_analysis` finding is present (invented predicates / missing execution) and no-progress is active, the verifier must surface the *proof-contract* repair instruction as primary and must **not** request "more excerpt/display."
4. **Fix architect per-task contract generation (H4).** Determine why filter & openssl got empty contracts while sparql got a full one; make the proof/evidence contract populate for every task, and make the SPARQL-style "execute against the source" requirement a general evidence class (query tasks execute; filter/security tasks require adversarial before/after).
5. **Only then** consider raising `max_steps`. filter showed real progress and may just need more budget — but *not* before no-progress has teeth, or more steps just buys more loop room (per the standing warning).

## Do not start Stage 2

A 1/3 baseline where 2 of the 3 contracts were inert and the enforcement was advisory is not a base to expand from. Next action is a repair slice (fixes 1–4), a replay proving no-progress now hard-blocks the sparql loop and the verifier stops asking for display, then a Stage-1-only rerun. Expanding now would multiply the same failure mode without new information.
