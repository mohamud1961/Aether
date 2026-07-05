# Plan — Semantic Proof Contract + Finding Resolution Slice

Status: proposed (not started). Author: Claude (Opus 4.8), 2026-07-01.
Predecessors: STAGE1_TERMINAL_RUN_FULL_AUDIT.md, the repair-slice ledger entries,
and the terminal repair-slice rerun (run id `20260701T_runtime_enforcement_repair_slice_rerun`).

## Why this slice

The prior repair slice moved the harness from "mechanisms missing/invisible/inert"
to "mechanisms exist but their judgement logic is brittle." The terminal rerun
proved the six evidence-hygiene/enforcement fixes work on VM evidence, but exposed
three logic problems (one already fixed, two open):

1. **(fixed)** Trace-capture ordering dropped submit-branch verifier receipts — patched
   in kernel.py; a task calling the verifier 7 times now shows all 7 in the trace.
2. **(open) Proof-contract brittleness.** `proof_contract.py` fires the adversarial-
   sample gate only on hardcoded phrases (`"one trivial input"`, `"single sample"`).
   The rerun's filter architect wrote a *better*, more specific false-positive risk
   that lacked those phrases, so the gate silently never engaged and the run
   false-cleaned (kernel status=completed, reward=0.0, grader failed both tests).
3. **(open) Active-finding never resolves + grader/status mismatch.** Confirmed root
   cause in `verifier.py` `ActiveFindingStore.apply_result`: a finding clears ONLY on
   a literal `completed` verdict, or when superseded by a same-verdict/same-`applies_to`
   finding. There is no evidence-based resolution. OpenSSL's step-2 `uncertain` finding
   therefore blocked the completion gate for all 30 steps even though the solver
   re-ran `stat`/`openssl x509` exactly as asked and the official grader passed 6/6.
   The row came out `reward=1.0` but `incomplete/model_limit` — nonsense audit semantics.

Decision: fix the logic first, replay-prove locally, THEN spend one Stage 1 VM rerun.
Do NOT rerun first. Do NOT start Stage 2.

## Invariant-core guardrails (must hold throughout)

- The **completion gate stays grader-blind.** The official grader runs only AFTER
  `kernel.run()` returns (docker_runner post-loop). No grader/benchmark state may
  enter the solve loop. All grader reconciliation happens in the post-run record/
  classifier layer, never in `CompletionGate` or the verifier packet.
- **Finding resolution is evidence-based, never claim-based** (No Fake Work). A finding
  clears because the runtime can point to the requested artifact/check/probe evidence,
  not because the solver asserted completion.
- **No task-name hardcoding.** Task-family analyzers key on structured surface signals
  (success criteria shape, evidence requirements, artifact types), not benchmark names.

## Approved additions (2026-07-01, post-review)

- **No vacuous proof-contract pass.** If `success_definition`, `evidence_requirements`,
  and `false_positive_risks` are all empty (no real architect contract to check
  against), `proof_contract_analysis.status` must be `contract_missing`, never
  `passed`. A pass must mean "checked and clean," not "nothing to check."
- **Three separate status fields on every result row**, not one conflated status:
  `official_grader_status` (from the grader, authoritative), `internal_completion_status`
  (what the kernel/gate concluded), `verifier_alignment_status` (did the verifier's
  verdict agree with the grader — `aligned` / `verifier_completion_miss` /
  `verifier_false_clean` / `not_applicable`). A grader pass with an internal miss must
  read as `official_grader_status=pass, internal_completion_status=incomplete,
  verifier_alignment_status=verifier_completion_miss` — never collapsed into one
  confusing label.
- **Explainable findings, not just block/no-block**, for every task-family analyzer in
  A1: each finding carries `summary` (what's wrong), `evidence` (what was observed),
  and `next_action` (concrete repair instruction) — matching the pattern the SPARQL
  analyzer already uses. The new filter/security and openssl analyzers must follow the
  same shape so the solver gets a repair instruction, not just a failure label.

## Decisions taken (previously open questions)

- **Finding resolution = hybrid by type.** Auto-resolve only findings the runtime can
  independently verify (file-exists, permission bits, syntax/parse). Downgrade + force
  re-verification (verifier still decides) for semantic findings (does the query mean
  the right thing, does the sanitizer actually preserve clean HTML). The runtime never
  auto-resolves a judgment it cannot ground itself.
- **Scope = Slice A now; Slice B (verifier probes) deferred** to a scoped follow-on
  after Slice A is replay-proven and rerun-verified.

---

## Slice A — steps, files, acceptance

### A1. Structural/semantic proof-contract obligations
File: `aether_next/proof_contract.py`
- Remove the exact-phrase trigger in `_adversarial_sample_findings`. Replace with a
  structural signal: when the compiled success-definition / evidence-requirements /
  false-positive-risks are security/sanitization/XSS/clean-preservation SHAPED (a small
  semantic signal set, e.g. co-occurrence of {html, javascript|xss|sanitize|script|
  event handler|clean} with a preservation or adversarial notion), the completion
  obligation requires: adversarial-fixture coverage + clean-preservation evidence +
  before/after file evidence. Wording-independent.
- Add task-family analyzers keyed on structured fields, each defining evidence
  obligations (extend the existing SPARQL analyzer; add security/html-filter and
  cert/openssl):
  - security/html-filter: dangerous-input-before + sanitized-after + benign-HTML-
    preserved + >1 attack class + in-place demonstrated + no reserialization drift.
  - query/sparql (mostly exists): query executes against the actual graph where
    possible; every predicate/class grounded or justified; projection matches; output
    shape checked.
  - cert/openssl: required files exist; key perms checked; cert subject/validity
    checked; a checker/grader-like validation run where available.
- Acceptance: the rerun's actual filter contract (its real, better-worded false-positive
  risks) now triggers the gate; a single solver-authored fixture no longer satisfies
  completion. Add a unit test with the rerun's real risk text as the fixture input.

