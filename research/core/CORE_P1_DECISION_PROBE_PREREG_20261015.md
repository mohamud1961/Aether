# P1 — where the wrong finishes go wrong, and decision probes (pre-registration, 2026-10-15)

Follows the GPT-6-Astra / ChatGPT review exchange. Plan agreed with the principal: (1) check from saved data whether the
model noticed the relevant alternative, (2) offline decision probes, (3) fresh task variants that must first
reproduce the failure, (4) binary-extract out of any capability claim (spec defect, terminal-bench-2-1 #194).

## Step 1 result (offline, free): the relevant alternative, per failing class

Read from model text and the artifacts the runs printed (`scratchpad/s1/*.py`). "Noticed" = the model's own
reasoning names the decisive alternative before finishing.

| Class (wrong finishes with traces) | Noticed | What actually went wrong |
|---|---|---|
| construct-assembly, GLM (8) | 8/8 discuss the PDB tag | **4 decided to include the tag, then the artifact dropped it** (b1r3-e2 and s6-r1-e1 state "I'll go with the PDB fasta version" / "including the full fasta (tag included)", then build from the `clover` fpbase variable; s5-x2-e2 decides "include", drifts to fpbase two turns later; s4-b1-e2 states "take fasta seq, strip first M"). 2 decided to drop it (s4-b1-e1, s6-r1-e2). 2 kept the tag and failed elsewhere (s4-x1-e2 X→Y chromophore; s6-x2r-e1 FLAG at index 18, cause not recovered). |
| construct-assembly, GPT-6-Luna (8) | 7/8 | 4 dropped the tag with an explicit justification ("tags aren't functional components"); 4 have the antigen wrong (FLAG not found). |
| net-fit, GLM (11) | format stated correctly in ≥5 | **7 write parent-first under `to,from`**; at least 5 of these had written the correct rule ("write each edge as child,parent"; "for U→Y: Y,U") and then built rows from pgmpy `(parent, child)` tuples (`for to,fr in edges`). One (s6-x2r-e1) re-read its file and misread it. 3 misapply the stated tie-break (M→R). 1 correct DAG, wrong intervened file. |
| binary-extract, GPT-6-Luna (12) | 12/12 | All notice the binary is PIE/ET_DYN with relative addresses and that the example's `0x400000` does not come from this file; all adopt the example's base. Spec defect (#194): excluded from capability claims. |
| seq-assembly (16) | n/a | No single decisive reading: grader Tm span over the annealed region incl. matching overhang (6), BsaI missing from a primer (4), reverse primer has no annealing site (2), clamp before BsaI (2), non-ACGT (1), assembly (1). |
| graph-query-catalog (6) | 1/6 | Failing GLM queries use one department variable for both conditions (passing ones use separate variables). s6-x2r-e1 states "these could be different departments" and still fails. |
| credential-recovery, GLM (2) | — | one wrote `PASSWORD=` prefix; one wrote a 14-character value (GPT-6-Astra's case). |

**Corrections to earlier claims.** (a) "All 8 GLM construct-assembly failures dropped the tag; `flag_idx=0`": wrong — 6/8
dropped it (artifact-confirmed in 3 by the gBlock seq-assembly in the call log, the rest by construct length 821 vs 842 aa
and the build code), 7/8 had `flag_idx=0`. (b) "In all four dominant failures the losing choice is convention over
the task's words": **wrong for GLM.** In GLM net-fit and construct-assembly the reading was right in most runs; the meaning was
lost between the decision and the artifact (a library tuple convention, a stale variable). The pattern holds for
GPT-6-Luna construct-assembly and GPT-6-Luna binary-extract (and the latter is a spec defect). (c) The 81% marker scan was right that
noticing is common (near-universal in construct-assembly and binary-extract), but it hid that about half the GLM failures are
execution losses, which a reading-level rule cannot fix.

Self-checks did not catch the execution losses because they compared the artifact with the same variable that
built it (b1r3-e2: `assert tr[...] == clover`; s6-r1-e1: `rest.find(subs['clover'])`), or misread it.

## Step 2: decision probes (to run; GLM, same deployment and sampling as the runs)

Tool `tools/aether_program/core_decision_probe.py`; cases `scratchpad/probe/cases.json` (24 cases, bundled call
logs). Replays the exact saved request at the decision point; no tools are executed.

- **E cases (execution)**, at the request that produced the first finish: 7 net-fit and 7 construct-assembly failures, 3 controls
  (correct artifacts). Conditions: **A** resample the saved request unchanged (scored: does the reply flag a
  problem); **B** generic "check your delivered files against every requirement" (the kind of finish-time check
  that failed six times); **C** named re-read from the source ("read learned_dag.csv by its header names…";
  "compare each construct-assembly segment with the PDB FASTA as returned…"). Expected: MISMATCH for failures, OK for controls.
- **R cases (resolution)**, at the response that made the decision: construct-assembly tag (2 failures, 2 passing controls),
  net-fit tie-break (2 failures, 1 control). Conditions: **C** boundary named; **D** boundary + rule ("where the task's
  own words specify a format, source or procedure exactly, follow them over library, domain or example
  conventions"). Expected: INCLUDE; R→M and Y→D.
- k = 3 per cell, 195 calls, about 3M input tokens. **Cap $3** (expected ~$1).

**Predictions (recorded before running):**
1. E-bn A flags ≤ 1/3 of samples; E-bn B detects ≤ 30% of failure samples.
2. E-bn C detects ≥ 60% (the file contents are in the context). If C − B ≥ 30 points, the execution losses are
   within the model's capability when the right re-read is asked for: a utilisation problem.
3. E-protein C detects ≤ 50% (the full gBlock is not in context; the model must recall the encoded segment).
4. Controls: false MISMATCH ≤ 1/3 under C.
5. R-tag failures: C gives INCLUDE ≤ 50% (they had already weighed it); D raises INCLUDE by ≥ 30 points.
   Controls stay INCLUDE under both.
6. R-tie-break: C correct ≥ 2/3; D ≈ C.

**What each outcome means.** If (2) holds, the next lever to test is an **artifact re-read against the named
source at write time** (single model, no second model), not a reading principle. If (5) holds, a decision rule
helps the resolution share (GPT-6-Luna construct-assembly, GLM construct-assembly ×2). If neither, the losses are not recoverable by asking
the same model at the decision point, and the remaining levers are tools that make the check mechanical.

## Step 3 (after step 2; needs results): fresh variants

Only for the lever(s) step 2 supports. Fresh small tasks written by us, each first run at baseline to confirm it
**reproduces** the failure (≥ 2/3 wrong at baseline) before any lever is scored, with controls where the
conventional reading is correct. Pre-registered separately.
