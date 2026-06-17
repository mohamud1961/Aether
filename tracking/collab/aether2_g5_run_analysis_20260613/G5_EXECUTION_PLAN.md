# Aether-2 G5 Execution Plan — Eval-Substrate Repair → Capability Lanes

**Status:** ACTIVE · **Created:** 2026-06-13 · **Owner:** orchestrator
**Review gate:** `codex_review_skill_plus_adversarial` (measurement-critical: runner / verifier / result-rows / contamination)

## Governing evidence (read before acting)
- `tracking/collab/aether2_g5_run_analysis_20260613/` — full run-analysis (README, evidence_inventory, outcome_scoreboard, failure_taxonomy, task_findings, prediction_audit, g5_lane_recommendation, next_goal_prompt, normalized_attempt_rows.jsonl).
- Two external peer reviews (GPT-5.5): `aether2_g5_failure_analysis_report.md`, `aether2_agent_trajectory_analysis_report.md` (in user Downloads). **Three independent analyses converge** on the diagnosis below.

## Convergent diagnosis (what the data actually says)
1. **The frozen run is a run-validity failure, not a capability result.** 457/482 attempts crashed at `ModuleNotFoundError: No module named 'runner'` before any task work (216 Attempt-1 tail + all 241 Attempt-2), triggered by a ~12:05 UTC VM reboot → autorestart relaunched without the repo root on `sys.path`. Authoritative grader rows exist for only **24/241 Attempt-1** tasks; **0/241 Attempt-2** (contaminated). Confirmed root cause: `tools/run_aether2_g3_official.py` imports `runner.aether2.*` at module top with **no `sys.path` bootstrap** — whereas `tools/run_aether2_g2.py:34-35` and the other eval entrypoints **do** have it. Single-file regression.
2. **Authoritative valid-window result: 5 passes** (acl-permissions-inheritance, analyze-access-logs, assign-seats, attention-mil, build-pmars). Honest valid-scored rate **5/19 ≈ 26%** (after removing break-filter as a harness/mount bug → ~5/18); naïve 5/241 = 2.07% is misleading. True 241-task rate = INSUFFICIENT_EVIDENCE.
3. **Deeper harness bottleneck beyond launch:** the loop records observations but does not turn them into durable, requirement-level proof/issue state. Symptoms: self-confirming `task_done` checks (advisory verifier false-clean ~69–74%; `unverifiable` is non-blocking by design), and **dead anti-loop detection** (mirror fired 0×, blind-retry 1× across 21 trajectories) that misses *varied* flailing (broken-python ran `ensurepip` 21×; adaptive-rejection re-ran its R script 10×).
4. **Budget/context are NOT the bottleneck:** STEP_CAP=120 but longest run was 40 steps; compaction never fired. Failures are voluntary stops with weak evidence, not budget exhaustion.

## CORPUS CORRECTION (must propagate everywhere)
The 241-task run used **`terminal-bench-core==head` / VM `original-tasks` (241; registry HEAD shows ~247)** — **NOT** the official **TB 2.0 (89-task)** frozen set. Do **not** report any number here as a "TB 2.0 score." Before any "official" checkpoint, **confirm the exact frozen TB 2.0 89-task selector/list** and run *that*. Label runs precisely: `core-HEAD stress corpus` vs `TB 2.0 official`.

## Hard constraints (apply to every phase)
- **Genericity gate:** no change to `runner/aether2/*.py` may add hardcoded task names, benchmark vocabulary, or task-conditional affordances; `tools/aether2_genericity_check.py` must stay green.
- **Banned mechanisms:** no phase gates, doctrines-as-control, action-rewriting, **completion vetoes**, or harness-side planning. All new verification/recovery features are **reflections/instrumentation** (the model pilots; the verifier reflects; the grader decides). Bounded rounds only.
- **Eval-first:** every capability lane needs a target eval/diagnostic, baseline, known-bad case, ceiling check, predicted delta, named sentinels, and A-only/B-only/A+B interaction before promotion.
- **Attempt separation & honest rows:** Attempt 1 and Attempt 2 scored separately; any attempt that does not reach the grader is emitted as an explicit `invalid_launch`/`invalid_environment` row and **excluded from pass-rate denominators** — never silently counted as a capability fail.
- **Run cadence (no blind full reruns):** `micro-smoke (3) → targeted (10–15) → official checkpoint (89, TB2.0) → optional stress (241/247 core-HEAD)`. Full reruns are measurement checkpoints, not per-patch validation.

## Standing sentinels (every promotion must hold these)
- **5 known passes** must still pass: acl-permissions-inheritance, analyze-access-logs, assign-seats, attention-mil, build-pmars.
- Spec §14 G5 sentinels: `qemu-startup` green-check, BFCL/tool-call adapter, `tools/aether2_genericity_check.py` green, non-TB generalization board.
- **Reach-grader rate** (fraction of attempts that produce an authoritative row): baseline 24/241 ≈ 10% → target ≥ 95%.

