# Aether — Current Winning Harness Line

`harness/aether2` is the current winning harness line. It supersedes the kernel
line (documented in `../harness/`) and the MLPCP v3 line
(documented in `../harness/mlpcp_v3/`).

## What Aether-2 is

Aether-2 is a complete reimplementation of the agent harness with:
- `harness/aether2/control/loop.py` (2634 lines) — the main agent control loop
- `harness/aether2/traces/delta.py` (2099 lines) — delta/trace capture
- `harness/aether2/runtime/` — model client, session management, TPM pacer,
  action bus, metrics, compactor, and verification
- `harness/aether2/tools/` — native tools, MCP tools, permissions
- `harness/aether2/skills/` — skill loader, registry, invocation
- `harness/aether2/hooks/` — lifecycle hooks and builtins

Total: 16,603 lines across the package (as of 2026-06-16).

The code lives at `harness/aether2/`. This `variants/aether/` directory is a
pointer and evidence summary only — the code is not copied here.

## Hypothesis backlog (H1–H8)

The `../harness/variant_hypothesis_backlog.md` contains the active H1–H8
backlog from the G5 run analysis (2026-06-13/14):

- **H1** (eval-substrate launch integrity) — EVIDENCE-BACKED / ACTIONABLE
- **H2** (false-positive task_done reducer) — UNVALIDATED / GATED
- **H3** (step/effort-budget tuning) — UNVALIDATED / GATED
- **H4** (advisory-verifier reliability) — UNVALIDATED / GATED (diagnostic first)
- **H5** (grader/test-harness robustness) — UNVALIDATED / GATED (diagnostic first)
- **H6** (activity/evidence separation) — EVIDENCE-BACKED / ACTIONABLE AFTER EVAL BASELINE
- **H7** (evidence-strength-aware verifier) — EVIDENCE-BACKED / ACTIONABLE AFTER EVAL BASELINE
- **H8** (EnvContract v2 + attributable monitoring) — EVIDENCE-BACKED / ACTIONABLE AFTER EVAL BASELINE

## G5 run evidence

The G5 run (`full_twice_20260612T200830Z`) produced 24/241 authoritative A1 rows,
0/241 A2 rows, and 457/482 attempts as invalid launches (mass `ModuleNotFoundError`
after a reboot autorestart). H1 directly addresses this launch-integrity failure.

The 5 known task passes from the valid rows:
- acl-permissions-inheritance
- analyze-access-logs
- assign-seats
- attention-mil
- build-pmars

## Status

Aether-2 is implementation-complete. No benchmark promotion has been claimed.
The launch-integrity failure (H1) must be resolved before the next full eval run.

## References

- `../harness/variant_hypothesis_backlog.md` — H1–H8 backlog
- `../harness/decision_history.md` — Phase 0–7 history including how Aether-2 emerged
- `../scoreboards/aether2_g5_harness_upgrade_v1.yaml` — G5 snapshot summary
- `../shared/lineage_map.md` — lineage from evidence kernel → aether2