### A2. Evidence-based active-finding resolution (hybrid by type)
File: `aether_next/verifier.py` (`ActiveFindingStore`), with the signal already in
`verifier_packets.py` (`changes_since_active_findings`).
- Add a runtime resolution path invoked each step (or at gate evaluation):
  - For deterministically-checkable findings: if the finding's `applies_to` artifacts
    now show the requested evidence via passing checks/receipts created AFTER the
    finding's `created_step`, archive it status=`resolved_by_evidence`.
  - For semantic findings: do not auto-resolve; instead downgrade priority and mark it
    "re-verify pending", and ensure the next verifier call receives the changed-since-
    finding evidence prominently so it can clear or re-assert. Never let a semantic
    finding block indefinitely with no re-evaluation.
- Guard: only evidence created after `created_step` counts; solver text claims do not.
- Acceptance: replay of the openssl trace shows the step-2 finding clears (or downgrades
  and is re-verified) once the stat/openssl evidence lands, instead of persisting to
  step 30.

### A3. Grader reconciliation at the record layer (invariant-safe)
Files: `aether_next/runners/docker_runner.py` (record builder), `aether_next/classifier.py`.
- Post-run only: when `reward == 1.0` (official grader pass), the row status is a pass
  and the classifier label is `none`/pass; the internal verifier's failure to recognize
  completion is recorded as a distinct signal, e.g. `verifier_completion_miss`, not
  `model_limit`/`incomplete`.
- Explicitly untouched: `CompletionGate`, verifier packet, solve loop (all stay
  grader-blind).
- Acceptance: no row can be `reward=1.0` AND `incomplete`/`model_limit`. Add a unit test
  that feeds a KernelResult(incomplete) + reward=1.0 through the record builder and
  asserts the reconciled status/label.

### A4. Replay + regression tests (gate before any VM spend)
Files: extend `run_stage1_replay_acceptance.py`; unit tests in `tests/`.
- filter: a solver-authored single-fixture "proof" no longer completes; adversarial +
  clean-preservation evidence is required.
- openssl: replayed evidence clears/downgrades the active finding; a reward=1.0 row
  cannot be classified incomplete.
- (keep green, already landed) sparql no-progress hard-block after one write; trace
  captures all verifier receipts.
- Acceptance: `run_stage1_replay_acceptance.py` overall_passed=True with the new cases.

### A5. Gates + one rerun
- Local: `python3 -m compileall aether_next` + `pytest -q --ignore=tests/test_docker_runner.py`.
- Sync to VM; VM preflight: same compile + pytest.
- Then exactly ONE Stage 1 rerun (3 tasks), fresh canonical run id, monitored by direct
  SSH polling on a scheduled cadence (not an open-ended Haiku elapsed-time loop — that
  hallucinated elapsed time last run). Audit the 3 terminal rows against the acceptance
  criteria above.

---

## Slice B — Bounded read-only verifier probes (deferred, scoped here for later)

Target architecture (three layers): solver tools / read-only verifier probes / external
grader. Give the verifier a NARROW, policy-gated surface, executed by the runtime and
recorded as receipts — never a raw shell, never mutation:
- `read_artifact(path)`, `inspect_diff(path)`, `inspect_check_result(check_id)`,
  `inspect_artifact_history(path)` (read-only).
- `request_validation_probe{kind, command?, timeout, read_only:true, allow_mutation:false,
  allowed_paths: workspace only, reason: required}` — e.g. execute the candidate SPARQL
  against the Turtle graph; run filter.py on a verifier-owned temp fixture; run
  `openssl x509 -noout -subject -dates`.
- Runtime validates every probe against an allowlist/timeout/read-only policy and writes
  a receipt; the verifier consumes results, never executes directly.

Why deferred: this wires an executor handle + probe policy into the verifier lane =
new invariant-core surface (executor boundaries, path safety, No Fake Work). It gets its
own slice and its own adversarial faithfulness review, not a bolt-on to Slice A.

Directly strengthens: SPARQL (verifier requests real query execution instead of asking
for "a longer excerpt"), filter (verifier runs its own adversarial fixture instead of
trusting the solver's), openssl (verifier confirms perms/subject/validity itself).

---

## Sequencing

1. Slice A (A1 → A5), replay-green, one Stage 1 rerun, audit rows.
2. Report; decide whether Slice B or Stage 2 is next.
3. Slice B as a scoped follow-on if approved.

Do NOT start Stage 2. Do NOT rerun before A4 replay is green.
