# 11 — Subagent Execution Model

Hierarchy: **Fable decides. Subagents execute. Evidence validates. Fable
revises plan.** Fable should treat itself as Chief Architect, not as the
implementer of every lane. Target executor for the harness itself is
**GPT-5.4 mini**; subagents performing audit/research/synthesis/review work
may use stronger models where it materially improves quality (this
packet's research was done with mixed-capability agents — that pattern is
fine to continue).

For each lane: suitable model tier, input, output, acceptance criteria, how
Fable audits, what NOT to delegate.

---

## Lane 1: Architecture Audit

- **Suitable model**: strong reasoning model (Sonnet).
- **Input**: `03`, `05`, specific kernel/active_evidence_kernel files,
  `runner/agent.py` wiring.
- **Output**: a written verdict on whether `active_evidence_kernel.py` is
  reachable from the default runner, a diff summary between
  `evidence_kernel.py` and `active_evidence_kernel.py`, and a
  recommendation on Option 3/4 (`10`) viability.
- **Acceptance criteria**: must cite exact import chains/line numbers; must
  not assert "wired in" without grep/trace evidence.
- **Fable audits by**: spot-checking 2-3 cited line numbers directly.
- **Do NOT delegate**: the final keep/kill/merge/redesign call (`12`).

## Lane 2: Implementation Patching

- **Suitable model**: GPT-5.4 mini-class (same tier as the target executor —
  good dogfooding) or a coding-focused model.
- **Input**: a single, narrowly-scoped mechanism spec (e.g.
  `filesystem_cwd_path_normalization_wrapper_01` from
  `vm-pulled:tracking/collab/variant_hypothesis_backlog.md`), the relevant
  source files from `05`.
- **Output**: a code diff + new/updated unit tests, run in a worktree.
- **Acceptance criteria**: existing tests still pass; new tests cover the
  mechanism; no hardcoded task-specific names/values (`09` checklist).
- **Fable audits by**: code review against the `09` benchification
  checklist + AGENTS.md review-gate rules
  (`codex_review_skill_plus_adversarial` for runner/sandbox/eval/grader
  code).
- **Do NOT delegate**: scope decisions ("should this also handle X") beyond
  the spec — escalate as a follow-up.

## Lane 3: Regression Test Generation

- **Suitable model**: mid-tier.
- **Input**: a mechanism diff from Lane 2, the three documented regressions
  in `08` (Combined Guard V1.5 sentinel, long-horizon BFCL regression, lean
  probe evidence-hiding).
- **Output**: regression sentinel tests/fixtures that would have caught
  each of the three documented regressions, plus any new regression risk
  specific to the new mechanism.
- **Acceptance criteria**: sentinels are generic (not tuned to pass), run
  fast enough to be part of the standard A/B/A+B testing loop.
- **Fable audits by**: confirming the sentinels actually fail against the
  known-bad historical variants (Combined Guard V1.5 code,
  `076ba7694`) as a sanity check.
- **Do NOT delegate**: deciding whether a regression is acceptable —
  AGENTS.md requires this go to a global sentinel board decision.

## Lane 4: Trace Mining

- **Suitable model**: strong long-context model (large trace volumes).
- **Input**: trace bundles from any new run (Option 1/2/3 reruns), plus
  `research/analysis/bigai_trace_layer/` for comparison.
- **Output**: a Trace Diff Workbench-style divergence report (per AGENTS.md
  §"Certified Trace Diff Workbench") — action/state/verifier diffs, not
  prose.
- **Acceptance criteria**: cites exact trace event indices/paths; classifies
  failures using the AGENTS.md taxonomy (environment/runtime, provider, tool
  contract, path/cwd, schema/parsing, evidence acquisition,
  reduction/selection, verification/grading, model capability, unclear).
- **Fable audits by**: checking 1-2 classifications against raw trace
  excerpts.
- **Do NOT delegate**: turning a trace finding directly into a promoted
  mechanism without going through Lane 2's eval-gated process.

## Lane 5: Run/Eval Execution

- **Suitable model**: orchestration-capable agent with Azure CLI/Docker
  access (this lane is largely mechanical/infrastructure, doesn't need a
  top-tier model for the execution itself, but needs reliable tool use).
