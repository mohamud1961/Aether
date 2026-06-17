# Next Goal — ready-to-use prompt

This authorizes a **bounded environment/runtime repair + re-baseline diagnostic** (the one lane
with decisive evidence, L1). It is **not** a capability-mechanism implementation prompt: no proper
capability eval exists yet, so capability lanes (L2–L5) stay gated behind a valid baseline. Per
AGENTS.md, environment/runtime repair is explicitly allowed without a prior proper eval.

---

```
GOAL: aether2_g5_lane1_launch_integrity_rebaseline

OBJECTIVE
Restore measurement validity to the Aether-2 full TerminalBench tournament by (1) fixing the
launch/import defect that invalidated 457/482 attempts in the frozen
full_twice_20260612T200830Z run, (2) making the eval harness fail loud-and-early instead of
silently recording launch crashes as task failures, and (3) producing a VALID n=2 baseline whose
authoritative grader rows cover ≥95% of tasks. Do not open capability mechanisms in this Goal.

REVIEW GATE: codex_review_skill_plus_adversarial
(runner/eval-substrate + result-row + contamination integrity is measurement-critical)

ENTRY CRITERIA
- Frozen analysis accepted: tracking/collab/aether2_g5_run_analysis_20260613/
  (root cause F1: ModuleNotFoundError 'runner' at run_aether2_g3_official.py:30 after the ~12:05
  reboot autorestart relaunched without repo root on sys.path; 24/241 A1 rows, 0 A2 rows).
- Azure VM Docker backend reachable (G3/G4 conditions) OR Mac-side execution path recorded.

SCOPE
- Edit tools/run_aether2_g3_official.py to self-bootstrap sys.path (insert repo root =
  Path(__file__).resolve().parents[1]) BEFORE importing runner.aether2.* ; verify import works
  when launched as `python3 tools/run_aether2_g3_official.py` from any cwd and with no PYTHONPATH.
- Harden the run orchestrator (resume_full_twice.sh / autorestart unit): export PYTHONPATH; abort
  the whole tournament on a fatal launch fault (e.g., N consecutive instant rc≠0 with elapsed ≤2s)
  instead of marching through tasks; emit an explicit invalid_launch / invalid_environment row for
  any task that never reaches the grader (no silent rc=1).
- A-only / B-only / A+B interaction test (runner self-bootstrap vs launcher PYTHONPATH/fail-fast).
- (Secondary) Docker image prune + disk guard between tasks (latent risk; 80% disk at freeze).
- Re-run: first the 25 already-executed A1 tasks (ceiling/regression check), then a full n=2.

OUT OF SCOPE (do NOT do in this Goal)
- runner/aether2/*.py behavior changes (must still pass tools/aether2_genericity_check.py).
- Any model-facing/capability mechanism (false-positive task_done reducer, advisory-verifier
  changes, step-budget tuning, prompt edits) — gated behind a valid baseline + proper eval.
- Reinterpreting the frozen run's outcomes; the frozen bundle stays immutable.

KNOWN-BAD REPRODUCTION (must pass before/after)
- Before fix: launching run_aether2_g3_official.py with repo root NOT on sys.path reproduces
  `ModuleNotFoundError: No module named 'runner'`. After fix: clean import from any cwd / no PYTHONPATH.

BASELINE (authoritative, from frozen analysis)
- A1 valid-scored pass rate 5/19 = 26.3%; reach-grader rate 24/241 = 10%; invalid launches 457/482.
- 5 known passes: acl-permissions-inheritance, analyze-access-logs, assign-seats, attention-mil,
  build-pmars.

EXIT CRITERIA
- Known-bad reproduction fixed (import clean from any cwd, no PYTHONPATH).
- Re-baseline reach-grader rate ≥95% per attempt; invalid-launch rate ~0%.
- The 5 known passes still pass (ceiling/regression); zero new launch-crash rows.
- Attempt 1 and Attempt 2 scored separately; invalid/launch attempts excluded from pass-rate
  denominators and emitted as explicit invalid rows.
- A valid n=2 scoreboard + result rows produced, with predictions 1–4 (qemu-startup,
  extract-moves-from-video, install-windows-3.11, video-processing) now resolvable.

REGRESSION SENTINELS
- 5 known passes; spec §14 G5 sentinels: qemu-startup green-check, BFCL/tool-call adapter,
  tools/aether2_genericity_check.py green, non-TB generalization board.

STOP / KILL CRITERIA
- Import fix does not eliminate the F1 signature → stop, escalate.
- Any of the 5 known passes regresses → stop, bisect.
- Reach-grader stays <95% for a non-F1 reason → close as partial; open a narrower diagnostic for
  that new failure class (do NOT widen into capability work).

EVIDENCE OUTPUTS
- Diff of the launch-integrity fix + A/B/A+B interaction table (reach-grader rate per variant).
- New valid n=2 result rows + scoreboard; reach-grader and invalid-launch metrics; separated
  A1/A2 tables; prediction-audit refresh for 1–4.
- RAW_LEDGER_UPDATE.

ESCAPE HATCH
- If the VM/Docker backend is unreachable, close as invalid_due_to_environment with the exact
  control-plane limitation and the Mac-side command to run; do not poll.

FOLLOW-ON (not this Goal)
- Only after a valid baseline exists: open capability lanes L2 (false-positive task_done), L3
  (advisory-verifier reliability), L4 (step budget), L5 (grader robustness) — each WITH a proper
  homolog eval, baseline, ceiling, predicted delta, and the sentinels above, per the eval-first reset.
```
