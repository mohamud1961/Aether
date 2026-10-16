# P1 Experiment 1: named semantic roles at the graph-to-file boundary (pre-registration, 2026-10-16)

Status: **SEALED by Claude before any model call.** Authority: the principal's "go, run experiment 1, audit it, deallocate
after" (2026-10-16), after the context-study reviews (Codex audit; ChatGPT reviews of the revised design).

## Question

When GLM must turn a library's **positional** pairs into a file with **named** columns, does one generic instruction
to name positional roles and map them explicitly (the model creates the roles; the harness supplies none) reduce
reversed files, without harming the format GLM already writes correctly?

Claim scope (agreed with the reviews): a positive result shows a model-generated representation habit helps this one
transformation. It does not show autonomous graph inference improves, or that the model selects the relevant meaning
on unfamiliar tasks.

## Tasks (`eval_suite/role_p1/generate.py`, deterministic)

- Source: `/app/bn_model.py` builds a fitted pgmpy `LinearGaussianBayesianNetwork` from `/app/data.csv`; the edge
  list exists only as pgmpy's positional pairs. **Neither the prompt nor the module states the pair order** (same
  for both arms; pgmpy's order is parent, child). "Do not re-estimate its structure."
- Steps: write the DAG to `learned_dag.csv`; intervene on a named node (do = 0.0); write `intervened_dag.csv`.
- **Fresh graphs** (no earlier node names): g1 (5 nodes, 5 edges, do(T)), g2 (6/6, do(J)), g3 (5/5, do(F)).
- **Both column orders:** `tofrom` (header `to,from`: the reversal-prone order) and `fromto` (header `from,to`: an
  "always swap" habit fails here).
