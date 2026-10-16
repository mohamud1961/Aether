# Check-independence study (offline, archived traces only) — pre-registration (2026-10-16)

Status: **sealed before any check is classified or counted.** No VM, no model calls. Follows the Experiment 1 reviews
(Codex: "classify which checks reuse raw tuple order and which check a separate source/constraint, and whether the
agent changes the artifact after a contradiction").

## Question

When GLM checks the edge file it wrote, does the check use a direction fact that does **not** pass through its own
reading of tuple order? And are reversals repaired when, and only when, such a check exists?

## Population

Every archived graph-export row in which the solver itself maps edges into `learned_dag.csv`:
role experiment (pilot 12 + main 36), matched repair (36), step 2 (16), step 4 (4), B1/S4/S5/S6 (12), worldclass
(6, if GLM). GPT-6-Luna L1/L2 (4) reported separately as a reference. Serialization (graph supplied) excluded.
Outcome = the grader's verdict on the final learned file (`check.json` for role rows; `test_learned_dag_structure`
for the others, reversed = extra edges into U, as in the context study).

## Classes (per check = any tool call after a learned_dag write that reads the written file or tests the graph)

- **I (independent direction):** reads the written file **by header name** and compares it with a direction fact
  obtained without positional tuple reading: `get_parents`/`predecessors`/`successors`/`get_children`, CPD
  `evidence`/`variables`, `in_degree`/`in_edges`, the intervention constraint "no incoming edges to X", or a
  directional statement in the task.
- **T (tuple compare):** compares file contents with `model.edges()`-style tuples (positional or by header). Shares
  the tuple-order binding, so it cannot catch a reversal the writer made with the same binding.
- **V (view):** prints/cats the file, no programmatic comparison.
- **M (model only):** tests the in-memory model, not the file.
Row label = strongest class present after the **last** write (I > T > V > M > none). Regex extraction, then **every
I-labelled row, every reversed-final row and every multi-write row is hand-read**; disagreements are recorded.

## Predictions

- **K-P1 (rarity):** ≤ 20% of GLM rows contain an I check after any learned_dag write.
- **K-P2 (reversals survive non-independent checks):** of final-reversed GLM rows, ≤ 10% have an I check after the
  last write.
- **K-P3 (repair link):** of GLM rows whose file went reversed → correct within the run, ≥ 50% had an I check or
  another independent contradiction (hand-read) between the reversed write and the repair.
- **K-P4 (descriptive):** count of T checks that preceded a reversed→correct repair.

Failed predictions are recorded as failed. Scripts and per-row labels are archived next to the results.

## Results (2026-10-16, appended after classification; predictions above unchanged)

**Custody.** Scripts, automatic per-row output and hand labels in `audit_output/aether_p1_checkindep_20261016/`
(`chkaudit.py`, `timeline2.py`, `showcand.py`, `rows_auto.json`, `candidates.json`, `hand_labels.json`). 122 GLM
rows + 4 GPT-6-Luna rows; 2 GLM rows never wrote the file. Final verdicts: 70 correct, 39 reversed, 17 other (all 126).

**Method deviations (disclosed).**
1. The pre-registered regex for I missed checks written as `t != 'U'` / `r[0] != 'U'` (column index consistent with
   the header). I widened the candidate net (any check that reads the file and compares against a node literal or a
   parent/predecessor API, 35 GLM rows) and **hand-read every candidate**. Hand-reading also split the I class:
   **IH** = the fact is applied with the header's meaning; **IP** = the same fact applied through the writer's own
   binding (e.g. `nx.DiGraph(df.itertuples())`). The predictions are scored on IH (the class the prereg intended:
   "reads the written file by header").
2. Repairs were found from printed readbacks (decoded by header) plus a reasoning-text detector
   (reversed/swapped/inverted…), then hand-read. A readback parser bug (sample header glued onto an edge list) was
   fixed before scoring. Repairs that left no printed file and no such words are not visible.
3. K-P3 counts **solver-written** reversals. In matched-repair rows a reversed *starting* file is task state; those
   repairs are reported separately.

**K-P1 HELD.** IH checks after a write: **9/122 GLM rows (7%)**. GPT-6-Luna: 0/4 (views only; never reversed).

**K-P2 HELD.** Final-reversed GLM rows with an IH check after the last write: **0/39**. Their strongest check: view
only 29, tuple compare (T) 6, IP 1 (+1 IP inside a T row), model-only 1, none 2. Every IP check that ran on a reversed
file **passed it** (3 instances, `hand_labels.json`).

**K-P3 HELD.** Solver-written reversal → repaired within the run: **9 rows**; **7/9** had an independent
contradiction first:
- IH file check failed on the reversed file: **3** (role g1-tofrom-named e3, matched k1-check e1, step-4 contract4 e1).
  Every IH check that ran on a reversed file failed it and was followed by a repair (3/3).
- Task fact ("U has no parents") noticed in reasoning: **2** (one during a CLM context condensation).
- Step-2 harness check-tool message: **2** (final learned graph still "other" in both).
- Self-review of its own code, no independent check: **2** (both base `to,from` role rows).

**K-P4 (descriptive).** 0 repairs were triggered by a T or IP check. In 2 of the 3 IH repairs a T/IP check had
already passed the reversed file earlier in the same run.

**Also observed.** Two rows (s5 x2 e1, step-4 reviewerp4 e2) made the same binding error in the opposite direction (passed
`to,from` tuples into pgmpy as `(parent, child)`) and caught it by printing CPDs whose parents contradicted the intended
graph. Matched-repair rows repaired reversed starting files by re-deriving the graph and applying the task's
"U has no parents" (task state, not counted above).

**Reading.** On this board GLM's file checks mostly re-use the binding that produced the file (views, tuple compares,
positional graphs) and therefore pass reversed files. The few checks that apply a direction fact with the header's
meaning are rare (7%) but were decisive every time they met a reversed file (3/3 caught, 3/3 repaired, 0 false
passes), and most repairs (7/9) follow some independent contradiction. This is observational: rows that wrote IH
checks may differ in other ways, n is small (3 decisive IH events), and it is one task family. No mechanism is
proposed here; a causal test would have to vary whether such a check is made, not observe it.
