# 08 — Solved vs. Open Failure Classes

## Evidence-tier definitions (used throughout)

- **unit-test-pass**: a `pytest` test for a module/function passes in
  isolation.
- **smoke-pass**: a minimal end-to-end run (often `sandbox_type=none` or a
  single task) completes without crashing.
- **live-run-pass**: a real agent run against a custom eval task, on a
  working backend (local or VM Docker), produces a `pass` result row.
- **certified-pass**: a live-run-pass on the **Azure VM Docker** backend (or
  equivalent confirmed-valid certified backend), with correct
  `admission_level`/`backend_ref` labeling per the 2026-05-18 authority-audit
  standard.
- **benchmark-pass**: a certified-pass specifically on real TB2.0 task rows
  via `runner/benchmark_adapter_terminalbench_native.py`.

A class is only marked **solved** here if certified-pass or benchmark-pass
evidence exists. Unit-test-pass alone is explicitly insufficient, per
AGENTS.md ("promotion requires scored eval evidence").

---

## Classification table

| Failure class | Classification | Evidence tier | Notes |
|---|---|---|---|
| Long-horizon artifact handoff | **SOLVED** | certified-pass (6/6, 2026-05-30) | One Goal-1 candidate (`spb_01`/`bounded_episode_01`) regressed BFCL when changed — don't touch without a BFCL sentinel. |
| Filesystem / cwd / path confusion | **OPEN** | certified-fail (0/6, 2026-05-30) | Concrete fix proposed (`filesystem_cwd_path_normalization_wrapper_01`), not implemented. |
| Service readiness / process identity | **OPEN** | certified-fail (0/3, 2026-05-30) | Concrete fix proposed and predicted to go to 3/3 (`service_contract_first_receipt_closure_01`), not implemented. |
| Service readiness hallucination / port-open-but-broken-protocol | **OPEN** (vocabulary exists) | none | `service_not_ready` status exists in `GOVERNED_STATUSES`; mechanism unverified. Subsumed under service-readiness family above. |
| Context / evidence-carry-forward / reduction | **PARTIALLY SOLVED (code), UNVERIFIED (eval)** | unit-test-pass only for the 2026-06-05 fix | 2/7 certified-fail as of 2026-05-30, predates the fix. Rerun needed. |
| Environment / toolchain / dependency confusion | **OPEN** | certified-partial (4/7, 2026-05-30) | `dependency_runner_resolution_contract_01` proposed, not implemented. |
| Tool-contract / schema mismatch — tooling baseline family | **PARTIALLY SOLVED, with caveat** | certified (4/7 → 7/7 with combined guard) | The 7/7 result depends on Combined Guard V1.5, which has a **certified sentinel regression (0/1)** — net result is NOT a clean promotion. Treat as open until re-resolved. |
| Tool-contract / schema mismatch — tool_result_attribution family | **OPEN / possibly REGRESSED** | certified-fail (0/2 across all 4 variants, 0/1 sentinel, 2026-05-18) | May partly be an eval-quality issue (#12 in `07`) — diagnose before more mechanism attempts. |
| Finalization-truth bug / `ungoverned_model_claim` | **PARTIALLY SOLVED (code), UNVERIFIED (eval)** | unit-test-pass + adversarial-review-pass only | Also unclear if reachable from the default `agent.py` runner (imports `evidence_kernel.py`, not `active_evidence_kernel.py`) — verify wiring before claiming any progress. |
| Unsupported finalization / weak compile-only proof / fake artifacts | **UNKNOWN** | none (eval itself flagged non-discriminating) | `terminalbench_verifier_repair` eval passed both routes at 100% (2026-05-18) — likely too weak to detect this class either way. |
| Hidden/eval leakage (tool_result_attribution) | **UNKNOWN** | none | Diagnosis recommended (Goal 1), not done. |
| Repeated inspection/repair loops, step/token efficiency | **UNKNOWN** | none (predictions only, one related lean-run regressed) | No Aether-specific measurement exists. |
| Local Docker unavailability / certified-loop infrastructure | **OPEN** | n/a (infrastructure) | Azure VM Docker confirmed working 2026-05-17; lifecycle scripts referenced by AGENTS.md missing from repo. |
| Architecture churn without scored deltas | **OPEN (process)** | n/a | 4 architecture lines built since Phase 3 with effectively zero comparative scoring between them. |
| Stale ledger / fragmented decision history | **OPEN (process)** | n/a | 27 unprocessed inbox entries; `vm-pulled`/`master` divergence on key files. |
| `winning_harness_v1` overall capability | **UNKNOWN — INVALID, not failed** | invalid (62/62 rows, local Docker unavailable) | Distinct from "failed" — must be rerun on Azure VM Docker before any verdict. |
| Model-led substrate v1 overall capability | **UNKNOWN — never run** | unit-test-pass + adversarial-review-pass only | Newest code, zero eval evidence. |
| MLPCP v2/v3 | **OPEN (paused)** | certified-partial (qemu pass, hard2 fail, 2026-06-11) | `qemu-startup` passed with receipt patch, but hard2 tasks stayed at 0.0 because the model ignored background tools. Progress-escalation patch is unapplied due to missing anchors. |

---

## Regressions to watch (things that were "fixed" but then broke something else)

1. **Combined Guard V1.5**: fixed `clean_tool_contract_semantics` target
   tasks (2/2) but regressed sentinel `ctc_semantics_001_multi_required_order`
   (1/1 → 0/1).
2. **`long_horizon_artifact_handoff` Goal-1 candidates**: passed target+TB
   but regressed BFCL (0/0 detail not given, but explicitly "fail BFCL" —
   treat as a confirmed cross-benchmark regression).
3. **Lean/zero-abstraction probe (2026-05-30)**: improved one path-state row
   but regressed overall by hiding evidence and using brittle anchors.

These three are the project's only documented A/B-with-sentinel comparisons
that produced a *negative* delta on something — i.e., the only real evidence
the project has about what NOT to do. Any new mechanism touching tool
contracts, long-horizon handoff, or context/evidence visibility should be
checked against these three regressions specifically.

---

## What this means for "true 100%"

Of TB2.0's failure surface, only **one family (long-horizon artifact
handoff) has certified-pass evidence**, and even that has a
regression-prone edge (BFCL). **Two families (filesystem, service
readiness) are at 0% with concrete unimplemented fixes.** **Everything else
is either partial, unverified-since-fix, unknown, or invalid.** "True 100%"
requires, at minimum: closing filesystem and service-readiness from 0%,
re-verifying context after the compaction fix, resolving the tool-contract
sentinel regression, and — critically — establishing a certified eval loop
that can actually produce benchmark-pass evidence repeatedly (item 9 in
`07`), since without that, "100%" cannot even be measured, let alone
achieved.
