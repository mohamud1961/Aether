# Aether-Next — Phase 2 FULL Audit (step-by-step, traced)

Date 2026-06-27. Terminal-Bench 2.0, **10 tasks × 2 models**, run on the VM with the
docker-exec runner. Solvers/architects: **gpt-5.4-mini** and **gpt-5.3-codex**. Effort
medium, max_steps 30. Reward = official `test.sh` → `/logs/verifier/reward.txt`.

This audit is built from **full per-step traces** (`--trace-dir`): for every step we
captured what the model *saw* (the context packet), what it *decided* (the solver turn +
per-action intent), what it *observed* (exit codes, stdout/stderr), the architect's full
config/contract, and every completion-gate decision. Raw traces:
`traces_mini/<task>.trace.json`, `traces_codex/<task>.trace.json`. Per-step tables:
appendices `PHASE2_STEPS_MINI.md`, `PHASE2_STEPS_CODEX.md`.

---

## 1. Scorecard (this traced run)

| | mini | codex |
|---|---|---|
| Real reward (grader) | **2 / 10** | **3 / 10** |
| Solved | openssl, constraints | openssl, log-summary, constraints |
| config_invalid (aborts) | 0 | 0 |
| runner crashes | 0 | 0 |
| Architect config **rejected → safety-net default** | **8 / 10** | **0 / 10** |
| Mean steps | 15.7 | 22.1 |
| Repeated commands (total) | 1 | 23 |
| Failed commands (total) | 21 | 73 |
| Authoritative checks the gate actually ran | **0** | **0** |

(Reward varies run-to-run; an earlier untraced run was 3/10 for both. The *mechanics*
below are stable across runs.)

---

## 2. Headline finding: **the verifier is inert — it ran 0 real checks in 20 runs**

Across **all 20 runs**, the completion gate executed **zero** authoritative checks
(`check_results_run = 0`, `used_check_ids = []` at every gate). Every `completed` verdict
was `ready=True` reached purely by **evidence-fallback** — i.e. "the model called
submit and claimed done." Consequences, straight from the traces:

- **False positives:** mini `filter-js`, `gcode`, `log-summary`, `sparql` all reach
  `status=completed` with `ready=True` **and reward 0.0**. The gate rubber-stamped wrong
  solutions because it had nothing to check them against.
- **False negatives:** codex `openssl` produces a correct cert (**grader 1.0**) but never
  calls submit, so the gate never runs → `status=incomplete`. Status and reward are
  effectively **decoupled**; the only ground truth is the external grader.

**Why:** the eval-index surfaces no authoritative checks for these tasks (correct — the
harness must never read the hidden grader), so `planned_checks` is empty (18/20; `fix-git`
had 1, never reached). The architect *does* express success criteria — codex authored
`proof_plan` of **6–9 obligations** and `inspection_plan` of 1–4 per task — but those live
in free-text plans that the gate **never compiles into runnable checks**. The executable
path (`check_plan → planned_checks → check_result`) stays empty, so the gate falls back to
trust. **The model states how it should be verified; the harness doesn't execute it.**

This is the single most important harness gap the trace audit found: the gate's
`ready=True` is a green that, on most tasks, verifies nothing.

---

## 3. Architect performance: model-led config **works with a strong model, fails with a weak one**

The architect (LLM) configures the runtime: capabilities, process mode, workflow policy,
proof/inspection/check plans, model tiers. The traces show a stark split.

**codex architect — genuinely task-adaptive, 0 invalid configs:**
- 0/10 fell back. Every config validated.
- **Workflow contract adapted to the task** (not boilerplate): `reverse_engineer_local`
  for extract-elf, `artifact_extract` for gcode, `explore_first` for fix-git & sparql,
  `optimize_search` for train-fasttext, `direct_build` for the straightforward ones.
- Tight capability selection (3 caps: shell+filesystem+one task-relevant), proof plans of
  3–9 obligations, inspection plans of 1–4. The contracts are *sensible and specific*.
- The direction is right. The only gap is that it doesn't author runnable `check_plan`
  entries (§2).

**mini architect — systematically broken, 8/10 invalid:**
- 8/10 configs **failed validation** with the *same* error: `missing_service_probe` — mini
  sets `require_fresh_probe=True` (or a managed mode) but **forgets to select the
  `service_probe` capability**. A consistent, mechanical mistake.
