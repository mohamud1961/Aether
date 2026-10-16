# P1 serialization test (pre-registration, 2026-10-16)

Status: **SEALED by Claude before any model call.** Authority: the principal's "Investigate the output-writing step
directly: can GLM reliably translate a known-correct graph into the required to,from CSV representation? Test that
separately from graph inference … run this experiment, then audit the final files … archive … deallocate"
(2026-10-16).

## Why

In the matched repair test 15/24 wrong final graphs had every edge reversed against the `to,from` header. Free
pre-look at those rows' write code (archived evidence, before sealing): 13/13 rows with a recoverable write wrote
pgmpy's `(parent, child)` edge tuples straight under the `to,from` header, e.g.
`pd.DataFrame(sorted(model.edges()), columns=["to","from"])`, `for to, frm in sorted(edges): f.write(f"{to},{frm}")`.
The tuple's first element (the parent) is labelled `to`. So the question is whether GLM can serialize a correct graph
at all, and whether it fails only when the graph comes through code objects.

The task's format block is `to,from` / `A,B`; the grader reads by header (`from` = parent, `to` = child), so a
correct file puts the child under `to`.

## Conditions (correct graph always supplied; no inference)

**Text probe (no tools, one API call each; `eval_suite/serialize_p1/text_probe.py`)**, same format block:
- `arrow`: the six edges as "U → M, …" (parent → child). n = 10.
- `tuple`: the same edges as a pgmpy `model.edges()` list of `(parent, child)` pairs. n = 10.
Scored by header (same reading as the grader): correct / reversed / other / bad_header. Scorer validated offline
including a known-reversed file.

**Agent rows (Harbor, Core `coreb1` flags, GLM-5.3-Flash, the run VM, ≤ 3 parallel;
`eval_suite/serialize_p1/generate.py`):**
- `ser-files`: write only the two files; both edge lists (learned and intervened) supplied in arrow form. n = 5.
- `ser-full`: the original task with the recovery step replaced by the supplied DAG ("do not re-estimate");
  fitting, intervention, sampling unchanged. n = 5.
Phase 0: one oracle row per task must score 1.

## Outcomes (from the graded final files)

- **Primary:** both grader graph tests pass (`test_learned_dag_structure`, `test_intervened__data_structure`), read
  from the grader output; failures classified by the grader's extra/missing edges (reversed / other).
- `ser-files` does not produce a sample, so its sample tests fail by design; only graph tests count there.
- Secondary: full reward on `ser-full`; how the file was written (by hand vs from code objects), from the trace.

## Predictions

- **SZ-P1:** `arrow` text ≥ 9/10 correct (GLM can serialize a correct graph in isolation).
- **SZ-P2:** `ser-files` ≥ 4/5 both graph tests pass.
- **SZ-P3:** `ser-full` ≤ 3/5 both graph tests pass, failures mainly reversed (the code-object path).
- **SZ-P4 (descriptive):** `tuple` vs `arrow` reversal rate.

## Decision rule (the principal's)

- Serialization correct in isolation (SZ-P1, SZ-P2 hold) → the failure is in connecting graph reasoning/objects to
  file construction (if SZ-P3 holds, specifically the code path).
- Serialization fails in isolation → serialization itself is the bottleneck.

## Budget

≈ 20 text calls (< $0.05) + 12 rows (≈ $0.02–0.05 each) ≈ $0.4; VM ≈ $0.5. **Hard stop $1 token-priced.** No
expansion without asking. Archive to blob + `audit_output/aether_p1_serialization_20261016/`; deallocate the run VM.
