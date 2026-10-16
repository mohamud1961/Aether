# P1 serialization test (pre-registration, 2026-10-16)

Status: **SEALED by Claude before any model call.** Authority: the principal's "Investigate the output-writing step
directly: can GLM reliably translate a known-correct graph into the required to,from CSV representation? Test that
separately from graph inference … run this experiment, then audit the final files … archive … deallocate"
(2026-10-16).

## Why

In the matched repair test 15/24 wrong final graphs had every edge reversed against the `to,from` header. Free
pre-look at those rows' write code (archived evidence, before sealing): of the 13 fully reversed rows, 11 have a
recoverable write; 10 write `(a, b)` edge tuples (pgmpy order: parent, child) straight under the `to,from` header, e.g.
`pd.DataFrame(sorted(model.edges()), columns=["to","from"])`, `for to, frm in sorted(edges): f.write(f"{to},{frm}")`.
The tuple's first element (the parent) is labelled `to`. The 11th (e check e2) writes `{child},{par}`, so its
reversal arose upstream (tuple unpacked in the wrong order); not yet read in full. So the question is whether GLM can serialize a correct graph
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

## Results (2026-10-16, the run VM, VM HEAD `e62af8cf4`, all calls/rows valid)

**Custody.** Grader sha `364069f893e336a0` (= the matched test's). Phase 0 oracle 2/2. Archive
`run-evidence/p1-serialization-20261016/p1_serialization_20261016.tgz` (sha256 `8275b7047d8bc3f6…`), extracted to
`audit_output/aether_p1_serialization_20261016/`; audit `sp1audit.py` (scratchpad). 0 infra-invalid, 0 timeouts.
Spend **$0.056** agent rows + < $0.01 text probe. the run VM deallocated.

| Condition | Both graphs correct (grader on final files) | Notes |
|---|---|---|
| text `arrow` | **10/10** | identical file every time |
| text `tuple` (pgmpy `(parent, child)` list) | **10/10** | |
| agent `ser-files` | **5/5** | typed the rows by hand (`write_file`), then `cat` |
| agent `ser-full` | learned **5/5**, both **4/5**; full reward 4/5 | wrote from a Python edge list |

- **ser-full write code:** all 5 rows named the loop variables by role, `for p, c in edges: f.write(f"{c},{p}")`,
  under an edge list commented "(parent -> child)". Compare the matched test's reversed rows:
  `for to, frm in sorted(edges)`, `for a, b in …`, `columns=["to","from"]` over `model.edges()`: the same tuple
  labelled by the file's column names instead of by its role.
- **The one ser-full miss is not serialization:** e4 applied do(Y) by replacing Y's CPD and wrote the intervened
  file from the model's edges, so it kept U→Y; its summary claims "severing U→Y". Claim and file disagree; the
  graded file is what counts.
- No row re-estimated the structure (0 structure-search calls), unlike 36/36 in the matched test.

### Predictions

- **SZ-P1 HELD** (arrow 10/10).
- **SZ-P2 HELD** (ser-files 5/5).
- **SZ-P3 FAILED.** ser-full 4/5 (> 3), and the one failure is the intervention, not a reversal: once the graph is
  supplied with its edge direction named, the code path serializes it correctly too.
- **SZ-P4:** tuple vs arrow reversal 0/10 vs 0/10.

### Conclusion (by the pre-registered rule)

**Serialization is not the bottleneck.** GLM writes a correct, supplied graph in the `to,from` format every time
(25/25 learned files across text and agent conditions), including from code. The reversals occur only when GLM
produces the graph itself: its own edges come out of its inference as unlabelled pairs (`model.edges()`, `(a, b)`),
and at write time it binds them to the file's column names rather than to parent/child. So the failure is in
connecting graph reasoning to file construction, not in knowing the format. A second, smaller loss is the same kind:
the intervention is done on the model while the delivered intervened file is written from different state (here and
in 3 matched rows).

Caveat: n is small (5 per agent arm), and the supplied prompt itself names the direction ("parent → child"), which may
be exactly what prevents the binding error; the next test should check that by supplying the graph *unlabelled*
(e.g. only as a fitted pgmpy model) before proposing any lever. Not run (beyond this sealed scope).