- All 8 ran on the **guaranteed-default safety net** I added this session (all caps,
  stateless_shell, direct_build). Without that fallback these 8 would have been
  `config_invalid` aborts — the fix is load-bearing for mini.
- On the 2 it got right (gcode, log-summary) it produced a reasonable stateless/direct
  config — so mini's architect is *capable but unreliable*, tripping on one recurring rule.

**Verdict:** the model-led architecture is sound — a capable model drives it well. But the
architect's good intentions (proof plans, adapted workflows) are **not wired through to
execution** (verification, §2), so they don't yet change outcomes.

---

## 4. Solver behavior, step efficiency, and the smarter-model effect

Per-task `steps / commands / repeats / failed / submitted? / arch-fallback? / workflow`:

| task | mini | codex |
|---|---|---|
| constraints-scheduling | 2/1/0/0 ✓sub | 2/1/0/0 ✓sub |
| openssl-selfsigned-cert | **2/1/0/0 ✓sub** | **30/20/9/0 ✗sub** |
| log-summary | 5/2/0/0 ✓sub | 6/1/0/0 ✓sub |
| filter-js | 17/9/1/3 ✓sub | 3/3/0/0 ✓sub |
| gcode-to-text | 4/1/0/0 ✓sub | **30/0/0/0 ✗sub** |
| extract-elf | 30/6/0/3 ✗sub | 30/35/9/11 ✗sub |
| fix-git | 30/9/0/7 ✗sub | **30/61/8/48 ✗sub** |
| raman-fitting | 30/3/0/1 ✗sub | 30/7/0/7 ✗sub |
| sparql-university | 7/0/0/0 ✓sub | 30/9/4/0 ✗sub |
| train-fasttext | 30/7/0/3 ✗sub | 30/30/3/3 ✗sub |

**How a smarter model changed behavior:**

1. **Configuration / decision-making — large improvement.** codex 0/10 invalid configs and
   task-adapted workflows vs mini 8/10 invalid, always-`direct_build`. The stronger model
   *reads the task and designs for it*; the weaker one defaults and mis-specifies.

2. **Step efficiency — got WORSE, not better.** codex mean 22.1 steps vs mini 15.7; codex
   **23 repeated commands vs 1**; **73 failed commands vs 21**. codex explores harder and
   deeper, but on a wall it *churns the full 30 steps* (fix-git: 61 commands, 48 failures)
   instead of stopping or pivoting. mini is terse — it one-shots when it can and otherwise
   goes quiet.

3. **Submission discipline — codex is worse.** The signature case is **openssl**: mini
   solves and submits in **2 steps**; codex solves the identical task but **never submits**,
   running 30 steps of extra verification/polish → marked incomplete despite grader 1.0.
   codex submitted on only 3/10 tasks; mini on 5/10. Thoroughness without a stop condition
   becomes a liability.

4. **Same wall, opposite failure modes (gcode, 1.66 MB input).** mini emits **1** command (a
   quick wrong guess) and submits; codex emits **0** commands in 30 steps — the large file
   floods context and it can't produce a single valid action. Neither solves it, but the
   smarter model is *more* paralyzed by the context-management limit.

**Net:** the smarter model is a better *architect* and *explorer* but a less *efficient*
and less *decisive* solver under this harness. Step efficiency is not monotonic in model
strength — it depends on a stop/submit discipline the harness doesn't currently enforce.

---

## 5. Harness substrate limiters (block a capable model regardless of skill)

- **git "dubious ownership" (fix-git).** Every git command returns exit 128:
  `fatal: detected dubious ownership in repository at '/app/personal-site'`. The container
  runs as root; the bind-mounted workspace is owned by another uid. **Both** models hit it;
  **neither** applied the fix the error message literally prints
  (`git config --global --add safe.directory …`) — so it's a harness substrate bug *and* a
  model recovery gap, but the harness owns it. Fix: set `safe.directory` (or
  `docker run -u`/chown) at container bootstrap. Same root cause produced a transient
  host-side `PermissionError` writing `solution.sparql` (container-root files in a
  host-owned dir).
- **Large-input context flooding (gcode).** A 1.66 MB input degrades the solver loop;
  codex produced 0 actions in 30 steps. Needs size-aware/chunked file handling.
- **Minimal-image tool gaps (extract-elf, sparql, raman).** Models repeatedly invoked tools
  absent from the image — `file`, `python` (only `python3` exists), `rg`, `rdflib`, numpy —
  getting exit 127, and didn't bootstrap-install. Partly model adaptation, but the
  classifier over-labels these `substrate_missing` (harness-ward) when they're mostly model
  behaviour.

