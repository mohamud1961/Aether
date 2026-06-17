# Run Analysis Case Study

A sanitized example of the run-analysis workflow applied to a real tournament
run. Task names, VM state, harness-specific paths, and internal artifact
addresses have been removed. The causal family analysis structure, evidence
chain method, and competing-hypothesis rejection discipline are the public artifacts.

---

## Context

This case study documents one complete pass of the `analyze` stage of the loop
for a tournament run that produced mostly invalid results due to an environment
failure. The analysis shows:

1. how to freeze the authority surface before concluding;
2. how to separate environment/tooling failures from capability failures;
3. how causal families are constructed with competing-hypothesis rejection;
4. what a validity verdict looks like before capability analysis begins.

---

## Evidence Inventory (freeze before analysis)

**Bundle analyzed (immutable):** a frozen snapshot collected at a known timestamp.
The freeze marker is treated as **provenance only**, not proof of completeness
(per EVIDENCE RULES §8).

> Two freeze-marker facts that turned out to be load-bearing: the VM had been
> up only ~9 minutes at freeze (fingerprint of the reboot that produced the
> contamination), and disk usage was near capacity (an early red-herring —
> the disk-exhaustion hypothesis was raised and **falsified** by logs).

### File-type inventory

| Evidence type | Status | Notes |
|---|---|---|
| Freeze/provenance marker | present | 690 B |
| Run orchestrator script | present | 2.4 KB |
| Progress table | present, complete | 1 row per attempt per task |
| Summary (non-authoritative) | present | **not trusted** per rules |
| Authoritative rows — Attempt 1 | **partial** | Only ~10% produced valid rows |
| Authoritative rows — Attempt 2 | **empty** | Zero rows; legitimately empty |
| Per-task scoreboards | corroborating | Match the authoritative row count |
| Per-task logs | present | Mix of real and crash-only logs |
| Orchestration logs | present | Load-bearing for root cause |
| Error index | present | Index only; not authority |

The per-task authoritative row format was not valid JSONL — it was a
concatenation of pretty-printed files separated by file-path markers, requiring
custom parsing.

### Manifest coverage

The file manifest listed ~30 row paths. The G3-calibration rows were referenced
in the manifest but their **content was not in the bundle** (no tree present;
verified by search). They are therefore unusable as authoritative evidence here.

**Net:** only Attempt-1 real rows and **zero** Attempt-2 rows ever existed. The
coverage gap is a real artifact of the run, not a bundling omission.

### Authoritative-field map

- **AUTHORITATIVE (external grader):** `row_status`, `verifier_exit_code`, `reason`,
  `verifier_stdout_tail`, `verifier_stderr_tail`. Triangulated three ways: combined
  row file, per-task scoreboards, and progress table return codes.
- **ADVISORY (internal verifier):** `loop_result.verifier_clean`. Advisory only;
  preserved separately. Not promotion evidence.
- **`loop_result.grader_reward` is null in every captured row** — do **not** use it.

### Integrity verdict

1. Authoritative grader coverage is ~10% for Attempt 1 and 0% for Attempt 2.
2. Only ~25 Attempt-1 tasks ever executed for real. The other ~95% of attempts
   never ran — they crashed at launch before any task work.
3. The bundle does NOT support a full-population capability scoreboard. It
   supports an authoritative read on ~24 Attempt-1 tasks plus a high-confidence
   harness-integrity diagnosis.
4. Attempt 2 is uniformly contaminated and carries zero scoring weight.
5. Per EVIDENCE RULES §4, every full-population capability rate is
   `INSUFFICIENT_EVIDENCE`; only the small valid sub-population yields
   authoritative outcomes.

---

## Failure Taxonomy — Causal Families

Families are ordered by number of affected attempts. Capability families are computed
only over the valid Attempt-1 rows (small-n).

Taxonomy classes used: environment/runtime, provider/model transport,
sandbox/container setup, tool contract, path/cwd, schema/parsing, evidence
acquisition, reduction/selection, execution/reasoning, process/service/session
persistence, verification/grading, timeout/step-budget, contamination, model
capability, unclear.

---

### F1 — Launch / import-path collapse · **~457 attempts** · confidence HIGH

**Primary class: environment/runtime.** Contributing: process/service/session
persistence; contamination (Attempt 2).

**Size:** ~216 Attempt-1 (every task after the first ~25) + ~241 Attempt-2 = ~457
of 482 attempts (94.8%).

**Signature (byte-identical across all crash attempts):** the harness launch script
imports the harness package at the top of the module with no sys.path bootstrap.
Every crash produced the identical `ModuleNotFoundError` within 2 seconds.

**First material divergence:** process start — crash occurs before argparse, any
container launch, model call, or task work. The progress table records `rc=1` with
elapsed ≤2 s.

**Causal mechanism (evidence-chained):**
1. The tournament orchestrator script died mid-run at a specific task.
2. A ~10-hour gap followed, then a **VM reboot** (fingerprint: `up 9 min` at
   freeze time).
3. An auto-restart mechanism relaunched the tournament immediately, skipping the
   ~25 already-done real runs and racing through all remaining attempts.
4. The relaunch environment lacked the repo root on the module search path, and
   the launch script imports the harness package at module top **with no path
   self-bootstrap**.

**Competing explanations considered and rejected:**
- *Disk exhaustion* (disk was near capacity): **rejected** — crash is a Python
  import error before any container is touched; logs show no "no space left" error.
- *Deleted harness package*: **rejected** — package present in manifest and source
  snapshot; same script imported fine for the ~25 real runs.
- *Code regression in harness*: **rejected** — error is top-level package resolution,
  not a sub-module or attribute error.

**Why this dominates:** it invalidates ~90% of Attempt 1 and 100% of Attempt 2.