---

## Phases

### L1 — Launch integrity + valid re-baseline  ·  **BLOCKING / FIRST**  ·  owner: Phase-1 agent
Restore measurement validity. Files: `tools/run_aether2_g3_official.py` (VM), launcher/autorestart, `tests/`. **No `runner/aether2/` behavior change.**
- **L1-A (import hygiene):** add the `run_aether2_g2.py:34-35` `sys.path` bootstrap to `run_aether2_g3_official.py` (insert `repo_root = Path(__file__).resolve().parents[1]` before the `from runner.aether2...` imports). Add a **generic regression sentinel** that subprocess-launches every `tools/run_aether2_*.py` from a foreign cwd with `PYTHONPATH` stripped and asserts no `ModuleNotFoundError: No module named 'runner'`.
- **L1-B (launcher hardening):** new `scripts/run_aether2_tournament.sh` (or hardened resume script): export `PYTHONPATH=<repo root>`; **preflight import check** before the loop; **fail-fast** if N consecutive launches return rc≠0 with elapsed ≤2s (abort, don't march through the corpus); emit explicit `invalid_launch` rows instead of silent `rc=1`.
- **L1-C (P4 measurement fidelity — folded in):** mirror official test mount layout (provide tests at both the official `/tests` path and the runner path); make the grader **hermetic** (bring its own pytest/uv toolchain so a deliberately-broken agent env can't 127 the grade); classify `verifier_exit_code==127` and `docker rc137` and provider-400 as `invalid_run`/`invalid_environment`, not capability fails; **row journaling** on timeout/kill (write a phase row so killed tasks like `build-initramfs-qemu` leave evidence).
- **Known-bad:** launching the entrypoint from `/tmp` with empty `PYTHONPATH` reproduces the F1 crash before the fix and imports cleanly after.
- **Exit:** entrypoint-hygiene sentinel green locally; genericity green; reach-grader ≥95% on the targeted set (VM); 5 known passes still pass; every attempted task produces a truthful row.
- **Stop/kill:** if import fix doesn't kill the F1 signature, or any known pass regresses → stop, escalate.
- **Score impact:** makes the score *real* (reach-grader 10%→≥95%); L1-C likely flips break-filter and clarifies broken-python/networking (**+1 to +2**).

### L2 — Verification-reflection lane  ·  owner: Lane-V  ·  *first capability lane, after L1*
Target the false-clean/self-confirming finalization (advisory verifier false-clean ~69–74%).
- **P1:** re-run the model's *own* declared `task_done.checks` in a **hermetic fresh shell** (no model-set env vars / no `sys.path` hacks); feed back real exit codes. (Catches amuse path-hack, build-stp `stp -h`.)
- **P2:** classify check **strength** generically (existence/echo/`cat`/`-h`/`test -f` = weak; executes-produced-artifact / fresh-client / hash-or-diff-vs-independent-recompute / full discoverable test-set = strong) + evidence-coverage reflection.
- **P3:** treat `workspace_diff_empty` / `no_final_verification_output` / no-evidence `unverifiable` as a **reflection round** (bounded ≤3, existing mechanism), not `clean`. (Catches 3d-model, blind-maze.)
- **Eval:** verification-reflection homolog + the 24-row replay. **Baseline** 5/19. **A/B:** P1 alone / P2+P3 alone / all. **Est. flips +4 to +7** (amuse, build-stp, build-cython-ext, audio, bank, blind-maze-5x5).

### L3 — Recovery / issue-ledger lane  ·  owner: Lane-R  ·  parallel with L2
Kill *varied* flailing the current detectors miss.
- **Semantic repeated-action detection:** cluster commands by normalized family (first-N tokens / target file); fire a factual reflection when the last *K* steps show no new passing evidence, no new artifact, and ≥M retries of one cluster. (Catches broken-python `ensurepip`×21, adaptive-rejection ×10.)
- **Exit-0-without-delta flag:** a command that exits 0 but produces no delta/artifact must not count as progress or reset the no-progress window.
- **Eval:** steps-to-completion + no-progress-window precision; baseline = broken-python(40)/adaptive(25) step counts. **Est. flips +1 to +2; ~30–40% step/token savings.**

### L4 — Context / requirement-proof state ledger  ·  owner: Lane-R (with L3)
Maintain `requirement → current evidence → failed checks → disproven assumptions → remaining risk` and surface it in tail telemetry every step (the loop already computes `installed_packages`/`nonzero_exits` at compaction — surface continuously). Fix the stale-plan bug (`_update_plan_text` freezes at step 1 unless an "PLAN"-prefixed line appears). **Est. flips +0 to +1; broad decision-quality gain.**

### L5 — Tool-contract cleanup  ·  owner: Lane-T  ·  parallel with L2/L3
Reduce avoidable friction: heredoc/multiline → write a literal command script + exec (no `eval`); clearer error than bare exit 126; container-aware path policy for task-required absolute paths (boundary-guard friction in acl/aimo); structured **truncation digest** (regex salient lines — `error|Traceback|FAILED|fatal|No such|undefined` — from the dropped middle, since raw-log grep is used 0×). **Est. flips +1 to +3 (mostly efficiency; ancient-puzzle heredoc may flip).**

### L6 — Task-type generic reflection  ·  LAST, only after valid baselines
Generic (no task names): performance-benchmark reflection, numeric-artifact independent comparison, exploration-frontier ledger. Only after L1–L5 isolate the true model-capability floor (aimo formula, bn-fit stats, adaptive numerics, accelerate perf).

---

## Parallelization

### A. Development parallelism (after L1 lands)
| Lane | Phases | Independence | Integration rule |
|---|---|---|---|
| **Lane-V** | L2 (verification-reflection) | touches `verify.py` + finalize path in `loop.py` | shared sentinel board |
| **Lane-R** | L3 + L4 (recovery + state ledger) | touches mirror/delta-feedback + tail telemetry in `loop.py` | shared sentinel board |
| **Lane-T** | L5 (tool-contract) | touches `executor.py`/`tools.py` + envelope digest | shared sentinel board |

L2/L3/L5 may be built concurrently by separate agents, but **all three touch `loop.py`/verify path** — merge on a single integration branch and run **A-only / B-only / A+B** on the shared sentinel board before any promotion (AGENTS.md interaction rule). L4 sequences with L3 (same ledger). L6 is strictly last. **L1 is not parallelizable — it blocks everything** (no valid measurement without it).

### B. Run-execution parallelism (the VM scheduler — task-class aware)
Disk was ~80% full at freeze and `build-linux-kernel-qemu` hit docker rc137 → resource pressure is real. Use a **class-aware scheduler**, max **3 lanes**:
| Lane | Class | Concurrency | Examples |
|---|---|---|---|
| A | light file/data/code, pure-Python | up to ~3 concurrent | analyze-access-logs, assign-seats, bank-trans-filter, audio-synth, break-filter |
| B | build/package (Docker-heavy) | **1 heavy build at a time** | build-cython-ext, build-stp, build-pmars |
| C | service/QEMU/GPU/network/download | **serial; 1 QEMU at a time** | qemu-startup, install-windows-3.11, fibonacci-server, extract-moves-from-video, build-*-qemu |
Caps: ≤3 concurrent Docker containers, 1 QEMU, 1 heavy build. Prune Docker images between tasks + disk guard. Never parallelize blindly — random parallelism creates false failures (port/device/disk clashes).

### C. Run cadence (validation ladder — not full reruns)
1. **micro-smoke (3):** `hello-world` (or simplest), `acl-permissions-inheritance` (known pass), `break-filter-js-from-html` (mount fidelity). Checks: runner imports, `row.json` writes, grader runs, `/tests` mount works.
2. **targeted (10–15):** 5 known passes + measurement/fidelity failures (break-filter, broken-python, broken-networking, build-stp, build-cython-ext) + hard sentinels (qemu-startup, extract-moves-from-video, install-windows-3.11, video-processing). Ask only: did reach-grader improve? did known passes regress? did mount/toolchain issues disappear? truthful row per task?
3. **official checkpoint (89):** only after the **TB 2.0 selector is confirmed**, L1 passes, sentinels pass, scheduler stable.
4. **stress corpus (241/247 core-HEAD):** optional, labelled as stress — not a TB 2.0 score.

---

## Expected aggregate (hypotheses, validate via re-baseline — not promises)
Valid window 21 model-scoreable, baseline 5 passes:
- L1: reach-grader 10%→≥95% (makes score real) + L1-C **+1–2**
- L2 verification-reflection: **+4–7**
- L3/L4 recovery+state: **+2–4**
- L5 tool-contract: **+1–3** (mostly efficiency)
- Harness-addressable total ≈ **+8–12 of 21** (≈24% → ≈60–80%); residual (aimo/bn-fit/adaptive/accelerate) is the **model-capability floor** — needs a stronger model or L6 independent-verification, not harness tweaks. **100% is not reachable by harness alone with this model.**

## Phase status
- [ ] **L1** — Phase-1 agent (tasked now)
- [ ] L2 / L3+L4 / L5 — after L1 re-baseline (parallel lanes)
- [ ] L6 — last
- [ ] Confirm TB 2.0 89-task selector (prerequisite for any "official" checkpoint)
