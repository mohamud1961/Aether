# P1 step 2 — decision probe results (2026-10-15)

Pre-registration: `CORE_P1_DECISION_PROBE_PREREG_20261015.md` (predictions 1–8, amendment). Tool
`tools/aether_program/core_decision_probe.py`; audit mapping `tools/aether_program/core_decision_probe_audit.py`
(every logged call matched back to its case by hash of the replayed context: GLM 213/213, GPT-6-Luna 61/61, 0 unmatched).

- **GLM** (the run VM, managed identity): 213 calls, 0 failed, **$0.423**. Evidence on the VM at
  `<run-dir>/p1old/p1_glm/` (`results.jsonl`, `summary.json`, `audit.jsonl`, call log).
- **GPT-6-Luna** (the run VM): 61 attempts, 1 failed, **$0.385** (lower bound). Evidence at `<run-dir>/p1_luna/`.
- Diagnostic only: B/C/D prompts are written with hindsight; nothing here supports a claim about autonomous runs.

## Scoring: hand labels, not the auto-scorer

The auto-scorer was wrong in both directions and is **not** used for the verdicts:
- E-bn C: most replies detected the reversal, fixed the file, then ended `VERDICT: OK` (as a fixed file should);
  auto counted those as misses. Three replies were empty (≤ 38 output tokens).
- GLM E-prot controls: `FLAG_RE` matched `'MISMATCH'` inside verification code (`'EXACT MATCH' if ok else
  'MISMATCH'`), so auto reported false alarms that the replies never made.
- GPT-6-Luna R-tag-e-e2 shares its decision point with L-prot-e-e2 (the substring matched the last call), so the audit
  maps both to one id; separated by the reply format (DECISION vs VERDICT).

Hand rule: a detection counts if the reply states the actual fault (in text or reasoning), even if it then fixes
it and says OK. "Clear" only; ambiguous replies are not counted.

## Results against the predictions

| # | Prediction | Hand result | Held? |
|---|---|---|---|
| 1 | E-bn A flags ≤ 1/3; B ≤ 30% | A **0/21**; B **3/21** (14%) | yes |
| 2 | E-bn C ≥ 60%; C−B ≥ 30 pts ⇒ utilisation | C **18/21** (86%; 18/18 of non-empty replies); C−B = 72 pts | **yes** |
| 3 | E-prot C ≤ 50% | GLM C **4/21** clear (19%); B 0/21 (all defend the tag drop) | yes |
| 4 | Controls: false MISMATCH ≤ 1/3 under C | GLM net-fit 0/3, GLM construct-assembly 0/6 stated false alarms (replies were checks without a verdict yet, or OK). **GPT-6-Luna construct-assembly 3/3 false alarms** (X → GYG/MYG is not a literal match) | GLM yes; **GPT-6-Luna no** |
| 5 | R-tag fail: C INCLUDE ≤ 50%; D +≥ 30 pts; controls stay INCLUDE | Fail C **2/6**, D **6/6** (+67 pts). Controls C **2/6** (x2-e1 **0/3**: naming the tag flipped a passing run to EXCLUDE), D 5/6 (1 undecided) | fail cases yes; **controls no** |
| 6 | Tie-break: C ≥ 2/3; D ≈ C | C **3/9**, D **3/9** (incl. control: C 1/3, D 2/3) | **no** (D ≈ C yes) |
| 7 | M keeps tag ≥ 2/3; A_build ≤ 1/3 | M **4/9** (coreb1 2/3, r1-e1 0/3, x2-e2 2/3); A_build **0/9** | **no** (direction yes) |
| 8 | GPT-6-Luna R-C ≤ 1/3; D +30 pts; E-C ≤ 1/3 | R-C **4/9**, D **8/9** (+44 pts); E-C 9/9 but controls 3/3 too (not discriminating). Control R: C 2/3, D 3/3 | R-C narrowly no; D yes; E-C no / uninformative |

Failed predictions recorded as failed: 4 (GPT-6-Luna), 5 (controls), 6, 7, 8 (R-C, E-C).

## What it means

1. **GLM net-fit: a utilisation loss, not a capability gap.** The same model, given the file it wrote and asked to read
   it by the header, finds the reversal in 18/18 answered replies; asked generically, 3/21; resampled, 0/21. The
   generic finish check is the kind that failed in the runs. The candidate lever is an **artifact re-read against
   the named format at write time** — but the C prompt names the boundary with hindsight; a lever has to find
   the boundary itself. Step 3 must test that.
2. **GLM construct-assembly: mostly a judgment, defended on re-check.** Asked to compare segments with the PDB FASTA, GLM
   detects the tag drop in 4/21 and otherwise justifies it ("the canonical construct-assembly, not the purification tag").
   A boundary question alone **hurts**: it moved a passing control to EXCLUDE 3/3. The explicit rule (follow the
   task's named source over convention) gives INCLUDE in 11/12 fail+control samples. The rule changes the answer;
   naming the issue without it does not.
3. **Context loss is a partial cause.** At the build call, A_build kept the tag 0/9; carrying the run's own earlier
   words kept it 4/9 (in r1-e1 the carried note did not change the build). Real but not sufficient; the earlier
   claim that keeping decisions in context would fix it is not supported at the predicted strength.
4. **Tie-break is a reasoning error.** GLM misapplies "first letter is the child" in about two thirds of samples,
   including on a passing control, and the rule does not help. Not an interpretation problem.
5. **GPT-6-Luna differs.** GPT-6-Luna's generic check (B) flags the tag drop in 4/9 with 0/3 control false alarms; the named
   comparison (C) flags everything, controls included, because the chromophore X can never match literally. The
   rule (D) gives INCLUDE 11/12. GPT-6-Luna's antigen misses were not detected under any condition. e-e2 is confounded:
   with its (wrong) H-Ras antigen, including the tag exceeds the 3,000-nt limit, which GPT-6-Luna reports in C/D.

## GLM reasoning tokens (offline, 2,839 run calls; plus probe replies)

- Reported reasoning tokens track the reasoning text (3.33 chars/token, 0 mismatches); no hidden reasoning.
- 55–69% of calls carry ≤ 20 reasoning tokens on the b1r3, s4 and s6 boards (s5: 28%).
- Right finishes: median 11 calls, 31 reasoning tokens/call, near-zero share 0.44. Wrong finishes: median 23
  calls, 14.5 tokens/call, near-zero share 0.56. The finish step carries ~5 reasoning tokens in both.
- Build-step reasoning does not separate right from wrong (net-fit failing 37–2,463, passing 15; construct-assembly failing 0,
  0, 36 … 1,058, passing 28, 652).
- In the probes GLM spends 0–16k reasoning tokens per reply; the long C/D replies are where the reversal is
  found. Effort is not the missing ingredient at finish — the named re-read is.

## Step 3 (not started; user said test, audit, stop)

Only levers supported here: (a) a write-time re-read of an artifact against the format/source the task names,
which the agent must locate without hindsight; (b) a source-over-convention rule, tested on controls where the
conventional reading is the right one. ChatGPT's condition stands: carried decisions must remain revisable when
they are wrong. Fresh tasks must reproduce the failure at baseline (≥ 2/3) before any lever is scored.