> **Note:** F1 is not a model-capability or task-difficulty result. Per the analysis
> discipline ("separate environment/tooling failures from capability failures"), it
> must be repaired before any capability rate is trusted.

---

### F2 — False-positive task completion (agent declares done; grader fails) · **10 valid rows** · MEDIUM

**Primary class: execution/reasoning.** Contributing: verification/grading.

**Size:** 10 of 14 valid `finalize=task_done` Attempt-1 rows failed grading
(the other 4 are the passes). Among captured fails, this is the single largest
**capability** pattern.

**Representative shapes (task details removed):**
- Agent wrote an output in 3 steps and called `task_done`; partial tests passed
  but the completion check failed. Stopped far too early.
- Agent called `task_done` after a setup step, but the install was incomplete.
- Agent called `task_done` after a build, but a required library was not on the
  loader path.

**Common shape:** the agent's own stopping criterion is satisfied while the
externally observable condition is not; the advisory verifier fails to catch it.

---

### F3 — Step/effort exhaustion → implicit stop without completion · **6 valid rows** · MEDIUM

**Primary class: execution/reasoning ↔ timeout/step-budget (task-dependent).**

**Size:** 6 valid Attempt-1 rows finalized with implicit stop and failed.

**Split:** some tasks look budget-bound (hit the step cap); one task stopped at
only 6 steps (algorithmic — speed threshold not met). This family is **not**
uniformly "needs more steps"; it mixes budget pressure with genuine task difficulty.
Low confidence to act on with n=6.

---

### F4 — Advisory verifier over-optimism (false "clean") · **14 valid rows** · MEDIUM-HIGH

**Primary class: verification/grading (advisory layer).**

**Size:** of 21 rows with an advisory verdict, `verifier_clean=True` on 19, but only
5 actually passed → **14 false "clean" verdicts**. The advisory verifier has ~26%
precision and very low recall for real failures on this sample.

**Reading:** the advisory verifier provides almost no usable promotion/keep signal.

**Constraint:** advisory output is **not** promotion evidence (per EVIDENCE RULES §6).
Disagreement with the external grader is preserved, not reconciled.

---

### F5 — Verifier/test-harness execution failure (exit 127) · **2 valid runs** · MEDIUM

**Primary class: verification/grading.** Contributing: environment/runtime.

Two tasks where the test harness depended on a tool (`uv`) that was either absent
or disabled by the task environment itself. **Open question:** is exit 127 a
legitimate "agent didn't repair env" fail, or a grader-design defect? Both are
plausible; needs the run-tests script source to resolve. Classified as
`verification/grading` + flagged for diagnosis.

---

### F6 — Invalid runs: provider / sandbox / filesystem · **3 attempts** · HIGH

- **provider/model transport:** a 400-class rejected request (malformed/oversized/filtered),
  not a capability fail.
- **environment/runtime:** permission error in the harness during artifact/workspace write.
- **sandbox/container setup:** a container build killed by OOM (returncode 137) in ~5 s.

---

### F7 — Timeout / step-budget (real run, no grade) · **1 attempt** · HIGH

One task hit a wall-clock SIGTERM (`rc=143`). Zero-byte log; no result row (killed
before grading) → authoritative outcome **UNCLEAR**.

---

## Family Rollup

| Family | Class (primary) | Attempts | Population | Confidence | Actionable? |
|---|---|---:|---|---|---|
| F1 launch/import collapse | environment/runtime | **~457** | all attempts | HIGH | **Yes — precondition repair** |
| F2 false-positive task_done | execution/reasoning | 10 | valid A1 | MEDIUM | Not yet (need valid baseline) |
| F3 step exhaustion | execution/reasoning | 6 | valid A1 | MEDIUM | Not yet |
| F4 advisory verifier over-optimism | verification/grading | 14 | valid A1 | MED-HIGH | Not yet (advisory ≠ promotion) |
| F5 verifier exec failure | verification/grading | 2 | valid A1 | MEDIUM | Diagnose grader robustness |
| F6 invalid runs | mixed | 3 | A1 | HIGH | Guardrail, not a lane |
| F7 timeout no-grade | timeout/step-budget | 1 | A1 | HIGH | Guardrail |

**No capability family (F2–F5) has adequate evidence to anchor a mechanism:** each
rests on 6–14 rows from a run that is 95% invalid, and the advisory signal (F4) is
unreliable. The only family with decisive evidence and harness-general scope is **F1**.

---

## What This Case Study Demonstrates

### Evidence-freeze before analysis

The evidence inventory was completed and a validity verdict was issued before any
capability analysis began. This is the non-negotiable first step. A run can look
impressive by volume while being nearly useless for capability analysis.

### Competing-hypothesis rejection

For F1, three alternative explanations (disk exhaustion, deleted package, code
regression) were each raised and falsified with specific log evidence. The surviving
explanation is the one that explains all observations without contradiction.

### Environment vs. capability separation

F1 is an environment/runtime failure. Folding those 457 attempts into a capability
rate would produce a number that is 94.8% environmental artifact. The analysis
discipline requires separating these classes before any capability number is trusted.

### Advisory vs. authoritative signal

F4 shows that the advisory verifier (internal, running mid-loop) has ~26% precision
for real failures. It is preserved as a signal but it is not promotion evidence.
The external grader result is the authoritative signal.

### Small-n discipline

With only ~24 valid rows, no capability family has adequate evidence to anchor a
mechanism. This is the correct conclusion to record. The temptation is to find a
"real" insight in the data — but real insights require an adequate denominator.

---

*Task names, VM state, suite-specific paths, and internal artifact addresses
have been removed. The causal family analysis structure, evidence chain method,
and competing-hypothesis rejection discipline are the public artifacts.*
