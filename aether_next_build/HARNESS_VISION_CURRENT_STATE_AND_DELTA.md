# Current-State Map & Delta Plan — Aether-Next vs the Harness Vision

Measures the active harness (`aether_next_build/aether_next/`) against
[`docs/HARNESS_VISION.md`](../docs/HARNESS_VISION.md). This is the required
"map before build" artifact. **It proposes; it builds nothing.** No code in this
plan is implemented without explicit approval of the specific delta step.

Author: Claude (Sonnet 5), 2026-07-02. Grounded in the code as read this session.

## The vision, one line

Architect designs the workbench → solver works → verifier independently verifies
the task **state** with read-only tools → official grader is external, post-run,
never in the loop. The better the model, the better the system.

---

## What already MATCHES the vision

| Element | Where | Status |
|---|---|---|
| Solver is a simple execution agent, no grader access | `kernel.py` act loop: sees `context_packet`, returns `SolverTurn`; grep confirms zero `grader` references in `kernel.py` / solver message path | **Matches.** |
| Architect authors the solver AND verifier system prompts | `workbench_hooks.py` `WORKBENCH_ARCHITECT_SYSTEM_PROMPT` emits `solver_system_prompt` + `verifier_system_prompt` | **Matches.** |
| Official grader is external, post-run only, never in the loop | grader subprocess runs in `docker_runner.py` only *after* `kernel.run()` returns; `reconcile_grader_alignment` (A3) is post-run record-layer only; `completion.py` / `kernel_verifier.py` have zero grader references | **Matches** (audited clean this session). |
| Config failures surfaced, not silently defaulted | `kernel_config.py` now emits `workbench_architect_configure_failed` into `fallback_codes` (H4 fix), firing the `config_fallback` receipt instead of running silently on an empty contract | **Matches** (as of this session). |
| Reusable generic mechanism (no-progress, budgets, receipts, memory) | `no_progress.py`, `ledger.py`, `verifier_packets.py` | **Matches** — and reusable for the verifier loop below. |

## What VIOLATES the vision

| Violation | Where | Why it violates |
|---|---|---|
| **Verifier is a single-shot packet judge, not an independent state inspector** | `model_hooks.py` `verify(packet, compiled, ledger)` — no executor, no tools; returns a verdict from one LLM call | The verifier judges the solver's *story*, not the task *state*. It cannot inspect the workspace or run a check itself. This is the root of the filter false-clean and the openssl 7×`uncertain`. |
| **Verifier packet is stuffed with the solver's story** | `verifier_packets.py` `build_verifier_packet`: `recent_actions`, `recent_receipts`, `latest_file_reads`, `artifact_evidence`, `changes_since_active_findings`, `memory_events`, `observations` | Makes the solver's narrative the verifier's primary input. Vision wants a clean context: task + architect verifier prompt + current workspace state. |
| **Task-specific judgment logic in the harness** | `proof_contract.py`: `_semantic_query_findings` (sparql), `_filter_security_findings`, `_openssl_cert_findings` | Harness-as-crutch. A verifier that inspects state and runs its own checks makes these redundant. Fails the one test: a better model routed through a read-only probe verifier would not need them. |
| **"Done" is a tangled multi-decider gate, not the verifier's call** | `completion.py` `CompletionGate` blocks on `proof_contract` + `check_result` + active findings + `no_progress`; `kernel.py` auto-submit/`cheap_checks_all_passed` dance | Who decides "done" is split between a deterministic gate and the model verifier, wired together with special cases (e.g. the act-turn verifier-starvation deadlock found this session). Vision: verifier decides done against the architect contract, plus a thin *generic* floor only. |
| **Substrate not fully robust** | `real_executor.py` `write_file` (partial fix landed); `docker_runner.py` teardown `shutil.rmtree(ignore_errors=True)` | openssl `PermissionError` on `check_cert.py` still recurs flakily even with the write-path fix; 24 leftover root-owned `/tmp/tbench_openssl*` dirs teardown can't remove. The substrate is supposed to never fail. |

## What is MISSING

- A **read-only executor handle + probe toolset** in the verifier lane
  (`read_artifact`, `inspect_diff`, `run read-only command`, `inspect_check_result`).
- The verifier as a **bounded read-only loop** (probe → observe → judge) with its
  own step/time budget and no-progress discipline (reuse existing machinery).
- A **clean verifier context** (task + architect verifier prompt + workspace
  tree); solver history demoted to a rare, explicit fallback.
- A thin **generic completion floor** (architect's declared deliverables exist /
  are non-empty) to replace the task-family proof logic.
- **Substrate robustness closure**: pinpoint + fix the residual `check_cert.py`
  write/read path; teardown that can actually remove root-owned files.

---

## Delta plan — smallest reversible steps, each gated on approval

Nothing below is built without explicit approval of that specific step. Steps are
ordered smallest/safest first; each is independently valuable and reversible.

**D0 — Diagnostic (not a build): pinpoint the residual substrate failure.**
`run_tbench_task` swallows the exception into a one-line message, so the residual
openssl `PermissionError` path is unknown. Add traceback capture to the error
record (or a one-off reproduction) so the exact failing host-side path is known.
Prerequisite for "substrate never fails." *Removal/robustness, not new mechanism.*

**D1 — Slim the verifier packet (removal).** Drop the solver-story fields
(`recent_actions`, `recent_receipts`, `changes_since_active_findings`,
`memory_events`, `observations`) from the default verifier packet, leaving task
prompt + architect verifier prompt + current workspace/artifact presence. Cheap,
reversible, immediately reduces "judge the story" pressure. No new capability.

**D2 — Give the verifier read-only inspection (smallest capability add).** Wire a
read-only executor handle into the verifier lane and a small, declared,
runtime-executed probe set (read a file, run one allowlisted read-only command),
every probe recorded as a receipt. Single-round first (architect declares the
probes; runtime runs them; verifier judges the results). No mutation, no raw
shell, strict path/timeout policy. This is the core of the vision.

**D3 — Verifier as a bounded read-only loop (only if D2 proves insufficient).**
Let the verifier request probes iteratively (probe → observe → probe) under its
own budget + no-progress discipline, reusing the existing controllers. Escalate
to this only if single-round probing can't verify real tasks.

**D4 — Shrink `proof_contract` to a generic floor.** Once the probing verifier
can confirm evidence itself, delete the task-family analyzers
(`_filter_security_findings`, `_openssl_cert_findings`, sparql specifics) and keep
only a generic invariant: the architect's declared deliverables exist / are
non-empty. Pure removal + generalization.

**D5 — Collapse the completion gate.** "Done" = verifier says done AND the generic
floor holds. Remove the auto-submit / `cheap_checks_all_passed` / multi-blocker
dance. The deterministic gate stops being a co-decider; it becomes only the thin
anti-hallucination floor.

## Open questions for approval before D2+

1. **Verifier shape:** full read-only *agent loop* (D3, more capable, more
   expensive) vs *fixed declared probes run once* (D2 only, simpler/cheaper)?
2. **Floor thinness:** how minimal is the generic deterministic floor you want
   kept as the anti-hallucination backstop (declared-deliverables-exist only, or
   slightly more)?
3. **Sequencing vs Slice A closeout:** D0 (substrate diagnostic) overlaps with the
   still-unverified openssl path from Slice A. Fold D0 into closing Slice A, or
   start it fresh here?

Do not begin D1+ without answers to these and explicit approval of the step.
