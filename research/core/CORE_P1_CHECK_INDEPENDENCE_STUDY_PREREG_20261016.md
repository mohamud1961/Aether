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