- **Input**: a specific run request (e.g. "rerun `winning_harness_v1`
  family-level surface on Azure VM Docker").
- **Output**: result rows, scoreboard, run summary, with explicit
  `admission_level`/`backend_ref` labeling per the 2026-05-18 authority-audit
  standard; VM lifecycle action recorded (deallocated or left running with
  justification).
- **Acceptance criteria**: must not label a run `certified`/`azure_vm_docker`
  unless `docker_preflight.available: true` was actually confirmed for that
  run (this is exactly the mistake the 05-18 audit caught).
- **Fable audits by**: spot-checking the `docker_preflight` field in the
  raw run summary.
- **Do NOT delegate**: interpreting INVALID as FAIL or vice versa —
  surface raw status to Fable.

## Lane 6: Verifier Audit

- **Suitable model**: strong reasoning model.
- **Input**: `terminalbench_verifier_repair` eval (flagged
  non-discriminating, `07`#11), `tool_result_attribution` eval (flagged
  possible leakage, `07`#12).
- **Output**: diagnosis of whether each eval's verifier/fixture is itself
  broken vs. the harness being broken; if eval-broken, a proposed fix to the
  eval (not the harness) that strengthens pressure / fixes isolation,
  written BEFORE any new mechanism targets that family.
- **Acceptance criteria**: must distinguish "eval is too easy" from
  "eval leaks hidden truth" from "harness genuinely passes/fails this
  correctly."
- **Fable audits by**: requiring before/after pass rates on a trivially-bad
  control variant to confirm the eval can discriminate.
- **Do NOT delegate**: don't let this lane's output be used to retroactively
  justify an existing mechanism's score (`09` risk #4/#5).

## Lane 7: Context Pack Maintenance

- **Suitable model**: mid-tier.
- **Input**: this packet, `tracking/ledger/inbox/` (27 unprocessed entries),
  `vm-pulled`-only files.
- **Output**: (a) a ledger-historian pass converting inbox entries into
  canonical `tracking/ledger/{decisions,timeline,claims}.md` updates; (b)
  reconciliation of `vm-pulled`-only files (`variant_hypothesis_backlog.md`,
  `single_family_winner_discovery_gate/`) into `master`.
- **Acceptance criteria**: per AGENTS.md, only the historian writes
  canonical ledger files; this lane should produce the *raw* synthesis the
  historian (or Fable acting as historian) then commits.
- **Fable audits by**: spot-checking that no inbox entry's "failed
  prediction" or "killed hypothesis" was silently dropped (AGENTS.md:
  "preserve negative results").
- **Do NOT delegate**: the decision of what becomes "canonical" — that's
  historian/Fable territory per AGENTS.md.

## Lane 8: Benchmark-Native Runner Analysis

- **Suitable model**: strong reasoning model with sandbox/Docker access.
- **Input**: `runner/benchmark_adapter_terminalbench_native.py`,
  `runner/certified_sandbox*.py`, the 2026-05-18 "not native authority"
  finding.
- **Output**: a concrete "what's missing for true native TB2.0 status"
  report (Option 5, `10`).
- **Acceptance criteria**: must test against `EXPECTED_REMOTE_FRAGMENT`
  provenance check with a real `harbor-framework/terminal-bench` checkout if
  possible.
- **Fable audits by**: confirming the provenance check actually runs (not
  dead code, echoing the Lane-1 "is X actually wired in" pattern that
  recurred in Phase 6).
- **Do NOT delegate**: claiming "native" status without a successful run
  against real TB2.0 task rows.

## Lane 9: Eval Suite Repair

- **Suitable model**: mid-tier.
- **Input**: `tools/run_final_harness_eval_suite_baseline.py` (hardcoded to
  `recipe_control`), `runner/packet04_route_manifest.py`.
- **Output**: route-manifest-aware baseline runner so that any of
  Architectures B/C/D can actually be scored through
  `final_harness_eval_suite` without ad hoc one-off scripts.
- **Acceptance criteria**: `recipe_control` behavior unchanged (regression
  test); new variant routes selectable via config, not code edits.
- **Fable audits by**: running `recipe_control` before/after to confirm no
  behavior change.
- **Do NOT delegate**: this is plumbing, low-risk — good first task for a
  smaller model, but Fable should sequence it early since Options 1-4 all
  depend on it.

## Lane 10: Failure Taxonomy Updates

- **Suitable model**: mid-tier.
- **Input**: new run results from Lanes 4/5, `07`/`08`.
- **Output**: updated classification (open→partial→solved or
  →regressed) with new evidence citations.
- **Acceptance criteria**: never mark "solved" without certified-pass or
  benchmark-pass evidence (per `08`'s tier definitions).
- **Fable audits by**: checking the evidence tier matches the claimed
  status.
- **Do NOT delegate**: nothing special — but this lane should run after
  every Lane-5 eval execution, continuously.

## Lane 11: Source-Code Integration

- **Suitable model**: GPT-5.4 mini-class (dogfooding) or coding model.
- **Input**: approved mechanism diffs from Lane 2 across multiple lanes that
  may touch overlapping files (e.g. both filesystem and service-readiness
  fixes might touch `kernel_state.py`).
- **Output**: merged, conflict-free integration branch.
- **Acceptance criteria**: AGENTS.md's "test A alone, B alone, A+B together"
  — this lane is responsible for producing the "A+B" build.
- **Fable audits by**: requiring the A+B scoreboard before promoting either
  individually-promoted change as "final."
- **Do NOT delegate**: promotion decisions — those go through Lane 10/Fable.

## Lane 12: Run Result Summarization

- **Suitable model**: mid-tier, good at structured summarization.
- **Input**: raw `result_rows.jsonl`/`scoreboard.json` from Lane 5.
- **Output**: compact scoreboard deltas vs. the 2026-05-30 baseline
  (`06`#3), formatted for ledger/inbox per AGENTS.md's `RAW_LEDGER_UPDATE`.
- **Acceptance criteria**: must include failed-prediction reporting (don't
  silently reinterpret).
- **Fable audits by**: spot-checking 1-2 summarized numbers against raw
  files.
- **Do NOT delegate**: nothing special.

---

## General rules across all lanes

- Every lane's output must cite exact paths/commit hashes — no
  unsourced claims (this packet's own standard, propagated forward).
- No lane may unilaterally mark something "promoted"/"certified" — Fable (or
  the historian under Fable's direction) does that, gated on Lane 5's
  evidence and Lane 10's taxonomy update.
- Parallel diagnosis across lanes is encouraged (AGENTS.md); parallel
  *promotion* is not — converge on a shared sentinel board before promoting
  anything (this is the rule Phase 3 violated).
- If a lane reports `blocked`/`partial_complete`/`invalid_due_to_environment`,
  Fable should not let it "wait for approval" (AGENTS.md's no-mid-goal-
  approval-wait rule) — close it honestly and replan.