---

## 6. What the model saw (perception)

The context packet is well-formed and compact: `open_obligations`, `obligation_status`,
`monitor_alerts`, `live_processes`, `recent_progress`, `failure_clusters`,
`artifacts_present`, `candidate_leaderboard`, `installed_capabilities`, `planned_checks`,
plus the static `kernel_contract` + `task_prompt`. No benchmark/grader leakage (invariant
held). The weak spot: `planned_checks` is almost always empty and `recent_progress` /
`artifacts_present` stay sparse — so the model gets little *verification signal* back about
whether it is converging. This couples directly to §2.

---

## 7. Per-task step-by-step (summary; full tables in the appendices)

- **openssl ✓ (both 1.0).** mini: one shell command builds key+cert+pem+report+script →
  submit → done (2 steps). codex: same correct artifacts but 30 steps of re-verification,
  never submits → incomplete despite 1.0. *Architect fell back (mini) / adapted (codex).*
- **constraints ✓ (both 1.0).** Both one-shot it (1–2 steps) and submit. Cleanest case.
- **log-summary (mini 0 / codex 1.0).** codex's single command produced the correct
  summary; mini's was wrong. Gate "completed" both via evidence-fallback.
- **filter-js (both 0, completed).** mini wrote `filter.py` over 17 steps, gate `ready=True`
  with 0 checks → false positive; codex wrote one in 3 steps, same false-positive path.
- **gcode (both 0).** Large-file limiter; mini 1 wrong command, codex 0 commands.
- **extract-elf (both 0).** Heavy readelf/objdump inspection; codex 35 cmds/11 fails vs
  mini 6 cmds; neither submitted a correct decode. `file` missing (exit 127).
- **fix-git (both 0).** git ownership wall (exit 128) on every git command; codex churned
  61 commands/48 failures, mini 9; neither applied the printed fix; neither submitted.
- **raman (both 0).** numpy/scipy fitting; codex 7/7 commands failed (deps), mini 3; no
  bootstrap-install attempted.
- **sparql (both 0).** Graph querying; mini wrote a query and submitted (wrong); codex
  explored 30 steps, never submitted. `python`/`rdflib` exit 127.
- **train-fasttext (both 0).** Both ran the full 30 steps; the earlier UnicodeDecode crash
  is gone (decode fix holds) — now a clean model-capability miss.

---

## 8. Recommendations (priority order)

1. **Make verification real — compile the architect's proof_plan into executed checks.**
   The model already authors proof/inspection obligations; the gate must run them (as
   shell assertions on the workspace) and require ≥1 passing authoritative check before
   `ready=True`. This closes both the false-positive (claim-only completion) and gives the
   solver real convergence feedback. Biggest single quality lever.
2. **Add a "you may already be done" detector / auto-submit-on-evidence.** Stop a capable
   model (codex openssl) from solving yet never declaring done. If the architect's proof
   obligations are satisfied, prompt or auto-trigger the gate.
3. **Fix the git ownership wall** (`safe.directory` / `-u` / chown at bootstrap) — converts
   fix-git (and any git task) from a harness-blocked zero into a real capability test.
4. **Fix the mini architect's `missing_service_probe` pattern** at the source: when the
   architect requests `require_fresh_probe`, auto-include `service_probe` during
   sanitization (don't even need the fallback). Recovers mini's architect.
5. **Large-input handling** (gcode): size-aware/chunked file presentation so big inputs
   don't zero out the solver.
6. **Reclassify env-adaptation failures**: `file`/`python`/numpy 127s are model-didn't-adapt,
   not `substrate_missing`.
7. **Step-efficiency guardrails for strong models**: a soft "stop exploring / commit"
   nudge to curb codex's 30-step churn and repeated commands.

---

## 9. Bottom line

The two fixes shipped this session (architect-IR fallback, subprocess decode) are proven:
**0 aborts, 0 crashes, 20/20 clean attempts.** The deep trace audit then exposes the next
layer: the **verifier is inert** (0 real checks, status decoupled from reward), the
**model-led architect works** (codex) **but isn't wired to execution**, and a **smarter
model improves design but not step-efficiency or submission discipline** under the current
loop. Fixing verification (rec 1–2) is the highest-value next step — it's also a
No-Fake-Work issue: today a `ready=True`/`completed` can mean nothing was actually checked.