- **Arms:** `base` (task text only) and `named` (+ one generic paragraph, identical in every task: "When you work with
  structured values whose positions carry meaning (pairs, tuples, rows, columns), give each position a name that
  states its role where you create or receive the value, and when you write the value in another format, map each
  named role to the target field explicitly.").
- Image `alexgshaw/net-fit:20251031` + pinned `pgmpy==1.1.2 pandas==3.0.6 numpy==2.5.4` (the versions the
  agents installed themselves earlier), same in every task. Agent timeout 1200 s. Core `coreb1` flags, GLM-5.3-Flash,
  the run VM, ≤ 3 parallel.
- **Checker** (`tests/check.py`, stdlib only): reads each file by header names (`from` = parent, `to` = child, as the
  original grader did), classifies learned and intervened as correct / reversed / other / unreadable; header order
  recorded separately. Validated offline before sealing: **72/72** fixtures as expected (good, fully reversed, other
  column order, intervention not applied, quoted, missing × 12 tasks); oracle solutions pass **12/12** locally.

## Phases

- **Phase 0 (free):** 12 oracle rows must score 1; in each task image `from bn_model import model` must import and
  `model.edges()` must equal the true edge set.
- **Phase 1 — pilot gate:** `base` × `tofrom` × 3 graphs × 4 episodes = 12 rows. **Gate: ≥ 3/12 learned files
  reversed.** If not met: **stop**, record the fixture as not diagnostic (not as evidence that named roles do not
  help), no redesign tonight. Pilot rows are not pooled into Phase 2.
- **Phase 2 (only if the gate passes):** 12 tasks × 3 episodes = 36 rows.

## Outcomes and predictions (Phase 2, from the graded files)

- **R-P1 (primary):** on `tofrom`, named reversals ≤ base reversals − 3 (of 9 rows each).
- **R-P2 (harm):** on `fromto`, named learned files not correct ≤ base + 1 (of 9 each).
- **R-P3 (adherence, from the write code):** ≥ 7/18 `named` rows map named roles (parent/child or equivalent) to the
  target fields in the code that writes `learned_dag.csv`; base measured the same way. Rows that adhered but still
  wrote a wrong file are reported (naming ≠ correct meaning).
- **R-P4 (descriptive):** intervened-file correctness by arm.
- **R-P5 (cost):** named mean cost/row ≤ 1.3 × base.
- Results are reported per graph and format (repeats on one graph are not independent tasks).

## Budget

≈ 60 rows × $0.005–0.02 ≈ $0.6; VM ≈ $0.5. **Hard stop $1.5 token-priced.** No expansion without asking. Archive to
blob + `audit_output/aether_p1_role_20261016/`; deallocate the run VM.

## Results (2026-10-16, appended after the run; predictions above unchanged)

**Custody.** Archive `p1-role-20261016/p1_role_20261016.tgz` (sha256 prefix `7bad4ec1f46ab364`), local copy
`audit_output/aether_p1_role_20261016/`. Checker validated on fixtures before any call (72/72); oracle 12/12;
image import check 12/12. All verdicts below are the stdlib checker's reading of the **final files**
(`check.json`); adherence is read by hand from the code that last wrote `learned_dag.csv` (audit script
`rp2audit.py` locates it; its regex style labels were corrected by hand, see below). 0 timeouts, 0 infra-invalid.
VM the run VM deallocated (verified).

**Pilot gate.** base × tofrom, 3 graphs × 4 episodes: **6/12 reversed** (≥ 3 needed) → passed.

**Phase 2 (36 rows), learned-file verdicts; intervened verdict equalled learned in every row:**

| | g1 | g2 | g3 | total |
|---|---|---|---|---|
| base tofrom reversed | 1/3 | 0/3 | 2/3 | **3/9** |
| named tofrom reversed | 0/3 | 1/3 | 0/3 | **1/9** |
| base fromto correct | 3/3 | 3/3 | 3/3 | 9/9 |
| named fromto correct | 3/3 | 3/3 | 3/3 | 9/9 |

**Adherence (hand-read).** Named rows whose write code binds role-named positions (parent/child, src/dst,
from_node/to_node, frm/to, edge_to/edge_from) to the target fields: **tofrom 8/9, fromto 5/9 → 13/18**. Non-adherent:
`pd.DataFrame(model.edges(), columns=…)` (3), `{'to': v, 'from': u} for u, v` (1), hand-typed rows (1). Base: **0/18**
(the regex's one base "role-named" hit, g2-tofrom e2, is `for u,v` → false positive).

**Adherent but wrong (1/13): g2-tofrom-named e1.** The model named the roles and wrote a docstring, but bound them
wrongly: "position 0: `to` (the child…)", `for edge_to, edge_from in edges` over `model.edges()`, which is
(parent, child). Naming faithfully transmitted a wrong reading of the **source** convention.

**Base reversals have the same shape.** 2/3 are `[(t,f) for t,f in edges]` over `sorted(model.edges())` (positions
named after the target columns, i.e. the wrong roles), 1/3 is `pd.DataFrame(sorted(model.edges()), columns=['to','from'])`.
Correct base tofrom rows all swap positionally (`for u,v …: (v,u)`).

**Predictions.**
- **R-P1 FAILED.** named 1/9 vs base 3/9 = −2; needed −3. Direction favours named; n too small to separate.
- **R-P2 HELD.** fromto not-correct 0 vs 0.
- **R-P3 HELD.** 13/18 adherent (≥ 7). 12/13 adherent rows correct; 4/5 non-adherent rows correct.
- **R-P4 (descriptive).** Intervened files track learned files exactly in both arms.
- **R-P5 FAILED.** named $0.00364/row vs base $0.00249/row = **1.47×** (limit 1.3×). Cost rise is mostly tofrom
  (named $0.038 vs base $0.019 for 9 rows: longer code, docstrings, self-check asserts).

**Spend.** Token-priced $0.110 (Phase 2) + $0.038 (pilot) ≈ **$0.15**, under the $1.5 hard stop. Pilot + Phase 2 base
tofrom combined (descriptive, not pooled for any prediction): 9/21 reversed.

**Reading.** The guidance is followed (13/18) and does not harm the format GLM already gets right, but the reversal
reduction (3→1 of 9) is below the pre-registered bar and costs ~1.5×. The remaining error is not a missing name but a
wrong **source** binding (what does position 0 of `model.edges()` mean?), which naming alone does not check. That
points the next question at grounding the source convention (e.g. the model verifying the source's meaning against
something observable) rather than at more naming; no new mechanism is proposed here.
